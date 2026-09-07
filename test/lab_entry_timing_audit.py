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

print("=" * 110)
print("GERCEK GIRIS ZAMANLAMASI VE TEYIT OTOPSISI (TOP 10 SAMPIYON ISLEM)")
print("=" * 110)
print(f"{'Fon':<5} | {'Giris Tarihi':<12} | {'Cikis Tarihi':<12} | {'Giris Oncesi 10G':<18} | {'Giris Oncesi 20G':<18} | {'Tasirken Net Getiri':<20} | {'Net Kar'}")
print("-" * 110)

for _, r in top_winners.iterrows():
    f_kod = r["fon_kod"]
    g_dt = r["giris_dt"]
    c_dt = r["cikis_dt"]
    
    if f_kod in fiyat_df.columns:
        seri = fiyat_df[f_kod].dropna()
        loc_g = seri.index.get_indexer([g_dt], method="nearest")[0]
        
        # Girişten önceki 10 ve 20 gün getirisi
        ret_pre_10 = (seri.iloc[loc_g] / seri.iloc[max(0, loc_g - 10)] - 1.0) * 100.0 if loc_g >= 10 else 0.0
        ret_pre_20 = (seri.iloc[loc_g] / seri.iloc[max(0, loc_g - 20)] - 1.0) * 100.0 if loc_g >= 20 else 0.0
    else:
        ret_pre_10, ret_pre_20 = 0.0, 0.0
        
    s_pre10 = f"%{ret_pre_10:>+5.2f}"
    s_pre20 = f"%{ret_pre_20:>+5.2f}"
    net_r = f"%{r['net_pct_kar']:>+6.2f}"
    kar_tl = f"+{r['net_tl_kar']:>10,.0f} TL"
    
    print(f"{f_kod:<5} | {g_dt.strftime('%Y-%m-%d'):<12} | {c_dt.strftime('%Y-%m-%d'):<12} | {s_pre10:<18} | {s_pre20:<18} | {net_r:<20} | {kar_tl}")
    
print("=" * 110)
