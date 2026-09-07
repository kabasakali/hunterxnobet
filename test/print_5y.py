import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harmony_v1_motor import HarmonyMotor
import pandas as pd

motor = HarmonyMotor()
modeller = [
    ("1. Saf Hunter v6 (%0 SFB / %100 H6)", "saf_hunter"),
    ("2. Sabit %25 SFB / %75 Hunter", "sabit_25_75"),
    ("3. Sabit %50 SFB / %50 Hunter", "sabit_50_50"),
    ("4. Sabit %75 SFB / %25 Hunter", "sabit_75_25"),
    ("5. Saf Fon Nobetcisi (%100 SFB / %0 H6)", "saf_nobetci"),
    ("6. Rejim Bazli Dinamik", "rejim_dinamik"),
    ("7. Momentum Spread Dinamik", "momentum_spread"),
    ("8. Risk Paritesi Dinamik", "risk_paritesi"),
    ("9. HARMONY v1 Uclu Model (Model C)", "harmony_v1"),
    ("10. Drawdown-Aware Switching", "dd_aware_switching"),
]

res_5y = []
for b, k in modeller:
    r = motor.simule_et_model(k)
    res_5y.append({
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

print(pd.DataFrame(res_5y).to_string(index=False))
