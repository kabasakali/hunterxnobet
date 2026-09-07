import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

"""
v2_2_adversarial_break_test.py
==============================
HARMONY v2.2 (Altın Denge) 4 Boyutlu Kırma ve Dayanıklılık Test Paketi:
1. Kayma Taraması (%0.00 -> %1.00, 101 Nokta)
2. Başlangıç Tarihi Taraması (Rolling Start Date Sweep)
3. Parametre Perturbasyon Yüzeyi (5x5 = 25 Nokta)
4. Fon Nöbetçisi & Bileşen Ablation Testi (Alfa İzolasyonu)
"""

import os
import sys
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Any, Optional

from harmony_v2_2_golden import HarmonyV22GoldenMotor
from meta_allocator_motor import MetaAllocatorMotor

class HarmonyV22AdversarialAuditor:
    def __init__(self):
        self.engine = HarmonyV22GoldenMotor()
        self.tarihler = self.engine.tarihler

    # -------------------------------------------------------------------------
    # 1. TEST: KAYMA TARAMASI (%0.00 -> %1.00, 101 NOKTA)
    # -------------------------------------------------------------------------
    def kayma_sweep_testi(self) -> Dict[str, Any]:
        kayma_oranlari = np.linspace(0.000, 0.010, 101) # %0.00 -> %1.00
        kayitlar = []
        anomali_sayisi = 0
        
        prev_bakiye = None
        for k in kayma_oranlari:
            res = self.engine.simule_et_v2_2("v2_2_agile", ozel_kayma_pct=float(k))
            bakiye = res["son_bakiye_tl"]
            
            # Anomali kontrolü: Kayma artarken bakiye belirgin artmış mı?
            if prev_bakiye is not None and (bakiye - prev_bakiye) > (prev_bakiye * 0.005):
                anomali_sayisi += 1
                
            prev_bakiye = bakiye
            kayitlar.append({
                "kayma_pct": float(k * 100.0),
                "son_bakiye_tl": bakiye,
                "cagr_pct": res["cagr_pct"],
                "max_drawdown_pct": res["max_drawdown_pct"],
                "calmar_orani": res["calmar_orani"]
            })
            
        df_kayma = pd.DataFrame(kayitlar)
        monotonluk_orani = (1.0 - (anomali_sayisi / 100.0)) * 100.0
        
        return {
            "df_kayma": df_kayma,
            "anomali_sayisi": anomali_sayisi,
            "monotonluk_orani": monotonluk_orani,
            "bakiye_0pct": df_kayma.iloc[0]["son_bakiye_tl"],
            "bakiye_005pct": df_kayma.iloc[5]["son_bakiye_tl"],
            "bakiye_010pct": df_kayma.iloc[10]["son_bakiye_tl"],
            "bakiye_020pct": df_kayma.iloc[20]["son_bakiye_tl"],
            "bakiye_050pct": df_kayma.iloc[50]["son_bakiye_tl"],
            "bakiye_100pct": df_kayma.iloc[100]["son_bakiye_tl"],
        }

    # -------------------------------------------------------------------------
    # 2. TEST: BAŞLANGIÇ TARİHİ TARAMASI (ROLLING START DATE SWEEP)
    # -------------------------------------------------------------------------
    def baslangic_tarihi_sweep_testi(self, adim_gun: int = 20) -> Dict[str, Any]:
        pencereler = []
        
        # 65. günden 650. güne kadar her 20 günde bir başlat (2021 sonu - 2024 başı arası başlangıçlar)
        for b_idx in range(65, 650, adim_gun):
            dt_bas = self.tarihler[b_idx].strftime("%Y-%m-%d")
            res = self.engine.simule_et_v2_2("v2_2_agile", baslangic_tarihi=dt_bas)
            
            pencereler.append({
                "baslangic_tarihi": dt_bas,
                "islem_gunu_sayisi": len(res["gunluk_kayitlar"]),
                "son_bakiye_tl": res["son_bakiye_tl"],
                "toplam_getiri_pct": res["toplam_getiri_pct"],
                "cagr_pct": res["cagr_pct"],
                "max_drawdown_pct": res["max_drawdown_pct"],
                "calmar_orani": res["calmar_orani"],
                "sharpe_orani": res["sharpe_orani"],
                "sortino_orani": res["sortino_orani"]
            })
            
        df_pencere = pd.DataFrame(pencereler)
        
        return {
            "df_pencereler": df_pencere,
            "toplam_pencere": len(df_pencere),
            "medyan_cagr": df_pencere["cagr_pct"].median(),
            "ortalama_cagr": df_pencere["cagr_pct"].mean(),
            "min_cagr": df_pencere["cagr_pct"].min(),
            "max_cagr": df_pencere["cagr_pct"].max(),
            "medyan_max_dd": df_pencere["max_drawdown_pct"].median(),
            "en_kotu_max_dd": df_pencere["max_drawdown_pct"].min(),
            "medyan_calmar": df_pencere["calmar_orani"].median(),
            "min_calmar": df_pencere["calmar_orani"].min()
        }

    # -------------------------------------------------------------------------
    # 3. TEST: PARAMETRE HASSASİYET MATRİSİ (5x5 = 25 NOKTA)
    # -------------------------------------------------------------------------
    def parametre_perturbation_testi(self) -> Dict[str, Any]:
        high_list = [0.035, 0.038, 0.040, 0.042, 0.045]
        low_list = [0.023, 0.025, 0.028, 0.030, 0.033]
        
        matris_kayitlari = []
        
        for h in high_list:
            for l in low_list:
                # Geçici motor oluştur
                temp_eng = HarmonyV22GoldenMotor(
                    dd_trigger_high=h,
                    dd_trigger_low=l
                )
                res = temp_eng.simule_et_v2_2("v2_2_agile")
                
                matris_kayitlari.append({
                    "DD_Giris (%)": f"%{h*100:.1f}",
                    "DD_Cikis (%)": f"%{l*100:.1f}",
                    "Deadband": f"%{(h-l)*100:.1f}",
                    "Son Bakiye": res["son_bakiye_tl"],
                    "CAGR (%)": res["cagr_pct"],
                    "Max DD (%)": res["max_drawdown_pct"],
                    "Calmar": res["calmar_orani"],
                    "Sharpe": res["sharpe_orani"],
                    "Sortino": res["sortino_orani"]
                })
                
        df_pert = pd.DataFrame(matris_kayitlari)
        
        return {
            "df_perturbation": df_pert,
            "ortalama_bakiye": df_pert["Son Bakiye"].mean(),
            "medyan_bakiye": df_pert["Son Bakiye"].median(),
            "min_bakiye": df_pert["Son Bakiye"].min(),
            "max_bakiye": df_pert["Son Bakiye"].max(),
            "ortalama_cagr": df_pert["CAGR (%)"].mean(),
            "std_cagr": df_pert["CAGR (%)"].std(),
            "ortalama_max_dd": df_pert["Max DD (%)"].mean(),
            "en_kotu_max_dd": df_pert["Max DD (%)"].min(),
            "ortalama_calmar": df_pert["Calmar"].mean(),
            "min_calmar": df_pert["Calmar"].min(),
        }

    # -------------------------------------------------------------------------
    # 4. TEST: ABLATION TESTİ (FON NÖBETÇİSİ ALFA İZOLASYONU)
    # -------------------------------------------------------------------------
    def ablation_testi(self) -> Dict[str, Any]:
        """
        Her bileşenin sisteme net katkısını ölçer:
        1. Tam Model (V2.2 Altın Denge)
        2. Fon Nöbetçisi Devre Dışı (Yalnızca Hunter + DD-Aware + T0)
        3. Hunter Devre Dışı (Yalnızca Fon Nöbetçisi + DD-Aware + T0)
        4. Savunma (DD-Aware) Devre Dışı (Yalnızca Hunter + Fon Nöbetçisi + T0)
        """
        # 1. Tam Model
        r_full = self.engine.simule_et_v2_2("v2_2_agile")
        
        # 2. SFB / Nöbetçi Devre Dışı Modeli Simüle Et
        # (Momentum ralli sinyalinde dahi Hunter'da kal)
        kayitlar_no_sfb = []
        sermaye = 100_000.0
        zirve = 100_000.0
        aktif_motor = "HUNTER"
        motor_elde_gun = 0
        savunma_modu = False
        tarih_dilimi = self.tarihler[65:]
        
        for idx, dt in enumerate(tarih_dilimi):
            rh = self.engine.r_h6.get(dt, 0.0)
            rdd = self.engine.r_dd.get(dt, 0.0)
            breadth = self.engine.market_breadth.get(dt, 0.0)
            top5 = self.engine.top5_avg_r20.get(dt, 0.0)
            
            if sermaye > zirve:
                zirve = sermaye
            cur_dd = (zirve - sermaye) / (zirve + 1e-8)
            
            if cur_dd >= 0.040 or breadth <= 0.25 or top5 <= 0.015:
                savunma_modu = True
            elif cur_dd <= 0.028 and (breadth >= 0.35 or top5 >= 0.03):
                savunma_modu = False
                
            hedef_motor = "DD_AWARE" if savunma_modu else "HUNTER"
            
            asgari_sure = 5 if aktif_motor == "DD_AWARE" else 3
            if hedef_motor != aktif_motor:
                if motor_elde_gun >= asgari_sure or (hedef_motor == "DD_AWARE" and cur_dd >= 0.045):
                    sermaye *= (1.0 - self.engine.kayma_pct)
                    aktif_motor = hedef_motor
                    motor_elde_gun = 1
                else:
                    motor_elde_gun += 1
            else:
                motor_elde_gun += 1
                
            gunluk_ret = rh if aktif_motor == "HUNTER" else rdd
            sermaye *= (1 + gunluk_ret)
            kayitlar_no_sfb.append(sermaye)
            
        vals_no_sfb = np.array(kayitlar_no_sfb)
        n_days = len(vals_no_sfb)
        cagr_no_sfb = ((vals_no_sfb[-1] / 100_000.0) ** (252 / n_days) - 1) * 100.0
        kum_max = np.maximum.accumulate(vals_no_sfb)
        mdd_no_sfb = float(np.min((vals_no_sfb - kum_max) / (kum_max + 1e-8))) * 100.0
        calmar_no_sfb = cagr_no_sfb / abs(mdd_no_sfb)
        
        # 3. Hunter Devre Dışı Modeli (Yalnızca SFB + DD-Aware)
        kayitlar_no_hunter = []
        sermaye_h = 100_000.0
        zirve_h = 100_000.0
        aktif_motor_h = "MOMENTUM"
        motor_elde_gun_h = 0
        savunma_modu_h = False
        
        for idx, dt in enumerate(tarih_dilimi):
            rm = self.engine.r_mom.get(dt, 0.0)
            rdd = self.engine.r_dd.get(dt, 0.0)
            breadth = self.engine.market_breadth.get(dt, 0.0)
            top5 = self.engine.top5_avg_r20.get(dt, 0.0)
            
            if sermaye_h > zirve_h:
                zirve_h = sermaye_h
            cur_dd = (zirve_h - sermaye_h) / (zirve_h + 1e-8)
            
            if cur_dd >= 0.040 or breadth <= 0.25 or top5 <= 0.015:
                savunma_modu_h = True
            elif cur_dd <= 0.028 and (breadth >= 0.35 or top5 >= 0.03):
                savunma_modu_h = False
                
            hedef_motor = "DD_AWARE" if savunma_modu_h else "MOMENTUM"
            
            asgari_sure = 5 if aktif_motor_h == "DD_AWARE" else 3
            if hedef_motor != aktif_motor_h:
                if motor_elde_gun_h >= asgari_sure or (hedef_motor == "DD_AWARE" and cur_dd >= 0.045):
                    sermaye_h *= (1.0 - self.engine.kayma_pct)
                    aktif_motor_h = hedef_motor
                    motor_elde_gun_h = 1
                else:
                    motor_elde_gun_h += 1
            else:
                motor_elde_gun_h += 1
                
            gunluk_ret = rm if aktif_motor_h == "MOMENTUM" else rdd
            sermaye_h *= (1 + gunluk_ret)
            kayitlar_no_hunter.append(sermaye_h)
            
        vals_no_h = np.array(kayitlar_no_hunter)
        cagr_no_h = ((vals_no_h[-1] / 100_000.0) ** (252 / n_days) - 1) * 100.0
        kum_max_h = np.maximum.accumulate(vals_no_h)
        mdd_no_h = float(np.min((vals_no_h - kum_max_h) / (kum_max_h + 1e-8))) * 100.0
        calmar_no_h = cagr_no_h / abs(mdd_no_h)
        
        # 4. Savunma (DD-Aware) Devre Dışı Modeli (Yalnızca Hunter + Momentum Ralli)
        kayitlar_no_def = []
        sermaye_d = 100_000.0
        zirve_d = 100_000.0
        aktif_motor_d = "HUNTER"
        motor_elde_gun_d = 0
        
        for idx, dt in enumerate(tarih_dilimi):
            rm = self.engine.r_mom.get(dt, 0.0)
            rh = self.engine.r_h6.get(dt, 0.0)
            breadth = self.engine.market_breadth.get(dt, 0.0)
            
            f_sfb = self.engine.sfb_aktif_fon.get(dt, "PPZ")
            f_h6 = self.engine.h6_aktif_fon.get(dt, "PPZ")
            r20_s = self.engine.r20_df.at[dt, f_sfb] if f_sfb in self.engine.r20_df.columns and pd.notna(self.engine.r20_df.at[dt, f_sfb]) else 0.0
            r20_h = self.engine.r20_df.at[dt, f_h6] if f_h6 in self.engine.r20_df.columns and pd.notna(self.engine.r20_df.at[dt, f_h6]) else 0.0
            spread = r20_s - r20_h
            
            if breadth >= 0.45 and spread >= 0.020:
                hedef_motor = "MOMENTUM"
            else:
                hedef_motor = "HUNTER"
                
            if hedef_motor != aktif_motor_d:
                if motor_elde_gun_d >= 3:
                    sermaye_d *= (1.0 - self.engine.kayma_pct)
                    aktif_motor_d = hedef_motor
                    motor_elde_gun_d = 1
                else:
                    motor_elde_gun_d += 1
            else:
                motor_elde_gun_d += 1
                
            gunluk_ret = rm if aktif_motor_d == "MOMENTUM" else rh
            sermaye_d *= (1 + gunluk_ret)
            kayitlar_no_def.append(sermaye_d)
            
        vals_no_def = np.array(kayitlar_no_def)
        cagr_no_def = ((vals_no_def[-1] / 100_000.0) ** (252 / n_days) - 1) * 100.0
        kum_max_d = np.maximum.accumulate(vals_no_def)
        mdd_no_def = float(np.min((vals_no_def - kum_max_d) / (kum_max_d + 1e-8))) * 100.0
        calmar_no_def = cagr_no_def / abs(mdd_no_def)
        
        return {
            "tam_model": {
                "bakiye": r_full["son_bakiye_tl"],
                "cagr": r_full["cagr_pct"],
                "mdd": r_full["max_drawdown_pct"],
                "calmar": r_full["calmar_orani"]
            },
            "no_nobetci": {
                "bakiye": round(vals_no_sfb[-1], 2),
                "cagr": round(cagr_no_sfb, 2),
                "mdd": round(mdd_no_sfb, 2),
                "calmar": round(calmar_no_sfb, 2)
            },
            "no_hunter": {
                "bakiye": round(vals_no_h[-1], 2),
                "cagr": round(cagr_no_h, 2),
                "mdd": round(mdd_no_h, 2),
                "calmar": round(calmar_no_h, 2)
            },
            "no_savunma": {
                "bakiye": round(vals_no_def[-1], 2),
                "cagr": round(cagr_no_def, 2),
                "mdd": round(mdd_no_def, 2),
                "calmar": round(calmar_no_def, 2)
            },
            "nobetci_net_tl_alfa": round(r_full["son_bakiye_tl"] - vals_no_sfb[-1], 2),
            "nobetci_net_cagr_alfa": round(r_full["cagr_pct"] - cagr_no_sfb, 2),
            "hunter_net_tl_katki": round(r_full["son_bakiye_tl"] - vals_no_h[-1], 2),
            "savunma_mdd_iyilestirme": round(abs(mdd_no_def) - abs(r_full["max_drawdown_pct"]), 2)
        }
