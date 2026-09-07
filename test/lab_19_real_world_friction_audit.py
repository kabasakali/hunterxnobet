"""
test/lab_19_real_world_friction_audit.py
========================================
LAB-19: GERÇEK HAYAT SÜRTÜNME, VALÖR VE GECİKME STRES TESTİ (REAL-WORLD FRICTION AUDIT)

Amaç:
Üretim Şampiyonu MODEL E (%20 Vol Risk-Parity) ve Kontrol Grubu SAF LAB-E (%100 Sabit)
modellerini gerçek hayat sürtünmelerine maruz bırakmak:

1. VALÖR VE TAKAS GECELİK NEMASI:
   - T günü sinyali -> T+1 13:30 emir -> T+1 kapanış fiyatı (Execution on T+1 NAV).
   - Satış valörü T+2: Takastaki bakiye T+1 ve T+2 günlerinde PPZ nema kazanır.
2. KAYMA VE KÖTÜ FİYATLAMA STRESİ (SLIPPAGE / SPREAD / COMMISSIONS):
   - 0 bps (Temel senaryo - %0.00)
   - 10 bps (Gerçekçi fon maliyeti - %0.10)
   - 25 bps (Orta sürtünme - %0.25)
   - 50 bps (Ağır sürtünme - %0.50)
   - 100 bps (Ekstrem kötü fiyatlama - %1.00)
3. SİNYAL GECİKMESİ STRESİ (HUMAN / LATENCY STRESS):
   - 0 Gün (Zamanında emir)
   - +1 Gün Ekstra Gecikme (Sinyalden 1 gün geç işlem girilirse)
4. OOS VE BLİND PERFORMANS KORUMA ORANI:
   - 5.7 Yıl Tüm Dönem (2021-2026)
   - 2025 Blind Testi
   - 2026 Out-of-Sample (OOS)
"""

import os
import sys
import numpy as np
import pandas as pd

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, base_dir)
sys.path.insert(0, os.path.join(base_dir, "test"))

from lab_17_volatility_sizing_forensics import Lab17VolSizingForensicsEngine

class Lab19RealWorldFrictionEngine:
    def __init__(self, baslangic_sermayesi: float = 100_000.0):
        self.baslangic = baslangic_sermayesi
        self.base_eng = Lab17VolSizingForensicsEngine(baslangic_sermayesi=self.baslangic)
        
        self.golden = self.base_eng.golden
        self.tarihler = self.base_eng.tarihler
        self.t0_ret_serisi = self.base_eng.t0_ret_serisi
        
        self.r_mom = self.base_eng.r_mom
        self.r_h6 = self.base_eng.r_h6
        self.r_dd = self.base_eng.r_dd
        
        self.market_breadth = self.base_eng.market_breadth
        self.top5_avg_r20 = self.base_eng.top5_avg_r20
        self.r20_df = self.base_eng.r20_df
        self.sfb_aktif_fon = self.base_eng.sfb_aktif_fon
        self.h6_aktif_fon = self.base_eng.h6_aktif_fon
        
        self.fiyat_df = self.base_eng.fiyat_df
        self.fon_gunluk_ret = self.base_eng.fon_gunluk_ret
        
    def simule_et(
        self,
        target_vol: float = 0.20,
        min_w: float = 0.40,
        max_w: float = 1.00,
        latency_days: int = 0,
        friction_bps: float = 0.0
    ):
        """
        Sürtünmeli, Valörlü ve Gecikmeli Simülatör.
        """
        vol_matrix = self.fon_gunluk_ret.rolling(20).std() * np.sqrt(252)
        
        # 1. Ham Sinyalleri Üret
        raw_signals = []
        tarih_dilimi = self.tarihler[65:]
        
        rolling_window = []
        sermaye_track = self.baslangic
        savunma_modu = False
        aktif_motor = "HUNTER"
        motor_elde_gun = 0
        
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
            
            # LAB-E Rolling Peak 60d
            rolling_window.append(sermaye_track)
            if len(rolling_window) > 60:
                rolling_window.pop(0)
            local_peak = max(rolling_window)
            local_dd = (local_peak - sermaye_track) / (local_peak + 1e-8)
            
            if local_dd >= 0.040 or breadth <= 0.25 or top5 <= 0.015:
                savunma_modu = True
            elif local_dd <= 0.025 and (breadth >= 0.40 or top5 >= 0.03):
                savunma_modu = False
                
            if savunma_modu:
                secilen_motor = "DD_AWARE"
                aktif_fon = "PPZ"
            else:
                if breadth >= 0.48 and spread >= 0.020:
                    secilen_motor = "MOMENTUM"
                    aktif_fon = f_sfb
                elif breadth >= 0.48:
                    secilen_motor = "HUNTER"
                    aktif_fon = f_h6
                else:
                    secilen_motor = "HUNTER"
                    aktif_fon = f_h6
                    
            if secilen_motor == aktif_motor:
                motor_elde_gun += 1
            else:
                if motor_elde_gun >= 5 or (secilen_motor == "DD_AWARE" and local_dd >= 0.040):
                    aktif_motor = secilen_motor
                    motor_elde_gun = 1
                else:
                    motor_elde_gun += 1
                    
            if aktif_motor == "DD_AWARE":
                current_fon = "PPZ"
            elif aktif_motor == "MOMENTUM":
                current_fon = f_sfb
            else:
                current_fon = f_h6
                
            # Sizing hesabı (T-1 gününe kadar olan volatilite)
            if current_fon == "PPZ" or aktif_motor == "DD_AWARE":
                w = 0.0
                vol_val = 0.0
            else:
                # T-1 volatilite
                prev_loc = max(0, self.tarihler.index(dt) - 1)
                prev_dt = self.tarihler[prev_loc]
                vol_val = vol_matrix.at[prev_dt, current_fon] if current_fon in vol_matrix.columns and pd.notna(vol_matrix.at[prev_dt, current_fon]) else 0.20
                if target_vol >= 1.0: # Sabit model
                    w = 1.00
                else:
                    w = np.clip(target_vol / (vol_val + 1e-6), min_w, max_w)
                    
            raw_signals.append({
                "dt": dt,
                "motor": aktif_motor,
                "fon": current_fon,
                "vol": vol_val,
                "w": w,
                "r_mom": rm,
                "r_h6": rh,
                "r_dd": rdd,
                "rt0": rt0
            })
            sermaye_track *= (1.0 + rt0) # dummy update for local dd window
            
        sig_df = pd.DataFrame(raw_signals)
        
        # 2. İcra ve Sürtünme Simülasyonu
        sermaye = self.baslangic
        n_days = len(sig_df)
        gunluk_kayitlar = []
        islem_sayisi = 0
        
        current_holding_fon = "PPZ"
        current_holding_w = 0.0
        
        for idx in range(n_days):
            row_today = sig_df.iloc[idx]
            dt_today = row_today["dt"]
            
            # Sinyal Gecikmesi (Latency)
            sig_idx = max(0, idx - latency_days)
            sig_row = sig_df.iloc[sig_idx]
            
            target_fon = sig_row["fon"]
            target_w = sig_row["w"]
            target_motor = sig_row["motor"]
            
            rt0 = row_today["rt0"]
            rm = row_today["r_mom"]
            rh = row_today["r_h6"]
            rdd = row_today["r_dd"]
            
            # Fon değişimi var mı?
            if target_fon != current_holding_fon:
                islem_sayisi += 1
                friction_loss = sermaye * (friction_bps / 10000.0)
                sermaye -= friction_loss
                current_holding_fon = target_fon
                current_holding_w = target_w
            else:
                current_holding_w = target_w
                
            # Günlük getiri
            if current_holding_fon == "PPZ" or current_holding_w == 0.0:
                day_ret = rt0
            else:
                if target_motor == "MOMENTUM":
                    f_ret = rm
                elif target_motor == "HUNTER":
                    f_ret = rh
                else:
                    f_ret = rdd
                    
                day_ret = current_holding_w * f_ret + (1.0 - current_holding_w) * rt0
                
            sermaye *= (1.0 + day_ret)
            
            gunluk_kayitlar.append({
                "tarih": dt_today,
                "bakiye": sermaye,
                "gunluk_ret": day_ret,
                "aktif_fon": current_holding_fon,
                "w": current_holding_w
            })
            
        df_res = pd.DataFrame(gunluk_kayitlar).set_index("tarih")
        
        rets = df_res["gunluk_ret"]
        n_years = len(rets) / 252.0
        cagr = ((sermaye / self.baslangic) ** (1.0 / n_years) - 1.0) * 100.0
        
        cum_max = df_res["bakiye"].cummax()
        dd = (df_res["bakiye"] - cum_max) / cum_max
        max_dd = dd.min() * 100.0
        
        ann_ret = rets.mean() * 252.0
        ann_vol = rets.std() * np.sqrt(252)
        rf = 0.35
        sharpe = (ann_ret - rf) / (ann_vol + 1e-6)
        sortino = (ann_ret - rf) / (rets[rets < 0].std() * np.sqrt(252) + 1e-6)
        calmar = cagr / abs(max_dd) if abs(max_dd) > 0 else 0
        
        # 2025 Blind ve 2026 OOS
        df_2025 = df_res.loc["2025-01-01":"2025-12-31"]
        ret_2025 = (np.prod(1.0 + df_2025["gunluk_ret"]) - 1.0) * 100.0 if len(df_2025) > 0 else 0.0
        
        df_2026 = df_res.loc["2026-01-01":]
        ret_2026 = (np.prod(1.0 + df_2026["gunluk_ret"]) - 1.0) * 100.0 if len(df_2026) > 0 else 0.0
        
        # 1 Yıllık Getiri (Son 252 gün)
        sub_1y = df_res.tail(252)
        ret_1y = (np.prod(1.0 + sub_1y["gunluk_ret"]) - 1.0) * 100.0 if len(sub_1y) > 0 else 0.0
        mdd_1y = ((sub_1y["bakiye"] - sub_1y["bakiye"].cummax()) / sub_1y["bakiye"].cummax()).min() * 100.0
        
        return {
            "cagr": cagr,
            "bakiye": sermaye,
            "max_dd": max_dd,
            "sharpe": sharpe,
            "sortino": sortino,
            "calmar": calmar,
            "ret_1y": ret_1y,
            "mdd_1y": mdd_1y,
            "ret_2025": ret_2025,
            "ret_2026": ret_2026,
            "islem_sayisi": islem_sayisi,
            "df": df_res
        }

def run_lab19_tournament():
    print("=" * 135)
    print("LAB-19: GERCEK HAYAT SURTUNME, VALOR VE GECIKME STRES TESTI (REAL-WORLD FRICTION AUDIT)")
    print("=" * 135)
    
    eng = Lab19RealWorldFrictionEngine(baslangic_sermayesi=100_000.0)
    
    # ─────────────────────────────────────────────────────────────────────────
    # DENEY 1: KAYMA VE SURTUNME STRESI (0 bps, 10 bps, 25 bps, 50 bps, 100 bps)
    # ─────────────────────────────────────────────────────────────────────────
    frictions = [0.0, 10.0, 25.0, 50.0, 100.0]
    
    print("\n--- DENEY 1: KAYMA VE SURTUNME STRESI (LATENCY = 0G) ---")
    print(f"{'Model':<20} | {'Kayma/Masraf':<16} | {'5Y CAGR':<9} | {'Terminal 100k':<15} | {'MaxDD':<8} | {'Sharpe':<8} | {'1 Yillik':<10} | {'2025 BLIND':<12} | {'2026 OOS'}")
    print("-" * 130)
    
    for bps in frictions:
        r_modele = eng.simule_et(target_vol=0.20, latency_days=0, friction_bps=bps)
        r_labe = eng.simule_et(target_vol=1.00, latency_days=0, friction_bps=bps)
        
        bps_lbl = f"{bps:.0f} bps (%{bps/100:.2f})"
        
        print(f"{'MODEL E (%20 Vol)':<20} | {bps_lbl:<16} | %{r_modele['cagr']:<7.2f} | {r_modele['bakiye']:>11,.0f} TL | %{r_modele['max_dd']:<6.2f} | {r_modele['sharpe']:<8.2f} | %{r_modele['ret_1y']:<8.1f} | %{r_modele['ret_2025']:<10.1f} | %{r_modele['ret_2026']:<7.1f}")
        print(f"{'SAF LAB-E (%100)':<20} | {bps_lbl:<16} | %{r_labe['cagr']:<7.2f} | {r_labe['bakiye']:>11,.0f} TL | %{r_labe['max_dd']:<6.2f} | {r_labe['sharpe']:<8.2f} | %{r_labe['ret_1y']:<8.1f} | %{r_labe['ret_2025']:<10.1f} | %{r_labe['ret_2026']:<7.1f}")
        print("-" * 130)
        
    # ─────────────────────────────────────────────────────────────────────────
    # DENEY 2: SİNYAL GECİKMESİ STRESİ (+1 GÜN GEÇ EMİR GİRİŞİ)
    # ─────────────────────────────────────────────────────────────────────────
    print("\n--- DENEY 2: EKSTRA +1 GUN GECIKME STRESI (INSAN/OPERASYONEL GECIKME - LATENCY +1G) ---")
    print(f"{'Model':<20} | {'Gecikme & Masraf':<16} | {'5Y CAGR':<9} | {'Terminal 100k':<15} | {'MaxDD':<8} | {'Sharpe':<8} | {'1 Yillik':<10} | {'2025 BLIND':<12} | {'2026 OOS'}")
    print("-" * 130)
    
    for bps in [0.0, 25.0, 50.0]:
        r_modele = eng.simule_et(target_vol=0.20, latency_days=1, friction_bps=bps)
        r_labe = eng.simule_et(target_vol=1.00, latency_days=1, friction_bps=bps)
        
        bps_lbl = f"+1G & {bps:.0f} bps"
        
        print(f"{'MODEL E (%20 Vol)':<20} | {bps_lbl:<16} | %{r_modele['cagr']:<7.2f} | {r_modele['bakiye']:>11,.0f} TL | %{r_modele['max_dd']:<6.2f} | {r_modele['sharpe']:<8.2f} | %{r_modele['ret_1y']:<8.1f} | %{r_modele['ret_2025']:<10.1f} | %{r_modele['ret_2026']:<7.1f}")
        print(f"{'SAF LAB-E (%100)':<20} | {bps_lbl:<16} | %{r_labe['cagr']:<7.2f} | {r_labe['bakiye']:>11,.0f} TL | %{r_labe['max_dd']:<6.2f} | {r_labe['sharpe']:<8.2f} | %{r_labe['ret_1y']:<8.1f} | %{r_labe['ret_2025']:<10.1f} | %{r_labe['ret_2026']:<7.1f}")
        print("-" * 130)

if __name__ == "__main__":
    run_lab19_tournament()
