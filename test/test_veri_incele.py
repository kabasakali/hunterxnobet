import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import os
import sys
import json
import pandas as pd

pivot_csv = r"C:\Users\kabasakali\Desktop\calismalar\fonbot\serbest_fon_bot\csv\5_yil_pivot.csv"
if not os.path.exists(pivot_csv):
    pivot_csv = r"C:\Users\kabasakali\Desktop\calismalar\fonbot\serbest_fon_bot\5_yil_pivot.csv"

print(f"Pivot path: {pivot_csv}, exists: {os.path.exists(pivot_csv)}")
df = pd.read_csv(pivot_csv)
col_t = "date" if "date" in df.columns else "tarih"
print(f"Columns: {len(df.columns)}, rows: {len(df)}")
print(f"Min date: {df[col_t].min()}, Max date: {df[col_t].max()}")

t0_kurallar = r"C:\Users\kabasakali\Desktop\calismalar\fonbot\t0fon\fon_kurallari.json"
with open(t0_kurallar, "r", encoding="utf-8") as f:
    kdata = json.load(f)
print(f"T0 fonlar: {list(kdata.get('fonlar', {}).keys())}")

t0_onbellek = r"C:\Users\kabasakali\Desktop\calismalar\fonbot\t0fon\onbellek"
for k in list(kdata.get('fonlar', {}).keys()):
    p3 = os.path.join(t0_onbellek, f"fiyatlar_3yil_{k}.json")
    if os.path.exists(p3):
        with open(p3, "r", encoding="utf-8") as f:
            d = json.load(f)
            print(f"T0 fon {k} 3yil: {len(d)} rows, min {d[0]['tarih']} max {d[-1]['tarih']}")
