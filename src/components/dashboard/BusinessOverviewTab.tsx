import { useEffect, useMemo, useState } from 'react';
import { type SKUData, type Recommendation, type KPISnapshot, type MonthlyTrend, fetchKPIs, fetchMonthlyTrends } from '@/lib/pricing-engine';
import { Card, CardContent } from '@/components/ui/card';
import { 
  DollarSign, 
  TrendingUp, 
  ArrowUpRight, 
  ArrowDownRight, 
  Package, 
  BarChart3, 
  PieChart,
  Zap,
  Layers,
  Award,
  ShoppingCart,
  Tag,
  Loader2
} from 'lucide-react';
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend
} from 'recharts';
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group';

interface Props {
  rawData: SKUData[];
  recommendations: Recommendation[];
  bonusPct: number;
}

interface MetricGroupProps {
  title: string;
  v24: number;
  v25: number;
  v26: number;
  isCurrency?: boolean;
  icon?: any;
  suffix?: string;
}

function MetricGroup({ title, v24, v25, v26, isCurrency = true, icon: Icon, suffix }: MetricGroupProps) {
  let yoy = v24 !== 0 ? ((v25 - v24) / v24) * 100 : 0;
  let growthDelta = v25 !== 0 ? ((v26 - v25) / v25) * 100 : 0;
  
  if (isNaN(yoy)) yoy = 0;
  if (isNaN(growthDelta)) growthDelta = 0;

  const format = (v: number) => {
    if (suffix === '%') return `${v.toFixed(1)}%`;
    if (isCurrency) {
      return `€${v.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
    }
    return v.toLocaleString(undefined, { maximumFractionDigits: 0 });
  };

  return (
    <div className="space-y-4">
      <h3 className="text-sm font-black uppercase tracking-[0.2em] text-muted-foreground/70 ml-1 flex items-center gap-2">
        {Icon && <Icon size={14} />} {title} PERFORMANCE
      </h3>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card className="bg-card shadow-sm border-muted transition-all hover:shadow-md">
          <CardContent className="p-5">
            <div className="flex justify-between items-start mb-2">
              <span className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">2024 {title}</span>
              {isCurrency && <span className="text-muted-foreground/40 font-bold">€</span>}
            </div>
            <div className="text-2xl font-black mb-1">{format(v24)}</div>
            <div className="text-[10px] font-medium text-muted-foreground">Baseline</div>
          </CardContent>
        </Card>

        <Card className="bg-card shadow-sm border-muted transition-all hover:shadow-md">
          <CardContent className="p-5">
            <div className="flex justify-between items-start mb-2">
              <span className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">2025 {title}</span>
            </div>
            <div className="text-2xl font-black mb-1">{format(v25)}</div>
            <div className={`flex items-center gap-1 text-[10px] font-bold ${yoy >= 0 ? 'text-success' : 'text-destructive'}`}>
              {yoy >= 0 ? <ArrowUpRight size={12} /> : <ArrowDownRight size={12} />}
              {yoy >= 0 ? '+' : ''}{yoy.toFixed(1)}% vs LY
            </div>
          </CardContent>
        </Card>

        <Card className="bg-card shadow-sm border-l-4 border-l-success border-muted transition-all hover:shadow-md">
          <CardContent className="p-5">
            <div className="flex justify-between items-start mb-2">
              <span className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">2026 TARGET {title}</span>
              <TrendingUp size={14} className="text-success/40" />
            </div>
            <div className="text-2xl font-black mb-1">{format(v26)}</div>
          </CardContent>
        </Card>

        <Card className="bg-card shadow-sm border-muted transition-all hover:shadow-md">
          <CardContent className="p-5">
            <div className="flex justify-between items-start mb-2">
              <span className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">GROWTH DELTA</span>
            </div>
            <div className={`text-2xl font-black mb-1 ${growthDelta >= 0 ? 'text-foreground' : 'text-destructive'}`}>
              {growthDelta >= 0 ? '+' : ''}{growthDelta.toFixed(1)}%
            </div>
            <div className="text-[10px] font-medium text-muted-foreground">Projected Uplift</div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

export function BusinessOverviewTab({ rawData, recommendations, bonusPct }: Props) {
  const [activeKpi, setActiveKpi] = useState<'rev' | 'cogs' | 'qty' | 'margin' | 'netMargin' | 'netRev'>('rev');
  const [kpiData, setKpiData] = useState<KPISnapshot | null>(null);
  const [monthlyData, setMonthlyData] = useState<MonthlyTrend[]>([]);
  const [loading, setLoading] = useState(true);

  // Fetch model-driven KPIs from backend
  useEffect(() => {
    let active = true;
    setLoading(true);
    Promise.all([fetchKPIs(), fetchMonthlyTrends()])
      .then(([kpis, monthly]) => {
        if (active) {
          setKpiData(kpis);
          setMonthlyData(monthly);
        }
      })
      .catch(console.error)
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);

  // Fallback stats from raw pipeline data (for 2026 projections)
  const stats = useMemo(() => {
    // Use KPI data if available, else compute from raw
    const k = kpiData;

    const rev24 = k?.yearly['2024']?.revenue ?? rawData.reduce((a, c) => a + c.SALES_2024, 0);
    const cogs24 = k?.yearly['2024']?.cogs ?? rawData.reduce((a, c) => a + c.COST_2024, 0);
    const qty24 = k?.yearly['2024']?.quantity ?? rawData.reduce((a, c) => a + c.QTY_2024, 0);
    const margin24 = k?.yearly['2024']?.grossMargin ?? (rev24 - cogs24);
    const nr24 = k?.yearly['2024']?.netRevenue ?? rev24;
    const nm24 = k?.yearly['2024']?.netMargin ?? margin24;
    const asp24 = k?.yearly['2024']?.avgSellingPrice ?? 0;
    const app24 = k?.yearly['2024']?.avgPurchasePrice ?? 0;

    const rev25 = k?.yearly['2025']?.revenue ?? rawData.reduce((a, c) => a + c.SALES_2025, 0);
    const cogs25 = k?.yearly['2025']?.cogs ?? rawData.reduce((a, c) => a + c.COST_2025, 0);
    const qty25 = k?.yearly['2025']?.quantity ?? rawData.reduce((a, c) => a + c.QTY_2025, 0);
    const margin25 = k?.yearly['2025']?.grossMargin ?? (rev25 - cogs25);
    const nr25 = k?.yearly['2025']?.netRevenue ?? rev25;
    const nm25 = k?.yearly['2025']?.netMargin ?? margin25;
    const asp25 = k?.yearly['2025']?.avgSellingPrice ?? 0;
    const app25 = k?.yearly['2025']?.avgPurchasePrice ?? 0;

    // 2026 is always from optimizer projections
    const rev26 = recommendations.reduce((a, c) => a + c.OptRev, 0);
    const cogs26 = recommendations.reduce((a, c) => a + (c.CurrentCost * c.OptVol), 0);
    const qty26 = recommendations.reduce((a, c) => a + c.OptVol, 0);
    const margin26 = rev26 - cogs26;
    const nr26 = rev26;  // projected
    const nm26 = recommendations.reduce((a, c) => a + c.OptNM, 0);

    const cats = k?.yearly['2025']?.categoryCount ?? [...new Set(recommendations.map(r => r.Category))].length;
    const brands = k?.yearly['2025']?.brandCount ?? [...new Set(recommendations.map(r => r.Brand))].length;
    const skus = k?.yearly['2025']?.skuCount ?? recommendations.length;

    return {
      rev:       { v24: rev24, v25: rev25, v26: rev26 },
      cogs:      { v24: cogs24, v25: cogs25, v26: cogs26 },
      qty:       { v24: qty24, v25: qty25, v26: qty26 },
      margin:    { v24: margin24, v25: margin25, v26: margin26 },
      netRev:    { v24: nr24, v25: nr25, v26: nr26 },
      netMargin: { v24: nm24, v25: nm25, v26: nm26 },
      selling:   { v24: asp24, v25: asp25 },
      purchase:  { v24: app24, v25: app25 },
      counts:    { cats, brands, skus }
    };
  }, [rawData, recommendations, bonusPct, kpiData]);

  // Chart data: use REAL monthly data from backend
  const chartData = useMemo(() => {
    if (monthlyData.length > 0) {
      return monthlyData.map(m => ({
        name: m.label,
        rev: m.revenue,
        cogs: m.cogs,
        qty: m.quantity,
        margin: m.grossMargin,
        netRev: m.netRevenue,
        netMargin: m.netMargin,
        isProjected: m.year >= 2026,
      }));
    }

    // Fallback: synthetic (old behavior, only if monthly endpoint fails)
    const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    const data: any[] = [];
    const generateMonthly = (yearlyTotal: number, year: string, isProjected: boolean) =>
      months.map((m, i) => ({
        name: `${m} ${year}`,
        val: (yearlyTotal / 12) * (1 + Math.sin((i / 11) * Math.PI) * 0.1) * (0.98 + Math.random() * 0.04),
        isProjected,
      }));

    for (const [yearKey, yearLabel, projected] of [['v24', '24', false], ['v25', '25', false], ['v26', '26', true]] as const) {
      const rev = generateMonthly(stats.rev[yearKey] as number, yearLabel, projected as boolean);
      const cogs = generateMonthly(stats.cogs[yearKey] as number, yearLabel, projected as boolean);
      const qty = generateMonthly(stats.qty[yearKey] as number, yearLabel, projected as boolean);
      const margin = generateMonthly(stats.margin[yearKey] as number, yearLabel, projected as boolean);
      for (let i = 0; i < 12; i++) {
        data.push({
          name: rev[i].name, rev: rev[i].val, cogs: cogs[i].val,
          qty: qty[i].val, margin: margin[i].val,
          netRev: rev[i].val, netMargin: margin[i].val,
          isProjected: projected,
        });
      }
    }
    return data;
  }, [monthlyData, stats]);

  const kpiLabel: Record<string, string> = {
    rev: 'Revenue',
    cogs: 'COGS',
    qty: 'Quantity',
    margin: 'Gross Margin',
    netRev: 'Net Revenue',
    netMargin: 'Net Margin',
  };

  return (
    <div className="space-y-12 animate-fade-in p-4 pb-20">
      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-5 gap-6">
        <Card className="bg-navy text-navy-foreground shadow-lg border-none">
          <CardContent className="p-6 flex items-center gap-4">
            <div className="p-3 bg-white/10 rounded-xl"><Layers size={24} /></div>
            <div>
              <div className="text-[10px] font-bold uppercase tracking-widest opacity-60">Categories</div>
              <div className="text-3xl font-black">{stats.counts.cats}</div>
            </div>
          </CardContent>
        </Card>
        <Card className="bg-primary text-primary-foreground shadow-lg border-none">
          <CardContent className="p-6 flex items-center gap-4">
            <div className="p-3 bg-white/10 rounded-xl"><Award size={24} /></div>
            <div>
              <div className="text-[10px] font-bold uppercase tracking-widest opacity-60">Brands</div>
              <div className="text-3xl font-black">{stats.counts.brands}</div>
            </div>
          </CardContent>
        </Card>
        <Card className="bg-card shadow-lg border-muted">
          <CardContent className="p-6 flex items-center gap-4">
            <div className="p-3 bg-primary/10 rounded-xl text-primary"><Package size={24} /></div>
            <div>
              <div className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground">Active SKUs</div>
              <div className="text-3xl font-black text-foreground">{stats.counts.skus.toLocaleString()}</div>
            </div>
          </CardContent>
        </Card>

        {/* NEW: Selling Price & Purchase Price cards */}
        <Card className="bg-card shadow-lg border-muted">
          <CardContent className="p-6 flex items-center gap-4">
            <div className="p-3 bg-success/10 rounded-xl text-success"><Tag size={24} /></div>
            <div>
              <div className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground">Avg Selling Price</div>
              <div className="text-2xl font-black text-foreground">€{stats.selling.v25.toFixed(2)}</div>
              {stats.selling.v24 > 0 && (
                <div className={`text-[10px] font-bold ${stats.selling.v25 >= stats.selling.v24 ? 'text-success' : 'text-destructive'}`}>
                  {stats.selling.v25 >= stats.selling.v24 ? '+' : ''}{((stats.selling.v25 - stats.selling.v24) / stats.selling.v24 * 100).toFixed(1)}% vs LY
                </div>
              )}
            </div>
          </CardContent>
        </Card>
        <Card className="bg-card shadow-lg border-muted">
          <CardContent className="p-6 flex items-center gap-4">
            <div className="p-3 bg-orange-500/10 rounded-xl text-orange-500"><ShoppingCart size={24} /></div>
            <div>
              <div className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground">Avg Purchase Price</div>
              <div className="text-2xl font-black text-foreground">€{stats.purchase.v25.toFixed(2)}</div>
              {stats.purchase.v24 > 0 && (
                <div className={`text-[10px] font-bold ${stats.purchase.v25 <= stats.purchase.v24 ? 'text-success' : 'text-destructive'}`}>
                  {stats.purchase.v25 >= stats.purchase.v24 ? '+' : ''}{((stats.purchase.v25 - stats.purchase.v24) / stats.purchase.v24 * 100).toFixed(1)}% vs LY
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* KPI Metric Groups (model-driven) */}
      <MetricGroup title="Revenue" v24={stats.rev.v24} v25={stats.rev.v25} v26={stats.rev.v26} icon={DollarSign} />
      <MetricGroup title="COGS" v24={stats.cogs.v24} v25={stats.cogs.v25} v26={stats.cogs.v26} icon={BarChart3} />
      <MetricGroup title="Quantity" v24={stats.qty.v24} v25={stats.qty.v25} v26={stats.qty.v26} isCurrency={false} icon={Package} />
      <MetricGroup title="Gross Margin" v24={stats.margin.v24} v25={stats.margin.v25} v26={stats.margin.v26} icon={PieChart} />
      <MetricGroup title="Net Revenue" v24={stats.netRev.v24} v25={stats.netRev.v25} v26={stats.netRev.v26} icon={Zap} />
      <MetricGroup title="Net Margin" v24={stats.netMargin.v24} v25={stats.netMargin.v25} v26={stats.netMargin.v26} icon={TrendingUp} />

      {/* Trend Chart — REAL monthly data from backend */}
      <div className="dashboard-card-elevated">
        <div className="flex items-center justify-between mb-6">
          <h3 className="text-sm font-black uppercase tracking-widest flex items-center gap-2">
            <TrendingUp size={16} className="text-primary" /> Performance Trends
            {loading && <Loader2 size={12} className="animate-spin text-muted-foreground" />}
          </h3>
          <ToggleGroup type="single" value={activeKpi} onValueChange={(v) => v && setActiveKpi(v as any)} className="bg-muted p-1 h-9">
            <ToggleGroupItem value="rev" className="text-[10px] px-3 font-bold">Revenue</ToggleGroupItem>
            <ToggleGroupItem value="cogs" className="text-[10px] px-3 font-bold">COGS</ToggleGroupItem>
            <ToggleGroupItem value="qty" className="text-[10px] px-3 font-bold">Quantity</ToggleGroupItem>
            <ToggleGroupItem value="margin" className="text-[10px] px-3 font-bold">Gross Margin</ToggleGroupItem>
            <ToggleGroupItem value="netRev" className="text-[10px] px-3 font-bold">Net Rev</ToggleGroupItem>
            <ToggleGroupItem value="netMargin" className="text-[10px] px-3 font-bold">Net Margin</ToggleGroupItem>
          </ToggleGroup>
        </div>

        <div className="h-[400px] w-full">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={chartData} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
              <defs>
                <linearGradient id="colorHistorical" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#2563eb" stopOpacity={0.3}/>
                  <stop offset="95%" stopColor="#2563eb" stopOpacity={0}/>
                </linearGradient>
                <linearGradient id="colorProjected" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#60a5fa" stopOpacity={0.2}/>
                  <stop offset="95%" stopColor="#60a5fa" stopOpacity={0}/>
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="hsl(var(--muted-foreground))" opacity={0.1} />
              <XAxis 
                dataKey="name" 
                axisLine={false} 
                tickLine={false} 
                tick={{fontSize: 9, fontWeight: 'bold'}} 
                dy={10}
                interval={2}
              />
              <YAxis 
                axisLine={false} 
                tickLine={false} 
                tick={{fontSize: 10}} 
                tickFormatter={(v) => activeKpi === 'qty' ? v.toLocaleString() : `€${(v / 1000000).toFixed(1)}M`}
              />
              <Tooltip 
                contentStyle={{ backgroundColor: 'hsl(var(--card))', borderRadius: '12px', border: '1px solid hsl(var(--border))', fontSize: '12px', fontWeight: 'bold' }}
                formatter={(v: number, name: string, props: any) => {
                  const isProjected = props.payload.isProjected;
                  const label = `${kpiLabel[activeKpi]}${isProjected ? ' (Projected)' : ''}`;
                  const val = activeKpi === 'qty' ? v.toLocaleString() : `€${v.toLocaleString(undefined, {maximumFractionDigits: 0})}`;
                  return [val, label];
                }}
              />
              
              {/* Historical Area */}
              <Area 
                type="monotone" 
                dataKey={(d) => d.isProjected ? null : d[activeKpi]} 
                stroke="#2563eb" 
                strokeWidth={4} 
                fillOpacity={1} 
                fill="url(#colorHistorical)" 
                animationDuration={1000}
                connectNulls={false}
              />
              
              {/* Projected Area */}
              <Area 
                type="monotone" 
                dataKey={(d) => d.isProjected || d.name?.endsWith('25') ? d[activeKpi] : null} 
                stroke="#60a5fa" 
                strokeWidth={4} 
                strokeDasharray="5 5"
                fillOpacity={1} 
                fill="url(#colorProjected)" 
                animationDuration={1000}
                connectNulls={true}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}
