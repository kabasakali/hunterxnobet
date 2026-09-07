import pandas as pd, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from harmony_v2_2_live_production import HarmonyV22LiveProduction

eng = HarmonyV22LiveProduction()
fiyat = eng.golden.base_motor.base_motor.fiyat_df

baslangic = pd.to_datetime('2021-11-22')
sinir = pd.to_datetime('2023-01-01')

ilk_veri = fiyat.apply(lambda c: c.first_valid_index())
gec_girenler = ilk_veri[ilk_veri > baslangic].sort_values()

print(f"Toplam fon: {len(fiyat.columns)}")
print(f"Simülasyon başlangıcı: {baslangic.date()}")
print(f"Sonradan giren fon sayısı: {len(gec_girenler)}")
print()

erken = gec_girenler[gec_girenler <= sinir]
gec = gec_girenler[gec_girenler > sinir]

print("2021-11-22 ile 2023-01-01 arası piyasaya girenler:")
for fon, tarih in erken.items():
    print(f"  {fon}: {tarih.date()}")

print(f"\n2023'ten sonra piyasaya girenler: {len(gec)} fon")
for fon, tarih in gec.items():
    print(f"  {fon}: {tarih.date()}")

print("\nSurvivorShip Bias Notu:")
print("Bu fonlar 2021'de henüz TEFAS'ta yoktu ama simülasyon onları")
print("o tarihten itibaren tutuyorsa, bu geriye dönük bilgi sızdırmasıdır.")
