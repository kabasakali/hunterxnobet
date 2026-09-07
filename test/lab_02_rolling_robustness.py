"""
test/lab_02_rolling_robustness.py
=================================
LAB-02: ROLLING PEAK KOMŞULUK VE DAYANIKLILIK (ROBUSTNESS PLATEAU) TESTİ

Amaç:
LAB-E'deki 60 günlük hareketli zirve (Rolling Peak) parametresinin tekil bir aşırı
öğrenme (overfitting) tepesi mi yoksa geniş ve sağlam bir plato (robust plateau) mu
olduğunu kanıtlamak.

Test Edilen Pencereler:
20, 30, 45, 60, 75, 90, 120, 150, 180 gün

Kurallar:
- Katı T-1 veri kullanımı
- 13:00 karar kesimi
- Gerçek fon valörleri (T+1 / T+2)
- T0 PPZ nakit neması
- Sıfır sızıntı garantisi
"""

import os
import sys
import json
import numpy as np
import pandas as pd

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, base_dir)

from harmony_v1_motor import HarmonyMotor
from meta_allocator_motor import MetaAllocatorMotor
from harmony_v2_2_golden import HarmonyV22GoldenMotor

class Lab02RollingRobustnessEngine:
    def __init__(self, baslangic_sermayesi: float = 100_000.0, kayma_pct: float = 0.0005):
        self.baslangic_sermayesi = baslangic_sermayesi
        self.kayma_pct = kayma_pct
        
        self.golden = HarmonyV22GoldenMotor(baslangic_sermayesi=baslangic_sermayesi, kayma_pct=kayma_pct)
        self.tarihler = self.golden.tarihler
        self.t0_ret_serisi = self.golden.t0_ret_serisi
        
        self.r_mom = self.golden.r_mom
        self.r_h6 = self.golden.r_h6
        self.r_dd = self.golden.r_dd
        self.r_sfb = self.golden.r_sfb
        
        self.market_breadth = self.golden.market_breadth
        self.top5_avg_r20 = self.golden.top5_avg_r20
        self.r20_df = self.golden.r20_df
        self.sfb_aktif_fon = self.golden.sfb_aktif_fon
        self.h6_aktif_fon = self.golden.h6_aktif_fon

    def simule_et_rolling(
        self,
        window_days: int,
        dd_entry: float = 0.040,
        dd_exit: float = 0.025,
        breadth_reentry: float = 0.40,
        use_settlement: bool = True
    ) -> dict:
        sermaye = self.baslangic_sermayesi
        rolling_zirve_pencerisi = []
        
        tarih_dilimi = self.tarihler[65:]
        gunluk_kayitlar = []
        
        aktif_motor = "HUNTER"
        motor_elde_gun = 0
        savunma_modu = False
        takas_kalan_gun = 0
        gecis_sayisi = 0
        
        for idx, dt in enumerate(tarih_dilimi):
            rm = self.r_mom.get(dt, 0.0)
            rh = self.r_h6.get(dt, 0.0)
            rdd = self.r_dd.get(dt, 0.0)
            rt0 = self.t0_ret_serisi.loc[dt]
            
            breadth = self.market_breadth.get(dt, 0.0)
            top5 = self.top5_avg_r20.get(dt, 0.0)
            
            f_sfb = self.sfb_aktif_fon.get(dt, "PPZ")
            f_h6 = self.h6_aktif_fon.get(dt, "PPZ")
            r20_s = self.r20_df.at[dt, f_sfb] if f_sfb in self.r20_df.columns and pd.notna(self.r20_df.at[dt, f_sfb]) else 0.0
            r20_h = self.r20_df.at[dt, f_h6] if f_h6 in self.r20_df.columns and pd.notna(self.r20_df.at[dt, f_h6]) else 0.0
            spread = r20_s - r20_h
            
            # Rolling Zirve Hesabı
            rolling_zirve_pencerisi.append(sermaye)
            if len(rolling_zirve_pencerisi) > window_days:
                rolling_zirve_pencerisi.pop(0)
            local_peak = max(rolling_zirve_pencerisi)
            local_dd = (local_peak - sermaye) / (local_peak + 1e-8)
            
            nobetci_onay = (spread >= 0.020 and r20_s >= 0.03 and breadth >= 0.45)
            
            # Savunma ve Re-entry Mantığı
            if local_dd >= dd_entry or breadth <= 0.25 or top5 <= 0.015:
                savunma_modu = True
            elif local_dd <= dd_exit and (breadth >= breadth_reentry or top5 >= 0.03):
                savunma_modu = False
                
            if savunma_modu:
                hedef_motor = "DD_AWARE"
            elif nobetci_onay:
                hedef_motor = "MOMENTUM"
            else:
                hedef_motor = "HUNTER"
                
            asgari_sure = 5 if aktif_motor == "DD_AWARE" else 3
            acil_fren = (hedef_motor == "DD_AWARE" and local_dd >= 0.045)
            hizli_cikis = (aktif_motor == "DD_AWARE" and breadth >= 0.48 and spread >= 0.025)
            
            if hedef_motor != aktif_motor and (not use_settlement or takas_kalan_gun == 0):
                if motor_elde_gun >= asgari_sure or acil_fren or hizli_cikis:
                    sermaye *= (1.0 - self.kayma_pct)
                    if use_settlement:
                        val_satis = 2 if aktif_motor == "MOMENTUM" else 1
                        takas_kalan_gun = val_satis
                    aktif_motor = hedef_motor
                    motor_elde_gun = 1
                    gecis_sayisi += 1
                else:
                    motor_elde_gun += 1
            else:
                motor_elde_gun += 1
                
            if use_settlement and takas_kalan_gun > 0:
                sermaye *= (1 + rt0)
                takas_kalan_gun -= 1
                g_ret = rt0
            else:
                if aktif_motor == "HUNTER":
                    g_ret = rh
                elif aktif_motor == "MOMENTUM":
                    g_ret = rm
                else:
                    g_ret = rdd
                sermaye *= (1 + g_ret)
                
            gunluk_kayitlar.append({
                "tarih": dt.strftime("%Y-%m-%d"),
                "bakiye": sermaye,
                "aktif_motor": aktif_motor,
                "gunluk_ret": g_ret
            })
            
        df_res = pd.DataFrame(gunluk_kayitlar)
        df_res["tarih"] = pd.to_datetime(df_res["tarih"])
        df_res.set_index("tarih", inplace=True)
        
        gun_sayisi = len(df_res)
        yil_sayisi = gun_sayisi / 252.0
        cagr = ((sermaye / self.baslangic_sermayesi) ** (1.0 / yil_sayisi) - 1.0) * 100.0
        
        df_res["peak"] = df_res["bakiye"].cummax()
        df_res["dd"] = (df_res["bakiye"] - df_res["peak"]) / df_res["peak"]
        mdd = df_res["dd"].min() * 100.0
        
        daily_rets = df_res["gunluk_ret"]
        mean_ret = daily_rets.mean()
        std_ret = daily_rets.std()
        sharpe = (mean_ret / (std_ret + 1e-9)) * np.sqrt(252)
        
        gains = daily_rets[daily_rets > 0].sum()
        losses = abs(daily_rets[daily_rets < 0].sum())
        pf = gains / losses if losses > 0 else np.nan
        
        yillik_ret = {}
        yillik_mdd = {}
        for y in sorted(df_res.index.year.unique()):
            sub = df_res[df_res.index.year == y]
            r = (sub["bakiye"].iloc[-1] - sub["bakiye"].iloc[0]) / sub["bakiye"].iloc[0] * 100.0
            p = sub["bakiye"].cummax()
            d = (sub["bakiye"] - p) / p
            yillik_ret[y] = r
            yillik_mdd[y] = d.min() * 100.0
            
        sub_2022 = df_res[df_res.index.year == 2022]
        savunma_gun_2022 = (sub_2022["aktif_motor"] == "DD_AWARE").sum()
        
        return {
            "window": window_days,
            "cagr": cagr,
            "son_bakiye": sermaye,
            "mdd": mdd,
            "sharpe": sharpe,
            "pf": pf,
            "gecis_sayisi": gecis_sayisi,
            "yillik_ret": yillik_ret,
            "yillik_mdd": yillik_mdd,
            "savunma_gun_2022": savunma_gun_2022
        }

def run_robustness_test():
    engine = Lab02RollingRobustnessEngine()
    windows = [20, 30, 45, 60, 75, 90, 120, 150, 180]
    
    sonuclar = []
    for w in windows:
        res = engine.simule_et_rolling(window_days=w)
        sonuclar.append(res)
        
    print("=" * 110)
    print("LAB-02: ROLLING PEAK DAYANIKLILIK VE KOMŞULUK (PLATEAU) TURNUVA MATRİSİ")
    print("=" * 110)
    
    hdr = f"{'Pencere (Gün)':<14} | {'CAGR':<10} | {'Son Bakiye':<14} | {'MaxDD':<10} | {'Sharpe':<8} | {'PF':<6} | {'2022':<10} | {'2026 YTD':<10} | {'2022 PPZ Gün'}"
    print(hdr)
    print("-" * 110)
    
    for s in sonuclar:
        w_lbl = f"{s['window']} Gün"
        if s['window'] == 60:
            w_lbl = f"--> {s['window']} Gün (*)"
        r22 = f"%{s['yillik_ret'].get(2022, 0):+.2f}"
        r26 = f"%{s['yillik_ret'].get(2026, 0):+.2f}"
        print(f"{w_lbl:<14} | %{s['cagr']:<8.2f} | {s['son_bakiye']:<12,.0f} TL | %{s['mdd']:<8.2f} | {s['sharpe']:<6.2f} | {s['pf']:<4.2f} | {r22:<10} | {r26:<10} | {s['savunma_gun_2022']}/252 gün")
        
    print("-" * 110)
    print("YILLARA GÖRE DETAYLI GETİRİ DAĞILIMI (TÜM PENCERELER):")
    print("-" * 110)
    
    y_hdr = f"{'Pencere':<12} | {'2021':<9} | {'2022':<9} | {'2023':<9} | {'2024':<9} | {'2025':<9} | {'2026 YTD':<10} | {'5Y MDD'}"
    print(y_hdr)
    print("-" * 110)
    for s in sonuclar:
        w_str = f"{s['window']} Gün"
        r21 = f"%{s['yillik_ret'].get(2021, 0):+.1f}"
        r22 = f"%{s['yillik_ret'].get(2022, 0):+.1f}"
        r23 = f"%{s['yillik_ret'].get(2023, 0):+.1f}"
        r24 = f"%{s['yillik_ret'].get(2024, 0):+.1f}"
        r25 = f"%{s['yillik_ret'].get(2025, 0):+.1f}"
        r26 = f"%{s['yillik_ret'].get(2026, 0):+.1f}"
        mdd_s = f"%{s['mdd']:.1f}"
        print(f"{w_str:<12} | {r21:<9} | {r22:<9} | {r23:<9} | {r24:<9} | {r25:<9} | {r26:<10} | {mdd_s}")
        
    print("=" * 110)

if __name__ == "__main__":
    run_robustness_test()
