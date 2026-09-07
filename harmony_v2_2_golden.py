"""
harmony_v2_2_golden.py
======================
HARMONY v2.2: Altın Denge (The Golden Balance) Meta Allocator
- V2'nin Yüksek Alfa ve Büyüme Gücü
- V2.1'in Kelebek Etkisi Karşıtı Dar Deadband & Histerezis Güvencesi
- Asimetrik Çevik Geçiş (Asymmetric Agile Re-Entry)
- Fon Nöbetçisi Alfa Takviyesi
"""

import os
import sys
import json
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Any, Optional

from meta_allocator_motor import MetaAllocatorMotor

class HarmonyV22GoldenMotor:
    def __init__(
        self,
        baslangic_sermayesi: float = 100_000.0,
        kayma_pct: float = 0.0005,
        min_hold_growth: int = 3,           # Büyüme motoruna geçişte çevik asgari süre (3 gün)
        min_hold_defense: int = 5,          # Savunmada asgari süre (5 gün)
        dd_trigger_high: float = 0.040,     # Korumaya geçiş çekilme eşiği (%4.0)
        dd_trigger_low: float = 0.028,      # Korumadan çıkış histerezis eşiği (%2.8 - Dar Deadband)
        confidence_spread_esigi: float = 0.020 # Momentum üstünlük güven eşiği (%2.0)
    ):
        self.baslangic_sermayesi = baslangic_sermayesi
        self.kayma_pct = kayma_pct
        self.min_hold_growth = min_hold_growth
        self.min_hold_defense = min_hold_defense
        self.dd_trigger_high = dd_trigger_high
        self.dd_trigger_low = dd_trigger_low
        self.confidence_spread_esigi = confidence_spread_esigi
        
        # Meta Motor Temeli
        self.base_motor = MetaAllocatorMotor(baslangic_sermayesi=baslangic_sermayesi, kayma_pct=kayma_pct)
        self.tarihler = self.base_motor.tarihler
        self.t0_ret_serisi = self.base_motor.t0_ret_serisi
        
        self.r_mom = self.base_motor.r_mom
        self.r_h6 = self.base_motor.r_h6
        self.r_dd = self.base_motor.r_dd
        self.r_sfb = self.base_motor.r_sfb
        
        self.market_breadth = self.base_motor.market_breadth
        self.top5_avg_r20 = self.base_motor.top5_avg_r20
        self.r20_df = self.base_motor.r20_df
        self.sfb_aktif_fon = self.base_motor.sfb_aktif_fon
        self.h6_aktif_fon = self.base_motor.h6_aktif_fon

    def simule_et_v2_2(
        self,
        varyant: str = "v2_2_agile", # 'v2_2_agile', 'v2_2_soft_brake', 'v2_2_turbo_alpha'
        baslangic_tarihi: Optional[str] = None,
        bitis_tarihi: Optional[str] = None,
        ozel_kayma_pct: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        HARMONY v2.2 Simülatörü.
        """
        kayma = ozel_kayma_pct if ozel_kayma_pct is not None else self.kayma_pct
        
        if baslangic_tarihi is None:
            b_idx = 65
        else:
            dt_b = pd.to_datetime(baslangic_tarihi)
            b_idx = next(i for i, t in enumerate(self.tarihler) if t >= dt_b)
            b_idx = max(65, b_idx)
            
        if bitis_tarihi is None:
            s_idx = len(self.tarihler) - 1
        else:
            dt_s = pd.to_datetime(bitis_tarihi)
            s_idx = next(i for i, t in reversed(list(enumerate(self.tarihler))) if t <= dt_s)
            
        tarih_dilimi = self.tarihler[b_idx : s_idx + 1]
        
        sermaye = self.baslangic_sermayesi
        zirve = self.baslangic_sermayesi
        gunluk_kayitlar = []
        
        aktif_motor = "HUNTER" # 'HUNTER', 'MOMENTUM', 'DD_AWARE', 'NOBETCI', 'SOFT_BUFFER'
        motor_elde_gun = 0
        savunma_modu = False
        toplam_motor_gecisi = 0
        t0_agirlik_toplami = 0.0
        
        gun_500k = None
        tarih_500k = None
        gun_700k = None
        tarih_700k = None
        
        for idx, dt in enumerate(tarih_dilimi):
            rm = self.r_mom.get(dt, 0.0)
            rh = self.r_h6.get(dt, 0.0)
            rdd = self.r_dd.get(dt, 0.0)
            rsfb = self.r_sfb.get(dt, 0.0)

            
            breadth = self.market_breadth.get(dt, 0.0)
            top5 = self.top5_avg_r20.get(dt, 0.0)
            
            f_sfb = self.sfb_aktif_fon.get(dt, "PPZ")
            f_h6 = self.h6_aktif_fon.get(dt, "PPZ")
            r20_s = self.r20_df.at[dt, f_sfb] if f_sfb in self.r20_df.columns and pd.notna(self.r20_df.at[dt, f_sfb]) else 0.0
            r20_h = self.r20_df.at[dt, f_h6] if f_h6 in self.r20_df.columns and pd.notna(self.r20_df.at[dt, f_h6]) else 0.0
            spread = r20_s - r20_h
            
            if sermaye > zirve:
                zirve = sermaye
            cur_dd = (zirve - sermaye) / (zirve + 1e-8)
            
            # =========================================================================
            # HARMONY v2.2 ALTIN DENGE MANTIĞI
            # =========================================================================
            if varyant == "v2_2_agile":
                # 1. Dar Deadband Histerezisi (%4.0 Giriş, %2.8 Çıkış)
                if cur_dd >= self.dd_trigger_high or breadth <= 0.25 or top5 <= 0.015:
                    savunma_modu = True
                elif cur_dd <= self.dd_trigger_low and (breadth >= 0.35 or top5 >= 0.03):
                    savunma_modu = False
                    
                # Hedef Motor
                if savunma_modu:
                    hedef_motor = "DD_AWARE"
                elif breadth >= 0.45 and spread >= self.confidence_spread_esigi and cur_dd < 0.028:
                    hedef_motor = "MOMENTUM"
                else:
                    hedef_motor = "HUNTER"
                    
                # Asimetrik Geçiş Kilidi
                asgari_sure = self.min_hold_defense if aktif_motor == "DD_AWARE" else self.min_hold_growth
                acil_fren = (hedef_motor == "DD_AWARE" and cur_dd >= 0.045)
                hizli_ralli_cikis = (aktif_motor == "DD_AWARE" and breadth >= 0.48 and spread >= 0.025)
                
                if hedef_motor != aktif_motor:
                    if motor_elde_gun >= asgari_sure or acil_fren or hizli_ralli_cikis:
                        sermaye *= (1.0 - kayma)
                        aktif_motor = hedef_motor
                        motor_elde_gun = 1
                        toplam_motor_gecisi += 1
                    else:
                        motor_elde_gun += 1
                else:
                    motor_elde_gun += 1
                    
            elif varyant == "v2_2_soft_brake":
                # 2. Kademeli Yumuşak Fren (Soft-Brake Transition)
                if cur_dd >= 0.048 or breadth <= 0.22:
                    hedef_motor = "DD_AWARE" # Tam Savunma
                elif cur_dd >= 0.032 or breadth <= 0.30:
                    hedef_motor = "SOFT_BUFFER" # %50 Hunter + %50 DD-Aware
                elif breadth >= 0.45 and spread >= 0.020 and cur_dd < 0.025:
                    hedef_motor = "MOMENTUM" # Tam Ralli
                else:
                    hedef_motor = "HUNTER" # Dengeli
                    
                if hedef_motor != aktif_motor:
                    if motor_elde_gun >= 3 or cur_dd >= 0.048:
                        sermaye *= (1.0 - kayma)
                        aktif_motor = hedef_motor
                        motor_elde_gun = 1
                        toplam_motor_gecisi += 1
                    else:
                        motor_elde_gun += 1
                else:
                    motor_elde_gun += 1
                    
            elif varyant == "v2_2_turbo_alpha":
                # 3. Turbo Fon Nöbetçisi + Çevik Deadband
                if cur_dd >= 0.040 or breadth <= 0.25:
                    savunma_modu = True
                elif cur_dd <= 0.028:
                    savunma_modu = False
                    
                if savunma_modu:
                    hedef_motor = "DD_AWARE"
                elif breadth >= 0.52 and r20_s >= 0.10 and spread >= 0.035:
                    hedef_motor = "NOBETCI" # Doğrudan %100 Saf Fon Nöbetçisi Turbo Modu!
                elif breadth >= 0.45 and spread >= 0.020 and cur_dd < 0.028:
                    hedef_motor = "MOMENTUM"
                else:
                    hedef_motor = "HUNTER"
                    
                if hedef_motor != aktif_motor:
                    if motor_elde_gun >= 3 or (hedef_motor == "DD_AWARE" and cur_dd >= 0.045):
                        sermaye *= (1.0 - kayma)
                        aktif_motor = hedef_motor
                        motor_elde_gun = 1
                        toplam_motor_gecisi += 1
                    else:
                        motor_elde_gun += 1
                else:
                    motor_elde_gun += 1
                    
            # Getiri Uygulama
            if aktif_motor == "HUNTER":
                gunluk_ret = rh
                eff_t0 = 0.31
            elif aktif_motor == "MOMENTUM":
                gunluk_ret = rm
                eff_t0 = 0.12
            elif aktif_motor == "NOBETCI":
                gunluk_ret = rsfb
                eff_t0 = 0.05
            elif aktif_motor == "SOFT_BUFFER":
                gunluk_ret = (0.50 * rh) + (0.50 * rdd)
                eff_t0 = 0.33
            else: # DD_AWARE
                gunluk_ret = rdd
                eff_t0 = 0.35
                
            sermaye *= (1 + gunluk_ret)
            t0_agirlik_toplami += eff_t0
            
            gun_no = idx + 1
            t_str = dt.strftime("%Y-%m-%d")
            if gun_500k is None and sermaye >= 500_000.0:
                gun_500k = gun_no
                tarih_500k = t_str
            if gun_700k is None and sermaye >= 700_000.0:
                gun_700k = gun_no
                tarih_700k = t_str
                
            gunluk_kayitlar.append({
                "tarih": t_str,
                "bakiye": sermaye,
                "aktif_motor": aktif_motor,
                "cur_dd": cur_dd
            })
            
        vals = np.array([k["bakiye"] for k in gunluk_kayitlar])
        n_days = len(vals)
        toplam_ret = (vals[-1] - self.baslangic_sermayesi) / self.baslangic_sermayesi * 100.0
        cagr = ((vals[-1] / self.baslangic_sermayesi) ** (252 / n_days) - 1) * 100.0 if n_days > 0 else 0.0
        kum_max = np.maximum.accumulate(vals)
        dd = (vals - kum_max) / (kum_max + 1e-8)
        mdd_pct = float(np.min(dd)) * 100.0
        max_tl_kayip = float(np.max(kum_max - vals))
        
        calmar = cagr / abs(mdd_pct) if abs(mdd_pct) > 1e-4 else 0.0
        gunluk_rets = np.diff(vals) / vals[:-1]
        
        rf_daily = (1 + 0.45) ** (1 / 252) - 1
        sharpe = float(np.mean(gunluk_rets - rf_daily) / (np.std(gunluk_rets, ddof=1) + 1e-8) * np.sqrt(252)) if len(gunluk_rets) > 1 else 0.0
        
        neg_rets = gunluk_rets[gunluk_rets < rf_daily] - rf_daily
        downside_std = np.std(neg_rets, ddof=1) if len(neg_rets) > 1 else 0.001
        sortino = float(np.mean(gunluk_rets - rf_daily) / (downside_std + 1e-8) * np.sqrt(252)) if len(gunluk_rets) > 1 else 0.0
        
        dd_durations = []
        cur_dur = 0
        for d_val in dd:
            if d_val < -0.001:
                cur_dur += 1
            else:
                if cur_dur > 0:
                    dd_durations.append(cur_dur)
                cur_dur = 0
        if cur_dur > 0:
            dd_durations.append(cur_dur)
        max_dd_duration = max(dd_durations) if dd_durations else 0
        
        df_log = pd.DataFrame(gunluk_kayitlar)
        df_log["dt"] = pd.to_datetime(df_log["tarih"])
        df_log["yil"] = df_log["dt"].dt.year
        
        yillik_getiriler = {}
        for y, grp in df_log.groupby("yil"):
            b_val = grp["bakiye"].iloc[0]
            e_val = grp["bakiye"].iloc[-1]
            y_ret = (e_val - b_val) / b_val * 100.0
            yillik_getiriler[y] = round(y_ret, 2)
            
        worst_year = min(yillik_getiriler.values()) if yillik_getiriler else 0.0
        worst_year_key = min(yillik_getiriler, key=yillik_getiriler.get) if yillik_getiriler else "N/A"
        worst_year_str = f"%{worst_year:.2f} ({worst_year_key})"
        
        t0_pct = (t0_agirlik_toplami / n_days * 100.0) if n_days > 0 else 0.0
        
        return {
            "model_kodu": f"HARMONY_{varyant}",
            "son_bakiye_tl": round(vals[-1], 2),
            "toplam_getiri_pct": round(toplam_ret, 2),
            "cagr_pct": round(cagr, 2),
            "max_drawdown_pct": round(mdd_pct, 2),
            "max_tl_kayip": round(max_tl_kayip, 2),
            "calmar_orani": round(calmar, 3),
            "sharpe_orani": round(sharpe, 2),
            "sortino_orani": round(sortino, 2),
            "max_dd_gun": max_dd_duration,
            "worst_year": worst_year_str,
            "yillik_getiriler": yillik_getiriler,
            "t0_sure_pct": round(t0_pct, 1),
            "gecis_sayisi": toplam_motor_gecisi,
            "ort_tutma_gunu": round(n_days / max(1, toplam_motor_gecisi), 1),
            "gun_500k": f"{gun_500k}. Gün ({tarih_500k})" if gun_500k else "Ulaşılmadı",
            "gun_700k": f"{gun_700k}. Gün ({tarih_700k})" if gun_700k else "Ulaşılmadı",
            "gunluk_kayitlar": gunluk_kayitlar
        }
