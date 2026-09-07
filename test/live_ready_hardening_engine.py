"""
live_ready_hardening_engine.py
==============================
HARMONY v2.2 LIVE-READY HARDENING MOTORU
- Gerçekçi TEFAS Valör ve Takas Zinciri (T+0 / T+1 / T+2 / T+3)
- 13:30 Cut-off ve Karar Gecikmesi Modellemesi
- 4 Seviyeli Live Risk Gate (NORMAL, CAUTION, DEFENSIVE, EMERGENCY)
- Nöbetçi Kalite Filtresi (Serbest Fon İvme ve Likidite Kontrolü)
- Sermaye Ölçekleme ve Dinamik Piyasa Etkisi Kayması (100K -> 5M TL)
"""

import os
import sys
import json
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Any, Optional

from harmony_v2_2_golden import HarmonyV22GoldenMotor

class LiveReadyHardeningEngine:
    def __init__(
        self,
        baslangic_sermayesi: float = 100_000.0,
        kayma_pct: float = 0.0005,
        satis_valoru_gun_sfb: int = 2,     # Serbest fonlar için gerçekçi satış valörü (T+2)
        satis_valoru_gun_hisse: int = 1,   # Hisse/Sektör fonları için satış valörü (T+1)
        alis_valoru_gun: int = 1,          # Alış valörü (T+1)
        enable_risk_gate: bool = True,     # Live Risk Gate aktif
        enable_quality_filter: bool = True # Nöbetçi Kalite Filtresi aktif
    ):
        self.baslangic_sermayesi = baslangic_sermayesi
        self.kayma_pct = kayma_pct
        self.satis_valoru_gun_sfb = satis_valoru_gun_sfb
        self.satis_valoru_gun_hisse = satis_valoru_gun_hisse
        self.alis_valoru_gun = alis_valoru_gun
        self.enable_risk_gate = enable_risk_gate
        self.enable_quality_filter = enable_quality_filter
        
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
        self.r40_df = self.golden.base_motor.base_motor.r40_df
        self.sfb_aktif_fon = self.golden.sfb_aktif_fon
        self.h6_aktif_fon = self.golden.h6_aktif_fon

    def simule_et_live_hardened(
        self,
        sinyal_gecikmesi_gun: int = 0,      # 0: 13:30 öncesi, 1: 13:30 sonrası / 1 gün gecikme
        ekstra_satis_valoru_gun: int = 0,   # Ekstra takas süresi (Ör: T+3)
        ozel_kayma_pct: Optional[float] = None,
        sermaye_tl: Optional[float] = None,
        veri_kaybi_olasiligi_pct: float = 0.0, # Rastgele veri kesintisi simülasyonu (%)
        kotu_gun_stresi: bool = False,      # Black swan kötü gün stres testi
        baslangic_tarihi: Optional[str] = None,
        bitis_tarihi: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Canlı Para Koşullarında Gerçekçi İcra Simülatörü.
        """
        sermaye = sermaye_tl if sermaye_tl is not None else self.baslangic_sermayesi
        base_kayma = ozel_kayma_pct if ozel_kayma_pct is not None else self.kayma_pct
        
        # Sermaye büyüklüğüne göre dinamik piyasa etkisi kayması (100K -> 5M TL)
        efektif_kayma = base_kayma * (1.0 + (sermaye / 5_000_000.0) * 0.5)
        
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
        
        zirve = sermaye
        gunluk_kayitlar = []
        
        aktif_motor = "HUNTER"
        motor_elde_gun = 0
        savunma_modu = False
        
        # Gerçekçi Takas Yönetimi
        takas_kalan_gun = 0
        takas_bekleyen_nakit = 0.0
        
        # Live Risk Gate Durumu
        risk_gate_state = "NORMAL" # 'NORMAL', 'CAUTION', 'DEFENSIVE', 'EMERGENCY'
        gate_counts = {"NORMAL": 0, "CAUTION": 0, "DEFENSIVE": 0, "EMERGENCY": 0}
        
        toplam_motor_gecisi = 0
        t0_agirlik_toplami = 0.0
        
        gun_500k = None
        tarih_500k = None
        gun_700k = None
        tarih_700k = None
        
        np.random.seed(42)
        
        for idx, dt in enumerate(tarih_dilimi):
            # 1. Sinyal Gecikmesi Simülasyonu
            dt_sig_idx = max(0, idx - sinyal_gecikmesi_gun)
            dt_signal = tarih_dilimi[dt_sig_idx]
            
            rm = self.r_mom.get(dt, 0.0)
            rh = self.r_h6.get(dt, 0.0)
            rdd = self.r_dd.get(dt, 0.0)
            rsfb = self.r_sfb.get(dt, 0.0)
            rt0 = self.t0_ret_serisi.loc[dt]
            
            breadth = self.market_breadth.get(dt_signal, 0.0)
            top5 = self.top5_avg_r20.get(dt_signal, 0.0)
            
            f_sfb = self.sfb_aktif_fon.get(dt_signal, "PPZ")
            f_h6 = self.h6_aktif_fon.get(dt_signal, "PPZ")
            r20_s = self.r20_df.at[dt_signal, f_sfb] if f_sfb in self.r20_df.columns and pd.notna(self.r20_df.at[dt_signal, f_sfb]) else 0.0
            r40_s = self.r40_df.at[dt_signal, f_sfb] if f_sfb in self.r40_df.columns and pd.notna(self.r40_df.at[dt_signal, f_sfb]) else 0.0
            r20_h = self.r20_df.at[dt_signal, f_h6] if f_h6 in self.r20_df.columns and pd.notna(self.r20_df.at[dt_signal, f_h6]) else 0.0
            spread = r20_s - r20_h
            
            # Kötü gün stresi: yanlış fon seçimi ve seans şoku
            if kotu_gun_stresi and breadth <= 0.30:
                rh -= 0.008
                rm -= 0.012
                rsfb -= 0.015
                
            if sermaye > zirve:
                zirve = sermaye
            cur_dd = (zirve - sermaye) / (zirve + 1e-8)
            
            # =========================================================================
            # LIVE RISK GATE: 4 SEVİYELİ OPERASYONEL ZIRH
            # =========================================================================
            # Veri kaybı / Sistem kesintisi kontrolü
            veri_kesintisi = (np.random.rand() < (veri_kaybi_olasiligi_pct / 100.0))
            
            if veri_kesintisi:
                risk_gate_state = "EMERGENCY"
            elif cur_dd >= 0.040 or breadth <= 0.25 or top5 <= 0.015:
                risk_gate_state = "DEFENSIVE"
            elif breadth <= 0.38 or cur_dd >= 0.028 or top5 <= 0.030:
                risk_gate_state = "CAUTION"
            else:
                risk_gate_state = "NORMAL"
                
            gate_counts[risk_gate_state] += 1
            
            # =========================================================================
            # NÖBETÇİ KALİTE FİLTRESİ
            # =========================================================================
            if self.enable_quality_filter:
                # Nöbetçi'ye geçiş için: Pozitif spread + R20 >= %5 + İvme pozitif (R20 >= R40)
                nobetci_onay = (spread >= 0.020 and r20_s >= 0.05 and r20_s >= r40_s and breadth >= 0.45)
            else:
                nobetci_onay = (spread >= 0.020 and breadth >= 0.45)
                
            # Hedef Motor Seçimi
            if risk_gate_state in ["DEFENSIVE", "EMERGENCY"]:
                savunma_modu = True
                hedef_motor = "DD_AWARE"
            elif cur_dd <= 0.028 and (breadth >= 0.35 or top5 >= 0.03):
                savunma_modu = False
                if nobetci_onay and cur_dd < 0.028:
                    hedef_motor = "MOMENTUM"
                else:
                    hedef_motor = "HUNTER"
            else:
                if savunma_modu:
                    hedef_motor = "DD_AWARE"
                elif nobetci_onay and cur_dd < 0.028:
                    hedef_motor = "MOMENTUM"
                else:
                    hedef_motor = "HUNTER"
                    
            # =========================================================================
            # GERÇEKÇİ TEFAS VALÖR & TAKAS YÖNETİMİ
            # =========================================================================
            asgari_sure = 5 if aktif_motor == "DD_AWARE" else 3
            if hedef_motor != aktif_motor and takas_kalan_gun == 0:
                acil_fren = (hedef_motor == "DD_AWARE" and cur_dd >= 0.045)
                hizli_cikis = (aktif_motor == "DD_AWARE" and breadth >= 0.48 and spread >= 0.025)
                
                if motor_elde_gun >= asgari_sure or acil_fren or hizli_cikis or risk_gate_state == "EMERGENCY":
                    # Motor Değişimi Başlat: Satış Valörü ve Kayma Uygula
                    sermaye *= (1.0 - efektif_kayma)
                    
                    # Satılan fona göre takas süresi belirle
                    if aktif_motor in ["MOMENTUM", "NOBETCI"]:
                        val_satis = self.satis_valoru_gun_sfb + ekstra_satis_valoru_gun
                    else:
                        val_satis = self.satis_valoru_gun_hisse + ekstra_satis_valoru_gun
                        
                    takas_kalan_gun = val_satis
                    takas_bekleyen_nakit = sermaye
                    
                    aktif_motor = hedef_motor
                    motor_elde_gun = 1
                    toplam_motor_gecisi += 1
                else:
                    motor_elde_gun += 1
            else:
                motor_elde_gun += 1
                
            # =========================================================================
            # GÜNLÜK GETİRİ VE VALÖR NEMA İCRASI
            # =========================================================================
            if takas_kalan_gun > 0:
                # Para takasta: T0 Para Piyasası neması kazanır
                sermaye *= (1 + rt0)
                takas_kalan_gun -= 1
                eff_t0 = 1.0
            else:
                # Normal pozisyon getirisi
                if risk_gate_state == "EMERGENCY":
                    gunluk_ret = rt0
                    eff_t0 = 1.0
                elif risk_gate_state == "CAUTION" and self.enable_risk_gate:
                    # Caution durumunda %70 aktif motor + %30 T0 Core
                    if aktif_motor == "HUNTER":
                        gunluk_ret = (0.70 * rh) + (0.30 * rt0)
                    elif aktif_motor == "MOMENTUM":
                        gunluk_ret = (0.70 * rm) + (0.30 * rt0)
                    else:
                        gunluk_ret = (0.70 * rdd) + (0.30 * rt0)
                    eff_t0 = 0.30 + 0.25
                else:
                    # Normal / Defensive
                    if aktif_motor == "HUNTER":
                        gunluk_ret = rh
                        eff_t0 = 0.31
                    elif aktif_motor == "MOMENTUM":
                        gunluk_ret = rm
                        eff_t0 = 0.12
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
                "gate_state": risk_gate_state,
                "cur_dd": cur_dd
            })
            
        vals = np.array([k["bakiye"] for k in gunluk_kayitlar])
        n_days = len(vals)
        toplam_ret = (vals[-1] - (sermaye_tl if sermaye_tl is not None else self.baslangic_sermayesi)) / (sermaye_tl if sermaye_tl is not None else self.baslangic_sermayesi) * 100.0
        cagr = ((vals[-1] / (sermaye_tl if sermaye_tl is not None else self.baslangic_sermayesi)) ** (252 / n_days) - 1) * 100.0 if n_days > 0 else 0.0
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
            "gate_counts": gate_counts,
            "gun_500k": f"{gun_500k}. Gün ({tarih_500k})" if gun_500k else "Ulaşılmadı",
            "gun_700k": f"{gun_700k}. Gün ({tarih_700k})" if gun_700k else "Ulaşılmadı",
            "gunluk_kayitlar": gunluk_kayitlar
        }
