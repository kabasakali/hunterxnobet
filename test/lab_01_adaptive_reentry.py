"""
test/lab_01_adaptive_reentry.py
===============================
LAB-01: ADAPTIVE RE-ENTRY (SAVUNMADAN ÇIKIŞ DİNAMİĞİ) AR-GE DENEYİ

Amaç:
2021 KKM şokunda yaşanan -%25 çekilme sonrasında sistemin 2022 boyunca
%20 mevduat faizinde (PPZ) kilitli kalmasını çözmek; bunu yaparken 2021
şokunu derinleştirmemek.

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

# Hunterxnobet dizini
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, base_dir)

from harmony_v1_motor import HarmonyMotor
from meta_allocator_motor import MetaAllocatorMotor
from harmony_v2_2_golden import HarmonyV22GoldenMotor

class Lab01AdaptiveReentryEngine:
    def __init__(self, baslangic_sermayesi: float = 100_000.0, kayma_pct: float = 0.0005):
        self.baslangic_sermayesi = baslangic_sermayesi
        self.kayma_pct = kayma_pct
        
        # Temel dondurulmuş motor
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

    def simule_et_lab(
        self,
        varyant_kodu: str = "V2_2_BENCHMARK",
        use_settlement: bool = True
    ) -> dict:
        """
        LAB-01 Varyant Simülatörü:
        - V2_2_BENCHMARK : Orijinal Dondurulmuş Harmony v2.2
        - LAB_A          : Breadth >= 0.45 ile Re-entry
        - LAB_B          : Breadth >= 0.45 + Top5 R20 > 0.015 (1.5%) ile Re-entry
        - LAB_C          : Breadth >= 0.45 + Spread > 0.02 + 2 Gün Persist (Teyitli)
        - LAB_D          : Breadth >= 0.50 + Top5 R20 >= 0.06 (Güçlü Boğa Teyitli)
        - LAB_E_ROLLING  : 60 Günlük Hareketli Zirve (Rolling Peak) + Breadth >= 0.40
        """
        sermaye = self.baslangic_sermayesi
        zirve = self.baslangic_sermayesi
        rolling_zirve_pencerisi = []
        
        tarih_dilimi = self.tarihler[65:]
        gunluk_kayitlar = []
        
        aktif_motor = "HUNTER"
        motor_elde_gun = 0
        savunma_modu = False
        takas_kalan_gun = 0
        gecis_sayisi = 0
        
        # Persist sayacı
        persist_sayaci = 0
        
        # Motor bazlı getiri katkı takibi
        motor_katkilari_tl = {"HUNTER": 0.0, "MOMENTUM": 0.0, "DD_AWARE": 0.0, "T0_NEMA": 0.0}
        
        for idx, dt in enumerate(tarih_dilimi):
            # 1. Alt motor ve nema getirileri (dt günü)
            rm = self.r_mom.get(dt, 0.0)
            rh = self.r_h6.get(dt, 0.0)
            rdd = self.r_dd.get(dt, 0.0)
            rt0 = self.t0_ret_serisi.loc[dt]
            
            # 2. Göstergeler (Katı T-1)
            breadth = self.market_breadth.get(dt, 0.0)
            top5 = self.top5_avg_r20.get(dt, 0.0)
            
            f_sfb = self.sfb_aktif_fon.get(dt, "PPZ")
            f_h6 = self.h6_aktif_fon.get(dt, "PPZ")
            r20_s = self.r20_df.at[dt, f_sfb] if f_sfb in self.r20_df.columns and pd.notna(self.r20_df.at[dt, f_sfb]) else 0.0
            r20_h = self.r20_df.at[dt, f_h6] if f_h6 in self.r20_df.columns and pd.notna(self.r20_df.at[dt, f_h6]) else 0.0
            spread = r20_s - r20_h
            
            # 3. Zirve ve Drawdown Hesabı
            if sermaye > zirve:
                zirve = sermaye
            cur_dd = (zirve - sermaye) / (zirve + 1e-8)
            
            # Rolling zirve (Varyant E için)
            rolling_zirve_pencerisi.append(sermaye)
            if len(rolling_zirve_pencerisi) > 60:
                rolling_zirve_pencerisi.pop(0)
            local_peak = max(rolling_zirve_pencerisi)
            local_dd = (local_peak - sermaye) / (local_peak + 1e-8)
            
            # 4. Nöbetçi Onay
            nobetci_onay = (spread >= 0.020 and r20_s >= 0.03 and breadth >= 0.45)
            
            # 5. RE-ENTRY VE SAVUNMA KARAR MANTIĞI
            if varyant_kodu == "V2_2_BENCHMARK":
                # Orijinal: Zirveden %2.8 altına inmeden ve breadth >= 0.35 olmadan savunmadan çıkamaz
                if cur_dd >= 0.040 or breadth <= 0.25 or top5 <= 0.015:
                    savunma_modu = True
                elif cur_dd <= 0.028 and (breadth >= 0.35 or top5 >= 0.03):
                    savunma_modu = False
                    
            elif varyant_kodu == "LAB_A":
                # Kural A: Breadth >= 0.45 ise zirveye bakmaksızın Re-entry
                if cur_dd >= 0.040 or breadth <= 0.25 or top5 <= 0.015:
                    savunma_modu = True
                if breadth >= 0.45:
                    savunma_modu = False
                    
            elif varyant_kodu == "LAB_B":
                # Kural B: Breadth >= 0.45 + Top5 > 1.5% ise Re-entry
                if cur_dd >= 0.040 or breadth <= 0.25 or top5 <= 0.015:
                    savunma_modu = True
                if breadth >= 0.45 and top5 > 0.015:
                    savunma_modu = False
                    
            elif varyant_kodu == "LAB_C":
                # Kural C: Breadth >= 0.45 + Spread > 0.02 + 2 Gün Persist
                if cur_dd >= 0.040 or breadth <= 0.25 or top5 <= 0.015:
                    savunma_modu = True
                    persist_sayaci = 0
                if breadth >= 0.45 and spread > 0.020:
                    persist_sayaci += 1
                else:
                    persist_sayaci = 0
                if persist_sayaci >= 2:
                    savunma_modu = False
                    
            elif varyant_kodu == "LAB_D":
                # Kural D: Breadth >= 0.50 + Top5 >= 0.06 (Güçlü Boğa Teyidi)
                if cur_dd >= 0.040 or breadth <= 0.25 or top5 <= 0.015:
                    savunma_modu = True
                if breadth >= 0.50 and top5 >= 0.06:
                    savunma_modu = False
                    
            elif varyant_kodu == "LAB_E_ROLLING":
                # Kural E: Yerel 60 Günlük Zirveden DD < %3.0 + Breadth >= 0.40
                if local_dd >= 0.040 or breadth <= 0.25 or top5 <= 0.015:
                    savunma_modu = True
                elif local_dd <= 0.025 and (breadth >= 0.40 or top5 >= 0.03):
                    savunma_modu = False
                    
            # 6. Hedef Motor Belirleme
            if savunma_modu:
                hedef_motor = "DD_AWARE"
            elif nobetci_onay and (cur_dd < 0.028 or varyant_kodu != "V2_2_BENCHMARK"):
                hedef_motor = "MOMENTUM"
            else:
                hedef_motor = "HUNTER"
                
            # 7. İcra ve Geçiş Kontrolü
            asgari_sure = 5 if aktif_motor == "DD_AWARE" else 3
            acil_fren = (hedef_motor == "DD_AWARE" and (cur_dd >= 0.045 or (varyant_kodu == "LAB_E_ROLLING" and local_dd >= 0.045)))
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
                
            # 8. Günlük Getiri Uygulama
            onceki_sermaye = sermaye
            if use_settlement and takas_kalan_gun > 0:
                sermaye *= (1 + rt0)
                takas_kalan_gun -= 1
                g_ret = rt0
                motor_katkilari_tl["T0_NEMA"] += (sermaye - onceki_sermaye)
            else:
                if aktif_motor == "HUNTER":
                    g_ret = rh
                    motor_katkilari_tl["HUNTER"] += (sermaye * g_ret)
                elif aktif_motor == "MOMENTUM":
                    g_ret = rm
                    motor_katkilari_tl["MOMENTUM"] += (sermaye * g_ret)
                else:
                    g_ret = rdd
                    motor_katkilari_tl["DD_AWARE"] += (sermaye * g_ret)
                sermaye *= (1 + g_ret)
                
            gunluk_kayitlar.append({
                "tarih": dt.strftime("%Y-%m-%d"),
                "bakiye": sermaye,
                "aktif_motor": aktif_motor,
                "savunma_modu": savunma_modu,
                "breadth": breadth,
                "cur_dd": cur_dd,
                "gunluk_ret": g_ret
            })
            
        df_res = pd.DataFrame(gunluk_kayitlar)
        df_res["tarih"] = pd.to_datetime(df_res["tarih"])
        df_res.set_index("tarih", inplace=True)
        
        # Metrikler
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
        
        # Yıllık Getiriler
        yillik_ret = {}
        yillik_mdd = {}
        for y in sorted(df_res.index.year.unique()):
            sub = df_res[df_res.index.year == y]
            r = (sub["bakiye"].iloc[-1] - sub["bakiye"].iloc[0]) / sub["bakiye"].iloc[0] * 100.0
            p = sub["bakiye"].cummax()
            d = (sub["bakiye"] - p) / p
            yillik_ret[y] = r
            yillik_mdd[y] = d.min() * 100.0
            
        # 2022'de Savunmada Geçen Gün Sayısı
        sub_2022 = df_res[df_res.index.year == 2022]
        savunma_gun_2022 = (sub_2022["aktif_motor"] == "DD_AWARE").sum()
        
        return {
            "varyant": varyant_kodu,
            "cagr": cagr,
            "son_bakiye": sermaye,
            "mdd": mdd,
            "sharpe": sharpe,
            "pf": pf,
            "gecis_sayisi": gecis_sayisi,
            "yillik_ret": yillik_ret,
            "yillik_mdd": yillik_mdd,
            "savunma_gun_2022": savunma_gun_2022,
            "toplam_gun_2022": len(sub_2022),
            "motor_katkilari": motor_katkilari_tl,
            "df_res": df_res
        }

def run_lab_01_tournament():
    engine = Lab01AdaptiveReentryEngine()
    
    varyantlar = ["V2_2_BENCHMARK", "LAB_A", "LAB_B", "LAB_C", "LAB_D", "LAB_E_ROLLING"]
    sonuclar = {}
    
    for v in varyantlar:
        sonuclar[v] = engine.simule_et_lab(varyant_kodu=v)
        
    print("=" * 110)
    print("LAB-01: ADAPTIVE RE-ENTRY AR-GE TURNUVASI RESMI KARSILASTIRMA MATRISI")
    print("=" * 110)
    
    # Başlık Tablosu
    header = f"{'Metrik':<20} | {'V2.2 (Ref)':<12} | {'LAB-A (B45)':<12} | {'LAB-B (B45+T)':<13} | {'LAB-C (Persist)':<14} | {'LAB-D (B50+T6)':<14} | {'LAB-E (Rolling)':<14}"
    print(header)
    print("-" * 110)
    
    print(f"{'5Y CAGR':<20} | %{sonuclar['V2_2_BENCHMARK']['cagr']:<10.2f} | %{sonuclar['LAB_A']['cagr']:<10.2f} | %{sonuclar['LAB_B']['cagr']:<11.2f} | %{sonuclar['LAB_C']['cagr']:<12.2f} | %{sonuclar['LAB_D']['cagr']:<12.2f} | %{sonuclar['LAB_E_ROLLING']['cagr']:<12.2f}")
    print(f"{'Son Bakiye (100k)':<20} | {sonuclar['V2_2_BENCHMARK']['son_bakiye']:<11,.0f} | {sonuclar['LAB_A']['son_bakiye']:<11,.0f} | {sonuclar['LAB_B']['son_bakiye']:<12,.0f} | {sonuclar['LAB_C']['son_bakiye']:<13,.0f} | {sonuclar['LAB_D']['son_bakiye']:<13,.0f} | {sonuclar['LAB_E_ROLLING']['son_bakiye']:<13,.0f}")
    print(f"{'Max Drawdown':<20} | %{sonuclar['V2_2_BENCHMARK']['mdd']:<10.2f} | %{sonuclar['LAB_A']['mdd']:<10.2f} | %{sonuclar['LAB_B']['mdd']:<11.2f} | %{sonuclar['LAB_C']['mdd']:<12.2f} | %{sonuclar['LAB_D']['mdd']:<12.2f} | %{sonuclar['LAB_E_ROLLING']['mdd']:<12.2f}")
    print(f"{'Sharpe Orani':<20} | {sonuclar['V2_2_BENCHMARK']['sharpe']:<12.2f} | {sonuclar['LAB_A']['sharpe']:<12.2f} | {sonuclar['LAB_B']['sharpe']:<13.2f} | {sonuclar['LAB_C']['sharpe']:<14.2f} | {sonuclar['LAB_D']['sharpe']:<14.2f} | {sonuclar['LAB_E_ROLLING']['sharpe']:<14.2f}")
    print(f"{'Profit Factor':<20} | {sonuclar['V2_2_BENCHMARK']['pf']:<12.2f} | {sonuclar['LAB_A']['pf']:<12.2f} | {sonuclar['LAB_B']['pf']:<13.2f} | {sonuclar['LAB_C']['pf']:<14.2f} | {sonuclar['LAB_D']['pf']:<14.2f} | {sonuclar['LAB_E_ROLLING']['pf']:<14.2f}")
    print(f"{'Toplam Islem':<20} | {sonuclar['V2_2_BENCHMARK']['gecis_sayisi']:<12} | {sonuclar['LAB_A']['gecis_sayisi']:<12} | {sonuclar['LAB_B']['gecis_sayisi']:<13} | {sonuclar['LAB_C']['gecis_sayisi']:<14} | {sonuclar['LAB_D']['gecis_sayisi']:<14} | {sonuclar['LAB_E_ROLLING']['gecis_sayisi']:<14}")
    print(f"{'2022 PPZ Gun / Top':<20} | {sonuclar['V2_2_BENCHMARK']['savunma_gun_2022']}/{sonuclar['V2_2_BENCHMARK']['toplam_gun_2022']:<8} | {sonuclar['LAB_A']['savunma_gun_2022']}/{sonuclar['LAB_A']['toplam_gun_2022']:<8} | {sonuclar['LAB_B']['savunma_gun_2022']}/{sonuclar['LAB_B']['toplam_gun_2022']:<9} | {sonuclar['LAB_C']['savunma_gun_2022']}/{sonuclar['LAB_C']['toplam_gun_2022']:<10} | {sonuclar['LAB_D']['savunma_gun_2022']}/{sonuclar['LAB_D']['toplam_gun_2022']:<10} | {sonuclar['LAB_E_ROLLING']['savunma_gun_2022']}/{sonuclar['LAB_E_ROLLING']['toplam_gun_2022']:<10}")
    
    print("-" * 110)
    print("YILLIK GETIRILER:")
    for y in [2021, 2022, 2023, 2024, 2025, 2026]:
        lbl = "2026 YTD" if y == 2026 else str(y)
        print(f"{lbl:<20} | %{sonuclar['V2_2_BENCHMARK']['yillik_ret'].get(y, 0):<+10.2f} | %{sonuclar['LAB_A']['yillik_ret'].get(y, 0):<+10.2f} | %{sonuclar['LAB_B']['yillik_ret'].get(y, 0):<+11.2f} | %{sonuclar['LAB_C']['yillik_ret'].get(y, 0):<+12.2f} | %{sonuclar['LAB_D']['yillik_ret'].get(y, 0):<+12.2f} | %{sonuclar['LAB_E_ROLLING']['yillik_ret'].get(y, 0):<+12.2f}")
        
    print("-" * 110)
    print("YILLIK MAX DRAWDOWN:")
    for y in [2021, 2022, 2023, 2024, 2025, 2026]:
        lbl = "2026 YTD" if y == 2026 else str(y)
        print(f"{lbl:<20} | %{sonuclar['V2_2_BENCHMARK']['yillik_mdd'].get(y, 0):<10.2f} | %{sonuclar['LAB_A']['yillik_mdd'].get(y, 0):<10.2f} | %{sonuclar['LAB_B']['yillik_mdd'].get(y, 0):<11.2f} | %{sonuclar['LAB_C']['yillik_mdd'].get(y, 0):<12.2f} | %{sonuclar['LAB_D']['yillik_mdd'].get(y, 0):<12.2f} | %{sonuclar['LAB_E_ROLLING']['yillik_mdd'].get(y, 0):<12.2f}")
        
    print("=" * 110)


if __name__ == "__main__":
    run_lab_01_tournament()
