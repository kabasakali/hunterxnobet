"""
test/lab_q4_projection_calculator.py
====================================
Kalan 4 Ay (Eylül - Aralık) Tarihsel Getiri ve Yıl Sonu Beklenti Analizi
"""

import os
import sys
import numpy as np
import pandas as pd

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, base_dir)
sys.path.insert(0, os.path.join(base_dir, "test"))

from lab_18_nested_walk_forward_vol_lock import Lab17VolSizingForensicsEngine

e17 = Lab17VolSizingForensicsEngine(baslangic_sermayesi=100_000.0)
res = e17.simule_et_vol(vol_window=20, target_vol=0.20)
df = res["df"]

# Her yılın Eylül 1 - Aralık 31 (Son 4 Ay) getirilerini çıkar
q4_results = []
for y in range(2021, 2026):
    s_dt = f"{y}-09-01"
    e_dt = f"{y}-12-31"
    sub = df.loc[s_dt:e_dt]
    if len(sub) > 0:
        ret_q4 = (np.prod(1.0 + sub["gunluk_ret"]) - 1.0) * 100.0
        q4_results.append((y, ret_q4))

print("=== TARIHSEL SON 4 AY (EYLUL - ARALIK) MODEL E PERFORMANSLARI ===")
for y, r in q4_results:
    print(f"{y} Son 4 Ay (Eylül-Aralık): %{r:+.2f}")

avg_q4 = np.mean([r for _, r in q4_results])
median_q4 = np.median([r for _, r in q4_results])
min_q4 = np.min([r for _, r in q4_results])
max_q4 = np.max([r for _, r in q4_results])

print(f"\nTarihsel Q4 Ortalama : %{avg_q4:+.2f}")
print(f"Tarihsel Q4 Medyan   : %{median_q4:+.2f}")
print(f"Tarihsel Q4 En Kotu  : %{min_q4:+.2f}")
print(f"Tarihsel Q4 En Iyi   : %{max_q4:+.2f}")
