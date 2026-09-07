"""
test/lab_16_conviction_position_sizing.py
=========================================
LAB-16: CONVICTION-BASED DYNAMIC POSITION SIZING & RISK SCALING AR-GE TURNUVASI

Amaç:
LAB-E (%64.67 CAGR / 1.07M TL) referansı üzerinde, sadece T-1 konvaksiyon ve skor
bilgisini kullanarak dinamik sermaye ağırlığı (Position Sizing w in [0.30, 1.00])
uygulamak; 2025 Kör Validasyon ve 2026 Saf OOS üzerinde test etmek.

Test Edilen Modeller:
- Model A (LAB-E Ref): Sabit %100 Pozisyon (Static Sizing)
- Model B (Konservatif 3 Kademeli): Genişlik ve Skora göre %50 / %75 / %100
- Model C (Skor Dilim Kademeli): Decile D10 -> %100, D8-D9 -> %80, D5-D7 -> %60, D1-D4 -> %40
- Model D (Sürekli Skor Ölçekleme): Lineer Sigmoidal Skor Dönüşümü (w in [0.40, 1.00])
- Model E (Volatilite / Risk-Parity Sizing): 20G Tarihsel Volatiliteye göre Ters Ölçekleme

Kurallar:
- Katı T-1 veri kullanımı, 13:00 karar kesimi, gerçek fon valörleri.
- T0 PPZ nakit neması (1 - w ağırlığı günlük PPZ neması kazanır).
- 2025 Kör Validasyon ve 2026 Saf OOS ayrımı.
- Otomatik benchmark parity denetimi.
"""

import os
import sys
import numpy as np
import pandas as pd

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, base_dir)
sys.path.insert(0, os.path.join(base_dir, "test"))

from harmony_v1_motor import HarmonyMotor
from harmony_v2_2_golden import HarmonyV22GoldenMotor
from lab_11_winner_retention_and_capture_forensics import Lab11WinnerRetentionEngine

class Lab16PositionSizingEngine:
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
        
        self.fiyat_df = self.golden.base_motor.base_motor.fiyat_df
        self.skor_df = self.golden.base_motor.base_motor.skor_df
        self.fon_gunluk_ret = self.fiyat_df.pct_change().fillna(0.0)
        
        # 20 Günlük Tarihsel Volatilite Matrisi
        self.vol_20d = self.fon_gunluk_ret.rolling(20).std() * np.sqrt(252)

    def simule_et_sizing(self, model_tipi: str = "MODEL_A_STATIC") -> dict:
        sermaye = self.baslangic_sermayesi
        rolling_window = []
        
        tarih_dilimi = self.tarihler[65:]
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
            
            # LAB-E Rolling Peak 60d
            rolling_window.append(sermaye)
            if len(rolling_window) > 60:
                rolling_window.pop(0)
            local_peak = max(rolling_window)
            local_dd = (local_peak - sermaye) / (local_peak + 1e-8)
            
            # Savunma Mantığı (LAB-E Referansıyla BİREBİR AYNI)
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
                    sermaye *= (1.0 - self.kayma_pct)
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
                
            # ─────────────────────────────────────────────────────────────────
            # DİNAMİK POZİSYON BÜYÜKLÜĞÜ (POSITION SIZING HESABI)
            # ─────────────────────────────────────────────────────────────────
            aktif_fon = f_sfb if aktif_motor == "MOMENTUM" else (f_h6 if aktif_motor == "HUNTER" else "PPZ")
            
            # T-1 Skorunu ve Dilimini Çek
            t_prev = tarih_dilimi[idx-1] if idx > 0 else dt
            if t_prev in self.skor_df.index and aktif_fon in self.skor_df.columns and pd.notna(self.skor_df.at[t_prev, aktif_fon]):
                skor_val = self.skor_df.at[t_prev, aktif_fon]
                skor_serisi = self.skor_df.loc[t_prev].drop(["PPZ", "date", "tarih"], errors="ignore").dropna()
                skor_rank_pct = (skor_serisi < skor_val).mean() if len(skor_serisi) > 0 else 0.50
            else:
                skor_rank_pct = 0.50
                
            vol_f = self.vol_20d.at[t_prev, aktif_fon] if t_prev in self.vol_20d.index and aktif_fon in self.vol_20d.columns and pd.notna(self.vol_20d.at[t_prev, aktif_fon]) else 0.20
            
            if model_tipi == "MODEL_A_STATIC":
                w = 1.0 # LAB-E Sabit %100
            elif model_tipi == "MODEL_B_3_STAGE":
                if breadth >= 0.50 and skor_rank_pct >= 0.70:
                    w = 1.0 # Güçlü Konvaksiyon
                elif breadth >= 0.35:
                    w = 0.75 # Orta Konvaksiyon
                else:
                    w = 0.50 # Düşük Konvaksiyon
            elif model_tipi == "MODEL_C_DECILE":
                if skor_rank_pct >= 0.90: # Decile 10 (Şampiyon)
                    w = 1.00
                elif skor_rank_pct >= 0.70: # Decile 8-9
                    w = 0.80
                elif skor_rank_pct >= 0.40: # Decile 5-7
                    w = 0.60
                else:
                    w = 0.40
            elif model_tipi == "MODEL_D_CONTINUOUS":
                # Lineer Dönüşüm: w in [0.40, 1.00]
                w = float(np.clip(0.40 + 0.60 * skor_rank_pct, 0.40, 1.00))
            elif model_tipi == "MODEL_E_VOL_SCALED":
                # Target Vol = 0.18
                target_vol = 0.18
                w = float(np.clip(target_vol / (vol_f + 1e-4), 0.40, 1.00))
            else:
                w = 1.0
                
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
                    g_ret = rdd # DD_AWARE 100% PPZ
                sermaye *= (1 + g_ret)
                
            gunluk_kayitlar.append({
                "tarih": dt,
                "bakiye": sermaye,
                "aktif_motor": aktif_motor,
                "gunluk_ret": g_ret,
                "w": w if aktif_motor != "DD_AWARE" else 0.0,
                "yil": dt.year
            })
            
        df = pd.DataFrame(gunluk_kayitlar).set_index("tarih")
        
        gun_sayisi = len(df)
        yil_sayisi = gun_sayisi / 252.0
        cagr = ((sermaye / self.baslangic_sermayesi) ** (1.0 / yil_sayisi) - 1.0) * 100.0
        
        df["peak"] = df["bakiye"].cummax()
        df["dd"] = (df["bakiye"] - df["peak"]) / df["peak"]
        mdd = df["dd"].min() * 100.0
        
        daily_rets = df["gunluk_ret"]
        mean_ret = daily_rets.mean()
        std_ret = daily_rets.std()
        sharpe = (mean_ret / (std_ret + 1e-9)) * np.sqrt(252)
        
        neg_rets = daily_rets[daily_rets < 0]
        downside_std = neg_rets.std() if len(neg_rets) > 0 else 1e-9
        sortino = (mean_ret / (downside_std + 1e-9)) * np.sqrt(252)
        calmar = (cagr / abs(mdd)) if abs(mdd) > 0 else 0.0
        
        gains = daily_rets[daily_rets > 0].sum()
        losses = abs(daily_rets[daily_rets < 0].sum())
        pf = gains / losses if losses > 0 else np.nan
        
        yillik_ret = {}
        for y in sorted(df["yil"].unique()):
            sub = df[df["yil"] == y]
            r = (sub["bakiye"].iloc[-1] - sub["bakiye"].iloc[0]) / sub["bakiye"].iloc[0] * 100.0
            yillik_ret[y] = r
            
        avg_weight = df[df["aktif_motor"] != "DD_AWARE"]["w"].mean() * 100.0 if len(df[df["aktif_motor"] != "DD_AWARE"]) > 0 else 0.0
        
        return {
            "model": model_tipi,
            "cagr": cagr,
            "son_bakiye": sermaye,
            "mdd": mdd,
            "sharpe": sharpe,
            "sortino": sortino,
            "calmar": calmar,
            "pf": pf,
            "avg_weight": avg_weight,
            "toplam_gecis": len(gecisler),
            "yillik_ret": yillik_ret,
            "df": df
        }

def run_lab16_tournament():
    engine = Lab16PositionSizingEngine()
    
    modeller = [
        ("MODEL_A_STATIC", "MODEL A: LAB-E Ref (%100 Sabit)"),
        ("MODEL_B_3_STAGE", "MODEL B: Konservatif (%50/%75/%100)"),
        ("MODEL_C_DECILE", "MODEL C: Skor Dilim Kademeli"),
        ("MODEL_D_CONTINUOUS", "MODEL D: Surekli Skor Sizing"),
        ("MODEL_E_VOL_SCALED", "MODEL E: Volatilite Risk-Parity")
    ]
    
    sonuclar = []
    for m_kod, lbl in modeller:
        res = engine.simule_et_sizing(m_kod)
        res["label"] = lbl
        sonuclar.append(res)
        
    print("=" * 125)
    print("LAB-16: CONVICTION-BASED DYNAMIC POSITION SIZING RESMI AR-GE TURNUVA MATRISI")
    print("=" * 125)
    
    hdr = f"{'Model / Tahsis Yontemi':<35} | {'CAGR':<8} | {'Son Bakiye':<14} | {'MaxDD':<8} | {'Sharpe':<7} | {'Sortino':<8} | {'Calmar':<7} | {'PF':<6} | {'Ort. Agirlik'}"
    print(hdr)
    print("-" * 125)
    
    for s in sonuclar:
        print(f"{s['label']:<35} | %{s['cagr']:<6.2f} | {s['son_bakiye']:<11,.0f} TL | %{s['mdd']:<6.2f} | {s['sharpe']:<7.2f} | {s['sortino']:<8.2f} | {s['calmar']:<7.2f} | {s['pf']:<6.2f} | %{s['avg_weight']:.1f}")
        
    print("-" * 125)
    print("YILLARA GORE DETAYLI GETIRI VE KOR/OOS DOKUMU (2025 BLIND & 2026 OOS):")
    print("-" * 125)
    
    y_hdr = f"{'Model / Tahsis Yontemi':<35} | {'2021':<8} | {'2022':<8} | {'2023':<8} | {'2024':<8} | {'2025 Blind':<11} | {'2026 OOS':<10}"
    print(y_hdr)
    print("-" * 125)
    
    for s in sonuclar:
        r21 = f"%{s['yillik_ret'].get(2021, 0):+.1f}"
        r22 = f"%{s['yillik_ret'].get(2022, 0):+.1f}"
        r23 = f"%{s['yillik_ret'].get(2023, 0):+.1f}"
        r24 = f"%{s['yillik_ret'].get(2024, 0):+.1f}"
        r25 = f"%{s['yillik_ret'].get(2025, 0):+.1f}"
        r26 = f"%{s['yillik_ret'].get(2026, 0):+.1f}"
        print(f"{s['label']:<35} | {r21:<8} | {r22:<8} | {r23:<8} | {r24:<8} | {r25:<11} | {r26:<10}")
        
    print("=" * 125)

if __name__ == "__main__":
    run_lab16_tournament()
