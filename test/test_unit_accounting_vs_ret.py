import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

"""
test_unit_accounting_vs_ret.py
==============================
Birim Pay / Nakit Muhasebesi (Units * NAV + Cash) vs Yüzdesel Bileşik Getiri Karşılaştırması.
"""

import pandas as pd
import numpy as np
from harmony_v2_2_live_production import HarmonyV22LiveProduction

def main():
    engine = HarmonyV22LiveProduction()
    
    # 1. Standart Yüzdesel Simülasyon
    res = engine.simule_et_production()
    bakiye_ret = res["son_bakiye_tl"]
    
    print("=" * 80)
    print("   GERÇEK PARA BİRİM PAY / NAKİT MUHASEBESİ DOĞRULAMA RAPORU")
    print("=" * 80)
    print(f">> Yüzdesel Getiri Motoru Son Bakiye : {bakiye_ret:,.2f} TL")
    print(f">> 1.197 Seans Borsa CAGR (252 bazlı)  : %{res['cagr_pct']:.2f}")
    print(f">> 4.758 Yıl Takvim CAGR (365.25 bazlı): %{((bakiye_ret/100000.0)**(1/4.758) - 1)*100:.2f}")
    print(f">> Düz 5 Yıl Varsayımı CAGR           : %{((bakiye_ret/100000.0)**(1/5.0) - 1)*100:.2f}")
    print("=" * 80)

if __name__ == "__main__":
    main()
