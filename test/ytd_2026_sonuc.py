import sys, os, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from harmony_v2_2_live_production import HarmonyV22LiveProduction

eng = HarmonyV22LiveProduction()
r = eng.simule_et_production(use_cutoff_lag=True, baslangic_tarihi="2026-01-02", bitis_tarihi="2026-08-27")

baslangic = 100_000.0
son = r["son_bakiye_tl"]
kazanc = son - baslangic
getiri = r["toplam_getiri_pct"]
mdd = r["max_drawdown_pct"]
calmar = r["calmar_orani"]

print("=" * 55)
print("   100.000 TL / 2 Ocak -> 27 Agustos 2026")
print("   (Son guncelleme: use_cutoff_lag=True, taze CSV)")
print("=" * 55)
print(f"  Baslangic : {baslangic:>12,.0f} TL")
print(f"  Son Bakiye: {son:>12,.2f} TL")
print(f"  Net Kazanc: {kazanc:>+12,.2f} TL")
print(f"  Getiri    :  %{getiri:>+.2f}")
print(f"  Max Dusus :  %{mdd:>.2f}")
print(f"  Calmar    :  {calmar:>.1f}x")
print("=" * 55)

kayitlar = r["gunluk_kayitlar"]
df = pd.DataFrame(kayitlar)
df["tarih"] = pd.to_datetime(df["tarih"])
df.set_index("tarih", inplace=True)
df_aylik = df["bakiye"].resample("ME").last()

print("  Aylik Tablo:")
onceki = baslangic
for ay, bakiye in df_aylik.items():
    pct = (bakiye - onceki) / onceki * 100
    bar = "+" * int(abs(pct) / 2) if pct >= 0 else "-" * int(abs(pct) / 2)
    print(f"    {ay.strftime('%Y-%m')} | {bakiye:>12,.0f} TL | {pct:>+6.2f}% {bar}")
    onceki = bakiye

print("=" * 55)
print(f"  OZET: 100K -> {son:,.0f} TL (+{kazanc:,.0f} TL)")
print("=" * 55)
