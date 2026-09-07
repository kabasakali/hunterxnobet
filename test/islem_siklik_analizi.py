import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from harmony_v2_2_live_production import HarmonyV22LiveProduction

eng = HarmonyV22LiveProduction()
r5y = eng.simule_et_production(use_cutoff_lag=True)
kayitlar = r5y["gunluk_kayitlar"]

# Kayit alanlarini goster
if kayitlar:
    print("Ornek kayit alanlari:", list(kayitlar[100].keys()))
    print()

onceki = None
degisimler = []
for k in kayitlar:
    # Tum olasi alan isimlerini dene
    fon = None
    for alan in ["aktif_fon", "fon", "pozisyon", "hunter_fon", "secilen_fon"]:
        if alan in k and k[alan] is not None:
            fon = k[alan]
            break

    if fon != onceki and onceki is not None:
        tarih = k.get("tarih", "?")
        degisimler.append((tarih, onceki, fon))
    onceki = fon

toplam = len(kayitlar)
print(f"5 yillik toplam islem gunu : {toplam}")
print(f"Fon degisim (switch) sayisi: {len(degisimler)}")
if degisimler:
    print(f"Ortalama tutma suresi      : {toplam / len(degisimler):.0f} gun")
    print()
    print("Tum fon degisimleri:")
    for tarih, eski, yeni in degisimler:
        print(f"  {tarih} | {str(eski):>5} -> {str(yeni):>5}")
else:
    # Baska alanlara bak
    print()
    print("Degisim bulunamadi. Mevcut alanlar:")
    ornek = kayitlar[100]
    for k2, v2 in ornek.items():
        print(f"  {k2}: {v2}")
