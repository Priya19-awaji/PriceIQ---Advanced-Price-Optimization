# -*- coding: utf-8 -*-
"""Quick API endpoint verification."""
import sys, io, json, urllib.request

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

BASE = 'http://localhost:5001/api'

def fetch(path):
    return json.loads(urllib.request.urlopen(f'{BASE}/{path}').read())

print('=' * 60)
print('API Endpoint Verification')
print('=' * 60)

# 1. Health
h = fetch('health')
print(f"\n[1] /api/health => status={h['status']}, exists={h['exists']}")

# 2. KPIs
k = fetch('kpis')
print(f"\n[2] /api/kpis => years={k['years']}")
for y in k['years']:
    d = k['yearly'][str(y)]
    print(f"    Year {y}:")
    print(f"      Revenue:          EUR {d['revenue']:,.0f}")
    print(f"      COGS:             EUR {d['cogs']:,.0f}")
    print(f"      Gross Margin:     EUR {d['grossMargin']:,.0f} ({d['grossMarginPct']:.1f}%)")
    print(f"      Net Revenue:      EUR {d['netRevenue']:,.0f}")
    print(f"      Net Margin:       EUR {d['netMargin']:,.0f} ({d['netMarginPct']:.1f}%)")
    print(f"      Avg Selling Price:  EUR {d['avgSellingPrice']:.2f}")
    print(f"      Avg Purchase Price: EUR {d['avgPurchasePrice']:.2f}")
    print(f"      SKUs: {d['skuCount']} | Brands: {d['brandCount']} | Categories: {d['categoryCount']}")

if 'yoyGrowth' in k:
    g = k['yoyGrowth']
    print(f"    YoY Growth ({g['years'][0]}->{g['years'][1]}):")
    print(f"      Revenue: {g['revenue']:+.1f}% | Gross Margin: {g['grossMargin']:+.1f}% | Net Margin: {g['netMargin']:+.1f}%")

print(f"    Dimension breakdowns: {len(k['byCategory'])} cats, {len(k['byBrand'])} brands, {len(k['byPGS'])} PGS")

# 3. Monthly trends
m = fetch('monthly-trends')
print(f"\n[3] /api/monthly-trends => {len(m)} months")
for row in m[:4]:
    print(f"    {row['label']:8s}  Rev EUR {row['revenue']:>12,.0f}  NetMargin EUR {row['netMargin']:>10,.0f}")
print(f"    ...")

# 4. Pipeline
p = fetch('pipeline')
recs = p['recommendations']
raw = p['rawData']
model = p['model']
print(f"\n[4] /api/pipeline => {len(recs)} recommendations, {len(raw)} raw records")
print(f"    Model: k_global={model['kGlobal']:.2f}, MAPE={model['mape']:.1f}%, R2={model['r2']:.4f}")

r = recs[0]
print(f"    Sample SKU: {r['PNO']}")
print(f"      Brand:          {r['Brand']}")
print(f"      PGS:            {r['PGS']}")
print(f"      Selling Price:  EUR {r['SellingPrice']}")
print(f"      Purchase Price: EUR {r['PurchasePrice']}")
print(f"      Optimal Price:  EUR {r['OptimalPrice']}")
print(f"      Gross Margin %: {r['GrossMarginPct']}%")
print(f"      Net Margin %:   {r['NetMarginPct']}%")
print(f"      Customer Bonus: {r['CustomerBonus']}")
print(f"      EPD:            {r['EPD']}")
print(f"      Action:         {r['Recommendation']}")

# Backward compat check
assert r['SellingPrice'] == r['CurrentPrice'], 'SellingPrice != CurrentPrice'
assert r['PurchasePrice'] == r['CurrentCost'], 'PurchasePrice != CurrentCost'
print(f"    [OK] Backward compatibility (CurrentPrice/CurrentCost) verified")

print(f"\n{'=' * 60}")
print(f"[OK] ALL API ENDPOINTS VERIFIED")
print(f"{'=' * 60}")
