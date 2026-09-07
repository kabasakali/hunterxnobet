import os
import sys
import pandas as pd
import requests
import json
from concurrent.futures import ThreadPoolExecutor

base_dir = os.path.dirname(os.path.abspath(__file__))
csv_path = os.path.abspath(os.path.join(base_dir, '..', 'serbest_fon_bot', 'csv', '5_yil_pivot.csv'))
arsiv_path = os.path.abspath(os.path.join(base_dir, 'flow_research', 'data', 'gunluk_detay_arsivi.json'))

df = pd.read_csv(csv_path, index_col=0, parse_dates=True).sort_index()

# Arsivdeki unvanlari yukle
arsiv_unvanlar = {}
if os.path.exists(arsiv_path):
    with open(arsiv_path, 'r', encoding='utf-8') as f:
        arsiv_data = json.load(f)
        for f_kod, dates_dict in arsiv_data.items():
            if dates_dict:
                last_d = list(dates_dict.keys())[-1]
                u = dates_dict[last_d].get('fonUnvan', '')
                t = dates_dict[last_d].get('fonTuru', '')
                arsiv_unvanlar[f_kod] = {'unvan': u, 'tur': t}

# Eksik olanlari TEFAS'tan headers ile cek
url = 'https://www.tefas.gov.tr/api/funds/fonBilgiGetir'
headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://www.tefas.gov.tr/"}

def fetch_missing(f):
    if f in arsiv_unvanlar and arsiv_unvanlar[f]['unvan']:
        return f, arsiv_unvanlar[f]
    try:
        r = requests.post(url, json={'fonKodu': f.upper(), 'dil': 'TR'}, headers=headers, timeout=5)
        if r.status_code == 200:
            res = r.json().get('resultList', [])
            if res:
                return f, {'unvan': res[0].get('fonUnvan', ''), 'tur': res[0].get('fonTuru', '')}
    except:
        pass
    return f, {'unvan': f'{f} Fonu', 'tur': 'Yatırım Fonu'}

missing = [c for c in df.columns if c not in arsiv_unvanlar or not arsiv_unvanlar[c]['unvan']]
with ThreadPoolExecutor(max_workers=10) as ex:
    res = list(ex.map(fetch_missing, missing))
    for f, d in res:
        arsiv_unvanlar[f] = d

# Bilinen bazi ozel fonlar
manual_titles = {
    'DGF': 'Deniz Portföy Birinci Değişken Fon',
    'CKL': 'Albatross Portföy Birinci Değişken Fon',
    'URA': 'Ünlü Portföy İkinci Değişken Fon',
    'RPM': 'Rota Portföy Birinci Değişken Fon',
    'GZG': 'Garanti Portföy Temiz Teknoloji Değişken Fon',
    'SOS': 'Hedef Portföy Sağlık Sektörü Değişken Fon',
    'ICH': 'İş Portföy Yenilenebilir Enerji Değişken Fon',
    'MTD': 'BV Portföy Malzeme Teknolojileri Değişken Fon',
    'HKG': 'Hedef Portföy Birinci Değişken Fon',
    'PBR': 'Pardus Portföy Birinci Hisse Senedi Fonu',
    'GPG': 'Gedik Portföy Birinci Değişken Fon',
    'PPZ': 'Azimut Portföy Para Piyasası Fonu'
}

rows = []
for fon in df.columns:
    seri = df[fon].dropna()
    if len(seri) < 65:
        continue
        
    p_now = float(seri.iloc[-1])
    p20 = float(seri.iloc[-21]) if len(seri) > 20 else float(seri.iloc[0])
    p63 = float(seri.iloc[-64]) if len(seri) > 63 else float(seri.iloc[0])
    
    if p20 <= 0 or p63 <= 0 or p_now <= 0:
        continue
        
    r20 = (p_now / p20 - 1) * 100
    r63 = (p_now / p63 - 1) * 100
    skor = r20 * 0.6 + r63 * 0.4
    
    unvan = manual_titles.get(fon) or arsiv_unvanlar.get(fon, {}).get('unvan', f'{fon} Yatırım Fonu')
    
    # Kategori / Alan tespiti
    u_up = unvan.upper()
    alan = "Değişken Fon"
    if "SAĞLIK" in u_up or "SAGLIK" in u_up or fon == "SOS":
        alan = "Sağlık Sektörü"
    elif "ENERJİ" in u_up or "ENERJI" in u_up or "TEMİZ" in u_up or fon in ["ICH", "GZG"]:
        alan = "Yenilenebilir Enerji / Temiz Teknoloji"
    elif "MALZEME" in u_up or fon == "MTD":
        alan = "Malzeme & Sanayi Teknolojileri"
    elif "TEKNOLOJİ" in u_up or "TEKNOLOJI" in u_up:
        alan = "Teknoloji Temalı"
    elif "SERBEST" in u_up:
        alan = "Serbest Fon"
    elif "HİSSE" in u_up or "HISSE" in u_up or fon == "PBR":
        alan = "Hisse Senedi Yoğun"
    elif "FON SEPETİ" in u_up:
        alan = "Fon Sepeti"
    elif "KATILIM" in u_up:
        alan = "Katılım / Faizsiz"
    elif "BORÇLANMA" in u_up or "BORCLANMA" in u_up:
        alan = "Borçlanma Araçları"
    elif "PARA PİYASASI" in u_up:
        alan = "Para Piyasası (Likit)"
    else:
        alan = "Çoklu Varlık Değişken"
        
    # Durum tespiti
    if r20 > 12 and r63 > 15:
        durum = "🔥 Zirve Lideri"
    elif r20 > 8 and r63 > 10:
        durum = "🟢 Güçlü Trend"
    elif r20 > 4 and r63 > 5:
        durum = "🟢 Pozitif İvme"
    elif r20 >= 0 and r63 >= 0:
        durum = "🟡 Dengeli / Ilımlı"
    elif r20 < 0 and r63 >= 0:
        durum = "🟠 Kısa Düzeltme"
    elif r20 < -5 or r63 < -5:
        durum = "🔴 Zayıf Trend"
    else:
        durum = "🟡 Nötr"
        
    if r20 < -10 or fon == "PBR":
        durum = "💥 Sert Çöküş / Riskli"
        
    rows.append({
        'fon': fon,
        'unvan': unvan,
        'alan': alan,
        'r20': r20,
        'r63': r63,
        'skor': skor,
        'durum': durum
    })

rows.sort(key=lambda x: x['skor'], reverse=True)
for idx, r in enumerate(rows):
    r['sira'] = idx + 1

# Markdown tablosu
md_lines = ["# 🏆 TEFAS TÜM HAVUZ FON SIRALAMASI (147 AKTİF FON)\n",
            "| Sıra | Fon Kodu | Fonun Türü / Alanı | 20 Günlük | 63 Günlük | Durum |",
            "|:---:|:---:|:---|:---:|:---:|:---|"]

for r in rows:
    md_lines.append(f"| {r['sira']} | **`{r['fon']}`** | {r['alan']} | `%{r['r20']:+.2f}` | `%{r['r63']:+.2f}` | {r['durum']} |")

with open(os.path.join(base_dir, 'tum_havuz_tam_liste.md'), 'w', encoding='utf-8') as f:
    f.write("\n".join(md_lines))

print(f"Toplam {len(rows)} fon listelendi ve tum_havuz_tam_liste.md olusturuldu!")
