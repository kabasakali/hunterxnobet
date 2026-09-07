import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

"""
v3_continuous_allocator.py
==========================
HARMONY v3: Continuous Allocation, Top-Level Risk Budgeting,
Hysteresis Transition Control and Volatility Scaling Motor.
"""

import os
import sys
import json
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Any, Optional

from meta_allocator_motor import MetaAllocatorMotor

class HarmonyV3ContinuousAllocator:
    def __init__(
        self,
        baslangic_sermayesi: float = 100_000.0,
        kayma_pct: float = 0.0005,
        ema_alpha: float = 0.30,          # Yumuşak geçiş katsayısı (Hysteresis)
        rebalance_esigi: float = 0.05     # Churn engelleyici asgari ağırlık değişim eşiği
    ):
        self.baslangic_sermayesi = baslangic_sermayesi
        self.kayma_pct = kayma_pct
        self.ema_alpha = ema_alpha
        self.rebalance_esigi = rebalance_esigi
        
        self.meta_base = MetaAllocatorMotor(baslangic_sermayesi=baslangic_sermayesi, kayma_pct=kayma_pct)
        self.tarihler = self.meta_base.tarihler
        self.t0_ret_serisi = self.meta_base.t0_ret_serisi
        
        self.r_mom = self.meta_base.r_mom
        self.r_h6 = self.meta_base.r_h6
        self.r_dd = self.meta_base.r_dd
        self.r_sfb = self.meta_base.r_sfb
        
        self.market_breadth = self.meta_base.market_breadth
        self.top5_avg_r20 = self.meta_base.top5_avg_r20
        self.r20_df = self.meta_base.r20_df
        self.sfb_aktif_fon = self.meta_base.sfb_aktif_fon
        self.h6_aktif_fon = self.meta_base.h6_aktif_fon

    def simule_et_v3(
        self,
        v3_varyant: str = "v3_full", # 'v3_full', 'v3_no_ema', 'v3_pure_continuous'
        baslangic_tarihi: Optional[str] = None,
        bitis_tarihi: Optional[str] = None,
        ozel_kayma_pct: Optional[float] = None,
        sinyal_gecikmesi_gun: int = 0
    ) -> Dict[str, Any]:
        """
        V3 Sürekli Ağırlıklandırma Simülatörü.
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
        
        # Önceki günün efektif ağırlıkları (EMA yumuşatma için)
        prev_w_mom = 0.0
        prev_w_h6 = 1.0
        prev_w_dd = 0.0
        prev_w_t0 = 0.0
        
        toplam_turnover = 0.0
        motor_degisim_sayisi = 0
        t0_agirlik_toplami = 0.0
        
        gun_500k = None
        tarih_500k = None
        gun_700k = None
        tarih_700k = None
        
        for idx, dt in enumerate(tarih_dilimi):
            # Sinyal gecikmesi simülasyonu
            dt_signal_idx = max(0, idx - sinyal_gecikmesi_gun)
            dt_signal = tarih_dilimi[dt_signal_idx]
            
            rm = self.r_mom.get(dt, 0.0)
            rh = self.r_h6.get(dt, 0.0)
            rdd = self.r_dd.get(dt, 0.0)
            rt0 = self.t0_ret_serisi.loc[dt]
            
            breadth = self.market_breadth.get(dt_signal, 0.0)
            top5 = self.top5_avg_r20.get(dt_signal, 0.0)
            
            f_sfb = self.sfb_aktif_fon.get(dt_signal, "PPZ")
            f_h6 = self.h6_aktif_fon.get(dt_signal, "PPZ")
            r20_s = self.r20_df.at[dt_signal, f_sfb] if f_sfb in self.r20_df.columns and pd.notna(self.r20_df.at[dt_signal, f_sfb]) else 0.0
            r20_h = self.r20_df.at[dt_signal, f_h6] if f_h6 in self.r20_df.columns and pd.notna(self.r20_df.at[dt_signal, f_h6]) else 0.0
            spread = r20_s - r20_h
            
            if sermaye > zirve:
                zirve = sermaye
            cur_dd = (zirve - sermaye) / (zirve + 1e-8)
            
            # =========================================================================
            # V3-B: ÜST SEVİYE RİSK BÜTÇESİ (T0 CORE HESABI)
            # =========================================================================
            # Çekilme arttıkça veya piyasa derinliği çöktükçe T0 Kasa payı sürekli fonksiyonla artar
            if cur_dd >= 0.060:
                raw_w_t0 = 0.85
            elif cur_dd >= 0.040:
                raw_w_t0 = 0.40 + (cur_dd - 0.040) / 0.020 * 0.45
            elif cur_dd >= 0.020:
                raw_w_t0 = 0.10 + (cur_dd - 0.020) / 0.020 * 0.30
            else:
                raw_w_t0 = 0.05
                
            if breadth <= 0.20 or top5 <= 0.01:
                raw_w_t0 = max(raw_w_t0, 0.70)
            elif breadth <= 0.30:
                raw_w_t0 = max(raw_w_t0, 0.35)
                
            # Kalan Aktif Sermaye Bütçesi
            aktif_butce = 1.0 - raw_w_t0
            
            # =========================================================================
            # V3-A: AKTİF MOTORLAR ARASINDA SÜREKLİ DAĞILIM (MOM / H6 / DD)
            # =========================================================================
            # Faktör çekicilik puanları
            score_mom = max(0.0, float((spread * 15.0) + (top5 * 8.0) + ((breadth - 0.35) * 5.0)))
            score_h6 = 1.5  # Temel güçlü dayanak
            score_dd = max(0.0, float((cur_dd / 0.03 * 4.0) + (max(0.0, 0.40 - breadth) * 6.0)))
            
            # Softmax Ağırlıklandırma
            exp_m = np.exp(min(5.0, score_mom))
            exp_h = np.exp(score_h6)
            exp_d = np.exp(min(5.0, score_dd))
            tot_exp = exp_m + exp_h + exp_d
            
            p_mom = exp_m / tot_exp
            p_h6 = exp_h / tot_exp
            p_dd = exp_d / tot_exp
            
            target_w_mom = float(p_mom * aktif_butce)
            target_w_h6 = float(p_h6 * aktif_butce)
            target_w_dd = float(p_dd * aktif_butce)
            target_w_t0 = float(raw_w_t0)
            
            # =========================================================================
            # V3-C: HYSTERESIS VE EMA YUMUŞATMA (TRANSITION CONTROL)
            # =========================================================================
            if v3_varyant == "v3_full":
                # EMA yumuşatma
                alpha = self.ema_alpha
                w_mom = float(alpha * target_w_mom + (1 - alpha) * prev_w_mom)
                w_h6 = float(alpha * target_w_h6 + (1 - alpha) * prev_w_h6)
                w_dd = float(alpha * target_w_dd + (1 - alpha) * prev_w_dd)
                w_t0 = float(alpha * target_w_t0 + (1 - alpha) * prev_w_t0)
                
                # Normalize et
                tot_w = w_mom + w_h6 + w_dd + w_t0
                w_mom /= tot_exp if tot_w == 0 else tot_w
                w_h6 /= tot_exp if tot_w == 0 else tot_w
                w_dd /= tot_exp if tot_w == 0 else tot_w
                w_t0 /= tot_exp if tot_w == 0 else tot_w
            else:
                w_mom, w_h6, w_dd, w_t0 = target_w_mom, target_w_h6, target_w_dd, target_w_t0
                
            # Turnover ve Rebalance Maliyeti Hesabı
            delta_w = (abs(w_mom - prev_w_mom) + abs(w_h6 - prev_w_h6) + 
                       abs(w_dd - prev_w_dd) + abs(w_t0 - prev_w_t0)) / 2.0
            
            if delta_w >= self.rebalance_esigi and idx > 0:
                sermaye *= (1.0 - (delta_w * kayma))
                toplam_turnover += delta_w
                motor_degisim_sayisi += 1
                
            prev_w_mom, prev_w_h6, prev_w_dd, prev_w_t0 = w_mom, w_h6, w_dd, w_t0
            
            # Günlük Getiri
            gunluk_ret = (w_mom * rm) + (w_h6 * rh) + (w_dd * rdd) + (w_t0 * rt0)
            sermaye *= (1 + gunluk_ret)
            
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
                "w_t0": w_t0
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
            "model_kodu": f"HARMONY_v3_{v3_varyant}",
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
            "turnover_toplam": round(toplam_turnover, 2),
            "rebalance_sayisi": motor_degisim_sayisi,
            "gun_500k": f"{gun_500k}. Gün ({tarih_500k})" if gun_500k else "Ulaşılmadı",
            "gun_700k": f"{gun_700k}. Gün ({tarih_700k})" if gun_700k else "Ulaşılmadı",
            "gunluk_kayitlar": gunluk_kayitlar
        }
