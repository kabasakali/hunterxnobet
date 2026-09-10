# -*- coding: utf-8 -*-
"""
telegram_harmony_bot.py
=======================
HARMONY v2.1/v2.2 RESMİ TELEGRAM KONTROL BOTU (TAM NÖBETÇİ UYUMLU İŞLEM AKIŞI)
- Canlı TEFAS Resmi Detayları (Son Fiyat, Pay Adedi, Fon Büyüklüğü, Yatırımcı Sayısı, Kategori Derecesi, Pazar Payı)
- Günlük Değişim Takibi (Dünden Bugüne Pay ve Yatırımcı Farkları)
- Nöbetçi Bot Tarzı Esnek Manuel İşlem Girişi (Hem Butonla Hem Elle Adet/Tutar/Fiyat Girişi)
- %100 Butonlu Menüler + Tekil Fon Kodu Arama (Örn: 'SOS', 'MTD', 'GPG')
- Her 10 dakikada bir GitHub Cache kontrolü (09:55, 10:15, 12:45, 13:00, 18:30 Alarmları)
"""

import os
import sys
import time
import json
import threading
import datetime
import requests
import pandas as pd
import telebot
from telebot.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton
)

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
AUTHORIZED_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "7082317405")

if not BOT_TOKEN:
    print("[UYARI]: TELEGRAM_BOT_TOKEN ortam değişkeni tanımlanmamış!")

GITHUB_FIYAT_CACHE_URL = "https://raw.githubusercontent.com/kabasakali/fonbot-data/main/fiyat_cache.json"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def get_pivot_csv_path():
    olasi = [
        os.path.join(os.path.dirname(BASE_DIR), "serbest_fon_bot", "csv", "5_yil_pivot.csv"),
        os.path.join(os.path.dirname(BASE_DIR), "serbest_fon_bot", "5_yil_pivot.csv"),
        os.path.join(BASE_DIR, "5_yil_pivot.csv"),
        os.path.join(BASE_DIR, "flow_research", "data", "5_yil_pivot.csv")
    ]
    for p in olasi:
        if os.path.exists(p):
            return p
    return olasi[0]

PIVOT_CSV_PATH = get_pivot_csv_path()
PORTFOY_JSON_PATH = os.path.join(BASE_DIR, "portfoy_durumu.json")
ISLEM_LOG_PATH = os.path.join(BASE_DIR, "islem_gunlugu.jsonl")
DETAY_ARSIV_PATH = os.path.join(BASE_DIR, "flow_research", "data", "gunluk_detay_arsivi.json")

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")
user_states = {} # FSM işlem durumları

def otomatik_pivot_guncelle(zorla: bool = False):
    """Eksik günleri doğrudan TEFAS'tan çekip 5_yil_pivot.csv'yi sunucu üzerinde otomatik günceller."""
    try:
        from tefas import Crawler
        if not os.path.exists(PIVOT_CSV_PATH):
            return False, "Pivot dosyası bulunamadı"
            
        df_pivot = pd.read_csv(PIVOT_CSV_PATH, index_col=0, parse_dates=True).sort_index()
        son_kayitli_tarih = df_pivot.index[-1].date()
        bugun = datetime.date.today()
        
        hedef_tarih = bugun
        if bugun.weekday() == 5:
            hedef_tarih = bugun - datetime.timedelta(days=1)
        elif bugun.weekday() == 6:
            hedef_tarih = bugun - datetime.timedelta(days=2)
            
        now = datetime.datetime.now()
        if now.time() < datetime.time(9, 0) and hedef_tarih == bugun:
            hedef_tarih = bugun - datetime.timedelta(days=1)
            if hedef_tarih.weekday() == 6:
                hedef_tarih = hedef_tarih - datetime.timedelta(days=2)
                
        if not zorla and son_kayitli_tarih >= hedef_tarih:
            return True, f"Pivot güncel ({son_kayitli_tarih})"
            
        baslangic = (son_kayitli_tarih + datetime.timedelta(days=1)).strftime('%Y-%m-%d')
        bitis = bugun.strftime('%Y-%m-%d')
        
        crawler = Crawler()
        fonlar = list(df_pivot.columns)
        
        def fetch_single(f):
            try:
                c_df = crawler.fetch(start=baslangic, end=bitis, name=f)
                if c_df is not None and not c_df.empty:
                    return f, c_df[['date', 'price']].set_index('date')['price']
            except:
                pass
            return f, None
            
        with ThreadPoolExecutor(max_workers=15) as ex:
            results = list(ex.map(fetch_single, fonlar))
            
        new_data = {}
        for f, s in results:
            if s is not None and not s.empty:
                new_data[f] = s
                
        if not new_data:
            return False, "Yeni veri bulunamadı"
            
        df_new = pd.DataFrame(new_data)
        df_new.index = pd.to_datetime(df_new.index)
        df_new = df_new.sort_index()
        
        df_combined = pd.concat([df_pivot, df_new], axis=0)
        df_combined = df_combined[~df_combined.index.duplicated(keep='last')].sort_index()
        df_combined = df_combined.replace(0.0, np.nan).ffill()
        df_combined.to_csv(PIVOT_CSV_PATH)

        
        for p_alt in [os.path.join(BASE_DIR, "5_yil_pivot.csv"), os.path.join(os.path.dirname(BASE_DIR), "5_yil_pivot.csv")]:
            if os.path.exists(p_alt) and p_alt != PIVOT_CSV_PATH:
                df_combined.to_csv(p_alt)
                
        print(f"[OTO-PIVOT GÜNCELLEME]: {df_combined.index[-1].strftime('%Y-%m-%d')} tarihine eşitlendi.")
        return True, "Güncellendi"
    except Exception as e:
        print(f"[OTO-PIVOT HATA]: {e}")
        return False, str(e)

def github_verisini_guncelle(zorla: bool = False):
    return otomatik_pivot_guncelle(zorla=zorla)




# ─────────────────────────────────────────────────────────────────────────────
# 1. CANLI TEFAS FON BİLGİSİ VE GÜNLÜK ARŞİVLEME
# ─────────────────────────────────────────────────────────────────────────────

from concurrent.futures import ThreadPoolExecutor

def tum_fonlarin_detaylarini_topla():
    """Tüm fon evreninin (156 fon) TEFAS canlı detaylarını toplu olarak çeker ve arşivler."""
    if not os.path.exists(PIVOT_CSV_PATH):
        return 0
    try:
        df = pd.read_csv(PIVOT_CSV_PATH, index_col=0, parse_dates=True)
        fonlar = list(df.columns)
        
        def fetch_single(f):
            url = "https://www.tefas.gov.tr/api/funds/fonBilgiGetir"
            headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://www.tefas.gov.tr/"}
            try:
                r = requests.post(url, json={"fonKodu": f, "dil": "TR"}, headers=headers, timeout=5)
                if r.status_code == 200:
                    res = r.json().get("resultList", [])
                    if res:
                        data = res[0]
                        # TEFAS akşam takas/sıfır fiyat filtrelemesi (Geçici glitch engeli)
                        if data.get("sonFiyat", 0) <= 0.0001 or (data.get("gunlukGetiri") is not None and data.get("gunlukGetiri") <= -30.0):
                            return f, None
                        vd, av, sv = get_varlik_dagilimi_ve_valor(f)
                        data["varlik_dagilimi"] = dict(vd)
                        data["alisValor"] = av
                        data["satisValor"] = sv
                        return f, data
            except:
                pass
            return f, None
            
        with ThreadPoolExecutor(max_workers=10) as ex:
            results = list(ex.map(fetch_single, fonlar))
            
        os.makedirs(os.path.dirname(DETAY_ARSIV_PATH), exist_ok=True)
        arsiv = {}
        if os.path.exists(DETAY_ARSIV_PATH):
            try:
                with open(DETAY_ARSIV_PATH, "r", encoding="utf-8") as f:
                    arsiv = json.load(f)
            except:
                arsiv = {}
                
        bugun_str = datetime.date.today().strftime("%Y-%m-%d")
        basarili = 0
        for f_kod, data in results:
            if data:
                if f_kod not in arsiv:
                    arsiv[f_kod] = {}
                arsiv[f_kod][bugun_str] = data
                basarili += 1
                
        with open(DETAY_ARSIV_PATH, "w", encoding="utf-8") as f:
            json.dump(arsiv, f, indent=2, ensure_ascii=False)
            
        print(f"[TOPLU ARSIV]: {basarili} fon basariyla arsivlendi ({bugun_str})")
        return basarili
    except Exception as e:
        print(f"[TOPLU ARSIV HATA]: {e}")
        return 0


from bs4 import BeautifulSoup

def get_varlik_dagilimi_ve_valor(fon_kodu: str):
    """TEFAS fon-detayli-analiz sayfasından Varlık Dağılımı ve Valör Simülatörü verilerini çeker."""
    url = f"https://www.tefas.gov.tr/tr/fon-detayli-analiz/{fon_kodu}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    try:
        r = requests.get(url, headers=headers, timeout=6)
        if r.status_code != 200:
            return [], 1, 2
            
        soup = BeautifulSoup(r.text, "html.parser")
        
        # 1. Varlık Dağılımı Tablosu
        dagilim = []
        tbl = soup.find("table")
        if tbl:
            for tr in tbl.find_all("tr")[1:]:
                tds = tr.find_all("td")
                if len(tds) >= 2:
                    v_tur = tds[0].text.strip()
                    v_oran = tds[1].text.strip()
                    dagilim.append((v_tur, v_oran))
                    
        # 2. Valör Simülatörü Verileri
        alis_v, satis_v = 1, 2
        for el in soup.find_all(["div", "span", "p"]):
            t = el.text.strip()
            if "Alış Valörü" in t:
                try: alis_v = int("".join(filter(str.isdigit, t)) or 1)
                except: pass
            elif "Satış Valörü" in t:
                try: satis_v = int("".join(filter(str.isdigit, t)) or 2)
                except: pass
                
        return dagilim, alis_v, satis_v
    except Exception as e:
        print(f"[VARLIK DAGILIMI HATA]: {e}")
        return [], 1, 2





def get_tefas_canli_fon_bilgisi(fon_kodu: str):
    """TEFAS resmi fonBilgiGetir endpoint'inden canlı fon kartını çeker."""
    url = "https://www.tefas.gov.tr/api/funds/fonBilgiGetir"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Referer": "https://www.tefas.gov.tr/",
        "Content-Type": "application/json"
    }
    try:
        r = requests.post(url, json={"fonKodu": fon_kodu.upper(), "dil": "TR"}, headers=headers, timeout=6)
        if r.status_code == 200:
            res = r.json().get("resultList", [])
            if res:
                return res[0]
    except Exception as e:
        print(f"[TEFAS CANLI DETAY HATA]: {e}")
    return None


def arsivle_ve_karsilastir_fon_bilgisi(fon_kodu: str, canli_veri: dict):
    os.makedirs(os.path.dirname(DETAY_ARSIV_PATH), exist_ok=True)
    arsiv = {}
    if os.path.exists(DETAY_ARSIV_PATH):
        try:
            with open(DETAY_ARSIV_PATH, "r", encoding="utf-8") as f:
                arsiv = json.load(f)
        except:
            arsiv = {}
            
    bugun_str = datetime.date.today().strftime("%Y-%m-%d")
    fon_gecmisi = arsiv.get(fon_kodu, {})
    
    onceki_tarihler = [t for t in fon_gecmisi.keys() if t < bugun_str]
    fark_sonuc = {}
    
    if onceki_tarihler:
        son_onceki_tarih = sorted(onceki_tarihler)[-1]
        eski_veri = fon_gecmisi[son_onceki_tarih]
        
        d_pay = canli_veri.get("payAdet", 0) - eski_veri.get("payAdet", 0)
        d_kisi = canli_veri.get("yatirimciSayi", 0) - eski_veri.get("yatirimciSayi", 0)
        d_aum = canli_veri.get("portBuyukluk", 0) - eski_veri.get("portBuyukluk", 0)
        
        fark_sonuc = {
            "onceki_tarih": son_onceki_tarih,
            "d_pay": d_pay,
            "d_pay_pct": (d_pay / eski_veri.get("payAdet", 1)) * 100 if eski_veri.get("payAdet", 0) > 0 else 0,
            "d_kisi": d_kisi,
            "d_aum": d_aum,
            "d_aum_pct": (d_aum / eski_veri.get("portBuyukluk", 1)) * 100 if eski_veri.get("portBuyukluk", 0) > 0 else 0
        }
        
    fon_gecmisi[bugun_str] = canli_veri
    arsiv[fon_kodu] = fon_gecmisi
    
    try:
        with open(DETAY_ARSIV_PATH, "w", encoding="utf-8") as f:
            json.dump(arsiv, f, indent=2, ensure_ascii=False)
    except:
        pass
        
    return fark_sonuc

gun_isimleri = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]

def is_gunu_ekle(baslangic_dt, gun_sayisi):
    cur = baslangic_dt
    eklenen = 0
    while eklenen < gun_sayisi:
        cur += datetime.timedelta(days=1)
        if cur.weekday() < 5:
            eklenen += 1
    return cur

def valor_simulasyonu_metni_olustur(alis_v=1, satis_v=2):
    now = datetime.datetime.now()
    saat_str = now.strftime("%H:%M")
    bugun_weekday = now.weekday()
    
    if bugun_weekday < 5 and now.time() < datetime.time(13, 30):
        t0 = now.date()
        durum_baslik = f"Şu an (<b>{saat_str}</b>) ile <b>13:30</b> arasında emir girerseniz:"
    else:
        if bugun_weekday >= 5:
            gun_farki = 7 - bugun_weekday
            t0 = now.date() + datetime.timedelta(days=gun_farki)
            pzt_str = t0.strftime('%d.%m')
            durum_baslik = f"Hafta sonu girilen emirler ilk iş günü (<b>{pzt_str} Pazartesi</b>) işleme alınır:"
        else:
            t0 = is_gunu_ekle(now.date(), 1)
            gun_adi = gun_isimleri[t0.weekday()]
            t0_str = t0.strftime('%d.%m')
            durum_baslik = f"Saat 13:30 kesimi geçtiği için emriniz ilk iş günü (<b>{t0_str} {gun_adi}</b>) işleme alınır:"

    t_alis = is_gunu_ekle(t0, alis_v)
    t_satis = is_gunu_ekle(t0, satis_v)
    
    alis_gun_adi = gun_isimleri[t_alis.weekday()]
    satis_gun_adi = gun_isimleri[t_satis.weekday()]
    
    sim_metin = (
        f"• <b>Canlı Takas Simülasyonu:</b>\n"
        f"  └─ <i>{durum_baslik}</i>\n"
        f"     • 🛒 <b>ALIŞ :</b> <b>{t_alis.strftime('%d.%m.%Y')} ({alis_gun_adi})</b> fona geçer.\n"
        f"     • 💰 <b>SATIŞ:</b> <b>{t_satis.strftime('%d.%m.%Y')} ({satis_gun_adi})</b> para hesaba geçer."
    )
    return sim_metin


def tekil_fon_detayi_getir(fon_kodu: str) -> str:
    fon_kodu = fon_kodu.upper().strip()
    canli = get_tefas_canli_fon_bilgisi(fon_kodu)
    varlik_dagilimi, alis_val, satis_val = get_varlik_dagilimi_ve_valor(fon_kodu)

    
    r20, r40, r63, sira_no, skor_val = 0.0, 0.0, 0.0, "Belirsiz", 0.0
    if os.path.exists(PIVOT_CSV_PATH):
        try:
            df_csv = pd.read_csv(PIVOT_CSV_PATH, index_col=0, parse_dates=True)
            if fon_kodu in df_csv.columns:
                seri = df_csv[fon_kodu].dropna()
                if len(seri) > 20: r20 = (seri.iloc[-1] / seri.iloc[-21] - 1) * 100
                if len(seri) > 40: r40 = (seri.iloc[-1] / seri.iloc[-41] - 1) * 100
                if len(seri) > 63: r63 = (seri.iloc[-1] / seri.iloc[-64] - 1) * 100
                
                dt = df_csv.index[-1]
                sys.path.insert(0, BASE_DIR)
                from harmony_v2_2_live_production import HarmonyV22LiveProduction
                eng = HarmonyV22LiveProduction()
                skor_df = eng.golden.base_motor.base_motor.skor_df.loc[dt].dropna().sort_values(ascending=False)
                if fon_kodu in skor_df:
                    sira_no = list(skor_df.index).index(fon_kodu) + 1
                    skor_val = skor_df[fon_kodu]
        except:
            pass

    if not canli:
        return (
            f"❌ <b>{fon_kodu}</b> fonu TEFAS canlı sisteminde bulunamadı.\n\n"
            f"<i>Lütfen 3 harfli geçerli bir TEFAS fon kodu giriniz (Örn: SOS, MTD, GPG, CKL, PPZ).</i>"
        )

    fark = arsivle_ve_karsilastir_fon_bilgisi(fon_kodu, canli)
    
    fon_unvan = canli.get("fonUnvan", fon_kodu)
    son_fiyat = canli.get("sonFiyat", 0.0)
    gunluk_getiri = canli.get("gunlukGetiri", 0.0)
    pay_adet = canli.get("payAdet", 0)
    aum = canli.get("portBuyukluk", 0.0)
    kisi = canli.get("yatirimciSayi", 0)
    kategori = canli.get("fonKategori", "Değişken Fon")
    derece = f"{canli.get('kategoriDerece', '-')}/{canli.get('kategoriFonSay', '-')}"
    pazar_payi = canli.get("pazarPayi", 0.0)

    if r20 >= 10.0: durum_rozeti = "🟢 GÜÇLÜ RALLİ"
    elif r20 >= 3.0: durum_rozeti = "🟡 POZİTİF / DENGELİ"
    else: durum_rozeti = "🔴 ZAYIF / DÜŞÜŞTE"

    msg = (
        f"📋 <b>TEFAS RESMİ FON ANALİZİ: {fon_kodu}</b>\n"
        f"<b>{fon_unvan}</b>\n"
        f"<code>═════════════════════════════════════════</code>\n"
        f"📌 <b>FON VE PAZAR BİLGİSİ</b>\n"
        f"• <b>Son Birim Fiyat  :</b> <b>{son_fiyat:.6f} TL</b>\n"
        f"• <b>Günlük Getiri     :</b> <b>%{gunluk_getiri:+.2f}</b>\n"
        f"• <b>Kategorisi        :</b> {kategori}\n"
        f"• <b>Kategori Derecesi :</b> <b>{derece}</b> (Son 1 Yıl)\n"
        f"• <b>Pazar Payı        :</b> %{pazar_payi:.2f}\n"
        f"<code>─────────────────────────────────────────</code>\n"
        f"👥 <b>SERMAYE VE YATIRIMCI AKIŞI</b>\n"
        f"• <b>Yatırımcı Sayısı  :</b> <b>{kisi:,} Kişi</b>\n"
        f"• <b>Tedavüldeki Pay   :</b> <b>{pay_adet:,} Adet</b>\n"
        f"• <b>Fon Toplam Değeri :</b> <b>{aum:,.2f} TL</b>\n"
    )

    if fark:
        msg += (
            f"  └─ <i>Dünden Bugüne Değişim ({fark.get('onceki_tarih')}):</i>\n"
            f"     • 👥 <b>Yatırımcı:</b> <code>{fark['d_kisi']:+d} Kişi</code>\n"
            f"     • 📦 <b>Pay     :</b> <code>{fark['d_pay']:+,d} Adet (%{fark['d_pay_pct']:+.2f})</code>\n"
            f"     • 💰 <b>Büyüklük:</b> <code>{fark['d_aum']:+,.0f} TL (%{fark['d_aum_pct']:+.2f})</code>\n"
        )
    else:
        msg += f"  └─ <i>(Bugün ilk kayıt alındı, yarından itibaren günlük değişimler burada listelenecek)</i>\n"

    # Varlık Dağılımı Bölümü
    if varlik_dagilimi:
        msg += f"<code>─────────────────────────────────────────</code>\n"
        msg += f"🍰 <b>FON VARLIK DAĞILIMI (PORTFÖY İÇERİĞİ)</b>\n"
        for v_adi, v_oran in varlik_dagilimi[:5]:
            msg += f"• <b>{v_adi}:</b> <code>{v_oran}</code>\n"

    # Valör Simülatörü Bölümü
    msg += f"<code>─────────────────────────────────────────</code>\n"
    msg += f"⏳ <b>VALÖR HESAPLAMA SİMÜLATÖRÜ</b>\n"
    msg += f"• <b>Alış Valörü :</b> <b>T+{alis_val}</b> | <b>Satış Valörü:</b> <b>T+{satis_val}</b>\n"
    msg += valor_simulasyonu_metni_olustur(alis_val, satis_val) + "\n"

    msg += (
        f"<code>─────────────────────────────────────────</code>\n"
        f"📈 <b>İVME VE HARMONY LİGİ</b>\n"
        f"• <b>Lig Sıralaması    :</b> <b>{sira_no} / 151</b> (Puan: <code>{skor_val:.3f}</code>)\n"
        f"• <b>Teknik Durum      :</b> <code>[{durum_rozeti}]</code>\n"
        f"• <b>20G Getiri        :</b> <b>%{r20:+.2f}</b> (Kısa Vade)\n"
        f"• <b>63G Getiri        :</b> <b>%{r63:+.2f}</b> (Orta Vade)\n"
        f"<code>═════════════════════════════════════════</code>"
    )
    return msg


def get_fon_tum_getiri_periyotlari(fon_kodu: str) -> str:

    fon_kodu = fon_kodu.upper().strip()
    canli = get_tefas_canli_fon_bilgisi(fon_kodu)
    son_fiyat = canli.get("sonFiyat", 0.0) if canli else 0.0
    fon_unvan = canli.get("fonUnvan", fon_kodu) if canli else fon_kodu
    
    msg = (
        f"📊 <b>{fon_kodu} FON İÇİ GETİRİ VE ENSTRÜMAN ANALİZİ</b>\n"
        f"🏢 <b>{fon_unvan}</b>\n"
        f"💰 <b>Son Birim Fiyat:</b> <b>{son_fiyat:.6f} TL</b>\n"
        f"<code>═════════════════════════════════════════</code>\n"
        f"📈 <b>DÖNEMSEL GETİRİ TABLOSU:</b>\n"
    )
    
    if os.path.exists(PIVOT_CSV_PATH):
        try:
            df = pd.read_csv(PIVOT_CSV_PATH, index_col=0, parse_dates=True)
            if fon_kodu in df.columns:
                seri = df[fon_kodu].dropna()
                p_son = son_fiyat if son_fiyat > 0 else (seri.iloc[-1] if not seri.empty else 1.0)
                
                r_1g = canli.get("gunlukGetiri", 0.0) if canli else ((p_son / seri.iloc[-2] - 1) * 100 if len(seri) >= 2 else 0.0)
                r_1h = (p_son / seri.iloc[-6] - 1) * 100 if len(seri) >= 6 else 0.0
                r_1a = (p_son / seri.iloc[-22] - 1) * 100 if len(seri) >= 22 else 0.0
                r_3a = (p_son / seri.iloc[-64] - 1) * 100 if len(seri) >= 64 else 0.0
                r_6a = (p_son / seri.iloc[-127] - 1) * 100 if len(seri) >= 127 else 0.0
                
                # YTD
                yil_basi_tarih = [d for d in seri.index if hasattr(d, 'year') and d.year == seri.index[-1].year]
                p_ybb = seri.loc[yil_basi_tarih[0]] if yil_basi_tarih else seri.iloc[-1]
                r_ybb = (p_son / p_ybb - 1) * 100 if p_ybb > 0 else 0.0
                
                r_1y = (p_son / seri.iloc[-253] - 1) * 100 if len(seri) >= 253 else 0.0
                r_3y = (p_son / seri.iloc[-757] - 1) * 100 if len(seri) >= 757 else 0.0
                
                msg += f"• <b>1 Günlük Getiri  :</b> <b>%{r_1g:+.2f}</b>\n"
                msg += f"• <b>1 Haftalık Getiri:</b> <b>%{r_1h:+.2f}</b>\n"
                msg += f"• <b>1 Aylık Getiri   :</b> <b>%{r_1a:+.2f}</b>\n"
                msg += f"• <b>3 Aylık Getiri   :</b> <b>%{r_3a:+.2f}</b>\n"
                msg += f"• <b>6 Aylık Getiri   :</b> <b>%{r_6a:+.2f}</b>\n"
                msg += f"• <b>Yılbaşı (YTD)    :</b> <b>%{r_ybb:+.2f}</b>\n"
                msg += f"• <b>1 Yıllık Getiri  :</b> <b>%{r_1y:+.2f}</b>\n"
                if r_3y != 0.0:
                    msg += f"• <b>3 Yıllık Getiri  :</b> <b>%{r_3y:+.2f}</b>\n"
        except Exception as e:
            msg += f"<i>(Getiri hesaplama notu: {e})</i>\n"

    varlik_dagilimi, _, _ = get_varlik_dagilimi_ve_valor(fon_kodu)
    if varlik_dagilimi:
        msg += f"<code>─────────────────────────────────────────</code>\n"
        msg += f"🍰 <b>PORTFÖY İÇİ ENSTRÜMAN VE VARLIK DAĞILIMI:</b>\n"
        for v_adi, v_oran in varlik_dagilimi:
            msg += f"• <b>{v_adi}:</b> <code>{v_oran}</code>\n"
            
    msg += f"<code>─────────────────────────────────────────</code>\n"
    msg += (
        f"📑 <b>KAP PORTFÖY DAĞILIM RAPORU:</b>\n"
        f"<i>Fonun tuttuğu tekil hisse senetleri, yabancı hisseler ve vadeli işlemler SPK kuralları gereği her ayın ilk haftası KAP'ta ilan edilir.</i>\n"
        f"<code>═════════════════════════════════════════</code>"
    )
    return msg


def get_latest_radar():
    try:
        otomatik_pivot_guncelle()
        sys.path.insert(0, BASE_DIR)
        from harmony_v2_2_live_production import HarmonyV22LiveProduction
        eng = HarmonyV22LiveProduction()
        dec = eng.get_current_live_decision()
        
        rejim_rozeti = "🟢 HUNTER" if dec["rejim"] == "HUNTER" else ("🟡 NÖBETÇİ" if dec["rejim"] == "MOMENTUM" else "🔴 SAVUNMA")
        
        return {
            "tarih": dec["tarih"],
            "breadth": dec["breadth"],
            "rejim": rejim_rozeti,
            "rejim_aciklama": dec["rejim_aciklama"],
            "lider_fon": dec["aktif_fon"],
            "vol_val": dec["vol_val"],
            "w_pct": dec["w_pct"],
            "ppz_pct": dec["ppz_pct"],
            "top10": dec["top10"]
        }
    except Exception as e:
        return {"hata": str(e)}


def piyasa_isisi_metni_olustur() -> str:
    arsiv_path = DETAY_ARSIV_PATH
    arsiv = {}
    if os.path.exists(arsiv_path):
        try:
            with open(arsiv_path, "r", encoding="utf-8") as f:
                arsiv = json.load(f)
        except:
            arsiv = {}
            
    bugun_str = datetime.date.today().strftime("%Y-%m-%d")
    kazananlar, kaybedenler, notr, tum_getiriler = [], [], [], []
    
    for fon, gunler in arsiv.items():
        if bugun_str in gunler:
            g = gunler[bugun_str]
        elif gunler:
            son_tarih = sorted(gunler.keys())[-1]
            g = gunler[son_tarih]
        else:
            continue
            
        ret = g.get("gunlukGetiri", 0.0)
        son_fiyat = g.get("sonFiyat", 1.0)
        unvan = g.get("fonUnvan", fon)
        
        # TEFAS Veri Temizleme & Anomali Filtresi:
        # Fiyatı 0 olan veya anlık TEFAS güncelleme hatasıyla -%30'dan fazla düşen (örneğin -%100 glitch) kayıtları filtrele
        if ret is None or ret <= -30.0 or ret >= 100.0 or son_fiyat <= 0.0001:
            continue
            
        tum_getiriler.append(ret)
        if ret > 0:
            kazananlar.append((fon, ret, unvan))
        elif ret < 0:
            kaybedenler.append((fon, ret, unvan))
        else:
            notr.append((fon, ret, unvan))
            
    kazananlar.sort(key=lambda x: x[1], reverse=True)
    kaybedenler.sort(key=lambda x: x[1])
    
    toplam = len(kazananlar) + len(kaybedenler) + len(notr)
    yesil_pct = (len(kazananlar) / toplam * 100) if toplam > 0 else 0
    kirmizi_pct = (len(kaybedenler) / toplam * 100) if toplam > 0 else 0
    ort_getiri = (sum(tum_getiriler) / len(tum_getiriler)) if tum_getiriler else 0
    
    if yesil_pct >= 70:
        isi_ikon = "🔥"
        isi_durum = "AŞIRI SICAK (Güçlü Boğa İştahı)"
    elif yesil_pct >= 50:
        isi_ikon = "🌤️"
        isi_durum = "ILIK / POZİTİF (Alıcılı Seyir)"
    elif yesil_pct >= 35:
        isi_ikon = "⛅"
        isi_durum = "SERİN (Düzeltme / Karışık)"
    else:
        isi_ikon = "❄️"
        isi_durum = "SOĞUK (Ayı / Satış Baskısı)"
        
    msg = (
        f"════════ 🌡️ <b>PİYASA ISISI & GETİRİ HARİTASI</b> ════════\n"
        f"📅 <b>Tarih:</b> {datetime.date.today().strftime('%d.%m.%Y')}\n"
        f"🌡️ <b>Piyasa Nabzı:</b> {isi_ikon} <b>{isi_durum}</b>\n"
        f"📊 <b>Ortalama Günlük Getiri:</b> <b>%{ort_getiri:+.2f}</b>\n"
        f"<code>─────────────────────────────────────────</code>\n"
        f"🟢 <b>Kârda Kapananlar  :</b> <b>{len(kazananlar)} Fon (%{yesil_pct:.1f})</b>\n"
        f"🔴 <b>Zararda Kapananlar :</b> <b>{len(kaybedenler)} Fon (%{kirmizi_pct:.1f})</b>\n"
        f"⚪ <b>Nötr / Değişmeyen  :</b> <b>{len(notr)} Fon</b>\n"
        f"<code>─────────────────────────────────────────</code>\n"
        f"🏆 <b>GÜNÜN EN ÇOK KAZANDIRAN İLK 5 FONU:</b>\n"
    )
    for i, (f, r, u) in enumerate(kazananlar[:5], 1):
        msg += f"<b>{i}. {f}</b> : 🟢 <b>%{r:+.2f}</b> <i>({u[:24]})</i>\n"
        
    msg += f"<code>─────────────────────────────────────────</code>\n"
    msg += f"📉 <b>GÜNÜN EN ÇOK GERİLEYEN İLK 5 FONU:</b>\n"
    for i, (f, r, u) in enumerate(kaybedenler[:5], 1):
        msg += f"<b>{i}. {f}</b> : 🔴 <b>%{r:+.2f}</b> <i>({u[:24]})</i>\n"
        
    msg += f"<code>═════════════════════════════════════════</code>"
    return msg

# ─────────────────────────────────────────────────────────────────────────────
# 2. BUTON KLAVYELERİ (SADE & 1-2 KELİMELİK)
# ─────────────────────────────────────────────────────────────────────────────

def ana_menu_klavyesi():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        KeyboardButton("🧭 HARMONY"),
        KeyboardButton("💼 PORTFÖY")
    )
    markup.add(
        KeyboardButton("🌡️ PİYASA ISISI"),
        KeyboardButton("➕ İŞLEM GİR")
    )
    markup.add(
        KeyboardButton("⏳ VALÖR ONAY"),
        KeyboardButton("📜 GEÇMİŞ")
    )
    markup.add(
        KeyboardButton("📈 REJİMLER"),
        KeyboardButton("⚙️ SİSTEM")
    )
    return markup


def valor_onay_listesi_klavyesi(takastakiler):
    markup = InlineKeyboardMarkup(row_width=2)
    for idx, item in enumerate(takastakiler):
        fon = item.get("hedef_fon", item.get("fon", "Bilinmeyen"))
        tutar = item.get("tutar_tl", item.get("tutar", 0))
        adet = item.get("pay_adedi", 0)
        btn_onay = f"🟢 Hesaba Geçti: {fon}"
        btn_iptal = f"❌ İptal Et: {fon}"
        markup.add(
            InlineKeyboardButton(btn_onay, callback_data=f"valor_tamamla_{idx}"),
            InlineKeyboardButton(btn_iptal, callback_data=f"valor_iptal_{idx}")
        )
    markup.add(InlineKeyboardButton("🔙 Kapat", callback_data="btn_kapat"))
    return markup


# ─────────────────────────────────────────────────────────────────────────────
# 3. MESAJ VE BUTON İŞLEYİCİLERİ
# ─────────────────────────────────────────────────────────────────────────────

def yetki_kontrol(message):
    if str(message.chat.id) != str(AUTHORIZED_CHAT_ID):
        bot.send_message(message.chat.id, "⛔ <b>Erişim Engellendi:</b> Bu bot kişiye özel ve şifrelidir.")
        return False
    return True

@bot.message_handler(commands=['start', 'yardim'])
def cmd_start(message):
    if not yetki_kontrol(message): return
    msg = (
        "🦅 <b>HARMONY v2.1/v2.2 CANLI YATIRIM ASİSTANI</b>\n\n"
        "Hoş geldiniz İsmail Bey!\n\n"
        "• Aşağıdaki 1-2 kelimelik butonlarla portföyü ve radar kararlarını yönetebilirsiniz.\n"
        "• <b>➕ İŞLEM GİR:</b> Bankadan aldığınız veya sattığınız fonu Pay Adedi veya TL Tutarı ile manuel olarak girebilirsiniz.\n"
        "• <b>Tekil Fon Sorgulama:</b> Merak ettiğiniz fonun kodunu (Örn: <code>SOS</code>, <code>MTD</code>, <code>GPG</code>) yazarak 3 sekmedeki tüm resmi TEFAS verilerini görebilirsiniz.\n\n"
        "<i>Lütfen aşağıdaki menüden bir işlem seçin:</i>"
    )
    bot.send_message(message.chat.id, msg, reply_markup=ana_menu_klavyesi())

@bot.message_handler(commands=['arsivle', 'arsiv'])
def cmd_arsivle(message):
    if not yetki_kontrol(message): return
    bot.send_message(message.chat.id, "⏳ <b>TEFAS'taki TÜM fonlar ve portföy dağılımları taranıyor...</b>\n<i>Bu işlem arka planda ~15-20 saniye sürecektir.</i>")
    def run_archive():
        try:
            sys.path.insert(0, os.path.join(BASE_DIR, "flow_research", "collectors"))
            from tefas_tum_arsivleyici import tum_tefas_arsivle
            res = tum_tefas_arsivle()
            bot.send_message(
                message.chat.id,
                f"✅ <b>TEFAS EKSİKSİZ ARŞİVLEME TAMAMLANDI!</b>\n"
                f"<code>═════════════════════════════════════════</code>\n"
                f"📅 <b>Tarih          :</b> {res.get('tarih')}\n"
                f"📦 <b>Arşivlenen Fon :</b> <b>{res.get('basarili')} / {res.get('toplam')} adet</b>\n"
                f"⏱️ <b>İşlem Süresi    :</b> {res.get('sure_saniye')} saniye\n"
                f"📊 <b>Kapsam         :</b> Fiyat, 1A/3A/6A/1Y Getiriler, AUM, Pay, Yatırımcı ve <b>Tam Portföy Varlık Dağılımı</b>\n"
                f"<code>═════════════════════════════════════════</code>\n"
                f"<i>Not: Canlı 156 fonluk alım/satım havuzumuz bağımsız tutulmuştur.</i>"
            )
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ Arşivleme sırasında hata: {e}")
            
    import threading
    threading.Thread(target=run_archive, daemon=True).start()


@bot.message_handler(func=lambda msg: msg.text in ["🌡️ PİYASA ISISI", "PİYASA ISISI", "/isi", "isi", "İSİ"])
def menu_piyasa_isisi(message):
    if not yetki_kontrol(message): return
    msg = piyasa_isisi_metni_olustur()
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("🔄 Isıyı Güncelle", callback_data="btn_piyasa_isisi_yenile"),
        InlineKeyboardButton("🧭 Harmony Radarı", callback_data="btn_harmony_ac")
    )
    bot.send_message(message.chat.id, msg, reply_markup=markup)


@bot.message_handler(func=lambda msg: msg.text == "🧭 HARMONY")
def menu_harmony(message):

    if not yetki_kontrol(message): return
    try:
        radar = get_latest_radar()
        if "hata" in radar:
            bot.send_message(message.chat.id, f"⚠️ Radar hatası: {radar['hata']}")
            return
            
        sys.path.insert(0, BASE_DIR)
        from canli_muhasebe_motoru import CanliMuhasebeMotoru
        muh = CanliMuhasebeMotoru()
        durum = muh.portfoy_degerini_guncelle()
        
        eldeki_dict = durum.get("eldeki_fonlar", {})
        eldeki_fon = list(eldeki_dict.keys())[0] if isinstance(eldeki_dict, dict) and eldeki_dict else "PPZ"
        
        msg = (
            f"════════ 🦅 <b>HARMONY ALFA RADARI</b> ════════\n"
            f"📅 <b>Tarih:</b> {radar['tarih']}\n"
            f"🚦 <b>DURUM:</b> <code>[{radar['rejim']}]</code> ({radar['rejim_aciklama']})\n"
            f"📊 <b>Piyasa Genişliği:</b> %{radar['breadth']:.1f} (Geniş Katılım)\n\n"
            f"📍 <b>Mevcut Konumunuz:</b> <b>{eldeki_fon}</b>\n"
        )
        
        lider = radar.get("lider_fon", "DGF")
        if "DGF" in eldeki_dict and "SOS" in eldeki_dict:
            msg += f"🎯 <b>Tavsiye:</b> <b>SOS ve DGF Birlikte Taşınıyor</b> (Podyumun ilk 2 lideri portföyde)\n"
        elif eldeki_fon == lider:
            msg += f"🎯 <b>Tavsiye:</b> <b>{eldeki_fon} POZİSYONUNU KORU</b> (Zirve Lideri Pozisyonundasınız)\n"
        elif eldeki_fon == "SOS":
            msg += f"🎯 <b>Tavsiye:</b> <b>SOS Pozisyonunu Koru</b> (Trend Güçlü, DGF Alımıyla Dengeleniyor)\n"
        elif eldeki_fon == "PPZ":
            msg += f"🎯 <b>Tavsiye:</b> <b>Lider {lider} Fonuna Giriş Yapılabilir</b>\n"
        else:
            msg += f"🎯 <b>Tavsiye:</b> Pozisyonu koruyun, rotasyon barajı takip ediliyor.\n"
            
        tahsis_str = f"%{radar['w_pct']:.0f} {radar['lider_fon']}" + (f" + %{radar['ppz_pct']:.0f} PPZ" if radar['ppz_pct'] > 0 else "")
        msg += f"🛡️ <b>Model E Güvenli Tahsisi:</b> <b>{tahsis_str}</b> <i>(20G Oynaklık: %{radar['vol_val']:.1f})</i>\n\n"
            
        msg += f"🏆 <b>GÜNCEL LİDERLER SIRALAMASI:</b>\n"
        msg += f"<code>─────────────────────────────────────────</code>\n"
        
        for i, item in enumerate(radar["top10"][:7], 1):
            etiket = "🟢 SİZDEKİ" if item["fon"] in eldeki_dict else ("⭐ 1. LİDER" if item["fon"] == lider else "")
            vol_s = f"Vol: %{item.get('vol_pct', 20.0):.0f}"
            msg += (
                f"<b>{i}. {item['fon']}</b> | Puan: <code>{item['skor']:.3f}</code> "
                f"| 20G: <b>%{item['r20']:+.1f}</b> | {vol_s} {etiket}\n"
            )
        msg += f"<code>─────────────────────────────────────────</code>\n"
        
        try:
            sys.path.insert(0, BASE_DIR)
            from makro_veri_motoru import get_canli_makro_gostergeler
            makro = get_canli_makro_gostergeler()
            msg += (
                f"🌐 <b>CANLI PİYASA BENCHMARK:</b>\n"
                f"• USD/TRY: <code>{makro['usd_try']} TL</code> | BIST 100: <code>{makro['bist_100']:,.0f}</code> | Rf (Faiz): <code>%{makro['rf_yillik_pct']}</code>\n"
                f"🔍 <i>[{makro['kaynak']} | {makro['zaman']}]</i>\n"
            )
        except Exception:
            pass
            
        msg += f"<i>(Detaylı TEFAS verisi için aşağıdaki butonlara basabilir veya fon kodunu yazabilirsiniz)</i>"

        
        markup = InlineKeyboardMarkup(row_width=3)
        btns = [InlineKeyboardButton(f"🔎 {f['fon']}", callback_data=f"detay_{f['fon']}") for f in radar["top10"][:6]]
        markup.add(*btns)
        
        bot.send_message(message.chat.id, msg, reply_markup=markup)
    except Exception as e:
        bot.send_message(message.chat.id, f"⚠️ Bir hata oluştu: {e}")


@bot.message_handler(func=lambda msg: msg.text == "💼 PORTFÖY")
def menu_portfoy(message):
    if not yetki_kontrol(message): return
    try:
        sys.path.insert(0, BASE_DIR)
        from canli_muhasebe_motoru import CanliMuhasebeMotoru
        muh = CanliMuhasebeMotoru()
        durum = muh.portfoy_degerini_guncelle()
        
        toplam_tl = durum.get("toplam_portfoy_tl", 0.0)
        zirve_tl = durum.get("zirve_portfoy_tl", toplam_tl)
        cur_dd = durum.get("mevcut_cekilme_pct", 0.0)
        ks_aktif = durum.get("kill_switch_aktif", False)
        
        if ks_aktif:
            ks_status = f"🚨 <b>TETİKLENDİ / TEHLİKE!</b> (PPZ Savunmasına Geçiniz)"
        else:
            ks_status = f"🟢 <b>Güvenli Bölgede</b>"
            
        eldeki_dict = durum.get("eldeki_fonlar", {})
        takasta = durum.get("takasta_bekleyen_islemler", [])
        
        msg = (
            f"💼 <b>CANLI PORTFÖY DURUMUNUZ</b>\n"
            f"<code>─────────────────────────────────────────</code>\n"
            f"💰 <b>Toplam Portföy Değeri :</b> <b>{toplam_tl:,.2f} TL</b>\n"
            f"🏔️ <b>Görülen Zirve Değer   :</b> {zirve_tl:,.2f} TL\n"
            f"📉 <b>Tepe Çekilmesi (DD)   :</b> %{cur_dd:.2f}\n"
            f"🛡️ <b>Kill-Switch Durumu     :</b> {ks_status} (Eşik: %4.50)\n"
            f"<code>─────────────────────────────────────────</code>\n\n"
            f"📦 <b>ELDEKİ FONLAR:</b>\n"
        )

        
        if eldeki_dict:
            for fon_kodu, p in eldeki_dict.items():
                adet = p.get("pay_adedi", 0.0)
                maliyet = p.get("maliyet_fiyati", 0.0)
                nav = p.get("son_nav", 0.0)
                tutar = p.get("guncel_deger_tl", 0.0)
                
                maliyet_toplam = adet * maliyet if maliyet > 0 else tutar
                kar_zarar_tl = tutar - maliyet_toplam
                kar_zarar_pct = (kar_zarar_tl / maliyet_toplam * 100.0) if maliyet_toplam > 0 else 0.0
                kz_ikon = "🟢" if kar_zarar_tl >= 0 else "🔴"
                
                msg += (
                    f"• <b>{fon_kodu}</b> : <b>{adet:,.2f} Pay</b>\n"
                    f"  ├─ <b>Ort. Maliyet :</b> {maliyet:.6f} TL\n"
                    f"  ├─ <b>Son Fiyat    :</b> {nav:.6f} TL\n"
                    f"  ├─ <b>Güncel Tutar :</b> <b>{tutar:,.2f} TL</b>\n"
                    f"  └─ <b>Kâğıt Kârı   :</b> {kz_ikon} {kar_zarar_tl:+,.2f} TL (<b>%{kar_zarar_pct:+.2f}</b>)\n\n"
                )
        else:
            msg += f"• <i>Portföyde fon bulunmuyor (Nakit T0)</i>\n"
            
        if takasta:
            msg += f"\n⏳ <b>TAKASTA BEKLEYEN İŞLEMLER:</b> {len(takasta)} Adet\n"
            for t in takasta:
                msg += f"  └─ {t.get('hedef_fon', 'Fon')}: {t.get('pay_adedi', 0):,.2f} Pay ({t.get('tutar_tl', 0):,.2f} TL)\n"
                
        markup = InlineKeyboardMarkup(row_width=2)
        markup.add(
            InlineKeyboardButton("🔄 Fiyatları Yenile", callback_data="btn_portfoy_yenile"),
            InlineKeyboardButton("⏳ Valörleri Gör", callback_data="btn_valor_menusu")
        )
        
        bot.send_message(message.chat.id, msg, reply_markup=markup)
    except Exception as e:
        bot.send_message(message.chat.id, f"⚠️ Portföy okuma hatası: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# 4. NÖBETÇİ TARZI MANUEL İŞLEM GİRİŞ AKIŞI (FSM STEP HANDLERS)
# ─────────────────────────────────────────────────────────────────────────────

@bot.message_handler(func=lambda msg: msg.text == "➕ İŞLEM GİR")
def islem_gir_basla(message):
    if not yetki_kontrol(message): return
    markup = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True, row_width=2)
    markup.add("🟢 ALIŞ", "🔴 SATIŞ")
    markup.add("❌ İPTAL")
    bot.send_message(message.chat.id, "Lütfen işlem türünü seçin:", reply_markup=markup)
    bot.register_next_step_handler(message, islem_gir_tip)

def islem_gir_tip(message):
    if message.text in ["❌ İPTAL", "İPTAL"]:
        return bot.send_message(message.chat.id, "İşlem iptal edildi.", reply_markup=ana_menu_klavyesi())
        
    tip = "ALIS" if "ALIŞ" in message.text or "ALIS" in message.text else ("SATIS" if "SATIŞ" in message.text or "SATIS" in message.text else None)
    if not tip:
        return bot.send_message(message.chat.id, "Geçersiz işlem tipi seçildi.", reply_markup=ana_menu_klavyesi())
        
    user_states[message.chat.id] = {"tip": tip}
    
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=3)
    markup.add("SOS", "MTD", "CKL", "GPG", "DGF", "PPZ")
    markup.add("❌ İPTAL")
    
    bot.send_message(
        message.chat.id,
        "Lütfen <b>FON KODUNU</b> seçin veya klavyeden yazın (Örn: <code>SOS</code>):",
        reply_markup=markup
    )
    bot.register_next_step_handler(message, islem_gir_fon)

def islem_gir_fon(message):
    if message.text in ["❌ İPTAL", "İPTAL"]:
        return bot.send_message(message.chat.id, "İşlem iptal edildi.", reply_markup=ana_menu_klavyesi())
        
    fon = message.text.upper().strip()
    user_states[message.chat.id]["fon"] = fon
    
    # TEFAS son fiyatını çek
    canli = get_tefas_canli_fon_bilgisi(fon)
    fiyat = canli.get("sonFiyat", 1.0) if canli else 1.0
    user_states[message.chat.id]["fiyat"] = fiyat
    
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("📦 PAY ADEDİ GİR", "💵 TL TUTARI GİR")
    markup.add("❌ İPTAL")
    
    bot.send_message(
        message.chat.id,
        f"📍 Seçilen Fon: <b>{fon}</b>\n"
        f"📊 Güncel TEFAS Fiyatı: <b>{fiyat:.6f} TL</b>\n\n"
        f"İşlemi <b>Pay Adedi</b> olarak mı, yoksa <b>TL Tutarı</b> olarak mı girmek istersiniz?",
        reply_markup=markup
    )
    bot.register_next_step_handler(message, islem_gir_girdi_tipi)

def islem_gir_girdi_tipi(message):
    if message.text in ["❌ İPTAL", "İPTAL"]:
        return bot.send_message(message.chat.id, "İşlem iptal edildi.", reply_markup=ana_menu_klavyesi())
        
    if "PAY" in message.text or "ADET" in message.text:
        user_states[message.chat.id]["girdi_turu"] = "ADET"
        bot.send_message(
            message.chat.id,
            "Lütfen satın aldığınız/sattığınız <b>PAY ADEDİNİ</b> girin (Örn: <code>15213.5</code> veya <code>10000</code>):",
            reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("❌ İPTAL")
        )
        bot.register_next_step_handler(message, islem_gir_deger)
    else:
        user_states[message.chat.id]["girdi_turu"] = "TUTAR"
        markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        markup.add("10000", "25000", "50000", "100000")
        markup.add("❌ İPTAL")
        bot.send_message(
            message.chat.id,
            "Lütfen işlem yapmak istediğiniz <b>TL TUTARINI</b> girin veya seçin (Örn: <code>25000</code>):",
            reply_markup=markup
        )
        bot.register_next_step_handler(message, islem_gir_deger)

def islem_gir_deger(message):
    if message.text in ["❌ İPTAL", "İPTAL"]:
        return bot.send_message(message.chat.id, "İşlem iptal edildi.", reply_markup=ana_menu_klavyesi())
        
    try:
        val_str = message.text.replace('TL', '').replace('tl', '').replace('.', '').replace(',', '.').strip()
        # Eğer float dönüşümü gerekiyorsa
        ham_metin = message.text.replace('TL', '').replace('tl', '').strip()
        if ',' in ham_metin and '.' in ham_metin:
            ham_metin = ham_metin.replace('.', '').replace(',', '.')
        elif ',' in ham_metin:
            ham_metin = ham_metin.replace(',', '.')
            
        deger = float(ham_metin)
        state = user_states[message.chat.id]
        fiyat = state.get("fiyat", 1.0)
        
        if state["girdi_turu"] == "ADET":
            adet = deger
            tutar = adet * fiyat
        else:
            tutar = deger
            adet = tutar / fiyat if fiyat > 0 else 0
            
        state["adet"] = adet
        state["tutar"] = tutar
        
        markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        markup.add(f"✅ EVET ({fiyat:.6f} TL)", "✏️ FARKLI FİYAT YAZ")
        markup.add("❌ İPTAL")
        
        bot.send_message(
            message.chat.id,
            f"📋 <b>İŞLEM ÖZETİ:</b>\n"
            f"• <b>Fon      :</b> <b>{state['fon']}</b> ({state['tip']})\n"
            f"• <b>Pay Adedi:</b> <b>{adet:,.2f} Pay</b>\n"
            f"• <b>Toplam TL:</b> <b>{tutar:,.2f} TL</b>\n"
            f"• <b>Birim Fiyat:</b> <b>{fiyat:.6f} TL</b>\n\n"
            f"Birim fiyat olarak <b>{fiyat:.6f} TL</b> onaylansın mı?",
            reply_markup=markup
        )
        bot.register_next_step_handler(message, islem_gir_fiyat_onay)
    except Exception as e:
        bot.send_message(message.chat.id, f"⚠️ Geçersiz sayı girdiniz ({e}). Lütfen tekrar deneyin:")
        bot.register_next_step_handler(message, islem_gir_deger)

def islem_gir_fiyat_onay(message):
    if message.text in ["❌ İPTAL", "İPTAL"]:
        return bot.send_message(message.chat.id, "İşlem iptal edildi.", reply_markup=ana_menu_klavyesi())
        
    state = user_states[message.chat.id]
    
    if "FARKLI" in message.text:
        bot.send_message(
            message.chat.id,
            "Lütfen bankanızdaki <b>GERÇEKLEŞEN BİRİM FİYATI</b> yazın (Örn: <code>1.725000</code>):",
            reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("❌ İPTAL")
        )
        bot.register_next_step_handler(message, islem_gir_ozel_fiyat)
    else:
        # Fiyat onaylandı, valöre kaydet
        tamamla_ve_valore_al(message, state)

def islem_gir_ozel_fiyat(message):
    if message.text in ["❌ İPTAL", "İPTAL"]:
        return bot.send_message(message.chat.id, "İşlem iptal edildi.", reply_markup=ana_menu_klavyesi())
        
    try:
        fiyat_str = message.text.replace(',', '.').strip()
        yeni_fiyat = float(fiyat_str)
        state = user_states[message.chat.id]
        state["fiyat"] = yeni_fiyat
        state["tutar"] = state["adet"] * yeni_fiyat
        tamamla_ve_valore_al(message, state)
    except Exception as e:
        bot.send_message(message.chat.id, "⚠️ Geçersiz fiyat formatı. Lütfen sayı girin (Örn: 1.726496):")
        bot.register_next_step_handler(message, islem_gir_ozel_fiyat)

def tamamla_ve_valore_al(message, state):
    fon = state["fon"]
    tip = state["tip"]
    adet = state["adet"]
    tutar = state["tutar"]
    fiyat = state["fiyat"]
    val_gun = 1 if tip == "ALIS" else (2 if fon not in ["PPZ", "T0"] else 1)
    
    sys.path.insert(0, BASE_DIR)
    from canli_muhasebe_motoru import CanliMuhasebeMotoru
    muh = CanliMuhasebeMotoru()
    durum = muh.portfoy_degerini_guncelle()
    
    if "takasta_bekleyen_islemler" not in durum: durum["takasta_bekleyen_islemler"] = []
    durum["takasta_bekleyen_islemler"].append({
        "islem_tarihi": datetime.date.today().strftime("%Y-%m-%d"),
        "eylem": tip,
        "hedef_fon": fon,
        "pay_adedi": adet,
        "tutar_tl": tutar,
        "fiyat": fiyat,
        "valör_gunu": val_gun,
        "kalan_gun": val_gun
    })
    
    with open(PORTFOY_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(durum, f, indent=2, ensure_ascii=False)
        
    msg = (
        f"✅ <b>EMİR BAŞARIYLA VALÖRE ALINDI!</b>\n"
        f"<code>═════════════════════════════════════════</code>\n"
        f"• <b>Fon Kodu  :</b> <b>{fon}</b> ({tip})\n"
        f"• <b>Pay Adedi :</b> <b>{adet:,.2f} Pay</b>\n"
        f"• <b>Birim Fiyat:</b> {fiyat:.6f} TL\n"
        f"• <b>Toplam TL :</b> <b>{tutar:,.2f} TL</b>\n"
        f"• <b>Valör     :</b> T+{val_gun} İş Günü\n"
        f"<code>═════════════════════════════════════════</code>\n"
        f"⏳ <i>Bankadan paranız/fonunuz hesaba geçtiğinde <b>'⏳ VALÖR ONAY'</b> menüsünden tek tıkla onaylayıp portföyünüze kesinleştirebilirsiniz.</i>"
    )
    bot.send_message(message.chat.id, msg, reply_markup=ana_menu_klavyesi())
    if message.chat.id in user_states:
        del user_states[message.chat.id]


# ─────────────────────────────────────────────────────────────────────────────
# 5. VALÖR VE DİĞER MENÜLER
# ─────────────────────────────────────────────────────────────────────────────

@bot.message_handler(func=lambda msg: msg.text == "⏳ VALÖR ONAY")
def menu_valor_onay(message):
    if not yetki_kontrol(message): return
    try:
        sys.path.insert(0, BASE_DIR)
        from canli_muhasebe_motoru import CanliMuhasebeMotoru
        muh = CanliMuhasebeMotoru()
        durum = muh.portfoy_degerini_guncelle()
        takasta = durum.get("takasta_bekleyen_islemler", [])
        
        if not takasta:
            msg = (
                "⏳ <b>VALÖR VE TAKAS KASASI</b>\n\n"
                "✅ <b>Bekleyen valörünüz bulunmuyor.</b>\n"
                "Tüm alım ve satım işlemleriniz tamamlanmış ve portföyünüze işlenmiştir."
            )
            bot.send_message(message.chat.id, msg)
            return
            
        msg = (
            f"⏳ <b>VALÖRDE BEKLEYEN İŞLEMLERİNİZ ({len(takasta)} Adet)</b>\n"
            f"<code>─────────────────────────────────────────</code>\n"
            f"Bankadan gerçekleşen işleminizi onaylamak için aşağıdaki butona basınız:\n\n"
        )
        for idx, t in enumerate(takasta, 1):
            fon = t.get("hedef_fon", t.get("fon", "Fon"))
            tutar = t.get("tutar_tl", 0)
            adet = t.get("pay_adedi", 0)
            tarih = t.get("islem_tarihi", "")
            msg += f"<b>{idx}. {fon}</b> — {adet:,.1f} Pay ({tutar:,.2f} TL - {tarih})\n"
            
        bot.send_message(message.chat.id, msg, reply_markup=valor_onay_listesi_klavyesi(takasta))
    except Exception as e:
        bot.send_message(message.chat.id, f"⚠️ Valör okuma hatası: {e}")


@bot.message_handler(func=lambda msg: msg.text == "📜 GEÇMİŞ")
def menu_gecmis(message):
    if not yetki_kontrol(message): return
    if not os.path.exists(ISLEM_LOG_PATH) or os.path.getsize(ISLEM_LOG_PATH) == 0:
        bot.send_message(message.chat.id, "📜 <b>İşlem Günlüğü:</b> Henüz kaydedilmiş gerçek işlem bulunmuyor.")
        return
        
    islemler = []
    with open(ISLEM_LOG_PATH, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                islemler.append(json.loads(line))
                
    msg = f"📜 <b>SON GERÇEK İŞLEM KAYITLARI ({len(islemler)} Adet)</b>\n"
    msg += f"<code>─────────────────────────────────────────</code>\n"
    
    for item in reversed(islemler[-5:]):
        tarih = item.get("tarih", "?")
        eylem = item.get("eylem", "?")
        fon = item.get("fon", "?")
        tutar = item.get("tutar_tl", 0)
        adet = item.get("adet", 0)
        msg += f"• <b>{tarih}</b> | {eylem} <b>{fon}</b> | {tutar:,.2f} TL ({adet:,.2f} Pay)\n"
        
    bot.send_message(message.chat.id, msg)


@bot.message_handler(func=lambda msg: msg.text == "📈 REJİMLER")
def menu_rejimler(message):
    if not yetki_kontrol(message): return
    try:
        radar = get_latest_radar()
        breadth_val = radar.get('breadth', 0.0)
        rejim_val = radar.get('rejim', 'HUNTER')
        
        msg = (
            f"📈 <b>HARMONY v2.1/v2.2 REJİM MATRİSİ</b>\n"
            f"<code>─────────────────────────────────────────</code>\n"
            f"🚦 <b>Mevcut Rejim:</b> <b>{rejim_val}</b>\n"
            f"📊 <b>Piyasa Genişliği (Breadth):</b> %{breadth_val:.1f}\n\n"
            f"🟢 <b>HUNTER (Ralli):</b> Genişlik &gt; %48 → Hisse &amp; Sektör İvmesi\n"
            f"🟡 <b>NÖBETÇİ (Dengeli):</b> Genişlik %26 - %48 → Kaliteli Serbest Fon\n"
            f"🔴 <b>SAVUNMA (Koruma):</b> Genişlik &lt; %25 veya Çekilme &gt; %4.50 → T0 Nakit Repo (PPZ)\n"
            f"<code>─────────────────────────────────────────</code>\n"
            f"💡 <i>Sistem piyasa bozulduğunda otomatik olarak savunma kalkanına geçer.</i>"
        )
        bot.send_message(message.chat.id, msg)
    except Exception as e:
        bot.send_message(message.chat.id, f"⚠️ Rejim hatası: {e}")


@bot.message_handler(func=lambda msg: msg.text == "⚙️ SİSTEM")
def menu_sistem(message):
    if not yetki_kontrol(message): return
    msg = (
        "⚙️ <b>SİSTEM VE VERİ YÖNETİMİ</b>\n\n"
        "• <b>Canlı TEFAS Detayı:</b> Aktif (Fon Bilgisi, Yatırımcı & Pay Sayısı)\n"
        "• <b>GitHub Cache:</b> Her 10 dakikada bir otomatik taranır.\n"
        "• <b>Kritik Saatler:</b> 09:55, 10:15, 12:45, 13:00, 18:30\n"
        "• <b>Kill-Switch:</b> Aktif (Çekilme &gt; %4.50 olduğunda acil uyarı)\n"
        "• <b>Sinyal Modeli:</b> HARMONY v2.1 Adaptive + Cutoff Lag (1 Gün Gecikmeli)\n"
    )
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton("🔄 GitHub Verisini Şimdi Tazeleyin", callback_data="btn_manuel_guncelle"),
        InlineKeyboardButton("🛡️ Acil Durum / Kalkan Durumu", callback_data="btn_kalkan_kontrol")
    )
    bot.send_message(message.chat.id, msg, reply_markup=markup)


# ─────────────────────────────────────────────────────────────────────────────
# 6. TEKİL FON KODU ARAMA (Örn: 'SOS', 'MTD', 'GPG', 'CKL', 'PPZ')
# ─────────────────────────────────────────────────────────────────────────────

@bot.message_handler(func=lambda msg: True)
def handle_generic_text(message):
    if not yetki_kontrol(message): return
    text = message.text.strip().upper()
    
    if len(text) in [3, 4] and text.isalnum():
        bot.send_chat_action(message.chat.id, "typing")
        detay_msg = tekil_fon_detayi_getir(text)
        markup = InlineKeyboardMarkup(row_width=1)
        markup.add(
            InlineKeyboardButton(f"📊 {text} Fon İçi Getiriler & Varlıklar", callback_data=f"getiri_{text}"),
            InlineKeyboardButton(f"📑 KAP Portföy Dağılım Raporu", url=f"https://www.kap.org.tr/tr/fon-bilgileri/ozet/{text}"),
            InlineKeyboardButton(f"🌐 TEFAS'ta {text} Resmi Sayfası", url=f"https://www.tefas.gov.tr/tr/fon-detayli-analiz/{text}")
        )
        bot.send_message(message.chat.id, detay_msg, reply_markup=markup, disable_web_page_preview=True)
    else:
        bot.send_message(
            message.chat.id,
            "💡 <i>Menüden bir butona basabilir veya analizini görmek istediğiniz fonun kodunu yazabilirsiniz (Örn: <code>SOS</code>, <code>MTD</code>, <code>GPG</code>).</i>",
            reply_markup=ana_menu_klavyesi()
        )

# ─────────────────────────────────────────────────────────────────────────────
# 7. INLINE CALLBACK BUTON İŞLEYİCİLERİ
# ─────────────────────────────────────────────────────────────────────────────

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    chat_id = str(call.message.chat.id)
    if chat_id != str(AUTHORIZED_CHAT_ID):
        bot.answer_callback_query(call.id, "Yetkisiz erişim!")
        return

    data = call.data

    if data == "btn_iptal" or data == "btn_kapat":
        bot.delete_message(call.message.chat.id, call.message.message_id)
        bot.answer_callback_query(call.id, "İşlem kapatıldı.")
        return

    elif data.startswith("getiri_"):
        fon_kodu = data.replace("getiri_", "")
        bot.answer_callback_query(call.id, f"{fon_kodu} getiri ve varlık analizi hazırlanıyor...")
        getiri_msg = get_fon_tum_getiri_periyotlari(fon_kodu)
        markup = InlineKeyboardMarkup(row_width=1)
        markup.add(
            InlineKeyboardButton(f"📑 KAP Portföy Dağılım Raporu", url=f"https://www.kap.org.tr/tr/fon-bilgileri/ozet/{fon_kodu}"),
            InlineKeyboardButton(f"🔙 {fon_kodu} Ana Detayına Dön", callback_data=f"detay_{fon_kodu}")
        )
        bot.send_message(call.message.chat.id, getiri_msg, reply_markup=markup, disable_web_page_preview=True)


    elif data.startswith("valor_tamamla_"):
        idx = int(data.replace("valor_tamamla_", ""))
        sys.path.insert(0, BASE_DIR)
        from canli_muhasebe_motoru import CanliMuhasebeMotoru
        muh = CanliMuhasebeMotoru()
        durum = muh.portfoy_degerini_guncelle()
        takasta = durum.get("takasta_bekleyen_islemler", [])
        
        if 0 <= idx < len(takasta):
            item = takasta.pop(idx)
            fon = item.get("hedef_fon", item.get("fon", "PPZ"))
            tutar = item.get("tutar_tl", 0)
            adet = item.get("pay_adedi", 0)
            fiyat = item.get("fiyat", 1.0)
            eylem = item.get("eylem", "ALIS")
            
            if "eldeki_fonlar" not in durum: 
                durum["eldeki_fonlar"] = {}
                
            if eylem == "ALIS":
                if fon in durum["eldeki_fonlar"]:
                    # Mevcut fonun üzerine ekle (Ağırlıklı ortalama maliyet)
                    eskisi = durum["eldeki_fonlar"][fon]
                    eski_adet = eskisi.get("pay_adedi", 0.0)
                    eski_maliyet = eskisi.get("maliyet_fiyati", fiyat)
                    toplam_adet = eski_adet + adet
                    yeni_maliyet = ((eski_adet * eski_maliyet) + (adet * fiyat)) / toplam_adet if toplam_adet > 0 else fiyat
                    
                    durum["eldeki_fonlar"][fon]["pay_adedi"] = toplam_adet
                    durum["eldeki_fonlar"][fon]["maliyet_fiyati"] = yeni_maliyet
                    durum["eldeki_fonlar"][fon]["son_nav"] = fiyat
                    durum["eldeki_fonlar"][fon]["guncel_deger_tl"] = toplam_adet * fiyat
                else:
                    # Portföye yeni fon olarak ekle (diğer fonları silmeden!)
                    durum["eldeki_fonlar"][fon] = {
                        "fon_kodu": fon,
                        "fon_adi": f"{fon} Fonu",
                        "pay_adedi": adet,
                        "maliyet_fiyati": fiyat,
                        "son_nav": fiyat,
                        "guncel_deger_tl": tutar
                    }
            elif eylem == "SATIS":
                # Satılan fonu eldeki_fonlar'dan düş veya sil
                if fon in durum["eldeki_fonlar"]:
                    eski_adet = durum["eldeki_fonlar"][fon].get("pay_adedi", 0.0)
                    if eski_adet <= adet or adet <= 0:
                        del durum["eldeki_fonlar"][fon]
                    else:
                        durum["eldeki_fonlar"][fon]["pay_adedi"] = eski_adet - adet
                        durum["eldeki_fonlar"][fon]["guncel_deger_tl"] = (eski_adet - adet) * fiyat
                
                # PPZ Canlı Fiyatı Sorgusu (Dinamik NAV - Defensive Unpack)
                ppz_res = muh.son_fon_fiyati_getir("PPZ")
                ppz_fiyat = ppz_res[0] if isinstance(ppz_res, (tuple, list)) else ppz_res
                if not ppz_fiyat or ppz_fiyat <= 1.05: 
                    ppz_fiyat = 6.63

                
                if "PPZ" in durum["eldeki_fonlar"]:
                    durum["eldeki_fonlar"]["PPZ"]["pay_adedi"] += (tutar / ppz_fiyat)
                    durum["eldeki_fonlar"]["PPZ"]["guncel_deger_tl"] += tutar
                    durum["eldeki_fonlar"]["PPZ"]["son_nav"] = ppz_fiyat
                else:
                    durum["eldeki_fonlar"]["PPZ"] = {
                        "fon_kodu": "PPZ",
                        "fon_adi": "Azimut Para Piyasası Fonu",
                        "pay_adedi": tutar / ppz_fiyat,
                        "maliyet_fiyati": ppz_fiyat,
                        "son_nav": ppz_fiyat,
                        "guncel_deger_tl": tutar
                    }

                
            with open(ISLEM_LOG_PATH, "a", encoding="utf-8") as f:
                log_entry = {
                    "tarih": datetime.date.today().strftime("%Y-%m-%d %H:%M:%S"),
                    "eylem": eylem,
                    "fon": fon,
                    "tutar_tl": tutar,
                    "adet": adet,
                    "fiyat": fiyat,
                    "tip": "MANUEL_TELEGRAM_ONAYLI"
                }
                f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
                
            with open(PORTFOY_JSON_PATH, "w", encoding="utf-8") as f:
                json.dump(durum, f, indent=2, ensure_ascii=False)
                
            bot.edit_message_text(
                f"🎉 <b>VALÖR GERÇEKLEŞTİRİLDİ VE KESİNLEŞTİ!</b>\n\n"
                f"• <b>Fon:</b> <b>{fon}</b>\n"
                f"• <b>Pay Adedi:</b> <b>{adet:,.2f} Pay</b>\n"
                f"• <b>Birim Fiyat:</b> {fiyat:.6f} TL\n"
                f"• <b>Tutar:</b> <b>{tutar:,.2f} TL</b>\n\n"
                f"<i>İşlem günlüğüne işlendi ve canlı portföy bakiyeniz güncellendi.</i>",
                call.message.chat.id,
                call.message.message_id
            )

    elif data.startswith("valor_iptal_"):
        idx = int(data.replace("valor_iptal_", ""))
        sys.path.insert(0, BASE_DIR)
        from canli_muhasebe_motoru import CanliMuhasebeMotoru
        muh = CanliMuhasebeMotoru()
        durum = muh.portfoy_degerini_guncelle()
        takasta = durum.get("takasta_bekleyen_islemler", [])
        
        if 0 <= idx < len(takasta):
            item = takasta.pop(idx)
            fon = item.get("hedef_fon", item.get("fon", "Bilinmeyen"))
            tutar = item.get("tutar_tl", 0)
            
            with open(PORTFOY_JSON_PATH, "w", encoding="utf-8") as f:
                json.dump(durum, f, indent=2, ensure_ascii=False)
                
            bot.edit_message_text(
                f"🗑️ <b>VALÖR İŞLEMİ İPTAL EDİLDİ VE SİLİNDİ</b>\n\n"
                f"• <b>İptal Edilen Fon:</b> <b>{fon}</b>\n"
                f"• <b>Tutar:</b> <b>{tutar:,.2f} TL</b>\n\n"
                f"<i>Takas kaydı portföyünüzden temizlendi. Yeni emrinizi '➕ İŞLEM GİR' menüsünden girebilirsiniz.</i>",
                call.message.chat.id,
                call.message.message_id
            )

    elif data.startswith("detay_"):

        fon_kodu = data.replace("detay_", "")
        bot.answer_callback_query(call.id, f"{fon_kodu} detayları yükleniyor...")
        detay_msg = tekil_fon_detayi_getir(fon_kodu)
        markup = InlineKeyboardMarkup()
        markup.add(
            InlineKeyboardButton(f"🌐 TEFAS'ta {fon_kodu} Sayfası", url=f"https://www.tefas.gov.tr/tr/fon-detayli-analiz/{fon_kodu}"),
            InlineKeyboardButton("🔙 Kapat", callback_data="btn_kapat")
        )
        bot.send_message(call.message.chat.id, detay_msg, reply_markup=markup, disable_web_page_preview=True)

    elif data == "btn_manuel_guncelle":
        bot.answer_callback_query(call.id, "GitHub'dan taze veri çekiliyor...")
        ok, res_msg = github_verisini_guncelle(zorla=True)
        bot.send_message(call.message.chat.id, f"🔄 <b>GitHub Veri Sonucu:</b>\n{res_msg}")

    elif data == "btn_portfoy_yenile":
        bot.answer_callback_query(call.id, "Portföy değerleri güncellendi.")
        menu_portfoy(call.message)

    elif data == "btn_valor_menusu":
        bot.answer_callback_query(call.id, "Valör menüsü açılıyor.")
        menu_valor_onay(call.message)

    elif data == "btn_piyasa_isisi_yenile":
        bot.answer_callback_query(call.id, "Piyasa ısısı güncelleniyor...")
        msg = piyasa_isisi_metni_olustur()
        markup = InlineKeyboardMarkup(row_width=2)
        markup.add(
            InlineKeyboardButton("🔄 Isıyı Güncelle", callback_data="btn_piyasa_isisi_yenile"),
            InlineKeyboardButton("🧭 Harmony Radarı", callback_data="btn_harmony_ac")
        )
        try:
            bot.edit_message_text(msg, call.message.chat.id, call.message.message_id, reply_markup=markup)
        except Exception:
            pass

    elif data == "btn_harmony_ac":
        bot.answer_callback_query(call.id, "Harmony Radarı açılıyor...")
        menu_harmony(call.message)


def olustur_harmony_emir_talimati(zaman_baslik="13:00"):
    radar = get_latest_radar()
    sys.path.insert(0, BASE_DIR)
    from canli_muhasebe_motoru import CanliMuhasebeMotoru
    muh = CanliMuhasebeMotoru()
    durum = muh.portfoy_degerini_guncelle()
    eldeki_dict = durum.get("eldeki_fonlar", {})
    eldeki = list(eldeki_dict.keys())[0] if eldeki_dict else "PPZ"
    lider = radar.get("lider_fon", "SOS")
    
    msg = (
        f"🎯 <b>{zaman_baslik} HARMONY EMİR VE KARAR TALİMATI</b>\n"
        f"<code>═════════════════════════════════════════</code>\n"
        f"• <b>Mevcut Fonunuz :</b> <b>{eldeki}</b>\n"
        f"• <b>Portföy Değeri :</b> <b>{durum.get('toplam_portfoy_tl', 0):,.2f} TL</b>\n"
        f"• <b>Piyasa Rejimi  :</b> <code>[{radar.get('rejim', 'NORMAL')}]</code> (Genişlik: %{radar.get('breadth', 0):.1f})\n"
        f"• <b>1. Sıradaki Fon:</b> <b>{lider}</b>\n"
        f"<code>─────────────────────────────────────────</code>\n"
    )
    
    top3 = [f['fon'] for f in radar.get('top10', [])[:3]]
    if eldeki == lider or (eldeki in top3 and eldeki == "SOS"):
        msg += (
            f"🟢 <b>NET TALİMAT:</b> <b>{eldeki} FONUNDA KALMAYA DEVAM EDİN.</b>\n"
            f"  └─ <i>İşlem yapmanız gerekmez. Fonunuz şampiyonlar ligi podyumundadır; gereksiz valör yakmadan trendi taşımaya devam ediyoruz.</i>\n"
        )
    else:
        msg += (
            f"🔔 <b>NET TALİMAT:</b> <b>{eldeki} SATIŞI YAPIP {lider} ALIŞ EMRİ VERİNİZ.</b>\n"
            f"  └─ <i>Lider fon {lider}, mevcut fonunuzu ivme ve puan olarak belirgin şekilde geçmiştir. Saat 13:30 öncesi bankanızdan emir girebilirsiniz.</i>\n"
        )
    msg += f"<code>═════════════════════════════════════════</code>"
    return msg

# ─────────────────────────────────────────────────────────────────────────────
# 8. ARKA PLAN GÖREVİ: OTOMATİK PROAKTİF BİLDİRİMLER VE ALARMLAR
# ─────────────────────────────────────────────────────────────────────────────

gonderilmis_alarmlar = set()
son_bilinen_fon_fiyatlari = {}

def arka_plan_zamanlayici():
    global gonderilmis_alarmlar, son_bilinen_fon_fiyatlari
    print(">> Arka plan zamanlayici aktif (Otomatik Proaktif Bildirim Modu)")
    
    while True:
        try:
            now = datetime.datetime.now()
            bugun_str = now.strftime("%Y-%m-%d")
            saat_dakika = now.strftime("%H:%M")
            
            # Her 10 dakikada bir kontrol
            if now.minute % 10 == 0:
                github_verisini_guncelle()
                
                # Eldeki fonun fiyatı değişti mi kontrol et (Otomatik Anlık Bildirim)
                sys.path.insert(0, BASE_DIR)
                from canli_muhasebe_motoru import CanliMuhasebeMotoru
                muh = CanliMuhasebeMotoru()
                durum = muh.portfoy_degerini_guncelle()
                
                # 🚨 KILL-SWITCH PROAKTİF KONTROL VE ANLIK ALARM
                if durum.get("kill_switch_aktif", False):
                    ks_alarm_key = f"{bugun_str}_kill_switch_alert"
                    if ks_alarm_key not in gonderilmis_alarmlar:
                        ks_msg = (
                            f"🚨🚨 <b>ACİL UYARI: PORTFÖY KILL-SWITCH TETİKLENDİ!</b> 🚨🚨\n"
                            f"<code>═════════════════════════════════════════</code>\n"
                            f"📉 <b>Mevcut Tepe Çekilmesi:</b> <b>%{durum.get('mevcut_cekilme_pct', 0):.2f}</b>\n"
                            f"🛡️ <b>İzin Verilen Limit   :</b> %4.50 (AŞILDI!)\n"
                            f"💰 <b>Güncel Portföy Değeri:</b> <b>{durum.get('toplam_portfoy_tl', 0):,.2f} TL</b>\n"
                            f"🏔️ <b>Görülen Zirve Değer  :</b> {durum.get('zirve_portfoy_tl', 0):,.2f} TL\n"
                            f"<code>═════════════════════════════════════════</code>\n"
                            f"🛑 <b>GÜVENLİK PROTOKOLÜ DEVREDE:</b>\n"
                            f"<i>Portföyünüz zirveden %4.50'den fazla geri çekilerek güvenlik eşiğini aşmıştır. Sistemin sermaye koruma kuralı gereğince pozisyonları kapatıp <b>PPZ (Nakit / Para Piyasası)</b> savunmasına geçilmesi acilen önerilmektedir!</i>\n"
                            f"<code>═════════════════════════════════════════</code>"
                        )
                        bot.send_message(AUTHORIZED_CHAT_ID, ks_msg, reply_markup=ana_menu_klavyesi())
                        gonderilmis_alarmlar.add(ks_alarm_key)

                eldeki_dict = durum.get("eldeki_fonlar", {})

                
                bayat_listesi = durum.get("fiyat_verisi_bayat_fonlar", [])
                for f_kod, f_info in eldeki_dict.items():
                    if f_kod in bayat_listesi:
                        # Bayat/fallback veri TEFAS'ın yeni fiyatı değildir; yanlış alarm gönderme!
                        continue

                    yeni_fiyat = f_info.get("son_nav", 0.0)
                    eski_fiyat = son_bilinen_fon_fiyatlari.get(f_kod, 0.0)
                    
                    if eski_fiyat > 0 and yeni_fiyat != eski_fiyat and f"{bugun_str}_fiyat_degisti_{f_kod}" not in gonderilmis_alarmlar:
                        adet = f_info.get("pay_adedi", 0.0)
                        tutar = f_info.get("guncel_deger_tl", 0.0)
                        maliyet = f_info.get("maliyet_fiyati", 0.0)
                        kar_tl = tutar - (adet * maliyet)
                        kar_pct = (kar_tl / (adet * maliyet) * 100) if maliyet > 0 else 0
                        kz_ikon = "🟢" if kar_tl >= 0 else "🔴"
                        
                        oto_msg = (
                            f"🔔 <b>TEFAS YENİ FİYAT AÇIKLANDI! ({f_kod})</b>\n"
                            f"<code>─────────────────────────────────────────</code>\n"
                            f"• <b>Yeni Birim Fiyat  :</b> <b>{yeni_fiyat:.6f} TL</b>\n"
                            f"• <b>Önceki Fiyat       :</b> {eski_fiyat:.6f} TL\n"
                            f"• <b>Güncel Portföyünüz :</b> <b>{durum.get('toplam_portfoy_tl', 0):,.2f} TL</b>\n"
                            f"• <b>Kâğıt Kârı/Zararı  :</b> {kz_ikon} <b>{kar_tl:+,.2f} TL (%{kar_pct:+.2f})</b>\n"
                            f"• <b>Tepe Çekilmesi (DD):</b> %{durum.get('mevcut_cekilme_pct', 0):.2f}\n"
                            f"<code>─────────────────────────────────────────</code>"
                        )
                        bot.send_message(AUTHORIZED_CHAT_ID, oto_msg, reply_markup=ana_menu_klavyesi())
                        gonderilmis_alarmlar.add(f"{bugun_str}_fiyat_degisti_{f_kod}")
                        
                    son_bilinen_fon_fiyatlari[f_kod] = yeni_fiyat

            # 09:30 - Sabah İlk TEFAS Açılış ve Portföy Raporu
            alarm_0930 = f"{bugun_str}_0930"
            if saat_dakika == "09:30" and alarm_0930 not in gonderilmis_alarmlar:
                otomatik_pivot_guncelle()
                tum_fonlarin_detaylarini_topla()
                radar = get_latest_radar()
                sys.path.insert(0, BASE_DIR)
                from canli_muhasebe_motoru import CanliMuhasebeMotoru
                muh = CanliMuhasebeMotoru()
                durum = muh.portfoy_degerini_guncelle()
                eldeki_dict = durum.get("eldeki_fonlar", {})
                
                toplam_maliyet = 0.0
                fon_satirlari = []
                for f_kod, f_info in eldeki_dict.items():
                    f_adet = f_info.get("pay_adedi", 0.0)
                    f_maliyet = f_info.get("maliyet_fiyati", 0.0)
                    f_nav = f_info.get("son_nav", 0.0)
                    f_tutar = f_info.get("guncel_deger_tl", f_adet * f_nav)
                    f_top_mal = f_adet * f_maliyet
                    toplam_maliyet += f_top_mal
                    f_kar = f_tutar - f_top_mal
                    f_kar_pct = (f_kar / f_top_mal * 100) if f_top_mal > 0 else 0.0
                    f_ikon = "🟢" if f_kar >= 0 else "🔴"
                    fon_satirlari.append(f"• <b>{f_kod}:</b> <code>{f_adet:,.0f} Pay</code> ({f_nav:.4f} TL) ➔ <b>{f_tutar:,.2f} TL</b> | {f_ikon} %{f_kar_pct:+.2f}")
                
                toplam_portfoy = durum.get("toplam_portfoy_tl", 0.0)
                genel_kar_tl = toplam_portfoy - toplam_maliyet
                genel_kar_pct = (genel_kar_tl / toplam_maliyet * 100) if toplam_maliyet > 0 else 0.0
                genel_ikon = "🟢" if genel_kar_tl >= 0 else "🔴"
                fonlar_metin = "\n".join(fon_satirlari) if fon_satirlari else "• <i>Portföyde kayıtlı fon bulunmuyor.</i>"
                
                msg = (
                    f"☕ <b>GÜNAYDIN! İLK TEFAS VE PORTFÖY RAPORU (09:30)</b>\n"
                    f"<code>═════════════════════════════════════════</code>\n"
                    f"💰 <b>Toplam Portföy  :</b> <b>{toplam_portfoy:,.2f} TL</b>\n"
                    f"📈 <b>Genel Kâr/Zarar :</b> {genel_ikon} <b>{genel_kar_tl:+,.2f} TL (%{genel_kar_pct:+.2f})</b>\n"
                    f"📉 <b>Tepe Çekilmesi :</b> %{durum.get('mevcut_cekilme_pct', 0):.2f}\n"
                    f"<code>─────────────────────────────────────────</code>\n"
                    f"📦 <b>ELDEKİ TÜM FONLARINIZ:</b>\n"
                    f"{fonlar_metin}\n"
                    f"<code>─────────────────────────────────────────</code>\n"
                    f"🚦 <b>Piyasa Rejimi   :</b> <code>[{radar.get('rejim', 'NORMAL')}]</code> (Genişlik: %{radar.get('breadth', 0):.1f})\n"
                    f"🏆 <b>Radar Lideri    :</b> <b>{radar.get('lider_fon', 'SOS')}</b>\n"
                    f"<code>═════════════════════════════════════════</code>\n"
                    f"🎯 <i>Saat 13:00'te resmi emir ve karar talimatı gönderilecektir.</i>"
                )
                bot.send_message(AUTHORIZED_CHAT_ID, msg, reply_markup=ana_menu_klavyesi())
                gonderilmis_alarmlar.add(alarm_0930)

            # 09:55 - Sabah Eksiksiz Piyasa ve Portföy Raporu
            alarm_0955 = f"{bugun_str}_0955"

            if saat_dakika == "09:55" and alarm_0955 not in gonderilmis_alarmlar:
                tum_fonlarin_detaylarini_topla()
                radar = get_latest_radar()
                sys.path.insert(0, BASE_DIR)
                from canli_muhasebe_motoru import CanliMuhasebeMotoru
                muh = CanliMuhasebeMotoru()
                durum = muh.portfoy_degerini_guncelle()
                eldeki_dict = durum.get("eldeki_fonlar", {})
                
                toplam_maliyet = 0.0
                fon_satirlari = []
                for f_kod, f_info in eldeki_dict.items():
                    f_adet = f_info.get("pay_adedi", 0.0)
                    f_maliyet = f_info.get("maliyet_fiyati", 0.0)
                    f_nav = f_info.get("son_nav", 0.0)
                    f_tutar = f_info.get("guncel_deger_tl", f_adet * f_nav)
                    f_top_mal = f_adet * f_maliyet
                    toplam_maliyet += f_top_mal
                    f_kar = f_tutar - f_top_mal
                    f_kar_pct = (f_kar / f_top_mal * 100) if f_top_mal > 0 else 0.0
                    f_ikon = "🟢" if f_kar >= 0 else "🔴"
                    fon_satirlari.append(f"• <b>{f_kod}:</b> <code>{f_adet:,.0f} Pay</code> ({f_nav:.4f} TL) ➔ <b>{f_tutar:,.2f} TL</b> | {f_ikon} %{f_kar_pct:+.2f}")
                
                toplam_portfoy = durum.get("toplam_portfoy_tl", 0.0)
                genel_kar_tl = toplam_portfoy - toplam_maliyet
                genel_kar_pct = (genel_kar_tl / toplam_maliyet * 100) if toplam_maliyet > 0 else 0.0
                genel_ikon = "🟢" if genel_kar_tl >= 0 else "🔴"
                fonlar_metin = "\n".join(fon_satirlari) if fon_satirlari else "• <i>Portföyde kayıtlı fon bulunmuyor.</i>"
                
                msg = (
                    f"🌅 <b>SABAH AÇILIŞ VE PORTFÖY RAPORU (09:55)</b>\n"
                    f"<code>═════════════════════════════════════════</code>\n"
                    f"💰 <b>Toplam Portföy  :</b> <b>{toplam_portfoy:,.2f} TL</b>\n"
                    f"📈 <b>Genel Kâr/Zarar :</b> {genel_ikon} <b>{genel_kar_tl:+,.2f} TL (%{genel_kar_pct:+.2f})</b>\n"
                    f"📉 <b>Tepe Çekilmesi :</b> %{durum.get('mevcut_cekilme_pct', 0):.2f}\n"
                    f"<code>─────────────────────────────────────────</code>\n"
                    f"📦 <b>ELDEKİ TÜM FONLARINIZ:</b>\n"
                    f"{fonlar_metin}\n"
                    f"<code>─────────────────────────────────────────</code>\n"
                    f"🚦 <b>Piyasa Rejimi   :</b> <code>[{radar.get('rejim', 'NORMAL')}]</code> (Genişlik: %{radar.get('breadth', 0):.1f})\n"
                    f"🏆 <b>Radar Lideri    :</b> <b>{radar.get('lider_fon', 'SOS')}</b>\n"
                    f"<code>═════════════════════════════════════════</code>\n"
                    f"🎯 <i>Saat 13:00'te resmi emir ve karar talimatı gönderilecektir.</i>"
                )
                bot.send_message(AUTHORIZED_CHAT_ID, msg, reply_markup=ana_menu_klavyesi())
                gonderilmis_alarmlar.add(alarm_0955)

            # 13:00 - Resmi Son Çağrı ve Emir Fişi
            alarm_1300 = f"{bugun_str}_1300"
            if saat_dakika == "13:00" and alarm_1300 not in gonderilmis_alarmlar:
                msg = olustur_harmony_emir_talimati("13:00 RESMİ SON ÇAĞRI")
                bot.send_message(AUTHORIZED_CHAT_ID, msg, reply_markup=ana_menu_klavyesi())
                gonderilmis_alarmlar.add(alarm_1300)

            # 18:30 - Gün Sonu Eksiksiz Kapanış Raporu
            alarm_1830 = f"{bugun_str}_1830"
            if saat_dakika == "18:30" and alarm_1830 not in gonderilmis_alarmlar:
                tum_fonlarin_detaylarini_topla()
                sys.path.insert(0, BASE_DIR)
                from canli_muhasebe_motoru import CanliMuhasebeMotoru
                muh = CanliMuhasebeMotoru()
                durum = muh.portfoy_degerini_guncelle()
                eldeki_dict = durum.get("eldeki_fonlar", {})
                
                toplam_maliyet = 0.0
                fon_satirlari = []
                for f_kod, f_info in eldeki_dict.items():
                    f_adet = f_info.get("pay_adedi", 0.0)
                    f_maliyet = f_info.get("maliyet_fiyati", 0.0)
                    f_nav = f_info.get("son_nav", 0.0)
                    f_tutar = f_info.get("guncel_deger_tl", f_adet * f_nav)
                    f_top_mal = f_adet * f_maliyet
                    toplam_maliyet += f_top_mal
                    f_kar = f_tutar - f_top_mal
                    f_kar_pct = (f_kar / f_top_mal * 100) if f_top_mal > 0 else 0.0
                    f_ikon = "🟢" if f_kar >= 0 else "🔴"
                    fon_satirlari.append(f"• <b>{f_kod}:</b> <code>{f_adet:,.0f} Pay</code> ({f_nav:.4f} TL) ➔ <b>{f_tutar:,.2f} TL</b> | {f_ikon} <b>{f_kar:+,.2f} TL (%{f_kar_pct:+.2f})</b>")
                
                toplam_portfoy = durum.get("toplam_portfoy_tl", 0.0)
                genel_kar_tl = toplam_portfoy - toplam_maliyet
                genel_kar_pct = (genel_kar_tl / toplam_maliyet * 100) if toplam_maliyet > 0 else 0.0
                genel_ikon = "🟢" if genel_kar_tl >= 0 else "🔴"
                fonlar_metin = "\n".join(fon_satirlari) if fon_satirlari else "• <i>Portföyde kayıtlı fon bulunmuyor.</i>"
                
                msg = (
                    f"📊 <b>GÜN SONU KAPANIŞ VE PORTFÖY RAPORU (18:30)</b>\n"
                    f"<code>═════════════════════════════════════════</code>\n"
                    f"💰 <b>Toplam Portföy Değeri :</b> <b>{toplam_portfoy:,.2f} TL</b>\n"
                    f"📈 <b>Toplam Portföy Kâr/Zarar:</b> {genel_ikon} <b>{genel_kar_tl:+,.2f} TL (%{genel_kar_pct:+.2f})</b>\n"
                    f"📉 <b>Tepe Çekilmesi (DD)    :</b> %{durum.get('mevcut_cekilme_pct', 0):.2f}\n"
                    f"<code>─────────────────────────────────────────</code>\n"
                    f"📦 <b>GÜNCEL VARLIK DAĞILIMI:</b>\n"
                    f"{fonlar_metin}\n"
                    f"<code>═════════════════════════════════════════</code>\n"
                    f"İyi akşamlar dileriz! 🦅"
                )
                bot.send_message(AUTHORIZED_CHAT_ID, msg)
                gonderilmis_alarmlar.add(alarm_1830)

            # 18:45 - TEFAS TÜM FONLARIN EKSİKSİZ ARŞİVLENMESİ (1.000+ Fon ve Portföy Dağılımları)
            alarm_1845 = f"{bugun_str}_1845"
            if saat_dakika == "18:45" and alarm_1845 not in gonderilmis_alarmlar:
                print(f"[ZAMANLAYICI]: 18:45 TEFAS Tüm Fonlar ve Portföy Dağılımı Arşivleme Tetiklendi...")
                try:
                    sys.path.insert(0, os.path.join(BASE_DIR, "flow_research", "collectors"))
                    from tefas_tum_arsivleyici import tum_tefas_arsivle
                    threading.Thread(target=tum_tefas_arsivle, daemon=True).start()
                except Exception as e:
                    print(f"[18:45 ARSIV TETIKLEME HATA]: {e}")
                gonderilmis_alarmlar.add(alarm_1845)

        except Exception as e:
            print(f"[ZAMANLAYICI HATA]: {e}")
            
        time.sleep(30)

# ─────────────────────────────────────────────────────────────────────────────
# 9. ANA ÇALIŞTIRMA NOKTASI
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 70)
    print("   HARMONY v2.1/v2.2 TELEGRAM BOTU BASLATILIYOR (MANUEL ISLEM MODLU)...")
    print(f"   Yetkili Chat ID: {AUTHORIZED_CHAT_ID}")
    print("=" * 70)
    
    t_zamanlayici = threading.Thread(target=arka_plan_zamanlayici, daemon=True)
    t_zamanlayici.start()
    
    while True:
        try:
            bot.polling(none_stop=True, interval=1, timeout=30)
        except Exception as e:
            print(f"[POLLING HATA]: {e}")
            time.sleep(5)
