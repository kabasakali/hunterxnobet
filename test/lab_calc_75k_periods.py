import os
import sys
import pandas as pd
import numpy as np

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, base_dir)
sys.path.insert(0, os.path.join(base_dir, "test"))

from lab_11_winner_retention_and_capture_forensics import Lab11WinnerRetentionEngine
from lab_18_nested_walk_forward_vol_lock import Lab17VolSizingForensicsEngine

START_CAP = 75_000.0

# 1. LAB-E Reference Daily Returns
l11 = Lab11WinnerRetentionEngine(baslangic_sermayesi=START_CAP)
r_labe = l11.run_pure_labe()
df_labe = r_labe["df"]
rets_labe = df_labe["gunluk_ret"]

# 2. Model E Daily Returns
e17 = Lab17VolSizingForensicsEngine(baslangic_sermayesi=START_CAP)
r_modele = e17.simule_et_vol(vol_window=20, target_vol=0.20)
df_modele = r_modele["df"]
rets_modele = df_modele["gunluk_ret"]

def calc_period(rets, start_dt, end_dt, cap=75_000.0):
    sub = rets.loc[start_dt:end_dt]
    if len(sub) == 0:
        return {"ret_pct": 0, "end_cap": cap, "profit": 0, "mdd": 0}
    wealth = cap * (1 + sub).cumprod()
    end_cap = wealth.iloc[-1]
    ret_pct = (end_cap - cap) / cap * 100.0
    profit = end_cap - cap
    peak = wealth.cummax()
    dd = (wealth - peak) / peak
    mdd = dd.min() * 100.0
    return {
        "ret_pct": ret_pct,
        "end_cap": end_cap,
        "profit": profit,
        "mdd": mdd,
        "days": len(sub)
    }

tarihler = list(rets_labe.index)
last_dt = tarihler[-1]

periods = [
    ("2021 Yili (Agustos - Aralik)", "2021-08-19", "2021-12-31"),
    ("2022 Yili (Ocak - Aralik)", "2022-01-01", "2022-12-31"),
    ("2023 Yili (Ocak - Aralik)", "2023-01-01", "2023-12-31"),
    ("2024 Yili (Ocak - Aralik)", "2024-01-01", "2024-12-31"),
    ("2025 Yili (Ocak - Aralik)", "2025-01-01", "2025-12-31"),
    ("2026 YTD (Yilbasi -> Bugun)", "2026-01-01", "2026-08-28"),
    ("---", None, None),
    ("SON 3 AY (2026 Mayis -> Bugun)", str(tarihler[-63].strftime("%Y-%m-%d")), str(last_dt.strftime("%Y-%m-%d"))),
    ("SON 2 YIL (2024 Agustos -> Bugun)", str(tarihler[-504].strftime("%Y-%m-%d")), str(last_dt.strftime("%Y-%m-%d"))),
    ("SON 5 YIL (Tum Donem 2021 -> Bugun)", str(tarihler[0].strftime("%Y-%m-%d")), str(last_dt.strftime("%Y-%m-%d")))
]

print("=" * 115, flush=True)
print("75.000 TL BASLANGIC SERMAYESI ILE LAB-E VE MODEL E PERFORMANS BILANCOSU", flush=True)
print("=" * 115, flush=True)

print(f"{'Donem / Periyod':<36} | {'LAB-E Getiri':<14} | {'LAB-E Bakiye':<16} | {'LAB-E Net Kar':<15} | {'LAB-E MaxDD'}", flush=True)
print("-" * 115, flush=True)

for name, s_d, e_d in periods:
    if s_d is None:
        print("-" * 115, flush=True)
        continue
    res = calc_period(rets_labe, s_d, e_d, START_CAP)
    r_pct = f"%{res['ret_pct']:+.2f}"
    end_b = f"{res['end_cap']:,.2f} TL"
    prf = f"+{res['profit']:,.2f} TL" if res["profit"] >= 0 else f"{res['profit']:,.2f} TL"
    mdd_s = f"%{res['mdd']:.2f}"
    print(f"{name:<36} | {r_pct:<14} | {end_b:<16} | {prf:<15} | {mdd_s}", flush=True)

print("\n" + "=" * 115, flush=True)
print("75.000 TL BASLANGIC SERMAYESI ILE MODEL E (%20 VOL RISK-PARITY) BILANCOSU", flush=True)
print("=" * 115, flush=True)
print(f"{'Donem / Periyod':<36} | {'Model E Getiri':<16} | {'Model E Bakiye':<16} | {'Model E Net Kar':<15} | {'Model E MaxDD'}", flush=True)
print("-" * 115, flush=True)

for name, s_d, e_d in periods:
    if s_d is None:
        print("-" * 115, flush=True)
        continue
    res = calc_period(rets_modele, s_d, e_d, START_CAP)
    r_pct = f"%{res['ret_pct']:+.2f}"
    end_b = f"{res['end_cap']:,.2f} TL"
    prf = f"+{res['profit']:,.2f} TL" if res["profit"] >= 0 else f"{res['profit']:,.2f} TL"
    mdd_s = f"%{res['mdd']:.2f}"
    print(f"{name:<36} | {r_pct:<16} | {end_b:<16} | {prf:<15} | {mdd_s}", flush=True)
print("=" * 115, flush=True)
