"""
test/lab_1_yillik_tam_otopsi.py
===============================
SON 1 YILLIK TAM ADLİ OTOPSİ (2025-08-28 -> 2026-08-28)
- 1 Yıllık Model Karşılaştırması
- Son 1 Yıldaki Tüm İşlemlerin Giriş ve Çıkış Anatomisi
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

def run_1y_audit():
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
    
    fiyat_df = l11.golden.base_motor.base_motor.fiyat_df
    
    # Son 1 Yıl Filtresi (~252 İşlem Günü)
    tarihler = list(df_modele.index)
    son_1y_tarihler = [d for d in tarihler if d >= pd.to_datetime("2025-08-28")]
    s_dt = son_1y_tarihler[0]
    e_dt = son_1y_tarihler[-1]
    
    sub_modele = df_modele.loc[s_dt:e_dt].copy()
    sub_labe = df_labe.loc[s_dt:e_dt].copy()
    sub_v22 = df_v22.loc[s_dt:e_dt].copy()
    
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
    print(f"SON 1 YILLIK RESMI BILANCO ({s_dt.strftime('%Y-%m-%d')} -> {e_dt.strftime('%Y-%m-%d')} | {len(son_1y_tarihler)} Islem Gunu)")
    print("=" * 115)
    print(f"{'Model / Sistem':<30} | {'1 Yillik Getiri':<16} | {'35.7k Net Kar':<15} | {'75k Net Kar':<15} | {'100k Net Kar':<15} | {'1 Yillik MaxDD'}")
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
    
    # 2. Son 1 Yıldaki Pozisyonlar
    pozs = res_labe["pozisyonlar"]
    son_1y_pozs = [p for p in pozs if p["cikis_dt"] >= pd.to_datetime("2025-08-28")]
    
    print("\n" + "=" * 135)
    print(f"SON 1 YILDA GERCEKLESEN TUM ISLEMLERIN GIRIS & CIKIS OTOPSISI ({len(son_1y_pozs)} Islem):")
    print("=" * 135)
    print(f"{'Fon':<5} | {'Giris':<10} | {'Cikis':<10} | {'Gun':<4} | {'Giris Oncesi 10G':<17} | {'Giris Oncesi 20G':<17} | {'Bizdeyken Getiri':<17} | {'Cikis Sonrasi 10G':<18} | {'Cikis Sonrasi 20G'}")
    print("-" * 135)
    
    for p in son_1y_pozs:
        f_kod = p["fon_kod"]
        g_dt = p["giris_dt"]
        c_dt = p["cikis_dt"]
        t_gun = p["tutulan_gun"]
        
        if f_kod in fiyat_df.columns:
            seri = fiyat_df[f_kod].dropna()
            loc_g = seri.index.get_indexer([g_dt], method="nearest")[0]
            loc_c = seri.index.get_indexer([c_dt], method="nearest")[0]
            n_len = len(seri)
            
            ret_pre_10 = (seri.iloc[loc_g] / seri.iloc[max(0, loc_g - 10)] - 1.0) * 100.0 if loc_g >= 10 else 0.0
            ret_pre_20 = (seri.iloc[loc_g] / seri.iloc[max(0, loc_g - 20)] - 1.0) * 100.0 if loc_g >= 20 else 0.0
            
            r_post_10 = (seri.iloc[min(n_len - 1, loc_c + 10)] / seri.iloc[loc_c] - 1.0) * 100.0 if loc_c + 10 < n_len else (seri.iloc[-1] / seri.iloc[loc_c] - 1.0) * 100.0
            r_post_20 = (seri.iloc[min(n_len - 1, loc_c + 20)] / seri.iloc[loc_c] - 1.0) * 100.0 if loc_c + 20 < n_len else (seri.iloc[-1] / seri.iloc[loc_c] - 1.0) * 100.0
        else:
            ret_pre_10, ret_pre_20, r_post_10, r_post_20 = 0.0, 0.0, 0.0, 0.0
            
        s_pre10 = f"%{ret_pre_10:>+5.2f}"
        s_pre20 = f"%{ret_pre_20:>+5.2f}"
        s_hold = f"%{p['net_pct_kar']:>+6.2f}"
        s_post10 = f"%{r_post_10:>+6.2f}"
        s_post20 = f"%{r_post_20:>+6.2f}"
        
        print(f"{f_kod:<5} | {g_dt.strftime('%Y-%m-%d'):<10} | {c_dt.strftime('%Y-%m-%d'):<10} | {t_gun:<4} | {s_pre10:<17} | {s_pre20:<17} | {s_hold:<17} | {s_post10:<18} | {s_post20}")
        
    print("=" * 135)

if __name__ == "__main__":
    run_1y_audit()
