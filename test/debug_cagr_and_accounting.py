import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

"""
debug_cagr_and_accounting.py
============================
CAGR Matematiksel Hesaplama ve Bakiye / Valör Muhasebesi Adli İncelemesi.
"""

import pandas as pd
import numpy as np
from harmony_v2_2_live_production import HarmonyV22LiveProduction

live_engine = HarmonyV22LiveProduction()
res = live_engine.simule_et_production()
kayitlar = res["gunluk_kayitlar"]

t_bas = pd.to_datetime(kayitlar[0]["tarih"])
t_bit = pd.to_datetime(kayitlar[-1]["tarih"])

takvim_gunu = (t_bit - t_bas).days
takvim_yili = takvim_gunu / 365.25

islem_gunu = len(kayitlar)
islem_yili_252 = islem_gunu / 252.0

s0 = 100_000.0
sT = res["son_bakiye_tl"]
katlanma = sT / s0

cagr_takvim = ((katlanma) ** (1.0 / takvim_yili) - 1.0) * 100.0
cagr_252 = ((katlanma) ** (252.0 / islem_gunu) - 1.0) * 100.0
cagr_5_tam_yil = ((katlanma) ** (1.0 / 5.0) - 1.0) * 100.0

print("=" * 80)
print("     CAGR VE DÖNEM MATEMATİĞİ ADLİ RAPORU")
print("=" * 80)
print(f"Başlangıç Tarihi       : {t_bas.strftime('%Y-%m-%d')}")
print(f"Bitiş Tarihi           : {t_bit.strftime('%Y-%m-%d')}")
print(f"Toplam Takvim Günü     : {takvim_gunu} gün ({takvim_yili:.3f} Takvim Yılı)")
print(f"Toplam İşlem Günü      : {islem_gunu} seans ({islem_yili_252:.3f} Borsa Yılı / 252)")
print(f"Başlangıç Sermayesi    : {s0:,.2f} TL")
print(f"Nihai Bakiye           : {sT:,.2f} TL")
print(f"Katlanma Çarpanı       : {katlanma:.4f}x")
print("-" * 80)
print(f"1. Takvim Yılı CAGR (365.25 gün) : %{cagr_takvim:.2f}")
print(f"2. İşlem Günü CAGR (252 seans)   : %{cagr_252:.2f}")
print(f"3. Düz 5 Yıl Varsayımı CAGR     : %{cagr_5_tam_yil:.2f}")
print("=" * 80)
