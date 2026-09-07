"""
meta_allocator_motor.py
=======================
Meta Allocator (HARMONY v2): Riske-Ayarlı Üst Portföy Motoru (2021 - 2026).
3 Temel Kişilik (🚀 Momentum Spread, 🎯 Hunter v6, 🛡️ Drawdown-Aware) + 🏦 T0 Core Kasa.
"""

import os
import sys
import json
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Any, Optional

from harmony_v1_motor import HarmonyMotor

class MetaAllocatorMotor:
    def __init__(
        self,
        baslangic_sermayesi: float = 100_000.0,
        kayma_pct: float = 0.0005
    ):
        self.baslangic_sermayesi = baslangic_sermayesi
        self.kayma_pct = kayma_pct
        
        # 1. Alt Motor Altyapısını Başlat
        self.base_motor = HarmonyMotor(baslangic_sermayesi=baslangic_sermayesi, kayma_pct=kayma_pct)
        self.tarihler = self.base_motor.tarihler
        self.t0_ret_serisi = self.base_motor.t0_ret_serisi
        
        # 2. Üç Temel Kişiliğin Günlük Getirilerini Al
        self._temel_kisiliklerin_getirilerini_cikar()

    def _temel_kisiliklerin_getirilerini_cikar(self):
        """
        3 Temel Kişiliğin ve Alt Motorların Günlük Getiri Dizilerini Çıkarır:
        - r_mom: Momentum Spread Motoru (🚀 Büyüme)
        - r_h6: Saf Hunter v6 Motoru (🎯 Dengeli Alfa)
        - r_dd: Drawdown-Aware Motoru (🛡️ Sermaye Koruma)
        - r_sfb: Saf Fon Nöbetçisi (🦁 Serbest Fon)
        - r_t0: T0 Core Kasa (🏦 Nakit)
        """
        # Momentum Spread
        res_mom = self.base_motor.simule_et_model("momentum_spread")
        # Drawdown Aware
        res_dd = self.base_motor.simule_et_model("dd_aware_switching")
        
        self.r_mom = {}
        for i, k in enumerate(res_mom["gunluk_kayitlar"]):
            dt = pd.to_datetime(k["tarih"])
            if i == 0:
                self.r_mom[dt] = (k["bakiye"] - self.baslangic_sermayesi) / self.baslangic_sermayesi
            else:
                prev_b = res_mom["gunluk_kayitlar"][i-1]["bakiye"]
                self.r_mom[dt] = (k["bakiye"] - prev_b) / prev_b
                
        self.r_dd = {}
        for i, k in enumerate(res_dd["gunluk_kayitlar"]):
            dt = pd.to_datetime(k["tarih"])
            if i == 0:
                self.r_dd[dt] = (k["bakiye"] - self.baslangic_sermayesi) / self.baslangic_sermayesi
            else:
                prev_b = res_dd["gunluk_kayitlar"][i-1]["bakiye"]
                self.r_dd[dt] = (k["bakiye"] - prev_b) / prev_b
                
        self.r_h6 = self.base_motor.h6_gunluk_ret
        self.r_sfb = self.base_motor.sfb_gunluk_ret
        self.market_breadth = self.base_motor.market_breadth
        self.top5_avg_r20 = self.base_motor.top5_avg_r20
        self.r20_df = self.base_motor.r20_df
        self.sfb_aktif_fon = self.base_motor.sfb_aktif_fon
        self.h6_aktif_fon = self.base_motor.h6_aktif_fon

    def simule_et_meta(
        self,
        meta_model_kodu: str,
        baslangic_tarihi: Optional[str] = None,
        bitis_tarihi: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Meta Allocator Simülasyonu:
        1. 'meta_master_switcher' (🚀 Momentum / 🎯 Hunter / 🛡️ DD-Aware Rejim Seçici)
        2. 'meta_regime_spread' (Rejim & Momentum Spread Ağırlıklı Allocator)
        3. 'meta_vol_dd_gated' (Volatilite Paritesi + Drawdown Freni)
        4. 'meta_continuous_factor' (Sürekli Faktör Ağırlıklı Meta Allocator)
        5. 'saf_hunter' (Benchmark)
        6. 'saf_momentum_spread' (Benchmark)
        7. 'saf_dd_aware' (Benchmark)
        8. 'saf_nobetci' (Benchmark)
        9. 'sabit_25_75' (Benchmark)
        """
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
        t0_agirlik_toplami = 0.0
        
        gun_500k = None
        tarih_500k = None
        gun_700k = None
        tarih_700k = None
        
        hist_ret_mom = []
        hist_ret_h6 = []
        
        for idx, dt in enumerate(tarih_dilimi):
            rm = self.r_mom.get(dt, 0.0)
            rh = self.r_h6.get(dt, 0.0)
            rdd = self.r_dd.get(dt, 0.0)
            rsfb = self.r_sfb.get(dt, 0.0)
            rt0 = self.t0_ret_serisi.loc[dt]
            
            hist_ret_mom.append(rm)
            hist_ret_h6.append(rh)
            
            breadth = self.market_breadth.get(dt, 0.0)
            top5 = self.top5_avg_r20.get(dt, 0.0)
            
            # Momentum Spread
            f_sfb = self.sfb_aktif_fon.get(dt, "PPZ")
            f_h6 = self.h6_aktif_fon.get(dt, "PPZ")
            r20_s = self.r20_df.at[dt, f_sfb] if f_sfb in self.r20_df.columns and pd.notna(self.r20_df.at[dt, f_sfb]) else 0.0
            r20_h = self.r20_df.at[dt, f_h6] if f_h6 in self.r20_df.columns and pd.notna(self.r20_df.at[dt, f_h6]) else 0.0
            spread = r20_s - r20_h
            
            if sermaye > zirve:
                zirve = sermaye
            cur_dd = (zirve - sermaye) / (zirve + 1e-8)
            
            # =========================================================================
            # META ALLOCATOR AĞIRLIKLARI (w_mom, w_h6, w_dd, w_t0)
            # =========================================================================
            if meta_model_kodu == "meta_master_switcher":
                # 3-Kişilik Usta Seçici (Master Switcher):
                # 1. Ralli Rejimi: Piyasa genişliği > %45, Nöbetçi ivmesi güçlü ve DD < %3.0 -> %100 Momentum Spread
                # 2. Savunma / Kriz: Çekilme >= %4.0 veya Piyasa genişliği <= %25 -> %100 Drawdown-Aware Engine
                # 3. Normal / Dengeli: Diğer tüm durumlarda -> %100 Hunter v6
                if cur_dd >= 0.040 or breadth <= 0.25 or top5 <= 0.015:
                    w_mom, w_h6, w_dd, w_t0 = 0.0, 0.0, 1.0, 0.0
                    etiket = "DEFENSE (DD-Aware)"
                elif breadth >= 0.45 and spread >= 0.02 and cur_dd < 0.025:
                    w_mom, w_h6, w_dd, w_t0 = 1.0, 0.0, 0.0, 0.0
                    etiket = "RALLY (Momentum Spread)"
                else:
                    w_mom, w_h6, w_dd, w_t0 = 0.0, 1.0, 0.0, 0.0
                    etiket = "BALANCED (Hunter v6)"
                    
            elif meta_model_kodu == "meta_regime_spread":
                # Rejim & Spread Dinamik Allocator:
                if cur_dd >= 0.055:
                    w_mom, w_h6, w_dd, w_t0 = 0.0, 0.10, 0.90, 0.0
                    etiket = "HIGH_DD_DEFENSE"
                elif breadth >= 0.50 and spread >= 0.02:
                    w_mom, w_h6, w_dd, w_t0 = 0.70, 0.30, 0.0, 0.0
                    etiket = "BULL_MOMENTUM"
                elif breadth <= 0.30:
                    w_mom, w_h6, w_dd, w_t0 = 0.10, 0.40, 0.50, 0.0
                    etiket = "CAUTION_DEFENSE"
                else:
                    w_mom, w_h6, w_dd, w_t0 = 0.20, 0.60, 0.20, 0.0
                    etiket = "NEUTRAL_BALANCED"
                    
            elif meta_model_kodu == "meta_vol_dd_gated":
                # Volatilite Paritesi + Drawdown Freni:
                k20_m = hist_ret_mom[-20:]
                k20_h = hist_ret_h6[-20:]
                vol_m = max(0.003, np.std(k20_m, ddof=1) if len(k20_m) > 1 else 0.01)
                vol_h = max(0.003, np.std(k20_h, ddof=1) if len(k20_h) > 1 else 0.01)
                
                inv_m = 1.0 / vol_m
                inv_h = 1.0 / vol_h
                tot_inv = inv_m + inv_h
                base_w_mom = inv_m / tot_inv
                base_w_h6 = inv_h / tot_inv
                
                if cur_dd >= 0.050:
                    w_mom, w_h6, w_dd, w_t0 = 0.0, 0.20, 0.80, 0.0
                    etiket = "VOL_DD_PROTECT"
                elif cur_dd >= 0.030:
                    w_mom, w_h6, w_dd, w_t0 = base_w_mom * 0.5, base_w_h6 * 0.5, 0.50, 0.0
                    etiket = "VOL_DD_CAUTION"
                else:
                    w_mom, w_h6, w_dd, w_t0 = base_w_mom * 0.9, base_w_h6 * 0.9, 0.10, 0.0
                    etiket = "VOL_NORMAL"
                    
            elif meta_model_kodu == "meta_continuous_factor":
                # Sürekli Faktör Skoru ile Dinamik Dağılım
                # Momentum cazibesi: (spread + top5), Risk cazibesi: (1 - cur_dd / 0.065)
                score_mom = max(0.0, float(spread * 10.0 + top5 * 5.0))
                score_h6 = 1.0
                score_dd = max(0.0, float(cur_dd / 0.03 * 3.0 + (0.5 - breadth) * 4.0))
                
                exp_m = np.exp(min(4.0, score_mom))
                exp_h = np.exp(1.0)
                exp_d = np.exp(min(4.0, score_dd))
                tot_exp = exp_m + exp_h + exp_d
                
                w_mom = float(exp_m / tot_exp)
                w_h6 = float(exp_h / tot_exp)
                w_dd = float(exp_d / tot_exp)
                w_t0 = 0.0
                etiket = f"M:{int(w_mom*100)}|H:{int(w_h6*100)}|D:{int(w_dd*100)}"
                
            # Benchmark Modeller
            elif meta_model_kodu == "saf_hunter":
                w_mom, w_h6, w_dd, w_t0 = 0.0, 1.0, 0.0, 0.0
                etiket = "Saf Hunter v6"
            elif meta_model_kodu == "saf_momentum_spread":
                w_mom, w_h6, w_dd, w_t0 = 1.0, 0.0, 0.0, 0.0
                etiket = "Saf Momentum Spread"
            elif meta_model_kodu == "saf_dd_aware":
                w_mom, w_h6, w_dd, w_t0 = 0.0, 0.0, 1.0, 0.0
                etiket = "Saf DD-Aware"
            elif meta_model_kodu == "saf_nobetci":
                w_mom, w_h6, w_dd, w_t0 = 0.0, 0.0, 0.0, 0.0
                etiket = "Saf Fon Nöbetçisi"
            elif meta_model_kodu == "sabit_25_75":
                w_mom, w_h6, w_dd, w_t0 = 0.0, 0.75, 0.0, 0.0
                etiket = "Sabit %25 SFB + %75 H6"
            else:
                w_mom, w_h6, w_dd, w_t0 = 0.0, 1.0, 0.0, 0.0
                etiket = "Default"
                
            # Getiri Dağılımı
            if meta_model_kodu == "saf_nobetci":
                gunluk_ret = rsfb
            elif meta_model_kodu == "sabit_25_75":
                gunluk_ret = (0.25 * rsfb) + (0.75 * rh)
            else:
                gunluk_ret = (w_mom * rm) + (w_h6 * rh) + (w_dd * rdd) + (w_t0 * rt0)
                
            sermaye *= (1 + gunluk_ret)
            
            # Efektif T0 Süresi
            eff_t0 = w_t0 + (w_dd * 0.35) + (w_h6 * 0.31) + (w_mom * 0.12)
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
                "w_mom": w_mom,
                "w_h6": w_h6,
                "w_dd": w_dd,
                "etiket": etiket
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
        
        # En Uzun Drawdown Süresi (Max DD Duration)
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
            "meta_model_kodu": meta_model_kodu,
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
            "gun_500k": f"{gun_500k}. Gün ({tarih_500k})" if gun_500k else "Ulaşılmadı",
            "gun_700k": f"{gun_700k}. Gün ({tarih_700k})" if gun_700k else "Ulaşılmadı",
            "gunluk_kayitlar": gunluk_kayitlar
        }
