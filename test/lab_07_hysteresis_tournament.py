"""
test/lab_07_hysteresis_tournament.py
====================================
LAB-07: HUNTER ↔ MOMENTUM HİSTEREZİS (CONVICTION BAND) AR-GE TURNUVASI

Amaç:
LAB-E (%64.67 CAGR / 69 Geçiş) referans modelinde tespit edilen 26 adet gereksiz
whipsaw/terstere geçişi, HUNTER ↔ MOMENTUM arasına histerezis bandı koyarak
filtrelemek; işlem sayısını azaltıp net alfayı ve risk kalitesini artırmak.

Test Edilen Varyantlar (Conviction Buffer):
- LAB-07A: 0.0% (Mevcut LAB-E Referans)
- LAB-07B: +0.5% (Buffer = 0.005)
- LAB-07C: +1.0% (Buffer = 0.010)
- LAB-07D: +1.5% (Buffer = 0.015)
- LAB-07E: +2.0% (Buffer = 0.020)
- LAB-07F: +2.5% (Buffer = 0.025)
- LAB-07G: +3.0% (Buffer = 0.030)

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

class Lab07HysteresisEngine:
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

    def simule_et_histerezis(self, buffer_pct: float = 0.0) -> dict:
        sermaye = self.baslangic_sermayesi
        rolling_window = []
        
        tarih_dilimi = self.tarihler[65:]
        gunluk_kayitlar = []
        gecisler = []
        
        aktif_motor = "HUNTER"
        motor_elde_gun = 0
        savunma_modu = False
        takas_kalan_gun = 0
        
        # Geçiş sayaçları
        h_to_m_count = 0
        m_to_h_count = 0
        savunma_gecis_count = 0
        
        # Histerezis Eşikleri
        # Giriş (HUNTER -> MOMENTUM): Spread ve R20 daha yüksek conviction ister
        giris_spread_esik = 0.020 + buffer_pct
        giris_r20_esik = 0.030 + buffer_pct
        giris_breadth_esik = 0.45
        
        # Çıkış (MOMENTUM -> HUNTER): MOM üstünlüğü belirgin şekilde kaybolana kadar pozisyonu korur
        cikis_spread_esik = max(0.005, 0.015 - buffer_pct * 0.5)
        cikis_breadth_esik = 0.40
        
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
            
            # Savunma Mantığı (Değişmedi)
            if local_dd >= 0.040 or breadth <= 0.25 or top5 <= 0.015:
                savunma_modu = True
            elif local_dd <= 0.025 and (breadth >= 0.40 or top5 >= 0.03):
                savunma_modu = False
                
            # HİSTEREZİS KARAR MEKANİZMASI
            if savunma_modu:
                hedef_motor = "DD_AWARE"
            else:
                if aktif_motor == "MOMENTUM":
                    # Zaten Momentum'dayız: Çıkış koşulu oluşmadıkça devam et
                    mom_faded = (spread <= cikis_spread_esik or breadth < cikis_breadth_esik or r20_s < 0.020)
                    if mom_faded:
                        hedef_motor = "HUNTER"
                    else:
                        hedef_motor = "MOMENTUM"
                elif aktif_motor == "HUNTER":
                    # Hunter'dayız: Güçlü conviction olmadan MOM'a atlama
                    mom_conviction = (spread >= giris_spread_esik and r20_s >= giris_r20_esik and breadth >= giris_breadth_esik)
                    if mom_conviction:
                        hedef_motor = "MOMENTUM"
                    else:
                        hedef_motor = "HUNTER"
                else:
                    # DD_AWARE'dan çıkış anı:
                    mom_conviction = (spread >= giris_spread_esik and r20_s >= giris_r20_esik and breadth >= giris_breadth_esik)
                    if mom_conviction:
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
                    
                    if aktif_motor == "HUNTER" and hedef_motor == "MOMENTUM":
                        h_to_m_count += 1
                    elif aktif_motor == "MOMENTUM" and hedef_motor == "HUNTER":
                        m_to_h_count += 1
                    else:
                        savunma_gecis_count += 1
                        
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
                
            if takas_kalan_gun > 0:
                sermaye *= (1 + rt0)
                takas_kalan_gun -= 1
                g_ret = rt0
            else:
                if aktif_motor == "HUNTER":
                    g_ret = rh
                elif aktif_motor == "MOMENTUM":
                    g_ret = rm
                else:
                    g_ret = rdd
                sermaye *= (1 + g_ret)
                
            gunluk_kayitlar.append({
                "tarih": dt,
                "bakiye": sermaye,
                "aktif_motor": aktif_motor,
                "gunluk_ret": g_ret,
                "yil": dt.year
            })
            
        df = pd.DataFrame(gunluk_kayitlar).set_index("tarih")
        
        # Metrikler
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
        
        # Sortino (Downside risk)
        neg_rets = daily_rets[daily_rets < 0]
        downside_std = neg_rets.std() if len(neg_rets) > 0 else 1e-9
        sortino = (mean_ret / (downside_std + 1e-9)) * np.sqrt(252)
        
        # Calmar
        calmar = (cagr / abs(mdd)) if abs(mdd) > 0 else 0.0
        
        gains = daily_rets[daily_rets > 0].sum()
        losses = abs(daily_rets[daily_rets < 0].sum())
        pf = gains / losses if losses > 0 else np.nan
        
        # Yıllık Getiriler
        yillik_ret = {}
        for y in sorted(df["yil"].unique()):
            sub = df[df["yil"] == y]
            r = (sub["bakiye"].iloc[-1] - sub["bakiye"].iloc[0]) / sub["bakiye"].iloc[0] * 100.0
            yillik_ret[y] = r
            
        return {
            "buffer": buffer_pct,
            "cagr": cagr,
            "son_bakiye": sermaye,
            "mdd": mdd,
            "sharpe": sharpe,
            "sortino": sortino,
            "calmar": calmar,
            "pf": pf,
            "toplam_gecis": len(gecisler),
            "h_to_m": h_to_m_count,
            "m_to_h": m_to_h_count,
            "savunma_gecis": savunma_gecis_count,
            "yillik_ret": yillik_ret,
            "gecisler": gecisler,
            "df": df
        }

def run_lab_07_tournament():
    engine = Lab07HysteresisEngine()
    
    buffers = [0.0, 0.005, 0.010, 0.015, 0.020, 0.025, 0.030]
    varyant_adlari = [
        "LAB-07A (Ref 0.0%)",
        "LAB-07B (+0.5%)",
        "LAB-07C (+1.0%)",
        "LAB-07D (+1.5%)",
        "LAB-07E (+2.0%)",
        "LAB-07F (+2.5%)",
        "LAB-07G (+3.0%)"
    ]
    
    sonuclar = []
    for b in buffers:
        res = engine.simule_et_histerezis(buffer_pct=b)
        sonuclar.append(res)
        
    print("=" * 115)
    print("LAB-07: HUNTER <-> MOMENTUM HISTEREZIS (CONVICTION BAND) RESMI TURNUVA MATRISI")
    print("=" * 115)
    
    hdr = f"{'Varyant':<20} | {'CAGR':<8} | {'Son Bakiye':<14} | {'MaxDD':<8} | {'Sharpe':<7} | {'Sortino':<8} | {'Calmar':<7} | {'Gecis (H<->M)':<14} | {'Engellenen'}"
    print(hdr)
    print("-" * 115)
    
    ref_gecis = sonuclar[0]["toplam_gecis"]
    for i, s in enumerate(sonuclar):
        hm_str = f"{s['toplam_gecis']} ({s['h_to_m']}+{s['m_to_h']})"
        engellenen = f"-{ref_gecis - s['toplam_gecis']}" if i > 0 else "0 (Ref)"
        print(f"{varyant_adlari[i]:<20} | %{s['cagr']:<6.2f} | {s['son_bakiye']:<11,.0f} TL | %{s['mdd']:<6.2f} | {s['sharpe']:<7.2f} | {s['sortino']:<8.2f} | {s['calmar']:<7.2f} | {hm_str:<14} | {engellenen}")
        
    print("-" * 115)
    print("YILLARA GORE PERFORMANS VE VALIDASYON DOKUMU:")
    print("-" * 115)
    
    y_hdr = f"{'Varyant':<20} | {'2021':<8} | {'2022':<8} | {'2023':<8} | {'2024':<8} | {'2025 Blind':<11} | {'2026 OOS':<10}"
    print(y_hdr)
    print("-" * 115)
    
    for i, s in enumerate(sonuclar):
        r21 = f"%{s['yillik_ret'].get(2021, 0):+.1f}"
        r22 = f"%{s['yillik_ret'].get(2022, 0):+.1f}"
        r23 = f"%{s['yillik_ret'].get(2023, 0):+.1f}"
        r24 = f"%{s['yillik_ret'].get(2024, 0):+.1f}"
        r25 = f"%{s['yillik_ret'].get(2025, 0):+.1f}"
        r26 = f"%{s['yillik_ret'].get(2026, 0):+.1f}"
        print(f"{varyant_adlari[i]:<20} | {r21:<8} | {r22:<8} | {r23:<8} | {r24:<8} | {r25:<11} | {r26:<10}")
        
    print("=" * 115)

if __name__ == "__main__":
    run_lab_07_tournament()
