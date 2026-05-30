"""
PriceIQ Price Optimizer — ML-driven pricing recommendations.

Uses the DataModel for data access. Contains:
  - S-Curve demand model (interpretable, primary)
  - Feature engineering for elasticity calibration
  - Per-SKU optimization via grid search
  - Evaluation metrics (MAPE, R²)

Selling Price = AVG Price (price per item sold to customer)
Purchase Price = Unit Cogs (cost to acquire the product)
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Any, Optional, Tuple
from core.data_model import DataModel


# ─── S-Curve Demand Model ────────────────────────────────────────────────────
def sigmoid_demand(dp: float, k: float = 10.0, x0: float = 0.05, L: float = 1.1) -> float:
    """S-Curve: maps relative price change dp to volume multiplier shift."""
    exponent = np.clip(k * (dp + x0), -300, 300)
    return L / (1 + np.exp(exponent)) - (L / 2)


def find_inflection_point(k: float, x0: float = 0.05) -> float:
    """Inflection point of the sigmoid is at -x0."""
    return -x0


def detect_saturation_threshold(k: float, x0: float = 0.05, L: float = 1.1,
                                 threshold: float = 0.02) -> float:
    """Find price change point where marginal volume gain < 2%."""
    for dp in np.linspace(-0.3, 0.1, 40):
        slope = abs(sigmoid_demand(dp + 0.01, k, x0, L) - sigmoid_demand(dp, k, x0, L)) / 0.01
        if slope < threshold:
            return dp
    return -0.25


def calc_mape(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    m = y_true != 0
    return float(np.mean(np.abs((y_true[m] - y_pred[m]) / y_true[m])) * 100) if m.any() else 0.0


# ─── Price Optimizer ──────────────────────────────────────────────────────────
class PriceOptimizer:
    """
    ML-driven price optimization engine.
    
    Feature List:
      - price (AVG Price / Selling Price)
      - price_change_pct (YoY selling price delta)
      - quantity (demand volume)
      - revenue
      - gross_margin_pct
      - customer_bonus, epd, supplier_bonus
      - brand, category, pgs (encoded)
      
    Training Approach:
      - Calibrate S-Curve k-factor per Brand/Category/PGS from observed elasticity
      - Grid search optimization over ±20% price range
      
    Evaluation Metrics:
      - MAPE on volume prediction
      - R² on volume prediction per brand
      - Revenue uplift simulation
    """

    def __init__(self, data_model: DataModel, bonus_pct: float = 0.15):
        self.data_model = data_model
        self.bonus_pct = bonus_pct

        # Elasticity calibration results
        self.g_elast: float = -1.5
        self.k_global: float = 3.0
        self.br_elast: Dict[str, float] = {}
        self.br_k: Dict[str, float] = {}
        self.cat_elast: Dict[str, float] = {}
        self.cat_k: Dict[str, float] = {}
        self.pgs_elast: Dict[str, float] = {}
        self.pgs_k: Dict[str, float] = {}

        # Model fit metrics
        self.mape: float = 0.0
        self.r2: float = 0.0
        self.n_train: int = 0

    def run(self, y_prev: int = 2024, y_curr: int = 2025,
            max_skus: int = 50_000) -> Dict[str, Any]:
        """
        Full optimization pipeline:
          1. Get paired SKU data from DataModel
          2. Feature engineering (price changes, elasticity)
          3. Calibrate S-Curve per dimension
          4. Optimize each SKU
          5. Return results
        """
        # Step 1: Get paired data
        df = self.data_model.get_sku_paired(y_prev, y_curr)

        # Step 2: Feature engineering
        df = self._feature_engineering(df, max_skus)

        # Step 3: Calibrate elasticity
        tr = self._calibrate_elasticity(df)

        # Step 4: Evaluate model fit
        self._evaluate_model(tr)

        # Step 5: Optimize each SKU
        recommendations = self._optimize_skus(df)

        # Step 6: Build raw data list
        raw_data = self._build_raw_data(df)

        # Step 7: Build model info
        model_info = self._build_model_info(tr)

        return {
            'rawData': raw_data,
            'recommendations': recommendations,
            'model': model_info,
        }

    # ── Feature Engineering ───────────────────────────────────────────────────
    def _feature_engineering(self, df: pd.DataFrame, max_skus: int) -> pd.DataFrame:
        """Compute all features needed for elasticity and optimization."""
        # Limit to top N SKUs by current-year revenue
        if len(df) > max_skus:
            print(f"[Optimizer] Limiting to top {max_skus:,} SKUs by revenue.")
            df = df.sort_values('REVENUE_curr', ascending=False).head(max_skus).copy()

        # Filter: need positive qty in both years
        df = df[
            (df['QTY_curr'] > 0) & (df['QTY_prev'] > 0) &
            (df['REVENUE_curr'] > 0) & (df['REVENUE_prev'] > 0)
        ].copy()
        df['PNO'] = df['PNO'].astype(str)

        # Selling price per unit (from data model)
        df['ASP_PREV'] = df['SELLING_PRICE_CALC_prev']   # selling price prev year
        df['ASP_CURR'] = df['SELLING_PRICE_CALC_curr']   # selling price curr year
        df['ACP_CURR'] = df['PURCHASE_PRICE_CALC_curr']  # purchase price curr year

        # Guard against zero/inf
        df = df[(df['ASP_PREV'] > 0) & (df['ASP_CURR'] > 0) & (df['ACP_CURR'] > 0)].copy()
        df.replace([np.inf, -np.inf], np.nan, inplace=True)
        df.dropna(subset=['ASP_PREV', 'ASP_CURR', 'ACP_CURR'], inplace=True)

        # Net margin per unit (current year)
        df['NM_PER_UNIT'] = np.where(
            df['QTY_curr'] != 0,
            df['NET_MARGIN_curr'] / df['QTY_curr'],
            0
        )

        # Price and volume changes (features)
        df['PCT_CHANGE_PRICE'] = (df['ASP_CURR'] - df['ASP_PREV']) / df['ASP_PREV']
        df['PCT_CHANGE_VOL'] = (df['QTY_curr'] - df['QTY_prev']) / df['QTY_prev']
        df['PCT_CHANGE_PRICE'] = df['PCT_CHANGE_PRICE'].replace([np.inf, -np.inf], 0)
        df['PCT_CHANGE_VOL'] = df['PCT_CHANGE_VOL'].replace([np.inf, -np.inf], 0)

        # Trend factor (capped)
        df['TREND_FACTOR'] = (df['QTY_curr'] / df['QTY_prev']).clip(0.5, 2.0)
        df['TREND_FACTOR'] = df['TREND_FACTOR'].fillna(1.0)

        # Baseline volume for next year
        df['BASELINE_VOL_NEXT'] = df['QTY_curr'] * df['TREND_FACTOR']

        # Ensure dimension columns
        for col in ['BRAND', 'CATEGORY', 'PGS']:
            if col not in df.columns:
                df[col] = 'Unknown'

        print(f"[Optimizer] Features computed for {len(df):,} SKUs.")
        return df

    # ── Elasticity Calibration ────────────────────────────────────────────────
    def _calibrate_elasticity(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calibrate S-Curve k-factor from observed price-volume elasticity."""
        mask = (
            df['PCT_CHANGE_PRICE'].abs().between(0.005, 0.5) &
            (df['PCT_CHANGE_VOL'].abs() < 2.0)
        )
        tr = df[mask].dropna(subset=['PCT_CHANGE_PRICE', 'PCT_CHANGE_VOL']).copy()
        tr['elast'] = tr['PCT_CHANGE_VOL'] / tr['PCT_CHANGE_PRICE']
        tr['elast'] = tr['elast'].replace([np.inf, -np.inf], np.nan)
        tr = tr.dropna(subset=['elast'])

        self.g_elast = float(np.median(tr['elast'])) if len(tr) > 0 else -1.5
        self.k_global = abs(self.g_elast) * 3.5 if abs(self.g_elast) > 0.05 else 3.0

        # Per-brand
        self.br_elast, self.br_k = self._calibrate_dimension(tr, 'BRAND')
        # Per-category
        self.cat_elast, self.cat_k = self._calibrate_dimension(tr, 'CATEGORY')
        # Per-PGS
        self.pgs_elast, self.pgs_k = self._calibrate_dimension(tr, 'PGS')

        self.n_train = len(tr)
        print(f"[Optimizer] Elasticity calibrated: global_k={self.k_global:.2f}, "
              f"g_elast={self.g_elast:.3f}, training_points={self.n_train}")
        return tr

    def _calibrate_dimension(self, tr: pd.DataFrame, dim: str) -> Tuple[Dict, Dict]:
        elast_map = {}
        k_map = {}
        if len(tr) > 0 and dim in tr.columns:
            for name, grp in tr.groupby(dim):
                med_e = float(np.median(grp['elast'])) if len(grp) > 0 else np.nan
                key = str(name)
                elast_map[key] = med_e if not np.isnan(med_e) else self.g_elast
                k_map[key] = (abs(med_e) * 3.5 if (not np.isnan(med_e) and abs(med_e) > 0.05)
                              else self.k_global)
        return elast_map, k_map

    # ── Model Evaluation ──────────────────────────────────────────────────────
    def _evaluate_model(self, tr: pd.DataFrame):
        """Compute MAPE and R² for the S-Curve fit."""
        if len(tr) == 0:
            self.mape, self.r2 = 0.0, 0.0
            return

        X = tr['PCT_CHANGE_PRICE'].values
        Y = (1 + tr['PCT_CHANGE_VOL']).values
        y_pred = np.array([1.0 + sigmoid_demand(x, k=self.k_global) for x in X])
        self.mape = calc_mape(Y, y_pred)

        # R² per brand
        r2_scores = []
        for brand, bt in tr.groupby('BRAND'):
            if len(bt) > 3:
                bX = bt['PCT_CHANGE_PRICE'].values
                bY = (1 + bt['PCT_CHANGE_VOL']).values
                bk = self.br_k.get(str(brand), self.k_global)
                by_pred = np.array([1.0 + sigmoid_demand(x, k=bk) for x in bX])
                ss_res = np.sum((bY - by_pred) ** 2)
                ss_tot = np.sum((bY - np.mean(bY)) ** 2)
                if ss_tot > 0:
                    r2_scores.append(max(0, 1 - ss_res / ss_tot))
        self.r2 = float(np.mean(r2_scores)) if r2_scores else 0.0

    # ── SKU Optimization ──────────────────────────────────────────────────────
    def _optimize_skus(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """Optimize each SKU's price to maximize Net Margin using vectorized numpy operations."""
        dp_range = np.linspace(-0.20, 0.20, 81)
        bp = df['ASP_CURR'].values
        bc = df['ACP_CURR'].values
        bq = df['BASELINE_VOL_NEXT'].values

        sk = np.zeros(len(df))
        for i, (pgs, cat, br) in enumerate(zip(df.get('PGS', ['']*len(df)), df.get('CATEGORY', ['']*len(df)), df.get('BRAND', ['']*len(df)))):
            k = self.pgs_k.get(str(pgs), self.cat_k.get(str(cat), self.br_k.get(str(br), self.k_global)))
            sk[i] = k

        nmpu = df.get('NM_PER_UNIT', pd.Series([np.nan]*len(df))).values
        has_nmpu = pd.notna(nmpu)

        base_gp = (bp - bc) * bq
        base_rev = bp * bq
        base_nm = np.where(has_nmpu, nmpu * bq, base_gp - base_rev * self.bonus_pct)

        mn = np.maximum(bp * 0.80, bc * 1.05)
        mx = bp * 1.20

        best_nm = base_nm.copy()
        best_dp = np.zeros(len(df))
        rev_max_val = base_rev.copy()
        rev_max_dp = np.zeros(len(df))
        
        roi_max_val = np.zeros(len(df))
        mask_roi = bc > 0
        roi_max_val[mask_roi] = base_nm[mask_roi] / (bc[mask_roi] * bq[mask_roi])
        roi_max_dp = np.zeros(len(df))

        mask_mn = bp < mn
        if np.any(mask_mn):
            best_dp[mask_mn] = (mn[mask_mn] / bp[mask_mn]) - 1
            best_op = bp[mask_mn] * (1 + best_dp[mask_mn])
            best_vm = 1.0 + (1.1 / (1 + np.exp(np.clip(sk[mask_mn] * (best_dp[mask_mn] + 0.05), -300, 300))) - 0.55)
            best_nq = bq[mask_mn] * np.maximum(0.1, best_vm)
            best_ngp = (best_op - bc[mask_mn]) * best_nq
            
            nmpu_m = nmpu[mask_mn]
            bp_m = bp[mask_mn]
            bdp_m = best_dp[mask_mn]
            has_nmpu_m = has_nmpu[mask_mn]
            bonus = self.bonus_pct
            
            best_nm_mn = np.where(has_nmpu_m,
                (nmpu_m + bp_m * bdp_m * (1 - bonus)) * best_nq,
                best_ngp - best_op * best_nq * bonus)
                
            best_nm[mask_mn] = best_nm_mn

        dp_grid = dp_range[:, None]
        sk_grid = sk[None, :]
        bp_grid = bp[None, :]
        bc_grid = bc[None, :]
        bq_grid = bq[None, :]
        mn_grid = mn[None, :]
        mx_grid = mx[None, :]
        nmpu_grid = nmpu[None, :]
        has_nmpu_grid = has_nmpu[None, :]

        np_grid = bp_grid * (1 + dp_grid)
        valid_mask = (np_grid >= mn_grid) & (np_grid <= mx_grid)

        exponent = np.clip(sk_grid * (dp_grid + 0.05), -300, 300)
        vm = 1.0 + (1.1 / (1 + np.exp(exponent)) - 0.55)

        nq = bq_grid * np.maximum(0.1, vm)
        nrev = np_grid * nq
        ngp = (np_grid - bc_grid) * nq

        nnm = np.where(has_nmpu_grid,
            (nmpu_grid + bp_grid * dp_grid * (1 - self.bonus_pct)) * nq,
            ngp - nrev * self.bonus_pct)

        nnm[~valid_mask] = -np.inf
        nrev[~valid_mask] = -np.inf

        max_nnm_idx = np.argmax(nnm, axis=0)
        max_nnm_val = np.take_along_axis(nnm, max_nnm_idx[None, :], axis=0)[0]
        update_mask = max_nnm_val > best_nm
        best_nm[update_mask] = max_nnm_val[update_mask]
        best_dp[update_mask] = dp_range[max_nnm_idx[update_mask]]

        max_rev_idx = np.argmax(nrev, axis=0)
        max_rev_val = np.take_along_axis(nrev, max_rev_idx[None, :], axis=0)[0]
        update_mask = max_rev_val > rev_max_val
        rev_max_val[update_mask] = max_rev_val[update_mask]
        rev_max_dp[update_mask] = dp_range[max_rev_idx[update_mask]]

        bc_grid_0 = bc_grid > 0
        nq_0 = nq > 0
        nroi = np.zeros_like(nnm)
        roi_valid = bc_grid_0 & nq_0 & valid_mask
        bc_nq = bc_grid * nq
        nroi[roi_valid] = nnm[roi_valid] / bc_nq[roi_valid]
        nroi[~roi_valid] = -np.inf

        max_roi_idx = np.argmax(nroi, axis=0)
        max_roi_val = np.take_along_axis(nroi, max_roi_idx[None, :], axis=0)[0]
        update_mask = max_roi_val > roi_max_val
        roi_max_val[update_mask] = max_roi_val[update_mask]
        roi_max_dp[update_mask] = dp_range[max_roi_idx[update_mask]]

        inflection_dp = -0.05 * np.ones(len(df))
        saturation_dp = np.array([detect_saturation_threshold(k) for k in sk])
        is_saturated = (0.0 < saturation_dp).astype(int)

        op = bp * (1 + best_dp)
        om = 1.0 + (1.1 / (1 + np.exp(np.clip(sk * (best_dp + 0.05), -300, 300))) - 0.55)
        oq = (bq * np.maximum(0.1, om)).astype(int)
        ogp = (op - bc) * oq
        orev = op * oq
        onm = np.where(has_nmpu,
            (nmpu + bp * best_dp * (1 - self.bonus_pct)) * oq,
            ogp - orev * self.bonus_pct)

        rec_label = np.where(best_dp > 0.002, 'INCREASE', np.where(best_dp < -0.002, 'DECREASE', 'HOLD'))

        out_df = pd.DataFrame()
        out_df['PNO'] = df['PNO'].astype(str)
        out_df['Brand'] = df.get('BRAND', pd.Series(['N/A']*len(df))).fillna('N/A').astype(str)
        out_df['Category'] = df.get('CATEGORY', pd.Series(['N/A']*len(df))).fillna('N/A').astype(str)
        out_df['PGS'] = df.get('PGS', pd.Series(['N/A']*len(df))).fillna('N/A').astype(str)
        out_df['SellingPrice'] = np.round(bp, 2)
        out_df['PurchasePrice'] = np.round(bc, 2)
        out_df['CurrentPrice'] = np.round(bp, 2)
        out_df['CurrentCost'] = np.round(bc, 2)
        out_df['BaselineVol2026'] = bq.astype(int)
        out_df['BaselineProfit2026'] = np.round(base_gp, 0)
        out_df['CurrentRev2025'] = np.round(df['REVENUE_curr'].values.astype(float), 2)
        out_df['CurrentVol2025'] = df['QTY_curr'].values.astype(int)

        if 'GROSS_MARGIN_PCT_curr' in df:
            out_df['GrossMarginPct'] = np.round(df['GROSS_MARGIN_PCT_curr'].values.astype(float) * 100, 2)
        else:
            out_df['GrossMarginPct'] = 0.0

        if 'NET_MARGIN_PCT_curr' in df:
            out_df['NetMarginPct'] = np.round(df['NET_MARGIN_PCT_curr'].values.astype(float) * 100, 2)
        else:
            out_df['NetMarginPct'] = 0.0

        if 'CUSTOMER_BONUS_curr' in df:
            out_df['CustomerBonus'] = np.round(df['CUSTOMER_BONUS_curr'].values.astype(float), 4)
        else:
            out_df['CustomerBonus'] = 0.0

        if 'EPD_curr' in df:
            out_df['EPD'] = np.round(df['EPD_curr'].values.astype(float), 4)
        else:
            out_df['EPD'] = 0.0

        if 'SUPPLIER_BONUS_curr' in df:
            out_df['SupplierBonus'] = np.round(df['SUPPLIER_BONUS_curr'].values.astype(float), 4)
        else:
            out_df['SupplierBonus'] = 0.0

        out_df['OptimalPrice'] = np.round(op, 2)
        out_df['RecChange'] = np.round(best_dp, 4)
        out_df['OptVol'] = oq
        out_df['OptRev'] = np.round(orev, 0)
        out_df['OptimizedProfit2026'] = np.round(ogp, 0)
        out_df['ProfitUplift'] = np.round(ogp - base_gp, 0)
        out_df['BaseNM'] = np.round(base_nm, 0)
        out_df['OptNM'] = np.round(best_nm, 0)
        out_df['NetMarginUplift'] = np.round(best_nm - base_nm, 0)

        own_e = np.zeros(len(df))
        for i, br in enumerate(df.get('BRAND', ['']*len(df))):
            own_e[i] = self.br_elast.get(str(br), self.g_elast)
        out_df['OwnElasticity'] = np.round(own_e, 3)

        out_df['Recommendation'] = rec_label
        out_df['BrandK'] = np.round(sk, 2)
        out_df['RevMaxPrice'] = np.round(bp * (1 + rev_max_dp), 2)
        out_df['RevMaxDelta'] = np.round(rev_max_dp, 4)
        out_df['ROIMaxPrice'] = np.round(bp * (1 + roi_max_dp), 2)
        out_df['ROIMaxDelta'] = np.round(roi_max_dp, 4)
        out_df['InflectionDelta'] = np.round(inflection_dp, 4)
        out_df['SaturationDelta'] = np.round(saturation_dp, 4)
        out_df['IsSaturated'] = is_saturated.astype(bool)

        recs = out_df.to_dict('records')
        for rec in recs:
            for k, v in rec.items():
                if isinstance(v, (np.integer, np.int64, np.int32)):
                    rec[k] = int(v)
                elif isinstance(v, (np.floating, np.float64, np.float32)):
                    rec[k] = float(v)
        
        print(f"[Optimizer] Generated {len(recs):,} recommendations using vectorized optimization.")
        return recs

    def _build_raw_data(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        out_df = pd.DataFrame()
        out_df['PNO'] = df['PNO'].astype(str)
        out_df['Brand'] = df.get('BRAND', pd.Series(['N/A']*len(df))).fillna('N/A').astype(str)
        out_df['Category'] = df.get('CATEGORY', pd.Series(['N/A']*len(df))).fillna('N/A').astype(str)
        out_df['PGS'] = df.get('PGS', pd.Series(['N/A']*len(df))).fillna('N/A').astype(str)
        out_df['QTY_2024'] = df['QTY_prev'].astype(float)
        out_df['QTY_2025'] = df['QTY_curr'].astype(float)
        out_df['SALES_2024'] = df['REVENUE_prev'].astype(float)
        out_df['SALES_2025'] = df['REVENUE_curr'].astype(float)
        out_df['COST_2024'] = df['COGS_prev'].astype(float)
        out_df['COST_2025'] = df['COGS_curr'].astype(float)
        out_df['SellingPrice_2024'] = df['ASP_PREV'].astype(float).round(2)
        out_df['SellingPrice_2025'] = df['ASP_CURR'].astype(float).round(2)
        out_df['PurchasePrice_2025'] = df['ACP_CURR'].astype(float).round(2)
        out_df['ASP_2024'] = df['ASP_PREV'].astype(float)
        out_df['ASP_2025'] = df['ASP_CURR'].astype(float)
        out_df['ACP_2025'] = df['ACP_CURR'].astype(float)
        out_df['GrossMarginPct'] = (df.get('GROSS_MARGIN_PCT_curr', pd.Series([0.0]*len(df))).astype(float) * 100).round(2)
        out_df['NetMarginPct'] = (df.get('NET_MARGIN_PCT_curr', pd.Series([0.0]*len(df))).astype(float) * 100).round(2)
        out_df['Pct_Change_Price'] = df['PCT_CHANGE_PRICE'].astype(float)
        out_df['Pct_Change_Vol'] = df['PCT_CHANGE_VOL'].astype(float)
        out_df['Trend_Factor'] = df['TREND_FACTOR'].astype(float)
        out_df['Baseline_Vol_2026'] = df['BASELINE_VOL_NEXT'].astype(int)

        recs = out_df.to_dict('records')
        for rec in recs:
            for k, v in rec.items():
                if isinstance(v, (np.integer, np.int64, np.int32)):
                    rec[k] = int(v)
                elif isinstance(v, (np.floating, np.float64, np.float32)):
                    rec[k] = float(v)
        return recs

    # ── Model info for frontend ───────────────────────────────────────────────
    def _build_model_info(self, tr: pd.DataFrame) -> Dict[str, Any]:
        return {
            'kGlobal':    round(self.k_global, 4),
            'gElast':     round(self.g_elast, 4),
            'brandK':     {k: round(v, 4) for k, v in self.br_k.items()},
            'categoryK':  {k: round(v, 4) for k, v in self.cat_k.items()},
            'pgsK':       {k: round(v, 4) for k, v in self.pgs_k.items()},
            'mape':       round(self.mape, 4),
            'r2':         round(self.r2, 4),
            'nTrain':     self.n_train,
            'L':          1.1,
            'x0':         0.05,
            'warning':    ("Model calibrated from observed elasticity. "
                           "S-Curve reflects directional price sensitivity."),
        }
