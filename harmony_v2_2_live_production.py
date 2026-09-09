"""
harmony_v2_2_live_production.py
===============================
HARMONY MODEL E (VOLATILITY RISK-PARITY) LIVE-PRODUCTION MOTORU
- 60 Günlük Rolling Peak Adaptive Re-Entry
- %20 Hedef Volatilite Dinamik Pozisyon Büyüklüğü (w in [0.40, 1.00])
- Katı T-1 Zamanlama Güvencesi (Sıfır Gelecek Bilgisi Sızıntısı)
- Gerçek TEFAS Valör ve Takas Zinciri (Hisse T+1, SFB T+2)
- T0 PPZ Likit Fon Nemalandırması
"""

import os
import sys
import json
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Any, Optional

from harmony_v2_2_golden import HarmonyV22GoldenMotor

class HarmonyV22LiveProduction:
    def __init__(
        self,
        baslangic_sermayesi: float = 100_000.0,
        kayma_pct: float = 0.0005,
        target_vol: float = 0.20,
        vol_window: int = 20,
        rolling_peak_window: int = 60,
        min_w: float = 0.40,
        max_w: float = 1.00
    ):
        self.baslangic_sermayesi = baslangic_sermayesi
        self.kayma_pct = kayma_pct
        self.target_vol = target_vol
        self.vol_window = vol_window
        self.rolling_peak_window = rolling_peak_window
        self.min_w = min_w
        self.max_w = max_w
        
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
        
        self.fiyat_df = self.golden.base_motor.base_motor.fiyat_df
        self.skor_df = self.golden.base_motor.base_motor.skor_df
        self.fon_gunluk_ret = self.fiyat_df.pct_change().fillna(0.0)
        self.vol_matrix = self.fon_gunluk_ret.rolling(self.vol_window).std() * np.sqrt(252)

    def simule_et_production(
        self,
        sermaye_tl: Optional[float] = None,
        ozel_kayma_pct: Optional[float] = None,
        baslangic_tarihi: Optional[str] = None,
        bitis_tarihi: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Model E Live-Production Simülatörü.
        60-günlük Rolling Peak + %20 Hedef Volatilite Sizing.
        """
        sermaye = sermaye_tl if sermaye_tl is not None else self.baslangic_sermayesi
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
        
        rolling_window = []
        gunluk_kayitlar = []
        gecisler = []
        
        aktif_motor = "HUNTER"
        motor_elde_gun = 0
        savunma_modu = False
        takas_kalan_gun = 0
        
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
            
            # 60 Günlük Rolling Peak
            rolling_window.append(sermaye)
            if len(rolling_window) > self.rolling_peak_window:
                rolling_window.pop(0)
            local_peak = max(rolling_window)
            local_dd = (local_peak - sermaye) / (local_peak + 1e-8)
            
            # Savunma Tetikleyicileri
            if local_dd >= 0.040 or breadth <= 0.25 or top5 <= 0.015:
                savunma_modu = True
            elif local_dd <= 0.025 and (breadth >= 0.40 or top5 >= 0.03):
                savunma_modu = False
                
            nobetci_onay = (spread >= 0.020 and r20_s >= 0.03 and breadth >= 0.45)
            if savunma_modu:
                hedef_motor = "DD_AWARE"
            elif nobetci_onay:
                hedef_motor = "MOMENTUM"
            else:
                hedef_motor = "HUNTER"
                
            asgari_sure = 5 if aktif_motor == "DD_AWARE" else 3
            acil_fren = (hedef_motor == "DD_AWARE" and local_dd >= 0.045)
            hizli_cikis = (aktif_motor == "DD_AWARE" and breadth >= 0.48 and spread >= 0.025)
            
            t_eksi_1_str = tarih_dilimi[idx-1].strftime("%Y-%m-%d") if idx > 0 else dt.strftime("%Y-%m-%d")
            
            # Geçiş İcrası
            if hedef_motor != aktif_motor and takas_kalan_gun == 0:
                if motor_elde_gun >= asgari_sure or acil_fren or hizli_cikis:
                    sermaye *= (1.0 - kayma)
                    val_satis = 2 if aktif_motor == "MOMENTUM" else 1
                    takas_kalan_gun = val_satis
                    
                    gecisler.append({
                        "tarih": dt.strftime("%Y-%m-%d"),
                        "t_eksi_1": t_eksi_1_str,
                        "eski": aktif_motor,
                        "yeni": hedef_motor,
                        "bakiye": round(sermaye, 2),
                        "yil": dt.year
                    })
                    
                    aktif_motor = hedef_motor
                    motor_elde_gun = 1
                else:
                    motor_elde_gun += 1
            else:
                motor_elde_gun += 1
                
            # Dinamik Volatilite Sizing
            aktif_fon = f_sfb if aktif_motor == "MOMENTUM" else (f_h6 if aktif_motor == "HUNTER" else "PPZ")
            t_prev = tarih_dilimi[idx-1] if idx > 0 else dt
            
            if t_prev in self.vol_matrix.index and aktif_fon in self.vol_matrix.columns and pd.notna(self.vol_matrix.at[t_prev, aktif_fon]):
                vol_val = self.vol_matrix.at[t_prev, aktif_fon]
            else:
                vol_val = self.target_vol
                
            raw_w = self.target_vol / (vol_val + 1e-6)
            w = float(np.clip(raw_w, self.min_w, self.max_w))
            
            if takas_kalan_gun > 0:
                sermaye *= (1 + rt0)
                takas_kalan_gun -= 1
                g_ret = rt0
            else:
                if aktif_motor == "HUNTER":
                    g_ret = (w * rh) + ((1.0 - w) * rt0)
                elif aktif_motor == "MOMENTUM":
                    g_ret = (w * rm) + ((1.0 - w) * rt0)
                else:
                    g_ret = rdd
                sermaye *= (1 + g_ret)
                
            gunluk_kayitlar.append({
                "tarih": dt.strftime("%Y-%m-%d"),
                "dt": dt,
                "bakiye": sermaye,
                "aktif_motor": aktif_motor,
                "aktif_fon": aktif_fon,
                "vol_val": vol_val,
                "w": w if aktif_motor != "DD_AWARE" else 0.0,
                "gunluk_ret": g_ret,
                "local_dd": local_dd,
                "yil": dt.year
            })
            
        df = pd.DataFrame(gunluk_kayitlar).set_index("dt")
        n_days = len(df)
        cagr = ((sermaye / self.baslangic_sermayesi) ** (252.0 / n_days) - 1.0) * 100.0 if n_days > 0 else 0.0
        
        df["peak"] = df["bakiye"].cummax()
        df["dd"] = (df["bakiye"] - df["peak"]) / df["peak"]
        mdd = df["dd"].min() * 100.0
        
        daily_rets = df["gunluk_ret"]
        
        # Dinamik Risksiz Faiz (Rf) Düşülmüş Kurumsal Metrikler
        try:
            from makro_veri_motoru import hesapla_kurumsal_metrikler
            k_metrikler = hesapla_kurumsal_metrikler(daily_rets)
            sharpe = k_metrikler.get("kurumsal_sharpe", 0.0)
            sortino = k_metrikler.get("kurumsal_sortino", 0.0)
            net_alfa = k_metrikler.get("net_alfa_pct", 0.0)
        except Exception:
            # Fallback naive hesaplama
            sharpe = float((daily_rets.mean() / (daily_rets.std() + 1e-9)) * np.sqrt(252))
            neg_rets = daily_rets[daily_rets < 0]
            sortino = float((daily_rets.mean() / (neg_rets.std() + 1e-9)) * np.sqrt(252)) if len(neg_rets) > 0 else 0.0
            net_alfa = 0.0
            
        calmar = (cagr / abs(mdd)) if abs(mdd) > 0 else 0.0
        
        # Overfitting / In-sample bias denetim uyarısı
        if sharpe > 3.0 or calmar > 10.0:
            print(f"[UYARI - OVERFITTING ALARMI] Metrikler piyasa normlarının üzerinde (Kurumsal Sharpe: {sharpe}, Calmar: {round(calmar, 2)}). In-sample yanlılık veya aşırı uyum kontrolü yapılmalıdır.")
        
        yillik_ret = {}
        for y, grp in df.groupby("yil"):
            b_val = grp["bakiye"].iloc[0]
            e_val = grp["bakiye"].iloc[-1]
            yillik_ret[y] = round((e_val - b_val) / b_val * 100.0, 2)
            
        return {
            "model_kodu": "HARMONY_MODEL_E_VOL_RISK_PARITY",
            "son_bakiye_tl": round(sermaye, 2),
            "cagr_pct": round(cagr, 2),
            "max_drawdown_pct": round(mdd, 2),
            "sharpe_orani": round(sharpe, 2),
            "sortino_orani": round(sortino, 2),
            "calmar_orani": round(calmar, 2),
            "net_alfa_pct": round(net_alfa, 2),
            "gecis_sayisi": len(gecisler),
            "yillik_getiriler": yillik_ret,
            "gunluk_kayitlar": gunluk_kayitlar,
            "df": df
        }

    def get_current_live_decision(self) -> Dict[str, Any]:
        """
        En son güncel TEFAS verisi üzerinden canlı sinyal ve pozisyon ağırlığı üretir.
        """
        last_dt = self.tarihler[-1]
        
        breadth = self.market_breadth.get(last_dt, 0.0)
        top5 = self.top5_avg_r20.get(last_dt, 0.0)
        
        f_sfb = self.sfb_aktif_fon.get(last_dt, "PPZ")
        f_h6 = self.h6_aktif_fon.get(last_dt, "PPZ")
        r20_s = self.r20_df.at[last_dt, f_sfb] if f_sfb in self.r20_df.columns and pd.notna(self.r20_df.at[last_dt, f_sfb]) else 0.0
        r20_h = self.r20_df.at[last_dt, f_h6] if f_h6 in self.r20_df.columns and pd.notna(self.r20_df.at[last_dt, f_h6]) else 0.0
        spread = r20_s - r20_h
        
        nobetci_onay = (spread >= 0.020 and r20_s >= 0.03 and breadth >= 0.45)
        
        if breadth <= 0.25 or top5 <= 0.015:
            rejim = "DD_AWARE"
            aktif_fon = "PPZ"
            rejim_aciklama = "🔴 Savunma Modu (T0 Likit Nakit Kalkanı)"
        elif nobetci_onay:
            rejim = "MOMENTUM"
            aktif_fon = f_sfb
            rejim_aciklama = "🟡 Nöbetçi / Momentum Serbest Fon Modu"
        else:
            rejim = "HUNTER"
            aktif_fon = f_h6
            rejim_aciklama = "🟢 Hunter Güçlü Boğa / Lider Fon Modu"
            
        # Volatilite ve Sizing Ağırlığı
        if last_dt in self.vol_matrix.index and aktif_fon in self.vol_matrix.columns and pd.notna(self.vol_matrix.at[last_dt, aktif_fon]):
            vol_val = self.vol_matrix.at[last_dt, aktif_fon]
        else:
            vol_val = self.target_vol
            
        raw_w = self.target_vol / (vol_val + 1e-6)
        w = float(np.clip(raw_w, self.min_w, self.max_w)) if rejim != "DD_AWARE" else 0.0
        
        skor_df = self.golden.base_motor.base_motor.skor_df.loc[last_dt].dropna().sort_values(ascending=False)
        
        top10 = []
        for fon, skor in skor_df.head(10).items():
            r20 = self.r20_df.at[last_dt, fon] * 100 if fon in self.r20_df.columns and pd.notna(self.r20_df.at[last_dt, fon]) else 0.0
            vol_f = self.vol_matrix.at[last_dt, fon] * 100 if fon in self.vol_matrix.columns and pd.notna(self.vol_matrix.at[last_dt, fon]) else 20.0
            rec_w = float(np.clip(20.0 / (vol_f + 1e-4), 0.40, 1.00)) * 100.0
            top10.append({
                "fon": fon,
                "skor": skor,
                "r20": r20,
                "vol_pct": vol_f,
                "rec_w": rec_w
            })
            
        return {
            "tarih": last_dt.strftime("%Y-%m-%d"),
            "rejim": rejim,
            "rejim_aciklama": rejim_aciklama,
            "aktif_fon": aktif_fon,
            "breadth": breadth * 100.0,
            "vol_val": vol_val * 100.0,
            "w_pct": w * 100.0,
            "ppz_pct": (1.0 - w) * 100.0 if rejim != "DD_AWARE" else 100.0,
            "top10": top10
        }
