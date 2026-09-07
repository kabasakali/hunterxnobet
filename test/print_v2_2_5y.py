import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harmony_v2_2_golden import HarmonyV22GoldenMotor
from harmony_v2_1_adaptive import HarmonyV21AdaptiveMotor
from meta_allocator_motor import MetaAllocatorMotor
import pandas as pd

v22 = HarmonyV22GoldenMotor()
v21 = HarmonyV21AdaptiveMotor()
v2 = MetaAllocatorMotor()

modeller = [
    ("1. HARMONY v2.2 (Agile Deadband - Altin Denge)", "v2_2_agile"),
    ("2. HARMONY v2.2 (Soft-Brake Transition)", "v2_2_soft_brake"),
    ("3. HARMONY v2.2 (Turbo Nobetci Alpha)", "v2_2_turbo_alpha"),
    ("4. HARMONY v2 (Meta Master Switcher)", "v2_meta"),
    ("5. HARMONY v2.1 (Kati Deadband)", "v2_1"),
    ("6. Saf Hunter v6 (Benchmark 1)", "saf_hunter"),
    ("7. Saf Fon Nobetcisi (Benchmark 2)", "saf_nobetci"),
]

res = []
for b, k in modeller:
    if k.startswith("v2_2"):
        r = v22.simule_et_v2_2(varyant=k)
    elif k == "v2_1":
        r = v21.simule_et_v2_1()
    elif k == "v2_meta":
        r = v2.simule_et_meta("meta_master_switcher")
    elif k == "saf_hunter":
        r = v2.simule_et_meta("saf_hunter")
    else:
        r = v2.simule_et_meta("saf_nobetci")
        
    res.append({
        "Model": b,
        "Bakiye": f"{r['son_bakiye_tl']:,.2f} TL",
        "CAGR": f"%{r['cagr_pct']:.2f}",
        "Max DD": f"%{r['max_drawdown_pct']:.2f}",
        "Calmar": f"{r['calmar_orani']:.2f}",
        "Sharpe": f"{r['sharpe_orani']:.2f}",
        "Sortino": f"{r['sortino_orani']:.2f}",
        "En Uzun DD": f"{r['max_dd_gun']} Gun",
        "Worst Year": r['worst_year'],
        "T0 Kasa": f"%{r['t0_sure_pct']:.1f}",
        "500K": r['gun_500k'],
        "700K": r['gun_700k']
    })

print(pd.DataFrame(res).to_string(index=False))
