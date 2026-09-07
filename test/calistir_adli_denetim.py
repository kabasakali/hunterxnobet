import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

"""
calistir_adli_denetim.py
========================
HARMONY v2.2 ADLİ KATMAN DEKOMPOZİSYONU VE LIVE-PRODUCTION DOĞRULAMASI.
"""

import os
import sys
import pandas as pd
import numpy as np

from harmony_v2_2_live_production import HarmonyV22LiveProduction
from harmony_v2_2_golden import HarmonyV22GoldenMotor

def main():
    print("=" * 160)
    print("      HARMONY v2.2 ADLİ KATMAN DEKOMPOZİSYONU VE ALFA KORUYAN LIVE-PRODUCTION DENETİMİ (2021 - 2026)")
    print("=" * 160)
    print(">> Katman Dekompozisyonu | Gercekci Valör & Cut-off | Kalibre Edilmis Live Risk Gate | 4 Asamali Walk-Forward")
    print("=" * 160)
    
    prod_eng = HarmonyV22LiveProduction()
    golden_eng = HarmonyV22GoldenMotor()
    
    # -------------------------------------------------------------------------
    # 1. BÖLÜM: 6 KATMANLI ADLİ DEKOMPOZİSYON ANALİZİ
    # -------------------------------------------------------------------------
    print("\n" + "=" * 160)
    print("                    1. BOLUM: 6 KATMANLI ADLI DEKOMPOZISYON ANALIZI (NEREDE NE KADAR ALFA KAYBEDILDI?)")
    print("=" * 160)
    
    katmanlar = [
        ("1. V2.2 Saf Alfa (Referans Baz)", False, False, False, False),
        ("2. V2.2 + TEFAS Gerçek Valör", True, False, False, False),
        ("3. V2.2 + 13:30 Cut-off Gecikmesi", False, True, False, False),
        ("4. V2.2 + Valör + Cut-off Birleşik", True, True, False, False),
        ("5. V2.2 + Valör + Cut-off + Kalite Filtresi", True, True, True, False),
        ("6. HARMONY v2.2 Live-Production (Kalibre Gate)", True, True, True, True),
    ]
    
    dekomp_tablo = []
    base_bakiye = None
    base_cagr = None
    
    for k_ad, use_val, use_cut, use_q, use_gate in katmanlar:
        r = prod_eng.simule_et_production(
            use_settlement=use_val,
            use_cutoff_lag=use_cut,
            use_quality_filter=use_q,
            use_calibrated_gate=use_gate
        )
        
        if base_bakiye is None:
            base_bakiye = r["son_bakiye_tl"]
            base_cagr = r["cagr_pct"]
            fark_tl = "0 TL (BAZ)"
            fark_cagr = "%0.00"
        else:
            diff_tl = r["son_bakiye_tl"] - base_bakiye
            diff_cagr = r["cagr_pct"] - base_cagr
            fark_tl = f"{diff_tl:,.0f} TL"
            fark_cagr = f"%{diff_cagr:.2f}"
            
        dekomp_tablo.append({
            "Katman / Model Mimarisi": k_ad,
            "Son Bakiye (100K ->)": f"{r['son_bakiye_tl']:,.0f} TL",
            "CAGR (%)": f"%{r['cagr_pct']:.2f}",
            "Max DD (%)": f"%{r['max_drawdown_pct']:.2f}",
            "Calmar": f"{r['calmar_orani']:.2f}",
            "Sharpe": f"{r['sharpe_orani']:.2f}",
            "Sortino": f"{r['sortino_orani']:.2f}",
            "CAGR Etkisi": fark_cagr,
            "Net TL Maliyet": fark_tl,
        })
    print(pd.DataFrame(dekomp_tablo).to_string(index=False))
    
    # -------------------------------------------------------------------------
    # 2. BÖLÜM: GERÇEKÇİ KESİNTİ VE SİSTEM KESİNTİSİ STRESİ (MASKELENMEYEN)
    # -------------------------------------------------------------------------
    print("\n" + "=" * 160)
    print("        2. BOLUM: GERCEKCI SISTEM KESINTISI VE SEANS SOKU STRESI (MASKELENMEYEN CEKILME)")
    print("=" * 160)
    
    stres_tablo = []
    for k_pct in [0.0, 2.0, 5.0, 10.0]:
        r_k = prod_eng.simule_et_production(kesinti_olasiligi_pct=k_pct)
        stres_tablo.append({
            "Kesinti Senaryosu": f"%{k_pct:.0f} Karar Atlanmasi",
            "Son Bakiye (100K ->)": f"{r_k['son_bakiye_tl']:,.0f} TL",
            "CAGR (%)": f"%{r_k['cagr_pct']:.2f}",
            "Max DD (%)": f"%{r_k['max_drawdown_pct']:.2f}",
            "Calmar": f"{r_k['calmar_orani']:.2f}",
            "Sharpe": f"{r_k['sharpe_orani']:.2f}",
            "En Uzun DD": f"{r_k['max_dd_gun']} Gun",
            "Normal Gun": f"{r_k['gate_counts']['NORMAL']} Gun",
            "Caution Gun": f"{r_k['gate_counts']['CAUTION']} Gun",
        })
    print(pd.DataFrame(stres_tablo).to_string(index=False))
    
    # -------------------------------------------------------------------------
    # 3. BÖLÜM: 4 AŞAMALI WALK-FORWARD v2 DOĞRULAMA (SAF V2.2 vs LIVE-PRODUCTION)
    # -------------------------------------------------------------------------
    print("\n" + "=" * 160)
    print("        3. BOLUM: 4 ASAMALI WALK-FORWARD v2 DOGRULAMASI (SAF V2.2 VS LIVE-PRODUCTION)")
    print("=" * 160)
    
    wf2_dilimleri = [
        ("1. In-Sample (2021-11 -> 2023-12)", "2021-11-22", "2023-12-31"),
        ("2. Validation 1 (2024)", "2024-01-02", "2024-12-31"),
        ("3. Validation 2 (2025)", "2025-01-02", "2025-12-31"),
        ("4. Blind OOS (2026)", "2026-01-02", "2026-08-19"),
    ]
    
    wf_res = []
    for d_ad, t_b, t_s in wf2_dilimleri:
        r_prod = prod_eng.simule_et_production(baslangic_tarihi=t_b, bitis_tarihi=t_s)
        r_saf = golden_eng.simule_et_v2_2("v2_2_agile", baslangic_tarihi=t_b, bitis_tarihi=t_s)
        
        wf_res.append({
            "Donem": d_ad,
            "Live-Prod Bakiye": f"{r_prod['son_bakiye_tl']:,.0f} TL",
            "Live-Prod Getiri": f"%{r_prod['toplam_getiri_pct']:.1f}",
            "Live-Prod CAGR": f"%{r_prod['cagr_pct']:.1f}",
            "Live-Prod Max DD": f"%{r_prod['max_drawdown_pct']:.2f}",
            "Live-Prod Calmar": f"{r_prod['calmar_orani']:.2f}",
            "Saf V2.2 Getiri": f"%{r_saf['toplam_getiri_pct']:.1f}",
            "Saf V2.2 Max DD": f"%{r_saf['max_drawdown_pct']:.2f}",
            "Saf V2.2 Calmar": f"{r_saf['calmar_orani']:.2f}",
        })
    print(pd.DataFrame(wf_res).to_string(index=False))
    print("\n" + "=" * 160)

if __name__ == "__main__":
    main()
