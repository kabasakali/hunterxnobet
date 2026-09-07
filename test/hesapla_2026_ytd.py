"""
hesapla_2026_ytd.py
===================
2026 Yılı (YTD) Net Kazanç, Getiri ve Çekilme Tablosu (2026-01-02 -> 2026-08-26)
"""

import pandas as pd
import numpy as np

from harmony_v2_2_live_production import HarmonyV22LiveProduction
from harmony_v2_2_golden import HarmonyV22GoldenMotor
from meta_allocator_motor import MetaAllocatorMotor

def main():
    t_bas = "2026-01-02"
    t_bit = "2026-08-26"
    
    prod_eng = HarmonyV22LiveProduction(baslangic_sermayesi=100_000.0)
    gold_eng = HarmonyV22GoldenMotor(baslangic_sermayesi=100_000.0)
    meta_eng = MetaAllocatorMotor(baslangic_sermayesi=100_000.0)
    
    # 1. HARMONY v2.2 Live-Production (Gerçekçi Valör & Cut-off Hardened)
    r_prod = prod_eng.simule_et_production(baslangic_tarihi=t_bas, bitis_tarihi=t_bit)
    # 2. HARMONY v2.2 Golden Benchmark
    r_gold = gold_eng.simule_et_v2_2("v2_2_agile", baslangic_tarihi=t_bas, bitis_tarihi=t_bit)
    # 3. Saf Hunter v6
    r_h6 = meta_eng.simule_et_meta("saf_hunter", baslangic_tarihi=t_bas, bitis_tarihi=t_bit)
    # 4. Saf Fon Nöbetçisi
    r_sfb = meta_eng.simule_et_meta("saf_nobetci", baslangic_tarihi=t_bas, bitis_tarihi=t_bit)
    # 5. T0 Para Piyasası Core (Mevduat / Repo Karşılaştırması)
    r_t0 = meta_eng.t0_ret_serisi.loc[t_bas:t_bit]
    t0_ret = (np.prod(1 + r_t0) - 1) * 100.0
    t0_son = 100_000.0 * (1 + t0_ret / 100.0)
    
    tablo = [
        {
            "Model / Yatırım Stratejisi": "1. HARMONY v2.2 Live-Production (Canlı Model)",
            "Başlangıç (02.01.2026)": "100.000 TL",
            "Son Bakiye (26.08.2026)": f"{r_prod['son_bakiye_tl']:,.2f} TL",
            "Net TL Kazanç": f"+{r_prod['son_bakiye_tl'] - 100000:,.2f} TL",
            "Net Getiri (%)": f"+%{r_prod['toplam_getiri_pct']:.2f}",
            "2026 Max DD (%)": f"%{r_prod['max_drawdown_pct']:.2f}",
            "Calmar": f"{r_prod['calmar_orani']:.2f}",
            "Sharpe": f"{r_prod['sharpe_orani']:.2f}",
            "Sortino": f"{r_prod['sortino_orani']:.2f}",
        },
        {
            "Model / Yatırım Stratejisi": "2. HARMONY v2.2 Golden Benchmark (Saf Alfa)",
            "Başlangıç (02.01.2026)": "100.000 TL",
            "Son Bakiye (26.08.2026)": f"{r_gold['son_bakiye_tl']:,.2f} TL",
            "Net TL Kazanç": f"+{r_gold['son_bakiye_tl'] - 100000:,.2f} TL",
            "Net Getiri (%)": f"+%{r_gold['toplam_getiri_pct']:.2f}",
            "2026 Max DD (%)": f"%{r_gold['max_drawdown_pct']:.2f}",
            "Calmar": f"{r_gold['calmar_orani']:.2f}",
            "Sharpe": f"{r_gold['sharpe_orani']:.2f}",
            "Sortino": f"{r_gold['sortino_orani']:.2f}",
        },
        {
            "Model / Yatırım Stratejisi": "3. Saf Hunter v6 (Benchmark 1)",
            "Başlangıç (02.01.2026)": "100.000 TL",
            "Son Bakiye (26.08.2026)": f"{r_h6['son_bakiye_tl']:,.2f} TL",
            "Net TL Kazanç": f"+{r_h6['son_bakiye_tl'] - 100000:,.2f} TL",
            "Net Getiri (%)": f"+%{r_h6['toplam_getiri_pct']:.2f}",
            "2026 Max DD (%)": f"%{r_h6['max_drawdown_pct']:.2f}",
            "Calmar": f"{r_h6['calmar_orani']:.2f}",
            "Sharpe": f"{r_h6['sharpe_orani']:.2f}",
            "Sortino": f"{r_h6['sortino_orani']:.2f}",
        },
        {
            "Model / Yatırım Stratejisi": "4. Saf Fon Nöbetçisi (Benchmark 2)",
            "Başlangıç (02.01.2026)": "100.000 TL",
            "Son Bakiye (26.08.2026)": f"{r_sfb['son_bakiye_tl']:,.2f} TL",
            "Net TL Kazanç": f"+{r_sfb['son_bakiye_tl'] - 100000:,.2f} TL",
            "Net Getiri (%)": f"+%{r_sfb['toplam_getiri_pct']:.2f}",
            "2026 Max DD (%)": f"%{r_sfb['max_drawdown_pct']:.2f}",
            "Calmar": f"{r_sfb['calmar_orani']:.2f}",
            "Sharpe": f"{r_sfb['sharpe_orani']:.2f}",
            "Sortino": f"{r_sfb['sortino_orani']:.2f}",
        },
        {
            "Model / Yatırım Stratejisi": "5. T0 Para Piyasası / Gösterge Faiz",
            "Başlangıç (02.01.2026)": "100.000 TL",
            "Son Bakiye (26.08.2026)": f"{t0_son:,.2f} TL",
            "Net TL Kazanç": f"+{t0_son - 100000:,.2f} TL",
            "Net Getiri (%)": f"+%{t0_ret:.2f}",
            "2026 Max DD (%)": "%0.00",
            "Calmar": "N/A",
            "Sharpe": "0.00",
            "Sortino": "0.00",
        },
    ]
    
    print("=" * 140)
    print("                     2026 YILI YILBAŞINDAN BUGÜNE (YTD) NET KAZANÇ VE PERFORMANS TABLOSU")
    print("                                      (02 Ocak 2026 - 26 Ağustos 2026 / ~8 Ay)")
    print("=" * 140)
    print(pd.DataFrame(tablo).to_string(index=False))
    print("=" * 140)

if __name__ == "__main__":
    main()
