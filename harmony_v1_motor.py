"""
harmony_v1_motor.py
===================
HARMONY v1: Rejim Adaptif Allocator (Fon Nöbetçisi x Hunter v6 x T0 Core)
ve 10 Ayrı Dağıtım Modelinin Yüksek Hızlı Vektörize Simülasyon Motoru (2021 - 2026).
"""

import os
import sys
import json
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Any, Optional

class HarmonyMotor:
    def __init__(
        self,
        baslangic_sermayesi: float = 100_000.0,
        kayma_pct: float = 0.0005,
        siki_entry_nobetci: float = 0.08,
        siki_entry_hunter: float = 0.035,
        min_hold: int = 20,
        replacement_farki_nobetci: float = 0.02,
        replacement_farki_hunter: float = 0.03,
        panic_stop_nobetci: float = -0.05,
        panic_stop_hunter: float = 0.00,
        hunter_dd_freni: float = 0.065
    ):
        self.baslangic_sermayesi = baslangic_sermayesi
        self.kayma_pct = kayma_pct
        self.siki_entry_nobetci = siki_entry_nobetci
        self.siki_entry_hunter = siki_entry_hunter
        self.min_hold = min_hold
        self.replacement_farki_nobetci = replacement_farki_nobetci
        self.replacement_farki_hunter = replacement_farki_hunter
        self.panic_stop_nobetci = panic_stop_nobetci
        self.panic_stop_hunter = panic_stop_hunter
        self.hunter_dd_freni = hunter_dd_freni
        
        # 1. Ortak Fiyat Matrisi
        self.fiyat_df = self._verileri_yukle()
        self.tarihler = self.fiyat_df.index.tolist()
        
        # 2. T0 Core Kasa Getirisi
        self.t0_ret_serisi = self._t0_kasa_getirisi_olustur()
        
        # 3. Vektörize Göstergeleri Önceden Hesapla
        self._vektorize_gostergeleri_hesapla()
        
        # 4. Alt Motorların (SFB ve Hunter) Bağımsız Günlük Bakiye ve Getiri Serilerini Önceden Üret
        self._alt_motorlari_calistir()

    def _verileri_yukle(self) -> pd.DataFrame:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        parent_dir = os.path.dirname(current_dir)
        
        olasi_pivot_yollari = [
            os.path.join(current_dir, "5_yil_pivot.csv"),
            os.path.join(current_dir, "flow_research", "data", "5_yil_pivot.csv"),
            os.path.join(parent_dir, "serbest_fon_bot", "csv", "5_yil_pivot.csv"),
            os.path.join(parent_dir, "serbest_fon_bot", "5_yil_pivot.csv")
        ]
        
        pivot_csv = None
        for p in olasi_pivot_yollari:
            if os.path.exists(p):
                pivot_csv = p
                break
                
        if not pivot_csv:
            raise FileNotFoundError("5_yil_pivot.csv dosyası bulunamadı! Lütfen veri tabanını kontrol edin.")
        
        df_serbest = pd.read_csv(pivot_csv)
        col_t = "date" if "date" in df_serbest.columns else "tarih"
        df_serbest[col_t] = pd.to_datetime(df_serbest[col_t])
        df_serbest.sort_values(col_t, inplace=True)
        df_serbest.drop_duplicates(col_t, inplace=True)
        df_serbest.set_index(col_t, inplace=True)
        df_serbest = df_serbest.apply(pd.to_numeric, errors="coerce")
        
        # Sektör Fonları
        sektor_fonlar = ["TTE", "YZH", "IIH", "MAC", "NRC", "BIO", "GGK", "KZL", "TI3", "TAU"]
        local_c = os.path.join(current_dir, "onbellek")
        sn_c = os.path.join(parent_dir, "t0sniper", "onbellek")
        t0_c = os.path.join(parent_dir, "t0fon", "onbellek")
        sektor_fiyatlar = {}
        for f in sektor_fonlar:
            dosya = os.path.join(local_c, f"fiyatlar_alfa_{f}.json")
            if not os.path.exists(dosya):
                dosya = os.path.join(local_c, f"fiyatlar_3yil_{f}.json")
            if not os.path.exists(dosya):
                dosya = os.path.join(sn_c, f"fiyatlar_alfa_{f}.json")
            if not os.path.exists(dosya):
                dosya = os.path.join(t0_c, f"fiyatlar_3yil_{f}.json")
            if os.path.exists(dosya):
                try:
                    with open(dosya, "r", encoding="utf-8") as file:
                        data = json.load(file)
                    df_f = pd.DataFrame(data)
                    if not df_f.empty and "tarih" in df_f.columns and "fiyat" in df_f.columns:
                        df_f["tarih"] = pd.to_datetime(df_f["tarih"])
                        df_f["fiyat"] = pd.to_numeric(df_f["fiyat"], errors="coerce")
                        df_f = df_f[df_f["fiyat"] > 0].sort_values("tarih").drop_duplicates("tarih")
                        df_f.set_index("tarih", inplace=True)
                        sektor_fiyatlar[f] = df_f["fiyat"]
                except Exception:
                    pass
                    
        df_sektor = pd.DataFrame(sektor_fiyatlar)
        df_birlesik = pd.concat([df_serbest, df_sektor], axis=1)
        df_birlesik = df_birlesik.loc[:, ~df_birlesik.columns.duplicated()]
        df_birlesik.sort_index(inplace=True)
        df_birlesik.ffill(inplace=True)
        return df_birlesik

    def _t0_kasa_getirisi_olustur(self) -> pd.Series:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        parent_dir = os.path.dirname(current_dir)
        local_c = os.path.join(current_dir, "onbellek")
        t0_c = os.path.join(parent_dir, "t0fon", "onbellek")
        t0_fonlar = ["PPZ", "PRY", "TP2", "PNU"]
        t0_fiyatlar = {}
        for k in t0_fonlar:
            dosya = os.path.join(local_c, f"fiyatlar_3yil_{k}.json")
            if not os.path.exists(dosya):
                dosya = os.path.join(t0_c, f"fiyatlar_3yil_{k}.json")
            if os.path.exists(dosya):
                try:
                    with open(dosya, "r", encoding="utf-8") as file:
                        data = json.load(file)
                    df_k = pd.DataFrame(data)
                    if not df_k.empty and "tarih" in df_k.columns and "fiyat" in df_k.columns:
                        df_k["tarih"] = pd.to_datetime(df_k["tarih"])
                        df_k["fiyat"] = pd.to_numeric(df_k["fiyat"], errors="coerce")
                        df_k = df_k[df_k["fiyat"] > 0].sort_values("tarih").drop_duplicates("tarih")
                        df_k.set_index("tarih", inplace=True)
                        t0_fiyatlar[k] = df_k["fiyat"]
                except Exception:
                    pass
        df_t0 = pd.DataFrame(t0_fiyatlar)

        df_t0.sort_index(inplace=True)
        df_t0.ffill(inplace=True)
        
        t0_ret = pd.Series(index=self.fiyat_df.index, dtype=float)
        ppz_pivot = self.fiyat_df["PPZ"] if "PPZ" in self.fiyat_df.columns else None
        
        for idx in range(len(self.fiyat_df)):
            dt = self.fiyat_df.index[idx]
            if idx == 0:
                t0_ret.iloc[idx] = 0.0008
                continue
            dt_prev = self.fiyat_df.index[idx - 1]
            
            if dt in df_t0.index and dt_prev in df_t0.index:
                rets = (df_t0.loc[dt] - df_t0.loc[dt_prev]) / df_t0.loc[dt_prev]
                rets = rets.dropna()
                valid = rets[(rets >= 0) & (rets <= 0.0035)]
                if not valid.empty:
                    t0_ret.iloc[idx] = float(valid.max())
                    continue
                    
            if ppz_pivot is not None:
                p_cur = ppz_pivot.iloc[idx]
                p_prev = ppz_pivot.iloc[idx - 1]
                if p_prev > 0 and p_cur > 0:
                    ret_ppz = (p_cur - p_prev) / p_prev
                    t0_ret.iloc[idx] = max(0.0, float(ret_ppz))
                else:
                    t0_ret.iloc[idx] = 0.0008
            else:
                t0_ret.iloc[idx] = 0.0008
                
        t0_ret.fillna(0.0008, inplace=True)
        return t0_ret

    def _vektorize_gostergeleri_hesapla(self):
        fon_cols = [c for c in self.fiyat_df.columns if c not in ["PPZ", "date", "tarih"]]
        fiyatlar = self.fiyat_df[fon_cols]
        
        # Günlük gerçekleşen getiri (dt gününün kapanışından gelen getiri)
        self.gunluk_ret_df = fiyatlar.pct_change(1).fillna(0.0)
        
        # STRICT T-1 LAG: Tüm sinyal ve göstergeler 1 gün önceki resmi kapanışa göre hesaplanır
        shifted_fiyatlar = fiyatlar.shift(1)
        self.r20_df = shifted_fiyatlar.pct_change(20)
        self.r40_df = shifted_fiyatlar.pct_change(40)
        self.r63_df = shifted_fiyatlar.pct_change(63)
        
        r21_df = self.r20_df
        self.skor_df = (r21_df * 0.40) + (self.r63_df * 0.30) + (self.r20_df * 0.20) + ((r21_df - self.r63_df / 3.0) * 0.10)
        
        self.gunluk_sampiyon_fon = {}
        self.gunluk_sampiyon_skor = {}
        self.gunluk_sampiyon_r20 = {}
        self.rejim_serisi = {}
        self.market_breadth = {}
        self.top5_avg_r20 = {}
        
        for dt, row in self.skor_df.iterrows():
            valid_scores = row.dropna()
            if not valid_scores.empty:
                best_fon = valid_scores.idxmax()
                best_skor = valid_scores.max()
                best_r20 = self.r20_df.at[dt, best_fon] if pd.notna(self.r20_df.at[dt, best_fon]) else 0.0
                
                self.gunluk_sampiyon_fon[dt] = best_fon
                self.gunluk_sampiyon_skor[dt] = best_skor
                self.gunluk_sampiyon_r20[dt] = best_r20
                
                r20_row = self.r20_df.loc[dt].dropna()
                pozitif_oran = float((r20_row > 0).mean()) if not r20_row.empty else 0.0
                top5_avg = float(r20_row.nlargest(5).mean()) if not r20_row.empty else 0.0
                
                self.market_breadth[dt] = pozitif_oran
                self.top5_avg_r20[dt] = top5_avg
                
                if pozitif_oran >= 0.50 and top5_avg >= 0.06:
                    self.rejim_serisi[dt] = "BULL"
                elif pozitif_oran <= 0.25 or top5_avg <= 0.015:
                    self.rejim_serisi[dt] = "BEAR"
                else:
                    self.rejim_serisi[dt] = "NEUTRAL"
            else:
                self.gunluk_sampiyon_fon[dt] = None
                self.gunluk_sampiyon_skor[dt] = -999.0
                self.gunluk_sampiyon_r20[dt] = 0.0
                self.market_breadth[dt] = 0.0
                self.top5_avg_r20[dt] = 0.0
                self.rejim_serisi[dt] = "NEUTRAL"


    def _alt_motorlari_calistir(self):
        """
        SFB ve Hunter alt motorlarının 1257 günlük saf bakiye ve getiri dizilerini üretir.
        """
        tarih_dilimi = self.tarihler[65:]
        
        # 1. SFB Saf Motoru
        sfb_sermaye = 100_000.0
        sfb_fon = "PPZ"
        sfb_elde_gun = 0
        sfb_takas_bekleyen = 0.0
        sfb_takas_kalan = 0
        self.sfb_gunluk_ret = {}
        self.sfb_aktif_fon = {}
        self.sfb_islem_sayisi = 0
        
        for dt in tarih_dilimi:
            ret_t0 = self.t0_ret_serisi.loc[dt]
            sampiyon = self.gunluk_sampiyon_fon[dt]
            sampiyon_skor = self.gunluk_sampiyon_skor[dt]
            sampiyon_r20 = self.gunluk_sampiyon_r20[dt]
            
            if sfb_fon == "PPZ":
                if sampiyon is not None and sampiyon_r20 >= self.siki_entry_nobetci:
                    karar = "AL"
                    hedef = sampiyon
                else:
                    karar = "KAL"
                    hedef = "PPZ"
            else:
                cur_r20 = self.r20_df.at[dt, sfb_fon] if pd.notna(self.r20_df.at[dt, sfb_fon]) else 0.0
                cur_r40 = self.r40_df.at[dt, sfb_fon] if pd.notna(self.r40_df.at[dt, sfb_fon]) else 0.0
                cur_skor = self.skor_df.at[dt, sfb_fon] if pd.notna(self.skor_df.at[dt, sfb_fon]) else 0.0
                if cur_r20 <= self.panic_stop_nobetci:
                    karar = "NAKITE_GEC"
                    hedef = "PPZ"
                elif sampiyon is not None and sampiyon != sfb_fon:
                    yoruldu = (cur_r20 < cur_r40)
                    fark = 0.0 if yoruldu else self.replacement_farki_nobetci
                    if sampiyon_skor > (cur_skor + fark) and sfb_elde_gun >= self.min_hold:
                        karar = "DEGISTIR"
                        hedef = sampiyon
                    else:
                        karar = "KAL"
                        hedef = sfb_fon
                else:
                    karar = "KAL"
                    hedef = sfb_fon
                    
            if karar == "NAKITE_GEC" and sfb_fon != "PPZ":
                sfb_sermaye *= (1.0 - self.kayma_pct)
                sfb_takas_bekleyen = sfb_sermaye
                sfb_takas_kalan = 1
                sfb_fon = "PPZ"
                sfb_elde_gun = 0
                self.sfb_islem_sayisi += 1
            elif karar == "DEGISTIR" and sfb_fon != "PPZ":
                sfb_sermaye *= (1.0 - self.kayma_pct)
                sfb_takas_bekleyen = sfb_sermaye
                sfb_takas_kalan = 1
                sfb_fon = hedef
                sfb_elde_gun = 1
                self.sfb_islem_sayisi += 1
            elif karar == "AL" and sfb_fon == "PPZ" and sfb_takas_kalan == 0:
                sfb_sermaye *= (1.0 - self.kayma_pct)
                sfb_fon = hedef
                sfb_elde_gun = 1
                self.sfb_islem_sayisi += 1
            elif sfb_fon != "PPZ":
                sfb_elde_gun += 1
                
            if sfb_takas_kalan > 0:
                serbest = sfb_sermaye - sfb_takas_bekleyen
                yeni_sermaye = serbest * (1 + ret_t0) + sfb_takas_bekleyen
                g_ret = (yeni_sermaye - sfb_sermaye) / sfb_sermaye
                sfb_sermaye = yeni_sermaye
                sfb_takas_kalan -= 1
                if sfb_takas_kalan == 0:
                    sfb_takas_bekleyen = 0.0
            elif sfb_fon != "PPZ":
                ret_f = self.gunluk_ret_df.at[dt, sfb_fon] if sfb_fon in self.gunluk_ret_df.columns and pd.notna(self.gunluk_ret_df.at[dt, sfb_fon]) else 0.0
                sfb_sermaye *= (1 + ret_f)
                g_ret = ret_f
            else:
                sfb_sermaye *= (1 + ret_t0)
                g_ret = ret_t0
                
            self.sfb_gunluk_ret[dt] = g_ret
            self.sfb_aktif_fon[dt] = sfb_fon

        # 2. Hunter v6 Saf Motoru
        h6_sermaye = 100_000.0
        h6_zirve = 100_000.0
        h6_fon = "PPZ"
        h6_elde_gun = 0
        h6_takas_bekleyen = 0.0
        h6_takas_kalan = 0
        self.h6_gunluk_ret = {}
        self.h6_aktif_fon = {}
        self.h6_islem_sayisi = 0
        
        for dt in tarih_dilimi:
            ret_t0 = self.t0_ret_serisi.loc[dt]
            sampiyon = self.gunluk_sampiyon_fon[dt]
            sampiyon_skor = self.gunluk_sampiyon_skor[dt]
            sampiyon_r20 = self.gunluk_sampiyon_r20[dt]
            
            if h6_sermaye > h6_zirve:
                h6_zirve = h6_sermaye
            cur_dd = (h6_zirve - h6_sermaye) / (h6_zirve + 1e-8)
            
            if h6_fon == "PPZ":
                if sampiyon is not None and sampiyon_r20 >= self.siki_entry_hunter and cur_dd < self.hunter_dd_freni:
                    karar = "AL"
                    hedef = sampiyon
                else:
                    karar = "T0_CORE"
                    hedef = "PPZ"
            else:
                cur_r20 = self.r20_df.at[dt, h6_fon] if pd.notna(self.r20_df.at[dt, h6_fon]) else 0.0
                cur_r40 = self.r40_df.at[dt, h6_fon] if pd.notna(self.r40_df.at[dt, h6_fon]) else 0.0
                cur_skor = self.skor_df.at[dt, h6_fon] if pd.notna(self.skor_df.at[dt, h6_fon]) else 0.0
                
                if (cur_r20 <= self.panic_stop_hunter) or (cur_dd >= self.hunter_dd_freni):
                    karar = "SAT_T0"
                    hedef = "PPZ"
                elif sampiyon is not None and sampiyon != h6_fon:
                    yoruldu = (cur_r20 < cur_r40)
                    fark = 0.0 if yoruldu else self.replacement_farki_hunter
                    if sampiyon_skor > (cur_skor + fark) and h6_elde_gun >= self.min_hold:
                        karar = "ROTASYON"
                        hedef = sampiyon
                    else:
                        karar = "TUT"
                        hedef = h6_fon
                else:
                    karar = "TUT"
                    hedef = h6_fon
                    
            if karar in ["SAT_T0", "T0_CORE"] and h6_fon != "PPZ":
                h6_sermaye *= (1.0 - self.kayma_pct)
                h6_takas_bekleyen = h6_sermaye
                h6_takas_kalan = 1
                h6_fon = "PPZ"
                h6_elde_gun = 0
                self.h6_islem_sayisi += 1
            elif karar == "ROTASYON" and h6_fon != "PPZ":
                h6_sermaye *= (1.0 - self.kayma_pct)
                h6_takas_bekleyen = h6_sermaye
                h6_takas_kalan = 1
                h6_fon = hedef
                h6_elde_gun = 1
                self.h6_islem_sayisi += 1
            elif karar == "AL" and h6_fon == "PPZ" and h6_takas_kalan == 0:
                h6_sermaye *= (1.0 - self.kayma_pct)
                h6_fon = hedef
                h6_elde_gun = 1
                self.h6_islem_sayisi += 1
            elif h6_fon != "PPZ":
                h6_elde_gun += 1
                
            if h6_takas_kalan > 0:
                serbest = h6_sermaye - h6_takas_bekleyen
                yeni_sermaye = serbest * (1 + ret_t0) + h6_takas_bekleyen
                g_ret = (yeni_sermaye - h6_sermaye) / h6_sermaye
                h6_sermaye = yeni_sermaye
                h6_takas_kalan -= 1
                if h6_takas_kalan == 0:
                    h6_takas_bekleyen = 0.0
            elif h6_fon != "PPZ":
                ret_f = self.gunluk_ret_df.at[dt, h6_fon] if h6_fon in self.gunluk_ret_df.columns and pd.notna(self.gunluk_ret_df.at[dt, h6_fon]) else 0.0
                h6_sermaye *= (1 + ret_f)
                g_ret = ret_f
            else:
                h6_sermaye *= (1 + ret_t0)
                g_ret = ret_t0
                
            self.h6_gunluk_ret[dt] = g_ret
            self.h6_aktif_fon[dt] = h6_fon

    def simule_et_model(
        self,
        model_kodu: str,
        baslangic_tarihi: Optional[str] = None,
        bitis_tarihi: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        10 Modelin Simülasyonu:
        1. 'saf_hunter'
        2. 'sabit_25_75'
        3. 'sabit_50_50'
        4. 'sabit_75_25'
        5. 'saf_nobetci'
        6. 'rejim_dinamik'
        7. 'momentum_spread'
        8. 'risk_paritesi'
        9. 'harmony_v1'
        10. 'dd_aware_switching'
        """
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
        
        sermaye = self.baslangic_sermayesi
        zirve = self.baslangic_sermayesi
        gunluk_kayitlar = []
        t0_agirlik_toplami = 0.0
        
        gun_500k = None
        tarih_500k = None
        gun_700k = None
        tarih_700k = None
        
        # Volatilite takibi için geçmiş getiriler
        sfb_ret_hist = []
        h6_ret_hist = []
        
        for idx, dt in enumerate(tarih_dilimi):
            r_sfb = self.sfb_gunluk_ret[dt]
            r_h6 = self.h6_gunluk_ret[dt]
            r_t0 = self.t0_ret_serisi.loc[dt]
            
            sfb_ret_hist.append(r_sfb)
            h6_ret_hist.append(r_h6)
            
            rejim = self.rejim_serisi.get(dt, "NEUTRAL")
            breadth = self.market_breadth.get(dt, 0.0)
            top5_r20 = self.top5_avg_r20.get(dt, 0.0)
            
            if sermaye > zirve:
                zirve = sermaye
            cur_dd = (zirve - sermaye) / (zirve + 1e-8)
            
            # --- 10 MODELİN AĞIRLIK DAĞILIMI (w_sfb, w_h6, w_t0) ---
            if model_kodu == "saf_hunter":
                w_sfb, w_h6, w_t0 = 0.0, 1.0, 0.0
            elif model_kodu == "sabit_25_75":
                w_sfb, w_h6, w_t0 = 0.25, 0.75, 0.0
            elif model_kodu == "sabit_50_50":
                w_sfb, w_h6, w_t0 = 0.50, 0.50, 0.0
            elif model_kodu == "sabit_75_25":
                w_sfb, w_h6, w_t0 = 0.75, 0.25, 0.0
            elif model_kodu == "saf_nobetci":
                w_sfb, w_h6, w_t0 = 1.0, 0.0, 0.0
                
            elif model_kodu == "rejim_dinamik":
                if rejim == "BULL":
                    w_sfb, w_h6, w_t0 = 0.70, 0.30, 0.0
                elif rejim == "NEUTRAL":
                    w_sfb, w_h6, w_t0 = 0.30, 0.70, 0.0
                else:  # BEAR
                    w_sfb, w_h6, w_t0 = 0.0, 0.0, 1.0
                    
            elif model_kodu == "momentum_spread":
                # SFB lider ivmesi ile Hunter lider ivmesi farkı
                f_sfb = self.sfb_aktif_fon.get(dt, "PPZ")
                f_h6 = self.h6_aktif_fon.get(dt, "PPZ")
                r20_s = self.r20_df.at[dt, f_sfb] if f_sfb in self.r20_df.columns and pd.notna(self.r20_df.at[dt, f_sfb]) else 0.0
                r20_h = self.r20_df.at[dt, f_h6] if f_h6 in self.r20_df.columns and pd.notna(self.r20_df.at[dt, f_h6]) else 0.0
                
                spread = r20_s - r20_h
                if spread >= 0.03:
                    w_sfb, w_h6, w_t0 = 0.75, 0.25, 0.0
                elif spread <= -0.03:
                    w_sfb, w_h6, w_t0 = 0.15, 0.85, 0.0
                else:
                    w_sfb, w_h6, w_t0 = 0.40, 0.60, 0.0
                    
            elif model_kodu == "risk_paritesi":
                # Son 20 günlük volatilite ters orantısı
                k20_s = sfb_ret_hist[-20:]
                k20_h = h6_ret_hist[-20:]
                vol_s = np.std(k20_s, ddof=1) if len(k20_s) > 1 else 0.01
                vol_h = np.std(k20_h, ddof=1) if len(k20_h) > 1 else 0.01
                vol_s = max(0.002, vol_s)
                vol_h = max(0.002, vol_h)
                
                inv_s = 1.0 / vol_s
                inv_h = 1.0 / vol_h
                tot_inv = inv_s + inv_h
                w_sfb = float(inv_s / tot_inv)
                w_h6 = float(inv_h / tot_inv)
                w_t0 = 0.0
                
            elif model_kodu == "harmony_v1":
                # HARMONY v1: Rejim Adaptif Üçlü Model
                # 1. Çift Motor Rallisi: Piyasa çok güçlü, hem SFB hem Hunter fonları yükselişte
                # 2. Güçlü SFB Rejimi: Serbest fon patlaması, breadth yüksek
                # 3. Güçlü Hunter Rejimi: Sektör/Emtia veya T0 trendi
                # 4. Kararsız/Riskli: Market breadth çöküşü veya BEAR
                if rejim == "BEAR" or (breadth <= 0.25 and top5_r20 <= 0.02):
                    w_sfb, w_h6, w_t0 = 0.0, 0.0, 1.0  # %100 Güvenli T0 Core Kasa
                elif breadth >= 0.55 and top5_r20 >= 0.08:
                    w_sfb, w_h6, w_t0 = 0.40, 0.60, 0.0  # Çift Motorlu Agresif Ralli
                elif breadth >= 0.45:
                    w_sfb, w_h6, w_t0 = 0.75, 0.25, 0.0  # Güçlü SFB Alfa Rejimi
                else:
                    w_sfb, w_h6, w_t0 = 0.10, 0.90, 0.0  # Güçlü Hunter Savunma/Emtia Rejimi
                    
            elif model_kodu == "dd_aware_switching":
                # Drawdown-Aware Dynamic Switching
                if cur_dd >= 0.065:
                    w_sfb, w_h6, w_t0 = 0.0, 0.0, 1.0  # %100 Acil Fren (T0 Core)
                elif cur_dd >= 0.045:
                    w_sfb, w_h6, w_t0 = 0.15, 0.25, 0.60 # Kademeli Defans
                elif cur_dd >= 0.025:
                    w_sfb, w_h6, w_t0 = 0.25, 0.45, 0.30 # Erken Uyarı
                else:
                    w_sfb, w_h6, w_t0 = 0.40, 0.60, 0.00 # Normal Büyüme
            else:
                w_sfb, w_h6, w_t0 = 0.50, 0.50, 0.0
                
            # Günlük Getiri
            gunluk_ret = (w_sfb * r_sfb) + (w_h6 * r_h6) + (w_t0 * r_t0)
            sermaye *= (1 + gunluk_ret)
            
            # Gerçek T0 Süresi (Alt motorların içindeki T0/PPZ oranlarını da hesaba katar)
            sfb_f = self.sfb_aktif_fon.get(dt, "PPZ")
            h6_f = self.h6_aktif_fon.get(dt, "PPZ")
            eff_t0 = w_t0 + (w_sfb if sfb_f == "PPZ" else 0.0) + (w_h6 if h6_f == "PPZ" else 0.0)
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
                "w_sfb": w_sfb,
                "w_h6": w_h6,
                "w_t0": w_t0,
                "rejim": rejim
            })
            
        vals = np.array([k["bakiye"] for k in gunluk_kayitlar])
        n_days = len(vals)
        toplam_ret = (vals[-1] - self.baslangic_sermayesi) / self.baslangic_sermayesi * 100.0
        cagr = ((vals[-1] / self.baslangic_sermayesi) ** (252 / n_days) - 1) * 100.0 if n_days > 0 else 0.0
        kum_max = np.maximum.accumulate(vals)
        dd = (vals - kum_max) / (kum_max + 1e-8)
        mdd_pct = float(np.min(dd)) * 100.0
        max_tl_kayip = float(np.max(kum_max - vals))
        
        # Calmar, Sharpe, Sortino
        calmar = cagr / abs(mdd_pct) if abs(mdd_pct) > 1e-4 else 0.0
        gunluk_rets = np.diff(vals) / vals[:-1]
        
        rf_daily = (1 + 0.45) ** (1 / 252) - 1
        sharpe = float(np.mean(gunluk_rets - rf_daily) / (np.std(gunluk_rets, ddof=1) + 1e-8) * np.sqrt(252)) if len(gunluk_rets) > 1 else 0.0
        
        neg_rets = gunluk_rets[gunluk_rets < rf_daily] - rf_daily
        downside_std = np.std(neg_rets, ddof=1) if len(neg_rets) > 1 else 0.001
        sortino = float(np.mean(gunluk_rets - rf_daily) / (downside_std + 1e-8) * np.sqrt(252)) if len(gunluk_rets) > 1 else 0.0
        
        # En Uzun Drawdown Süresi (Max DD Duration)
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
        
        # Yıllık Getiriler
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
        
        # Tahmini toplam işlem sayısı
        islem_est = int(self.sfb_islem_sayisi * np.mean([k['w_sfb'] for k in gunluk_kayitlar]) + 
                        self.h6_islem_sayisi * np.mean([k['w_h6'] for k in gunluk_kayitlar]) + 15)
        
        return {
            "model_kodu": model_kodu,
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
            "toplam_islem": islem_est,
            "t0_sure_pct": round(t0_pct, 1),
            "gun_500k": f"{gun_500k}. Gün ({tarih_500k})" if gun_500k else "Ulaşılmadı",
            "gun_700k": f"{gun_700k}. Gün ({tarih_700k})" if gun_700k else "Ulaşılmadı",
            "gunluk_kayitlar": gunluk_kayitlar
        }
