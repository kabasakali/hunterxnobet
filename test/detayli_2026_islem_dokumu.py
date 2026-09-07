"""
detayli_2026_islem_dokumu.py
============================
2026 Yılı (YTD) Bütün İşlemlerin, Giriş-Çıkış Tarihlerinin,
Kâr/Zarar ve Karar Nedenlerinin Adli Dökümü.
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np

from harmony_v2_2_live_production import HarmonyV22LiveProduction

def main():
    live_eng = HarmonyV22LiveProduction(baslangic_sermayesi=100_000.0)
    res = live_eng.simule_et_production(baslangic_tarihi="2026-01-02", bitis_tarihi="2026-08-26")
    
    tarih_dilimi = [pd.to_datetime(k["tarih"]) for k in res["gunluk_kayitlar"]]
    b_idx = next(i for i, t in enumerate(live_eng.tarihler) if t == tarih_dilimi[0])
    s_idx = next(i for i, t in enumerate(live_eng.tarihler) if t == tarih_dilimi[-1])
    
    # 2026 gün gün fon pozisyonlarını çıkar
    tarihler_2026 = live_eng.tarihler[b_idx : s_idx + 1]
    
    pozisyonlar = []
    
    cur_fon = None
    cur_motor = None
    giris_tarih = None
    giris_bakiye = None
    giris_idx = 0
    giris_nedeni = ""
    
    for idx, dt in enumerate(tarihler_2026):
        k = res["gunluk_kayitlar"][idx]
        bakiye = k["bakiye"]
        motor = k["aktif_motor"]
        gate = k["gate_state"]
        dd = k["cur_dd"]
        
        # O günkü aktif fon kodu
        if motor == "MOMENTUM":
            fon = live_eng.sfb_aktif_fon.get(dt, "PPZ")
        elif motor == "HUNTER":
            fon = live_eng.h6_aktif_fon.get(dt, "PPZ")
        else: # DD_AWARE
            fon = "PPZ" # Savunma / Para Piyasası
            
        if cur_fon is None:
            cur_fon = fon
            cur_motor = motor
            giris_tarih = dt
            giris_bakiye = 100_000.0
            giris_idx = idx
            giris_nedeni = f"Yılbaşı Başlangıcı ({motor} Motoru)"
        elif fon != cur_fon or motor != cur_motor:
            # Pozisyon Kapanışı
            cikis_tarih = dt
            cikis_bakiye = bakiye
            kar_tl = cikis_bakiye - giris_bakiye
            kar_pct = (kar_tl / giris_bakiye) * 100.0
            tutma_gunu = (cikis_tarih - giris_tarih).days
            seans_sayisi = idx - giris_idx
            
            # Çıkış nedeni analizi
            if cur_motor != motor and motor == "DD_AWARE":
                cikis_nedeni = f"Savunma Freni (DD: %{dd*100:.1f} / Risk Gate: {gate})"
            elif cur_motor != motor and motor == "MOMENTUM":
                cikis_nedeni = "Serbest Fon Ralli Patlaması (SFB Momentum > Hunter)"
            elif cur_motor != motor and motor == "HUNTER":
                cikis_nedeni = "Normal Rejime Dönüş (Hunter Motoru)"
            else:
                cikis_nedeni = f"Lider Rotasyonu (Yeni Şampiyon: {fon})"
                
            pozisyonlar.append({
                "Fon Kodu": cur_fon,
                "Motor": cur_motor,
                "Giriş Tarihi": giris_tarih.strftime("%Y-%m-%d"),
                "Çıkış Tarihi": cikis_tarih.strftime("%Y-%m-%d"),
                "Süre": f"{seans_sayisi} Seans ({tutma_gunu} Gün)",
                "Giriş Bakiye": f"{giris_bakiye:,.2f} TL",
                "Çıkış Bakiye": f"{cikis_bakiye:,.2f} TL",
                "Net Kâr/Zarar (TL)": f"{kar_tl:+,.2f} TL",
                "Getiri (%)": f"%{kar_pct:+.2f}",
                "Giriş Nedeni": giris_nedeni,
                "Çıkış Nedeni": cikis_nedeni
            })
            
            cur_fon = fon
            cur_motor = motor
            giris_tarih = dt
            giris_bakiye = cikis_bakiye
            giris_idx = idx
            giris_nedeni = cikis_nedeni
            
    # Son açık pozisyon
    son_bakiye = res["gunluk_kayitlar"][-1]["bakiye"]
    kar_tl_son = son_bakiye - giris_bakiye
    kar_pct_son = (kar_tl_son / giris_bakiye) * 100.0
    seans_son = len(tarihler_2026) - giris_idx
    tutma_son = (tarihler_2026[-1] - giris_tarih).days
    
    pozisyonlar.append({
        "Fon Kodu": cur_fon,
        "Motor": cur_motor,
        "Giriş Tarihi": giris_tarih.strftime("%Y-%m-%d"),
        "Çıkış Tarihi": "HÂLÂ ELDE (2026-08-26)",
        "Süre": f"{seans_son} Seans ({tutma_son} Gün)",
        "Giriş Bakiye": f"{giris_bakiye:,.2f} TL",
        "Çıkış Bakiye": f"{son_bakiye:,.2f} TL",
        "Net Kâr/Zarar (TL)": f"{kar_tl_son:+,.2f} TL",
        "Getiri (%)": f"%{kar_pct_son:+.2f}",
        "Giriş Nedeni": giris_nedeni,
        "Çıkış Nedeni": "Açık Pozisyon (Bugünkü Lider)"
    })
    
    df_poz = pd.DataFrame(pozisyonlar)
    
    print("=" * 160)
    print("                    2026 YILI YILBAŞINDAN BUGÜNE (YTD) DETAYLI İŞLEM, POZİSYON VE KÂR/ZARAR DÖKÜMÜ")
    print("                                      (02 Ocak 2026 -> 26 Ağustos 2026)")
    print("=" * 160)
    
    for idx, p in df_poz.iterrows():
        print(f"\nİşlem #{idx+1}: [{p['Fon Kodu']}] ({p['Motor']} Motoru)")
        print(f"   * Giriş Tarihi   : {p['Giriş Tarihi']} | Bakiye: {p['Giriş Bakiye']}")
        print(f"   * Çıkış Tarihi   : {p['Çıkış Tarihi']} | Bakiye: {p['Çıkış Bakiye']}")
        print(f"   * Elde Tutma     : {p['Süre']}")
        print(f"   * Net Kâr / Zarar: {p['Net Kâr/Zarar (TL)']} ({p['Getiri (%)']})")
        print(f"   * Neden Girdi    : {p['Giriş Nedeni']}")
        print(f"   * Neden Çıktı    : {p['Çıkış Nedeni']}")
        print("-" * 120)
        
    print("\n" + "=" * 160)
    print("ÖZET TABLO:")
    print(df_poz[["Fon Kodu", "Motor", "Giriş Tarihi", "Çıkış Tarihi", "Giriş Bakiye", "Çıkış Bakiye", "Net Kâr/Zarar (TL)", "Getiri (%)"]].to_string(index=False))
    print("=" * 160)

if __name__ == "__main__":
    main()
