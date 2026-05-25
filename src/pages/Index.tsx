import { useEffect, useState, useCallback, useMemo } from 'react';
import { fetchPipeline, emptyResult, type PipelineResult } from '@/lib/pricing-engine';
import { BusinessOverviewTab } from '@/components/dashboard/BusinessOverviewTab';
import { PgsAnalysisTab } from '@/components/dashboard/PgsAnalysisTab';
import { CategoryAnalysisTab } from '@/components/dashboard/CategoryAnalysisTab';
import { BrandAnalysisTab } from '@/components/dashboard/BrandAnalysisTab';
import { ProductInspectorTab } from '@/components/dashboard/ProductInspectorTab';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Slider } from '@/components/ui/slider';
import {
  Shield, AlertCircle, Loader2, RefreshCw, Layers, Zap, Package
} from 'lucide-react';

// ── Backend status banner ──────────────────────────────────────────────────────
function StatusBanner({ status, onRetry }: { status: 'loading' | 'ok' | 'error'; onRetry: () => void }) {
  if (status === 'ok') return null;
  return (
    <div
      className={`flex items-center justify-between px-6 py-2 text-xs font-semibold ${status === 'error' ? 'bg-destructive/10 text-destructive' : 'bg-muted text-muted-foreground'
        }`}
    >
      <div className="flex items-center gap-2">
        {status === 'loading' ? (
          <><Loader2 size={12} className="animate-spin" /> Loading real data from backend…</>
        ) : (
          <>
            <AlertCircle size={12} />
            Backend offline — could not reach <code className="mx-1 font-mono">localhost:5001</code>.
            Start the Python backend: <code className="mx-1 font-mono">python backend.py</code>
          </>
        )}
      </div>
      {status === 'error' && (
        <button onClick={onRetry} className="flex items-center gap-1 underline hover:no-underline">
          <RefreshCw size={11} /> Retry
        </button>
      )}
    </div>
  );
}

// ── Loading skeleton ───────────────────────────────────────────────────────────
function LoadingSkeleton() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-background">
      <div className="text-center space-y-4">
        <Loader2 size={40} className="animate-spin text-primary mx-auto" />
        <p className="font-display text-lg font-semibold">Loading Pricing Data…</p>
        <p className="text-sm text-muted-foreground">Running S-Curve ML pipeline on real data</p>
      </div>
    </div>
  );
}

// ── Main page ──────────────────────────────────────────────────────────────────
const Index = () => {
  const [bonusPct, setBonusPct] = useState(0.15);

  const [pipeline, setPipeline] = useState<PipelineResult>(emptyResult());
  const [backendStatus, setBackendStatus] = useState<'loading' | 'ok' | 'error'>('loading');
  const [initialLoad, setInitialLoad] = useState(true);
  const [activeTab, setActiveTab] = useState('overview');

  // Global Filter State
  const [selectedCategory, setSelectedCategory] = useState<string>('');
  const [selectedPGS, setSelectedPGS] = useState<string>('');
  const [selectedBrand, setSelectedBrand] = useState<string>('');
  const [selectedPNO, setSelectedPNO] = useState<string>('');

  const loadData = useCallback(async () => {
    setBackendStatus('loading');
    try {
      const data = await fetchPipeline(bonusPct);
      setPipeline(data);
      setBackendStatus('ok');
    } catch (err) {
      console.error('Backend error:', err);
      setBackendStatus('error');
    } finally {
      setInitialLoad(false);
    }
  }, [bonusPct]);

  useEffect(() => {
    const timer = setTimeout(() => {
      loadData();
    }, 400);
    return () => clearTimeout(timer);
  }, [bonusPct]);

  const { rawData, recommendations, model } = pipeline;

  // Filter lists
  const categories = useMemo(() => [...new Set(recommendations.map(r => r.Category))].sort(), [recommendations]);
  const pgsList = useMemo(() => {
    const filtered = recommendations.filter(r => r.Category === selectedCategory);
    return [...new Set(filtered.map(r => r.PGS))].sort();
  }, [recommendations, selectedCategory]);

  const brands = useMemo(() => {
    const filtered = recommendations.filter(r => r.Category === selectedCategory && r.PGS === selectedPGS);
    return [...new Set(filtered.map(r => r.Brand))].sort();
  }, [recommendations, selectedCategory, selectedPGS]);

  const skus = useMemo(() => {
    let filtered = recommendations.filter(r => r.Category === selectedCategory && r.PGS === selectedPGS && r.Brand === selectedBrand);
    return filtered.sort((a, b) => b.OptRev - a.OptRev);
  }, [recommendations, selectedCategory, selectedPGS, selectedBrand]);

  // Update selectedPNO when data or filters change
  useEffect(() => {
    if (skus.length > 0) {
      if (!selectedPNO || !skus.find(s => s.PNO === selectedPNO)) {
        setSelectedPNO(skus[0].PNO);
      }
    }
  }, [skus, selectedPNO]);

  useEffect(() => {
    if (categories.length > 0 && !selectedCategory) {
      setSelectedCategory(categories[0]);
    }
  }, [categories, selectedCategory]);

  useEffect(() => {
    if (pgsList.length > 0 && !selectedPGS) {
      setSelectedPGS(pgsList[0]);
    }
  }, [pgsList, selectedPGS]);

  useEffect(() => {
    if (brands.length > 0 && !selectedBrand) {
      setSelectedBrand(brands[0]);
    }
  }, [brands, selectedBrand]);

  if (initialLoad) return <LoadingSkeleton />;

  // Resilient data selection
  const selectedRec = recommendations.find((r) => r.PNO === selectedPNO) || recommendations[0] || null;
  const selectedRaw = rawData.find((d) => d.PNO === selectedPNO) || rawData[0] || null;

  // If backend failed, show a dedicated error screen
  if (backendStatus === 'error') {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <div className="text-center space-y-4 max-w-md p-8 border rounded-2xl bg-destructive/5 border-destructive/10">
          <AlertCircle size={48} className="text-destructive mx-auto" />
          <h2 className="text-xl font-bold">Backend Connection Failed</h2>
          <p className="text-sm text-muted-foreground">
            The frontend could not reach the pricing engine at <code>localhost:5001</code>.
          </p>
          <div className="bg-muted p-3 rounded-lg text-left text-[11px] font-mono overflow-auto">
            1. Ensure Python is installed.<br/>
            2. Run: <code>python backend.py</code><br/>
            3. Ensure <code>Sales Data_POC.csv</code> exists.
          </div>
          <button 
            onClick={loadData} 
            className="w-full py-2 px-4 bg-primary text-primary-foreground rounded-lg font-bold hover:opacity-90 transition-opacity flex items-center justify-center gap-2"
          >
            <RefreshCw size={16} /> Retry Connection
          </button>
        </div>
      </div>
    );
  }

  // Only show "No Data" if backend succeeded but returned nothing
  if (backendStatus === 'ok' && (!selectedRec || !selectedRaw)) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <div className="text-center space-y-3">
          <AlertCircle size={40} className="text-destructive mx-auto" />
          <p className="font-display text-lg font-semibold">No Data Available</p>
          <p className="text-sm text-muted-foreground max-w-sm">
            The backend returned no results. This might be due to filter settings or an empty CSV file.
          </p>
          <button onClick={loadData} className="text-primary underline text-sm">Refresh Data</button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col min-h-screen bg-background">
      <Tabs defaultValue="overview" value={activeTab} onValueChange={setActiveTab} className="w-full h-full flex flex-col flex-1">
      {/* Fixed Top Header with Integrated Navigation */}
      <header className="bg-navy text-navy-foreground border-b border-navy-light sticky top-0 z-50 shadow-xl">
        <div className="max-w-[1600px] mx-auto px-6">
          {/* Top Row: Logo & Market Info */}
          <div className="h-14 flex items-center justify-between border-b border-navy-light/30">
            <div className="flex items-center gap-4">
              <div className="w-8 h-8 rounded-lg bg-primary flex items-center justify-center shadow-lg shadow-primary/20">
                <Shield size={16} className="text-primary-foreground" />
              </div>
              <div>
                <h1 className="font-display text-base font-bold tracking-tight">LKQ PriceIQ</h1>
                <p className="text-[8px] text-navy-foreground/40 uppercase tracking-[0.2em] font-semibold">Advanced Optimization Engine</p>
              </div>
            </div>

            <div className="flex items-center gap-6">
              <div className="flex items-center gap-4 text-[10px] font-medium text-navy-foreground/60">
                <div className="flex flex-col items-end">
                  <span className="text-[8px] uppercase text-navy-foreground/40">Market Regime</span>
                  <span className="text-primary">Normal Market</span>
                </div>
                <div className="h-6 w-px bg-navy-light" />
                <div className="flex flex-col items-end">
                  <span className="text-[8px] uppercase text-navy-foreground/40">Bonus Factor</span>
                  <span className="text-success">{(bonusPct * 100).toFixed(0)}%</span>
                </div>
              </div>
              <button
                onClick={loadData}
                disabled={backendStatus === 'loading'}
                className="p-1.5 rounded-lg bg-navy-light hover:bg-navy-light/80 transition-colors"
              >
                <RefreshCw size={14} className={backendStatus === 'loading' ? 'animate-spin' : ''} />
              </button>
            </div>
          </div>

          {/* Bottom Row: Centered Navigation & Status */}
          <div className="h-12 flex items-center justify-center relative">
            <TabsList className="bg-transparent h-auto p-0 gap-12">
              <TabsTrigger value="overview" className="tab-nav-trigger-compact">
                Business Overview
              </TabsTrigger>
              <TabsTrigger value="pgs" className="tab-nav-trigger-compact">
                PGS Analysis
              </TabsTrigger>
              <TabsTrigger value="category" className="tab-nav-trigger-compact">
                Category Analysis
              </TabsTrigger>
              <TabsTrigger value="brand" className="tab-nav-trigger-compact">
                Brand Performance
              </TabsTrigger>
              <TabsTrigger value="sku" className="tab-nav-trigger-compact">
                Product Inspector
              </TabsTrigger>
            </TabsList>

            <div className="absolute right-0 flex items-center gap-2 text-[9px] font-bold text-navy-foreground/60 bg-navy-light/30 px-3 py-1.5 rounded-full uppercase tracking-widest border border-navy-light/50">
              <span className="w-2 h-2 rounded-full bg-success animate-pulse shadow-[0_0_8px_rgba(34,197,94,0.6)]" />
              System Operational
            </div>
          </div>
        </div>
      </header>

      <main className="flex-1 overflow-y-auto pb-12">
        <StatusBanner status={backendStatus} onRetry={loadData} />

        <div className="w-full">
          {/* Sticky Filter Bar (Only if not on overview) */}
          {activeTab !== 'overview' && (
            <div className="bg-card border-b sticky top-[104px] z-40 shadow-sm animate-in slide-in-from-top-1 duration-300">
              <div className="max-w-[1600px] mx-auto px-6 py-3 flex items-center gap-6">
                <div className="flex items-center gap-2 flex-1 min-w-[150px]">
                  <Layers size={12} className="text-muted-foreground" />
                  <Select value={selectedCategory} onValueChange={(v) => { setSelectedCategory(v); setSelectedPGS(''); setSelectedBrand(''); }}>
                    <SelectTrigger className="h-8 text-[11px] border-none bg-muted/50 hover:bg-muted focus:ring-0 transition-colors">
                      <SelectValue placeholder="Category" />
                    </SelectTrigger>
                    <SelectContent>
                      {categories.map(c => <SelectItem key={c} value={c} className="text-xs">{c}</SelectItem>)}
                    </SelectContent>
                  </Select>
                </div>

                <div className="flex items-center gap-2 flex-1 min-w-[150px]">
                  <Package size={12} className="text-muted-foreground" />
                  <Select value={selectedPGS} onValueChange={(v) => { setSelectedPGS(v); setSelectedBrand(''); }}>
                    <SelectTrigger className="h-8 text-[11px] border-none bg-muted/50 hover:bg-muted focus:ring-0 transition-colors">
                      <SelectValue placeholder="PGS" />
                    </SelectTrigger>
                    <SelectContent>
                      {pgsList.map(p => <SelectItem key={p} value={p} className="text-xs">{p}</SelectItem>)}
                    </SelectContent>
                  </Select>
                </div>

                <div className="flex items-center gap-2 flex-1 min-w-[150px]">
                  <Zap size={12} className="text-muted-foreground" />
                  <Select value={selectedBrand} onValueChange={setSelectedBrand}>
                    <SelectTrigger className="h-8 text-[11px] border-none bg-muted/50 hover:bg-muted focus:ring-0 transition-colors">
                      <SelectValue placeholder="Brand" />
                    </SelectTrigger>
                    <SelectContent>
                      {brands.map(b => <SelectItem key={b} value={b} className="text-xs">{b}</SelectItem>)}
                    </SelectContent>
                  </Select>
                </div>

                <div className="flex items-center gap-2 flex-[1.5] min-w-[250px]">
                  <Package size={12} className="text-muted-foreground" />
                  <Select value={selectedPNO} onValueChange={setSelectedPNO}>
                    <SelectTrigger className="h-8 text-[11px] border-none bg-muted/50 hover:bg-muted focus:ring-0 transition-colors font-mono">
                      <SelectValue placeholder="SKU" />
                    </SelectTrigger>
                    <SelectContent className="max-h-[400px]">
                      {skus.map(s => (
                        <SelectItem key={s.PNO} value={s.PNO} className="text-xs font-mono">
                          {s.PNO} — {s.Brand}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div className="h-6 w-px bg-border" />

                <div className="flex items-center gap-4">
                  <div className="flex flex-col">
                    <div className="flex justify-between text-[9px] text-muted-foreground mb-1 uppercase font-bold tracking-wider">
                      <span>Bonus Opt.</span>
                      <span>{(bonusPct * 100).toFixed(0)}%</span>
                    </div>
                    <Slider
                      value={[bonusPct * 100]}
                      onValueChange={([v]) => setBonusPct(v / 100)}
                      max={30}
                      min={0}
                      step={1}
                      className="w-24"
                    />
                  </div>
                </div>
              </div>
            </div>
          )}

          <div className="max-w-[1600px] mx-auto px-6 mt-8">
            <TabsContent value="overview" className="mt-0 focus-visible:outline-none">
              <BusinessOverviewTab rawData={rawData} recommendations={recommendations} bonusPct={bonusPct} />
            </TabsContent>

            <TabsContent value="pgs" className="mt-0 focus-visible:outline-none">
              <PgsAnalysisTab recommendations={recommendations} selectedRec={selectedRec} bonusPct={bonusPct} />
            </TabsContent>

            <TabsContent value="category" className="mt-0 focus-visible:outline-none">
              <CategoryAnalysisTab recommendations={recommendations} selectedRec={selectedRec} bonusPct={bonusPct} />
            </TabsContent>

            <TabsContent value="brand" className="mt-0 focus-visible:outline-none">
              <BrandAnalysisTab recommendations={recommendations} model={model} bonusPct={bonusPct} />
            </TabsContent>

            <TabsContent value="sku" className="mt-0 focus-visible:outline-none">
              <ProductInspectorTab model={model} selectedRec={selectedRec} selectedRaw={selectedRaw} bonusPct={bonusPct} mape={model.mape} recommendations={recommendations} rawData={rawData} />
            </TabsContent>
          </div>
        </div>
      </main>
      </Tabs>
    </div>
  );
};

export default Index;

