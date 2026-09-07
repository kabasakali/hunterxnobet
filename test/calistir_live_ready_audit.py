import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

"""
calistir_live_ready_audit.py
============================
HARMONY v2.2 LIVE-READY HARDENING VE CANLI PARA DENETIM RAPORU.
"""

import os
import sys
import pandas as pd
import numpy as np

from live_ready_hardening_engine import LiveReadyHardeningEngine
from harmony_v2_2_golden import HarmonyV22GoldenMotor

def main():
    print("=" * 160)
    print("             HARMONY v2.2 LIVE-READY HARDENING: CANLI PARA OPERASYONEL DENETIM RAPORU")
    print("=" * 160)
    print(">> TEFAS Valör Zinciri (T+1/T+2/T+3) | 13:30 Cut-off | Sermaye Olcekleme (100K -> 5M) | Live Risk Gate | Black Swan Testi")
    print("=" * 160)
    
    live_eng = LiveReadyHardeningEngine()
    golden_eng = HarmonyV22GoldenMotor()
    
    # -------------------------------------------------------------------------
    # 1. TEST: GERÇEKÇİ TEFAS VALÖR VE TAKAS STRES TESTİ (T+0 -> T+3)
    # -------------------------------------------------------------------------
    print("\n" + "=" * 160)
    print("        1. TEST: TEFAS VALOR VE TAKAS GECIKMESI STRES TESTI (T+0 -> T+3)")
    print("=" * 160)
    
    valor_senaryolari = [
        ("T+0 (Teorik Sifir Gecikme)", 0, 0),
        ("T+1 / T+2 (Gercekci Tefas - Hisse T+1, SFB T+2)", 0, 0),
        ("T+2 / T+3 (Agir Takas - Hisse T+2, SFB T+3)", 1, 0),
        ("T+3 / T+4 (Ekstrem Serbest Fon Valoru)", 2, 0),
    ]
    
    v_tab = []
    for v_ad, e_val, g_sig in valor_senaryolari:
        r = live_eng.simule_et_live_hardened(ekstra_satis_valoru_gun=e_val, sinyal_gecikmesi_gun=g_sig)
        v_tab.append({
            "Valör Senaryosu": v_ad,
            "Son Bakiye (100K ->)": f"{r['son_bakiye_tl']:,.0f} TL",
            "CAGR (%)": f"%{r['cagr_pct']:.2f}",
            "Max DD (%)": f"%{r['max_drawdown_pct']:.2f}",
            "Calmar": f"{r['calmar_orani']:.2f}",
            "Sharpe": f"{r['sharpe_orani']:.2f}",
            "Sortino": f"{r['sortino_orani']:.2f}",
            "En Uzun DD": f"{r['max_dd_gun']} Gun",
            "Motor Gecisi": f"{r['gecis_sayisi']} Adet",
        })
    print(pd.DataFrame(v_tab).to_string(index=False))
    
    # -------------------------------------------------------------------------
    # 2. TEST: 13:30 CUT-OFF VE KARAR GECİKMESİ TESTİ (0 -> 2 GÜN)
    # -------------------------------------------------------------------------
    print("\n" + "=" * 160)
    print("        2. TEST: 13:30 CUT-OFF VE KARAR GECIKMESI TESTI (0 -> 2 IS GUNU GECIKME)")
    print("=" * 160)
    
    cut_tab = []
    for g in [0, 1, 2]:
        r_cut = live_eng.simule_et_live_hardened(sinyal_gecikmesi_gun=g)
        cut_tab.append({
            "Cut-off / Sinyal Durumu": f"{g} Is Gunu Gecikme" if g > 0 else "0 Gun (13:30 Oncesi Tam Karar)",
            "Son Bakiye (100K ->)": f"{r_cut['son_bakiye_tl']:,.0f} TL",
            "CAGR (%)": f"%{r_cut['cagr_pct']:.2f}",
            "Max DD (%)": f"%{r_cut['max_drawdown_pct']:.2f}",
            "Calmar": f"{r_cut['calmar_orani']:.2f}",
            "Sharpe": f"{r_cut['sharpe_orani']:.2f}",
            "Sortino": f"{r_cut['sortino_orani']:.2f}",
            "En Uzun DD": f"{r_cut['max_dd_gun']} Gun",
        })
    print(pd.DataFrame(cut_tab).to_string(index=False))
    
    # -------------------------------------------------------------------------
    # 3. TEST: SERMAYE ÖLÇEKLEME VE LİKİDİTE KISITI (100K -> 5M TL)
    # -------------------------------------------------------------------------
    print("\n" + "=" * 160)
    print("        3. TEST: SERMAYE OLCEKLEME VE LIKIDITE / PIYASA ETKISI TESTI (100K -> 5M TL)")
    print("=" * 160)
    
    sermaye_listesi = [
        ("100.000 TL (Bireysel Standart)", 100_000.0),
        ("500.000 TL (Yuksek Bakiye)", 500_000.0),
        ("1.000.000 TL (1 Milyon Portfoy)", 1_000_000.0),
        ("3.000.000 TL (3 Milyon Portfoy)", 3_000_000.0),
        ("5.000.000 TL (5 Milyon Kurumsal)", 5_000_000.0),
    ]
    
    cap_tab = []
    for c_ad, c_val in sermaye_listesi:
        r_cap = live_eng.simule_et_live_hardened(sermaye_tl=c_val)
        kat = r_cap["son_bakiye_tl"] / c_val
        cap_tab.append({
            "Baslangic Sermayesi": c_ad,
            "Nihai Portfoy": f"{r_cap['son_bakiye_tl']:,.0f} TL",
            "Katlanma": f"{kat:.1f}x",
            "CAGR (%)": f"%{r_cap['cagr_pct']:.2f}",
            "Max DD (%)": f"%{r_cap['max_drawdown_pct']:.2f}",
            "Calmar": f"{r_cap['calmar_orani']:.2f}",
            "Sharpe": f"{r_cap['sharpe_orani']:.2f}",
        })
    print(pd.DataFrame(cap_tab).to_string(index=False))
    
    # -------------------------------------------------------------------------
    # 4. TEST: VERİ KESİNTİSİ VE KARAR GÜNÜ ATLANMASI (SİSTEM KESİNTİSİ)
    # -------------------------------------------------------------------------
    print("\n" + "=" * 160)
    print("        4. TEST: VERI ANOMALISI VE RASTGELE SISTEM KESINTISI TESTI (%0 -> %10 ATLANMA)")
    print("=" * 160)
    
    kes_tab = []
    for k_pct in [0.0, 2.0, 5.0, 10.0]:
        r_kes = live_eng.simule_et_live_hardened(veri_kaybi_olasiligi_pct=k_pct)
        kes_tab.append({
            "Kesinti Olasiligi": f"%{k_pct:.0f} Karar Atlanmasi",
            "Son Bakiye (100K ->)": f"{r_kes['son_bakiye_tl']:,.0f} TL",
            "CAGR (%)": f"%{r_kes['cagr_pct']:.2f}",
            "Max DD (%)": f"%{r_kes['max_drawdown_pct']:.2f}",
            "Calmar": f"{r_kes['calmar_orani']:.2f}",
            "Emergency Gun Sayisi": f"{r_kes['gate_counts']['EMERGENCY']} Gun",
            "Normal Gun Sayisi": f"{r_kes['gate_counts']['NORMAL']} Gun",
        })
    print(pd.DataFrame(kes_tab).to_string(index=False))
    
    # -------------------------------------------------------------------------
    # 5. TEST: BLACK SWAN & KÖTÜ GÜN STRES TESTİ
    # -------------------------------------------------------------------------
    print("\n" + "=" * 160)
    print("        5. TEST: BLACK SWAN VE KOTU GUN STRES TESTI (SEANS SOKLARI & YANLIS FON CEZALANDIRMASI)")
    print("=" * 160)
    
    r_normal = live_eng.simule_et_live_hardened(kotu_gun_stresi=False)
    r_kotu = live_eng.simule_et_live_hardened(kotu_gun_stresi=True)
    
    kotu_tab = [
        {"Senaryo": "Standart Canli Hardened Model", "Bakiye": f"{r_normal['son_bakiye_tl']:,.0f} TL", "CAGR": f"%{r_normal['cagr_pct']:.2f}", "Max DD": f"%{r_normal['max_drawdown_pct']:.2f}", "Calmar": f"{r_normal['calmar_orani']:.2f}"},
        {"Senaryo": "Black Swan & Kötü Gün Stresi (Ekstra Şoklar)", "Bakiye": f"{r_kotu['son_bakiye_tl']:,.0f} TL", "CAGR": f"%{r_kotu['cagr_pct']:.2f}", "Max DD": f"%{r_kotu['max_drawdown_pct']:.2f}", "Calmar": f"{r_kotu['calmar_orani']:.2f}"},
    ]
    print(pd.DataFrame(kotu_tab).to_string(index=False))
    
    # -------------------------------------------------------------------------
    # 6. BÖLÜM: 4 AŞAMALI WALK-FORWARD v2 MÜHÜRLÜ DOĞRULAMA (HARDENED vs CHAMPION)
    # -------------------------------------------------------------------------
    print("\n" + "=" * 160)
    print("        6. BOLUM: 4 ASAMALI WALK-FORWARD v2 DOGRULAMA (LIVE-HARDENED VS CHAMPION V2.2)")
    print("=" * 160)
    
    wf2_dilimleri = [
        ("1. In-Sample (2021-11 -> 2023-12)", "2021-11-22", "2023-12-31"),
        ("2. Validation 1 (2024)", "2024-01-02", "2024-12-31"),
        ("3. Validation 2 (2025)", "2025-01-02", "2025-12-31"),
        ("4. Blind OOS (2026)", "2026-01-02", "2026-08-19"),
    ]
    
    wf_tab = []
    for d_ad, t_b, t_s in wf2_dilimleri:
        r_hard = live_eng.simule_et_live_hardened(baslangic_tarihi=t_b, bitis_tarihi=t_s)
        r_champ = golden_eng.simule_et_v2_2("v2_2_agile", baslangic_tarihi=t_b, bitis_tarihi=t_s)
        
        wf_tab.append({
            "Donem": d_ad,
            "Hardened Bakiye": f"{r_hard['son_bakiye_tl']:,.0f} TL",
            "Hardened Getiri": f"%{r_hard['toplam_getiri_pct']:.1f}",
            "Hardened Max DD": f"%{r_hard['max_drawdown_pct']:.2f}",
            "Hardened Calmar": f"{r_hard['calmar_orani']:.2f}",
            "Champion Getiri": f"%{r_champ['toplam_getiri_pct']:.1f}",
            "Champion Max DD": f"%{r_champ['max_drawdown_pct']:.2f}",
        })
    print(pd.DataFrame(wf_tab).to_string(index=False))
    print("\n" + "=" * 160)

if __name__ == "__main__":
    main()
