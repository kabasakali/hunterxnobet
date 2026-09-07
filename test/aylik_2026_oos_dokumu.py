import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np

from harmony_v2_2_live_production import HarmonyV22LiveProduction

def main():
    live_eng = HarmonyV22LiveProduction(baslangic_sermayesi=100_000.0)
    res = live_eng.simule_et_production(baslangic_tarihi="2026-01-02", bitis_tarihi="2026-08-26")
    
    df = pd.DataFrame(res["gunluk_kayitlar"])
    df["dt"] = pd.to_datetime(df["tarih"])
    df["ay"] = df["dt"].dt.strftime("%Y-%m")
    
    aylik_ozet = []
    prev_end = 100_000.0
    
    for ay_str, grp in df.groupby("ay"):
        b_val = prev_end
        e_val = grp["bakiye"].iloc[-1]
        ay_ret = (e_val - b_val) / b_val * 100.0
        
        # O ayki aktif motor ve fonlar
        motorlar = grp["aktif_motor"].unique().tolist()
        gate_states = grp["gate_state"].unique().tolist()
        max_dd_ay = grp["cur_dd"].max() * 100.0
        
        aylik_ozet.append({
            "Ay": ay_str,
            "Ay Başı Bakiye": f"{b_val:,.2f} TL",
            "Ay Sonu Bakiye": f"{e_val:,.2f} TL",
            "Aylık Getiri (%)": f"%{ay_ret:+.2f}",
            "Kümülatif Getiri (%)": f"%{((e_val - 100000.0) / 100000.0 * 100):+.2f}",
            "Aktif Motorlar": ", ".join(motorlar),
            "Risk Gate": ", ".join(gate_states),
            "Max DD (%)": f"%{max_dd_ay:.2f}"
        })
        prev_end = e_val
        
    print("=" * 120)
    print("           2026 KÖR OUT-OF-SAMPLE (OOS) DÖNEMİ AYLIK KAZANÇ VE PERFORMANS DÖKÜMÜ")
    print("                             (02 Ocak 2026 -> 26 Ağustos 2026)")
    print("=" * 120)
    print(pd.DataFrame(aylik_ozet).to_string(index=False))
    print("=" * 120)
    print(f">> Başlangıç Sermayesi (02.01.2026) : 100.000,00 TL")
    print(f">> Güncel Bakiye (26.08.2026)       : {res['son_bakiye_tl']:,.2f} TL")
    print(f">> Net Kazanılan Para               : +{res['son_bakiye_tl'] - 100000:,.2f} TL")
    print(f">> Toplam Net Getiri                : +%{res['toplam_getiri_pct']:.2f}")
    print(f">> 2026 Yılında Görülen En Büyük DD : %{res['max_drawdown_pct']:.2f}")
    print("=" * 120)

if __name__ == "__main__":
    main()
