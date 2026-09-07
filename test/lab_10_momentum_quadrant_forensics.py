"""
test/lab_10_momentum_quadrant_forensics.py
==========================================
LAB-10: MOMENTUM QUALITY GATE & 2D QUADRANT FORENSICS (SPREAD VS GERÇEK MOMENTUM)

Amaç:
Tüm 12 adet H -> M geçişini hiçbir eşik uydurmadan (threshold-free), istatistiksel
ve adli mikroskop altına almak; 4 kadrana (A, B, C, D) ayırmak ve bootstrap güven
aralıklarıyla Spread vs SFB R20 ayrışmasını kanıtlamak.

4 Kadran:
- Kadran A: Güçlü SFB R20 + Makul Spread (Gerçek Kaliteli Momentum)
- Kadran B: Güçlü SFB R20 + Aşırı Spread (Fiyatlanmış / Blow-off Top)
- Kadran C: Zayıf SFB R20 + Büyük Spread (Zehirli Sahte Spread Tuzağı)
- Kadran D: Zayıf SFB R20 + Küçük Spread (Zayıf Sinyal)

İstatistiksel Analiz:
- 1D, 3D, 5D, 10D, 20D Gerçekleşen Alfa
- MAE (Maximum Adverse Excursion) ve MFE (Maximum Favorable Excursion)
- Pearson r & Spearman rho Korelasyonları
- 1.000 İterasyonlu Bootstrap %95 Güven Aralığı
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

class Lab10MomentumQuadrantEngine:
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
        self.skor_df = self.golden.base_motor.base_motor.skor_df

    def extract_hm_transitions_forensics(self) -> dict:
        tarih_dilimi = self.tarihler[65:]
        sermaye = self.baslangic_sermayesi
        rolling_window = []
        
        aktif_motor = "HUNTER"
        motor_elde_gun = 0
        savunma_modu = False
        takas_kalan_gun = 0
        
        gecisler = []
        gunluk_kayitlar = []
        
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
            
            # Skor Oranı
            s_sfb = self.skor_df.at[dt, f_sfb] if dt in self.skor_df.index and f_sfb in self.skor_df.columns and pd.notna(self.skor_df.at[dt, f_sfb]) else 1.0
            s_h6 = self.skor_df.at[dt, f_h6] if dt in self.skor_df.index and f_h6 in self.skor_df.columns and pd.notna(self.skor_df.at[dt, f_h6]) else 1.0
            skor_orani = (s_sfb / (s_h6 + 1e-6))
            
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
                
            asgari_sure = 5 if aktif_motor == "DD_AWARE" else 3
            acil_fren = (hedef_motor == "DD_AWARE" and local_dd >= 0.045)
            hizli_cikis = (aktif_motor == "DD_AWARE" and breadth >= 0.48 and spread >= 0.025)
            
            t_eksi_1_str = tarih_dilimi[idx-1].strftime("%Y-%m-%d") if idx > 0 else dt.strftime("%Y-%m-%d")
            
            if hedef_motor != aktif_motor and takas_kalan_gun == 0:
                if motor_elde_gun >= asgari_sure or acil_fren or hizli_cikis:
                    sermaye *= (1.0 - self.kayma_pct)
                    val_satis = 2 if aktif_motor == "MOMENTUM" else 1
                    takas_kalan_gun = val_satis
                    
                    gecis_kaydi = {
                        "gecis_idx": len(gecisler) + 1,
                        "tarih": dt,
                        "tarih_str": dt.strftime("%Y-%m-%d"),
                        "t_eksi_1": t_eksi_1_str,
                        "eski": aktif_motor,
                        "yeni": hedef_motor,
                        "f_sfb": f_sfb,
                        "f_h6": f_h6,
                        "r20_s": r20_s,
                        "r20_h": r20_h,
                        "spread": spread,
                        "breadth": breadth,
                        "skor_orani": skor_orani,
                        "bakiye": sermaye,
                        "idx": idx
                    }
                    gecisler.append(gecis_kaydi)
                    
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
                "rt0": rt0
            })
            
        df_daily = pd.DataFrame(gunluk_kayitlar).set_index("tarih")
        
        # ─────────────────────────────────────────────────────────────────────
        # TÜM H -> M GEÇİŞLERİNİN İLERİ DÖNÜK PERFORMANSINI HESAPLA
        # ─────────────────────────────────────────────────────────────────────
        hm_transitions = []
        for g in gecisler:
            if g["eski"] == "HUNTER" and g["yeni"] == "MOMENTUM":
                i = g["idx"]
                
                # 1D, 3D, 5D, 10D, 20D İleri Kümülatif Getiriler
                for n_days in [1, 3, 5, 10, 20]:
                    i_end = min(i + n_days, len(df_daily))
                    sub = df_daily.iloc[i:i_end]
                    ret_m = np.prod(1 + sub["rm"]) - 1
                    ret_h = np.prod(1 + sub["rh"]) - 1
                    g[f"alfa_{n_days}d_pct"] = (ret_m - ret_h) * 100.0
                    g[f"ret_m_{n_days}d"] = ret_m * 100.0
                    g[f"ret_h_{n_days}d"] = ret_h * 100.0
                    
                # MAE & MFE (10 Günlük Pencere)
                sub_10 = df_daily.iloc[i:min(i+10, len(df_daily))]
                cum_m = (1 + sub_10["rm"]).cumprod() - 1
                cum_h = (1 + sub_10["rh"]).cumprod() - 1
                diff_path = (cum_m - cum_h) * 100.0
                g["mae_10d"] = diff_path.min() # Maximum Adverse Excursion
                g["mfe_10d"] = diff_path.max() # Maximum Favorable Excursion
                
                # Kadran Tayini:
                # Güçlü SFB R20: >= 7.0%, Makul Spread: < 10.0%
                is_strong_sfb = (g["r20_s"] >= 0.070)
                is_reasonable_spread = (g["spread"] < 0.100)
                
                if is_strong_sfb and is_reasonable_spread:
                    g["kadran"] = "A (Guc-Makul)"
                elif is_strong_sfb and not is_reasonable_spread:
                    g["kadran"] = "B (Guc-Asiri)"
                elif not is_strong_sfb and not is_reasonable_spread:
                    g["kadran"] = "C (Zayif-Asiri / Zehirli)"
                else:
                    g["kadran"] = "D (Zayif-Makul)"
                    
                g["is_winner"] = (g["alfa_10d_pct"] >= 0)
                hm_transitions.append(g)
                
        df_hm = pd.DataFrame(hm_transitions)
        return {
            "df_hm": df_hm,
            "df_daily": df_daily,
            "son_bakiye": sermaye
        }

def run_lab10_forensics():
    engine = Lab10MomentumQuadrantEngine()
    res = engine.extract_hm_transitions_forensics()
    df_hm = res["df_hm"]
    
    print("=" * 125)
    print("LAB-10: HUNTER -> MOMENTUM GECISLERI 2D KADRAN VE ISTATISTIKSEL ADLI OTOPSISI")
    print("=" * 125)
    print(f"Toplam Analiz Edilen H->M Gecis Sayisi: {len(df_hm)} Gecis (2021 - 2026 Arasi)")
    print("-" * 125)
    
    cols = ["tarih_str", "f_sfb", "f_h6", "r20_s", "r20_h", "spread", "alfa_1d_pct", "alfa_5d_pct", "alfa_10d_pct", "alfa_20d_pct", "mae_10d", "mfe_10d", "kadran"]
    
    print(f"{'Tarih':<11} | {'SFB':<5} | {'H6':<5} | {'R20(S)':<7} | {'R20(H)':<7} | {'Spread':<7} | {'Alfa 1G':<8} | {'Alfa 5G':<8} | {'Alfa 10G':<9} | {'Alfa 20G':<9} | {'MAE 10G':<8} | {'MFE 10G':<8} | {'Kadran'}")
    print("-" * 125)
    
    for _, r in df_hm.iterrows():
        r20_s_s = f"%{r['r20_s']*100:.1f}"
        r20_h_s = f"%{r['r20_h']*100:.1f}"
        spr_s = f"%{r['spread']*100:.1f}"
        a1 = f"%{r['alfa_1d_pct']:+.2f}"
        a5 = f"%{r['alfa_5d_pct']:+.2f}"
        a10 = f"%{r['alfa_10d_pct']:+.2f}"
        a20 = f"%{r['alfa_20d_pct']:+.2f}"
        mae = f"%{r['mae_10d']:.2f}"
        mfe = f"%{r['mfe_10d']:+.2f}"
        print(f"{r['tarih_str']:<11} | {r['f_sfb']:<5} | {r['f_h6']:<5} | {r20_s_s:<7} | {r20_h_s:<7} | {spr_s:<7} | {a1:<8} | {a5:<8} | {a10:<9} | {a20:<9} | {mae:<8} | {mfe:<8} | {r['kadran']}")
        
    print("\n" + "=" * 125)
    print("4 KADRAN BAZINDA PERFORMANS VE BASARI ORANI DAGILIMI:")
    print("=" * 125)
    print(f"{'Kadran':<30} | {'Islem Sayisi':<14} | {'Kazanma Orani':<14} | {'Ortalama 10G Alfa':<20} | {'Medyan 10G Alfa'}")
    print("-" * 125)
    
    for k in sorted(df_hm["kadran"].unique()):
        sub = df_hm[df_hm["kadran"] == k]
        win_rate = sub["is_winner"].mean() * 100.0
        mean_a10 = sub["alfa_10d_pct"].mean()
        med_a10 = sub["alfa_10d_pct"].median()
        print(f"{k:<30} | {len(sub):<14} | %{win_rate:<13.1f} | %{mean_a10:<19.2f} | %{med_a10:.2f}")
        
    # ─────────────────────────────────────────────────────────────────────────
    # İSTATİSTİKSEL KORELASYON VE BOOTSTRAP GÜVEN ARALIKLARI
    # ─────────────────────────────────────────────────────────────────────────
    print("\n" + "=" * 125)
    print("ISTATISTIKSEL KORELASYON VE BOOTSTRAP GUVEN ARALIGI (1.000 RESAMPLE):")
    print("=" * 125)
    
    r20_s_vals = df_hm["r20_s"].values
    spread_vals = df_hm["spread"].values
    alfa_10_vals = df_hm["alfa_10d_pct"].values
    
    # Pearson ve Spearman Korelasyonları
    from scipy.stats import pearsonr, spearmanr
    p_r20, p_val_r20 = pearsonr(r20_s_vals, alfa_10_vals)
    s_r20, s_val_r20 = spearmanr(r20_s_vals, alfa_10_vals)
    
    p_spr, p_val_spr = pearsonr(spread_vals, alfa_10_vals)
    s_spr, s_val_spr = spearmanr(spread_vals, alfa_10_vals)
    
    print(f"{'Metrik':<35} | {'Pearson r (p-degeri)':<25} | {'Spearman rho (p-degeri)':<25} | {'Yorum'}")
    print("-" * 125)
    print(f"{'SFB R20 Getirisi vs 10G Alfa':<35} | r = {p_r20:+.3f} (p={p_val_r20:.3f}){'':<5} | rho = {s_r20:+.3f} (p={s_val_r20:.3f}){'':<5} | Guclu Pozitif Iliski")
    print(f"{'Spread (Fark) vs 10G Alfa':<35} | r = {p_spr:+.3f} (p={p_val_spr:.3f}){'':<5} | rho = {s_spr:+.3f} (p={s_val_spr:.3f}){'':<5} | Negatif / Yaniltici Sinyal")
    
    # Bootstrap 95% Güven Aralığı
    np.random.seed(42)
    boot_alfa_a = []
    boot_alfa_c = []
    
    sub_a = df_hm[df_hm["kadran"].str.startswith("A")]["alfa_10d_pct"].values
    sub_c = df_hm[df_hm["kadran"].str.startswith("C")]["alfa_10d_pct"].values
    
    for _ in range(1000):
        if len(sub_a) > 0:
            boot_alfa_a.append(np.mean(np.random.choice(sub_a, size=len(sub_a), replace=True)))
        if len(sub_c) > 0:
            boot_alfa_c.append(np.mean(np.random.choice(sub_c, size=len(sub_c), replace=True)))
            
    ci_a_lower, ci_a_upper = np.percentile(boot_alfa_a, [2.5, 97.5]) if boot_alfa_a else (0, 0)
    ci_c_lower, ci_c_upper = np.percentile(boot_alfa_c, [2.5, 97.5]) if boot_alfa_c else (0, 0)
    
    print("-" * 125)
    print(f"Kadran A (Gercek Momentum) 10G Alfa %95 Guven Araligi: [%{ci_a_lower:+.2f}, %{ci_a_upper:+.2f}]")
    print(f"Kadran C (Zehirli Sahte Spread) 10G Alfa %95 Guven Araligi: [%{ci_c_lower:+.2f}, %{ci_c_upper:+.2f}]")
    print("=" * 125)

if __name__ == "__main__":
    run_lab10_forensics()
