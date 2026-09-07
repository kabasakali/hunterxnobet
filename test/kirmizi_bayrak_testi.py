"""
kirmizi_bayrak_testi.py
=======================
1. use_cutoff_lag=True vs False performans farkı
2. CSV tazeliği ve look-ahead teşhisi
3. Gerçek canlı sinyal ne kadar gecikmeyle üretiliyor?
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np
from harmony_v2_2_live_production import HarmonyV22LiveProduction

def main():
    print("=" * 90)
    print("       KIRMIZI BAYRAK TEKNİK DENETİM TESTİ")
    print("=" * 90)

    # -----------------------------------------------------------------------
    # TEST 1: use_cutoff_lag=False (Mevcut) vs True (Gerçekçi)
    # -----------------------------------------------------------------------
    print("\n[TEST 1] LOOK-AHEAD BIAS: use_cutoff_lag=False vs True (5 Yıl + 2026 OOS)")
    print("-" * 90)

    configs = [
        ("LAG=False (Mevcut Kod / Look-ahead ihtimalli)", False),
        ("LAG=True  (Gerçekçi / 1 Gün Gecikme)         ", True),
    ]

    for label, lag in configs:
        eng = HarmonyV22LiveProduction()
        r5y = eng.simule_et_production(use_cutoff_lag=lag)
        r26 = eng.simule_et_production(use_cutoff_lag=lag, baslangic_tarihi="2026-01-02", bitis_tarihi="2026-08-26")
        print(f"  {label}")
        print(f"    5Y  -> Bakiye: {r5y['son_bakiye_tl']:>12,.0f} TL | CAGR: %{r5y['cagr_pct']:>6.2f} | MaxDD: %{r5y['max_drawdown_pct']:>6.2f} | Calmar: {r5y['calmar_orani']:>6.2f}")
        print(f"    2026-> Bakiye: {r26['son_bakiye_tl']:>12,.0f} TL | Getiri: %{r26['toplam_getiri_pct']:>6.2f} | MaxDD: %{r26['max_drawdown_pct']:>6.2f} | Calmar: {r26['calmar_orani']:>6.2f}")
    
    # -----------------------------------------------------------------------
    # TEST 2: CSV Tazeliği
    # -----------------------------------------------------------------------
    print("\n[TEST 2] CSV VERİ TAZELIĞI VE CANLI KULLANIM UYUMU")
    print("-" * 90)
    csv_path = r"c:\Users\kabasakali\Desktop\calismalar\fonbot\serbest_fon_bot\csv\5_yil_pivot.csv"
    df = pd.read_csv(csv_path, index_col=0, parse_dates=True)
    son_veri = df.index[-1]
    bugun = pd.Timestamp.today()
    fark = (bugun - son_veri).days
    print(f"  CSV Son Veri Tarihi : {son_veri.strftime('%Y-%m-%d')}")
    print(f"  Bugün               : {bugun.strftime('%Y-%m-%d')}")
    print(f"  Veri Gecikmesi      : {fark} gün")
    if fark > 3:
        print(f"  [UYARI] Veri {fark} gün eski! Canli emir ureteci GUNCEL TEFAS verisiyle degil,")
        print(f"          {son_veri.strftime('%d.%m.%Y')} kapanish fiyatlariyla karar uretecek.")
        print(f"          Cozum: CSV'nin her gece TEFAS'tan otomatik guncellenmesi gerekiyor.")
    else:
        print(f"  [OK] Veri yeterince taze.")

    # -----------------------------------------------------------------------
    # TEST 3: Parametre Sayısı Özeti
    # -----------------------------------------------------------------------
    print("\n[TEST 3] PARAMETRE SAYISI VE OVERFITTING RİSKİ")
    print("-" * 90)
    parametreler = [
        ("harmony_v1_motor.py (Hunter v6)", ["r20_window=20", "r40_window=40", "r63_window=63", "min_hold=3", "panic_stop=0.055", "top_n=5", "siki_entry=0.03"]),
        ("meta_allocator_motor.py (Meta)", ["ralli_r20=0.065", "dd_stop=0.048", "breadth_ralli=0.52", "breadth_normal=0.30", "spread_nobetci=0.025", "mb_nobetci=0.52"]),
        ("harmony_v2_2_golden.py (Golden)", ["entry_dd=0.040", "exit_dd=0.028", "agile_lock=3", "turbo_alpha=0.025", "breadth_caution=0.35"]),
        ("harmony_v2_2_live_production.py (Live)", ["caution_breadth=0.32", "caution_dd=0.030", "defensive_dd=0.040", "ks_dd=0.045", "caution_ratio=0.85"]),
    ]
    toplam = 0
    for kat, params in parametreler:
        print(f"  {kat}: {len(params)} parametre")
        toplam += len(params)
    print(f"  Toplam Dokunulan Parametre Sayısı: {toplam}")
    print(f"  Veri Penceresi (Aynı 2021-2026): 5 yıl = ~1.257 işlem günü")
    print(f"  Parametre/Veri Oranı: {toplam}/{1257} = {toplam/1257:.4f}")
    print(f"  [TEŞHIS] Oran düşük görünse de katmanlı seçim aynı pencereye bakılarak yapıldıysa")
    print(f"           walk-forward dışı in-sample overfit riski mevcuttur.")

    print("=" * 90)

if __name__ == "__main__":
    main()
