import requests
import json
import os
import sys

base_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, base_dir)

from canli_muhasebe_motoru import CanliMuhasebeMotoru

muh = CanliMuhasebeMotoru()
durum = muh.portfoy_degerini_guncelle()

def get_tefas(fon):
    url = 'https://www.tefas.gov.tr/api/funds/fonBilgiGetir'
    try:
        r = requests.post(url, json={'fonKodu': fon, 'dil': 'TR'}, timeout=6)
        if r.status_code == 200:
            res = r.json().get('resultList', [])
            if res:
                return res[0]
    except Exception as e:
        return {}
    return {}

print("=== CANLI PORTFOY DURUMU ===")
print(f"Toplam Portfoy: {durum.get('toplam_portfoy_tl'):,.2f} TL")
print(f"Zirve Portfoy : {durum.get('zirve_portfoy_tl'):,.2f} TL")
print(f"Mevcut Cekilme: %{durum.get('mevcut_cekilme_pct'):.2f}")
print("Eldeki Fonlar:")
for f, info in durum.get("eldeki_fonlar", {}).items():
    print(f"  - {f}: {info.get('pay_adedi'):,.2f} Pay | Maliyet: {info.get('maliyet_fiyati'):.6f} | Son NAV: {info.get('son_nav'):.6f} | Tutar: {info.get('guncel_deger_tl'):,.2f} TL")
print("Takastaki Islemler:")
for t in durum.get("takasta_bekleyen_islemler", []):
    print(f"  - {t.get('hedef_fon')}: {t.get('pay_adedi'):,.2f} Pay | Tutar: {t.get('tutar_tl'):,.2f} TL | Kalan Gun: {t.get('kalan_gun')}")

print("\n=== TEFAS CANLI GETIRILER (31 AGUSTOS 2026) ===")
fonlar = ['SOS', 'MTD', 'CKL', 'DGF', 'GPG', 'PBR', 'PPZ']
for f in fonlar:
    d = get_tefas(f)
    if d:
        print(f"{f:<5} | Fiyat: {d.get('sonFiyat')} | Gunluk: %{d.get('gunlukGetiri')} | 1A: %{d.get('birAyGetiri')} | 3A: %{d.get('ucAyGetiri')} | 6A: %{d.get('altiAyGetiri')}")
    else:
        print(f"{f:<5} | Veri cekilemedi")
