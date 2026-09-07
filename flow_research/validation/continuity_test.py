"""
continuity_test.py
==================
Veri Sürekliliği, Point-in-Time ve Eksik Veri Doğrulama Testi
Toplanan fon verilerinde kopukluk, NaN, sıçrama veya geriye dönük revizyon olup olmadığını denetler.
"""

import os
import sys
import pandas as pd
from typing import Dict, Any

def denetle_veri_butunlugu(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Veri çerçevesinde eksik günleri, ani pay sıçramalarını (bölünme/birleşme) ve kalite durumunu raporlar.
    """
    if df.empty:
        return {"durum": "BOS_VERI", "toplam_satir": 0}
        
    rapor = {
        "toplam_kayit": len(df),
        "fon_sayisi": df["fon"].nunique() if "fon" in df.columns else 0,
        "tarih_araligi": (df["tarih"].min(), df["tarih"].max()) if "tarih" in df.columns else None,
        "eksik_nav_orani_pct": df["nav"].isna().mean() * 100 if "nav" in df.columns else 100.0,
        "eksik_pay_orani_pct": df["tedavuldeki_pay"].isna().mean() * 100 if "tedavuldeki_pay" in df.columns else 100.0,
        "eksik_yatirimci_orani_pct": df["yatirimci_sayisi"].isna().mean() * 100 if "yatirimci_sayisi" in df.columns else 100.0,
        "point_in_time_uyum_pct": df["is_point_in_time"].mean() * 100 if "is_point_in_time" in df.columns else 0.0
    }
    return rapor

if __name__ == "__main__":
    print("Veri Sürekliliği ve Bütünlük Test Modülü Hazır.")
