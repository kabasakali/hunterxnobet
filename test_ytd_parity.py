import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from harmony_v2_2_live_production import HarmonyV22LiveProduction
import pandas as pd

prod = HarmonyV22LiveProduction()
res = prod.simule_et_production(
    baslangic_tarihi='2026-01-02',
    bitis_tarihi='2026-09-08'
)

df_log = pd.DataFrame(res['gunluk_kayitlar'])
rotasyonlar = []
prev = None
for _, row in df_log.iterrows():
    f = row['aktif_fon']
    if f != prev:
        rotasyonlar.append(f"{row['tarih']}: {f}")
        prev = f

out = {
    "model_kodu": res['model_kodu'],
    "son_bakiye_tl": float(res['son_bakiye_tl']),
    "ytd_getiri_pct": float(res['yillik_getiriler'].get(2026, 0.0)),
    "cagr_pct": float(res['cagr_pct']),
    "max_drawdown_pct": float(res['max_drawdown_pct']),
    "sharpe_orani": float(res['sharpe_orani']),
    "sortino_orani": float(res['sortino_orani']),
    "calmar_orani": float(res['calmar_orani']),
    "gecis_sayisi": int(res['gecis_sayisi']),
    "toplam_gun": len(df_log),
    "rotasyonlar": rotasyonlar
}

print(json.dumps(out, indent=2))
