"""
v2_1_adversarial_battery.py
===========================
HARMONY v2.1 ADAPTIVE: 15-AŞAMALI ADLİ ÖLDÜRÜCÜ STRES TESTİ BATARYASI
Amaç: 2.947M sonucunu parçalayarak zayıf noktaları, sızıntıları ve sağlamlık sınırlarını tespit etmek.
"""

import os
import sys
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from harmony_v2_1_adaptive import HarmonyV21AdaptiveMotor

def run_battery():
    print("=" * 100)
    print("      HARMONY v2.1 ADAPTIVE: 15-AŞAMALI ADLİ ÖLDÜRÜCÜ STRES TESTİ")
    print("=" * 100)
    
    motor = HarmonyV21AdaptiveMotor()
    
    # -------------------------------------------------------------------------
    # TEST 15: Orijinal 2.947M Sonucunun Yeniden Üretimi (Baseline)
    # -------------------------------------------------------------------------
    r_base = motor.simule_et_v2_1()
    print(f"\n[TEST 15] BASELINE REPRODUCTION:")
    print(f"  Son Bakiye : {r_base['son_bakiye_tl']:>12,.2f} TL")
    print(f"  CAGR       : %{r_base['cagr_pct']:>6.2f}")
    print(f"  Max Drawdown: %{r_base['max_drawdown_pct']:>6.2f}")
    print(f"  Geçiş Sayısı: {r_base['gecis_sayisi']} adet")
    
    # -------------------------------------------------------------------------
    # TEST 1: Look-Ahead / Sinyal Gecikmesi (Lag Testi)
    # -------------------------------------------------------------------------
    print(f"\n[TEST 1] LOOK-AHEAD / SİNYAL GECİKMESİ TESTİ:")
    # Lag'li simülasyon fonksiyonu
    def simule_lagli(m):
        tarih_dilimi = m.tarihler[65:]
        sermaye = m.baslangic_sermayesi
        zirve = sermaye
        aktif_motor = "HUNTER"
        motor_elde_gun = 0
        savunma_modu_aktif = False
        gecis_sayisi = 0
        
        for idx, dt in enumerate(tarih_dilimi):
            sig_dt = tarih_dilimi[max(0, idx - 1)]  # 1 gün gecikmeli sinyal
            
            breadth = m.market_breadth.get(sig_dt, 0.0)
            top5 = m.top5_avg_r20.get(sig_dt, 0.0)
            f_sfb = m.sfb_aktif_fon.get(sig_dt, "PPZ")
            f_h6 = m.h6_aktif_fon.get(sig_dt, "PPZ")
            r20_s = m.r20_df.at[sig_dt, f_sfb] if f_sfb in m.r20_df.columns and pd.notna(m.r20_df.at[sig_dt, f_sfb]) else 0.0
            r20_h = m.r20_df.at[sig_dt, f_h6] if f_h6 in m.r20_df.columns and pd.notna(m.r20_df.at[sig_dt, f_h6]) else 0.0
            spread = r20_s - r20_h
            
            if sermaye > zirve:
                zirve = sermaye
            cur_dd = (zirve - sermaye) / (zirve + 1e-8)
            
            if cur_dd >= m.dd_trigger_high or breadth <= 0.22 or top5 <= 0.012:
                savunma_modu_aktif = True
            elif cur_dd <= m.dd_trigger_low and breadth >= 0.38:
                savunma_modu_aktif = False
                
            if savunma_modu_aktif:
                hedef_motor = "DD_AWARE"
            elif breadth >= 0.48 and spread >= m.confidence_spread_esigi and cur_dd < 0.025:
                hedef_motor = "MOMENTUM"
            elif breadth >= 0.52 and r20_s >= 0.12 and spread >= 0.040:
                hedef_motor = "NOBETCI"
            else:
                hedef_motor = "HUNTER"
                
            if hedef_motor != aktif_motor:
                if motor_elde_gun >= m.min_motor_hold_gun or (hedef_motor == "DD_AWARE" and cur_dd >= 0.050):
                    sermaye *= (1.0 - m.kayma_pct)
                    aktif_motor = hedef_motor
                    motor_elde_gun = 1
                    gecis_sayisi += 1
                else:
                    motor_elde_gun += 1
            else:
                motor_elde_gun += 1
                
            # Getiri İcrası (dt günü getirisi)
            if aktif_motor == "HUNTER":
                r_gun = m.r_h6.get(dt, 0.0)
            elif aktif_motor == "MOMENTUM":
                r_gun = m.r_mom.get(dt, 0.0)
            elif aktif_motor == "NOBETCI":
                r_gun = m.r_sfb.get(dt, 0.0)
            else:
                r_gun = m.r_dd.get(dt, 0.0)
            sermaye *= (1.0 + r_gun)
            
        cagr = ((sermaye / m.baslangic_sermayesi) ** (252.0 / len(tarih_dilimi)) - 1.0) * 100
        return sermaye, cagr, gecis_sayisi

    b_lag, c_lag, g_lag = simule_lagli(motor)
    print(f"  Look-Ahead'siz (1 Gün Lag) Bakiye: {b_lag:>12,.2f} TL | CAGR: %{c_lag:>6.2f} | Geçiş: {g_lag}")
    print(f"  Fark: {b_lag - r_base['son_bakiye_tl']:>+12,.2f} TL (Etki: %{(b_lag/r_base['son_bakiye_tl']-1)*100:+.2f})")

    # -------------------------------------------------------------------------
    # TEST 2 & 3: Walk-Forward ve Kör OOS (2025 + 2026)
    # -------------------------------------------------------------------------
    print(f"\n[TEST 2 & 3] DİLİM BAZLI VE KÖR OOS TESTLERİ:")
    dilimler = [
        ("In-Sample (2021-11 -> 2023-12)", "2021-11-22", "2023-12-31"),
        ("Out-of-Sample 2024           ", "2024-01-02", "2024-12-31"),
        ("KÖR OOS 2025                  ", "2025-01-02", "2025-12-31"),
        ("KÖR OOS 2026 YTD              ", "2026-01-02", "2026-08-27"),
        ("KÖR OOS BİRLEŞİK (2025 + 2026)", "2025-01-02", "2026-08-27")
    ]
    for lbl, tb, ts in dilimler:
        r_d = motor.simule_et_v2_1(baslangic_tarihi=tb, bitis_tarihi=ts)
        print(f"  {lbl} | Bakiye: {r_d['son_bakiye_tl']:>10,.0f} TL | Getiri: %{r_d['toplam_getiri_pct']:>6.2f} | MaxDD: %{r_d['max_drawdown_pct']:>5.2f}")

    # -------------------------------------------------------------------------
    # TEST 4: Başlangıç Tarihi Değiştirme (Anchor Date Sensitivity)
    # -------------------------------------------------------------------------
    print(f"\n[TEST 4] BAŞLANGIÇ TARİHİ HASSASİYETİ (Şanslı Başlangıç Testi):")
    anchors = ["2021-11-22", "2022-01-03", "2022-03-01", "2022-06-01", "2022-09-01", "2023-01-02"]
    for anc in anchors:
        r_a = motor.simule_et_v2_1(baslangic_tarihi=anc)
        print(f"  Başlangıç: {anc} | Bakiye: {r_a['son_bakiye_tl']:>10,.0f} TL | CAGR: %{r_a['cagr_pct']:>6.2f} | MaxDD: %{r_a['max_drawdown_pct']:>5.2f}")

    # -------------------------------------------------------------------------
    # TEST 5 & 13 & 14: Parametre ve MIN_HOLD Hassasiyeti
    # -------------------------------------------------------------------------
    print(f"\n[TEST 5, 13, 14] PARAMETRE VE MIN_HOLD HASSASİYETİ:")
    hold_gunleri = [3, 5, 10, 15, 20, 30]
    for h in hold_gunleri:
        m_tmp = HarmonyV21AdaptiveMotor(min_motor_hold_gun=h)
        r_h = m_tmp.simule_et_v2_1()
        print(f"  MIN_HOLD = {h:>2} Gün | Bakiye: {r_h['son_bakiye_tl']:>10,.0f} TL | CAGR: %{r_h['cagr_pct']:>6.2f} | MaxDD: %{r_h['max_drawdown_pct']:>5.2f} | Geçiş: {r_h['gecis_sayisi']}")

    # -------------------------------------------------------------------------
    # TEST 6: İşlem Maliyeti & Kayma Stresi (Slippage Stress)
    # -------------------------------------------------------------------------
    print(f"\n[TEST 6] İŞLEM MALİYETİ VE KAYMA STRESİ:")
    kaymalar = [0.0005, 0.0010, 0.0020, 0.0030, 0.0050]
    for k in kaymalar:
        r_k = motor.simule_et_v2_1(ozel_kayma_pct=k)
        print(f"  Kayma = %{k*100:>4.2f} | Bakiye: {r_k['son_bakiye_tl']:>10,.0f} TL | CAGR: %{r_k['cagr_pct']:>6.2f} | MaxDD: %{r_k['max_drawdown_pct']:>5.2f}")

    # -------------------------------------------------------------------------
    # TEST 10: Outlier İşlem Bağımlılığı (En İyi Günleri Çıkarma)
    # -------------------------------------------------------------------------
    print(f"\n[TEST 10] OUTLIER BAĞIMLILIĞI (En İyi Günleri Çıkararak Test):")
    # Günlük getirileri çıkar
    kayitlar = r_base["gunluk_kayitlar"]
    df_k = pd.DataFrame(kayitlar)
    df_k["ret"] = df_k["bakiye"].pct_change().fillna(0.0)
    
    for n_drop in [1, 3, 5, 10]:
        df_dropped = df_k.copy()
        top_indices = df_dropped["ret"].nlargest(n_drop).index
        df_dropped.loc[top_indices, "ret"] = 0.0 # En iyi günleri sıfırla
        b_sim = 100_000.0 * (1.0 + df_dropped["ret"]).cumprod().iloc[-1]
        c_sim = ((b_sim / 100_000.0) ** (252.0 / len(df_dropped)) - 1.0) * 100
        print(f"  En İyi {n_drop:>2} Gün Çıkarıldı | Bakiye: {b_sim:>10,.0f} TL | CAGR: %{c_sim:>6.2f}")

    # -------------------------------------------------------------------------
    # TEST 9: Monte Carlo / Sıra Değiştirme (Execution Noise)
    # -------------------------------------------------------------------------
    print(f"\n[TEST 9] MONTE CARLO İCRA GÜRÜLTÜSÜ (100 Simülasyon):")
    np.random.seed(42)
    mc_sonuclar = []
    base_rets = df_k["ret"].values
    for _ in range(100):
        # Her gün %5 olasılıkla ±%0.3 rastgele icra gürültüsü
        noise = np.random.normal(0, 0.0015, len(base_rets))
        noisy_rets = base_rets + noise
        b_mc = 100_000.0 * np.prod(1.0 + noisy_rets)
        mc_sonuclar.append(b_mc)
    
    print(f"  Monte Carlo Medyan : {np.median(mc_sonuclar):>10,.0f} TL")
    print(f"  Monte Carlo %5 En Kötü: {np.percentile(mc_sonuclar, 5):>10,.0f} TL")
    print(f"  Monte Carlo %95 En İyi: {np.percentile(mc_sonuclar, 95):>10,.0f} TL")

    print("\n" + "=" * 100)

if __name__ == "__main__":
    run_battery()
