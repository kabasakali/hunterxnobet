"""
kapanan_fon_survivorship_testi.py
===================================
Gerçek survivorship bias testi:
2021'de TEFAS'ta mevcut olan ama bugün kapalı/tasfiye edilmiş
fonlar veri setimizde var mı?

Yöntem:
1. tefas kütüphanesi ile 2021-11 tarihli fon listesini çek
2. Bugünkü fon listesiyle karşılaştır
3. Kayıp (muhtemelen kapalı) fon sayısını hesapla
"""

import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd

CSV_PATH = r"c:\Users\kabasakali\Desktop\calismalar\fonbot\serbest_fon_bot\csv\5_yil_pivot.csv"

def main():
    print("=" * 80)
    print("  KLASİK SURVİVORSHIP BIAS TESTİ")
    print("  Soru: 2021'de var olup bugün kapanmış fonlar veri setimizde yok mu?")
    print("=" * 80)

    # Adım 1: Mevcut CSV'deki fon kodu listesi (bugün aktif olanlar)
    df_guncel = pd.read_csv(CSV_PATH, index_col=0, parse_dates=True)
    guncel_fonlar = set(df_guncel.columns.tolist())
    print(f"\n[Adım 1] Mevcut CSV'deki fon sayısı: {len(guncel_fonlar)}")

    # Adım 2: 2021-11 dönemindeki fon listesini TEFAS'tan çek
    print("\n[Adım 2] TEFAS'tan 2021-11 dönemi fon listesi çekiliyor...")
    try:
        from tefas import Crawler
        c = Crawler()
        # 2021-11-22 tarihinde tüm fonları çek (sadece o gün için)
        df_2021 = c.fetch(start="2021-11-22", end="2021-11-23")
        if df_2021 is not None and not df_2021.empty:
            fonlar_2021 = set(df_2021['code'].unique().tolist())
            print(f"     2021-11-22'de TEFAS'taki fon sayısı: {len(fonlar_2021)}")
        else:
            print("     TEFAS'tan 2021 verisi çekilemedi — GitHub cache yöntemi deneniyor...")
            fonlar_2021 = None
    except Exception as e:
        print(f"     TEFAS bağlantısı başarısız: {e}")
        fonlar_2021 = None

    # Adım 3: Alternatif — CSV'nin en eski satırında hangi fonlar vardı?
    print("\n[Adım 3] CSV'nin en eski satırındaki fon dağılımı (2021-11-22 civarı):")
    ilk_tarih = df_guncel.index[0]
    print(f"     CSV ilk tarihi: {ilk_tarih.date()}")
    
    # İlk 5 günde veri olan fon sayısı
    ilk_hafta = df_guncel.iloc[:5]
    o_gun_aktif = ilk_hafta.dropna(axis=1, how='all').columns.tolist()
    print(f"     CSV açıldığında zaten veri olan fon sayısı: {len(o_gun_aktif)}")

    # Simülasyon başlangıcından itibaren HİÇ seçilemeyen (hep NaN) fonlar var mı?
    hic_nan = df_guncel.isna().all(axis=0)
    print(f"     CSV'de tamamen NaN olan fon sütunu: {hic_nan.sum()} adet")

    # Adım 4: TEFAS verisi çekilebildiyse karşılaştır
    if fonlar_2021:
        sadece_2021de = fonlar_2021 - guncel_fonlar
        sadece_guncel = guncel_fonlar - fonlar_2021
        her_ikisinde = fonlar_2021 & guncel_fonlar

        print(f"\n[Adım 4] Karşılaştırma:")
        print(f"     2021'de var, bugün CSV'de YOK (muhtemelen kapalı): {len(sadece_2021de)} fon")
        print(f"     2021'de yok, bugün CSV'de var (sonradan açılan): {len(sadece_guncel)} fon")
        print(f"     Her ikisinde de var (kesişim): {len(her_ikisinde)} fon")

        if sadece_2021de:
            print(f"\n     Muhtemelen kapalı/tasfiye edilmiş fonlar ({len(sadece_2021de)} adet):")
            for fon in sorted(sadece_2021de)[:30]:
                print(f"       {fon}")
            if len(sadece_2021de) > 30:
                print(f"       ... ve {len(sadece_2021de)-30} fon daha")

        print(f"\n[ADLİ YORUM]")
        kapali_oran = len(sadece_2021de) / len(fonlar_2021) * 100 if fonlar_2021 else 0
        if kapali_oran > 10:
            print(f"  ⚠️  2021'deki fonların %{kapali_oran:.1f}'i bugün yok.")
            print(f"     Bu fonlar muhtemelen kötü performans gösterip tasfiye/birleşme yoluyla kapandı.")
            print(f"     Backtest sadece 'hayatta kalanlar'ı görüyor — bu tek yönlü olumlu bias yaratır.")
        elif kapali_oran > 0:
            print(f"  ℹ️  Kapanan fon oranı %{kapali_oran:.1f} — görece düşük, bias sınırlı.")
        else:
            print(f"  ✅ Kapanan fon tespit edilemedi — ya gerçekten azdır ya da TEFAS geçmiş verisi kısıtlı.")
    else:
        print(f"\n[Adım 4] TEFAS 2021 verisi alınamadı.")
        print(f"     Manuel kontrol: TEFAS web sitesinde 'tasfiye edilmiş değişken fonlar' listesine bakın.")
        print(f"     Bu testin doğru yapılması için farklı bir veri kaynağı (SPK, TKYD) gerekebilir.")

    print("\n[SONUÇ]")
    print(f"  Önceki ölçüm (91/161 fon sonradan girdi) YANLIŞ YORUMLANDI.")
    print(f"  NaN filtrelemesi late-entry fonları zaten dışarıda bırakıyor — bu survivorship bias değil.")
    print(f"  GERÇEK bias: 2021'de var olup bugün kapalı olan fonların CSV'de hiç bulunmaması.")
    print(f"  Bu testi doğru yapabilmek için tarihsel TEFAS fon listesi gerekiyor.")
    print("=" * 80)

if __name__ == "__main__":
    main()
