import { useMemo, useState } from 'react';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell, Legend
} from 'recharts';
import { KPICard } from './KPICard';
import { type Recommendation, type ModelInfo } from '@/lib/pricing-engine';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { TrendingUp, Zap, BarChart3, Info, Award, DollarSign, PieChart, ArrowUpRight, Package } from 'lucide-react';

interface Props {
  recommendations: Recommendation[];
  model: ModelInfo;
  bonusPct?: number;
}

export function BrandAnalysisTab({ recommendations, model, bonusPct = 0.15 }: Props) {
  const brands = useMemo(() => [...new Set(recommendations.map((r) => r.Brand))].sort(), [recommendations]);
  const [selectedBrand, setSelectedBrand] = useState<string>('all');

  const brandStats = useMemo(() => {
    const stats = brands.map((brand) => {
      const brandRecs = recommendations.filter((r) => r.Brand === brand);
      
      const curRev = brandRecs.reduce((s, r) => s + r.CurrentRev2025, 0);
      const optRev = brandRecs.reduce((s, r) => s + r.OptRev, 0);
      
      const curNM = brandRecs.reduce((s, r) => s + r.BaseNM, 0);
      const optNM = brandRecs.reduce((s, r) => s + r.OptNM, 0);
      
      const totalUplift = optNM - curNM;
      const avgChg = brandRecs.reduce((s, r) => s + r.RecChange, 0) / brandRecs.length;
      
      return {
        brand,
        skus: brandRecs.length,
        curRev,
        optRev,
        curNM,
        optNM,
        uplift: totalUplift,
        avgChg: avgChg * 100
      };
    }).sort((a, b) => b.uplift - a.uplift);
    return stats;
  }, [recommendations, brands, bonusPct]);

  const portfolioStats = useMemo(() => {
    const filtered = selectedBrand === 'all' ? brandStats : brandStats.filter(b => b.brand === selectedBrand);
    
    return {
      curRev: filtered.reduce((s, b) => s + b.curRev, 0),
      optRev: filtered.reduce((s, b) => s + b.optRev, 0),
      curNM: filtered.reduce((s, b) => s + b.curNM, 0),
      optNM: filtered.reduce((s, b) => s + b.optNM, 0),
      uplift: filtered.reduce((s, b) => s + b.uplift, 0),
    };
  }, [brandStats, selectedBrand]);

  const filteredData = useMemo(() => {
    if (selectedBrand === 'all') return brandStats;
    return brandStats.filter(b => b.brand === selectedBrand);
  }, [brandStats, selectedBrand]);

  const top10Uplift = useMemo(() => brandStats.slice(0, 10), [brandStats]);

  return (
    <div className="space-y-6 animate-fade-in p-2">
      <div className="flex items-center justify-between bg-card p-4 rounded-xl border border-muted shadow-sm">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-primary/10 rounded-lg">
            <Award className="text-primary" size={20} />
          </div>
          <div>
            <h2 className="text-lg font-bold leading-none">Brand Performance</h2>
            <p className="text-xs text-muted-foreground mt-1">Optimization impact across your brand portfolio</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-xs font-bold text-muted-foreground uppercase tracking-wider">Focus Brand:</span>
          <Select value={selectedBrand} onValueChange={setSelectedBrand}>
            <SelectTrigger className="w-[280px] h-10 bg-muted/50 border-none font-bold">
              <SelectValue placeholder="All Brands" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all" className="font-bold">All Brands Portfolio</SelectItem>
              {brands.map((b) => (
                <SelectItem key={b} value={b} className="font-medium">
                  {b} ({recommendations.filter(r => r.Brand === b).length} SKUs)
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
          <div className="text-2xl font-black mb-1">€{portfolioStats.curRev.toLocaleString(undefined, { maximumFractionDigits: 0 })}</div>
          <div className="text-[10px] font-medium text-muted-foreground">Historical Baseline</div>
        </div>

        <div className="dashboard-card-elevated border-l-4 border-l-success">
          <div className="flex justify-between items-start mb-2">
            <span className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">Optimized Revenue</span>
            <TrendingUp size={14} className="text-success/40" />
          </div>
          <div className="text-2xl font-black mb-1 text-success">€{portfolioStats.optRev.toLocaleString(undefined, { maximumFractionDigits: 0 })}</div>
          <div className="flex items-center gap-1 text-[10px] font-bold text-success">
            <ArrowUpRight size={12} />
            +{(((portfolioStats.optRev - portfolioStats.curRev) / portfolioStats.curRev) * 100).toFixed(1)}% Projected Uplift
          </div>
        </div>

        <div className="dashboard-card-elevated border-l-4 border-l-navy">
          <div className="flex justify-between items-start mb-2">
            <span className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">Current Net Margin</span>
            <PieChart size={14} className="text-muted-foreground/40" />
          </div>
          <div className="text-2xl font-black mb-1">€{portfolioStats.curNM.toLocaleString(undefined, { maximumFractionDigits: 0 })}</div>
          <div className="text-[10px] font-medium text-muted-foreground">Baseline Margin</div>
        </div>

        <div className="dashboard-card-elevated border-l-4 border-l-primary">
          <div className="flex justify-between items-start mb-2">
            <span className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">Optimized Net Margin</span>
            <TrendingUp size={14} className="text-primary/40" />
          </div>
          <div className="text-2xl font-black mb-1 text-primary">€{portfolioStats.optNM.toLocaleString(undefined, { maximumFractionDigits: 0 })}</div>
          <div className="flex items-center gap-1 text-[10px] font-bold text-primary">
            <ArrowUpRight size={12} />
            +€{portfolioStats.uplift.toLocaleString(undefined, { maximumFractionDigits: 0 })} Uplift
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <KPICard 
          label="Top Brand (Uplift)" 
          value={brandStats[0]?.brand || 'N/A'} 
          icon={<Award size={14} className="text-yellow-500" />} 
          variant="accent"
        />
        <KPICard 
          label="Total Portfolio Uplift" 
          value={`€${brandStats.reduce((s, b) => s + b.uplift, 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}`} 
          icon={<TrendingUp size={14} />} 
        />
        <KPICard 
          label="Brands Tracked" 
          value={brandStats.length.toString()} 
          icon={<Zap size={14} />} 
        />
        <KPICard 
          label="Avg Rec. Change" 
          value={`${(brandStats.reduce((s, b) => s + b.avgChg, 0) / brandStats.length).toFixed(1)}%`} 
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card className="shadow-sm border-muted">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-bold flex items-center gap-2 uppercase tracking-wider text-muted-foreground">
              <BarChart3 size={16} /> Brand NM Uplift (Top 10)
            </CardTitle>
          </CardHeader>
          <CardContent className="h-[400px]">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={top10Uplift} layout="vertical" margin={{ left: 40, right: 40 }}>
                <CartesianGrid strokeDasharray="3 3" horizontal={true} vertical={false} opacity={0.1} />
                <XAxis type="number" hide />
                <YAxis 
                  dataKey="brand" 
                  type="category" 
                  tick={{fontSize: 10, fontWeight: 'bold'}} 
                  width={100}
                />
                <Tooltip 
                  cursor={{fill: 'hsl(var(--muted)/0.3)'}}
                  contentStyle={{ backgroundColor: 'hsl(var(--card))', borderRadius: '8px', fontSize: '11px', border: '1px solid hsl(var(--border))' }}
                  formatter={(v: number) => [`€${Math.round(v).toLocaleString()}`, 'Net Margin Uplift']}
                />
                <Bar dataKey="uplift" fill="hsl(var(--success))" radius={[0, 4, 4, 0]} barSize={20}>
                  {top10Uplift.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={`hsl(160, 84%, ${45 - index * 2}%)`} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        <Card className="shadow-sm border-muted">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-bold flex items-center gap-2 uppercase tracking-wider text-muted-foreground">
              Detailed Brand Metrics
            </CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            <div className="overflow-auto max-h-[400px]">
              <table className="w-full text-xs">
                <thead className="bg-muted/30 sticky top-0 z-10">
                  <tr className="border-b border-muted text-muted-foreground">
                    <th className="text-left p-3 font-bold uppercase tracking-widest">Brand</th>
                    <th className="text-right p-3 font-bold uppercase tracking-widest">SKUs</th>
                    <th className="text-right p-3 font-bold uppercase tracking-widest">NM Uplift</th>
                    <th className="text-right p-3 font-bold uppercase tracking-widest">Avg Chg</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-muted/50">
                  {filteredData.map((b) => (
                    <tr key={b.brand} className="hover:bg-muted/20 transition-colors">
                      <td className="p-3 font-black">{b.brand}</td>
                      <td className="p-3 text-right font-mono font-medium">{b.skus}</td>
                      <td className="p-3 text-right font-mono font-black text-success">€{Math.round(b.uplift).toLocaleString()}</td>
                      <td className="p-3 text-right font-mono font-bold">{b.avgChg >= 0 ? '+' : ''}{b.avgChg.toFixed(1)}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      </div>

      <Card className="bg-primary/5 border-primary/20 shadow-none">
        <CardContent className="p-6">
          <div className="flex items-start gap-4">
            <div className="p-2 bg-white rounded-lg shadow-sm">
              <Info className="text-primary" size={20} />
            </div>
            <div>
              <h4 className="text-sm font-black mb-2 uppercase tracking-widest">How Rec. Change % Is Calculated</h4>
              <p className="text-xs text-muted-foreground leading-relaxed">
                For each SKU, the engine sweeps price changes from <span className="font-bold text-foreground">-20% to +20%</span> in 0.5% steps. At each step, the S-Curve demand model predicts the volume response using the brand's calibrated elasticity (k). The step that produces the maximum <span className="font-bold text-foreground">Net Margin</span> (after bonuses deduction) is selected as the optimal price, subject to constraints: Min = max(80% of current, Cost + 5%) and Max = 120% of current.
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
