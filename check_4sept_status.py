import requests
import json
import os
import sys

base_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, base_dir)

from canli_muhasebe_motoru import CanliMuhasebeMotoru

muh = CanliMuhasebeMotoru()
durum = muh.portfoy_degerini_guncelle()

url = 'https://www.tefas.gov.tr/api/funds/fonBilgiGetir'
headers = {'User-Agent': 'Mozilla/5.0', 'Referer': 'https://www.tefas.gov.tr/'}
fonlar = ['SOS', 'MTD', 'DGF', 'CKL', 'ICH', 'GZG', 'GPG', 'PBR', 'PPZ']

print("=== 4 EYLUL 2026 TEFAS CANLI FIYAT VE GETIRILER ===")
for f in fonlar:
    try:
        r = requests.post(url, json={'fonKodu': f, 'dil': 'TR'}, headers=headers, timeout=5)
        if r.status_code == 200:
            res = r.json().get('resultList', [])
            if res:
                d = res[0]
                sf = d.get('sonFiyat', 0)
                gg = d.get('gunlukGetiri', 0)
                print(f"{f:<5} | Fiyat: {sf:<10} | Gunluk: %{gg:<8}")
    except Exception as e:
        print(f"{f}: {e}")

print("\n=== CANLI PORTFOY DURUMU ===")
print(f"Toplam Portfoy: {durum.get('toplam_portfoy_tl'):,.2f} TL")
print(f"Zirve Portfoy : {durum.get('zirve_portfoy_tl'):,.2f} TL")
print(f"Mevcut Cekilme: %{durum.get('mevcut_cekilme_pct'):.2f}")
print("Eldeki Fonlar:")
for f, info in durum.get("eldeki_fonlar", {}).items():
    kar_tl = info.get('guncel_deger_tl', 0) - info.get('pay_adedi', 0)*info.get('maliyet_fiyati', 0)
    kar_pct = (kar_tl / (info.get('pay_adedi', 0)*info.get('maliyet_fiyati', 1))) * 100
    print(f"  - {f}: {info.get('pay_adedi'):,.2f} Pay | Maliyet: {info.get('maliyet_fiyati'):.6f} | Son NAV: {info.get('son_nav'):.6f} | Tutar: {info.get('guncel_deger_tl'):,.2f} TL | Kar: {kar_tl:>+8.2f} TL (%{kar_pct:+.2f})")
print("Takastaki Islemler:")
for t in durum.get("takasta_bekleyen_islemler", []):
    print(f"  - {t.get('hedef_fon')}: {t.get('pay_adedi'):,.2f} Pay | Tutar: {t.get('tutar_tl'):,.2f} TL | Kalan Gun: {t.get('kalan_gun')}")
