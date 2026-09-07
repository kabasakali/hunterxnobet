"""
test/lab_post_exit_forensics.py
===============================
ÇIKIŞ SONRASI ADLİ OTOPSİ: ÇIKTIKTAN SONRA FONLARIN DURUMU NE OLDU?
"""

import os
import sys
import pandas as pd
import numpy as np

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, base_dir)
sys.path.insert(0, os.path.join(base_dir, "test"))

from lab_11_winner_retention_and_capture_forensics import Lab11WinnerRetentionEngine

l11 = Lab11WinnerRetentionEngine()
res = l11.run_pure_labe()
pozs = res["pozisyonlar"]
df_p = pd.DataFrame(pozs)
fiyat_df = l11.golden.base_motor.base_motor.fiyat_df

top_winners = df_p.sort_values(by="net_tl_kar", ascending=False).head(10)

print("=" * 125)
print("CIKIS SONRASI FON OTOPSISI (BIZ CIKTIKTAN SONRA FONLAR NE YAPTI?)")
print("=" * 125)
print(f"{'Fon':<5} | {'Giris Tarihi':<12} | {'Cikis Tarihi':<12} | {'Bizdeyken Kazanc':<18} | {'Cikis Sonrasi 10G':<18} | {'Cikis Sonrasi 20G':<18} | {'Cikis Sonrasi 40G'}")
print("-" * 125)

for _, r in top_winners.iterrows():
    f_kod = r["fon_kod"]
    g_dt = r["giris_dt"]
    c_dt = r["cikis_dt"]
    
    if f_kod in fiyat_df.columns:
        seri = fiyat_df[f_kod].dropna()
        loc_c = seri.index.get_indexer([c_dt], method="nearest")[0]
        
        # Çıkıştan sonraki 10, 20, 40 gün
        n_len = len(seri)
        r_post_10 = (seri.iloc[min(n_len - 1, loc_c + 10)] / seri.iloc[loc_c] - 1.0) * 100.0 if loc_c + 10 < n_len else (seri.iloc[-1] / seri.iloc[loc_c] - 1.0) * 100.0
        r_post_20 = (seri.iloc[min(n_len - 1, loc_c + 20)] / seri.iloc[loc_c] - 1.0) * 100.0 if loc_c + 20 < n_len else (seri.iloc[-1] / seri.iloc[loc_c] - 1.0) * 100.0
        r_post_40 = (seri.iloc[min(n_len - 1, loc_c + 40)] / seri.iloc[loc_c] - 1.0) * 100.0 if loc_c + 40 < n_len else (seri.iloc[-1] / seri.iloc[loc_c] - 1.0) * 100.0
    else:
        r_post_10, r_post_20, r_post_40 = 0.0, 0.0, 0.0
        
    s_holding = f"%{r['net_pct_kar']:>+6.2f}"
    s_post10 = f"%{r_post_10:>+6.2f}"
    s_post20 = f"%{r_post_20:>+6.2f}"
    s_post40 = f"%{r_post_40:>+6.2f}"
    
    print(f"{f_kod:<5} | {g_dt.strftime('%Y-%m-%d'):<12} | {c_dt.strftime('%Y-%m-%d'):<12} | {s_holding:<18} | {s_post10:<18} | {s_post20:<18} | {s_post40}")
    
print("=" * 125)
