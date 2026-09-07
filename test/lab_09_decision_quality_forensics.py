"""
test/lab_09_decision_quality_forensics.py
=========================================
LAB-09: HUNTER ↔ MOMENTUM KARAR KALİTESİ VE KARŞI-OLGUSAL (COUNTERFACTUAL) OTOPSİSİ

Amaç:
1. Benchmark Parity: LAB-E (%64.67 CAGR / 1.070.946 TL) ile %100 birebir eşitlik.
2. Karşı-Olgusal (Counterfactual) Simülasyonlar: Hangi geçiş yönünün (H->M vs M->H)
   gerçek sorun olduğunu ve teorik olarak ne kadar alfanın kurtarılabileceğini kanıtlamak.
3. Geçiş Anındaki Göstergelerin Ayırt Etme Gücü (Threshold-Free Feature Discriminator):
   Başarılı geçişlerle sahte (whipsaw) geçişleri doğal olarak ayıran bir sinyal var mı?

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

class Lab09DecisionQualityEngine:
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

    def run_simulation(
        self,
        block_h_to_m: bool = False,
        block_m_to_h: bool = False,
        perfect_oracle_h_to_m: bool = False, # Sadece zararlı H->M geçişlerini engelle
        perfect_oracle_m_to_h: bool = False  # Sadece zararlı M->H geçişlerini engelle
    ) -> dict:
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
                
            # Karşı-Olgusal Müdahaleler
            if block_h_to_m and aktif_motor == "HUNTER" and hedef_motor == "MOMENTUM":
                hedef_motor = "HUNTER"
                
            if block_m_to_h and aktif_motor == "MOMENTUM" and hedef_motor == "HUNTER":
                hedef_motor = "MOMENTUM"
                
            # Kahin Kontrolü (10 günlük ileri getiriye bakarak zararlıysa iptal et)
            if perfect_oracle_h_to_m and aktif_motor == "HUNTER" and hedef_motor == "MOMENTUM":
                i_son = min(idx + 10, len(tarih_dilimi))
                sub_dates = tarih_dilimi[idx:i_son]
                fut_rh = np.prod([1 + self.r_h6.get(d, 0.0) for d in sub_dates]) - 1
                fut_rm = np.prod([1 + self.r_mom.get(d, 0.0) for d in sub_dates]) - 1
                if fut_rm < fut_rh: # MOM daha kötü olacaksa geçme
                    hedef_motor = "HUNTER"
                    
            if perfect_oracle_m_to_h and aktif_motor == "MOMENTUM" and hedef_motor == "HUNTER":
                i_son = min(idx + 10, len(tarih_dilimi))
                sub_dates = tarih_dilimi[idx:i_son]
                fut_rh = np.prod([1 + self.r_h6.get(d, 0.0) for d in sub_dates]) - 1
                fut_rm = np.prod([1 + self.r_mom.get(d, 0.0) for d in sub_dates]) - 1
                if fut_rh < fut_rm: # HUNTER daha kötü olacaksa geçme
                    hedef_motor = "MOMENTUM"
                    
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
                        "spread": spread,
                        "breadth": breadth,
                        "top5": top5,
                        "r20_s": r20_s,
                        "r20_h": r20_h,
                        "idx": idx,
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
                "rh": rh,
                "rm": rm,
                "rdd": rdd,
                "rt0": rt0,
                "spread": spread,
                "breadth": breadth,
                "top5": top5,
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
            "cagr": cagr,
            "son_bakiye": sermaye,
            "mdd": mdd,
            "sharpe": sharpe,
            "sortino": sortino,
            "calmar": calmar,
            "pf": pf,
            "toplam_gecis": len(gecisler),
            "yillik_ret": yillik_ret,
            "gecisler": gecisler,
            "df": df
        }

def run_lab_09():
    engine = Lab09DecisionQualityEngine()
    
    # 1. Senaryo Koşumları
    res_labe = engine.run_simulation() # Gerçek LAB-E
    res_block_hm = engine.run_simulation(block_h_to_m=True) # H->M Engellendi
    res_block_mh = engine.run_simulation(block_m_to_h=True) # M->H Engellendi
    res_oracle_hm = engine.run_simulation(perfect_oracle_h_to_m=True) # Kahin H->M
    res_oracle_mh = engine.run_simulation(perfect_oracle_m_to_h=True) # Kahin M->H
    res_oracle_both = engine.run_simulation(perfect_oracle_h_to_m=True, perfect_oracle_m_to_h=True) # Mükemmel Kahin
    
    print("=" * 115)
    print("LAB-09: HUNTER <-> MOMENTUM KARAR KALITESI VE KARSI-OLGUSAL (COUNTERFACTUAL) RAPORU")
    print("=" * 115)
    
    print(f"{'Senaryo':<35} | {'CAGR':<8} | {'Son Bakiye':<14} | {'MaxDD':<8} | {'Sharpe':<7} | {'Sortino':<8} | {'Gecis'}")
    print("-" * 115)
    
    senaryolar = [
        ("0. Gercek LAB-E Benchmark", res_labe),
        ("1. Tum H->M Gecislerini Engelle", res_block_hm),
        ("2. Tum M->H Gecislerini Engelle", res_block_mh),
        ("3. Sadece Hatali H->M Engelle", res_oracle_hm),
        ("4. Sadece Hatali M->H Engelle", res_oracle_mh),
        ("5. Mukemmel Kahin (Tum Hatalar)", res_oracle_both)
    ]

    
    for lbl, s in senaryolar:
        print(f"{lbl:<35} | %{s['cagr']:<6.2f} | {s['son_bakiye']:<11,.0f} TL | %{s['mdd']:<6.2f} | {s['sharpe']:<7.2f} | {s['sortino']:<8.2f} | {s['toplam_gecis']}")
        
    print("-" * 115)
    print("YILLARA GORE DETAYLI GETIRI VE KOR/OOS KARSILASTIRMASI:")
    print("-" * 115)
    
    y_hdr = f"{'Senaryo':<35} | {'2021':<8} | {'2022':<8} | {'2023':<8} | {'2024':<8} | {'2025 Blind':<11} | {'2026 OOS':<10}"
    print(y_hdr)
    print("-" * 115)
    
    for lbl, s in senaryolar:
        r21 = f"%{s['yillik_ret'].get(2021, 0):+.1f}"
        r22 = f"%{s['yillik_ret'].get(2022, 0):+.1f}"
        r23 = f"%{s['yillik_ret'].get(2023, 0):+.1f}"
        r24 = f"%{s['yillik_ret'].get(2024, 0):+.1f}"
        r25 = f"%{s['yillik_ret'].get(2025, 0):+.1f}"
        r26 = f"%{s['yillik_ret'].get(2026, 0):+.1f}"
        print(f"{lbl:<35} | {r21:<8} | {r22:<8} | {r23:<8} | {r24:<8} | {r25:<11} | {r26:<10}")
        
    # ─────────────────────────────────────────────────────────────────────────
    # 2. THRESHOLD-FREE SİNYAL AYIRT ETME ANALİZİ (ÖZELLİK DAĞILIMI)
    # ─────────────────────────────────────────────────────────────────────────
    print("\n" + "=" * 115)
    print("HUNTER -> MOMENTUM GECISLERINDE BASARILI VS HATALI ISLEMLERIN GÖSTERGE OTOPSISI:")
    print("=" * 115)
    
    df_main = res_labe["df"]
    gecisler_labe = res_labe["gecisler"]
    
    hm_gecisler = []
    for g in gecisler_labe:
        if g["eski"] == "HUNTER" and g["yeni"] == "MOMENTUM":
            i = g["idx"]
            i_son = min(i + 10, len(df_main))
            sub = df_main.iloc[i:i_son]
            ret_m = (1 + sub["rm"]).prod() - 1
            ret_h = (1 + sub["rh"]).prod() - 1
            alfa_10g = ret_m - ret_h
            g["is_winner"] = (alfa_10g >= 0)
            g["alfa_10g_pct"] = alfa_10g * 100.0
            hm_gecisler.append(g)
            
    df_hm = pd.DataFrame(hm_gecisler)
    
    if not df_hm.empty:
        winners = df_hm[df_hm["is_winner"] == True]
        losers = df_hm[df_hm["is_winner"] == False]
        
        print(f"Toplam H->M Geçişi: {len(df_hm)} | Başarılı (Doğru): {len(winners)} | Hatalı (Whipsaw): {len(losers)}")
        print("-" * 115)
        print(f"{'Gösterge Parametresi':<30} | {'Başarılı Geçişler Ortalaması':<30} | {'Hatalı Geçişler Ortalaması':<30}")
        print("-" * 115)
        print(f"{'Spread (R20_SFB - R20_H6)':<30} | %{winners['spread'].mean()*100:<29.2f} | %{losers['spread'].mean()*100:<29.2f}")
        print(f"{'Market Breadth (Genişlik)':<30} | %{winners['breadth'].mean()*100:<29.2f} | %{losers['breadth'].mean()*100:<29.2f}")
        print(f"{'Top-5 Ortalama R20':<30} | %{winners['top5'].mean()*100:<29.2f} | %{losers['top5'].mean()*100:<29.2f}")
        print(f"{'SFB Lider R20 Getirisi':<30} | %{winners['r20_s'].mean()*100:<29.2f} | %{losers['r20_h'].mean()*100:<29.2f}")
        
    print("=" * 115)

if __name__ == "__main__":
    run_lab_09()
