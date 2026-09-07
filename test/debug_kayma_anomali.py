import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

"""
debug_kayma_anomali.py
======================
Kayma parametresi arttıkça oluşan sonuçların adli denetimi.
"""

from meta_allocator_motor import MetaAllocatorMotor
from harmony_v1_motor import HarmonyMotor
import pandas as pd

for k in [0.0000, 0.0005, 0.0010, 0.0020, 0.0030, 0.0050]:
    eng = MetaAllocatorMotor(kayma_pct=k)
    r_v2 = eng.simule_et_meta("meta_master_switcher")
    r_mom = eng.base_motor.simule_et_model("momentum_spread")
    r_h6 = eng.base_motor.simule_et_model("saf_hunter")
    r_dd = eng.base_motor.simule_et_model("dd_aware_switching")
    print(f"Kayma %{k*100:.2f} -> V2: {r_v2['son_bakiye_tl']:,.2f} TL | MOM: {r_mom['son_bakiye_tl']:,.2f} TL | H6: {r_h6['son_bakiye_tl']:,.2f} TL | DD: {r_dd['son_bakiye_tl']:,.2f} TL")
