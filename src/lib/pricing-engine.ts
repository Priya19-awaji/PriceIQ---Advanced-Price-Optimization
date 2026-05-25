// PriceIQ Pricing Engine — connects to Python Flask backend at localhost:5001
// Model-driven architecture: all KPIs computed server-side from DataModel.

const API_BASE = 'http://localhost:5001/api';

export interface SKUData {
  PNO: string;
  Brand: string;
  Category: string;
  PGS: string;
  QTY_2024: number;
  QTY_2025: number;
  SALES_2024: number;
  SALES_2025: number;
  COST_2024: number;
  COST_2025: number;
  SellingPrice_2024: number;   // AVG Price prev year
  SellingPrice_2025: number;   // AVG Price curr year
  PurchasePrice_2025: number;  // Unit Cogs curr year
  ASP_2024: number;            // backward compat
  ASP_2025: number;            // backward compat
  ACP_2025: number;            // backward compat
  GrossMarginPct: number;
  NetMarginPct: number;
  Pct_Change_Price: number;
  Pct_Change_Vol: number;
  Trend_Factor: number;
  Baseline_Vol_2026: number;
}

export interface Recommendation {
  PNO: string;
  Brand: string;
  Category: string;
  PGS: string;
  SellingPrice: number;        // AVG Price (price per item sold)
  PurchasePrice: number;       // Unit Cogs (cost to buy the product)
  CurrentPrice: number;        // backward compat (= SellingPrice)
  CurrentCost: number;         // backward compat (= PurchasePrice)
  BaselineVol2026: number;
  BaselineProfit2026: number;
  CurrentRev2025: number;
  CurrentVol2025: number;
  GrossMarginPct: number;
  NetMarginPct: number;
  CustomerBonus: number;
  EPD: number;
  SupplierBonus: number;
  OptimalPrice: number;
  RecChange: number;
  OptVol: number;
  OptRev: number;
  OptimizedProfit2026: number;
  ProfitUplift: number;
  BaseNM: number;
  OptNM: number;
  NetMarginUplift: number;
  OwnElasticity: number;
  Recommendation: 'INCREASE' | 'DECREASE' | 'HOLD';
  BrandK: number;
  RevMaxPrice: number;
  RevMaxDelta: number;
  ROIMaxPrice: number;
  ROIMaxDelta: number;
  InflectionDelta: number;
  SaturationDelta: number;
  IsSaturated: boolean;
}

export interface ModelInfo {
  kGlobal: number;
  gElast: number;
  brandK: Record<string, number>;
  categoryK: Record<string, number>;
  pgsK: Record<string, number>;
  mape: number;
  r2: number;
  nTrain: number;
  L: number;
  x0: number;
}

export interface PipelineResult {
  rawData: SKUData[];
  recommendations: Recommendation[];
  model: ModelInfo;
}

// ── KPI Types (from /api/kpis — model-driven) ─────────────────────────────
export interface YearlyKPI {
  revenue: number;
  cogs: number;
  quantity: number;
  grossMargin: number;
  grossMarginPct: number;
  netRevenue: number;
  netMargin: number;
  netMarginPct: number;
  avgSellingPrice: number;
  avgPurchasePrice: number;
  skuCount: number;
  brandCount: number;
  categoryCount: number;
}

export interface DimensionKPI {
  name: string;
  revenue: number;
  cogs: number;
  quantity: number;
  grossMargin: number;
  grossMarginPct: number;
  netRevenue: number;
  netMargin: number;
  netMarginPct: number;
  avgSellingPrice: number;
  avgPurchasePrice: number;
  skuCount: number;
}

export interface KPISnapshot {
  years: number[];
  yearly: Record<string, YearlyKPI>;
  yoyGrowth?: {
    years: number[];
    revenue: number;
    cogs: number;
    quantity: number;
    grossMargin: number;
    netRevenue: number;
    netMargin: number;
  };
  byCategory: DimensionKPI[];
  byBrand: DimensionKPI[];
  byPGS: DimensionKPI[];
}

export interface MonthlyTrend {
  label: string;
  year: number;
  month: number;
  revenue: number;
  cogs: number;
  quantity: number;
  grossMargin: number;
  netRevenue: number;
  netMargin: number;
}

// ── Sanitize Numeric Payloads ─────────────────────────────────────────────────
export function sanitizeNumericPayload<T>(data: T): T {
  if (data === null || data === undefined) return 0 as any;
  if (typeof data === 'number') return (isNaN(data) ? 0 : data) as any;
  if (Array.isArray(data)) return data.map(sanitizeNumericPayload) as unknown as T;
  if (typeof data === 'object') {
    const sanitized: any = {};
    for (const [key, val] of Object.entries(data)) {
      sanitized[key] = sanitizeNumericPayload(val);
    }
    return sanitized as T;
  }
  return data;
}

// ── Fetch pipeline from backend ────────────────────────────────────────────────
export async function fetchPipeline(bonusPct = 0.15): Promise<PipelineResult> {
  const url = `${API_BASE}/pipeline?bonus_pct=${bonusPct.toFixed(4)}`;
  const res = await fetch(url);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }));
    throw new Error(err.error || `HTTP ${res.status}`);
  }
  const data = await res.json();
  return sanitizeNumericPayload(data) as PipelineResult;
}

// ── Fetch centralized KPIs (model-driven) ──────────────────────────────────
export async function fetchKPIs(): Promise<KPISnapshot> {
  const res = await fetch(`${API_BASE}/kpis`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }));
    throw new Error(err.error || `HTTP ${res.status}`);
  }
  const data = await res.json();
  return sanitizeNumericPayload(data) as KPISnapshot;
}

// ── Fetch monthly trends (real data, not synthetic) ────────────────────────
export async function fetchMonthlyTrends(years?: number[]): Promise<MonthlyTrend[]> {
  let url = `${API_BASE}/monthly-trends`;
  if (years && years.length > 0) {
    url += `?years=${years.join(',')}`;
  }
  const res = await fetch(url);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }));
    throw new Error(err.error || `HTTP ${res.status}`);
  }
  const data = await res.json();
  return sanitizeNumericPayload(data) as MonthlyTrend[];
}

// ── Check if backend is reachable ──────────────────────────────────────────────
export async function checkBackendHealth(): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE}/health`, { signal: AbortSignal.timeout(3000) });
    return res.ok;
  } catch {
    return false;
  }
}

// ── S-Curve helper (pure math, used in frontend charts) ───────────────────────
export function sigmoidDemand(dp: number, k = 10, x0 = 0.05, L = 1.1): number {
  return L / (1 + Math.exp(k * (dp + x0))) - L / 2;
}

// ── Generate S-curve chart points ─────────────────────────────────────────────
export function generateSCurvePoints(k: number, baseVol: number, x0 = 0.05, L = 1.1, steps = 100) {
  const points: { priceChange: number; volume: number }[] = [];
  for (let i = 0; i <= steps; i++) {
    const dp = -0.3 + (0.6 * i) / steps;
    const vm = 1 + sigmoidDemand(dp, k, x0, L);
    points.push({
      priceChange: Math.round(dp * 1000) / 10,
      volume: Math.round(baseVol * Math.max(0.1, vm)),
    });
  }
  return points;
}

// ── Seasonal factors ───────────────────────────────────────────────────────────
export const SEASONALITY = [0.85, 0.88, 0.95, 1.02, 1.05, 1.08, 1.10, 0.92, 1.04, 1.06, 0.98, 0.85];
export const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

// ── Empty/placeholder result for loading state ────────────────────────────────
export function emptyResult(): PipelineResult {
  return {
    rawData: [],
    recommendations: [],
    model: { kGlobal: 0, gElast: 0, brandK: {}, categoryK: {}, pgsK: {}, mape: 0, r2: 0, nTrain: 0, L: 1.1, x0: 0.05 },
  };
}

export interface InflationData {
  maxInflationTolerance: number;
  inflationData: { rate: string; nm: number; baseNM: number; margin: number }[];
  sensitivityData: { priceChange: number; normal: number; moderate: number; high: number }[];
  costBreakdown: { component: string; current: number; inflated5: number; inflated10: number; pct: number }[];
  breakevenData: { inflation: string; breakeven: number; currentPrice: number; optimalPrice: number }[];
  resilience: { brand: string; margin: number; elasticity: number; resilience: number; skus: number }[];
  categoryResilience: { category: string; margin: number; elasticity: number; resilience: number; skus: number }[];
}

export async function fetchInflationData(pno: string, bonusPct = 0.15): Promise<InflationData> {
  const url = `${API_BASE}/inflation?pno=${encodeURIComponent(pno)}&bonus_pct=${bonusPct.toFixed(4)}`;
  const res = await fetch(url);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }));
    throw new Error(err.error || `HTTP ${res.status}`);
  }
  const data = await res.json();
  return sanitizeNumericPayload(data) as InflationData;
}

export interface CrossElasticityData {
  heatmapData: { source: string; target: string; value: number }[];
  substitutionRisk: { pno: string; risk: number; price: number; elasticity: number; substitutes: number; rec: string }[];
  priceCorridors: { pno: string; current: number; optimal: number; floor: number; ceiling: number; cost: number }[];
  cannibalization: { price: number; volume: number; neighbors: number; pno: string; change: number }[];
  coordImpact: { totalUplift: number; inc: number; dec: number; hold: number; total: number };
}

export async function fetchCrossElasticityData(params: { brand?: string; category?: string; pgs?: string }, bonusPct = 0.15): Promise<CrossElasticityData> {
  const queryParts: string[] = [`bonus_pct=${bonusPct.toFixed(4)}`];
  if (params.brand) queryParts.push(`brand=${encodeURIComponent(params.brand)}`);
  if (params.category) queryParts.push(`category=${encodeURIComponent(params.category)}`);
  const url = `${API_BASE}/cross-elasticity?${queryParts.join('&')}`;
  const res = await fetch(url);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }));
    throw new Error(err.error || `HTTP ${res.status}`);
  }
  const data = await res.json();
  return sanitizeNumericPayload(data) as CrossElasticityData;
}
