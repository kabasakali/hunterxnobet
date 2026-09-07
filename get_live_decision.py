import os
import sys
import pandas as pd

base_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, base_dir)

from harmony_v2_2_live_production import HarmonyV22LiveProduction

prod = HarmonyV22LiveProduction()
dec = prod.get_current_live_decision()

print("=== HARMONY MODEL E CANLI KARAR ===")
print("Rejim:", dec.get('rejim'))
print(f"Piyasa Genisligi: %{dec.get('market_breadth', 0)*100:.1f}")
print(f"Hedef Lider Fon : {dec.get('target_fon')}")
print(f"Model E Tahsisi : %{dec.get('w_pct'):.0f} {dec.get('target_fon')} + %{dec.get('ppz_pct'):.0f} PPZ")
print(f"20G Oynaklik    : %{dec.get('vol_val'):.1f}")


top_df = dec.get('top_funds')
if isinstance(top_df, pd.DataFrame):
    print("\nTop 7 Siralamasi:")
    for i, r in top_df.head(7).iterrows():
        f = r.get('fon')
        s = r.get('skor', 0)
        r20 = r.get('r20', 0)*100
        r63 = r.get('r63', 0)*100
        print(f"{i+1}. {f:<5} | Puan: {s:.3f} | 20G: %{r20:>+6.2f} | 63G: %{r63:>+6.2f}")
