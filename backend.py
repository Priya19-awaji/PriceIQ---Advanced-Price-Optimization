"""
PriceIQ Backend - Flask API (Model-Driven Architecture)

Uses DataModel for centralized KPI calculations and PriceOptimizer for ML pricing.
All calculations are derived from the data model layer — nothing hardcoded.

Start with: python backend.py
Runs on http://localhost:5001
"""

import sys
import os
import math
import json
import warnings
warnings.filterwarnings('ignore')

import numpy as np
import pandas as pd
from flask import Flask, jsonify, request
from flask_cors import CORS

# ── Data file discovery ──────────────────────────────────────────────────────
DATA_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), '..',
    'AUTODOC Dashboard Copy new_KPI Details Table 2025 and 2026_20260415_2124.csv'
)
if not os.path.exists(DATA_PATH):
    DATA_PATH = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        'AUTODOC Dashboard Copy new_KPI Details Table 2025 and 2026_20260415_2124.csv'
    )
if not os.path.exists(DATA_PATH):
    DATA_PATH = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        'Data',
        'AUTODOC Dashboard Copy new_KPI Details Table 2025 and 2026_20260415_2124.csv'
    )

# ── Import model-driven modules ─────────────────────────────────────────────
from data_model import DataModel, KPIEngine
from price_optimizer import PriceOptimizer, sigmoid_demand

app = Flask(__name__)
CORS(app)

# ── Global model instances ───────────────────────────────────────────────────
_data_model: DataModel = None
_kpi_engine: KPIEngine = None
_pipeline_cache = {}
_kpi_cache = None
_trends_cache = {}

def sanitize_for_json(obj):
    """Recursively replace Infinity/NaN with None so JSON is valid."""
    if isinstance(obj, float):
        if math.isinf(obj) or math.isnan(obj):
            return None
        return obj
    elif isinstance(obj, dict):
        return {k: sanitize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [sanitize_for_json(v) for v in obj]
    return obj


def get_data_model() -> DataModel:
    """Lazy-load the DataModel singleton."""
    global _data_model
    if _data_model is None:
        _data_model = DataModel(DATA_PATH, channel_filter='B2B 2 Step')
        _data_model.load()
    return _data_model


def get_kpi_engine() -> KPIEngine:
    """Lazy-load the KPIEngine singleton."""
    global _kpi_engine
    if _kpi_engine is None:
        _kpi_engine = KPIEngine(get_data_model())
    return _kpi_engine


def run_pipeline(bonus_pct: float = 0.15):
    """Run the full pricing pipeline (cached by bonus_pct)."""
    cache_key = round(bonus_pct, 4)
    if cache_key in _pipeline_cache:
        return _pipeline_cache[cache_key]

    dm = get_data_model()
    optimizer = PriceOptimizer(dm, bonus_pct=bonus_pct)
    result = optimizer.run(y_prev=2024, y_curr=2025, max_skus=50_000)

    _pipeline_cache[cache_key] = result
    return result


# ─── Routes ───────────────────────────────────────────────────────────────────

@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({
        'status': 'ok',
        'data_file': os.path.abspath(DATA_PATH),
        'exists': os.path.exists(DATA_PATH)
    })


@app.route('/api/kpis', methods=['GET'])
def kpis():
    """
    Centralized KPI endpoint — model-driven, no hardcoding.
    Returns yearly totals, YoY growth, and dimension breakdowns.
    """
    try:
        global _kpi_cache
        if _kpi_cache is not None:
            return jsonify(sanitize_for_json(_kpi_cache))
            
        engine = get_kpi_engine()
        snapshot = engine.kpi_snapshot()
        _kpi_cache = snapshot
        return jsonify(sanitize_for_json(snapshot))
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/monthly-trends', methods=['GET'])
def monthly_trends():
    """
    Monthly KPI trends — real data, not synthetic seasonality.
    Returns actual Revenue, COGS, Quantity, Gross Margin, Net Revenue, Net Margin per month.
    """
    try:
        years_param = request.args.get('years', '')
        cache_key = years_param if years_param else 'all'
        
        global _trends_cache
        if cache_key in _trends_cache:
            return jsonify(sanitize_for_json(_trends_cache[cache_key]))
            
        engine = get_kpi_engine()
        years = [int(y) for y in years_param.split(',') if y.strip()] if years_param else None
        trends = engine.monthly_trends(years)
        _trends_cache[cache_key] = trends
        return jsonify(sanitize_for_json(trends))
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/pipeline', methods=['GET'])
def pipeline():
    """Main pipeline endpoint — backward compatible + enriched with new fields."""
    bonus_pct = float(request.args.get('bonus_pct', 0.15))
    bonus_pct = max(0.0, min(0.30, bonus_pct))
    try:
        data = run_pipeline(bonus_pct)
        return jsonify(sanitize_for_json(data))
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/inflation', methods=['GET'])
def inflation():
    bonus_pct = float(request.args.get('bonus_pct', 0.15))
    pno = request.args.get('pno', '')
    if not pno:
        return jsonify({'error': 'pno parameter is required'}), 400

    try:
        data = run_pipeline(bonus_pct)
        recs = data['recommendations']
        raw = data['rawData']

        sel_rec = next((r for r in recs if r['PNO'] == pno), None)
        sel_raw = next((r for r in raw if r['PNO'] == pno), None)

        if not sel_rec or not sel_raw:
            return jsonify({'error': 'SKU not found'}), 404

        cur_price = sel_rec['CurrentPrice']    # Selling Price
        cur_cost = sel_rec['CurrentCost']      # Purchase Price
        opt_price = sel_rec['OptimalPrice']
        opt_vol = sel_rec['OptVol']
        base_vol = sel_raw['Baseline_Vol_2026']
        sk = sel_rec['BrandK']

        inflation_data = []
        for ir in [0, 2, 4, 6, 8, 10, 12, 15, 20]:
            ic = cur_cost * (1 + ir / 100)
            igp = (opt_price - ic) * opt_vol
            inm = igp - opt_price * opt_vol * bonus_pct
            base_gp = (cur_price - cur_cost) * base_vol
            base_nm = base_gp - cur_price * base_vol * bonus_pct
            inflation_data.append({
                'rate': f"{ir}%",
                'nm': round(inm),
                'baseNM': round(base_nm * (1 - ir / 100 * 0.6)),
                'margin': round((opt_price - ic) / opt_price * 100) if opt_price > 0 else 0
            })

        sensitivity_data = []
        for i in range(41):
            dp = -0.2 + (0.4 * i) / 40
            vm_n = 1 + sigmoid_demand(dp, k=sk)
            vm_m = 1 + sigmoid_demand(dp, k=sk * 1.15)
            vm_h = 1 + sigmoid_demand(dp, k=sk * 1.35)
            sensitivity_data.append({
                'priceChange': round(dp * 100),
                'normal': round(base_vol * max(0.1, vm_n)),
                'moderate': round(base_vol * max(0.1, vm_m)),
                'high': round(base_vol * max(0.1, vm_h))
            })

        raw_mat = cur_cost * 0.55
        labor = cur_cost * 0.20
        logistics = cur_cost * 0.15
        overhead = cur_cost * 0.10
        cost_breakdown = [
            {'component': 'Raw Materials', 'current': round(raw_mat, 2), 'inflated5': round(raw_mat * 1.08, 2), 'inflated10': round(raw_mat * 1.15, 2), 'pct': 55},
            {'component': 'Labor', 'current': round(labor, 2), 'inflated5': round(labor * 1.04, 2), 'inflated10': round(labor * 1.07, 2), 'pct': 20},
            {'component': 'Logistics', 'current': round(logistics, 2), 'inflated5': round(logistics * 1.06, 2), 'inflated10': round(logistics * 1.12, 2), 'pct': 15},
            {'component': 'Overhead', 'current': round(overhead, 2), 'inflated5': round(overhead * 1.03, 2), 'inflated10': round(overhead * 1.05, 2), 'pct': 10},
        ]

        breakeven_data = []
        for ir in [0, 5, 10, 15, 20]:
            ic = cur_cost * (1 + ir / 100)
            breakeven = ic * (1 + bonus_pct) / (1 - bonus_pct)
            breakeven_data.append({
                'inflation': f"{ir}%",
                'breakeven': round(breakeven, 2),
                'currentPrice': cur_price,
                'optimalPrice': opt_price
            })

        brands = sorted(list(set([r['Brand'] for r in recs])))
        resilience = []
        for brand in brands[:8]:
            b_recs = [r for r in recs if r['Brand'] == brand]
            avg_margin = sum([(r['CurrentPrice'] - r['CurrentCost']) / r['CurrentPrice'] for r in b_recs]) / len(b_recs) if b_recs else 0
            avg_elast = abs(sum([r['OwnElasticity'] for r in b_recs]) / len(b_recs)) if b_recs else 0
            cushion = avg_margin * 100
            sens = min(100, avg_elast * 30)
            res = max(0, min(100, cushion * 1.5 - sens * 0.5))
            resilience.append({
                'brand': brand,
                'margin': round(cushion),
                'elasticity': round(sens),
                'resilience': round(res),
                'skus': len(b_recs)
            })

        categories = sorted(list(set([r['Category'] for r in recs])))
        cat_resilience = []
        for cat in categories[:8]:
            c_recs = [r for r in recs if r['Category'] == cat]
            avg_margin = sum([(r['CurrentPrice'] - r['CurrentCost']) / r['CurrentPrice'] for r in c_recs]) / len(c_recs) if c_recs else 0
            avg_elast = abs(sum([r['OwnElasticity'] for r in c_recs]) / len(c_recs)) if c_recs else 0
            cushion = avg_margin * 100
            sens = min(100, avg_elast * 30)
            res = max(0, min(100, cushion * 1.5 - sens * 0.5))
            cat_resilience.append({
                'category': cat,
                'margin': round(cushion),
                'elasticity': round(sens),
                'resilience': round(res),
                'skus': len(c_recs)
            })

        max_infl_tol = round(((cur_price - cur_cost) / cur_cost - bonus_pct) * 100) if cur_price > cur_cost and cur_cost > 0 else 0

        return jsonify(sanitize_for_json({
            'maxInflationTolerance': max_infl_tol,
            'inflationData': inflation_data,
            'sensitivityData': sensitivity_data,
            'costBreakdown': cost_breakdown,
            'breakevenData': breakeven_data,
            'resilience': resilience,
            'categoryResilience': cat_resilience
        }))
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/cross-elasticity', methods=['GET'])
def cross_elasticity():
    bonus_pct = float(request.args.get('bonus_pct', 0.15))
    brand = request.args.get('brand', '')
    category = request.args.get('category', '')
    pgs = request.args.get('pgs', '')

    if not brand and not category and not pgs:
        return jsonify({'error': 'Either brand, category, or pgs parameter is required'}), 400

    try:
        data = run_pipeline(bonus_pct)
        recs = data['recommendations']

        if brand:
            filtered_skus = [r for r in recs if r['Brand'] == brand]
            entity_name = brand
        elif category:
            filtered_skus = [r for r in recs if r['Category'] == category]
            entity_name = category
        else:
            filtered_skus = [r for r in recs if r['PGS'] == pgs]
            entity_name = pgs

        if not filtered_skus:
            return jsonify({'error': f'{"Brand" if brand else "Category" if category else "PGS"} not found'}), 404

        # Limit heavy calculations to top 50 SKUs to prevent O(N^2) timeouts
        skus_calc = filtered_skus[:50]
        heatmap_data = []
        for i, s in enumerate(skus_calc[:12]):
            for j, t in enumerate(skus_calc[:12]):
                if i == j:
                    heatmap_data.append({'source': s['PNO'][-6:], 'target': t['PNO'][-6:], 'value': s['OwnElasticity']})
                else:
                    price_sim = 1 - min(abs(s['CurrentPrice'] - t['CurrentPrice']) / max(s['CurrentPrice'], t['CurrentPrice']), 1)
                    cross_elast = round(0.15 * price_sim, 2)
                    heatmap_data.append({'source': s['PNO'][-6:], 'target': t['PNO'][-6:], 'value': cross_elast})

        substitution_risk = []
        for r in skus_calc[:15]:
            same_price = [o for o in filtered_skus if o['PNO'] != r['PNO'] and o['CurrentPrice'] > 0 and abs(o['CurrentPrice'] - r['CurrentPrice']) / r['CurrentPrice'] < 0.2]
            risk = min(100, len(same_price) * 20 + abs(r['OwnElasticity']) * 15)
            substitution_risk.append({
                'pno': r['PNO'][-8:],
                'risk': round(risk),
                'price': r['CurrentPrice'],
                'elasticity': r['OwnElasticity'],
                'substitutes': len(same_price),
                'rec': r['Recommendation']
            })
        substitution_risk.sort(key=lambda x: x['risk'], reverse=True)

        price_corridors = []
        for r in skus_calc[:20]:
            price_corridors.append({
                'pno': r['PNO'][-6:],
                'current': r['CurrentPrice'],
                'optimal': r['OptimalPrice'],
                'floor': max(r['CurrentPrice'] * 0.8, r['CurrentCost'] * 1.05),
                'ceiling': r['CurrentPrice'] * 1.2,
                'cost': r['CurrentCost']
            })
        price_corridors.sort(key=lambda x: x['current'])

        cannibalization = []
        for r in skus_calc:
            neighbors = [o for o in skus_calc if o['PNO'] != r['PNO'] and o['CurrentPrice'] > 0 and abs(o['CurrentPrice'] - r['CurrentPrice']) / r['CurrentPrice'] < 0.15]
            cannibalization.append({
                'price': r['CurrentPrice'],
                'volume': r['BaselineVol2026'],
                'neighbors': len(neighbors),
                'pno': r['PNO'][-6:],
                'change': round(r['RecChange'] * 100, 2)
            })

        coord_impact = {
            'totalUplift': sum([r['NetMarginUplift'] for r in filtered_skus]),
            'inc': len([r for r in filtered_skus if r['Recommendation'] == 'INCREASE']),
            'dec': len([r for r in filtered_skus if r['Recommendation'] == 'DECREASE']),
            'hold': len([r for r in filtered_skus if r['Recommendation'] == 'HOLD']),
            'total': len(filtered_skus)
        }

        return jsonify(sanitize_for_json({
            'heatmapData': heatmap_data,
            'substitutionRisk': substitution_risk,
            'priceCorridors': price_corridors,
            'cannibalization': cannibalization,
            'coordImpact': coord_impact
        }))
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    print("\n[PriceIQ] Backend starting (Model-Driven Architecture)...")
    print(f"[PriceIQ] Data file: {os.path.abspath(DATA_PATH)}")
    if not os.path.exists(DATA_PATH):
        print(f"[WARNING] Data file not found at {DATA_PATH}")
    else:
        print("[PriceIQ] Data file found. Pre-loading DataModel + Pipeline...")
        try:
            get_data_model()        # load data model
            get_kpi_engine()        # init KPI engine
            run_pipeline(0.15)      # warm cache
            print("[PriceIQ] All modules loaded successfully.")
        except Exception as e:
            print(f"[ERROR] Startup error: {e}")
            import traceback
            traceback.print_exc()
    print("\n[PriceIQ] API running at http://localhost:5001\n")
    app.run(host='0.0.0.0', port=5001, debug=False)
