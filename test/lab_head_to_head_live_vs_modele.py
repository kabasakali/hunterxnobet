"""
test/lab_head_to_head_live_vs_modele.py
=======================================
CANLIDAKİ MEVCUT MODEL (HARMONY V2.2) VS YENİ ŞAMPİYON MODEL E (%20 VOL RISK-PARITY)
VE SAF LAB-E BÜYÜK YARIŞI

Karşılaştırılan Modeller:
1. CANLIDAKİ MEVCUT HARMONY V2.2 (All-Time Peak Drawdown / Sabit %100)
2. SAF LAB-E (60G Rolling Peak Adaptive Re-entry / Sabit %100)
3. YENİ ŞAMPİYON MODEL E (60G Rolling Peak + %20 Target Volatility Risk-Parity Sizing)
"""

import os
import sys
import numpy as np
import pandas as pd

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, base_dir)
sys.path.insert(0, os.path.join(base_dir, "test"))

from harmony_v2_2_golden import HarmonyV22GoldenMotor
from lab_11_winner_retention_and_capture_forensics import Lab11WinnerRetentionEngine
from lab_18_nested_walk_forward_vol_lock import Lab17VolSizingForensicsEngine

def calc_sub_period(rets, start_dt, end_dt, cap=100_000.0):
    sub = rets.loc[start_dt:end_dt]
    if len(sub) == 0:
        return {"ret_pct": 0, "end_cap": cap, "profit": 0, "mdd": 0}
    wealth = cap * (1 + sub).cumprod()
    end_cap = wealth.iloc[-1]
    ret_pct = (end_cap - cap) / cap * 100.0
    profit = end_cap - cap
    peak = wealth.cummax()
    dd = (wealth - peak) / peak
    mdd = dd.min() * 100.0
    return {
        "ret_pct": ret_pct,
        "end_cap": end_cap,
        "profit": profit,
        "mdd": mdd
    }

def run_race():
    # 1. Canlıdaki Harmony V2.2 Golden
    m_v22 = HarmonyV22GoldenMotor(baslangic_sermayesi=100_000.0)
    res_v22 = m_v22.simule_et_v2_2()
    df_v22 = pd.DataFrame(res_v22["gunluk_kayitlar"])
    df_v22["dt"] = pd.to_datetime(df_v22["tarih"])
    df_v22 = df_v22.set_index("dt")
    df_v22["gunluk_ret"] = df_v22["bakiye"].pct_change().fillna(0.0)
    rets_v22 = df_v22["gunluk_ret"]
    res_v22["cagr"] = res_v22["cagr_pct"]
    res_v22["son_bakiye"] = res_v22["son_bakiye_tl"]
    res_v22["mdd"] = res_v22["max_drawdown_pct"]
    res_v22["sharpe"] = res_v22["sharpe_orani"]
    res_v22["yillik_ret"] = res_v22["yillik_getiriler"]


    
    # 2. Saf LAB-E
    m_labe = Lab11WinnerRetentionEngine(baslangic_sermayesi=100_000.0)
    res_labe = m_labe.run_pure_labe()
    df_labe = res_labe["df"]
    rets_labe = df_labe["gunluk_ret"]
    
    # 3. Model E (%20 Vol)
    m_modele = Lab17VolSizingForensicsEngine(baslangic_sermayesi=100_000.0)
    res_modele = m_modele.simule_et_vol(vol_window=20, target_vol=0.20)
    df_modele = res_modele["df"]
    rets_modele = df_modele["gunluk_ret"]
    
    tarihler = list(rets_labe.index)
    last_dt = tarihler[-1]
    dt_3m = str(tarihler[-63].strftime("%Y-%m-%d"))
    dt_2y = str(tarihler[-504].strftime("%Y-%m-%d"))
    dt_start = str(tarihler[0].strftime("%Y-%m-%d"))
    dt_end = str(last_dt.strftime("%Y-%m-%d"))
    
    print("=" * 125, flush=True)
    print("RESMI BUYUK YARIS: CANLIDAKI HARMONY V2.2 vs MODEL E (%20 VOL) vs SAF LAB-E", flush=True)
    print("=" * 125, flush=True)
    
    # TABLO 1: GENEL 5 YILLIK METRİK TABLOSU (100k ve 75k BAZINDA)
    models = [
        ("1. CANLIDAKI HARMONY V2.2", res_v22, rets_v22),
        ("2. SAF LAB-E (%100 Sabit)", res_labe, rets_labe),
        ("3. MODEL E (%20 Vol Risk-Parity)", res_modele, rets_modele)
    ]
    
    print("1. TABLO: GENEL 5 YILLIK RISK VE SERVET KARSILASTIRMASI (100.000 TL BASLANGIC):", flush=True)
    hdr1 = f"{'Model':<35} | {'5Y CAGR':<8} | {'100k Bakiye':<15} | {'75k Bakiye':<14} | {'MaxDD':<8} | {'Sharpe':<7} | {'Sortino':<8} | {'Calmar':<7} | {'PF':<6}"
    print(hdr1, flush=True)
    print("-" * 125, flush=True)
    
    for lbl, r, rets in models:
        cagr = r["cagr"]
        b100 = r["son_bakiye"]
        b75 = 75_000.0 * (b100 / 100_000.0)
        mdd = r["mdd"]
        sharpe = r["sharpe"]
        
        # sortino & calmar & pf
        neg_r = rets[rets < 0]
        sortino = (rets.mean() / (neg_r.std() + 1e-9)) * np.sqrt(252) if len(neg_r) > 0 else 0
        calmar = cagr / abs(mdd) if abs(mdd) > 0 else 0
        gains = rets[rets > 0].sum()
        losses = abs(rets[rets < 0].sum())
        pf = gains / losses if losses > 0 else 0
        
        print(f"{lbl:<35} | %{cagr:<6.2f} | {b100:<12,.0f} TL | {b75:<11,.0f} TL | %{mdd:<6.2f} | {sharpe:<7.2f} | {sortino:<8.2f} | {calmar:<7.2f} | {pf:<6.2f}", flush=True)
        
    print("-" * 125, flush=True)
    
    # TABLO 2: YILLARA GÖRE KAZANÇ MATRİSİ
    print("\n2. TABLO: YILLARA GORE GETIRI OTOPSISI (2022 KILIDI, 2025 BLIND VE 2026 OOS):", flush=True)
    hdr2 = f"{'Model':<35} | {'2021':<8} | {'2022 (Ralli)':<13} | {'2023':<8} | {'2024':<8} | {'2025 Blind':<11} | {'2026 OOS'}"
    print(hdr2, flush=True)
    print("-" * 125, flush=True)
    
    for lbl, r, rets in models:
        df_m = r["df"] if "df" in r else pd.DataFrame()
        y_rets = {}
        for y, grp in rets.groupby(rets.index.year):
            r_val = np.prod(1.0 + grp) - 1.0
            y_rets[y] = r_val * 100.0
            
        r21 = f"%{y_rets.get(2021, 0):+.1f}"
        r22 = f"%{y_rets.get(2022, 0):+.1f}"
        r23 = f"%{y_rets.get(2023, 0):+.1f}"
        r24 = f"%{y_rets.get(2024, 0):+.1f}"
        r25 = f"%{y_rets.get(2025, 0):+.1f}"
        r26 = f"%{y_rets.get(2026, 0):+.1f}"
        print(f"{lbl:<35} | {r21:<8} | {r22:<13} | {r23:<8} | {r24:<8} | {r25:<11} | {r26}", flush=True)
        
    print("-" * 125, flush=True)

    
    # TABLO 3: SON 3 AY, SON 2 YIL, SON 5 YIL UFUKLARI (75.000 TL BAZINDA)
    print("\n3. TABLO: 75.000 TL ILE ZAMAN UFUKLARI YARISI (SON 3 AY, SON 2 YIL, SON 5 YIL):", flush=True)
    hdr3 = f"{'Model':<35} | {'Son 3 Ay Getiri':<16} | {'Son 2 Yil Getiri':<16} | {'Son 5 Yil Getiri':<16} | {'5 Yil Net Kar (75k)'}"
    print(hdr3, flush=True)
    print("-" * 125, flush=True)
    
    for lbl, r, rets in models:
        p3m = calc_sub_period(rets, dt_3m, dt_end, 75_000.0)
        p2y = calc_sub_period(rets, dt_2y, dt_end, 75_000.0)
        p5y = calc_sub_period(rets, dt_start, dt_end, 75_000.0)
        
        s3m = f"%{p3m['ret_pct']:+.1f} ({p3m['end_cap']:,.0f} TL)"
        s2y = f"%{p2y['ret_pct']:+.1f} ({p2y['end_cap']:,.0f} TL)"
        s5y = f"%{p5y['ret_pct']:+.1f} ({p5y['end_cap']:,.0f} TL)"
        net_kar_5y = f"+{p5y['profit']:>11,.0f} TL"
        
        print(f"{lbl:<35} | {s3m:<16} | {s2y:<16} | {s5y:<16} | {net_kar_5y}", flush=True)
        
    print("=" * 125, flush=True)

if __name__ == "__main__":
    run_race()
