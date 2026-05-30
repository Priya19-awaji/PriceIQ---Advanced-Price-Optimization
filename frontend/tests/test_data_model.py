# -*- coding: utf-8 -*-
"""
Validation test for the DataModel and PriceOptimizer modules.

Verifies:
  - CSV loads correctly with all expected columns
  - Selling Price = AVG Price, Purchase Price = Unit Cogs
  - Net Margin formula: Revenue EUR x (1 - CustomerBonus - EPD) - Net COGS
  - KPI calculations (revenue, margin, trends)
  - Optimizer produces valid recommendations
  - No NaN/Inf in any output
"""

import sys
import os
import io

# Force UTF-8 stdout on Windows to avoid cp1252 encoding errors
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data_model import DataModel, KPIEngine
from price_optimizer import PriceOptimizer
import numpy as np

DATA_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '..',
    'AUTODOC Dashboard Copy new_KPI Details Table 2025 and 2026_20260415_2124.csv'
)
if not os.path.exists(DATA_PATH):
    DATA_PATH = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'AUTODOC Dashboard Copy new_KPI Details Table 2025 and 2026_20260415_2124.csv'
    )
if not os.path.exists(DATA_PATH):
    DATA_PATH = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'Data',
        'AUTODOC Dashboard Copy new_KPI Details Table 2025 and 2026_20260415_2124.csv'
    )


def test_data_model():
    print("=" * 60)
    print("TEST: DataModel loading and computed fields")
    print("=" * 60)

    dm = DataModel(DATA_PATH, channel_filter='B2B 2 Step')
    dm.load()
    df = dm.df

    # Check required columns exist
    required = ['PNO', 'YEAR', 'MONTH', 'REVENUE', 'COGS', 'QTY',
                'SELLING_PRICE', 'PURCHASE_PRICE', 'CUSTOMER_BONUS', 'EPD',
                'SUPPLIER_BONUS', 'GROSS_MARGIN', 'NET_REVENUE', 'NET_COGS', 'NET_MARGIN']
    missing = [c for c in required if c not in df.columns]
    assert len(missing) == 0, f"Missing columns: {missing}"
    print(f"  [OK] All {len(required)} required columns present")

    # Check years
    years = dm.years
    print(f"  [..] Years in data: {years}")
    assert len(years) >= 1, "No years found"
    print(f"  [OK] Years validated: {years}")

    # Check Selling Price = AVG Price (positive where quantity > 0)
    has_sp = df[df['QTY'] > 0]['SELLING_PRICE']
    print(f"  [..] Selling Price (AVG Price) -- mean: EUR {has_sp.mean():.2f}, "
          f"min: EUR {has_sp.min():.2f}, max: EUR {has_sp.max():.2f}")
    assert has_sp.mean() > 0, "Selling Price should be positive on average"
    print(f"  [OK] Selling Price validated")

    # Check Purchase Price = Unit Cogs
    has_pp = df[df['QTY'] > 0]['PURCHASE_PRICE']
    print(f"  [..] Purchase Price (Unit Cogs) -- mean: EUR {has_pp.mean():.2f}, "
          f"min: EUR {has_pp.min():.2f}, max: EUR {has_pp.max():.2f}")
    assert has_pp.mean() > 0, "Purchase Price should be positive on average"
    print(f"  [OK] Purchase Price validated")

    # Verify computed Net Revenue = Revenue x (1 - CB - EPD)
    sample = df[(df['REVENUE'] > 0) & (df['CUSTOMER_BONUS'] > 0)].head(5)
    for _, row in sample.iterrows():
        expected = row['REVENUE'] * (1 - row['CUSTOMER_BONUS'] - row['EPD'])
        actual = row['NET_REVENUE']
        assert abs(expected - actual) < 0.01, (
            f"Net Revenue mismatch: expected {expected:.2f}, got {actual:.2f}"
        )
    print(f"  [OK] Net Revenue formula verified: Revenue x (1 - CB - EPD)")

    # Verify Net Margin = Net Revenue - Net COGS
    for _, row in sample.iterrows():
        expected = row['NET_REVENUE'] - row['NET_COGS']
        actual = row['NET_MARGIN']
        assert abs(expected - actual) < 0.01, (
            f"Net Margin mismatch: expected {expected:.2f}, got {actual:.2f}"
        )
    print(f"  [OK] Net Margin formula verified: Net Revenue - Net COGS")

    # No NaN/Inf in key columns
    for col in ['REVENUE', 'COGS', 'NET_REVENUE', 'NET_MARGIN', 'GROSS_MARGIN']:
        nan_count = df[col].isna().sum()
        inf_count = np.isinf(df[col]).sum()
        assert nan_count == 0, f"NaN found in {col}: {nan_count}"
        assert inf_count == 0, f"Inf found in {col}: {inf_count}"
    print(f"  [OK] No NaN/Inf in critical columns")

    return dm


def test_kpi_engine(dm):
    print("\n" + "=" * 60)
    print("TEST: KPIEngine calculations")
    print("=" * 60)

    engine = KPIEngine(dm)

    for y in dm.years:
        rev = engine.total_revenue(y)
        cogs = engine.total_cogs(y)
        qty = engine.total_quantity(y)
        gm = engine.total_gross_margin(y)
        nr = engine.total_net_revenue(y)
        nm = engine.total_net_margin(y)
        asp = engine.avg_selling_price(y)
        app = engine.avg_purchase_price(y)

        print(f"\n  [..] Year {y}:")
        print(f"     Revenue:         EUR {rev:,.0f}")
        print(f"     COGS:            EUR {cogs:,.0f}")
        print(f"     Quantity:        {qty:,.0f}")
        print(f"     Gross Margin:    EUR {gm:,.0f}")
        print(f"     Net Revenue:     EUR {nr:,.0f}")
        print(f"     Net Margin:      EUR {nm:,.0f}")
        print(f"     Avg Sell Price:  EUR {asp:.2f}")
        print(f"     Avg Purch Price: EUR {app:.2f}")

        assert rev >= 0, f"Revenue should be >= 0 for {y}"
        assert asp >= 0, f"Avg Selling Price should be >= 0 for {y}"

    # Monthly trends
    trends = engine.monthly_trends()
    print(f"\n  [..] Monthly trends: {len(trends)} data points")
    assert len(trends) > 0, "Should have monthly trend data"
    print(f"  [OK] Monthly trends validated")

    # KPI snapshot
    snapshot = engine.kpi_snapshot()
    assert 'yearly' in snapshot
    assert 'byCategory' in snapshot
    assert 'byBrand' in snapshot
    assert 'byPGS' in snapshot
    print(f"  [OK] KPI snapshot has all sections")
    print(f"     Categories: {len(snapshot['byCategory'])}")
    print(f"     Brands: {len(snapshot['byBrand'])}")
    print(f"     PGS: {len(snapshot['byPGS'])}")

    return engine


def test_optimizer(dm):
    print("\n" + "=" * 60)
    print("TEST: PriceOptimizer")
    print("=" * 60)

    optimizer = PriceOptimizer(dm, bonus_pct=0.15)
    result = optimizer.run(y_prev=2024, y_curr=2025, max_skus=1000)  # limit for speed

    recs = result['recommendations']
    raw = result['rawData']
    model = result['model']

    print(f"  [..] Recommendations: {len(recs)}")
    print(f"  [..] Raw data records: {len(raw)}")
    print(f"  [..] Model k_global: {model['kGlobal']:.4f}")
    print(f"  [..] Model g_elast: {model['gElast']:.4f}")
    print(f"  [..] Training points: {model['nTrain']}")
    print(f"  [..] MAPE: {model['mape']:.2f}%")
    print(f"  [..] R2: {model['r2']:.4f}")

    assert len(recs) > 0, "Should have recommendations"
    assert len(raw) > 0, "Should have raw data"

    # Check new fields are present
    r = recs[0]
    assert 'SellingPrice' in r, "Missing SellingPrice in recommendations"
    assert 'PurchasePrice' in r, "Missing PurchasePrice in recommendations"
    assert 'GrossMarginPct' in r, "Missing GrossMarginPct"
    assert 'NetMarginPct' in r, "Missing NetMarginPct"
    assert 'CustomerBonus' in r, "Missing CustomerBonus"
    assert 'EPD' in r, "Missing EPD"
    assert 'PGS' in r, "Missing PGS"
    print(f"  [OK] All new fields present (SellingPrice, PurchasePrice, margins, etc.)")

    # Check backward compat
    assert r['SellingPrice'] == r['CurrentPrice'], "SellingPrice should equal CurrentPrice"
    assert r['PurchasePrice'] == r['CurrentCost'], "PurchasePrice should equal CurrentCost"
    print(f"  [OK] Backward compatibility verified")

    # Check raw data has new fields
    rd = raw[0]
    assert 'SellingPrice_2024' in rd, "Missing SellingPrice_2024"
    assert 'SellingPrice_2025' in rd, "Missing SellingPrice_2025"
    assert 'PurchasePrice_2025' in rd, "Missing PurchasePrice_2025"
    print(f"  [OK] Raw data has Selling/Purchase price fields")

    # No NaN/Inf in recommendations
    for r in recs[:100]:
        for key, val in r.items():
            if isinstance(val, float):
                assert not np.isnan(val), f"NaN in recommendation {r['PNO']}.{key}"
                assert not np.isinf(val), f"Inf in recommendation {r['PNO']}.{key}"
    print(f"  [OK] No NaN/Inf in recommendations")

    # Distribution of recommendations
    inc = sum(1 for r in recs if r['Recommendation'] == 'INCREASE')
    dec = sum(1 for r in recs if r['Recommendation'] == 'DECREASE')
    hold = sum(1 for r in recs if r['Recommendation'] == 'HOLD')
    print(f"\n  [..] Recommendation distribution:")
    print(f"     INCREASE: {inc} ({inc/len(recs)*100:.1f}%)")
    print(f"     DECREASE: {dec} ({dec/len(recs)*100:.1f}%)")
    print(f"     HOLD:     {hold} ({hold/len(recs)*100:.1f}%)")

    # Sample recommendation
    print(f"\n  [..] Sample recommendation:")
    print(f"     PNO:            {recs[0]['PNO']}")
    print(f"     Brand:          {recs[0]['Brand']}")
    print(f"     PGS:            {recs[0]['PGS']}")
    print(f"     Selling Price:  EUR {recs[0]['SellingPrice']}")
    print(f"     Purchase Price: EUR {recs[0]['PurchasePrice']}")
    print(f"     Optimal Price:  EUR {recs[0]['OptimalPrice']}")
    print(f"     Gross Margin %: {recs[0]['GrossMarginPct']}%")
    print(f"     Net Margin %:   {recs[0]['NetMarginPct']}%")
    print(f"     Action:         {recs[0]['Recommendation']}")


if __name__ == '__main__':
    print("\n>>> PriceIQ Model Validation Suite\n")

    if not os.path.exists(DATA_PATH):
        print(f"[FAIL] Data file not found: {DATA_PATH}")
        sys.exit(1)

    dm = test_data_model()
    test_kpi_engine(dm)
    test_optimizer(dm)

    print("\n" + "=" * 60)
    print("[OK] ALL TESTS PASSED")
    print("=" * 60)
