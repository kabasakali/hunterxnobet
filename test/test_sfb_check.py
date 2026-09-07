import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import os
import sys
import pandas as pd
import numpy as np

sys.path.append(r"c:\Users\kabasakali\Desktop\calismalar\fonbot\t0sniper")
from yaristir_5yil_ve_ytd import simule_et_serbest_fon_bot, HunterV6UnifiedSuper

hunter_engine = HunterV6UnifiedSuper()
pivot_df = hunter_engine.birlesik_fiyat_matrisi

t_5yil_b = str(pivot_df.index[65].date())
t_5yil_s = str(pivot_df.index[-1].date())

res_sfb = simule_et_serbest_fon_bot(pivot_df, t_5yil_b, t_5yil_s)
print(f"SFB Son Bakiye (yaristir): {res_sfb['son_bakiye_tl']:,.2f} TL, Max DD: %{res_sfb['max_drawdown_pct']}")

# Check date alignment
print(f"Start date: {t_5yil_b}, End date: {t_5yil_s}, Total days: {len(pivot_df.loc[t_5yil_b:t_5yil_s])}")
