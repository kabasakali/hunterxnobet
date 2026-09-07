import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from meta_allocator_motor import MetaAllocatorMotor
import pandas as pd

meta_engine = MetaAllocatorMotor()
modeller = [
    ("1. Meta Master Switcher (Meta C)", "meta_master_switcher"),
    ("2. Regime-Spread Allocator (Meta A)", "meta_regime_spread"),
    ("3. Volatility-DD Gated (Meta B)", "meta_vol_dd_gated"),
    ("4. Continuous Factor Allocator (Meta D)", "meta_continuous_factor"),
    ("5. Saf Hunter v6 (Benchmark 1)", "saf_hunter"),
    ("6. Momentum Spread Motoru (Benchmark 2)", "saf_momentum_spread"),
    ("7. Drawdown-Aware Motoru (Benchmark 3)", "saf_dd_aware"),
    ("8. Saf Fon Nobetcisi (Benchmark 4)", "saf_nobetci"),
    ("9. Sabit %25 SFB + %75 Hunter (Benchmark 5)", "sabit_25_75"),
]

res_5y = []
for b, k in modeller:
    r = meta_engine.simule_et_meta(k)
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
