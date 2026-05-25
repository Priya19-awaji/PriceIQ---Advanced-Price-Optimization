"""Quick edge case and calculation verification tests."""
import requests, json, sys, math
import numpy as np

API = "http://localhost:5001/api"

def sigmoid_demand(dp, k=10.0, x0=0.05, L=1.1):
    exponent = np.clip(k * (dp + x0), -300, 300)
    return L / (1 + np.exp(exponent)) - (L / 2)

print("=== EDGE CASE: bonus_pct=0 (120s timeout) ===")
try:
    r = requests.get(f"{API}/pipeline?bonus_pct=0", timeout=120)
    print(f"Status: {r.status_code}")
    data = r.json()
    recs = data.get("recommendations", [])
    print(f"Recs: {len(recs)}")
    if recs:
        print(f"Sample NM: BaseNM={recs[0]['BaseNM']}, OptNM={recs[0]['OptNM']}")
except Exception as e:
    print(f"Error: {e}")

print("\n=== EDGE CASE: bonus_pct=0.30 (120s timeout) ===")
try:
    r = requests.get(f"{API}/pipeline?bonus_pct=0.30", timeout=120)
    print(f"Status: {r.status_code}")
    data = r.json()
    recs = data.get("recommendations", [])
    print(f"Recs: {len(recs)}")
except Exception as e:
    print(f"Error: {e}")

print("\n=== MAIN PIPELINE DATA CHECKS ===")
r = requests.get(f"{API}/pipeline?bonus_pct=0.15", timeout=120)
data = r.json()
recs = data["recommendations"]
raw = data["rawData"]
model = data["model"]

print(f"Total Recs: {len(recs)}")
print(f"Model: kGlobal={model['kGlobal']}, gElast={model['gElast']}, MAPE={model['mape']}, R2={model['r2']}")

# Brand K range analysis
brand_k = model.get("brandK", {})
k_vals = list(brand_k.values())
outliers_low = [b for b, k in brand_k.items() if k < 3]
outliers_high = [b for b, k in brand_k.items() if k > 15]
print(f"\nBrand K: min={min(k_vals):.2f}, max={max(k_vals):.2f}, median={np.median(k_vals):.2f}")
print(f"Outliers < 3: {len(outliers_low)} brands")
print(f"Outliers > 15: {len(outliers_high)} brands")
if outliers_high:
    # Show top 5 extreme outliers
    extreme = sorted([(b, k) for b, k in brand_k.items() if k > 15], key=lambda x: x[1], reverse=True)[:5]
    print(f"Top extreme K brands: {extreme}")

# Price bounds check (detailed)
violations = []
for r_item in recs:
    cp = r_item["CurrentPrice"]
    op = r_item["OptimalPrice"]
    cc = r_item["CurrentCost"]
    floor = max(cp * 0.80, cc * 1.05)
    ceiling = cp * 1.20
    if not (cp * 0.79 <= op <= cp * 1.21):
        violations.append({
            "PNO": r_item["PNO"],
            "CP": cp,
            "OP": op,
            "CC": cc,
            "Floor": round(floor, 2),
            "Ceiling": round(ceiling, 2),
            "Change": round(r_item["RecChange"] * 100, 2)
        })

print(f"\nPrice Bound Violations: {len(violations)}/{len(recs)}")
if violations:
    print("Sample violations:")
    for v in violations[:5]:
        print(f"  PNO={v['PNO']}: CP={v['CP']}, OP={v['OP']}, CC={v['CC']}, Change={v['Change']}%")
    # Check if violations are from floor constraint (cost > price*0.80)
    floor_forced = [v for v in violations if v['OP'] >= v['CC'] * 1.05 and v['OP'] < v['CP'] * 0.80]
    print(f"  Floor-forced violations (OP < 0.8*CP but OP >= 1.05*CC): {len(floor_forced)}")

# Spot-check 5 SKUs
print("\n=== SPOT CHECK: 5 SKUs ===")
for i, rec in enumerate(recs[:5]):
    bp = rec["CurrentPrice"]
    bc = rec["CurrentCost"]
    dp = rec["RecChange"]
    bv = rec["BaselineVol2026"]
    sk = rec["BrandK"]
    
    calc_op = bp * (1 + dp)
    calc_vm = 1.0 + sigmoid_demand(dp, k=sk)
    calc_oq = int(bv * max(0.1, calc_vm))
    calc_orev = calc_op * calc_oq
    calc_ogp = (calc_op - bc) * calc_oq
    
    op_match = abs(calc_op - rec["OptimalPrice"]) < 0.02
    oq_match = abs(calc_oq - rec["OptVol"]) <= 5
    orev_match = abs(calc_orev - rec["OptRev"]) / max(1, abs(rec["OptRev"])) < 0.01
    ogp_match = abs(calc_ogp - rec["OptimizedProfit2026"]) / max(1, abs(rec["OptimizedProfit2026"])) < 0.01
    
    status = "OK" if (op_match and oq_match and orev_match and ogp_match) else "MISMATCH"
    print(f"  SKU {i+1} [{rec['PNO']}] [{status}]:")
    print(f"    OptPrice: calc={calc_op:.2f} vs {rec['OptimalPrice']:.2f} {'OK' if op_match else 'FAIL'}")
    print(f"    OptVol:   calc={calc_oq} vs {rec['OptVol']} {'OK' if oq_match else 'FAIL'}")
    print(f"    OptRev:   calc={calc_orev:.0f} vs {rec['OptRev']:.0f} {'OK' if orev_match else 'FAIL'}")
    print(f"    OptGP:    calc={calc_ogp:.0f} vs {rec['OptimizedProfit2026']:.0f} {'OK' if ogp_match else 'FAIL'}")

# Revenue and profit aggregation check
print("\n=== AGGREGATE CHECKS ===")
total_current_rev = sum(r_item["CurrentRev2025"] for r_item in recs)
total_opt_rev = sum(r_item["OptRev"] for r_item in recs)
total_base_nm = sum(r_item["BaseNM"] for r_item in recs)
total_opt_nm = sum(r_item["OptNM"] for r_item in recs)
total_nm_uplift = sum(r_item["NetMarginUplift"] for r_item in recs)
total_profit_uplift = sum(r_item["ProfitUplift"] for r_item in recs)

print(f"Current Revenue (2025): EUR {total_current_rev:,.0f}")
print(f"Optimized Revenue (2026): EUR {total_opt_rev:,.0f}")
print(f"Revenue Change: EUR {total_opt_rev - total_current_rev:,.0f} ({(total_opt_rev/total_current_rev - 1)*100:.1f}%)")
print(f"Baseline Net Margin: EUR {total_base_nm:,.0f}")
print(f"Optimized Net Margin: EUR {total_opt_nm:,.0f}")
print(f"NM Uplift: EUR {total_nm_uplift:,.0f}")
print(f"Gross Profit Uplift: EUR {total_profit_uplift:,.0f}")

# Recommendation distribution
inc = sum(1 for r_item in recs if r_item["Recommendation"] == "INCREASE")
dec = sum(1 for r_item in recs if r_item["Recommendation"] == "DECREASE")
hold = sum(1 for r_item in recs if r_item["Recommendation"] == "HOLD")
print(f"\nRecommendation Distribution:")
print(f"  INCREASE: {inc} ({inc/len(recs)*100:.1f}%)")
print(f"  DECREASE: {dec} ({dec/len(recs)*100:.1f}%)")
print(f"  HOLD: {hold} ({hold/len(recs)*100:.1f}%)")

# Check for any NaN/None in critical fields
null_count = 0
for r_item in recs:
    for field in ['CurrentPrice', 'OptimalPrice', 'CurrentCost', 'OptRev', 'OptVol', 'BaseNM', 'OptNM']:
        if r_item.get(field) is None:
            null_count += 1
print(f"\nNull values in critical fields: {null_count}")

print("\n=== ALL CHECKS COMPLETE ===")
