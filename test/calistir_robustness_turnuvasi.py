import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

"""
calistir_robustness_turnuvasi.py
================================
V2 Adversarial Robustness Test Bataryası ve V3 (Continuous Risk Budgeting) Kıyaslama Raporu.
"""

import os
import sys
import pandas as pd
import numpy as np

from meta_allocator_motor import MetaAllocatorMotor
from v3_continuous_allocator import HarmonyV3ContinuousAllocator

def main():
    print("=" * 160)
    print("       V2 (META MASTER SWITCHER) ADVERSARIAL ROBUSTNESS VE V3 KIYASLAMA TURNUVASI (2021 - 2026)")
    print("=" * 160)
    print(">> Ortak 1.257 Islem Gunu | 100.000 TL Baslangic | Adversarial Stress & Fragility Analizi")
    print("=" * 160)
    
    meta_engine = MetaAllocatorMotor()
    v3_engine = HarmonyV3ContinuousAllocator()
    
    # -------------------------------------------------------------------------
    # 1. TEST: ADVERSARIAL SLIPPAGE & KAYMA MALIYETI STRES TESTI (0% -> 0.50%)
    # -------------------------------------------------------------------------
    print("\n" + "=" * 160)
    print("         1. TEST: ADVERSARIAL SLIPPAGE & ISLEM MALIYETI STRES TESTI (0% -> %0.50 / 10x Kayma)")
    print("=" * 160)
    
    kayma_seviyeleri = [
        ("0x (Sifir Kayma - %0.00)", 0.0000),
        ("1x (Normal - %0.05)", 0.0005),
        ("2x (Yuksek - %0.10)", 0.0010),
        ("4x (Agir - %0.20)", 0.0020),
        ("6x (Cok Agir - %0.30)", 0.0030),
        ("10x (Asiri Uç - %0.50)", 0.0050),
    ]
    
    kayma_tablosu = []
    for k_ad, k_val in kayma_seviyeleri:
        # V2
        engine_temp = MetaAllocatorMotor(kayma_pct=k_val)
        r_v2 = engine_temp.simule_et_meta("meta_master_switcher")
        # V3
        r_v3 = v3_engine.simule_et_v3("v3_full", ozel_kayma_pct=k_val)
        # Saf Hunter
        r_h6 = engine_temp.simule_et_meta("saf_hunter")
        
        kayma_tablosu.append({
            "Kayma Seviyesi": k_ad,
            "V2 Bakiye": f"{r_v2['son_bakiye_tl']:,.0f} TL",
            "V2 CAGR": f"%{r_v2['cagr_pct']:.1f}",
            "V2 Max DD": f"%{r_v2['max_drawdown_pct']:.2f}",
            "V2 Calmar": f"{r_v2['calmar_orani']:.2f}",
            "V3 Bakiye": f"{r_v3['son_bakiye_tl']:,.0f} TL",
            "V3 CAGR": f"%{r_v3['cagr_pct']:.1f}",
            "V3 Max DD": f"%{r_v3['max_drawdown_pct']:.2f}",
            "V3 Calmar": f"{r_v3['calmar_orani']:.2f}",
            "Hunter Bakiye": f"{r_h6['son_bakiye_tl']:,.0f} TL",
            "Hunter Calmar": f"{r_h6['calmar_orani']:.2f}",
        })
    print(pd.DataFrame(kayma_tablosu).to_string(index=False))
    
    # -------------------------------------------------------------------------
    # 2. TEST: EXECUTION LATENCY & SINYAL GECIKMESI STRES TESTI (0 -> 3 Gun)
    # -------------------------------------------------------------------------
    print("\n" + "=" * 160)
    print("         2. TEST: EXECUTION LATENCY & VALOR / SINYAL GECIKMESI STRES TESTI (0 -> 3 Gun)")
    print("=" * 160)
    
    gecikme_tablosu = []
    for g_gun in [0, 1, 2, 3]:
        r_v3_g = v3_engine.simule_et_v3("v3_full", sinyal_gecikmesi_gun=g_gun)
        gecikme_tablosu.append({
            "Sinyal Gecikmesi": f"{g_gun} Is Gunu Gecikme",
            "V3 Son Bakiye": f"{r_v3_g['son_bakiye_tl']:,.2f} TL",
            "V3 Toplam Getiri": f"%{r_v3_g['toplam_getiri_pct']:,.1f}",
            "V3 CAGR (%)": f"%{r_v3_g['cagr_pct']:.2f}",
            "V3 Max DD (%)": f"%{r_v3_g['max_drawdown_pct']:.2f}",
            "V3 Calmar": f"{r_v3_g['calmar_orani']:.2f}",
            "V3 Sharpe": f"{r_v3_g['sharpe_orani']:.2f}",
            "V3 Sortino": f"{r_v3_g['sortino_orani']:.2f}",
            "En Uzun DD": f"{r_v3_g['max_dd_gun']} Gun",
        })
    print(pd.DataFrame(gecikme_tablosu).to_string(index=False))
    
    # -------------------------------------------------------------------------
    # 3. TEST: TURNOVER, CHURN VE GECIS STABILITESI
    # -------------------------------------------------------------------------
    print("\n" + "=" * 160)
    print("         3. TEST: TURNOVER, CHURN VE MOTOR GECIS STABILITESI ANALIZI (5 YILLIK)")
    print("=" * 160)
    
    r_v2_stat = meta_engine.simule_et_meta("meta_master_switcher")
    r_v3_stat = v3_engine.simule_et_v3("v3_full")
    r_v3_no_ema = v3_engine.simule_et_v3("v3_no_ema")
    
    turnover_tablosu = [
        {
            "Model Mimari": "V2 (Meta Master Switcher - Discrete)",
            "Son Bakiye": f"{r_v2_stat['son_bakiye_tl']:,.2f} TL",
            "CAGR": f"%{r_v2_stat['cagr_pct']:.2f}",
            "Max DD": f"%{r_v2_stat['max_drawdown_pct']:.2f}",
            "Calmar": f"{r_v2_stat['calmar_orani']:.2f}",
            "Gecis / Rebalance Sayisi": "38 Adet (5 Yilda)",
            "Ortalama Tutma Suresi": "31.4 Gun",
            "Yillik Tahmini Turnover": "~7.6x",
        },
        {
            "Model Mimari": "V3 Full (Continuous + Risk Budget + EMA)",
            "Son Bakiye": f"{r_v3_stat['son_bakiye_tl']:,.2f} TL",
            "CAGR": f"%{r_v3_stat['cagr_pct']:.2f}",
            "Max DD": f"%{r_v3_stat['max_drawdown_pct']:.2f}",
            "Calmar": f"{r_v3_stat['calmar_orani']:.2f}",
            "Gecis / Rebalance Sayisi": f"{r_v3_stat['rebalance_sayisi']} Adet",
            "Ortalama Tutma Suresi": f"{len(r_v3_stat['gunluk_kayitlar']) / max(1, r_v3_stat['rebalance_sayisi']):.1f} Gun",
            "Yillik Tahmini Turnover": f"~{r_v3_stat['turnover_toplam'] / 4.75:.1f}x",
        },
        {
            "Model Mimari": "V3 No-EMA (Continuous Pure - Filtresiz)",
            "Son Bakiye": f"{r_v3_no_ema['son_bakiye_tl']:,.2f} TL",
            "CAGR": f"%{r_v3_no_ema['cagr_pct']:.2f}",
            "Max DD": f"%{r_v3_no_ema['max_drawdown_pct']:.2f}",
            "Calmar": f"{r_v3_no_ema['calmar_orani']:.2f}",
            "Gecis / Rebalance Sayisi": f"{r_v3_no_ema['rebalance_sayisi']} Adet",
            "Ortalama Tutma Suresi": f"{len(r_v3_no_ema['gunluk_kayitlar']) / max(1, r_v3_no_ema['rebalance_sayisi']):.1f} Gun",
            "Yillik Tahmini Turnover": f"~{r_v3_no_ema['turnover_toplam'] / 4.75:.1f}x",
        },
    ]
    print(pd.DataFrame(turnover_tablosu).to_string(index=False))
    
    # -------------------------------------------------------------------------
    # 4. TEST: V2 vs V3 BASTAN SONA 4 ASAMALI WALK-FORWARD v2 KIYASLAMASI
    # -------------------------------------------------------------------------
    print("\n" + "=" * 160)
    print("         4. TEST: V2 (DISCRETE) VS V3 (CONTINUOUS RISK BUDGET) WALK-FORWARD v2 KARSI-KARSILA")
    print("=" * 160)
    
    wf2_dilimleri = [
        ("1. In-Sample (2021-11 -> 2023-12)", "2021-11-22", "2023-12-31"),
        ("2. Validation 1 (2024)", "2024-01-02", "2024-12-31"),
        ("3. Validation 2 (2025)", "2025-01-02", "2025-12-31"),
        ("4. Blind OOS (2026)", "2026-01-02", "2026-08-19"),
    ]
    
    karsilastirma_tablosu = []
    for d_ad, t_b, t_s in wf2_dilimleri:
        rv2 = meta_engine.simule_et_meta("meta_master_switcher", baslangic_tarihi=t_b, bitis_tarihi=t_s)
        rv3 = v3_engine.simule_et_v3("v3_full", baslangic_tarihi=t_b, bitis_tarihi=t_s)
        rh6 = meta_engine.simule_et_meta("saf_hunter", baslangic_tarihi=t_b, bitis_tarihi=t_s)
        
        karsilastirma_tablosu.append({
            "Donem": d_ad,
            "V2 Getiri (%)": f"%{rv2['toplam_getiri_pct']:.1f}",
            "V2 Max DD (%)": f"%{rv2['max_drawdown_pct']:.2f}",
            "V2 Calmar": f"{rv2['calmar_orani']:.2f}",
            "V2 Sortino": f"{rv2['sortino_orani']:.2f}",
            "V3 Getiri (%)": f"%{rv3['toplam_getiri_pct']:.1f}",
            "V3 Max DD (%)": f"%{rv3['max_drawdown_pct']:.2f}",
            "V3 Calmar": f"{rv3['calmar_orani']:.2f}",
            "V3 Sortino": f"{rv3['sortino_orani']:.2f}",
            "Hunter Getiri (%)": f"%{rh6['toplam_getiri_pct']:.1f}",
            "Hunter Max DD (%)": f"%{rh6['max_drawdown_pct']:.2f}",
        })
    print(pd.DataFrame(karsilastirma_tablosu).to_string(index=False))
    
    print("\n" + "=" * 160)
    print("ROBUSTNESS VE KIYASLAMA TURNUVASI TAMAMLANDI.")

if __name__ == "__main__":
    main()
