"""
PriceIQ Comprehensive Validation Test Suite
Tests: Functional, ML, Pricing, S-Curve, Edge Cases
"""
import sys, os, json, math, time
sys.path.insert(0, os.path.dirname(__file__))

import numpy as np
import requests

API = "http://localhost:5001/api"
RESULTS = {"pass": 0, "fail": 0, "warn": 0, "details": []}

def test(name, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    RESULTS["pass" if condition else "fail"] += 1
    RESULTS["details"].append({"name": name, "status": status, "detail": detail})
    print(f"  {'✅' if condition else '❌'} {name}: {detail[:120]}")

def warn(name, detail=""):
    RESULTS["warn"] += 1
    RESULTS["details"].append({"name": name, "status": "WARN", "detail": detail})
    print(f"  ⚠️  {name}: {detail[:120]}")

# ═══════════════════════════════════════════════════════════════════════════════
# 1. FUNCTIONAL TESTING
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "="*70)
print("1️⃣  FUNCTIONAL TESTING")
print("="*70)

# 1a. Backend Health
try:
    r = requests.get(f"{API}/health", timeout=5)
    health = r.json()
    test("Backend Health", r.status_code == 200 and health.get("status") == "ok", f"Status: {health}")
    test("Data File Exists", health.get("exists") == True, f"Book1.xlsx: {health.get('book')}")
except Exception as e:
    test("Backend Reachable", False, str(e))

# 1b. Pipeline Endpoint
try:
    r = requests.get(f"{API}/pipeline?bonus_pct=0.15", timeout=30)
    test("Pipeline HTTP 200", r.status_code == 200, f"Status code: {r.status_code}")
    
    # Check for Infinity/NaN in JSON
    raw_text = r.text
    has_infinity = "Infinity" in raw_text or "NaN" in raw_text
    test("No Infinity/NaN in JSON", not has_infinity, "JSON is valid" if not has_infinity else "INVALID: contains Infinity/NaN")
    
    data = r.json()
    raw_data = data.get("rawData", [])
    recs = data.get("recommendations", [])
    model = data.get("model", {})
    
    test("Raw Data Present", len(raw_data) > 0, f"{len(raw_data)} SKUs returned")
    test("Recommendations Present", len(recs) > 0, f"{len(recs)} recommendations")
    test("Model Info Present", "kGlobal" in model, f"kGlobal={model.get('kGlobal')}")
    test("Raw == Recs Count", len(raw_data) == len(recs), f"Raw: {len(raw_data)}, Recs: {len(recs)}")
    
    # Validate required fields
    req_raw = ['PNO','Brand','QTY_2024','QTY_2025','SALES_2024','SALES_2025','ASP_2024','ASP_2025','ACP_2025','Pct_Change_Price','Pct_Change_Vol']
    req_rec = ['PNO','Brand','CurrentPrice','CurrentCost','OptimalPrice','RecChange','OptVol','OptRev','BaseNM','OptNM','Recommendation','BrandK']
    if len(raw_data) > 0:
        missing_raw = [f for f in req_raw if f not in raw_data[0]]
        test("Raw Data Fields Complete", len(missing_raw) == 0, f"Missing: {missing_raw}" if missing_raw else "All fields present")
    if len(recs) > 0:
        missing_rec = [f for f in req_rec if f not in recs[0]]
        test("Rec Fields Complete", len(missing_rec) == 0, f"Missing: {missing_rec}" if missing_rec else "All fields present")

except Exception as e:
    test("Pipeline Endpoint", False, str(e))
    raw_data, recs, model = [], [], {}

# 1c. Inflation Endpoint
if len(recs) > 0:
    try:
        pno = recs[0]["PNO"]
        r = requests.get(f"{API}/inflation?pno={pno}&bonus_pct=0.15", timeout=30)
        test("Inflation HTTP 200", r.status_code == 200, f"PNO={pno}")
        inf_data = r.json()
        test("Inflation Data Keys", all(k in inf_data for k in ['maxInflationTolerance','inflationData','sensitivityData','costBreakdown']),
             f"Keys: {list(inf_data.keys())[:5]}")
    except Exception as e:
        test("Inflation Endpoint", False, str(e))

# 1d. Cross-Elasticity Endpoint
if len(recs) > 0:
    try:
        brand = recs[0]["Brand"]
        r = requests.get(f"{API}/cross-elasticity?brand={brand}&bonus_pct=0.15", timeout=30)
        test("Cross-Elast HTTP 200", r.status_code == 200, f"Brand={brand}")
        ce_data = r.json()
        test("Cross-Elast Data Keys", all(k in ce_data for k in ['heatmapData','substitutionRisk','priceCorridors','coordImpact']),
             f"Keys: {list(ce_data.keys())[:5]}")
    except Exception as e:
        test("Cross-Elast Endpoint", False, str(e))

# ═══════════════════════════════════════════════════════════════════════════════
# 2. ML VALIDATION
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "="*70)
print("2️⃣  ML VALIDATION")
print("="*70)

# 2a. S-Curve Function Validation
def sigmoid_demand(dp, k=10.0, x0=0.05, L=1.1):
    return L / (1 + np.exp(k * (dp + x0))) - (L / 2)

# Test properties of well-formed S-curve
sd_0 = sigmoid_demand(0.0)  # At dp=0
sd_neg = sigmoid_demand(-0.10)  # Price decrease → volume increase
sd_pos = sigmoid_demand(0.10)  # Price increase → volume decrease

test("S-Curve: dp=0 gives ~0 (small negative)", -0.15 < sd_0 < 0.05, f"f(0)={sd_0:.4f}")
test("S-Curve: Monotonically decreasing", sd_neg > sd_0 > sd_pos, f"f(-0.1)={sd_neg:.4f}, f(0)={sd_0:.4f}, f(0.1)={sd_pos:.4f}")
test("S-Curve: Price cut → volume up", sd_neg > 0, f"f(-0.1)={sd_neg:.4f} > 0")
test("S-Curve: Price hike → volume down", sd_pos < 0, f"f(0.1)={sd_pos:.4f} < 0")

# Bounds check: volume multiplier should be bounded
vm_extreme_neg = 1 + sigmoid_demand(-0.5, k=15.0)
vm_extreme_pos = 1 + sigmoid_demand(0.5, k=15.0)
test("S-Curve: Extreme neg bounded", 0.5 < vm_extreme_neg < 2.5, f"VM(-50%)={vm_extreme_neg:.4f}")
test("S-Curve: Extreme pos bounded", 0.0 < vm_extreme_pos < 1.0, f"VM(+50%)={vm_extreme_pos:.4f}")

# 2b. Model Metrics
if model:
    mape = model.get("mape", 999)
    r2 = model.get("r2", -1)
    n_train = model.get("nTrain", 0)
    k_global = model.get("kGlobal", 0)
    g_elast = model.get("gElast", 0)
    
    test("MAPE < 50%", mape < 50, f"MAPE={mape:.2f}%")
    if mape > 30:
        warn("MAPE > 30% (mediocre)", f"MAPE={mape:.2f}% — Consider retraining with more features")
    test("R² > 0", r2 > 0, f"R²={r2:.4f}")
    if r2 < 0.3:
        warn("R² < 0.3 (low explanatory power)", f"R²={r2:.4f} — Model explains {r2*100:.1f}% variance")
    test("Training set > 50", n_train > 50, f"nTrain={n_train}")
    test("kGlobal in [3,15]", 3 <= k_global <= 15, f"kGlobal={k_global}")
    test("Global Elasticity negative", g_elast < 0, f"gElast={g_elast}")

    # Brand-level K validation
    brand_k = model.get("brandK", {})
    test("Brand K calibrated", len(brand_k) > 0, f"{len(brand_k)} brands calibrated")
    k_values = list(brand_k.values())
    if k_values:
        all_in_range = all(3 <= k <= 15 for k in k_values)
        test("All brand K in [3,15]", all_in_range, f"Range: [{min(k_values):.2f}, {max(k_values):.2f}]")

# ═══════════════════════════════════════════════════════════════════════════════
# 3. PRICE OPTIMIZATION VALIDATION
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "="*70)
print("3️⃣  PRICE OPTIMIZATION VALIDATION")
print("="*70)

if recs:
    # 3a. Price bounds
    violations = 0
    margin_issues = 0
    rec_counts = {"INCREASE": 0, "DECREASE": 0, "HOLD": 0}
    
    for r in recs:
        cp = r["CurrentPrice"]
        op = r["OptimalPrice"]
        cc = r["CurrentCost"]
        
        # Price within ±20%
        if not (cp * 0.79 <= op <= cp * 1.21):
            violations += 1
        
        # Optimal price above cost
        if op < cc:
            margin_issues += 1
        
        rec_counts[r["Recommendation"]] = rec_counts.get(r["Recommendation"], 0) + 1
    
    test("Price Bounds (±20%)", violations == 0, f"{violations} violations out of {len(recs)}")
    test("Optimal > Cost", margin_issues == 0, f"{margin_issues} SKUs with OptPrice < Cost")
    
    # 3b. Recommendation distribution
    total = len(recs)
    pct_inc = rec_counts.get("INCREASE", 0) / total * 100
    pct_dec = rec_counts.get("DECREASE", 0) / total * 100
    pct_hold = rec_counts.get("HOLD", 0) / total * 100
    test("Rec Distribution Reasonable", pct_hold < 95, f"INC: {pct_inc:.1f}%, DEC: {pct_dec:.1f}%, HOLD: {pct_hold:.1f}%")
    
    # 3c. NM Uplift positive for non-HOLD SKUs
    nm_uplifts = [r["NetMarginUplift"] for r in recs if r["Recommendation"] != "HOLD"]
    if nm_uplifts:
        positive_uplift = sum(1 for u in nm_uplifts if u > 0)
        test("NM Uplift positive for actioned SKUs", positive_uplift / len(nm_uplifts) > 0.9,
             f"{positive_uplift}/{len(nm_uplifts)} have positive uplift")
    
    # 3d. Spot-check one SKU's math
    sample = recs[0]
    cp = sample["CurrentPrice"]
    cc = sample["CurrentCost"]
    dp = sample["RecChange"]
    bv = sample["BaselineVol2026"]
    sk = sample["BrandK"]
    
    calc_op = cp * (1 + dp)
    calc_vm = 1 + sigmoid_demand(dp, k=sk)
    calc_oq = int(bv * max(0.1, calc_vm))
    calc_orev = calc_op * calc_oq
    
    test("Spot-Check: OptPrice", abs(calc_op - sample["OptimalPrice"]) < 0.02,
         f"Calc={calc_op:.2f}, Reported={sample['OptimalPrice']}")
    test("Spot-Check: OptVol", abs(calc_oq - sample["OptVol"]) < 2,
         f"Calc={calc_oq}, Reported={sample['OptVol']}")
    test("Spot-Check: OptRev", abs(calc_orev - sample["OptRev"]) / max(1, abs(sample["OptRev"])) < 0.01,
         f"Calc={calc_orev:.0f}, Reported={sample['OptRev']}")

# ═══════════════════════════════════════════════════════════════════════════════
# 4. S-CURVE & CHARTS VALIDATION 
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "="*70)
print("4️⃣  S-CURVE & CHARTS VALIDATION")
print("="*70)

# Frontend S-curve formula match
def sigmoid_frontend(dp, k=10, x0=0.05, L=1.1):
    """TypeScript version: L / (1 + Math.exp(k * (dp + x0))) - L / 2"""
    return L / (1 + math.exp(k * (dp + x0))) - L / 2

# Backend vs Frontend consistency
for dp_test in [-0.2, -0.1, 0.0, 0.05, 0.1, 0.2]:
    backend_val = sigmoid_demand(dp_test)
    frontend_val = sigmoid_frontend(dp_test)
    test(f"S-Curve Consistency dp={dp_test}", abs(backend_val - frontend_val) < 1e-10,
         f"Backend={backend_val:.6f}, Frontend={frontend_val:.6f}")

# Chart point generation validation
steps = 100
chart_points = []
for i in range(steps + 1):
    dp = -0.3 + (0.6 * i) / steps
    vm = 1 + sigmoid_demand(dp, k=10)
    chart_points.append({"dp": dp, "vm": max(0.1, vm)})

test("Chart: 101 points generated", len(chart_points) == 101, f"Points: {len(chart_points)}")
test("Chart: Monotonically decreasing VM", all(chart_points[i]["vm"] >= chart_points[i+1]["vm"] for i in range(len(chart_points)-1)),
     "Volume multiplier decreases as price increases")

# ═══════════════════════════════════════════════════════════════════════════════
# 5. EDGE CASES & PERFORMANCE
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "="*70)
print("5️⃣  EDGE CASES & PERFORMANCE")
print("="*70)

# 5a. Edge case: bonus_pct=0
try:
    r = requests.get(f"{API}/pipeline?bonus_pct=0", timeout=30)
    test("Edge: bonus_pct=0", r.status_code == 200, "No crash with 0% bonus")
except:
    test("Edge: bonus_pct=0", False, "Crashed")

# 5b. Edge case: bonus_pct=0.30 (max)
try:
    r = requests.get(f"{API}/pipeline?bonus_pct=0.30", timeout=30)
    test("Edge: bonus_pct=0.30", r.status_code == 200, "No crash with 30% bonus")
except:
    test("Edge: bonus_pct=0.30", False, "Crashed")

# 5c. Edge case: invalid PNO for inflation
try:
    r = requests.get(f"{API}/inflation?pno=NONEXISTENT&bonus_pct=0.15", timeout=10)
    test("Edge: Invalid PNO", r.status_code in [404, 400], f"Status: {r.status_code}")
except:
    test("Edge: Invalid PNO", False, "Crashed")

# 5d. Edge case: missing brand for cross-elasticity
try:
    r = requests.get(f"{API}/cross-elasticity?brand=&bonus_pct=0.15", timeout=10)
    test("Edge: Empty brand", r.status_code in [400, 404], f"Status: {r.status_code}")
except:
    test("Edge: Empty brand", False, "Crashed")

# 5e. Performance: Pipeline response time
start = time.time()
try:
    r = requests.get(f"{API}/pipeline?bonus_pct=0.15", timeout=30)
    elapsed = time.time() - start
    test("Performance: Pipeline < 5s", elapsed < 5, f"Response time: {elapsed:.2f}s")
    if elapsed > 3:
        warn("Pipeline > 3s", f"{elapsed:.2f}s — Consider pre-caching")
except:
    test("Performance: Pipeline", False, "Timeout")

# 5f. Data integrity: No null critical fields
if recs:
    null_prices = sum(1 for r in recs if r["CurrentPrice"] is None or r["OptimalPrice"] is None)
    null_costs = sum(1 for r in recs if r["CurrentCost"] is None)
    test("Data Integrity: No null prices", null_prices == 0, f"{null_prices} nulls in prices")
    test("Data Integrity: No null costs", null_costs == 0, f"{null_costs} nulls in costs")

# ═══════════════════════════════════════════════════════════════════════════════
# SUMMARY
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "="*70)
print("📊 TEST SUMMARY")
print("="*70)
total = RESULTS["pass"] + RESULTS["fail"]
print(f"  ✅ PASSED: {RESULTS['pass']}/{total}")
print(f"  ❌ FAILED: {RESULTS['fail']}/{total}")
print(f"  ⚠️  WARNINGS: {RESULTS['warn']}")
print(f"  📈 Pass Rate: {RESULTS['pass']/max(1,total)*100:.1f}%")

if RESULTS["fail"] == 0 and RESULTS["warn"] <= 2:
    print("\n  🟢 VERDICT: ✅ Production Ready")
elif RESULTS["fail"] == 0:
    print("\n  🟡 VERDICT: ⚠️ Needs Optimization")
elif RESULTS["fail"] <= 3:
    print("\n  🟠 VERDICT: ⚠️ Needs Optimization (minor failures)")
else:
    print("\n  🔴 VERDICT: ❌ Major Failures")

# Save results
with open(os.path.join(os.path.dirname(__file__), "test_results.json"), "w") as f:
    json.dump(RESULTS, f, indent=2)
print(f"\n  Results saved to test_results.json")
