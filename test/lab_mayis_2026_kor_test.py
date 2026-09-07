"""
test/lab_mayis_2026_kor_test.py
===============================
SADECE MAYIS 2026 KÖR TESTİ VE GÜN BE GÜN TELEMETRİSİ (2026-05-01 -> 2026-05-31)
"""

import os
import sys
import numpy as np
import pandas as pd

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, base_dir)
sys.path.insert(0, os.path.join(base_dir, "test"))

from harmony_v2_2_golden import HarmonyV22GoldenMotor
from lab_11_winner_retention_and_capture_forensics import Lab11WinnerRetentionEngine
from lab_18_nested_walk_forward_vol_lock import Lab17VolSizingForensicsEngine

def run_mayis_blind_test():
    # 1. Model E
    e17 = Lab17VolSizingForensicsEngine(baslangic_sermayesi=100_000.0)
    res_modele = e17.simule_et_vol(vol_window=20, target_vol=0.20)
    df_modele = res_modele["df"]
    
    # 2. Saf LAB-E
    l11 = Lab11WinnerRetentionEngine(baslangic_sermayesi=100_000.0)
    res_labe = l11.run_pure_labe()
    df_labe = res_labe["df"]
    
    # 3. Canlıdaki V2.2
    v22 = HarmonyV22GoldenMotor(baslangic_sermayesi=100_000.0)
    res_v22 = v22.simule_et_v2_2()
    df_v22 = pd.DataFrame(res_v22["gunluk_kayitlar"])
    df_v22["dt"] = pd.to_datetime(df_v22["tarih"])
    df_v22 = df_v22.set_index("dt")
    df_v22["gunluk_ret"] = df_v22["bakiye"].pct_change().fillna(0.0)
    
    # Mayıs 2026 Verilerini Filtrele
    sub_modele = df_modele.loc["2026-05-01":"2026-05-31"].copy()
    sub_labe = df_labe.loc["2026-05-01":"2026-05-31"].copy()
    sub_v22 = df_v22.loc["2026-05-01":"2026-05-31"].copy()
    
    tarihler_mayis = list(sub_modele.index)
    s_dt = tarihler_mayis[0]
    e_dt = tarihler_mayis[-1]
    
    cum_ret_modele = np.prod(1.0 + sub_modele["gunluk_ret"]) - 1.0
    cum_ret_labe = np.prod(1.0 + sub_labe["gunluk_ret"]) - 1.0
    cum_ret_v22 = np.prod(1.0 + sub_v22["gunluk_ret"]) - 1.0
    
    rt0_sub = e17.t0_ret_serisi.loc[s_dt:e_dt]
    cum_ret_ppz = np.prod(1.0 + rt0_sub) - 1.0
    
    def calc_mdd(rets):
        w = 100_000.0 * (1.0 + rets).cumprod()
        pk = w.cummax()
        dd = (w - pk) / pk
        return dd.min() * 100.0
        
    mdd_modele = calc_mdd(sub_modele["gunluk_ret"])
    mdd_labe = calc_mdd(sub_labe["gunluk_ret"])
    mdd_v22 = calc_mdd(sub_v22["gunluk_ret"])
    
    print("=" * 115)
    print(f"MAYIS 2026 RESMI KOR TEST BILANCOSU ({s_dt.strftime('%Y-%m-%d')} -> {e_dt.strftime('%Y-%m-%d')} | {len(tarihler_mayis)} Islem Gunu)")
    print("=" * 115)
    
    print(f"{'Model / Sistem':<30} | {'Mayis Getirisi':<16} | {'35.7k Net Kar':<15} | {'75k Net Kar':<15} | {'100k Net Kar':<15} | {'Mayis MaxDD'}")
    print("-" * 115)
    
    def format_row(lbl, r_pct, mdd):
        kar_35k = 35_710.47 * r_pct
        kar_75k = 75_000.0 * r_pct
        kar_100k = 100_000.0 * r_pct
        print(f"{lbl:<30} | %{r_pct*100:<15.2f} | {kar_35k:>+12,.2f} TL | {kar_75k:>+12,.2f} TL | {kar_100k:>+12,.2f} TL | %{mdd:.2f}")
        
    format_row("MODEL E (%20 Vol Risk-Parity)", cum_ret_modele, mdd_modele)
    format_row("SAF LAB-E (%100 Sabit)", cum_ret_labe, mdd_labe)
    format_row("CANLIDAKI ESKI V2.2", cum_ret_v22, mdd_v22)
    format_row("PPZ (Nakit / Mevduat)", cum_ret_ppz, 0.0)
    print("-" * 115)
    
    print("\n" + "=" * 115)
    print("GUN BE GUN MAYIS 2026 ISLEM VE SERMAYE TELEMETRISI (MODEL E):")
    print("=" * 115)
    print(f"{'Tarih':<12} | {'Aktif Motor':<12} | {'Aktif Fon':<10} | {'20G Vol':<10} | {'Tahsis':<10} | {'Gunluk Getiri':<15} | {'Kumulatif Bakiye (100k)'}")
    print("-" * 115)
    
    bakiye_100k = 100_000.0
    for dt in tarihler_mayis:
        row = sub_modele.loc[dt]
        g_r = row["gunluk_ret"]
        bakiye_100k *= (1.0 + g_r)
        
        m_name = row["aktif_motor"]
        f_kod = row["aktif_fon"]
        v_val = row["vol_val"] * 100.0
        w_val = row["w"] * 100.0
        
        print(f"{dt.strftime('%Y-%m-%d'):<12} | {m_name:<12} | {f_kod:<10} | %{v_val:<9.1f} | %{w_val:<9.0f} | %{g_r*100:>+13.2f} | {bakiye_100k:,.2f} TL")
        
    print("=" * 115)

if __name__ == "__main__":
    run_mayis_blind_test()
