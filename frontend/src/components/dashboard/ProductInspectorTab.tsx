import { useEffect, useMemo, useState } from 'react';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  BarChart, Bar, Cell, AreaChart, Area, ReferenceLine, ComposedChart
} from 'recharts';
import { Slider } from '@/components/ui/slider';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { KPICard } from './KPICard';
import { sigmoidDemand, fetchInflationData, type InflationData, type ModelInfo, type Recommendation, type SKUData } from '@/lib/pricing-engine';
import { 
  Target, AlertTriangle, CheckCircle, ArrowRight, Shield, 
  RotateCcw, Flame, Loader2, TrendingUp, Search, Download,
  Filter, ArrowUpRight, ArrowDownRight, Package, DollarSign,
  BarChart3, PieChart, Zap
} from 'lucide-react';

interface Props {
  model: ModelInfo;
  selectedRec: Recommendation;
  selectedRaw: SKUData;
  bonusPct: number;
  mape: number;
  recommendations: Recommendation[]; // Added to show the table
  rawData: SKUData[]; // Added for prev yr actuals
}

export function ProductInspectorTab({ model, selectedRec, selectedRaw, bonusPct, mape, recommendations, rawData }: Props) {
  const [manualDp, setManualDp] = useState(selectedRec ? Math.round(selectedRec.RecChange * 1000) / 10 : 0);
  const [inflationData, setInflationData] = useState<InflationData | null>(null);
  const [selectedInflation, setSelectedInflation] = useState('0%');
  const [searchTerm, setSearchTerm] = useState('');

  const rawMap = useMemo(() => new Map(rawData.map(d => [d.PNO, d])), [rawData]);

  useEffect(() => {
    if (!selectedRec) return;
    let active = true;
    fetchInflationData(selectedRec.PNO, bonusPct).then(res => {
      if (active) setInflationData(res);
    }).catch(console.error);
    return () => { active = false; };
  }, [selectedRec?.PNO, bonusPct]);

  if (!selectedRec || !selectedRaw) return null;

  // Reset helper
  const handleReset = () => {
    if (!selectedRec) return;
    setManualDp(Math.round(selectedRec.RecChange * 1000) / 10);
    setSelectedInflation('0%');
  };

  const dp = manualDp / 100;
  const curPrice = selectedRec.CurrentPrice;
  const curCost = selectedRec.CurrentCost;
  const baseVol = selectedRaw.Baseline_Vol_2026;
  const sk = selectedRec.BrandK;

  const calc = (d: number) => {
    const vm = 1 + sigmoidDemand(d, sk);
    const vol = Math.round(baseVol * Math.max(0.1, vm));
    const price = curPrice * (1 + d);
    const gp = (price - curCost) * vol;
    const rev = price * vol;
    const nm = gp - rev * bonusPct;
    return { vol, gp, nm, price, rev };
  };

  const base = calc(0);
  const optimal = calc(selectedRec.RecChange);
  const manual = calc(dp);

  // Filtered recommendations for the table
  const filteredRecs = useMemo(() => {
    return recommendations.filter(r => 
      r.PNO.toLowerCase().includes(searchTerm.toLowerCase()) ||
      r.Brand.toLowerCase().includes(searchTerm.toLowerCase()) ||
      r.Category.toLowerCase().includes(searchTerm.toLowerCase())
    );
  }, [recommendations, searchTerm]);

  // Curve data (Current vs Optimized context)
  const currentCurve = useMemo(() => {
    const pts = [];
    for (let i = 0; i <= 60; i++) {
      const d = -0.3 + (0.6 * i) / 60;
      const r = calc(d);
      pts.push({ price: Math.round(r.price * 100) / 100, vol: r.vol, priceChange: Math.round(d * 100) });
    }
    return pts;
  }, [curPrice, curCost, baseVol, sk, bonusPct]);

  const zones = useMemo(() => {
    const inf = (selectedRec.InflectionDelta ?? -0.05) * 100;
    const sat = (selectedRec.SaturationDelta ?? 0.1) * 100;
    return [
      { name: 'Elastic', xStart: -30, xEnd: inf },
      { name: 'Transition', xStart: inf, xEnd: sat },
      { name: 'Saturation', xStart: sat, xEnd: 30 },
    ];
  }, [selectedRec]);

  // Waterfall
  const priceEffect = Math.round((manual.price - curPrice) * manual.vol);
  const volumeEffect = Math.round((manual.vol - base.vol) * (curPrice - curCost));

  // Current selected inflation object from backend
  const activeInflationObj = inflationData?.inflationData.find(d => d.rate === selectedInflation);
  const inflatedCost = curCost * (1 + parseInt(selectedInflation) / 100);

  const exportCSV = () => {
    const headers = ['PNO', 'Brand', 'Category', 'Current Price', 'Optimal Price', 'Change %', 'Current Vol', 'Optimal Vol', 'NM Uplift', 'Action'];
    const rows = filteredRecs.map(r => [
      r.PNO,
      r.Brand,
      r.Category,
      r.CurrentPrice.toFixed(2),
      r.OptimalPrice.toFixed(2),
      (r.RecChange * 100).toFixed(1) + '%',
      r.BaselineVol2026.toLocaleString(),
      r.OptVol.toLocaleString(),
      r.NetMarginUplift.toFixed(0),
      r.Recommendation
    ]);
    const csvContent = "data:text/csv;charset=utf-8," + [headers.join(','), ...rows.map(e => e.join(','))].join('\n');
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", "sku_recommendations.csv");
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div className="space-y-8 animate-fade-in p-2">

      {/* KPI Cards Row (2025 Current vs Optimized) */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="dashboard-card-elevated border-l-4 border-l-primary">
          <div className="flex justify-between items-start mb-2">
            <span className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">Current 2025 Revenue</span>
            <DollarSign size={14} className="text-muted-foreground/40" />
          </div>
          <div className="text-2xl font-black mb-1">€{base.rev.toLocaleString(undefined, { maximumFractionDigits: 0 })}</div>
          <div className="text-[10px] font-medium text-muted-foreground">Historical Baseline</div>
        </div>

        <div className="dashboard-card-elevated border-l-4 border-l-success">
          <div className="flex justify-between items-start mb-2">
            <span className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">Optimized Revenue</span>
            <TrendingUp size={14} className="text-success/40" />
          </div>
          <div className="text-2xl font-black mb-1 text-success">€{optimal.rev.toLocaleString(undefined, { maximumFractionDigits: 0 })}</div>
          <div className="flex items-center gap-1 text-[10px] font-bold text-success">
            <ArrowUpRight size={12} />
            +{(((optimal.rev - base.rev) / base.rev) * 100).toFixed(1)}% Projected Uplift
          </div>
        </div>

        <div className="dashboard-card-elevated border-l-4 border-l-navy">
          <div className="flex justify-between items-start mb-2">
            <span className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">Current Net Margin</span>
            <PieChart size={14} className="text-muted-foreground/40" />
          </div>
          <div className="text-2xl font-black mb-1">€{base.nm.toLocaleString(undefined, { maximumFractionDigits: 0 })}</div>
          <div className="text-[10px] font-medium text-muted-foreground">Baseline Margin</div>
        </div>

        <div className="dashboard-card-elevated border-l-4 border-l-primary">
          <div className="flex justify-between items-start mb-2">
            <span className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">Optimized Net Margin</span>
            <Zap size={14} className="text-primary/40" />
          </div>
          <div className="text-2xl font-black mb-1 text-primary">€{optimal.nm.toLocaleString(undefined, { maximumFractionDigits: 0 })}</div>
          <div className="flex items-center gap-1 text-[10px] font-bold text-primary">
            <ArrowUpRight size={12} />
            +€{(optimal.nm - base.nm).toLocaleString(undefined, { maximumFractionDigits: 0 })} Uplift
          </div>
        </div>
      </div>

      {/* ROW 1: Historical / Current Data & Current Curve */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="dashboard-card-elevated flex flex-col justify-center">
          <h3 className="text-sm font-semibold mb-4 flex items-center gap-2">
            <Target size={16} className="text-muted-foreground" /> Historical Basis (2025)
          </h3>
          <div className="grid grid-cols-3 gap-4">
            <div>
              <span className="text-xs text-muted-foreground block mb-1">Selling Price</span>
              <span className="font-mono text-3xl font-bold">€{curPrice.toFixed(2)}</span>
            </div>
            <div>
              <span className="text-xs text-muted-foreground block mb-1">Baseline Volume</span>
              <span className="font-mono text-3xl font-bold">{base.vol.toLocaleString()}</span>
            </div>
            <div>
              <span className="text-xs text-muted-foreground block mb-1">Purchase Price</span>
              <span className="font-mono text-2xl font-medium text-muted-foreground">€{curCost.toFixed(2)}</span>
            </div>
            <div>
              <span className="text-xs text-muted-foreground block mb-1">Current Gross Profit</span>
              <span className="font-mono text-2xl font-medium text-muted-foreground">€{Math.round(base.gp).toLocaleString()}</span>
            </div>
            <div>
              <span className="text-xs text-muted-foreground block mb-1">Gross Margin %</span>
              <span className="font-mono text-2xl font-medium text-primary">{(selectedRec.GrossMarginPct ?? ((curPrice - curCost) / curPrice * 100)).toFixed(1)}%</span>
            </div>
            <div>
              <span className="text-xs text-muted-foreground block mb-1">Net Margin %</span>
              <span className="font-mono text-2xl font-medium text-success">{(selectedRec.NetMarginPct ?? 0).toFixed(1)}%</span>
            </div>
          </div>
        </div>

        <div className="dashboard-card-elevated relative">
          <div className="flex items-center justify-between mb-2">
            <h4 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">Demand S-Curve & Saturation</h4>
            {selectedRec.IsSaturated && (
              <span className="bg-destructive/10 text-destructive text-[10px] font-bold px-2 py-0.5 rounded-full animate-pulse">SATURATION ZONE</span>
            )}
          </div>
          <ResponsiveContainer width="100%" height={200}>
            <ComposedChart data={currentCurve}>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(220 13% 91%)" />
              <XAxis dataKey="priceChange" tick={{ fontSize: 10 }} label={{ value: 'Price %', position: 'bottom', fontSize: 9 }} />
              <YAxis tick={{ fontSize: 10 }} />
              <Tooltip formatter={(v: number) => [v.toLocaleString(), 'Volume']} contentStyle={{ borderRadius: 8, fontSize: 12 }} />

              {/* Zones */}
              {zones.map(z => (
                <ReferenceLine key={z.name} x={z.xStart} stroke="none" label={{ value: z.name, position: 'insideTopLeft', fontSize: 8, fill: 'gray', opacity: 0.4 }} />
              ))}

              <Area type="monotone" dataKey="vol" stroke="hsl(217 91% 60%)" fill="hsl(217 91% 60% / 0.1)" strokeWidth={2} />

              <ReferenceLine x={0} stroke="red" strokeWidth={2} label={{ value: 'CUR', position: 'top', fontSize: 9, fill: 'red' }} />
              <ReferenceLine x={selectedRec.RecChange * 100} stroke="#16a34a" strokeWidth={2} label={{ value: 'PROFIT', position: 'top', fontSize: 9, fill: '#16a34a' }} />
              <ReferenceLine x={(selectedRec.RevMaxDelta ?? 0) * 100} stroke="#3b82f6" strokeDasharray="3 3" label={{ value: 'REV', position: 'bottom', fontSize: 9, fill: '#3b82f6' }} />
              <ReferenceLine x={(selectedRec.ROIMaxDelta ?? 0) * 100} stroke="#8b5cf6" strokeDasharray="3 3" label={{ value: 'ROI', position: 'bottom', fontSize: 9, fill: '#8b5cf6' }} />

              <ReferenceLine x={manualDp} stroke="orange" strokeDasharray="5 5" label={{ value: 'SET', position: 'top', fontSize: 10, fill: 'orange' }} />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* ROW 2: Predicted / Optimized Data */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="dashboard-card-elevated border-l-4 border-l-primary flex flex-col justify-center">
          <h3 className="text-sm font-semibold mb-4 flex items-center gap-2">
            <TrendingUp size={16} className="text-primary" /> AI Optimized Prediction (2026)
          </h3>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <span className="text-xs text-primary block mb-1">Optimized Price</span>
              <span className="font-mono text-3xl font-bold text-primary">€{optimal.price.toFixed(2)}</span>
              <span className="ml-2 text-sm font-bold bg-primary/10 text-primary px-2 py-0.5 rounded-full">
                {(selectedRec.RecChange * 100).toFixed(1)}%
              </span>
            </div>
            <div>
              <span className="text-xs text-primary block mb-1">Predicted Volume</span>
              <span className="font-mono text-3xl font-bold text-primary">{optimal.vol.toLocaleString()}</span>
            </div>
            <div>
              <span className="text-xs text-muted-foreground block mb-1">Predicted Gross Profit</span>
              <span className="font-mono text-2xl font-medium text-muted-foreground">€{Math.round(optimal.gp).toLocaleString()}</span>
            </div>
            <div>
              <span className="text-xs text-success block mb-1">GP Uplift</span>
              <span className="font-mono text-2xl font-medium text-success">+€{Math.round(optimal.gp - base.gp).toLocaleString()}</span>
            </div>
          </div>
        </div>

        <div className="dashboard-card-elevated">
          <h4 className="text-sm font-semibold mb-2 text-primary">Marginal Utility (Profit vs Volume)</h4>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={[
              { name: 'Revenue', value: manual.rev, color: '#3b82f6' },
              { name: 'Gross Profit', value: manual.gp, color: '#10b981' },
              { name: 'Net Margin', value: manual.nm, color: '#8b5cf6' },
            ]}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} opacity={0.3} />
              <XAxis dataKey="name" tick={{ fontSize: 10 }} />
              <YAxis tick={{ fontSize: 10 }} tickFormatter={(v) => `€${(v / 1000).toFixed(0)}k`} />
              <Tooltip formatter={(v: number) => [`€${v.toLocaleString()}`, '']} />
              <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                {[0, 1, 2].map((i) => (
                  <Cell key={i} fill={['#3b82f6', '#10b981', '#8b5cf6'][i]} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* SKU Recommendations Table */}
      <div className="dashboard-card-elevated">
        <div className="flex flex-col md:flex-row md:items-center justify-between mb-6 gap-4">
          <div>
            <h3 className="text-sm font-black uppercase tracking-widest flex items-center gap-2">
              <Package size={16} className="text-primary" /> SKU Optimization Recommendations
            </h3>
            <p className="text-[10px] text-muted-foreground font-bold mt-1 uppercase tracking-wider">Detailed portfolio breakdown</p>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" size={14} />
              <Input 
                placeholder="Search PNO or Brand..." 
                className="pl-9 h-9 text-xs w-64 bg-muted/50 border-none font-medium"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
              />
            </div>
            <Button variant="outline" size="sm" className="h-9 font-bold text-xs gap-2" onClick={exportCSV}>
              <Download size={14} /> Export CSV
            </Button>
            <Button variant="outline" size="sm" className="h-9 font-bold text-xs gap-2">
              <Filter size={14} /> Filter
            </Button>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="bg-muted/50 border-b border-muted">
                <th className="p-4 text-left font-black uppercase tracking-widest text-muted-foreground">PNO</th>
                <th className="p-4 text-left font-black uppercase tracking-widest text-muted-foreground">Brand</th>
                <th className="p-4 text-left font-black uppercase tracking-widest text-muted-foreground">PGS</th>
                <th className="p-4 text-right font-black uppercase tracking-widest text-muted-foreground">Purchase Price</th>
                <th className="p-4 text-right font-black uppercase tracking-widest text-muted-foreground">Prev Yr Actuals (2024)</th>
                <th className="p-4 text-right font-black uppercase tracking-widest text-muted-foreground">Current (2025)</th>
                <th className="p-4 text-right font-black uppercase tracking-widest text-muted-foreground">Optimal (2026)</th>
                <th className="p-4 text-right font-black uppercase tracking-widest text-muted-foreground">Change</th>
                <th className="p-4 text-right font-black uppercase tracking-widest text-muted-foreground">Volume</th>
                <th className="p-4 text-right font-black uppercase tracking-widest text-muted-foreground">NM Uplift</th>
                <th className="p-4 text-center font-black uppercase tracking-widest text-muted-foreground">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-muted/30">
              {filteredRecs.slice(0, 10).map((r) => {
                const rd = rawMap.get(r.PNO);
                return (
                <tr key={r.PNO} className={`hover:bg-muted/20 transition-colors ${r.PNO === selectedRec.PNO ? 'bg-primary/5' : ''}`}>
                  <td className="p-4 font-mono font-black">{r.PNO}</td>
                  <td className="p-4 font-bold">{r.Brand}</td>
                  <td className="p-4 text-xs text-muted-foreground">{r.PGS || 'N/A'}</td>
                  <td className="p-4 text-right font-mono text-muted-foreground">€{(r.PurchasePrice ?? r.CurrentCost).toFixed(2)}</td>
                  <td className="p-4 text-right font-mono text-muted-foreground">{rd?.SellingPrice_2024 ? `€${rd.SellingPrice_2024.toFixed(2)}` : 'N/A'}</td>
                  <td className="p-4 text-right font-mono">€{(r.SellingPrice ?? r.CurrentPrice).toFixed(2)}</td>
                  <td className="p-4 text-right font-mono font-black text-primary">€{r.OptimalPrice.toFixed(2)}</td>
                  <td className="p-4 text-right">
                    <span className={`px-2 py-1 rounded-full text-[10px] font-black ${r.RecChange >= 0 ? 'bg-success/10 text-success' : 'bg-destructive/10 text-destructive'}`}>
                      {r.RecChange >= 0 ? '+' : ''}{(r.RecChange * 100).toFixed(1)}%
                    </span>
                  </td>
                  <td className="p-4 text-right font-mono">{r.OptVol.toLocaleString()}</td>
                  <td className="p-4 text-right font-mono font-black text-success">+€{Math.round(r.NetMarginUplift).toLocaleString()}</td>
                  <td className="p-4 text-center">
                    <span className={`text-[10px] font-black px-2 py-1 rounded-md uppercase tracking-tighter ${
                      r.Recommendation === 'INCREASE' ? 'bg-success text-success-foreground' :
                      r.Recommendation === 'DECREASE' ? 'bg-destructive text-destructive-foreground' :
                      'bg-muted text-muted-foreground'
                    }`}>
                      {r.Recommendation}
                    </span>
                  </td>
                </tr>
              )}
              )}
            </tbody>
          </table>
          {filteredRecs.length > 10 && (
            <div className="p-4 text-center border-t border-muted">
              <p className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest">
                Showing top 10 of {filteredRecs.length} SKUs. Use search to find specific parts.
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Impact Analysis & Controls */}
      <div>
        <h3 className="tab-section-title">Impact Analysis (Active Scenario)</h3>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-4">
          <KPICard label="Scenario Revenue" value={`€${manual.rev.toLocaleString()}`} trend={((manual.rev - base.vol * curPrice) / (base.vol * curPrice)) * 100} />
          <KPICard label="Scenario COGS" value={`€${Math.round(inflatedCost * manual.vol).toLocaleString()}`} />
          <KPICard label="Scenario Gross Profit" value={`€${Math.round((manual.price - inflatedCost) * manual.vol).toLocaleString()}`} trend={((manual.gp - base.gp) / Math.abs(base.gp)) * 100} />
          <KPICard label="Scenario Net Margin" value={`€${Math.round((manual.price - inflatedCost) * manual.vol - manual.rev * bonusPct).toLocaleString()}`} trend={((manual.nm - base.nm) / Math.abs(base.nm)) * 100} />
        </div>

        <div className="dashboard-card-elevated w-full md:w-2/3 lg:w-1/2 mx-auto">
          <h4 className="text-sm font-semibold mb-2 text-center">Profit Waterfall</h4>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={[
              { name: 'Base GP', value: Math.round(base.gp) },
              { name: 'Price Effect', value: priceEffect },
              { name: 'Volume Effect', value: volumeEffect },
              { name: 'Inflated Cost Effect', value: -Math.round((inflatedCost - curCost) * manual.vol) },
              { name: 'Final GP', value: Math.round((manual.price - inflatedCost) * manual.vol) },
            ]} margin={{ top: 20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(220 13% 91%)" vertical={false} />
              <XAxis dataKey="name" tick={{ fontSize: 10 }} interval={0} />
              <YAxis tick={{ fontSize: 10 }} tickFormatter={(v) => `€${(v / 1000).toFixed(0)}k`} />
              <Tooltip formatter={(v: number) => [`€${v.toLocaleString()}`, '']} contentStyle={{ borderRadius: 8, fontSize: 12 }} />
              <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                {[Math.round(base.gp), priceEffect, volumeEffect, -Math.round((inflatedCost - curCost) * manual.vol), Math.round((manual.price - inflatedCost) * manual.vol)].map((v, i) => (
                  <Cell key={i} fill={i === 0 || i === 4 ? 'hsl(217 91% 60%)' : v >= 0 ? 'hsl(160 84% 39%)' : 'hsl(0 84% 60%)'} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* ROW 4 & 5: Controls (Manual Override & Inflation) */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 pb-20">
        <div className="dashboard-card border-l-4 border-l-warning">
          <div className="flex items-center justify-between mb-4">
            <h4 className="text-sm font-black uppercase tracking-widest text-muted-foreground flex items-center gap-2">
              <AlertTriangle size={14} className="text-orange-500" /> Manual Price Override
            </h4>
            <div className="flex items-center gap-3">
              <span className="font-mono text-lg font-black text-primary">
                €{manual.price.toFixed(2)} <span className="text-sm font-medium text-muted-foreground">({manualDp > 0 ? '+' : ''}{manualDp.toFixed(1)}%)</span>
              </span>
              <Button size="sm" variant="outline" onClick={handleReset} className="h-8 shadow-sm font-bold">
                <RotateCcw size={14} className="mr-1" /> Reset to Optimized
              </Button>
            </div>
          </div>
          <div className="px-2 py-6">
            <Slider 
              value={[manualDp]} 
              min={-20} 
              max={20} 
              step={0.5} 
              onValueChange={([v]) => setManualDp(v)}
              className="py-4"
            />
            <div className="flex justify-between text-[10px] font-black text-muted-foreground uppercase tracking-widest mt-2">
              <span>-20% (Aggressive)</span>
              <span>Baseline (0%)</span>
              <span>+20% (Premium)</span>
            </div>
          </div>
        </div>

        <div className="dashboard-card border-l-4 border-l-destructive">
          <div className="flex items-center justify-between mb-4">
            <h4 className="text-sm font-black uppercase tracking-widest text-muted-foreground flex items-center gap-2">
              <Flame size={14} className="text-destructive" /> Cost Inflation Simulator
            </h4>
            <Select value={selectedInflation} onValueChange={setSelectedInflation}>
              <SelectTrigger className="w-32 h-8 font-bold">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {['0%', '2%', '5%', '10%', '15%'].map(r => (
                  <SelectItem key={r} value={r} className="text-xs font-bold">{r} Inflation</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-4">
             <div className="flex items-center justify-between p-3 bg-destructive/5 rounded-lg border border-destructive/10">
               <div className="flex items-center gap-3">
                 <Shield size={18} className="text-destructive" />
                 <div>
                   <span className="text-[10px] font-black uppercase tracking-widest text-muted-foreground block">Max Inflation Tolerance</span>
                   <span className="text-lg font-black text-destructive">{(inflationData?.maxInflationTolerance ?? 0).toFixed(1)}%</span>
                 </div>
               </div>
               <div className="text-right">
                 <span className="text-[10px] font-black uppercase tracking-widest text-muted-foreground block">Scenario Cost</span>
                 <span className="text-lg font-black">€{inflatedCost.toFixed(2)}</span>
               </div>
             </div>
             <p className="text-[10px] leading-relaxed text-muted-foreground italic px-1">
               * Simulates the impact of rising supply chain costs on your net margin. The "Tolerance" indicates the break-even point where optimized pricing can no longer absorb cost increases.
             </p>
          </div>
        </div>
      </div>
    </div>
  );
}
