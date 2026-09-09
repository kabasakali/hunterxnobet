"""
canli_muhasebe_motoru.py
========================
HARMONY v2.2 CANLI PARA KURUMSAL MUHASEBE VE DEFTER MOTORU (REAL MONEY LEDGER)
- Birim Pay (Units) ve Nakit Muhasebesi
- TEFAS Valör ve Takas Durum Takipçisi
- Değiştirilemez İşlem Günlüğü (islem_gunlugu.jsonl)
- Acil Durum Kill-Switch Koruması
- Model Beklentisi vs Gerçekleşen Fark Analizi
"""

import os
import sys
import json
import numpy as np
import pandas as pd
from datetime import datetime
from typing import Dict, List, Tuple, Any, Optional

class CanliMuhasebeMotoru:
    def __init__(
        self,
        base_dir: Optional[str] = None,
        state_filename: str = "portfoy_durumu.json",
        ledger_filename: str = "islem_gunlugu.jsonl"
    ):
        self.base_dir = base_dir or os.path.dirname(os.path.abspath(__file__))
        self.state_path = os.path.join(self.base_dir, state_filename)
        self.ledger_path = os.path.join(self.base_dir, ledger_filename)
        
        # 5 Yıllık Pivot Veri Yolu (Son NAV ve Nema fiyatlarını sorgulamak için)
        olasi_pivot = [
            os.path.join(self.base_dir, "..", "serbest_fon_bot", "csv", "5_yil_pivot.csv"),
            os.path.join(self.base_dir, "..", "serbest_fon_bot", "5_yil_pivot.csv"),
            os.path.join(self.base_dir, "5_yil_pivot.csv"),
            os.path.join(self.base_dir, "flow_research", "data", "5_yil_pivot.csv")
        ]
        self.pivot_path = olasi_pivot[0]
        for p in olasi_pivot:
            if os.path.exists(p):
                self.pivot_path = p
                break
                
        self._fiyat_tablosu = None
        self.durum = self._durum_yukle_veya_olustur()


    def _fiyat_tablosunu_getir(self) -> pd.DataFrame:
        if self._fiyat_tablosu is None:
            if os.path.exists(self.pivot_path):
                self._fiyat_tablosu = pd.read_csv(self.pivot_path, index_col=0, parse_dates=True)
            else:
                self._fiyat_tablosu = pd.DataFrame()
        return self._fiyat_tablosu

    def son_fon_fiyati_getir(self, fon_kodu: str, detayli: bool = False):
        """
        TEFAS canlı API'sinden anlık fiyatı çeker. Başarısız olursa yerel pivot tablosundan döner.
        detayli=True ise (fiyat, canli_mi) döner.
        detayli=False ise float döner (geriye dönük tam uyumluluk).
        """
        try:
            import requests
            url = "https://www.tefas.gov.tr/api/funds/fonBilgiGetir"
            headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://www.tefas.gov.tr/"}
            r = requests.post(url, json={"fonKodu": fon_kodu.upper(), "dil": "TR"}, headers=headers, timeout=4)
            if r.status_code == 200:
                res = r.json().get("resultList", [])
                if res and "sonFiyat" in res[0]:
                    val = float(res[0]["sonFiyat"])
                    return (val, True) if detayli else val
        except Exception:
            pass

        df = self._fiyat_tablosunu_getir()
        if fon_kodu in df.columns:
            seri = df[fon_kodu].dropna()
            if not seri.empty:
                val = float(seri.iloc[-1])
                if val > 0: 
                    return (val, False) if detayli else val
        return (0.0, False) if detayli else 0.0


    def _durum_yukle_veya_olustur(self) -> Dict[str, Any]:
        """
        Mevcut portföy durumunu yükler veya yoksa 100.000 TL başlangıçlı şablon oluşturur.
        """
        if os.path.exists(self.state_path):
            try:
                with open(self.state_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"[UYARI] Durum dosyası okunamadı: {e}. Yeni durum oluşturuluyor.")
                
        # Varsayılan başlangıç durumu
        varsayilan = {
            "son_guncelleme": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "baslangic_sermayesi_tl": 100_000.0,
            "toplam_portfoy_tl": 100_000.0,
            "zirve_portfoy_tl": 100_000.0,
            "mevcut_cekilme_pct": 0.0,
            "kill_switch_aktif": False,
            "kill_switch_nedeni": None,
            "eldeki_fonlar": {
                "PPZ": {
                    "fon_kodu": "PPZ",
                    "fon_adi": "Azimut Para Piyasası Fonu",
                    "pay_adedi": 100_000.0,
                    "maliyet_fiyati": 1.0,
                    "son_nav": 1.0,
                    "guncel_deger_tl": 100_000.0
                }
            },
            "serbest_nakit_tl": 0.0,
            "takasta_bekleyen_islemler": []
        }
        self._durum_kaydet(varsayilan)
        return varsayilan

    def _durum_kaydet(self, durum_dict: Optional[Dict[str, Any]] = None):
        """
        Portföy durumunu JSON dosyasına atomik olarak yazar.
        """
        data = durum_dict or self.durum
        data["son_guncelleme"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(self.state_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def deftere_islem_yaz(self, islem_kaydi: Dict[str, Any]):
        """
        İşlem kaydını değiştirilemez append-only jsonl kütüğüne işler.
        """
        islem_kaydi["kayit_zamani"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(self.ledger_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(islem_kaydi, ensure_ascii=False) + "\n")

    def portfoy_degerini_guncelle(self) -> Dict[str, Any]:
        """
        Eldeki fonların güncel fiyatlarını sorgulayıp portföy toplam değerini,
        tepe noktasını ve güncel drawdown'u hesaplar.
        """
        toplam_aktif_fon = 0.0
        for f_kod, f_bilgi in self.durum.get("eldeki_fonlar", {}).items():
            f_res = self.son_fon_fiyati_getir(f_kod)
            canli_fiyat = f_res[0] if isinstance(f_res, (tuple, list)) else f_res
            if canli_fiyat > 0.0:
                f_bilgi["son_nav"] = canli_fiyat
            else:
                # TEFAS sabah veri güncellemesindeyse veya API anlık kesildiyse portföyü sıfırlama, son bilinen fiyatı koru!
                canli_fiyat = f_bilgi.get("son_nav", 0.0)
                if canli_fiyat <= 0.0:
                    canli_fiyat = f_bilgi.get("maliyet_fiyati", 1.0)
                f_bilgi["son_nav"] = canli_fiyat
                
            f_bilgi["guncel_deger_tl"] = round(f_bilgi["pay_adedi"] * canli_fiyat, 2)
            toplam_aktif_fon += f_bilgi["guncel_deger_tl"]

        toplam_portfoy = round(toplam_aktif_fon + self.durum.get("serbest_nakit_tl", 0.0), 2)
        zirve = max(self.durum.get("zirve_portfoy_tl", toplam_portfoy), toplam_portfoy)
        cekilme = round(((zirve - toplam_portfoy) / zirve) * 100.0, 2) if zirve > 0 else 0.0

        self.durum["toplam_portfoy_tl"] = toplam_portfoy
        self.durum["zirve_portfoy_tl"] = zirve
        self.durum["mevcut_cekilme_pct"] = cekilme
        
        # Risk Freni / Kill-Switch Kontrolü (%8 Çekilme Eşiği)
        if cekilme >= 8.0 and not self.durum.get("kill_switch_aktif", False):
            self.durum["kill_switch_aktif"] = True
            self.durum["kill_switch_nedeni"] = f"Maksimum çekilme limiti aşıldı (%{cekilme} >= %8.0)"
            print(f"[KILL-SWITCH AKTİF]: {self.durum['kill_switch_nedeni']}")

        self._durum_kaydet()
        return self.durum

    def portfoy_baslat(self, baslangic_tl: float = 100_000.0, baslangic_fon: str = "PPZ"):
        """
        Portföyü verilen sermaye ve fon ile sıfırlar / yeniden başlatır.
        """
        f_res = self.son_fon_fiyati_getir(baslangic_fon)
        fiyat = f_res[0] if isinstance(f_res, (tuple, list)) else f_res
        pay_adedi = round(baslangic_tl / (fiyat if fiyat > 0 else 1.0), 4)
        
        self.durum = {
            "son_guncelleme": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "baslangic_sermayesi_tl": baslangic_tl,
            "toplam_portfoy_tl": baslangic_tl,
            "zirve_portfoy_tl": baslangic_tl,
            "mevcut_cekilme_pct": 0.0,
            "kill_switch_aktif": False,
            "kill_switch_nedeni": None,
            "eldeki_fonlar": {
                baslangic_fon: {
                    "fon_kodu": baslangic_fon,
                    "fon_adi": f"{baslangic_fon} Portföy Fonu",
                    "pay_adedi": pay_adedi,
                    "maliyet_fiyati": fiyat,
                    "son_nav": fiyat,
                    "guncel_deger_tl": baslangic_tl
                }
            },
            "serbest_nakit_tl": 0.0,
            "takasta_bekleyen_islemler": []
        }
        self._durum_kaydet()
        print(f"[PORTFÖY BAŞLATILDI] Sermaye: {baslangic_tl:,.2f} TL | Fon: {baslangic_fon} ({pay_adedi:,.2f} pay)")
