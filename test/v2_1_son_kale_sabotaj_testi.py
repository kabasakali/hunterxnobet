"""
v2_1_son_kale_sabotaj_testi.py
==============================
HARMONY v2.1 ADAPTIVE: "SON KALE" KASITLI SABOTAJ VE ÖLÜM TESTİ
Amaç: Sistemi kırmak, öldürmek ve hangi koşulda iflas ettiğini bulmak.
"""

import os
import sys
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from harmony_v2_1_adaptive import HarmonyV21AdaptiveMotor

def run_sabotage_battery():
    print("=" * 105)
    print("        HARMONY v2.1: 'SON KALE' KASITLI BOZMA VE SİSTEMİ ÖLDÜRME TESTİ")
    print("=" * 105)

    base_motor = HarmonyV21AdaptiveMotor()
    r_base = base_motor.simule_et_v2_1()
    base_bakiye = r_base['son_bakiye_tl']
    base_cagr = r_base['cagr_pct']
    base_mdd = r_base['max_drawdown_pct']
    
    print(f"\n[ORİJİNAL SAĞLIKLI DURUM]: Bakiye: {base_bakiye:>12,.0f} TL | CAGR: %{base_cagr:>5.2f} | MaxDD: %{base_mdd:>5.2f}")
    print("-" * 105)

    sonuclar = []

    # -------------------------------------------------------------------------
    # SALDIRI 1: Sinyalleri 1, 2, 3 Gün Geciktirme (Extreme Execution Delay)
    # -------------------------------------------------------------------------
    print("\n[SALDIRI 1] SİNYAL GECİKTİRME STRESİ (1, 2, 3 Gün Geç Emir Verme):")
    for lag_gun in [1, 2, 3]:
        tarih_dilimi = base_motor.tarihler[65:]
        sermaye = 100_000.0
        zirve = sermaye
        mdd = 0.0
        aktif = "HUNTER"
        elde = 0
        savunma = False
        
        for idx, dt in enumerate(tarih_dilimi):
            sig_dt = tarih_dilimi[max(0, idx - lag_gun)]
            breadth = base_motor.market_breadth.get(sig_dt, 0.0)
            top5 = base_motor.top5_avg_r20.get(sig_dt, 0.0)
            f_sfb = base_motor.sfb_aktif_fon.get(sig_dt, "PPZ")
            f_h6 = base_motor.h6_aktif_fon.get(sig_dt, "PPZ")
            r20_s = base_motor.r20_df.at[sig_dt, f_sfb] if f_sfb in base_motor.r20_df.columns and pd.notna(base_motor.r20_df.at[sig_dt, f_sfb]) else 0.0
            r20_h = base_motor.r20_df.at[sig_dt, f_h6] if f_h6 in base_motor.r20_df.columns and pd.notna(base_motor.r20_df.at[sig_dt, f_h6]) else 0.0
            spread = r20_s - r20_h
            
            if sermaye > zirve: zirve = sermaye
            cur_dd = (zirve - sermaye) / (zirve + 1e-8)
            if cur_dd > mdd: mdd = cur_dd
            
            if cur_dd >= 0.045 or breadth <= 0.22 or top5 <= 0.012: savunma = True
            elif cur_dd <= 0.020 and breadth >= 0.38: savunma = False
            
            hedef = "DD_AWARE" if savunma else ("MOMENTUM" if (breadth>=0.48 and spread>=0.025 and cur_dd<0.025) else ("NOBETCI" if (breadth>=0.52 and r20_s>=0.12 and spread>=0.040) else "HUNTER"))
            
            if hedef != aktif:
                if elde >= 15 or (hedef == "DD_AWARE" and cur_dd >= 0.050):
                    sermaye *= (1.0 - 0.0005)
                    aktif = hedef
                    elde = 1
                else: elde += 1
            else: elde += 1
            
            r_g = base_motor.r_h6.get(dt, 0.0) if aktif=="HUNTER" else (base_motor.r_mom.get(dt, 0.0) if aktif=="MOMENTUM" else (base_motor.r_sfb.get(dt, 0.0) if aktif=="NOBETCI" else base_motor.r_dd.get(dt, 0.0)))
            sermaye *= (1.0 + r_g)
            
        cagr = ((sermaye / 100_000.0) ** (252.0 / len(tarih_dilimi)) - 1.0) * 100
        durum = "YAŞIYOR" if cagr > 40 else "ÖLDÜ"
        print(f"  Lag = {lag_gun} Gün | Bakiye: {sermaye:>12,.0f} TL | CAGR: %{cagr:>5.2f} | MaxDD: %{-mdd*100:>5.2f} | [{durum}]")
        sonuclar.append((f"Sinyal Lag {lag_gun}G", cagr, -mdd*100, durum))

    # -------------------------------------------------------------------------
    # SALDIRI 2: %1.00 Devasa Komisyon / Slippage Cezası (Extreme Cost)
    # -------------------------------------------------------------------------
    print("\n[SALDIRI 2] DEVASA KOMİSYON VE KAYMA CEZASI (%1.00 Her İşlemde):")
    for k in [0.0050, 0.0100, 0.0150]:
        r_k = base_motor.simule_et_v2_1(ozel_kayma_pct=k)
        durum = "YAŞIYOR" if r_k['cagr_pct'] > 40 else "ÖLDÜ"
        print(f"  İşlem Başı Kayma = %{k*100:>4.2f} | Bakiye: {r_k['son_bakiye_tl']:>12,.0f} TL | CAGR: %{r_k['cagr_pct']:>5.2f} | MaxDD: %{r_k['max_drawdown_pct']:>5.2f} | [{durum}]")
        sonuclar.append((f"Kayma %{k*100:.2f}", r_k['cagr_pct'], r_k['max_drawdown_pct'], durum))

    # -------------------------------------------------------------------------
    # SALDIRI 3: En İyi %10 İşlemi Tamamen Silme (Alpha Extraction Sabotage)
    # -------------------------------------------------------------------------
    print("\n[SALDIRI 3] EN İYİ %10 GÜNÜ SİLME (Alfa Katliamı):")
    kayitlar = r_base["gunluk_kayitlar"]
    df_k = pd.DataFrame(kayitlar)
    df_k["ret"] = df_k["bakiye"].pct_change().fillna(0.0)
    
    n_total = len(df_k)
    for drop_pct in [0.02, 0.05, 0.10]:
        n_drop = int(n_total * drop_pct)
        df_sabotage = df_k.copy()
        top_idx = df_sabotage["ret"].nlargest(n_drop).index
        df_sabotage.loc[top_idx, "ret"] = 0.0  # En iyi günleri sıfırla
        b_sim = 100_000.0 * np.prod(1.0 + df_sabotage["ret"])
        c_sim = ((b_sim / 100_000.0) ** (252.0 / n_total) - 1.0) * 100
        durum = "YAŞIYOR" if c_sim > 35 else "ÖLDÜ"
        print(f"  En İyi %{drop_pct*100:>2.0f} ({n_drop:>3} gün) Silindi | Bakiye: {b_sim:>12,.0f} TL | CAGR: %{c_sim:>5.2f} | [{durum}]")
        sonuclar.append((f"En İyi %{drop_pct*100:.0f} Silindi", c_sim, base_mdd, durum))

    # -------------------------------------------------------------------------
    # SALDIRI 4: Parametreleri ±%30 Kasıtlı Bozma (De-optimization)
    # -------------------------------------------------------------------------
    print("\n[SALDIRI 4] PARAMETRELERİ ±%30 BOZMA (De-Optimization):")
    bozuk_paramlar = [
        ("Agresif Gecikmeli", 5, 0.050, 0.070, 0.010),
        ("Aşırı Korkak", 30, 0.010, 0.025, 0.015),
        ("Kör / Sağırlık", 25, 0.060, 0.080, 0.040)
    ]
    for ad, m_hold, c_spread, dd_hi, dd_lo in bozuk_paramlar:
        m_bozuk = HarmonyV21AdaptiveMotor(
            min_motor_hold_gun=m_hold,
            confidence_spread_esigi=c_spread,
            dd_trigger_high=dd_hi,
            dd_trigger_low=dd_lo
        )
        r_bzk = m_bozuk.simule_et_v2_1()
        durum = "YAŞIYOR" if r_bzk['cagr_pct'] > 40 else "ÖLDÜ"
        print(f"  Mod: {ad:<18} | Bakiye: {r_bzk['son_bakiye_tl']:>12,.0f} TL | CAGR: %{r_bzk['cagr_pct']:>5.2f} | MaxDD: %{r_bzk['max_drawdown_pct']:>5.2f} | [{durum}]")
        sonuclar.append((f"Bozuk Param ({ad})", r_bzk['cagr_pct'], r_bzk['max_drawdown_pct'], durum))

    # -------------------------------------------------------------------------
    # SALDIRI 5: Fon Evreninin %30'unu Rastgele Yok Etme (Fund Genocide)
    # -------------------------------------------------------------------------
    print("\n[SALDIRI 5] FON EVRENİNİN %30'UNU RASTGELE YOK ETME:")
    np.random.seed(99)
    # Motor getirilerine %30 kayıp/gürültü şoku
    bakiye_genocide = 100_000.0
    zirve_g = bakiye_genocide
    mdd_g = 0.0
    for r_ret in df_k["ret"]:
        # %30 ihtimalle o günkü fon bulunamadı (T0 repo getirisine düştü)
        if np.random.rand() < 0.30:
            ret_eff = 0.0008 # Sadece repo
        else:
            ret_eff = r_ret
        bakiye_genocide *= (1.0 + ret_eff)
        if bakiye_genocide > zirve_g: zirve_g = bakiye_genocide
        dd_curr = (zirve_g - bakiye_genocide) / zirve_g
        if dd_curr > mdd_g: mdd_g = dd_curr
        
    c_genocide = ((bakiye_genocide / 100_000.0) ** (252.0 / n_total) - 1.0) * 100
    durum = "YAŞIYOR" if c_genocide > 40 else "ÖLDÜ"
    print(f"  %30 Fon Kaybı Simülasyonu | Bakiye: {bakiye_genocide:>12,.0f} TL | CAGR: %{c_genocide:>5.2f} | MaxDD: %{-mdd_g*100:>5.2f} | [{durum}]")
    sonuclar.append(("%30 Fon Kaybı", c_genocide, -mdd_g*100, durum))

    # -------------------------------------------------------------------------
    # SALDIRI 6: Sentetik 2 Yıllık Vahşi Ayı Piyasası (-%40 BİST Çöküşü)
    # -------------------------------------------------------------------------
    print("\n[SALDIRI 6] SENTETİK 2 YILLIK VAHŞİ AYI PİYASASI ŞOKU:")
    # 250 seans boyunca her hisse/fon gününe -%0.50 ekstra düşüş cezası
    bakiye_bear = 100_000.0
    zirve_bear = bakiye_bear
    mdd_bear = 0.0
    for idx, r_ret in enumerate(df_k["ret"]):
        if 200 <= idx <= 500: # 300 seanslık (1.5 yıl) acımasız ayı dönemi
            ret_bear = r_ret - 0.0040 # Günlük -0.4% ekstra ceza
        else:
            ret_bear = r_ret
        bakiye_bear *= (1.0 + ret_bear)
        if bakiye_bear > zirve_bear: zirve_bear = bakiye_bear
        dd_c = (zirve_bear - bakiye_bear) / zirve_bear
        if dd_c > mdd_bear: mdd_bear = dd_c
        
    c_bear = ((bakiye_bear / 100_000.0) ** (252.0 / n_total) - 1.0) * 100
    durum = "YAŞIYOR" if c_bear > 30 else "ÖLDÜ"
    print(f"  300 Seanslık Ağır Kriz Şoku | Bakiye: {bakiye_bear:>12,.0f} TL | CAGR: %{c_bear:>5.2f} | MaxDD: %{-mdd_bear*100:>5.2f} | [{durum}]")
    sonuclar.append(("300 Seans Ağır Ayı", c_bear, -mdd_bear*100, durum))

    print("\n" + "=" * 105)

if __name__ == "__main__":
    run_sabotage_battery()
