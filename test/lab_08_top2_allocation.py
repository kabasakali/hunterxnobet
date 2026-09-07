"""
test/lab_08_top2_allocation.py
==============================
LAB-08: TOP-2 ALFA DAĞILIMI (İKİLİ ŞAMPİYON ALLOCATION) AR-GE TURNUVASI

Amaç:
LAB-E (%64.67 CAGR / 1.07M TL) saf referans omurgası üzerine, tek-fon konsantrasyon
riskini azaltmak ve ikinci güçlü fonun getirisini yakalamak amacıyla kontrollü
Top-2 Alfa Dağılımını test etmek.

Kalite Filtresi (Quality Gate):
- İkinci fon (Top-2) SADECE şu koşullarda portföye alınır:
  1. Skor(Top-2) >= %70 * Skor(Top-1) (İkinci fon lidere yakın güçte olmalı)
  2. R20(Top-2) >= %2.0 (İkinci fon pozitif trendde olmalı)
- Koşul sağlanmazsa portföy %100 Lider fona odaklanır.

Test Edilen Varyantlar (Top-1 / Top-2):
- REF (100 / 0) : %100 Lider (Saf LAB-E Benchmark)
- LAB-08A (90/10): %90 Lider + %10 İkinci
- LAB-08B (80/20): %80 Lider + %20 İkinci
- LAB-08C (70/30): %70 Lider + %30 İkinci
- LAB-08D (60/40): %60 Lider + %40 İkinci
- LAB-08E (50/50): %50 Lider + %50 İkinci

Kurallar:
- Katı T-1 veri kullanımı
- 13:00 karar kesimi
- Gerçek fon valörleri (T+1 / T+2)
- T0 PPZ nakit neması
- 2025 Kör Validasyon ve 2026 Saf OOS ayrımı
- Sıfır sızıntı garantisi
"""

import os
import sys
import numpy as np
import pandas as pd

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, base_dir)

from harmony_v1_motor import HarmonyMotor
from meta_allocator_motor import MetaAllocatorMotor
from harmony_v2_2_golden import HarmonyV22GoldenMotor

class Lab08Top2AllocationEngine:
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
        
        # Temel fiyat ve getiri matrisleri
        self.base_v1 = self.golden.base_motor.base_motor
        self.fiyat_df = self.base_v1.fiyat_df
        self.skor_df = self.base_v1.skor_df
        self.fon_gunluk_ret = self.fiyat_df.pct_change().fillna(0.0)

    def simule_et_top2(self, w1: float = 1.0, w2: float = 0.0) -> dict:
        sermaye = self.baslangic_sermayesi
        rolling_window = []
        
        tarih_dilimi = self.tarihler[65:]
        gunluk_kayitlar = []
        gecisler = []
        
        aktif_motor = "HUNTER"
        motor_elde_gun = 0
        savunma_modu = False
        takas_kalan_gun = 0
        
        # Top-2 Metrik Takibi
        top2_aktif_gun_sayisi = 0
        top2_ekstra_tl = 0.0
        
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
            
            # Savunma Mantığı (LAB-E Referansıyla Birebir Aynı)
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
            # TOP-2 GETİRİ HESABI
            # ─────────────────────────────────────────────────────────────────
            if takas_kalan_gun > 0:
                sermaye *= (1 + rt0)
                takas_kalan_gun -= 1
                g_ret = rt0
            else:
                if aktif_motor == "DD_AWARE":
                    g_ret = rdd
                else:
                    # Top-1 ve Top-2 Fonlarını Belirle
                    if dt in self.skor_df.index:
                        skorlar = self.skor_df.loc[dt].dropna().sort_values(ascending=False)
                        # PPZ hariç fonlar
                        skorlar = skorlar[[c for c in skorlar.index if c not in ['PPZ', 'date', 'tarih']]]
                        if len(skorlar) >= 2:
                            fon1 = skorlar.index[0]
                            fon2 = skorlar.index[1]
                            s1 = skorlar.iloc[0]
                            s2 = skorlar.iloc[1]
                            
                            r20_2 = self.r20_df.at[dt, fon2] if fon2 in self.r20_df.columns and pd.notna(self.r20_df.at[dt, fon2]) else 0.0
                            
                            # Kalite Filtresi: Top-2 güçlü mü?
                            top2_gecerli = (s2 >= 0.70 * s1 and r20_2 >= 0.020 and w2 > 0)
                            
                            r_f1 = self.fon_gunluk_ret.at[dt, fon1] if fon1 in self.fon_gunluk_ret.columns else 0.0
                            r_f2 = self.fon_gunluk_ret.at[dt, fon2] if fon2 in self.fon_gunluk_ret.columns else 0.0
                            
                            if top2_gecerli:
                                top2_aktif_gun_sayisi += 1
                                g_ret = (w1 * r_f1) + (w2 * r_f2)
                                top2_ekstra_tl += (g_ret - r_f1) * sermaye
                            else:
                                g_ret = r_f1
                        else:
                            g_ret = rh if aktif_motor == "HUNTER" else rm
                    else:
                        g_ret = rh if aktif_motor == "HUNTER" else rm
                        
                sermaye *= (1 + g_ret)
                
            gunluk_kayitlar.append({
                "tarih": dt,
                "bakiye": sermaye,
                "aktif_motor": aktif_motor,
                "gunluk_ret": g_ret,
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
            
        return {
            "w1": w1,
            "w2": w2,
            "cagr": cagr,
            "son_bakiye": sermaye,
            "mdd": mdd,
            "sharpe": sharpe,
            "sortino": sortino,
            "calmar": calmar,
            "pf": pf,
            "toplam_gecis": len(gecisler),
            "top2_gun": top2_aktif_gun_sayisi,
            "top2_ekstra_tl": top2_ekstra_tl,
            "yillik_ret": yillik_ret,
            "df": df
        }

def run_top2_tournament():
    engine = Lab08Top2AllocationEngine()
    
    agirliklar = [
        (1.0, 0.0, "REF (100/0)"),
        (0.9, 0.1, "LAB-08A (90/10)"),
        (0.8, 0.2, "LAB-08B (80/20)"),
        (0.7, 0.3, "LAB-08C (70/30)"),
        (0.6, 0.4, "LAB-08D (60/40)"),
        (0.5, 0.5, "LAB-08E (50/50)")
    ]

    
    sonuclar = []
    for w1, w2, lbl in agirliklar:
        res = engine.simule_et_top2(w1=w1, w2=w2)
        res["label"] = lbl
        sonuclar.append(res)
        
    print("=" * 115)
    print("LAB-08: TOP-2 ALFA DAGILIMI (IKILI SAMPİYON) RESMI TURNUVA MATRISI")
    print("=" * 115)
    
    hdr = f"{'Varyant':<20} | {'CAGR':<8} | {'Son Bakiye':<14} | {'MaxDD':<8} | {'Sharpe':<7} | {'Sortino':<8} | {'Calmar':<7} | {'PF':<6} | {'Top-2 Gun'}"
    print(hdr)
    print("-" * 115)
    
    for s in sonuclar:
        print(f"{s['label']:<20} | %{s['cagr']:<6.2f} | {s['son_bakiye']:<11,.0f} TL | %{s['mdd']:<6.2f} | {s['sharpe']:<7.2f} | {s['sortino']:<8.2f} | {s['calmar']:<7.2f} | {s['pf']:<6.2f} | {s['top2_gun']} gun")
        
    print("-" * 115)
    print("YILLARA GORE DETAYLI GETIRI VE KOR/OOS DOKUMU:")
    print("-" * 115)
    
    y_hdr = f"{'Varyant':<20} | {'2021':<8} | {'2022':<8} | {'2023':<8} | {'2024':<8} | {'2025 Blind':<11} | {'2026 OOS':<10}"
    print(y_hdr)
    print("-" * 115)
    
    for s in sonuclar:
        r21 = f"%{s['yillik_ret'].get(2021, 0):+.1f}"
        r22 = f"%{s['yillik_ret'].get(2022, 0):+.1f}"
        r23 = f"%{s['yillik_ret'].get(2023, 0):+.1f}"
        r24 = f"%{s['yillik_ret'].get(2024, 0):+.1f}"
        r25 = f"%{s['yillik_ret'].get(2025, 0):+.1f}"
        r26 = f"%{s['yillik_ret'].get(2026, 0):+.1f}"
        print(f"{s['label']:<20} | {r21:<8} | {r22:<8} | {r23:<8} | {r24:<8} | {r25:<11} | {r26:<10}")
        
    print("=" * 115)

if __name__ == "__main__":
    run_top2_tournament()
