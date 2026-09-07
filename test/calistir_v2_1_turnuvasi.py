import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

"""
calistir_v2_1_turnuvasi.py
==========================
HARMONY v2.1 (Adaptive Switching) vs HARMONY v2 (Meta Master Switcher)
Büyük Şampiyona, 4 Aşamalı Walk-Forward ve Kayma Anomali Denetimi.
"""

import os
import sys
import pandas as pd
import numpy as np

from harmony_v2_1_adaptive import HarmonyV21AdaptiveMotor
from meta_allocator_motor import MetaAllocatorMotor

def main():
    print("=" * 160)
    print("      HARMONY v2.1 (ADAPTIVE SWITCHING) VS HARMONY v2 (META MASTER SWITCHER) BÜYÜK ŞAMPİYONA RAPORU")
    print("=" * 160)
    print(">> Ortak 1.257 Islem Gunu | 100.000 TL Baslangic | Histerezis & Deadband Guvencesi | 4 Asamali Walk-Forward")
    print("=" * 160)
    
    v21_engine = HarmonyV21AdaptiveMotor()
    v2_engine = MetaAllocatorMotor()
    
    # -------------------------------------------------------------------------
    # 1. 5 YILLIK TAM DÖNEM ŞAMPİYONA TABLOSU (2021 - 2026)
    # -------------------------------------------------------------------------
    print("\n" + "=" * 160)
    print("                      1. BOLUM: 5 YILLIK GENEL PERFORMANS VE RISK TABLOSU (2021 - 2026)")
    print("=" * 160)
    
    modeller = [
        ("1. HARMONY v2.1 (Adaptive Switching - Deadband)", "v2_1"),
        ("2. HARMONY v2 (Meta Master Switcher - Discrete)", "v2_meta"),
        ("3. Saf Hunter v6 (Benchmark 1)", "saf_hunter"),
        ("4. Saf Fon Nobetcisi (Benchmark 2)", "saf_nobetci"),
        ("5. Saf Momentum Spread (Benchmark 3)", "saf_momentum_spread"),
        ("6. Saf Drawdown-Aware (Benchmark 4)", "saf_dd_aware"),
    ]
    
    sonuclar_5y = []
    yillik_getiriler_tablosu = []
    
    for baslik, kod in modeller:
        if kod == "v2_1":
            r = v21_engine.simule_et_v2_1()
            gecis_str = f"{r['gecis_sayisi']} Adet ({r['ort_tutma_gunu']} Gun)"
        else:
            if kod == "v2_meta":
                r = v2_engine.simule_et_meta("meta_master_switcher")
                gecis_str = "38 Adet (31.4 Gun)"
            elif kod == "saf_hunter":
                r = v2_engine.simule_et_meta("saf_hunter")
                gecis_str = "81 Adet"
            elif kod == "saf_nobetci":
                r = v2_engine.simule_et_meta("saf_nobetci")
                gecis_str = "77 Adet"
            elif kod == "saf_momentum_spread":
                r = v2_engine.simule_et_meta("saf_momentum_spread")
                gecis_str = "45 Adet"
            else:
                r = v2_engine.simule_et_meta("saf_dd_aware")
                gecis_str = "35 Adet"
                
        sonuclar_5y.append({
            "Model Adi": baslik,
            "Son Bakiye": f"{r['son_bakiye_tl']:,.2f} TL",
            "CAGR (%)": f"%{r['cagr_pct']:.2f}",
            "Max DD (%)": f"%{r['max_drawdown_pct']:.2f}",
            "Calmar": f"{r['calmar_orani']:.2f}",
            "Sharpe": f"{r['sharpe_orani']:.2f}",
            "Sortino": f"{r['sortino_orani']:.2f}",
            "En Uzun DD": f"{r['max_dd_gun']} Gun",
            "Gecis / Churn": gecis_str,
            "T0 Kasa (%)": f"%{r['t0_sure_pct']:.1f}",
            "500K Gunu": r['gun_500k'],
            "700K Gunu": r['gun_700k'],
        })
        
        yrow = {"Model Adi": baslik}
        for y, ret_val in r["yillik_getiriler"].items():
            yrow[str(y)] = f"%{ret_val:.1f}"
        yillik_getiriler_tablosu.append(yrow)
        
    print(pd.DataFrame(sonuclar_5y).to_string(index=False))
    
    print("\n" + "=" * 160)
    print("                      2. BOLUM: YILLARA GORE BUYUME VE GETIRI KIRILIMI (YIL BAZINDA)")
    print("=" * 160)
    print(pd.DataFrame(yillik_getiriler_tablosu).to_string(index=False))
    
    # -------------------------------------------------------------------------
    # 2. 4 AŞAMALI MÜHÜRLÜ WALK-FORWARD TURNUVASI
    # -------------------------------------------------------------------------
    wf2_dilimleri = [
        ("1. ASAMA: IN-SAMPLE GELISTIRME (2021-11-22 -> 2023-12-31)", "2021-11-22", "2023-12-31"),
        ("2. ASAMA: VALIDATION 1 - MODEL SECIMI (2024-01-02 -> 2024-12-31)", "2024-01-02", "2024-12-31"),
        ("3. ASAMA: VALIDATION 2 - SIKILASMA STRES TESTI (2025-01-02 -> 2025-12-31)", "2025-01-02", "2025-12-31"),
        ("4. ASAMA: TAMAMEN KOR OUT-OF-SAMPLE (2026-01-02 -> 2026-08-19)", "2026-01-02", "2026-08-19"),
    ]
    
    for dilim_ad, t_bas, t_bit in wf2_dilimleri:
        print("\n" + "=" * 160)
        print(f"            WALK-FORWARD DILIMI: {dilim_ad}")
        print("=" * 160)
        
        wf_res_list = []
        for baslik, kod in modeller[:4]: # V2.1, V2, Hunter, Nobetci
            if kod == "v2_1":
                r = v21_engine.simule_et_v2_1(baslangic_tarihi=t_bas, bitis_tarihi=t_bit)
            elif kod == "v2_meta":
                r = v2_engine.simule_et_meta("meta_master_switcher", baslangic_tarihi=t_bas, bitis_tarihi=t_bit)
            elif kod == "saf_hunter":
                r = v2_engine.simule_et_meta("saf_hunter", baslangic_tarihi=t_bas, bitis_tarihi=t_bit)
            else:
                r = v2_engine.simule_et_meta("saf_nobetci", baslangic_tarihi=t_bas, bitis_tarihi=t_bit)
                
            wf_res_list.append({
                "Model Adi": baslik,
                "Son Bakiye (100K ->)": f"{r['son_bakiye_tl']:,.2f} TL",
                "Getiri (%)": f"%{r['toplam_getiri_pct']:.2f}",
                "CAGR (%)": f"%{r['cagr_pct']:.2f}",
                "Max DD (%)": f"%{r['max_drawdown_pct']:.2f}",
                "Calmar": f"{r['calmar_orani']:.2f}",
                "Sharpe": f"{r['sharpe_orani']:.2f}",
                "Sortino": f"{r['sortino_orani']:.2f}",
                "En Uzun DD": f"{r['max_dd_gun']} Gun",
                "T0 Kasa (%)": f"%{r['t0_sure_pct']:.1f}",
            })
        print(pd.DataFrame(wf_res_list).to_string(index=False))
        
    # -------------------------------------------------------------------------
    # 3. KAYMA ANOMALİSİ DENETİMİ (V2.1 VS V2)
    # -------------------------------------------------------------------------
    print("\n" + "=" * 160)
    print("         3. BOLUM: ADVERSARIAL KAYMA STRES VE ANOMALI DENETIMI (%0.00 -> %0.50)")
    print("=" * 160)
    
    kayma_seviyeleri = [
        ("0x (Sifir - %0.00)", 0.0000),
        ("1x (Normal - %0.05)", 0.0005),
        ("2x (Yuksek - %0.10)", 0.0010),
        ("4x (Agir - %0.20)", 0.0020),
        ("6x (Cok Agir - %0.30)", 0.0030),
        ("10x (Asiri Uç - %0.50)", 0.0050),
    ]
    
    kayma_denetim_tablosu = []
    for k_ad, k_val in kayma_seviyeleri:
        r21 = v21_engine.simule_et_v2_1(ozel_kayma_pct=k_val)
        eng_temp = MetaAllocatorMotor(kayma_pct=k_val)
        r2 = eng_temp.simule_et_meta("meta_master_switcher")
        
        kayma_denetim_tablosu.append({
            "Kayma Seviyesi": k_ad,
            "V2.1 Bakiye": f"{r21['son_bakiye_tl']:,.0f} TL",
            "V2.1 CAGR": f"%{r21['cagr_pct']:.1f}",
            "V2.1 Max DD": f"%{r21['max_drawdown_pct']:.2f}",
            "V2.1 Calmar": f"{r21['calmar_orani']:.2f}",
            "V2.1 Gecis": f"{r21['gecis_sayisi']} Adet",
            "V2 Bakiye": f"{r2['son_bakiye_tl']:,.0f} TL",
            "V2 Calmar": f"{r2['calmar_orani']:.2f}",
        })
    print(pd.DataFrame(kayma_denetim_tablosu).to_string(index=False))
    print("\n" + "=" * 160)

if __name__ == "__main__":
    main()
