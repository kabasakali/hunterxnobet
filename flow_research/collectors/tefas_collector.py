"""
tefas_collector.py
==================
TEFAS Fon Veri Toplayıcı (WAF Uyumlu & Session Destekli)
Hedef: [NAV, Tedavüldeki Pay, AUM, Yatırımcı Sayısı]
Her satıra tam adli metadata ekler (source, retrieved_at, raw_hash).
"""

import os
import sys
import json
import hashlib
import datetime
import requests
import pandas as pd
from typing import Dict, List, Optional, Any

class TefasFlowCollector:
    BASE_URL = "https://www.tefas.gov.tr"
    
    def __init__(self, raw_dir: Optional[str] = None):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
            "Referer": "https://www.tefas.gov.tr/",
            "Origin": "https://www.tefas.gov.tr"
        })
        self.raw_dir = raw_dir or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "raw")
        os.makedirs(self.raw_dir, exist_ok=True)

    def _generate_hash(self, content: Any) -> str:
        serialized = json.dumps(content, sort_keys=True, default=str).encode('utf-8')
        return hashlib.sha256(serialized).hexdigest()

    def get_fund_daily_snapshot(self, fon_kodu: str, hedef_tarih: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Belirtilen fon için günlük NAV, Pay Sayısı, Büyüklük ve Yatırımcı verisini çeker.
        Adli metadata ile paketler.
        """
        now_str = datetime.datetime.now().isoformat()
        tarih = hedef_tarih or datetime.date.today().strftime("%Y-%m-%d")
        
        # 1. Fiyat Bilgisi (Standart Endpoint)
        price_url = f"{self.BASE_URL}/api/funds/fonFiyatBilgiGetir"
        payload = {"fonKodu": fon_kodu, "dil": "TR", "periyod": 1}
        
        try:
            r = self.session.post(price_url, json=payload, timeout=10)
            raw_hash = hashlib.sha256(r.content).hexdigest()
            
            if r.status_code == 200:
                data = r.json()
                result_list = data.get("resultList", [])
                
                # Hedef güne ait kaydı bul
                matched_row = None
                for row in reversed(result_list):
                    if row.get("tarih") == tarih:
                        matched_row = row
                        break
                        
                if matched_row is None and result_list:
                    matched_row = result_list[-1]  # En son geçerli gün
                
                if matched_row:
                    record = {
                        "tarih": matched_row.get("tarih"),
                        "fon": fon_kodu,
                        "nav": float(matched_row.get("fiyat", 0.0)),
                        "tedavuldeki_pay": None,       # Genişletilecek alan
                        "fon_toplam_degeri": None,     # Genişletilecek alan
                        "yatirimci_sayisi": None,      # Genişletilecek alan
                        # Adli Metadata
                        "source": "TEFAS_API_PRICE",
                        "retrieved_at": now_str,
                        "source_timestamp": matched_row.get("tarih"),
                        "data_quality": "PARTIAL_NAV_ONLY",
                        "is_point_in_time": True,
                        "raw_hash": raw_hash
                    }
                    return record
        except Exception as e:
            print(f"[HATA] {fon_kodu} çekilemedi: {e}")
            return None
        return None

if __name__ == "__main__":
    collector = TefasFlowCollector()
    snap = collector.get_fund_daily_snapshot("GPG")
    print("Örnek Kayıt:")
    print(json.dumps(snap, indent=2, ensure_ascii=False))
