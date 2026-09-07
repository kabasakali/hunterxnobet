import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

"""
harmony_v2_1_adaptive.py
========================
HARMONY v2.1: Adaptive Switching Meta Allocator
- Kelebek Etkisine Karşı Histerezis & Deadband Güvencesi
- Confidence Threshold (Güven Eşiği)
- Minimum Engine Holding Period (15 Gün Asgari Motor Tutuşu)
- Fon Nöbetçisi, Hunter v6, Drawdown-Aware ve T0 Core 4'lü Koordinasyonu
"""

import os
import sys
import json
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Any, Optional

from meta_allocator_motor import MetaAllocatorMotor

class HarmonyV21AdaptiveMotor:
    def __init__(
        self,
        baslangic_sermayesi: float = 100_000.0,
        kayma_pct: float = 0.0005,
        min_motor_hold_gun: int = 15,       # Asgari motor tutma süresi (Churn önleyici)
        confidence_spread_esigi: float = 0.025, # Momentum üstünlük güven eşiği (%2.5)
        dd_trigger_high: float = 0.045,     # Korumaya geçiş çekilme eşiği (%4.5)
        dd_trigger_low: float = 0.020       # Korumadan çıkış histerezis eşiği (%2.0 - Deadband)
    ):
        self.baslangic_sermayesi = baslangic_sermayesi
        self.kayma_pct = kayma_pct
        self.min_motor_hold_gun = min_motor_hold_gun
        self.confidence_spread_esigi = confidence_spread_esigi
        self.dd_trigger_high = dd_trigger_high
        self.dd_trigger_low = dd_trigger_low
        
        # Temel Motor Altyapısı
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

    def simule_et_v2_1(
        self,
        varyant: str = "v2_1_adaptive",
        baslangic_tarihi: Optional[str] = None,
        bitis_tarihi: Optional[str] = None,
        ozel_kayma_pct: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        HARMONY v2.1 Adaptive Switching Simülasyonu.
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
        
        # Meta State
        aktif_motor = "HUNTER" # 'HUNTER', 'MOMENTUM', 'DD_AWARE', 'NOBETCI'
        motor_elde_gun = 0
        savunma_modu_aktif = False # Histerezis durumu
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
            rt0 = self.t0_ret_serisi.loc[dt]
            
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
            # HARMONY v2.1 ADAPTIVE SWITCHING MANTIĞI
            # =========================================================================
            # 1. Histerezis & Deadband Kontrolü:
            if cur_dd >= self.dd_trigger_high or breadth <= 0.22 or top5 <= 0.012:
                savunma_modu_aktif = True
            elif cur_dd <= self.dd_trigger_low and breadth >= 0.38:
                savunma_modu_aktif = False
                
            # Hedef Motor Seçimi
            if savunma_modu_aktif:
                hedef_motor = "DD_AWARE"
            elif breadth >= 0.48 and spread >= self.confidence_spread_esigi and cur_dd < 0.025:
                hedef_motor = "MOMENTUM"
            elif breadth >= 0.52 and r20_s >= 0.12 and spread >= 0.040:
                hedef_motor = "NOBETCI"
            else:
                hedef_motor = "HUNTER"
                
            # 2. Minimum Holding & Histerezis Koruması:
            if hedef_motor != aktif_motor:
                # Eğer acil bir savunma/çöküş yoksa, asgari tutma süresini bekle
                acil_durum = (hedef_motor == "DD_AWARE" and cur_dd >= 0.050)
                if motor_elde_gun >= self.min_motor_hold_gun or acil_durum:
                    # Motor Değişimi
                    sermaye *= (1.0 - kayma)
                    aktif_motor = hedef_motor
                    motor_elde_gun = 1
                    toplam_motor_gecisi += 1
                else:
                    motor_elde_gun += 1
            else:
                motor_elde_gun += 1
                
            # Günlük Getiri Uygulama
            if aktif_motor == "HUNTER":
                gunluk_ret = rh
                w_m, w_h, w_d, w_s = 0.0, 1.0, 0.0, 0.0
                eff_t0 = 0.31
            elif aktif_motor == "MOMENTUM":
                gunluk_ret = rm
                w_m, w_h, w_d, w_s = 1.0, 0.0, 0.0, 0.0
                eff_t0 = 0.12
            elif aktif_motor == "NOBETCI":
                gunluk_ret = rsfb
                w_m, w_h, w_d, w_s = 0.0, 0.0, 0.0, 1.0
                eff_t0 = 0.05
            else: # DD_AWARE
                gunluk_ret = rdd
                w_m, w_h, w_d, w_s = 0.0, 0.0, 1.0, 0.0
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
                "cur_dd": cur_dd,
                "breadth": breadth
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
            "model_kodu": "HARMONY_v2_1_Adaptive",
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
