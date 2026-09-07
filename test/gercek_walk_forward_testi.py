"""
gercek_walk_forward_testi.py
============================
GERÇEK WALK-FORWARD TESTİ
- Parametreler 2023-12-31'de dondurulmuş sayılır
- 2024 ve 2025 ve 2026 TAM BAĞIMSIZ test edilir
- Ama dürüst uyarı: mevcut parametreler 2024-2026 görülerek ayarlandı;
  bu test "en azından ne kadar kötü overfit var?" sorusunu ölçer
- Karşılaştırma: Basit momentum (parametresiz) vs HARMONY v2.2
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np

from harmony_v2_2_live_production import HarmonyV22LiveProduction

def main():
    print("=" * 100)
    print("  GERÇEK WALK-FORWARD OVERFİT DENETİMİ")
    print("  Soru: Parametreler 2024-2026'yı görerek ayarlandıysa,")
    print("  ne kadar overfit var? Basit momentum ondan iyi olabilir mi?")
    print("=" * 100)

    eng = HarmonyV22LiveProduction()
    fiyat_df = eng.golden.base_motor.base_motor.fiyat_df
    r20_df = eng.r20_df
    tarihler = eng.tarihler

    # -----------------------------------------------------------------------
    # MODEL A: HARMONY v2.2 (Tüm Katmanlar / Parametreler 2026 dahil ayarlandı)
    # -----------------------------------------------------------------------
    dilimler = [
        ("In-Sample         (2021-11 -> 2023-12)", "2021-11-22", "2023-12-31"),
        ("Test Yıl 1 / 2024 (BAĞIMSIZ DÖNEM)   ", "2024-01-02", "2024-12-31"),
        ("Test Yıl 2 / 2025 (BAĞIMSIZ DÖNEM)   ", "2025-01-02", "2025-12-31"),
        ("Test Yıl 3 / 2026 (BAĞIMSIZ DÖNEM)   ", "2026-01-02", "2026-08-27"),
    ]

    print("\n[A] HARMONY v2.2 (use_cutoff_lag=True, tüm katmanlar):")
    print("-" * 100)
    harmony_sonuclar = []
    for ad, t_b, t_s in dilimler:
        r = eng.simule_et_production(use_cutoff_lag=True, baslangic_tarihi=t_b, bitis_tarihi=t_s)
        harmony_sonuclar.append(r['toplam_getiri_pct'])
        print(f"  {ad} | Getiri: %{r['toplam_getiri_pct']:>7.2f} | MaxDD: %{r['max_drawdown_pct']:>6.2f} | Calmar: {r['calmar_orani']:>6.2f} | Bakiye: {r['son_bakiye_tl']:>12,.0f} TL")

    # -----------------------------------------------------------------------
    # MODEL B: BASIT MOMENTUM (0 parametre tuning - sadece en yüksek R20 fonu tut)
    # Overfitting üst sınırını ölçmek için: eğer bu da iyi çalışıyorsa
    # alpha, TEFAS piyasasının kendi yapısından geliyor demektir.
    # -----------------------------------------------------------------------
    print("\n[B] BASİT MOMENTUM (Sıfır Parametre / Sadece En Yüksek 20G Fonu Tut):")
    print("-" * 100)

    def basit_momentum_test(t_b, t_s, sermaye=100_000.0, kayma=0.0005):
        t_b_dt = pd.to_datetime(t_b)
        t_s_dt = pd.to_datetime(t_s)
        dilim = [(t, i) for i, t in enumerate(tarihler) if t_b_dt <= t <= t_s_dt]
        if len(dilim) < 5:
            return None

        bakiye = sermaye
        zirve = bakiye
        mdd = 0.0
        aktif = None

        for dt, _ in dilim:
            # Bir önceki günün R20'sine bak (look-ahead yok)
            prev_dt = tarihler[tarihler.index(dt) - 1] if tarihler.index(dt) > 0 else dt
            if prev_dt not in r20_df.index:
                continue
            row = r20_df.loc[prev_dt].dropna()
            if row.empty:
                continue
            lider = row.idxmax()

            if lider != aktif:
                bakiye *= (1 - kayma)
                aktif = lider

            if aktif in fiyat_df.columns and dt in fiyat_df.index:
                gun_ret = fiyat_df.at[dt, aktif] / fiyat_df.shift(1).at[dt, aktif] - 1 if dt in fiyat_df.index else 0.0
                if not np.isnan(gun_ret):
                    bakiye *= (1 + gun_ret)

            if bakiye > zirve:
                zirve = bakiye
            dd = (zirve - bakiye) / zirve * 100
            if dd > mdd:
                mdd = dd

        getiri = (bakiye - sermaye) / sermaye * 100
        n = len(dilim)
        cagr = ((bakiye / sermaye) ** (252 / n) - 1) * 100
        calmar = cagr / mdd if mdd > 0.001 else 0
        return {"bakiye": bakiye, "getiri": getiri, "mdd": -mdd, "cagr": cagr, "calmar": calmar}

    for ad, t_b, t_s in dilimler:
        r = basit_momentum_test(t_b, t_s)
        if r:
            print(f"  {ad} | Getiri: %{r['getiri']:>7.2f} | MaxDD: %{r['mdd']:>6.2f} | Calmar: {r['calmar']:>6.2f} | Bakiye: {r['bakiye']:>12,.0f} TL")

    # -----------------------------------------------------------------------
    # YORUM
    # -----------------------------------------------------------------------
    print("\n" + "=" * 100)
    print("ADLİ YORUM:")
    print("  - Eğer Basit Momentum da HARMONY'ye yakın ise: alpha TEFAS piyasasının yapısından geliyor,")
    print("    HARMONY'nin karmaşık katmanları gereksiz veya overfit olabilir.")
    print("  - Eğer HARMONY in-sample'da çok yüksek, test yıllarında belirgin düşüyorsa:")
    print("    katmanlı parametre seçimi overfit imzası taşıyor demektir.")
    print("  - Eğer test yılları da in-sample'a yakınsa: ya piyasa çok momentum-dostu ya da overfit az.")
    print("=" * 100)

if __name__ == "__main__":
    main()
