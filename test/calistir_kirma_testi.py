import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

"""
calistir_kirma_testi.py
=======================
HARMONY v2.2 (Altın Denge) 4 Boyutlu Kırma ve Dayanıklılık Raporu.
"""

import os
import sys
import pandas as pd
import numpy as np

from v2_2_adversarial_break_test import HarmonyV22AdversarialAuditor

def main():
    print("=" * 160)
    print("        HARMONY v2.2 (ALTIN DENGE) 4 BOYUTLU ADVERSARIAL KIRMA VE STRES TESTI RAPORU")
    print("=" * 160)
    print(">> 101 Nokta Kayma Sweep | 30 Pencere Rolling Start Sweep | 25 Nokta Perturbation | Bilesen Ablation Analizi")
    print("=" * 160)
    
    auditor = HarmonyV22AdversarialAuditor()
    
    # -------------------------------------------------------------------------
    # 1. TEST: KAYMA TARAMASI (%0.00 -> %1.00, 101 NOKTA)
    # -------------------------------------------------------------------------
    print("\n" + "=" * 160)
    print("        1. TEST: %0.00 -> %1.00 KAYMA SWEEP ANALIZI (101 ADIMDA MONOTONLUK VE ANOMALI DENETIMI)")
    print("=" * 160)
    res_k = auditor.kayma_sweep_testi()
    df_k = res_k["df_kayma"]
    
    print(f">> Toplam Test Noktası: 101 Adet (%0.00'dan %1.00'e kadar %0.01 adimla)")
    print(f">> Tespit Edilen Sıçrama / Anomali Sayısı: {res_k['anomali_sayisi']} Adet")
    print(f">> Monotonluk Sağlamlık Oranı: %{res_k['monotonluk_orani']:.1f}")
    
    ozet_kayma = [
        {"Kayma (%)": "%0.00 (Sifir)", "Bakiye (100K ->)": f"{res_k['bakiye_0pct']:,.0f} TL", "CAGR": f"%{df_k.iloc[0]['cagr_pct']:.1f}", "Max DD": f"%{df_k.iloc[0]['max_drawdown_pct']:.2f}", "Calmar": f"{df_k.iloc[0]['calmar_orani']:.2f}"},
        {"Kayma (%)": "%0.05 (Normal)", "Bakiye (100K ->)": f"{res_k['bakiye_005pct']:,.0f} TL", "CAGR": f"%{df_k.iloc[5]['cagr_pct']:.1f}", "Max DD": f"%{df_k.iloc[5]['max_drawdown_pct']:.2f}", "Calmar": f"{df_k.iloc[5]['calmar_orani']:.2f}"},
        {"Kayma (%)": "%0.10 (Yuksek)", "Bakiye (100K ->)": f"{res_k['bakiye_010pct']:,.0f} TL", "CAGR": f"%{df_k.iloc[10]['cagr_pct']:.1f}", "Max DD": f"%{df_k.iloc[10]['max_drawdown_pct']:.2f}", "Calmar": f"{df_k.iloc[10]['calmar_orani']:.2f}"},
        {"Kayma (%)": "%0.20 (Agir)", "Bakiye (100K ->)": f"{res_k['bakiye_020pct']:,.0f} TL", "CAGR": f"%{df_k.iloc[20]['cagr_pct']:.1f}", "Max DD": f"%{df_k.iloc[20]['max_drawdown_pct']:.2f}", "Calmar": f"{df_k.iloc[20]['calmar_orani']:.2f}"},
        {"Kayma (%)": "%0.50 (Asiri)", "Bakiye (100K ->)": f"{res_k['bakiye_050pct']:,.0f} TL", "CAGR": f"%{df_k.iloc[50]['cagr_pct']:.1f}", "Max DD": f"%{df_k.iloc[50]['max_drawdown_pct']:.2f}", "Calmar": f"{df_k.iloc[50]['calmar_orani']:.2f}"},
        {"Kayma (%)": "%1.00 (Ekstrem)", "Bakiye (100K ->)": f"{res_k['bakiye_100pct']:,.0f} TL", "CAGR": f"%{df_k.iloc[100]['cagr_pct']:.1f}", "Max DD": f"%{df_k.iloc[100]['max_drawdown_pct']:.2f}", "Calmar": f"{df_k.iloc[100]['calmar_orani']:.2f}"},
    ]
    print(pd.DataFrame(ozet_kayma).to_string(index=False))
    
    # -------------------------------------------------------------------------
    # 2. TEST: BAŞLANGIÇ TARİHİ TARAMASI (ROLLING START DATE SWEEP)
    # -------------------------------------------------------------------------
    print("\n" + "=" * 160)
    print("        2. TEST: FARKLI BAŞLANGIÇ TARİHLERİ TARAMASI (ROLLING START DATE PATH-DEPENDENCY)")
    print("=" * 160)
    res_b = auditor.baslangic_tarihi_sweep_testi(adim_gun=20)
    df_p = res_b["df_pencereler"]
    
    print(f">> Toplam Test Edilen Farklı Başlangıç Penceresi: {res_b['toplam_pencere']} Adet")
    print(f">> Medyan CAGR: %{res_b['medyan_cagr']:.2f} | Ortalama CAGR: %{res_b['ortalama_cagr']:.2f}")
    print(f">> En Kötü (Worst-Case) CAGR: %{res_b['min_cagr']:.2f} | En Yüksek CAGR: %{res_b['max_cagr']:.2f}")
    print(f">> Medyan Max DD: %{res_b['medyan_max_dd']:.2f} | En Kötü Max DD: %{res_b['en_kotu_max_dd']:.2f}")
    print(f">> Medyan Calmar: {res_b['medyan_calmar']:.2f} | Minimum Calmar: {res_b['min_calmar']:.2f}")
    
    print("\nİlk 10 ve Son 5 Başlangıç Tarihi Pencere Özeti:")
    df_p_view = pd.concat([df_p.head(6), df_p.tail(4)])
    print(df_p_view[["baslangic_tarihi", "islem_gunu_sayisi", "son_bakiye_tl", "cagr_pct", "max_drawdown_pct", "calmar_orani"]].to_string(index=False))
    
    # -------------------------------------------------------------------------
    # 3. TEST: PARAMETRE HASSASİYET MATRİSİ (PERTURBATION SURFACE)
    # -------------------------------------------------------------------------
    print("\n" + "=" * 160)
    print("        3. TEST: PARAMETRE PERTURBASYON YÜZEYİ (5x5 = 25 KOMBİNASYONDA SENSITIVITY ANALİZİ)")
    print("=" * 160)
    res_p = auditor.parametre_perturbation_testi()
    df_pert = res_p["df_perturbation"]
    
    print(f">> Ortalama 5 Yıllık Bakiye: {res_p['ortalama_bakiye']:,.2f} TL (Medyan: {res_p['medyan_bakiye']:,.2f} TL)")
    print(f">> En Kötü Parametre Bakiyesi: {res_p['min_bakiye']:,.2f} TL | En Yüksek: {res_p['max_bakiye']:,.2f} TL")
    print(f">> Ortalama CAGR: %{res_p['ortalama_cagr']:.2f} (Std Sapma: %{res_p['std_cagr']:.2f})")
    print(f">> Ortalama Max DD: %{res_p['ortalama_max_dd']:.2f} | En Kötü Max DD: %{res_p['en_kotu_max_dd']:.2f}")
    print(f">> Ortalama Calmar: {res_p['ortalama_calmar']:.2f} | Minimum Calmar: {res_p['min_calmar']:.2f}")
    
    print("\nParametre Hassasiyet Matrisi (25 Kombinasyon):")
    print(df_pert[["DD_Giris (%)", "DD_Cikis (%)", "Deadband", "Son Bakiye", "CAGR (%)", "Max DD (%)", "Calmar"]].to_string(index=False))
    
    # -------------------------------------------------------------------------
    # 4. TEST: ABLATION TESTİ (FON NÖBETÇİSİ ALFA İZOLASYONU)
    # -------------------------------------------------------------------------
    print("\n" + "=" * 160)
    print("        4. TEST: ABLATION TESTI (FON NOBETCISI VE BILESEN ALFA IZOLASYON ANALIZI)")
    print("=" * 160)
    res_a = auditor.ablation_testi()
    
    ablation_tablosu = [
        {
            "Konfigurasyon / Model": "1. HARMONY v2.2 Tam Model (Tum Bilesenler Aktif)",
            "Son Bakiye": f"{res_a['tam_model']['bakiye']:,.2f} TL",
            "CAGR (%)": f"%{res_a['tam_model']['cagr']:.2f}",
            "Max DD (%)": f"%{res_a['tam_model']['mdd']:.2f}",
            "Calmar": f"{res_a['tam_model']['calmar']:.2f}",
            "Fark / Katki": "TAM MOTOR (Benchmark)",
        },
        {
            "Konfigurasyon / Model": "2. Nöbetçi Devre Dışı (Yalnızca Hunter + Savunma)",
            "Son Bakiye": f"{res_a['no_nobetci']['bakiye']:,.2f} TL",
            "CAGR (%)": f"%{res_a['no_nobetci']['cagr']:.2f}",
            "Max DD (%)": f"%{res_a['no_nobetci']['mdd']:.2f}",
            "Calmar": f"{res_a['no_nobetci']['calmar']:.2f}",
            "Fark / Katki": f"-{res_a['nobetci_net_tl_alfa']:,.0f} TL (-%{res_a['nobetci_net_cagr_alfa']:.1f} CAGR)",
        },
        {
            "Konfigurasyon / Model": "3. Hunter Devre Dışı (Yalnızca Nöbetçi + Savunma)",
            "Son Bakiye": f"{res_a['no_hunter']['bakiye']:,.2f} TL",
            "CAGR (%)": f"%{res_a['no_hunter']['cagr']:.2f}",
            "Max DD (%)": f"%{res_a['no_hunter']['mdd']:.2f}",
            "Calmar": f"{res_a['no_hunter']['calmar']:.2f}",
            "Fark / Katki": f"-{res_a['hunter_net_tl_katki']:,.0f} TL",
        },
        {
            "Konfigurasyon / Model": "4. Savunma (DD-Aware) Devre Dışı (Sadece Ralli)",
            "Son Bakiye": f"{res_a['no_savunma']['bakiye']:,.2f} TL",
            "CAGR (%)": f"%{res_a['no_savunma']['cagr']:.2f}",
            "Max DD (%)": f"%{res_a['no_savunma']['mdd']:.2f}",
            "Calmar": f"{res_a['no_savunma']['calmar']:.2f}",
            "Fark / Katki": f"+%{res_a['savunma_mdd_iyilestirme']:.2f} DD Korumasi Sagladi",
        },
    ]
    print(pd.DataFrame(ablation_tablosu).to_string(index=False))
    
    print("\n" + "=" * 160)
    print(">> ABLATION NET ÇIKARIMI:")
    print(f"   * Fon Nöbetçisi'nin sisteme net net nakit katkısı: +{res_a['nobetci_net_tl_alfa']:,.2f} TL (+%{res_a['nobetci_net_cagr_alfa']:.2f} CAGR)!")
    print(f"   * DD-Aware Savunma motorunun portföy çekilmesine sağladığı net kalkan: +%{res_a['savunma_mdd_iyilestirme']:.2f} Max DD iyileştirmesi!")
    print("=" * 160)

if __name__ == "__main__":
    main()
