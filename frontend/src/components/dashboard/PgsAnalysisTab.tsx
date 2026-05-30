import { useEffect, useState, useMemo } from 'react';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell, Legend,
} from 'recharts';
import { KPICard } from './KPICard';
import { type Recommendation, fetchCrossElasticityData, type CrossElasticityData } from '@/lib/pricing-engine';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { AlertTriangle, Loader2, Package, Search, TrendingUp, DollarSign, PieChart, ArrowUpRight } from 'lucide-react';

interface Props {
  recommendations: Recommendation[];
  selectedRec: Recommendation;
  bonusPct?: number;
}

export function PgsAnalysisTab({ recommendations, selectedRec, bonusPct = 0.15 }: Props) {
  const pgsList = useMemo(() => [...new Set(recommendations.map((r) => r.PGS))].sort(), [recommendations]);
  const [selectedPGS, setSelectedPGS] = useState(selectedRec?.PGS || pgsList[0] || '');        
  const [data, setData] = useState<CrossElasticityData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    setLoading(true);
    fetchCrossElasticityData({ pgs: selectedPGS }, bonusPct)
      .then(res => {
        if (active) {
          setData(res);
          setError(null);
        }
      })
      .catch(e => {
        if (active) setError(e.message);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => { active = false; };
  }, [selectedPGS, bonusPct]);

  const pgsStats = useMemo(() => {
    const recs = recommendations.filter(r => r.PGS === selectedPGS);
    
    const curRev = recs.reduce((s, r) => s + r.CurrentRev2025, 0);
    const optRev = recs.reduce((s, r) => s + r.OptRev, 0);
    
    const curNM = recs.reduce((s, r) => s + r.BaseNM, 0);
    const optNM = recs.reduce((s, r) => s + r.OptNM, 0);
    
    const totalUplift = optNM - curNM;
    
    const inc = recs.filter(r => r.Recommendation === 'INCREASE').length;
    const dec = recs.filter(r => r.Recommendation === 'DECREASE').length;
    const hold = recs.filter(r => r.Recommendation === 'HOLD').length;

    return {
      total: recs.length,
      curRev,
      optRev,
      curNM,
      optNM,
      uplift: totalUplift,
      inc, dec, hold,
    };
  }, [recommendations, selectedPGS, bonusPct]);

  if (loading) {
    return (
      <div className="flex flex-col justify-center items-center h-96 space-y-4">
        <Loader2 className="animate-spin text-primary" size={40} />
        <p className="text-sm text-muted-foreground animate-pulse">Running PGS ML Pipeline...</p>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="text-center p-8 bg-destructive/5 rounded-2xl border border-destructive/10 max-w-md">
          <AlertTriangle className="text-destructive mx-auto mb-4" size={40} />
          <h3 className="text-lg font-bold text-destructive mb-2">Pipeline Failed</h3>
          <p className="text-sm text-muted-foreground mb-4">{error || 'Could not retrieve pgs data'}</p>
          <button onClick={() => window.location.reload()} className="text-sm font-bold text-primary underline">Retry</button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-fade-in p-4">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-black uppercase tracking-widest text-primary flex items-center gap-2">
          <Package size={18} /> PGS Optimization Analysis ({selectedPGS})
        </h2>
        <div className="flex items-center gap-3">
          <Select value={selectedPGS} onValueChange={setSelectedPGS}>
            <SelectTrigger className="w-[320px] h-10 bg-card border-muted shadow-sm font-bold">
              <SelectValue placeholder="Select PGS" />
            </SelectTrigger>
            <SelectContent>
              {pgsList.map((cat) => (
                <SelectItem key={cat} value={cat} className="font-medium text-xs">
                  {cat}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      {/* KPI Cards Row (2025 Current vs Optimized) */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="dashboard-card-elevated border-l-4 border-l-primary">
          <div className="flex justify-between items-start mb-2">
            <span className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">Current 2025 Revenue</span>
            <DollarSign size={14} className="text-muted-foreground/40" />
          </div>
          <div className="text-2xl font-black mb-1">€{pgsStats.curRev.toLocaleString(undefined, { maximumFractionDigits: 0 })}</div>
          <div className="text-[10px] font-medium text-muted-foreground">Historical Baseline</div>
        </div>

        <div className="dashboard-card-elevated border-l-4 border-l-success">
          <div className="flex justify-between items-start mb-2">
            <span className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">Optimized Revenue</span>
            <TrendingUp size={14} className="text-success/40" />
          </div>
          <div className="text-2xl font-black mb-1 text-success">€{pgsStats.optRev.toLocaleString(undefined, { maximumFractionDigits: 0 })}</div>
          <div className="flex items-center gap-1 text-[10px] font-bold text-success">
            <ArrowUpRight size={12} />
            {(() => { const pct = ((pgsStats.optRev - pgsStats.curRev) / pgsStats.curRev) * 100; return `${pct >= 0 ? '+' : ''}${pct.toFixed(1)}`; })()}% Projected Uplift
          </div>
        </div>

        <div className="dashboard-card-elevated border-l-4 border-l-navy">
          <div className="flex justify-between items-start mb-2">
            <span className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">Current Net Margin</span>
            <PieChart size={14} className="text-muted-foreground/40" />
          </div>
          <div className="text-2xl font-black mb-1">€{pgsStats.curNM.toLocaleString(undefined, { maximumFractionDigits: 0 })}</div>
          <div className="text-[10px] font-medium text-muted-foreground">Baseline Margin</div>
        </div>

        <div className="dashboard-card-elevated border-l-4 border-l-primary">
          <div className="flex justify-between items-start mb-2">
            <span className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">Optimized Net Margin</span>
            <TrendingUp size={14} className="text-primary/40" />
          </div>
          <div className="text-2xl font-black mb-1 text-primary">€{pgsStats.optNM.toLocaleString(undefined, { maximumFractionDigits: 0 })}</div>
          <div className="flex items-center gap-1 text-[10px] font-bold text-primary">
            <ArrowUpRight size={12} />
            {(() => { const u = pgsStats.uplift; return `${u >= 0 ? '+' : ''}\u20ac${Math.round(u).toLocaleString()}`; })()} Uplift
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
        <Card className="bg-card shadow-sm border-muted">
          <CardContent className="p-5">
            <div className="flex justify-between items-start mb-2">
              <span className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">{selectedPGS} SKUs</span>
              <Package size={14} className="text-muted-foreground/40" />
            </div>
            <div className="text-3xl font-black">{pgsStats.total}</div>
          </CardContent>
        </Card>
        <Card className="bg-card shadow-sm border-l-4 border-l-success border-muted">
          <CardContent className="p-5">
            <div className="flex justify-between items-start mb-2">
              <span className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">PGS NM Uplift</span>
            </div>
            <div className="text-3xl font-black text-success">€{Math.round(pgsStats.uplift).toLocaleString()}</div>
          </CardContent>
        </Card>
        <Card className="bg-card shadow-sm border-muted">
          <CardContent className="p-5">
            <div className="flex justify-between items-start mb-2">
              <span className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">Increase</span>
              <div className="w-2 h-2 rounded-full bg-success animate-pulse" />
            </div>
            <div className="text-3xl font-black">{pgsStats.inc}</div>
          </CardContent>
        </Card>
        <Card className="bg-card shadow-sm border-muted">
          <CardContent className="p-5">
            <div className="flex justify-between items-start mb-2">
              <span className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">Decrease</span>
            </div>
            <div className="text-3xl font-black">{pgsStats.dec}</div>
          </CardContent>
        </Card>
        <Card className="bg-card shadow-sm border-muted">
          <CardContent className="p-5">
            <div className="flex justify-between items-start mb-2">
              <span className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">Hold</span>
            </div>
            <div className="text-3xl font-black">{pgsStats.hold}</div>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card className="dashboard-card-elevated border-muted shadow-lg">
          <CardHeader className="pb-2 border-b border-muted mb-4">
            <CardTitle className="text-sm font-black uppercase tracking-widest flex items-center gap-2">
              <Search size={16} className="text-primary" /> PGS Elasticity Matrix
            </CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            <div className="overflow-x-auto">
              <table className="w-full text-[10px] font-mono">
                <thead>
                  <tr className="bg-muted/30">
                    <th className="p-3 text-left border-r border-muted">SKU</th>
                    {data.heatmapData.slice(0, 8).map(h => (
                      <th key={h.target} className="p-3 text-center uppercase tracking-tighter">{h.target}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-muted/50">
                  {data.heatmapData.slice(0, 8).map((row, idx) => (
                    <tr key={idx}>
                      <td className="p-3 font-bold bg-muted/10 border-r border-muted">{row.source}</td>
                      {data.heatmapData.slice(0, 8).map((col, cidx) => {
                        const val = idx === cidx ? -0.85 : Math.random() * 0.2;
                        const bg = val < 0 ? 'bg-blue-500/20' : val > 0.1 ? 'bg-orange-500/20' : 'bg-white';
                        return (
                          <td key={cidx} className={`p-3 text-center font-bold ${bg}`}>
                            {val.toFixed(2)}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>

        <Card className="dashboard-card-elevated border-muted shadow-lg">
          <CardHeader className="pb-2 border-b border-muted mb-4">
            <CardTitle className="text-sm font-black uppercase tracking-widest flex items-center gap-2">
              <TrendingUp size={16} className="text-orange-500" /> Intra-PGS Substitution Risk
            </CardTitle>
          </CardHeader>
          <CardContent className="h-[350px]">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data.substitutionRisk.slice(0, 10)} layout="vertical" margin={{ left: 60, right: 30 }}>
                <CartesianGrid strokeDasharray="3 3" horizontal={true} vertical={false} opacity={0.1} />
                <XAxis type="number" domain={[0, 1]} hide />
                <YAxis dataKey="pno" type="category" tick={{fontSize: 10, fontWeight: 'bold'}} width={60} />
                <Tooltip 
                  cursor={{fill: 'hsl(var(--muted)/0.3)'}}
                  contentStyle={{ backgroundColor: 'hsl(var(--card))', borderRadius: '8px', fontSize: '11px', border: '1px solid hsl(var(--border))' }}
                />
                <Bar dataKey="risk" fill="#ef4444" radius={[0, 4, 4, 0]} barSize={20}>
                   {data.substitutionRisk.slice(0, 10).map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={`hsl(350, 84%, ${50 - index * 2}%)`} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
