import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np

from harmony_v2_2_live_production import HarmonyV22LiveProduction

live_eng = HarmonyV22LiveProduction()
dt_last = live_eng.tarihler[-1]
base = live_eng.golden.base_motor.base_motor

skor_row = base.skor_df.loc[dt_last].dropna().sort_values(ascending=False)
r20_row = base.r20_df.loc[dt_last].dropna()
r63_row = base.r63_df.loc[dt_last].dropna()
fiyat_row = base.fiyat_df.loc[dt_last].dropna()

# Hunter Lider
h6_lider = live_eng.h6_aktif_fon.get(dt_last, "PPZ")
sfb_lider = live_eng.sfb_aktif_fon.get(dt_last, "PPZ")

print("=" * 90)
print(f"      GÜNCEL TEFAS SKORLARI VE ALINABİLECEK ŞAMPİYON FONLAR ({dt_last.strftime('%Y-%m-%d')})")
print("=" * 90)
print(f">> [1] HARMONY v2.2 Birincil Önerisi (Aktif Şampiyon): {h6_lider}")
print(f"       * Fon Kodu         : {h6_lider}")
print(f"       * Son Birim Fiyat  : {fiyat_row.get(h6_lider, 0.0):.6f} TL")
print(f"       * 20 Günlük Getiri : %{r20_row.get(h6_lider, 0.0)*100:+.2f}")
print(f"       * 63 Günlük Getiri : %{r63_row.get(h6_lider, 0.0)*100:+.2f}")
print("-" * 90)
print(f">> [2] Fon Nöbetçisi (Serbest Fonlar) Lideri          : {sfb_lider}")
print(f"       * Fon Kodu         : {sfb_lider}")
print(f"       * Son Birim Fiyat  : {fiyat_row.get(sfb_lider, 0.0):.6f} TL")
print(f"       * 20 Günlük Getiri : %{r20_row.get(sfb_lider, 0.0)*100:+.2f}")
print(f"       * 63 Günlük Getiri : %{r63_row.get(sfb_lider, 0.0)*100:+.2f}")
print("-" * 90)

top_list = []
for f in skor_row.head(10).index:
    top_list.append({
        "Sıra": len(top_list) + 1,
        "Fon Kodu": f,
        "Kompozit Skor": f"{skor_row[f]:.4f}",
        "20G Getiri (%)": f"%{r20_row.get(f, 0.0)*100:+.2f}",
        "63G Getiri (%)": f"%{r63_row.get(f, 0.0)*100:+.2f}",
        "Birim Fiyat (TL)": f"{fiyat_row.get(f, 0.0):,.6f} TL"
    })

print(">> [3] TÜM TEFAS EVRENİNDE EN YÜKSEK SKORLU İLK 10 FON:")
print(pd.DataFrame(top_list).to_string(index=False))
print("=" * 90)
