import os
import sys
import pandas as pd
import numpy as np

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, base_dir)
sys.path.insert(0, os.path.join(base_dir, "test"))

from harmony_v1_motor import HarmonyMotor
from harmony_v2_2_golden import HarmonyV22GoldenMotor
from lab_18_nested_walk_forward_vol_lock import Lab17VolSizingForensicsEngine

e = Lab17VolSizingForensicsEngine()
res = e.simule_et_vol(vol_window=20, target_vol=0.20)
df = res["df"]
last_row = df.iloc[-1]
last_dt = df.index[-1]

# En son günün tüm skorları
skor_df = e.golden.base_motor.base_motor.skor_df
latest_skorlar = skor_df.loc[last_dt].drop(["PPZ", "date", "tarih"], errors="ignore").dropna().sort_values(ascending=False)

# R20 matrisi
r20_df = e.r20_df
latest_r20 = r20_df.loc[last_dt].drop(["PPZ"], errors="ignore").dropna()

# 20G Volatilite
vol_20d = (e.fon_gunluk_ret.rolling(20).std() * np.sqrt(252)).loc[last_dt]


print("=" * 80)
print(f"GUNCEL TEFAS TARAMA VE MODEL E POZISYON RAPORU ({last_dt.strftime('%Y-%m-%d')})")
print("=" * 80)
print("1. MODEL E AKTIF SINYAL VE POZISYON BILGISI:")
print(f"   • Aktif Motor               : {last_row['aktif_motor']}")
print(f"   • Lider Sampiyon Fon        : {last_row['aktif_fon']}")
print(f"   • Fonun 20G Oynakligi (Vol) : %{last_row['vol_val']*100:.2f}")
print(f"   • Dinamik Pozisyon Agirligi : %{last_row['w']*100:.1f} ({last_row['aktif_fon']}) + %{(1.0-last_row['w'])*100:.1f} (PPZ Nakit)")
print(f"   • Piyasa Genisligi (Breadth): %{e.market_breadth.get(last_dt, 0)*100:.1f} (Boga Rejimi)")

print("\n2. TEFAS GUNCEL EN YUKSEK SKORLU ILK 10 FON:")
print(f"{'Sira':<4} | {'Fon':<5} | {'Skor':<8} | {'20G Getiri':<11} | {'20G Volatilite':<15} | {'Onerilen Agirlik'}")
print("-" * 80)

for i in range(min(10, len(latest_skorlar))):
    f_kod = latest_skorlar.index[i]
    skor_v = latest_skorlar.iloc[i]
    r20_v = latest_r20.get(f_kod, 0.0) * 100.0
    vol_v = vol_20d.get(f_kod, 0.20) * 100.0
    rec_w = min(1.0, max(0.40, 20.0 / (vol_v + 1e-4))) * 100.0
    print(f"{i+1:<4} | {f_kod:<5} | {skor_v:<8.3f} | %{r20_v:>+8.2f} | %{vol_v:<14.2f} | %{rec_w:.1f} ({f_kod})")
print("=" * 80)
