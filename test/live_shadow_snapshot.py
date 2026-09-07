"""
live_shadow_snapshot.py
=======================
Meta Allocator (HARMONY v2) Canlı Gölge Durumu ve Güncel Karar Sinyali.
"""

from meta_allocator_motor import MetaAllocatorMotor
import pandas as pd

meta = MetaAllocatorMotor()
res = meta.simule_et_meta("meta_master_switcher")
kayitlar = res["gunluk_kayitlar"]

son_gun = kayitlar[-1]
son_10_gun = kayitlar[-10:]

print("=" * 80)
print("     META ALLOCATOR (HARMONY v2) — GÜNCEL CANLI GÖLGE DURUM RAPORU")
print("=" * 80)
print(f"Son Veri Tarihi  : {son_gun['tarih']}")
print(f"Portfoy Bakiyesi : {son_gun['bakiye']:,.2f} TL (100K ->)")
print(f"Aktif Meta Karar : {son_gun['etiket']}")
print(f"Agirliklar       : Momentum: %{int(son_gun['w_mom']*100)} | Hunter: %{int(son_gun['w_h6']*100)} | DD-Aware: %{int(son_gun['w_dd']*100)}")
print("=" * 80)
print("\nSon 10 Gunluk Karar Gecmisi:")
df_son = pd.DataFrame(son_10_gun)[["tarih", "bakiye", "etiket", "w_mom", "w_h6", "w_dd"]]
print(df_son.to_string(index=False))
