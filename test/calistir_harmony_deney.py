import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

"""
calistir_harmony_deney.py
=========================
HARMONY v1 — Rejim Adaptif Allocator (10 Model x 3 Aşamalı Walk-Forward Turnuvası).

Modeller:
1. %0 SFB / %100 Hunter v6 (Saf Hunter)
2. %25 SFB / %75 Hunter v6 (Sabit Hibrit 1)
3. %50 SFB / %50 Hunter v6 (Sabit Hibrit 2)
4. %75 SFB / %25 Hunter v6 (Sabit Hibrit 3)
5. %100 SFB / %0 Hunter v6 (Saf Fon Nöbetçisi)
6. Rejim Bazlı Dinamik Ağırlıklandırma
7. Momentum Farkına Göre Dinamik Ağırlıklandırma (Momentum Spread)
8. Risk-Paritesi Benzeri Dinamik Ağırlıklandırma
9. HARMONY v1: Hunter + SFB + T0 Core Üçlü Model (⭐)
10. Drawdown-Aware Dynamic Switching
"""

import os
import sys
import pandas as pd
import numpy as np
from harmony_v1_motor import HarmonyMotor

def main():
    print("=" * 160)
    print("      HARMONY v1 — REJİM ADAPTİF ALLOCATOR: 10 MODEL & 3 AŞAMALI WALK-FORWARD TURNUVASI (2021 - 2026)")
    print("=" * 160)
    print(">> Başlangıç Sermayesi: 100.000 TL | Ortak Valör (T+1) & Kayma (%0.05) | 1.257 İşlem Günü")
    print("=" * 160)
    
    motor = HarmonyMotor()
    
    modeller = [
        ("1. Saf Hunter v6 (%0 SFB / %100 H6)", "saf_hunter"),
        ("2. Sabit %25 SFB / %75 Hunter", "sabit_25_75"),
        ("3. Sabit %50 SFB / %50 Hunter", "sabit_50_50"),
        ("4. Sabit %75 SFB / %25 Hunter", "sabit_75_25"),
        ("5. Saf Fon Nöbetçisi (%100 SFB / %0 H6)", "saf_nobetci"),
        ("6. Rejim Bazlı Dinamik", "rejim_dinamik"),
        ("7. Momentum Spread Dinamik", "momentum_spread"),
        ("8. Risk Paritesi Dinamik", "risk_paritesi"),
        ("9. HARMONY v1 Uclu Model (Model C)", "harmony_v1"),
        ("10. Drawdown-Aware Switching", "dd_aware_switching"),
    ]
    
    # -------------------------------------------------------------------------
    # 1. 5 YILLIK GENEL PERFORMANS (2021 - 2026)
    # -------------------------------------------------------------------------
    print("\n" + "=" * 160)
    print("                     1. BÖLÜM: 5 YILLIK TAM DÖNEM GENEL PERFORMANS VE RİSK TABLOSU (2021 - 2026)")
    print("=" * 160)
    
    sonuclar_5y = []
    yillik_getiriler_tablosu = []
    
    for baslik, kod in modeller:
        res = motor.simule_et_model(kod)
        sonuclar_5y.append({
            "Model Adı": baslik,
            "Son Bakiye": f"{res['son_bakiye_tl']:,.2f} TL",
            "CAGR (%)": f"%{res['cagr_pct']:.2f}",
            "Max DD (%)": f"%{res['max_drawdown_pct']:.2f}",
            "Calmar": f"{res['calmar_orani']:.2f}",
            "Sharpe": f"{res['sharpe_orani']:.2f}",
            "Sortino": f"{res['sortino_orani']:.2f}",
            "En Uzun DD": f"{res['max_dd_gun']} Gün",
            "En Kötü Yıl": res['worst_year'],
            "T0 Kasa (%)": f"%{res['t0_sure_pct']:.1f}",
            "500K Günü": res['gun_500k'],
            "700K Günü": res['gun_700k'],
        })
        
        yrow = {"Model Adı": baslik}
        for y, r in res["yillik_getiriler"].items():
            yrow[str(y)] = f"%{r:.1f}"
        yillik_getiriler_tablosu.append(yrow)
        
    df_5y = pd.DataFrame(sonuclar_5y)
    print(df_5y.to_string(index=False))
    
    print("\n" + "=" * 160)
    print("                     2. BÖLÜM: YILLARA GÖRE BÜYÜME VE GETİRİ KIRILIMI (YIL BAZINDA)")
    print("=" * 160)
    df_yil = pd.DataFrame(yillik_getiriler_tablosu)
    print(df_yil.to_string(index=False))
    
    # -------------------------------------------------------------------------
    # 2. 3 AŞAMALI WALK-FORWARD VE OUT-OF-SAMPLE TESTİ
    # -------------------------------------------------------------------------
    wf_dilimleri = [
        ("1. IN-SAMPLE GELİŞTİRME (2021-11-22 -> 2024-12-31)", "2021-11-22", "2024-12-31"),
        ("2. VALIDATION / DOĞRULAMA (2025-01-02 -> 2025-12-31)", "2025-01-02", "2025-12-31"),
        ("3. TAMAMEN KÖR OUT-OF-SAMPLE (2026-01-02 -> 2026-08-19)", "2026-01-02", "2026-08-19"),
    ]
    
    for dilim_ad, t_bas, t_bit in wf_dilimleri:
        print("\n" + "=" * 160)
        print(f"            WALK-FORWARD DİLİMİ: {dilim_ad}")
        print("=" * 160)
        
        wf_res_list = []
        for baslik, kod in modeller:
            r = motor.simule_et_model(kod, baslangic_tarihi=t_bas, bitis_tarihi=t_bit)
            wf_res_list.append({
                "Model Adı": baslik,
                "Son Bakiye (100K ->)": f"{r['son_bakiye_tl']:,.2f} TL",
                "Getiri (%)": f"%{r['toplam_getiri_pct']:.2f}",
                "CAGR (%)": f"%{r['cagr_pct']:.2f}",
                "Max DD (%)": f"%{r['max_drawdown_pct']:.2f}",
                "Calmar": f"{r['calmar_orani']:.2f}",
                "Sharpe": f"{r['sharpe_orani']:.2f}",
                "Sortino": f"{r['sortino_orani']:.2f}",
                "En Uzun DD": f"{r['max_dd_gun']} Gün",
                "T0 Kasa (%)": f"%{r['t0_sure_pct']:.1f}",
            })
        print(pd.DataFrame(wf_res_list).to_string(index=False))
        
    print("\n" + "=" * 160)
    print("DENEY EKSİKSİZ TAMAMLANDI.")

if __name__ == "__main__":
    main()
