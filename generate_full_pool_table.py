import os
import sys
import pandas as pd
import requests
import json
from concurrent.futures import ThreadPoolExecutor

base_dir = os.path.dirname(os.path.abspath(__file__))
csv_path = os.path.abspath(os.path.join(base_dir, '..', 'serbest_fon_bot', 'csv', '5_yil_pivot.csv'))

df = pd.read_csv(csv_path, index_col=0, parse_dates=True).sort_index()

url = 'https://www.tefas.gov.tr/api/funds/fonBilgiGetir'

def fetch_fon_info(fon):
    try:
        r = requests.post(url, json={'fonKodu': fon, 'dil': 'TR'}, timeout=4)
        if r.status_code == 200:
            res = r.json().get('resultList', [])
            if res:
                d = res[0]
                return {
                    'fon': fon,
                    'unvan': d.get('fonUnvan', ''),
                    'tur': d.get('fonTuru', ''),
                    'son_fiyat': float(d.get('sonFiyat', 0)) if d.get('sonFiyat') else None
                }
    except:
        pass
    return {'fon': fon, 'unvan': '', 'tur': '', 'son_fiyat': None}

print("TEFAS'tan 156 fonun unvan ve guncel fiyatlari cekiliyor...")
all_info = {}
with ThreadPoolExecutor(max_workers=20) as executor:
    results = executor.map(fetch_fon_info, df.columns)
    for res in results:
        all_info[res['fon']] = res

# Simdi 20G ve 63G getirileri hesaplayalim
fund_rows = []
for fon in df.columns:
    seri = df[fon].dropna()
    if len(seri) < 65:
        continue
    
    info = all_info.get(fon, {})
    son_fiyat = info.get('son_fiyat')
    if not son_fiyat or son_fiyat <= 0:
        son_fiyat = float(seri.iloc[-1])
        
    p20 = float(seri.iloc[-21]) if len(seri) > 20 else float(seri.iloc[0])
    p63 = float(seri.iloc[-64]) if len(seri) > 63 else float(seri.iloc[0])
    
    if p20 <= 0 or p63 <= 0 or son_fiyat <= 0:
        continue
        
    r20 = (son_fiyat / p20 - 1) * 100
    r63 = (son_fiyat / p63 - 1) * 100
    skor = r20 * 0.6 + r63 * 0.4
    
    unvan = info.get('unvan', '')
    tur = info.get('tur', '')
    
    # Basit kategori tespiti
    kategori = "Değişken Fon"
    u_up = unvan.upper()
    if "SERBEST" in u_up:
        kategori = "Serbest Fon"
    elif "HİSSE" in u_up or "HISSE" in u_up:
        kategori = "Hisse Senedi Fonu"
    elif "KATILIM" in u_up:
        kategori = "Katılım Fonu"
    elif "FON SEPETİ" in u_up or "FON SEPETI" in u_up:
        kategori = "Fon Sepeti Fonu"
    elif "BORÇLANMA" in u_up or "BORCLANMA" in u_up:
        kategori = "Borçlanma Araçları"
    elif "PARA PİYASASI" in u_up or "LIKIT" in u_up:
        kategori = "Para Piyasası Fonu"
    elif "KIYMETLİ MADEN" in u_up or "ALTIN" in u_up:
        kategori = "Kıymetli Madenler"
    elif tur:
        kategori = tur
        
    # Kisa alan / sektor ozeti
    alan = kategori
    if "SAĞLIK" in u_up or "SAGLIK" in u_up or fon == "SOS":
        alan = "Sağlık Sektörü"
    elif "ENERJİ" in u_up or "ENERJI" in u_up or fon == "ICH":
        alan = "Yenilenebilir Enerji"
    elif "TEKNOLOJİ" in u_up or "TEKNOLOJI" in u_up or fon == "GZG":
        alan = "Temiz Teknoloji"
    elif "SÜRDÜRÜLEBİLİRLİK" in u_up:
        alan = "Sürdürülebilirlik"
    elif "YABANCI" in u_up:
        alan = "Yabancı Hisse/Teknoloji"
    elif "BIST" in u_up or "HİSSE" in u_up:
        alan = "Yerli Hisse (BIST)"
        
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
        
    if r20 < -15 or r63 < -15 or fon == "PBR":
        durum = "💥 Sert Çöküş / Riskli"
        
    fund_rows.append({
        'fon': fon,
        'unvan': unvan,
        'kategori': kategori,
        'alan': f"{kategori} ({alan})" if alan != kategori else kategori,
        'r20': r20,
        'r63': r63,
        'skor': skor,
        'durum': durum
    })

fund_rows.sort(key=lambda x: x['skor'], reverse=True)

# Siralama ata
for idx, item in enumerate(fund_rows):
    item['sira'] = idx + 1

print(f"Toplam {len(fund_rows)} fon basariyla puanlandi!")

# JSON olarak kaydet ki istenirse kullanilsin
with open(os.path.join(base_dir, 'tam_havuz_sonuc.json'), 'w', encoding='utf-8') as f:
    json.dump(fund_rows, f, ensure_ascii=False, indent=2)

# Simdi Markdown ciktisi hazirla
md_lines = []
md_lines.append("| Sıra | Fon Kodu | Fonun Türü / Alanı | 20 Günlük | 63 Günlük | Durum |")
md_lines.append("|:---:|:---:|:---|:---:|:---:|:---|")

for r in fund_rows:
    md_lines.append(f"| {r['sira']} | **`{r['fon']}`** | {r['alan']} | `%{r['r20']:+.2f}` | `%{r['r63']:+.2f}` | {r['durum']} |")

with open(os.path.join(base_dir, 'tam_havuz_tablosu.md'), 'w', encoding='utf-8') as f:
    f.write("\n".join(md_lines))

print("tam_havuz_tablosu.md basariyla olusturuldu!")
