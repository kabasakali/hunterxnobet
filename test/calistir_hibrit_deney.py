import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

"""
calistir_hibrit_deney.py
========================
7 Farklı Modelin 5 Yıllık ve Dönemsel Karşılaştırmalı Deney Raporu.

Modeller:
1. Fon Nöbetçisi (Saf Benchmark)
2. Hunter v6 Unified (Saf Benchmark)
3. %50 Fon Nöbetçisi + %50 Hunter v6
4. %75 Fon Nöbetçisi + %25 Hunter v6
5. %25 Fon Nöbetçisi + %75 Hunter v6
6. Dinamik Rejim Harmanı (Dynamic Regime Blender)
7. Hunter Risk Katmanı + Fon Nöbetçisi (Sentinel Alpha Shield)
"""

import os
import sys
import pandas as pd
import numpy as np
from hibrit_motor_simulasyon import HibritMotorSimulasyon

def main():
    print("=" * 145)
    print("           BÜYÜK HİBRİT DENEYİ: FON NÖBETÇİSİ x HUNTER v6 REJİM HARMANLAMA TURNUVASI (2021 - 2026)")
    print("=" * 145)
    print(">> Veri Seti: 1.257 İşlem Günü (5 Yıl) | Ortak Valör ve Kayma | 100.000 TL Başlangıç Sermayesi")
    print("=" * 145)
    
    sim = HibritMotorSimulasyon()
    
    modeller = [
        ("1. Fon Nöbetçisi (Saf Benchmark)", "fon_nobetcisi"),
        ("2. Hunter v6 Unified (Saf Benchmark)", "hunter_v6"),
        ("3. %50 Nöbetçi + %50 Hunter v6", "sabit_50_50"),
        ("4. %75 Nöbetçi + %25 Hunter v6", "sabit_75_25"),
        ("5. %25 Nöbetçi + %75 Hunter v6", "sabit_25_75"),
        ("6. Dinamik Rejim Harmanı (Model B)", "dinamik_rejim"),
        ("7. Hunter Shield + Nöbetçi (Model C)", "hunter_shield"),
    ]
    
    # -------------------------------------------------------------------------
    # 1. 5 YILLIK TAM DÖNEM SONUÇLARI (2021 - 2026)
    # -------------------------------------------------------------------------
    sonuclar_5y = []
    yillik_detay_tablosu = []
    
    for baslik, kod in modeller:
        res = sim.simule_et(kod)
        sonuclar_5y.append({
            "Model Adı": baslik,
            "Son Bakiye (TL)": f"{res['son_bakiye_tl']:,.2f} TL",
            "Getiri (%)": f"%{res['toplam_getiri_pct']:,.1f}",
            "CAGR (%)": f"%{res['cagr_pct']:.2f}",
            "Max DD (%)": f"%{res['max_drawdown_pct']:.2f}",
            "Calmar": f"{res['calmar_orani']:.2f}",
            "Sharpe": f"{res['sharpe_orani']:.2f}",
            "Max TL Kayıp": f"-{res['max_tl_kayip']:,.0f} TL",
            "Worst Year": res['worst_year'],
            "T0 Core (%)": f"%{res['t0_sure_pct']:.1f}",
            "İşlem": f"{res['toplam_islem']}",
            "500K Günü": res['gun_500k'],
            "700K Günü": res['gun_700k'],
        })
        
        yrow = {"Model Adı": baslik}
        for y, r in res["yillik_getiriler"].items():
            yrow[str(y)] = f"%{r:.1f}"
        yillik_detay_tablosu.append(yrow)
        
    print("\n" + "=" * 145)
    print("                           1. TABLO: 5 YILLIK GENEL PERFORMANS VE RİSK TABLOSU (2021 - 2026)")
    print("=" * 145)
    df_5y = pd.DataFrame(sonuclar_5y)
    print(df_5y.to_string(index=False))
    
    print("\n" + "=" * 145)
    print("                           2. TABLO: YILLARA GÖRE BÜYÜME VE GETİRİ KIRILIMI (YIL BAZINDA)")
    print("=" * 145)
    df_yil = pd.DataFrame(yillik_detay_tablosu)
    print(df_yil.to_string(index=False))
    
    # -------------------------------------------------------------------------
    # 2. DÖNEMSEL DERİNLEMESİNE TESTLER (2021-23, 2024-25, 2026 YTD)
    # -------------------------------------------------------------------------
    donemler = [
        ("2021–2023 (Ralli ve Enflasyonist Büyüme Dönemi)", "2021-11-20", "2023-12-31"),
        ("2024–2025 (Yüksek Faiz ve Sıkılaşma Dönemi)", "2024-01-02", "2025-12-31"),
        ("2026 YTD (Kör OOS & Güncel Dönem)", "2026-01-02", "2026-08-19"),
    ]
    
    for d_baslik, t_bas, t_bit in donemler:
        print("\n" + "=" * 145)
        print(f"               DÖNEMSEL ANALİZ: {d_baslik} ({t_bas} -> {t_bit})")
        print("=" * 145)
        d_sonuclar = []
        for baslik, kod in modeller:
            res_d = sim.simule_et(kod, baslangic_tarihi=t_bas, bitis_tarihi=t_bit)
            d_sonuclar.append({
                "Model Adı": baslik,
                "Son Bakiye (100K ->)": f"{res_d['son_bakiye_tl']:,.2f} TL",
                "Getiri (%)": f"%{res_d['toplam_getiri_pct']:.2f}",
                "CAGR (%)": f"%{res_d['cagr_pct']:.2f}",
                "Max DD (%)": f"%{res_d['max_drawdown_pct']:.2f}",
                "Calmar": f"{res_d['calmar_orani']:.2f}",
                "Sharpe": f"{res_d['sharpe_orani']:.2f}",
                "T0 Core (%)": f"%{res_d['t0_sure_pct']:.1f}",
                "İşlem": f"{res_d['toplam_islem']}",
            })
        print(pd.DataFrame(d_sonuclar).to_string(index=False))
        
    print("\n" + "=" * 145)
    print("DENEY TAMAMLANDI.")

if __name__ == "__main__":
    main()
