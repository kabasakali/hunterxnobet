"""
kapanan_fon_v2.py
==================
CSV'deki 5 yıllık veriden kapalı fonları tespit et.
Yöntem: CSV'de 2021'de veri olan ama 2024+ sonrası tamamen
NaN olan fonlar muhtemelen kapatılmış/birleştirilmiş.
Bu, TEFAS API limitini aşan güvenilir bir yöntem.
"""

import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd

CSV_PATH = r"c:\Users\kabasakali\Desktop\calismalar\fonbot\serbest_fon_bot\csv\5_yil_pivot.csv"

def main():
    print("=" * 80)
    print("  KAPANAN FON SURVİVORSHİP BİAS TESTİ v2")
    print("  Yontem: CSV icerisinde erken veri var ama sonradan tamamen kaybolan fonlar")
    print("=" * 80)

    df = pd.read_csv(CSV_PATH, index_col=0, parse_dates=True)
    df = df.sort_index()

    baslangic = pd.Timestamp("2021-11-22")
    test_siniri = pd.Timestamp("2024-01-01")
    son_tarih = df.index[-1]

    # Fon evreni gruplandirma
    simbasla = df[:baslangic]
    erken_aktif = simbasla.dropna(axis=1, how='all').columns.tolist()

    test_donemi = df[test_siniri:]
    test_aktif = test_donemi.dropna(axis=1, how='all').columns.tolist()

    # Simülasyon baslarken mevcut ama 2024'te tamamen kaybolan fonlar
    kaybolan = [f for f in erken_aktif if f not in test_aktif]
    hala_aktif = [f for f in erken_aktif if f in test_aktif]

    print(f"\nSimulasyon baslangicinda mevcut fon sayisi: {len(erken_aktif)}")
    print(f"2024'e ulasan (hala aktif) fon sayisi    : {len(hala_aktif)}")
    print(f"2024 oncesi kaybolan fon sayisi           : {len(kaybolan)}")

    if kaybolan:
        print(f"\nKaybolan fonlar ve son veri tarihleri:")
        print(f"{'Fon':>5} | {'Son Veri':>12} | {'2021-11':<10} | Yorum")
        print("-" * 60)
        for fon in sorted(kaybolan):
            seri = df[fon].dropna()
            if len(seri) == 0:
                devam = "(hic veri yok)"
                ilk = "-"
            else:
                devam = seri.index[-1].strftime('%Y-%m-%d')
                ilk = seri.index[0].strftime('%Y-%m-%d')
            print(f"  {fon:>3} | {devam:>12} | {ilk:<10} | muhtemelen kapatildi/birlestirildi")
    else:
        print("\nKaybolan fon yok — tum erken donem fonlari 2024'e ulasti.")
        print("Klasik survivorship bias bu veri setinde sinirli gorunuyor.")

    print(f"\nSimulasyonda kullanilan fon evreni (sadece guncel CSV'dekiler):")
    print(f"  Toplam: {len(df.columns)} fon")
    print(f"  Simbaslangic doneminde aktif: {len(erken_aktif)}")
    print(f"  Hayatta kalan: {len(hala_aktif)} ({100*len(hala_aktif)/max(len(erken_aktif),1):.1f}%)")

    # Ek: Simbaslangicta kac fon seckinden cikabiliyor?
    sim_gun = df.loc[baslangic] if baslangic in df.index else df.iloc[df.index.searchsorted(baslangic)]
    kac_fon_vardı = sim_gun.notna().sum()
    print(f"  {baslangic.date()} tarihinde NaN olmayan (secime giren) fon: {kac_fon_vardı}")

    print("\n" + "=" * 80)
    print("ADLİ YORUM:")
    if len(kaybolan) == 0:
        print("  TEFAS degisken fon segmenti gorece stabil — tasfiye/birlesme az.")
        print("  Bu, diger piyasalardaki (hisse, kripto) survivorship bias'tan farkli.")
        print("  TEFAS fonlari genellikle kapatilmaz, baska fona devredilir (devir sonrasi")
        print("  fiyat serisi kopukluk gosterebilir, ama kod NaN ile bunu hallediyor).")
        print("  SONUC: Klasik survivorship bias bu sistemde buyuk bir sorun degil gibi.")
    else:
        oran = len(kaybolan)/len(erken_aktif)*100
        print(f"  {len(kaybolan)} fon ({oran:.1f}%) simbaslagicta mevcut ama 2024'e ulasamamis.")
        print(f"  Bu fonlar backtest'e dahil edilmis ama yalnizca varoldugu donem icin.")
        print(f"  Eger bu fonlar buyuk kayip gosterip kapandiysa, bias anlamli boyutta.")
    print("=" * 80)

if __name__ == "__main__":
    main()
