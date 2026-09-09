"""
tefas_tum_arsivleyici.py
========================
TEFAS'taki TÜM Fonların (1.000+ fon) TÜM Verilerini Günlük Toplama ve Arşivleme Motoru.

Toplanan Bilgiler (Eksiksiz TEFAS Veri Seti):
1. Fiyat & Büyüklük: sonFiyat, gunlukGetiri, payAdet, portBuyukluk (AUM), pazarPayi
2. Kategori & Yatırımcı: fonKategori, fonTurAciklama, kategoriDerece, kategoriFonSay, yatirimciSayi
3. Dönemsel Getiriler: getiri1a, getiri3a, getiri6a, getiri1y, getiriyb, getiri3y, getiri5y
4. Risk & Valör: riskDegeri, alisValor, satisValor
5. Portföy Varlık Dağılımı: Hisse Senedi %, Yabancı Hisse %, Ters-Repo %, BYF %, VİOP Nakit Teminatı %, vb.

ÖNEMLİ KURAL: Bu arşiv bağımsız çalışır. Canlı alım/satım havuzumuz (5_yil_pivot.csv) ASLA etkilenmez!
"""

import os
import sys
import json
import time
import datetime
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Any, Optional, Tuple

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
SNAPSHOT_DIR = os.path.join(DATA_DIR, "gunluk_snapshotlar")
ANA_ARSIV_PATH = os.path.join(DATA_DIR, "gunluk_detay_arsivi.json")

def create_session() -> requests.Session:
    """Yüksek hızlı ve otomatik tekrar deneyen HTTP Session oluşturur."""
    s = requests.Session()
    retries = Retry(
        total=3,
        backoff_factor=0.3,
        status_forcelist=[500, 502, 503, 504, 429]
    )
    adapter = HTTPAdapter(pool_connections=40, pool_maxsize=40, max_retries=retries)
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Referer": "https://www.tefas.gov.tr/",
        "Origin": "https://www.tefas.gov.tr"
    })
    return s

def tum_fon_kodlarini_ve_getirilerini_al(session: requests.Session) -> Dict[str, Dict[str, Any]]:
    """TEFAS fonGetiriBazliBilgiGetir üzerinden TEFAS'taki TÜM fonları tek istekte getirir."""
    url = "https://www.tefas.gov.tr/api/funds/fonGetiriBazliBilgiGetir"
    payload = {
        "dil": "TR",
        "fonTipi": "YAT",
        "kurucuKodu": None,
        "sfonTurKod": None,
        "fonTurAciklama": None,
        "islem": 1,
        "fonTurKod": None,
        "fonGrubu": None,
        "donemGetiri1a": "1",
        "donemGetiri3a": "1",
        "donemGetiri6a": "1",
        "donemGetiri1y": "1",
        "donemGetiriyb": "1",
        "donemGetiri3y": "1",
        "donemGetiri5y": "1",
        "basTarih": None,
        "bitTarih": None,
        "calismaTipi": 2,
        "getiriOrani": "1"
    }
    
    fonlar_dict = {}
    try:
        r = session.post(url, json=payload, timeout=20)
        if r.status_code == 200:
            result_list = r.json().get("resultList", [])
            for row in result_list:
                f_kod = row.get("fonKodu")
                if f_kod:
                    fonlar_dict[f_kod] = {
                        "fonKodu": f_kod,
                        "fonUnvan": row.get("fonUnvan"),
                        "fonTurAciklama": row.get("fonTurAciklama"),
                        "tefasDurum": row.get("tefasDurum"),
                        "getiri1a": row.get("getiri1a"),
                        "getiri3a": row.get("getiri3a"),
                        "getiri6a": row.get("getiri6a"),
                        "getiri1y": row.get("getiri1y"),
                        "getiriyb": row.get("getiriyb"),
                        "getiri3y": row.get("getiri3y"),
                        "getiri5y": row.get("getiri5y"),
                        "riskDegeri": row.get("riskDegeri")
                    }
    except Exception as e:
        print(f"[TEFAS TOPLU GETIRI HATA]: {e}")
        
    return fonlar_dict

def tek_fon_canli_bilgi_al(session: requests.Session, fon_kodu: str) -> Optional[Dict[str, Any]]:
    """TEFAS fonBilgiGetir üzerinden günlük fiyat, pay, AUM ve yatırımcı sayısını çeker."""
    url = "https://www.tefas.gov.tr/api/funds/fonBilgiGetir"
    try:
        r = session.post(url, json={"fonKodu": fon_kodu, "dil": "TR"}, timeout=6)
        if r.status_code == 200:
            res = r.json().get("resultList", [])
            if res:
                return res[0]
    except:
        pass
    return None

def tek_fon_varlik_dagilimi_ve_valor_al(session: requests.Session, fon_kodu: str) -> Dict[str, Any]:
    """TEFAS fon-detayli-analiz sayfasından Varlık Dağılımı ve Valör sürelerini çeker."""
    url = f"https://www.tefas.gov.tr/tr/fon-detayli-analiz/{fon_kodu}"
    dagilim = {}
    alis_v, satis_v = 1, 2
    try:
        r = session.get(url, timeout=6)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, "html.parser")
            tbl = soup.find("table")
            if tbl:
                for tr in tbl.find_all("tr")[1:]:
                    tds = tr.find_all("td")
                    if len(tds) >= 2:
                        k = tds[0].text.strip()
                        v_str = tds[1].text.strip().replace("%", "").replace(",", ".").strip()
                        try:
                            dagilim[k] = float(v_str)
                        except:
                            dagilim[k] = v_str
                            
            for el in soup.find_all(["div", "span", "p"]):
                t = el.text.strip()
                if "Alış Valörü" in t:
                    try: alis_v = int("".join(filter(str.isdigit, t)) or 1)
                    except: pass
                elif "Satış Valörü" in t:
                    try: satis_v = int("".join(filter(str.isdigit, t)) or 2)
                    except: pass
    except:
        pass
        
    return {
        "varlik_dagilimi": dagilim,
        "alisValor": alis_v,
        "satisValor": satis_v
    }

def tek_fon_derle_worker(item_args) -> Tuple[str, Optional[Dict[str, Any]]]:
    """Her worker için tekil fon verisini çeker."""
    session, (fon_kodu, getiri_bilgisi) = item_args
    
    canli = tek_fon_canli_bilgi_al(session, fon_kodu)
    varlik = tek_fon_varlik_dagilimi_ve_valor_al(session, fon_kodu)
    
    if not canli and not getiri_bilgisi:
        return fon_kodu, None
        
    tam_kayit = {
        "fonKodu": fon_kodu,
        "fonUnvan": (canli.get("fonUnvan") if canli else None) or getiri_bilgisi.get("fonUnvan"),
        "fonKategori": canli.get("fonKategori") if canli else None,
        "fonTurAciklama": getiri_bilgisi.get("fonTurAciklama"),
        "tefasDurum": getiri_bilgisi.get("tefasDurum", True),
        "sonFiyat": canli.get("sonFiyat") if canli else None,
        "gunlukGetiri": canli.get("gunlukGetiri") if canli else None,
        "payAdet": canli.get("payAdet") if canli else None,
        "portBuyukluk": canli.get("portBuyukluk") if canli else None,
        "yatirimciSayi": canli.get("yatirimciSayi") if canli else None,
        "pazarPayi": canli.get("pazarPayi") if canli else None,
        "kategoriDerece": canli.get("kategoriDerece") if canli else None,
        "kategoriFonSay": canli.get("kategoriFonSay") if canli else None,
        "getiri1a": getiri_bilgisi.get("getiri1a"),
        "getiri3a": getiri_bilgisi.get("getiri3a"),
        "getiri6a": getiri_bilgisi.get("getiri6a"),
        "getiri1y": getiri_bilgisi.get("getiri1y"),
        "getiriyb": getiri_bilgisi.get("getiriyb"),
        "getiri3y": getiri_bilgisi.get("getiri3y"),
        "getiri5y": getiri_bilgisi.get("getiri5y"),
        "riskDegeri": getiri_bilgisi.get("riskDegeri"),
        "varlik_dagilimi": varlik.get("varlik_dagilimi", {}),
        "alisValor": varlik.get("alisValor", 1),
        "satisValor": varlik.get("satisValor", 2),
        "arsiv_zamani": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    
    return fon_kodu, tam_kayit

def tum_tefas_arsivle(max_fon: Optional[int] = None, workers: int = 15) -> Dict[str, Any]:
    """
    TEFAS'taki tüm fonları çeker, zenginleştirir ve hem ana arşive hem de günlük snapshot dosyasına kaydeder.
    """
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(SNAPSHOT_DIR, exist_ok=True)
    
    bugun_str = datetime.date.today().strftime("%Y-%m-%d")
    t0 = time.time()
    
    print(f"[{bugun_str}] TEFAS TÜM FONLARIN ARŞİVLEME SÜRECİ BAŞLATILIYOR...")
    session = create_session()
    
    # 1. Aşama: Tüm fon kodları ve getirilerini tek çağrıda al
    fonlar_dict = tum_fon_kodlarini_ve_getirilerini_al(session)
    toplam_bulunan = len(fonlar_dict)
    print(f">> 1. Aşama: TEFAS listesinden {toplam_bulunan} adet fon tespit edildi.")
    
    if not fonlar_dict:
        print("[HATA] TEFAS fon listesi alınamadı.")
        return {"basarili": 0, "toplam": 0, "sure": 0}
        
    fon_listesi = list(fonlar_dict.items())
    if max_fon:
        fon_listesi = fon_listesi[:max_fon]
        
    # 2. Aşama: Detayları ve varlık dağılımlarını paralel çek
    print(f">> 2. Aşama: {len(fon_listesi)} fon için detaylı bilgiler ve varlık dağılımları toplanıyor...")
    worker_args = [(session, item) for item in fon_listesi]
    
    gunluk_snapshot = {}
    with ThreadPoolExecutor(max_workers=workers) as executor:
        results = list(executor.map(tek_fon_derle_worker, worker_args))
        
    for f_kod, data in results:
        if data:
            gunluk_snapshot[f_kod] = data
            
    basarili_sayisi = len(gunluk_snapshot)
    sure = round(time.time() - t0, 1)
    print(f">> 3. Aşama: Toplama bitti! {basarili_sayisi}/{len(fon_listesi)} fon başarıyla derlendi ({sure} sn).")
    
    # 3. Aşama: Günlük bağımsız snapshot dosyasına yaz
    snapshot_file = os.path.join(SNAPSHOT_DIR, f"tefas_tam_snapshot_{bugun_str}.json")
    try:
        with open(snapshot_file, "w", encoding="utf-8") as f:
            json.dump(gunluk_snapshot, f, indent=2, ensure_ascii=False)
        print(f">> Günlük Snapshot kaydedildi: {snapshot_file}")
    except Exception as e:
        print(f"[SNAPSHOT KAYIT HATA]: {e}")
        
    # 4. Aşama: Ana birleşik arşive ekle (gunluk_detay_arsivi.json)
    arsiv = {}
    if os.path.exists(ANA_ARSIV_PATH):
        try:
            with open(ANA_ARSIV_PATH, "r", encoding="utf-8") as f:
                arsiv = json.load(f)
        except:
            arsiv = {}
            
    for f_kod, data in gunluk_snapshot.items():
        if f_kod not in arsiv:
            arsiv[f_kod] = {}
        arsiv[f_kod][bugun_str] = data
        
    try:
        with open(ANA_ARSIV_PATH, "w", encoding="utf-8") as f:
            json.dump(arsiv, f, indent=2, ensure_ascii=False)
        print(f">> Ana arşive entegre edildi: {ANA_ARSIV_PATH} ({len(arsiv)} fon takipte)")
    except Exception as e:
        print(f"[ANA ARSIV KAYIT HATA]: {e}")
        
    return {
        "tarih": bugun_str,
        "basarili": basarili_sayisi,
        "toplam": len(fon_listesi),
        "sure_saniye": sure,
        "snapshot_yolu": snapshot_file
    }

if __name__ == "__main__":
    # Test çalıştırması (ilk 25 fon)
    res = tum_tefas_arsivle(max_fon=25)
    print("\nTest Sonucu:", res)
