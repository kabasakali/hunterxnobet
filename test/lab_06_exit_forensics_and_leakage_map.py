"""
test/lab_06_exit_forensics_and_leakage_map.py
=============================================
LAB-06: ADLİ ÇIKIŞ VE KAYIP ALFA ANALİZİ (EXIT FORENSICS & MISSED ALPHA AUDIT)

Amaç:
LAB-E (%64.67 CAGR / -%25 MaxDD) modelinin 5.7 yıllık dönemde yaptığı tüm işlem
ve pozisyonları adli mikroskop altına alarak parayı NEREDE, NE KADAR ve NEDEN
bıraktığını kuruşu kuruşuna haritalandırmak.

Denetlenen 5 Kayıp Kaynağı:
1. Valör Fırsat Maliyeti (T+1/T+2 Takas beklerken kaçan alfa)
2. Kayma & Komisyon Sürtünmesi (İşlem başına %0.05 maliyet)
3. Hatalı / Erken Geçişler (Eski motor sonraki 10-20 günde daha iyi miydi?)
4. Tek Lider Kısıtı (Top-1 yerine Top-2 taşınsaydı ne olurdu?)
5. Savunma Nakit Maliyeti (PPZ'de boşuna beklenen günler vs hayat kurtaran günler)
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

class ExitForensicsEngine:
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

    def run_forensic_audit(self) -> dict:
        tarih_dilimi = self.tarihler[65:]
        sermaye = self.baslangic_sermayesi
        rolling_window = []
        
        aktif_motor = "HUNTER"
        motor_elde_gun = 0
        savunma_modu = False
        takas_kalan_gun = 0
        
        gecis_loglari = []
        gunluk_kayitlar = []
        
        # Sürtünme ve Fırsat Maliyeti Havuzları (TL)
        toplam_kayma_maliyeti_tl = 0.0
        toplam_valor_firsat_kaybi_tl = 0.0
        toplam_valor_firsat_kazanci_tl = 0.0
        
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
                
            asgari_sure = 5 if aktif_motor == "DD_AWARE" else 3
            acil_fren = (hedef_motor == "DD_AWARE" and local_dd >= 0.045)
            hizli_cikis = (aktif_motor == "DD_AWARE" and breadth >= 0.48 and spread >= 0.025)
            
            # Geçiş İcrası
            if hedef_motor != aktif_motor and takas_kalan_gun == 0:
                if motor_elde_gun >= asgari_sure or acil_fren or hizli_cikis:
                    kayma_tl = sermaye * self.kayma_pct
                    toplam_kayma_maliyeti_tl += kayma_tl
                    sermaye -= kayma_tl
                    
                    val_satis = 2 if aktif_motor == "MOMENTUM" else 1
                    takas_kalan_gun = val_satis
                    
                    gecis_kaydi = {
                        "gecis_idx": len(gecis_loglari) + 1,
                        "tarih": dt,
                        "tarih_str": dt.strftime("%Y-%m-%d"),
                        "t_eksi_1": tarih_dilimi[idx-1].strftime("%Y-%m-%d") if idx > 0 else dt.strftime("%Y-%m-%d"),
                        "eski_motor": aktif_motor,
                        "yeni_motor": hedef_motor,
                        "bakiye_tl": sermaye,
                        "kayma_tl": kayma_tl,
                        "val_gun": val_satis,
                        "breadth": breadth,
                        "top5": top5,
                        "local_dd": local_dd,
                        "idx_in_series": idx
                    }
                    gecis_loglari.append(gecis_kaydi)
                    
                    aktif_motor = hedef_motor
                    motor_elde_gun = 1
                else:
                    motor_elde_gun += 1
            else:
                motor_elde_gun += 1
                
            # Günlük Getiri ve Valör Fırsat Maliyeti
            if takas_kalan_gun > 0:
                # Hedef motor o gün ne kazandırırdı?
                hedef_r = rh if aktif_motor == "HUNTER" else (rm if aktif_motor == "MOMENTUM" else rdd)
                valor_farki = (rt0 - hedef_r) * sermaye
                if valor_farki < 0:
                    toplam_valor_firsat_kaybi_tl += abs(valor_farki)
                else:
                    toplam_valor_firsat_kazanci_tl += valor_farki
                    
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
                "savunma_modu": savunma_modu,
                "gunluk_ret": g_ret,
                "rh": rh,
                "rm": rm,
                "rdd": rdd,
                "rt0": rt0,
                "breadth": breadth,
                "top5": top5
            })
            
        df = pd.DataFrame(gunluk_kayitlar).set_index("tarih")
        
        # ─────────────────────────────────────────────────────────────────────
        # ADLİ DERİN ANALİZ 1: GEÇİŞ KALİTESİ (Sonraki 10-20 Günlük Performans)
        # ─────────────────────────────────────────────────────────────────────
        basarili_gecisler = 0
        hatali_gecisler = 0
        toplam_hatali_gecis_kaybi_tl = 0.0
        
        for g in gecis_loglari:
            i = g["idx_in_series"]
            eski = g["eski_motor"]
            yeni = g["yeni_motor"]
            
            # Sonraki 10 iş günü penceresi
            i_son = min(i + 10, len(df))
            if i_son > i:
                sub_df = df.iloc[i:i_son]
                if yeni == "HUNTER":
                    yeni_ret = (1 + sub_df["rh"]).prod() - 1
                elif yeni == "MOMENTUM":
                    yeni_ret = (1 + sub_df["rm"]).prod() - 1
                else:
                    yeni_ret = (1 + sub_df["rdd"]).prod() - 1
                    
                if eski == "HUNTER":
                    eski_ret = (1 + sub_df["rh"]).prod() - 1
                elif eski == "MOMENTUM":
                    eski_ret = (1 + sub_df["rm"]).prod() - 1
                else:
                    eski_ret = (1 + sub_df["rdd"]).prod() - 1
                    
                alfa_farki = yeni_ret - eski_ret
                g["alfa_10g_pct"] = alfa_farki * 100.0
                g["alfa_10g_tl"] = alfa_farki * g["bakiye_tl"]
                
                if alfa_farki >= 0:
                    basarili_gecisler += 1
                else:
                    hatali_gecisler += 1
                    toplam_hatali_gecis_kaybi_tl += abs(g["alfa_10g_tl"])
                    
        # ─────────────────────────────────────────────────────────────────────
        # ADLİ DERİN ANALİZ 2: SAVUNMA NAKİT DÖNGÜSÜ AYRIŞTIRMASI
        # ─────────────────────────────────────────────────────────────────────
        # PPZ'de kalınan günleri ikiye ayırıyoruz:
        # a) Hayat kurtaran günler (Hunter/Momentum o gün eksi yazmışken PPZ artı yazdı)
        # b) Fırsat kaçan günler (Hunter/Momentum o gün PPZ'den daha çok kazandırdı)
        hayat_kurtaran_gunler = 0
        hayat_kurtaran_tl = 0.0
        firsat_kacan_gunler = 0
        firsat_kacan_tl = 0.0
        
        ppz_rows = df[df["aktif_motor"] == "DD_AWARE"]
        for _, row in ppz_rows.iterrows():
            potansiyel_riskli = max(row["rh"], row["rm"])
            gercek_ppz = row["rt0"]
            fark_tl = (potansiyel_riskli - gercek_ppz) * row["bakiye"]
            
            if potansiyel_riskli < 0:
                hayat_kurtaran_gunler += 1
                hayat_kurtaran_tl += abs((0 - potansiyel_riskli) * row["bakiye"])
            elif potansiyel_riskli > gercek_ppz:
                firsat_kacan_gunler += 1
                firsat_kacan_tl += fark_tl
                
        return {
            "son_bakiye": sermaye,
            "gecis_sayisi": len(gecis_loglari),
            "gecis_loglari": gecis_loglari,
            "toplam_kayma_maliyeti_tl": toplam_kayma_maliyeti_tl,
            "toplam_valor_firsat_kaybi_tl": toplam_valor_firsat_kaybi_tl,
            "toplam_valor_firsat_kazanci_tl": toplam_valor_firsat_kazanci_tl,
            "net_valor_kaybi_tl": toplam_valor_firsat_kaybi_tl - toplam_valor_firsat_kazanci_tl,
            "basarili_gecisler": basarili_gecisler,
            "hatali_gecisler": hatali_gecisler,
            "toplam_hatali_gecis_kaybi_tl": toplam_hatali_gecis_kaybi_tl,
            "hayat_kurtaran_gunler": hayat_kurtaran_gunler,
            "hayat_kurtaran_tl": hayat_kurtaran_tl,
            "firsat_kacan_gunler": firsat_kacan_gunler,
            "firsat_kacan_tl": firsat_kacan_tl,
            "df": df
        }

def run_forensic_report():
    engine = ExitForensicsEngine()
    audit = engine.run_forensic_audit()
    
    print("=" * 105)
    print("LAB-06: ADLI CIKIS VE KAYIP ALFA HARITASI (EXIT FORENSICS & MISSED ALPHA AUDIT)")
    print("=" * 105)
    
    print(f"Nihai Portfoy Sermayesi (100k Baslangic): {audit['son_bakiye']:,.2f} TL (CAGR: %64.67)")
    print(f"Toplam Gerceklesen Gecis Sayisi         : {audit['gecis_sayisi']} Gecis")
    print("-" * 105)
    
    print("\n1. SURTUNME VE VALOR MALIYETI OTOPSISI:")
    print(f"  • Toplam Komisyon / Kayma Maliyeti    : -{audit['toplam_kayma_maliyeti_tl']:,.2f} TL")
    print(f"  • Valorde Beklerken Kacirilan Alfa    : -{audit['toplam_valor_firsat_kaybi_tl']:,.2f} TL")
    print(f"  • Valorde Beklerken Saglanan Koruma   : +{audit['toplam_valor_firsat_kazanci_tl']:,.2f} TL (Dususten Korunma)")
    print(f"  • Net Valor Firsat Maliyeti           : -{audit['net_valor_kaybi_tl']:,.2f} TL")
    
    print("\n2. MOTOR GECIS KALITESI (10 GUNLUK TAKIP):")
    toplam_g = audit['basarili_gecisler'] + audit['hatali_gecisler']
    basari_pct = (audit['basarili_gecisler'] / toplam_g * 100) if toplam_g > 0 else 0
    print(f"  • Basarili Gecisler (Daha Cok Kazandiran) : {audit['basarili_gecisler']} / {toplam_g} (%{basari_pct:.1f})")
    print(f"  • Hatali / Erken Gecisler (Whipsaw/Testere): {audit['hatali_gecisler']} / {toplam_g} (%{100 - basari_pct:.1f})")
    print(f"  • Hatali Gecislerin Toplam Firsat Kaybi   : -{audit['toplam_hatali_gecis_kaybi_tl']:,.2f} TL")
    
    print("\n3. SAVUNMA (PPZ) NAKIT DONGUSU OTOPSISI:")
    print(f"  • Hayat Kurtaran Gunler (Dususten Kacilan): {audit['hayat_kurtaran_gunler']} gun (+{audit['hayat_kurtaran_tl']:,.2f} TL Portfoy Korundu)")
    print(f"  • Firsat Kacan Gunler (Piyasayi Kaciran)  : {audit['firsat_kacan_gunler']} gun (-{audit['firsat_kacan_tl']:,.2f} TL Firsat Maliyeti)")
    
    print("\n" + "=" * 105)
    print("EN BUYUK 5 KAYIP GEÇİŞİN (HATALI/ERKEN ÇIKIŞ) DETAYI:")
    print("=" * 105)
    print(f"{'Tarih':<12} | {'Eski -> Yeni':<22} | {'Sermaye':<14} | {'10G Alfa Kaybi':<18} | {'Neden'}")
    print("-" * 105)
    
    gecisler_sorted = sorted(audit["gecis_loglari"], key=lambda x: x.get("alfa_10g_tl", 0))
    for g in gecisler_sorted[:5]:
        kayip_str = f"-{abs(g.get('alfa_10g_tl', 0)):,.2f} TL (%{g.get('alfa_10g_pct', 0):.1f})"
        neden = "Erken Savunma" if g["yeni_motor"] == "DD_AWARE" else "MOM Yanilgi"
        print(f"{g['tarih_str']:<12} | {g['eski_motor'] + ' -> ' + g['yeni_motor']:<22} | {g['bakiye_tl']:<12,.0f} TL | {kayip_str:<18} | {neden}")
        
    print("=" * 105)

if __name__ == "__main__":
    run_forensic_report()
