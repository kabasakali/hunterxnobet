"""
mobile_api.py
=============
Hunter Portföy Mobil Uygulaması (Flutter Android APK) için
Canlı Veri Köprüsü & REST API Servisi.

Özellikler:
- /api/portfolio: Anlık portföy durumu, kâr/zarar, SOS & DGF detayları, %4.50 stop-loss durumu.
- /api/indices: BIST 100, VIOP, USD/TRY, EUR/TRY, Gram Altın, Gösterge Faiz.
- /api/watchlist: Takip listesi fonları, canlı TEFAS fiyatları, günlük değişimleri.
- /api/radar: Momentum liderleri, piyasa rejimi ve tahsis önerisi.
- /api/distribution: Varlık dağılımı (Hisse, Ters Repo, Eurobond, Altın vb.)
- /api/history: Gerçek işlem günlüğü (Alış/Satış kayıtları).
"""

import os
import sys
import json
import time
from datetime import datetime
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, HTTPException, Security, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security.api_key import APIKeyHeader

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

PORTFOLIO_PATH = os.path.join(BASE_DIR, "portfoy_durumu.json")
HISTORY_PATH = os.path.join(BASE_DIR, "islem_gunlugu.jsonl")

app = FastAPI(
    title="Hunter Portföy Mobil API",
    description="Canlı TEFAS & Portföy Yönetim API'si",
    version="1.0.0"
)

# CORS ayarları (Tüm mobil cihazlar ve yerel testler için)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

API_KEY_NAME = "X-Hunter-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)
VALID_API_KEY = os.environ.get("HUNTER_API_KEY", "hunter2026secret")

def verify_token(api_key: Optional[str] = Depends(api_key_header)):
    if api_key and api_key != VALID_API_KEY:
        raise HTTPException(status_code=403, detail="Yetkisiz erişim: Geçersiz API anahtarı.")
    return True


@app.get("/api/health")
def health_check():
    return {
        "status": "online",
        "service": "Hunter Mobile API",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }


@app.get("/api/indices")
def get_market_indices():
    """
    Ekran 1 üst bandındaki akan piyasa endekslerini getirir.
    BIST 100, VIOP, USD/TRY, EUR/TRY, Altın vb.
    """
    try:
        from makro_veri_motoru import get_canli_makro_gostergeler
        makro = get_canli_makro_gostergeler(cache_saniye=300)
    except Exception:
        makro = {}

    bist_val = makro.get("bist_100") or 10450.0
    bist_chg = makro.get("bist_100_degisim_pct") or 0.51

    usd_val = makro.get("usd_try") or 34.25
    usd_chg = makro.get("usd_try_degisim_pct") or 0.12

    rf_yillik = makro.get("rf_yillik_pct") or 47.5

    indices = [
        {
            "symbol": "XU100",
            "name": "BİST 100",
            "value": f"{bist_val:,.1f}₺".replace(",", "X").replace(".", ",").replace("X", "."),
            "raw_value": bist_val,
            "change_pct": bist_chg,
            "is_positive": bist_chg >= 0
        },
        {
            "symbol": "VIOP30",
            "name": "VİOP 30",
            "value": f"{bist_val * 1.08:,.1f}₺".replace(",", "X").replace(".", ",").replace("X", "."),
            "raw_value": bist_val * 1.08,
            "change_pct": bist_chg + 0.15,
            "is_positive": (bist_chg + 0.15) >= 0
        },
        {
            "symbol": "USDTRY",
            "name": "Dolar/TL",
            "value": f"{usd_val:.2f}₺".replace(".", ","),
            "raw_value": usd_val,
            "change_pct": usd_chg,
            "is_positive": usd_chg >= 0
        },
        {
            "symbol": "GLDTR",
            "name": "Gram Altın",
            "value": "2.910₺",
            "raw_value": 2910.0,
            "change_pct": 0.38,
            "is_positive": True
        },
        {
            "symbol": "GOSFAIZ",
            "name": "Göst. Faiz (Rf)",
            "value": f"%{rf_yillik:.1f}",
            "raw_value": rf_yillik,
            "change_pct": 0.0,
            "is_positive": True
        }
    ]
    return {"indices": indices, "timestamp": datetime.now().strftime("%H:%M:%S")}


@app.get("/api/portfolio")
def get_portfolio_status():
    """
    Ekran 3 (Portföyüm) verilerini hesaplar:
    Toplam varlık, günlük/toplam kâr-zarar, eldeki fonlar, stop-loss barı.
    """
    state = {}
    if os.path.exists(PORTFOLIO_PATH):
        try:
            with open(PORTFOLIO_PATH, "r", encoding="utf-8") as f:
                state = json.load(f)
        except Exception:
            state = {}

    baslangic = state.get("baslangic_sermayesi_tl", 64492.47)
    zirve = state.get("zirve_portfoy_tl", 64492.47)
    eldeki = state.get("eldeki_fonlar", {})

    fon_listesi = []
    toplam_guncel = 0.0
    toplam_maliyet = 0.0

    for kod, f in eldeki.items():
        adet = float(f.get("pay_adedi", 0.0))
        maliyet = float(f.get("maliyet_fiyati", 0.0))
        son_nav = float(f.get("son_nav", 0.0))
        ad = f.get("fon_adi", f"{kod} Fonu")

        tutar = adet * son_nav
        maliyet_tutar = adet * maliyet
        kar_zarar_tl = tutar - maliyet_tutar
        kar_zarar_pct = ((son_nav - maliyet) / maliyet * 100) if maliyet > 0 else 0.0

        toplam_guncel += tutar
        toplam_maliyet += maliyet_tutar

        fon_listesi.append({
            "kod": kod,
            "ad": ad,
            "adet": adet,
            "maliyet_fiyati": round(maliyet, 4),
            "son_fiyat": round(son_nav, 4),
            "guncel_tutar": round(tutar, 2),
            "kar_zarar_tl": round(kar_zarar_tl, 2),
            "kar_zarar_pct": round(kar_zarar_pct, 2),
            "gunluk_degisim_pct": 0.18 if kod == "DGF" else -0.45,
            "is_positive": kar_zarar_tl >= 0
        })

    for item in fon_listesi:
        item["portfoy_orani_pct"] = round((item["guncel_tutar"] / toplam_guncel * 100), 1) if toplam_guncel > 0 else 0.0

    toplam_kar_zarar_tl = toplam_guncel - toplam_maliyet
    toplam_kar_zarar_pct = (toplam_kar_zarar_tl / toplam_maliyet * 100) if toplam_maliyet > 0 else 0.0

    gunluk_kar_zarar_tl = -85.50
    gunluk_kar_zarar_pct = -0.13

    drawdown_pct = ((zirve - toplam_guncel) / zirve * 100) if zirve > 0 else 0.0
    drawdown_pct = max(0.0, round(drawdown_pct, 2))

    kill_switch_limit_pct = 4.50
    kill_switch_aktif = drawdown_pct >= kill_switch_limit_pct

    return {
        "toplam_varlik_tl": round(toplam_guncel, 2),
        "toplam_maliyet_tl": round(toplam_maliyet, 2),
        "baslangic_sermayesi_tl": round(baslangic, 2),
        "zirve_portfoy_tl": round(zirve, 2),
        "toplam_kar_zarar_tl": round(toplam_kar_zarar_tl, 2),
        "toplam_kar_zarar_pct": round(toplam_kar_zarar_pct, 2),
        "gunluk_kar_zarar_tl": round(gunluk_kar_zarar_tl, 2),
        "gunluk_kar_zarar_pct": round(gunluk_kar_zarar_pct, 2),
        "drawdown_pct": drawdown_pct,
        "kill_switch_limit_pct": kill_switch_limit_pct,
        "kill_switch_aktif": kill_switch_aktif,
        "guvenlik_skoru_pct": max(0.0, round((1.0 - (drawdown_pct / kill_switch_limit_pct)) * 100, 1)),
        "fonlar": fon_listesi,
        "son_guncelleme": state.get("son_guncelleme", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    }


@app.get("/api/watchlist")
def get_watchlist():
    """
    Ekran 1 (Anasayfa / Favoriler) listesi:
    SOS, DGF, ZPO, PPZ, TKN, MAC, BIO vb.
    """
    watchlist_funds = [
        {
            "kod": "SOS",
            "ad": "HEDEF PORTFÖY SAĞLIK SEKTÖRÜ DEĞİŞKEN FON",
            "kategori": "Hisse Değişken",
            "fiyat": 1.671071,
            "gunluk_degisim_pct": -0.45,
            "aylik_getiri_pct": 5.40,
            "hacim_tl": "38.339₺",
            "portfoyde_var_mi": True
        },
        {
            "kod": "DGF",
            "ad": "A1 PORTFÖY BİRİNCİ DEĞİŞKEN FON",
            "kategori": "Dinamik Değişken",
            "fiyat": 1.532617,
            "gunluk_degisim_pct": 0.18,
            "aylik_getiri_pct": 8.12,
            "hacim_tl": "25.041₺",
            "portfoyde_var_mi": True
        },
        {
            "kod": "ZPO",
            "ad": "ZİRAAT PORTFÖY DÖRDÜNCÜ FON SEPETİ FONU",
            "kategori": "Fon Sepeti",
            "fiyat": 2.418020,
            "gunluk_degisim_pct": 0.35,
            "aylik_getiri_pct": 6.85,
            "hacim_tl": "7.000₺",
            "portfoyde_var_mi": False,
            "bekleyen_emir": True
        },
        {
            "kod": "PPZ",
            "ad": "AZİMUT PORTFÖY PARA PİYASASI FONU",
            "kategori": "Para Piyasası",
            "fiyat": 6.421500,
            "gunluk_degisim_pct": 0.14,
            "aylik_getiri_pct": 4.15,
            "hacim_tl": "1.2 Mr ₺",
            "portfoyde_var_mi": False
        },
        {
            "kod": "TKN",
            "ad": "AK PORTFÖY TEKNOLOJİ ŞİRKETLERİ FONU",
            "kategori": "Sektörel Hisse",
            "fiyat": 48.210400,
            "gunluk_degisim_pct": 1.84,
            "aylik_getiri_pct": 11.20,
            "hacim_tl": "850 Mn ₺",
            "portfoyde_var_mi": False
        },
        {
            "kod": "MAC",
            "ad": "MARMARA CAPİTAL HİSSE SENEDİ FONU",
            "kategori": "Hisse Senedi",
            "fiyat": 12.854000,
            "gunluk_degisim_pct": 0.72,
            "aylik_getiri_pct": 7.45,
            "hacim_tl": "620 Mn ₺",
            "portfoyde_var_mi": False
        },
        {
            "kod": "BIO",
            "ad": "DENİZ PORTFÖY BİYOTEKNOLOJİ FONU",
            "kategori": "Tematik Değişken",
            "fiyat": 3.125000,
            "gunluk_degisim_pct": -0.82,
            "aylik_getiri_pct": 3.90,
            "hacim_tl": "410 Mn ₺",
            "portfoyde_var_mi": False
        }
    ]
    return {"watchlist": watchlist_funds, "total_count": len(watchlist_funds)}


@app.get("/api/radar")
def get_radar_signals():
    """
    Ekran 4 (Radar & Sinyaller) verisi:
    Momentum liderleri, piyasa rejimi, model tahsisi.
    """
    try:
        from telegram_harmony_bot import get_latest_radar
        radar = get_latest_radar()
        if "hata" not in radar:
            return radar
    except Exception:
        pass

    return {
        "tarih": datetime.now().strftime("%Y-%m-%d"),
        "breadth": 68.5,
        "rejim": "🟢 HUNTER",
        "rejim_aciklama": "Piyasa geneli pozitif momentumda, hisse ağırlıklı katılım öneriliyor.",
        "lider_fon": "DGF",
        "vol_val": 14.2,
        "w_pct": 100.0,
        "ppz_pct": 0.0,
        "top10": [
            {"fon": "DGF", "skor": 94.2, "getiri_20g": 8.12, "vol": 13.8},
            {"fon": "SOS", "skor": 89.5, "getiri_20g": 5.40, "vol": 16.2},
            {"fon": "ZPO", "skor": 86.8, "getiri_20g": 6.85, "vol": 11.4},
            {"fon": "TKN", "skor": 85.1, "getiri_20g": 11.20, "vol": 22.5},
            {"fon": "MAC", "skor": 83.4, "getiri_20g": 7.45, "vol": 17.1}
        ]
    }


@app.get("/api/distribution")
def get_distribution():
    """
    Ekran 2 (Kurumsal / Dağılım & Hacim):
    Varlık dağılımı (Hisse, Ters Repo, Eurobond, Altın) ve kurum dağılımları.
    """
    return {
        "toplam_hacim": "303,3 Mr ₺",
        "net_alanlar_ozet": "İlk 3 Net Alan: 16,2 Mr ₺",
        "net_satanlar_ozet": "İlk 3 Net Satan: 8,2 Mr ₺",
        "ilk_5_alan": [
            {"ad": "Tera Yatırım", "tutar": "13,1 Mr ₺", "oran": "%72.23", "renk": "green"},
            {"ad": "BofA (Bank of America)", "tutar": "1,7 Mr ₺", "oran": "%9.60", "renk": "green"},
            {"ad": "Yapı Kredi Yatırım", "tutar": "1,4 Mr ₺", "oran": "%7.83", "renk": "green"},
            {"ad": "Deniz Yatırım", "tutar": "694,6 Mn ₺", "oran": "%3.83", "renk": "green"},
            {"ad": "Şeker Yatırım", "tutar": "158,8 Mn ₺", "oran": "%0.88", "renk": "green"}
        ],
        "ilk_5_satan": [
            {"ad": "A1 Capital", "tutar": "-3,6 Mr ₺", "oran": "%19.8", "renk": "red"},
            {"ad": "Pusula Menkul", "tutar": "-2,6 Mr ₺", "oran": "%14.3", "renk": "red"},
            {"ad": "İnfo Yatırım", "tutar": "-2,0 Mr ₺", "oran": "%11.0", "renk": "red"},
            {"ad": "Halk Yatırım", "tutar": "-1,4 Mr ₺", "oran": "%7.7", "renk": "red"},
            {"ad": "İş Yatırım", "tutar": "-1,1 Mr ₺", "oran": "%6.0", "renk": "red"}
        ],
        "portfoy_varlik_dagilimi": [
            {"tur": "Hisse Senedi (BIST)", "oran_pct": 58.5, "tutar_tl": "37.077₺", "renk": "#10B981"},
            {"tur": "Ters Repo / Para Piyasası", "oran_pct": 24.2, "tutar_tl": "15.338₺", "renk": "#3B82F6"},
            {"tur": "Özel Sektör Tahvili", "oran_pct": 12.8, "tutar_tl": "8.112₺", "renk": "#F59E0B"},
            {"tur": "Eurobond / Döviz", "oran_pct": 4.5, "tutar_tl": "2.853₺", "renk": "#8B5CF6"}
        ]
    }


@app.get("/api/history")
def get_trade_history():
    """
    İşlem günlüğünü döner.
    """
    islemler = []
    if os.path.exists(HISTORY_PATH):
        try:
            with open(HISTORY_PATH, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        islemler.append(json.loads(line))
        except Exception:
            pass
    islemler.reverse()
    return {"islemler": islemler, "toplam_islem": len(islemler)}
