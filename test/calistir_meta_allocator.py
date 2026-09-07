import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

"""
calistir_meta_allocator.py
==========================
Meta Allocator (HARMONY v2): 4 Aşamalı Walk-Forward v2 Doğrulama Turnuvası.
"""

import os
import sys
import pandas as pd
import numpy as np
from meta_allocator_motor import MetaAllocatorMotor

def main():
    print("=" * 160)
    print("   META ALLOCATOR (HARMONY v2): 4 ASAMALI WALK-FORWARD v2 TURNUVASI VE CANLI GOLGE RAPORU (2021 - 2026)")
    print("=" * 160)
    print(">> Baslangic Sermayesi: 100.000 TL | Ortak Valor (T+1) & Kayma (%0.05) | 1.257 Islem Gunu")
    print("=" * 160)
    
    meta_engine = MetaAllocatorMotor()
    
    modeller = [
        ("1. Meta Master Switcher (Meta C)", "meta_master_switcher"),
        ("2. Regime-Spread Allocator (Meta A)", "meta_regime_spread"),
        ("3. Volatility-DD Gated (Meta B)", "meta_vol_dd_gated"),
        ("4. Continuous Factor Allocator (Meta D)", "meta_continuous_factor"),
        ("5. Saf Hunter v6 (Benchmark 1)", "saf_hunter"),
        ("6. Momentum Spread Motoru (Benchmark 2)", "saf_momentum_spread"),
        ("7. Drawdown-Aware Motoru (Benchmark 3)", "saf_dd_aware"),
        ("8. Saf Fon Nobetcisi (Benchmark 4)", "saf_nobetci"),
        ("9. Sabit %25 SFB + %75 Hunter (Benchmark 5)", "sabit_25_75"),
    ]
    
    # -------------------------------------------------------------------------
    # 1. 5 YILLIK GENEL PERFORMANS (2021 - 2026)
    # -------------------------------------------------------------------------
    print("\n" + "=" * 160)
    print("               1. BOLUM: 5 YILLIK TAM DONEM META ALLOCATOR PERFORMANS VE RISK TABLOSU (2021 - 2026)")
    print("=" * 160)
    
    sonuclar_5y = []
    yillik_getiriler_tablosu = []
    
    for baslik, kod in modeller:
        res = meta_engine.simule_et_meta(kod)
        sonuclar_5y.append({
            "Model Adi": baslik,
            "Son Bakiye": f"{res['son_bakiye_tl']:,.2f} TL",
            "CAGR (%)": f"%{res['cagr_pct']:.2f}",
            "Max DD (%)": f"%{res['max_drawdown_pct']:.2f}",
            "Calmar": f"{res['calmar_orani']:.2f}",
            "Sharpe": f"{res['sharpe_orani']:.2f}",
            "Sortino": f"{res['sortino_orani']:.2f}",
            "En Uzun DD": f"{res['max_dd_gun']} Gun",
            "En Kotu Yil": res['worst_year'],
            "T0 Kasa (%)": f"%{res['t0_sure_pct']:.1f}",
            "500K Gunu": res['gun_500k'],
            "700K Gunu": res['gun_700k'],
        })
        
        yrow = {"Model Adi": baslik}
        for y, r in res["yillik_getiriler"].items():
            yrow[str(y)] = f"%{r:.1f}"
        yillik_getiriler_tablosu.append(yrow)
        
    df_5y = pd.DataFrame(sonuclar_5y)
    print(df_5y.to_string(index=False))
    
    print("\n" + "=" * 160)
    print("               2. BOLUM: YILLARA GORE BUYUME VE GETIRI KIRILIMI (YIL BAZINDA)")
    print("=" * 160)
    df_yil = pd.DataFrame(yillik_getiriler_tablosu)
    print(df_yil.to_string(index=False))
    
    # -------------------------------------------------------------------------
    # 2. 4 ASAMALI WALK-FORWARD v2 PROTOKOLU
    # -------------------------------------------------------------------------
    wf2_dilimleri = [
        ("1. ASAMA: IN-SAMPLE GELISTIRME (2021-11-22 -> 2023-12-31 / 532 Gun)", "2021-11-22", "2023-12-31"),
        ("2. ASAMA: VALIDATION 1 - MODEL SECIMI (2024-01-02 -> 2024-12-31 / 252 Gun)", "2024-01-02", "2024-12-31"),
        ("3. ASAMA: VALIDATION 2 - SIKILASMA STRES TESTI (2025-01-02 -> 2025-12-31 / 252 Gun)", "2025-01-02", "2025-12-31"),
        ("4. ASAMA: TAMAMEN KOR OUT-OF-SAMPLE (2026-01-02 -> 2026-08-19 / 156 Gun)", "2026-01-02", "2026-08-19"),
    ]
    
    for dilim_ad, t_bas, t_bit in wf2_dilimleri:
        print("\n" + "=" * 160)
        print(f"            WALK-FORWARD v2 DILIMI: {dilim_ad}")
        print("=" * 160)
        
        wf_res_list = []
        for baslik, kod in modeller:
            r = meta_engine.simule_et_meta(kod, baslangic_tarihi=t_bas, bitis_tarihi=t_bit)
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
        
    print("\n" + "=" * 160)
    print("META ALLOCATOR DENEYI TAMAMLANDI.")

if __name__ == "__main__":
    main()
