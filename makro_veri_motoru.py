"""
makro_veri_motoru.py
====================
Canlı, Doğrulanabilir Makro Veri ve Dinamik Risksiz Faiz (Rf) Motoru.

Görevleri:
1. Dolar Kuru (USD/TRY) ve Borsa Endeksini (BIST 100) canlı finans API'sinden anlık çeker.
2. Sabit faiz yerine TEFAS PPZ (Para Piyasası) üzerinden dinamik günlük/yıllık Risksiz Faizi (Rf) hesaplar.
3. Her veri çekişi "Zaman Damgası + Kaynak Adresi" ile makro_veri_gunlugu.jsonl dosyasına adli olarak loglar.
4. Portföy motoru için aşırı getiri (Excess Return / Net Alfa) ve kurumsal standartta dürüst Sharpe/Sortino üretir.
"""

import os
import sys
import json
import time
import datetime
import urllib.request
import pandas as pd
import numpy as np
from typing import Dict, Any, Optional

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(BASE_DIR, "flow_research", "data", "makro_veri_gunlugu.jsonl")
PIVOT_PATH = os.path.join(BASE_DIR, "5_yil_pivot.csv")

# Bellek içi 15 dakikalık önbellek (API kota koruması için)
_cache_veri = None
_cache_zamani = 0

def _fetch_yahoo_quote(symbol: str) -> Dict[str, Any]:
    """Yahoo Finance Chart API üzerinden canlı fiyat ve önceki kapanışı çeker."""
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=5d"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    }
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode('utf-8'))
        meta = data['chart']['result'][0]['meta']
        price = meta.get('regularMarketPrice')
        prev = meta.get('chartPreviousClose') or meta.get('previousClose')
        chg_pct = ((price - prev) / prev * 100) if (price and prev and prev > 0) else 0.0
        return {
            "fiyat": round(float(price), 4) if price else None,
            "onceki_kapanis": round(float(prev), 4) if prev else None,
            "gunluk_degisim_pct": round(float(chg_pct), 2),
            "sembol": symbol
        }

def get_dinamik_rf_orani(pivot_df: Optional[pd.DataFrame] = None) -> Dict[str, float]:
    """
    TEFAS resmi PPZ (Para Piyasası) verisi üzerinden dinamik risksiz faizi hesaplar.
    Son 20 günün ortalamasını alarak para piyasasının gerçek yıllık bileşik faizini bulur.
    """
    try:
        df = pivot_df
        if df is None and os.path.exists(PIVOT_PATH):
            df = pd.read_csv(PIVOT_PATH, index_col=0, parse_dates=True)
            
        if df is not None and "PPZ" in df.columns:
            ppz = df["PPZ"].dropna()
            if len(ppz) >= 5:
                daily_rets = ppz.pct_change().dropna()
                # Son 20 iş gününün geometrik/aritmetik ortalaması
                gunluk_rf = float(daily_rets.tail(20).mean())
                yillik_rf_pct = float(((1.0 + gunluk_rf) ** 252 - 1.0) * 100.0)
                return {
                    "rf_gunluk": gunluk_rf,
                    "rf_yillik_pct": round(yillik_rf_pct, 2)
                }
    except Exception as e:
        print(f"[RF HESAPLAMA UYARI]: {e}")
        
    # Güvenli varsayılan: TCMB ~%45 faiz bandı
    rf_g = (1.0 + 0.45) ** (1.0 / 252.0) - 1.0
    return {"rf_gunluk": rf_g, "rf_yillik_pct": 45.00}

def get_canli_makro_gostergeler(cache_saniye: int = 900) -> Dict[str, Any]:
    """
    Dolar (USD/TRY), BIST 100 ve Dinamik Rf verilerini canlı çeker.
    Her çağrıyı kaynak ve zaman damgasıyla doğrular ve loglar.
    """
    global _cache_veri, _cache_zamani
    now_ts = time.time()
    
    if _cache_veri is not None and (now_ts - _cache_zamani) < cache_saniye:
        return _cache_veri
        
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # 1. Canlı Dolar Kuru
    try:
        usd_data = _fetch_yahoo_quote("USDTRY=X")
    except Exception as e:
        usd_data = {"fiyat": None, "gunluk_degisim_pct": 0.0, "hata": str(e)}
        
    # 2. Canlı BIST 100 Endeksi
    try:
        bist_data = _fetch_yahoo_quote("XU100.IS")
    except Exception as e:
        bist_data = {"fiyat": None, "gunluk_degisim_pct": 0.0, "hata": str(e)}
        
    # 3. Dinamik Risksiz Faiz
    rf_data = get_dinamik_rf_orani()
    
    sonuc = {
        "zaman": now_str,
        "kaynak": "Yahoo Finance (Canlı) & TEFAS PPZ",
        "usd_try": usd_data.get("fiyat"),
        "usd_try_degisim_pct": usd_data.get("gunluk_degisim_pct", 0.0),
        "bist_100": bist_data.get("fiyat"),
        "bist_100_degisim_pct": bist_data.get("gunluk_degisim_pct", 0.0),
        "rf_yillik_pct": rf_data.get("rf_yillik_pct"),
        "rf_gunluk": rf_data.get("rf_gunluk"),
        "durum": "CANLI_DOGRULANMIS" if (usd_data.get("fiyat") and bist_data.get("fiyat")) else "KISMI_VERI"
    }
    
    _cache_veri = sonuc
    _cache_zamani = now_ts
    
    # 4. Adli Log Kaydı (Audit Trail)
    try:
        os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(sonuc, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"[MAKRO LOG HATA]: {e}")
        
    return sonuc

def hesapla_kurumsal_metrikler(gunluk_getiriler: pd.Series, rf_gunluk: Optional[float] = None) -> Dict[str, float]:
    """
    Risksiz faiz oranını (Rf) günlük getiri serisinden düşerek
    gerçek kurumsal Sharpe, Sortino ve Net Alfa oranlarını hesaplar.
    """
    if gunluk_getiriler.empty:
        return {"kurumsal_sharpe": 0.0, "kurumsal_sortino": 0.0, "net_alfa_pct": 0.0}
        
    if rf_gunluk is None:
        rf_gunluk = get_dinamik_rf_orani().get("rf_gunluk", 0.00146)
        
    excess_rets = gunluk_getiriler - rf_gunluk
    vol = float(gunluk_getiriler.std() + 1e-9)
    
    # Dürüst Sharpe: (Ortalama Aşırı Getiri / Volatilite) * sqrt(252)
    sharpe = float((excess_rets.mean() / vol) * np.sqrt(252))
    
    # Dürüst Sortino: Sadece negatif aşırı getirilerin sapmasına bölünür
    downside_rets = excess_rets[excess_rets < 0]
    downside_std = float(downside_rets.std() + 1e-9) if not downside_rets.empty else vol
    sortino = float((excess_rets.mean() / downside_std) * np.sqrt(252))
    
    # Net Alfa %: Strateji toplam getirisi eksi faizin kümülatif getirisi
    strat_cum = float((1.0 + gunluk_getiriler).prod() - 1.0) * 100.0
    rf_cum = float((1.0 + rf_gunluk) ** len(gunluk_getiriler) - 1.0) * 100.0
    net_alfa = strat_cum - rf_cum
    
    return {
        "kurumsal_sharpe": round(sharpe, 2),
        "kurumsal_sortino": round(sortino, 2),
        "net_alfa_pct": round(net_alfa, 2),
        "toplam_getiri_pct": round(strat_cum, 2),
        "karsilastirma_faiz_getirisi_pct": round(rf_cum, 2)
    }

if __name__ == "__main__":
    print("=== CANLI MAKRO MOTOR TESTİ ===")
    m = get_canli_makro_gostergeler(cache_saniye=0)
    print(json.dumps(m, indent=2, ensure_ascii=False))
    
    print("\n=== ÖRNEK KURUMSAL SHARPE TESTİ ===")
    # Örnek 100 günlük %0.2 getirili seri
    mock_rets = pd.Series([0.002] * 100)
    km = hesapla_kurumsal_metrikler(mock_rets)
    print(json.dumps(km, indent=2, ensure_ascii=False))
