"""
incele_sos_fonu.py
==================
SOS Fonunun Son 5-10 Günlük Durumu, Fiyatı, Getirisi ve Model Değerlendirmesi.
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np

from harmony_v2_2_live_production import HarmonyV22LiveProduction

def main():
    live_eng = HarmonyV22LiveProduction()
    fiyat_df = live_eng.golden.base_motor.base_motor.fiyat_df
    r20_df = live_eng.r20_df
    r63_df = live_eng.golden.base_motor.base_motor.r63_df
    skor_df = live_eng.golden.base_motor.base_motor.skor_df
    tarihler = live_eng.tarihler
    
    fon = "SOS"
    
    print("=" * 90)
    print(f"               SOS FONU ADLİ VE TEKNİK ANALİZ RAPORU")
    print("=" * 90)
    
    if fon not in fiyat_df.columns:
        print(f"[UYARI] {fon} fonu 156 fonluk veri setinde doğrudan bulunamadı.")
        # Benzer serbest fonları ara
        benzerler = [c for c in fiyat_df.columns if "SO" in c or "S" in c][:10]
        print(f"Mevcut benzer serbest fonlar: {benzerler}")
        return
        
    seri = fiyat_df[fon].dropna()
    son_10_gun = seri.tail(10)
    
    dt_last = tarihler[-1]
    son_fiyat = seri.iloc[-1]
    bes_gun_onceki_fiyat = seri.iloc[-5] if len(seri) >= 5 else seri.iloc[0]
    bes_gunluk_getiri = ((son_fiyat - bes_gun_onceki_fiyat) / bes_gun_onceki_fiyat) * 100.0
    
    r20 = r20_df.at[dt_last, fon] if fon in r20_df.columns and pd.notna(r20_df.at[dt_last, fon]) else 0.0
    r63 = r63_df.at[dt_last, fon] if fon in r63_df.columns and pd.notna(r63_df.at[dt_last, fon]) else 0.0
    skor = skor_df.at[dt_last, fon] if fon in skor_df.columns and pd.notna(skor_df.at[dt_last, fon]) else 0.0
    
    # Tüm fonlar içindeki sırası
    tum_skorlar = skor_df.loc[dt_last].dropna().sort_values(ascending=False)
    sira = list(tum_skorlar.index).index(fon) + 1 if fon in tum_skorlar.index else "N/A"
    toplam_fon = len(tum_skorlar)
    
    # Nöbetçi Motorunun Güncel Lideri
    sfb_lider = live_eng.sfb_aktif_fon.get(dt_last, "PPZ")
    
    print(f">> Fon Kodu                   : {fon}")
    print(f">> Son TEFAS Tarihi           : {dt_last.strftime('%Y-%m-%d')}")
    print(f">> Güncel Birim Fiyatı (NAV)  : {son_fiyat:,.6f} TL")
    print(f">> 5 Gün Önceki Fiyat         : {bes_gun_onceki_fiyat:,.6f} TL")
    print(f">> Son 5 Günlük Net Getiri    : %{bes_gunluk_getiri:+.2f}")
    print(f">> 20 Günlük Momentum (R20)   : %{r20*100:+.2f}")
    print(f">> 63 Günlük Momentum (R63)   : %{r63*100:+.2f}")
    print(f">> TEFAS Evrenindeki Sırası   : {sira}. sıra / {toplam_fon} Fon Arasında")
    print(f">> Fon Nöbetçisi Güncel Lideri: {sfb_lider}")
    print("-" * 90)
    print("SON 10 İŞLEM GÜNÜ FİYAT GEÇMİŞİ:")
    df_son10 = pd.DataFrame({
        "Tarih": [t.strftime("%Y-%m-%d") for t in son_10_gun.index],
        "Birim Fiyat (TL)": [f"{p:,.6f} TL" for p in son_10_gun.values],
        "Günlük Değişim (%)": [f"%{((son_10_gun.values[i] - son_10_gun.values[i-1])/son_10_gun.values[i-1]*100):+.2f}" if i > 0 else "%0.00" for i in range(len(son_10_gun))]
    })
    print(df_son10.to_string(index=False))
    print("=" * 90)

if __name__ == "__main__":
    main()
