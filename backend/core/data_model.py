"""
PriceIQ Data Model — Centralized, model-driven data layer.

All KPIs, revenue, margin, and time-based metrics are computed here.
Dashboards and APIs consume this model — no hardcoded calculations elsewhere.

CSV Column Mapping:
  - Selling Price  = AVG Price   (price per item sold to customer)
  - Purchase Price = Unit Cogs   (cost to acquire/buy the product)
  - Revenue        = Revenue Eur (Selling Price × Quantity)
  - COGS           = Cogs Eur    (Purchase Price × Quantity)
"""

import os
import numpy as np
import pandas as pd
from typing import Optional, List, Dict, Any

# ─── Column name constants (CSV → internal) ──────────────────────────────────
CSV_COLS = {
    'Company Name':          'COMPANY',
    'Date Y M':              'PERIOD',        # YYYYMM
    'Date_Year':             'YEAR',
    'Date_Month':            'MONTH',
    'Channel':               'CHANNEL',
    'Eos Cat':               'CATEGORY',
    'Eos Cat Name':          'CAT_NAME',
    'Cpg':                   'CPG_ID',
    'Cpg Name':              'CPG_NAME',
    'Brand':                 'BRAND',
    'PGS':                   'PGS',
    'Pgs Segment':           'PGS_SEGMENT',
    'Pgs Family':            'PGS_FAMILY',
    'Segment Name':          'SEGMENT_NAME',
    'Group Name':            'GROUP_NAME',
    'Family Name':           'FAMILY_NAME',
    'Brand Flag':            'BRAND_FLAG',
    'Company Item No':       'PNO',
    'One Lkq Item Number':   'LKQ_ITEM_NO',
    'Customer Bonus':        'CUSTOMER_BONUS',      # decimal rate
    'Early Payment Discount':'EPD',                  # decimal rate
    'Supplier Bonus':        'SUPPLIER_BONUS',       # decimal rate
    'Quantity':              'QTY',
    'Revenue Eur':           'REVENUE',              # = Selling Price × Qty
    'AVG Price':             'SELLING_PRICE',         # price per item sold
    'Gross Margin Eur':      'GROSS_MARGIN',
    'Cogs Eur':              'COGS',                 # = Purchase Price × Qty
    'Unit Cogs':             'PURCHASE_PRICE',        # cost per item bought
    'Net Revenue ':          'NET_REVENUE_CSV',       # from CSV (for validation)
    'Net Cogs':              'NET_COGS_CSV',
    'Net Margin ':           'NET_MARGIN_CSV',
    'Gross Margin % ':       'GROSS_MARGIN_PCT_CSV',
    'Net Margin % ':         'NET_MARGIN_PCT_CSV',
}

# Columns we actually need to read (strip whitespace variants)
NEEDED_CSV_COLS = list(CSV_COLS.keys())

# Numeric columns to coerce
NUMERIC_COLS = [
    'QTY', 'REVENUE', 'SELLING_PRICE', 'GROSS_MARGIN', 'COGS',
    'PURCHASE_PRICE', 'CUSTOMER_BONUS', 'EPD', 'SUPPLIER_BONUS',
    'NET_REVENUE_CSV', 'NET_COGS_CSV', 'NET_MARGIN_CSV',
    'GROSS_MARGIN_PCT_CSV', 'NET_MARGIN_PCT_CSV',
]


class DataModel:
    """
    Central data model — loads CSV once, provides all calculated fields.

    Fact Table : Sales transactions (one row per PNO × Period × Channel × ...)
    Dimensions : Date (Year/Month), Product (PNO), Brand, Category, PGS, Company

    Calculated Fields (defined once, reused everywhere):
      revenue             = Revenue Eur (from CSV)
      selling_price       = AVG Price (from CSV)
      purchase_price      = Unit Cogs (from CSV)
      gross_margin        = Gross Margin Eur (from CSV) = Revenue - COGS
      gross_margin_pct    = Gross Margin / Revenue
      net_revenue         = Revenue × (1 - Customer Bonus - EPD)
      net_cogs            = COGS × (1 - Supplier Bonus)
      net_margin          = Net Revenue - Net Cogs
      net_margin_pct      = Net Margin / Net Revenue
    """

    def __init__(self, csv_path: str, channel_filter: str = 'B2B 2 Step'):
        self.csv_path = csv_path
        self.channel_filter = channel_filter
        self._df: Optional[pd.DataFrame] = None
        self._sku_yearly: Optional[pd.DataFrame] = None

    # ── Loading ───────────────────────────────────────────────────────────────
    def load(self) -> 'DataModel':
        """Load CSV or SQL, normalize columns, filter channel, compute calculated fields."""
        use_sql = os.getenv("USE_SQL", "False").lower() in ('true', '1', 't', 'yes')
        
        if use_sql:
            print("[DataModel] USE_SQL is True. Loading from SQL Server...")
            from core.sql_connector import load_data_from_sql
            iterator = [load_data_from_sql()]
        else:
            print(f"[DataModel] Loading CSV from {self.csv_path}...")
            iterator = pd.read_csv(
                self.csv_path,
                chunksize=200_000,
                low_memory=False,
            )

        chunks = []
        for i, chunk in enumerate(iterator):
            # Normalize column names: strip quotes and whitespace
            chunk.columns = [c.strip('"').strip() for c in chunk.columns]

            # Rename to internal names
            rename_map = {}
            for csv_col, internal_col in CSV_COLS.items():
                # Try exact match first, then stripped match
                csv_col_stripped = csv_col.strip()
                if csv_col_stripped in chunk.columns:
                    rename_map[csv_col_stripped] = internal_col
                elif csv_col in chunk.columns:
                    rename_map[csv_col] = internal_col
            chunk.rename(columns=rename_map, inplace=True)

            # Channel filter
            if 'CHANNEL' in chunk.columns and self.channel_filter:
                chunk = chunk[chunk['CHANNEL'] == self.channel_filter]
            if len(chunk) == 0:
                continue

            # Coerce numerics
            for col in NUMERIC_COLS:
                if col in chunk.columns:
                    chunk[col] = pd.to_numeric(chunk[col], errors='coerce').fillna(0)

            # Coerce year/month to int
            if 'YEAR' in chunk.columns:
                chunk['YEAR'] = pd.to_numeric(chunk['YEAR'], errors='coerce').fillna(0).astype(int)
            if 'MONTH' in chunk.columns:
                chunk['MONTH'] = pd.to_numeric(chunk['MONTH'], errors='coerce').fillna(0).astype(int)

            chunks.append(chunk)
            if (i + 1) % 5 == 0:
                print(f"[DataModel]   processed {(i+1)*200_000:,} rows...")

        if not chunks:
            raise RuntimeError(f"No data found after filtering channel='{self.channel_filter}'")

        self._df = pd.concat(chunks, ignore_index=True)
        print(f"[DataModel] Loaded {len(self._df):,} records.")

        # ── Computed Fields ───────────────────────────────────────────────────
        self._compute_fields()
        return self

    def _compute_fields(self):
        """Add all model-driven calculated columns."""
        df = self._df

        # Gross Margin % = Gross Margin / Revenue
        df['GROSS_MARGIN_PCT'] = np.where(
            df['REVENUE'] != 0,
            df['GROSS_MARGIN'] / df['REVENUE'],
            0
        )

        # Net Revenue = Revenue × (1 - Customer Bonus - EPD)
        df['NET_REVENUE'] = df['REVENUE'] * (1 - df['CUSTOMER_BONUS'] - df['EPD'])

        # Net COGS = COGS × (1 - Supplier Bonus)
        df['NET_COGS'] = df['COGS'] * (1 - df['SUPPLIER_BONUS'])

        # Net Margin = Net Revenue - Net COGS
        df['NET_MARGIN'] = df['NET_REVENUE'] - df['NET_COGS']

        # Net Margin % = Net Margin / Net Revenue
        df['NET_MARGIN_PCT'] = np.where(
            df['NET_REVENUE'] != 0,
            df['NET_MARGIN'] / df['NET_REVENUE'],
            0
        )

        # Replace infinities
        df.replace([np.inf, -np.inf], 0, inplace=True)

    # ── Accessors ─────────────────────────────────────────────────────────────
    @property
    def df(self) -> pd.DataFrame:
        if self._df is None:
            raise RuntimeError("DataModel not loaded. Call .load() first.")
        return self._df

    @property
    def years(self) -> List[int]:
        return sorted(self.df['YEAR'].unique().tolist())

    @property
    def categories(self) -> List[str]:
        return sorted(self.df['CATEGORY'].dropna().unique().tolist())

    @property
    def brands(self) -> List[str]:
        return sorted(self.df['BRAND'].dropna().unique().tolist())

    @property
    def pgs_list(self) -> List[str]:
        return sorted(self.df['PGS'].dropna().unique().tolist())

    # ── SKU-Year Aggregation (for price optimization) ─────────────────────────
    def get_sku_yearly(self, force=False) -> pd.DataFrame:
        """Aggregate to PNO × Year level with all key metrics."""
        if self._sku_yearly is not None and not force:
            return self._sku_yearly

        df = self.df
        agg = df.groupby(['PNO', 'YEAR']).agg({
            'BRAND':           'first',
            'CATEGORY':        'first',
            'PGS':             'first',
            'PGS_SEGMENT':     'first',
            'FAMILY_NAME':     'first',
            'QTY':             'sum',
            'REVENUE':         'sum',
            'COGS':            'sum',
            'GROSS_MARGIN':    'sum',
            'SELLING_PRICE':   'mean',    # avg selling price
            'PURCHASE_PRICE':  'mean',    # avg purchase price
            'CUSTOMER_BONUS':  'mean',
            'EPD':             'mean',
            'SUPPLIER_BONUS':  'mean',
            'NET_REVENUE':     'sum',
            'NET_COGS':        'sum',
            'NET_MARGIN':      'sum',
        }).reset_index()

        # Recompute per-unit metrics after aggregation
        agg['SELLING_PRICE_CALC'] = np.where(agg['QTY'] != 0, agg['REVENUE'] / agg['QTY'], 0)
        agg['PURCHASE_PRICE_CALC'] = np.where(agg['QTY'] != 0, agg['COGS'] / agg['QTY'], 0)
        agg['GROSS_MARGIN_PCT'] = np.where(agg['REVENUE'] != 0, agg['GROSS_MARGIN'] / agg['REVENUE'], 0)
        agg['NET_MARGIN_PCT'] = np.where(agg['NET_REVENUE'] != 0, agg['NET_MARGIN'] / agg['NET_REVENUE'], 0)

        agg.replace([np.inf, -np.inf], 0, inplace=True)
        self._sku_yearly = agg
        print(f"[DataModel] SKU-Year aggregation: {len(agg):,} records across {agg['YEAR'].nunique()} years.")
        return agg

    def get_sku_paired(self, y_prev: int = 2024, y_curr: int = 2025) -> pd.DataFrame:
        """
        Merge two years of SKU data for YoY comparison.
        Returns one row per SKU with _prev and _curr suffixed columns.
        """
        sky = self.get_sku_yearly()
        years = sorted(sky['YEAR'].unique().tolist())

        if y_prev not in years:
            if y_prev == 2024 and 2025 in years and 2026 in years:
                y_prev, y_curr = 2025, 2026
                print(f"[DataModel] Fallback: using {y_prev} vs {y_curr}")
            else:
                raise RuntimeError(f"Required year {y_prev} not in data. Available: {years}")

        df_prev = sky[sky['YEAR'] == y_prev].copy()
        df_curr = sky[sky['YEAR'] == y_curr].copy()
        print(f"[DataModel] Pairing: {y_prev}={len(df_prev):,} SKUs, {y_curr}={len(df_curr):,} SKUs")

        # Merge with suffixes
        merged = pd.merge(
            df_curr, df_prev[['PNO', 'QTY', 'REVENUE', 'COGS', 'GROSS_MARGIN',
                               'SELLING_PRICE', 'PURCHASE_PRICE',
                               'CUSTOMER_BONUS', 'EPD', 'SUPPLIER_BONUS',
                               'NET_REVENUE', 'NET_COGS', 'NET_MARGIN',
                               'SELLING_PRICE_CALC', 'PURCHASE_PRICE_CALC',
                               'GROSS_MARGIN_PCT', 'NET_MARGIN_PCT']],
            on='PNO', how='inner', suffixes=('_curr', '_prev')
        )

        # Net Margin 2024 override: Revenue_prev × (1 - (CustomerBonus_curr + EPD_prev))
        merged['NET_MARGIN_ADJUSTED_PREV'] = (
            merged['REVENUE_prev'] * (1 - (merged['CUSTOMER_BONUS_curr'] + merged['EPD_prev']))
        )

        print(f"[DataModel] Paired SKUs: {len(merged):,}")
        return merged


class KPIEngine:
    """
    Centralized KPI calculations.
    All metrics are derived from the DataModel — zero hardcoding in dashboards.
    """

    def __init__(self, model: DataModel):
        self.model = model

    # ── Time-based metrics ────────────────────────────────────────────────────
    def total_revenue(self, year: int, month: Optional[int] = None) -> float:
        df = self.model.df[self.model.df['YEAR'] == year]
        if month is not None:
            df = df[df['MONTH'] == month]
        return float(df['REVENUE'].sum())

    def total_cogs(self, year: int, month: Optional[int] = None) -> float:
        df = self.model.df[self.model.df['YEAR'] == year]
        if month is not None:
            df = df[df['MONTH'] == month]
        return float(df['COGS'].sum())

    def total_quantity(self, year: int, month: Optional[int] = None) -> float:
        df = self.model.df[self.model.df['YEAR'] == year]
        if month is not None:
            df = df[df['MONTH'] == month]
        return float(df['QTY'].sum())

    def total_gross_margin(self, year: int, month: Optional[int] = None) -> float:
        df = self.model.df[self.model.df['YEAR'] == year]
        if month is not None:
            df = df[df['MONTH'] == month]
        return float(df['GROSS_MARGIN'].sum())

    def total_net_revenue(self, year: int, month: Optional[int] = None) -> float:
        df = self.model.df[self.model.df['YEAR'] == year]
        if month is not None:
            df = df[df['MONTH'] == month]
        return float(df['NET_REVENUE'].sum())

    def total_net_margin(self, year: int, month: Optional[int] = None) -> float:
        df = self.model.df[self.model.df['YEAR'] == year]
        if month is not None:
            df = df[df['MONTH'] == month]
        return float(df['NET_MARGIN'].sum())

    def avg_selling_price(self, year: int) -> float:
        df = self.model.df[self.model.df['YEAR'] == year]
        rev = df['REVENUE'].sum()
        qty = df['QTY'].sum()
        return float(rev / qty) if qty > 0 else 0.0

    def avg_purchase_price(self, year: int) -> float:
        df = self.model.df[self.model.df['YEAR'] == year]
        cogs = df['COGS'].sum()
        qty = df['QTY'].sum()
        return float(cogs / qty) if qty > 0 else 0.0

    # ── Growth metrics ────────────────────────────────────────────────────────
    def yoy_growth(self, metric: str, y_curr: int, y_prev: int) -> float:
        """Year-over-year growth for a given metric."""
        func_map = {
            'revenue': self.total_revenue,
            'cogs': self.total_cogs,
            'quantity': self.total_quantity,
            'gross_margin': self.total_gross_margin,
            'net_revenue': self.total_net_revenue,
            'net_margin': self.total_net_margin,
        }
        fn = func_map.get(metric)
        if fn is None:
            return 0.0
        prev = fn(y_prev)
        curr = fn(y_curr)
        return ((curr - prev) / prev * 100) if prev != 0 else 0.0

    def mom_growth(self, metric: str, year: int, month: int) -> float:
        """Month-over-month growth."""
        func_map = {
            'revenue': self.total_revenue,
            'cogs': self.total_cogs,
            'quantity': self.total_quantity,
            'gross_margin': self.total_gross_margin,
            'net_revenue': self.total_net_revenue,
            'net_margin': self.total_net_margin,
        }
        fn = func_map.get(metric)
        if fn is None:
            return 0.0
        curr = fn(year, month)
        # Previous month (handle Jan → Dec of prev year)
        prev_m = month - 1 if month > 1 else 12
        prev_y = year if month > 1 else year - 1
        prev = fn(prev_y, prev_m)
        return ((curr - prev) / prev * 100) if prev != 0 else 0.0

    # ── Monthly trends ────────────────────────────────────────────────────────
    def monthly_trends(self, years: Optional[List[int]] = None) -> List[Dict[str, Any]]:
        """Return monthly KPI breakdown for charting."""
        df = self.model.df
        if years:
            df = df[df['YEAR'].isin(years)]

        grouped = df.groupby(['YEAR', 'MONTH']).agg({
            'REVENUE':      'sum',
            'COGS':         'sum',
            'QTY':          'sum',
            'GROSS_MARGIN': 'sum',
            'NET_REVENUE':  'sum',
            'NET_MARGIN':   'sum',
        }).reset_index()

        month_names = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                       'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

        result = []
        for _, row in grouped.sort_values(['YEAR', 'MONTH']).iterrows():
            m = int(row['MONTH'])
            y = int(row['YEAR'])
            label = f"{month_names[m]} {str(y)[-2:]}" if 1 <= m <= 12 else f"M{m} {str(y)[-2:]}"
            result.append({
                'label':       label,
                'year':        y,
                'month':       m,
                'revenue':     round(float(row['REVENUE']), 2),
                'cogs':        round(float(row['COGS']), 2),
                'quantity':    int(row['QTY']),
                'grossMargin': round(float(row['GROSS_MARGIN']), 2),
                'netRevenue':  round(float(row['NET_REVENUE']), 2),
                'netMargin':   round(float(row['NET_MARGIN']), 2),
            })
        return result

    # ── Aggregation by dimension ──────────────────────────────────────────────
    def by_dimension(self, dimension: str, year: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Aggregate KPIs by a given dimension (CATEGORY, BRAND, PGS).
        Returns sorted list of dicts.
        """
        df = self.model.df
        if year:
            df = df[df['YEAR'] == year]

        grouped = df.groupby(dimension).agg({
            'REVENUE':      'sum',
            'COGS':         'sum',
            'QTY':          'sum',
            'GROSS_MARGIN': 'sum',
            'NET_REVENUE':  'sum',
            'NET_MARGIN':   'sum',
            'PNO':          'nunique',
        }).reset_index()

        grouped.rename(columns={'PNO': 'SKU_COUNT'}, inplace=True)
        grouped['GROSS_MARGIN_PCT'] = np.where(
            grouped['REVENUE'] != 0, grouped['GROSS_MARGIN'] / grouped['REVENUE'] * 100, 0
        )
        grouped['NET_MARGIN_PCT'] = np.where(
            grouped['NET_REVENUE'] != 0, grouped['NET_MARGIN'] / grouped['NET_REVENUE'] * 100, 0
        )
        grouped['AVG_SELLING_PRICE'] = np.where(
            grouped['QTY'] != 0, grouped['REVENUE'] / grouped['QTY'], 0
        )
        grouped['AVG_PURCHASE_PRICE'] = np.where(
            grouped['QTY'] != 0, grouped['COGS'] / grouped['QTY'], 0
        )

        result = []
        for _, row in grouped.sort_values('REVENUE', ascending=False).iterrows():
            result.append({
                'name':             str(row[dimension]),
                'revenue':          round(float(row['REVENUE']), 2),
                'cogs':             round(float(row['COGS']), 2),
                'quantity':         int(row['QTY']),
                'grossMargin':      round(float(row['GROSS_MARGIN']), 2),
                'grossMarginPct':   round(float(row['GROSS_MARGIN_PCT']), 2),
                'netRevenue':       round(float(row['NET_REVENUE']), 2),
                'netMargin':        round(float(row['NET_MARGIN']), 2),
                'netMarginPct':     round(float(row['NET_MARGIN_PCT']), 2),
                'avgSellingPrice':  round(float(row['AVG_SELLING_PRICE']), 2),
                'avgPurchasePrice': round(float(row['AVG_PURCHASE_PRICE']), 2),
                'skuCount':         int(row['SKU_COUNT']),
            })
        return result

    # ── Full KPI snapshot ─────────────────────────────────────────────────────
    def kpi_snapshot(self) -> Dict[str, Any]:
        """Return a complete KPI package for the frontend."""
        years = self.model.years
        snapshot: Dict[str, Any] = {'years': years, 'yearly': {}}

        for y in years:
            rev = self.total_revenue(y)
            cogs = self.total_cogs(y)
            qty = self.total_quantity(y)
            gm = self.total_gross_margin(y)
            nr = self.total_net_revenue(y)
            nm = self.total_net_margin(y)
            asp = self.avg_selling_price(y)
            app = self.avg_purchase_price(y)

            snapshot['yearly'][str(y)] = {
                'revenue':          round(rev, 2),
                'cogs':             round(cogs, 2),
                'quantity':         int(qty),
                'grossMargin':      round(gm, 2),
                'grossMarginPct':   round(gm / rev * 100, 2) if rev else 0,
                'netRevenue':       round(nr, 2),
                'netMargin':        round(nm, 2),
                'netMarginPct':     round(nm / nr * 100, 2) if nr else 0,
                'avgSellingPrice':  round(asp, 2),
                'avgPurchasePrice': round(app, 2),
                'skuCount':         int(self.model.df[self.model.df['YEAR'] == y]['PNO'].nunique()),
                'brandCount':       int(self.model.df[self.model.df['YEAR'] == y]['BRAND'].nunique()),
                'categoryCount':    int(self.model.df[self.model.df['YEAR'] == y]['CATEGORY'].nunique()),
            }

        # YoY growth (if at least 2 years)
        if len(years) >= 2:
            y1, y2 = years[-2], years[-1]
            snapshot['yoyGrowth'] = {
                'years': [y1, y2],
                'revenue':     round(self.yoy_growth('revenue', y2, y1), 2),
                'cogs':        round(self.yoy_growth('cogs', y2, y1), 2),
                'quantity':    round(self.yoy_growth('quantity', y2, y1), 2),
                'grossMargin': round(self.yoy_growth('gross_margin', y2, y1), 2),
                'netRevenue':  round(self.yoy_growth('net_revenue', y2, y1), 2),
                'netMargin':   round(self.yoy_growth('net_margin', y2, y1), 2),
            }

        # Dimension breakdowns (latest year)
        ly = years[-1] if years else None
        snapshot['byCategory'] = self.by_dimension('CATEGORY', ly)
        snapshot['byBrand']    = self.by_dimension('BRAND', ly)
        snapshot['byPGS']      = self.by_dimension('PGS', ly)

        return snapshot
