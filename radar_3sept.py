import os
import sys
import pandas as pd
import requests
import numpy as np

base_dir = os.path.dirname(os.path.abspath(__file__))

# 5 yillik pivot CSV'yi bul
csv_candidates = [
    os.path.join(os.path.dirname(base_dir), "serbest_fon_bot", "csv", "5_yil_pivot.csv"),
    os.path.join(os.path.dirname(base_dir), "5_yil_pivot.csv"),
    os.path.join(base_dir, "5_yil_pivot.csv"),
]
csv_path = None
for p in csv_candidates:
    if os.path.exists(p):
        csv_path = p
        break

if csv_path is None:
    print("5_yil_pivot.csv bulunamadi!")
    sys.exit(1)

df = pd.read_csv(csv_path, index_col=0, parse_dates=True)
df = df.sort_index()

# Son fiyatlari TEFAS API'den al
url = 'https://www.tefas.gov.tr/api/funds/fonBilgiGetir'
son_fiyatlar = {}
for fon in df.columns:
    try:
        r = requests.post(url, json={'fonKodu': fon, 'dil': 'TR'}, timeout=3)
        if r.status_code == 200:
            res = r.json().get('resultList', [])
            if res and res[0].get('sonFiyat'):
                son_fiyatlar[fon] = float(res[0]['sonFiyat'])
    except:
        pass

# Momentum puanlama: 20G ve 63G getiri
results = []
for fon in df.columns:
    seri = df[fon].dropna()
    if len(seri) < 65:
        continue
    son_fiyat = son_fiyatlar.get(fon, float(seri.iloc[-1]))
    if son_fiyat <= 0:
        continue
    p20 = float(seri.iloc[-21]) if len(seri) > 20 else float(seri.iloc[0])
    p63 = float(seri.iloc[-64]) if len(seri) > 63 else float(seri.iloc[0])
    if p20 <= 0 or p63 <= 0:
        continue
    r20 = (son_fiyat / p20 - 1) * 100
    r63 = (son_fiyat / p63 - 1) * 100

    skor = r20 * 0.6 + r63 * 0.4
    results.append({'fon': fon, 'skor': skor, 'r20': r20, 'r63': r63, 'son_fiyat': son_fiyat})

results.sort(key=lambda x: x['skor'], reverse=True)

print("=== HARMONY RADAR - 3 EYLUL 2026 - TOP 15 FONLAR ===")
print(f"{'Sira':<5} {'Fon':<6} {'Skor':>7} {'20G Getiri':>12} {'63G Getiri':>12} {'Son Fiyat':>12}")
print("-" * 60)
for i, r in enumerate(results[:15]):
    print(f"{i+1:<5} {r['fon']:<6} {r['skor']:>7.2f} {r['r20']:>+11.2f}% {r['r63']:>+11.2f}% {r['son_fiyat']:>12.6f}")

print()
lider = results[0] if results else {}
print(f"1. LIDER FON : {lider.get('fon')} | Skor: {lider.get('skor'):.2f} | 20G: %{lider.get('r20'):+.2f} | 63G: %{lider.get('r63'):+.2f}")

# SOS sira
sos_sira = next((i+1 for i, r in enumerate(results) if r['fon'] == 'SOS'), None)
sos_data = next((r for r in results if r['fon'] == 'SOS'), None)
if sos_data:
    print(f"SOS SIRA    : {sos_sira}. sirада | Skor: {sos_data.get('skor'):.2f} | 20G: %{sos_data.get('r20'):+.2f} | 63G: %{sos_data.get('r63'):+.2f}")
