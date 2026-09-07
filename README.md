# 🦅 HARMONY v2.2 - Hunter x Nöbet (Production System)

Bu repo, TEFAS yatırım fonları üzerinde kantitatif momentum, piyasa genişliği (market breadth), tepe takibi (rolling peak) ve **Model E (%20 Target Volatility Risk-Parity)** motorunu çalıştıran 7/24 canlı fon yönetim ve Telegram asistan sistemini içerir.

---

## 📂 Mimari ve Dosya Yapısı

* **`telegram_harmony_bot.py`**: Telegram arayüzü, proaktif sabah raporu (09:55), karar sinyali (10:00) ve canlı portföy muhasebe kontrolü.
* **`harmony_v2_2_live_production.py`**: Model E canlı tahsis motoru (Lider Fon + PPZ Volatilite Kalkanı).
* **`canli_muhasebe_motoru.py`**: Portföy durumu, Takasbank valör hesaplaması ve **%4.50 Kill-Switch** acil durum koruması.
* **`harmony_v2_2_golden.py`**: Model E altın strateji motoru.
* **`meta_allocator_motor.py`**: Meta rejim ve fon seçim motoru.
* **`portfoy_durumu.json`**: Anlık portföy varlıkları, maliyetler ve tepe çekilmesi durumu.
* **`islem_gunlugu.jsonl`**: Gerçekleşen emirlerin değiştirilemez kütüğü.
* **`flow_research/`**: Fon arşivleri, geçmiş getiri ve varlık simülasyonları.
* **`test/`**: Stres testleri, slippage/fakat ve 1 yıllık geriye dönük adli denetim motorları.

---

## 🛡️ Temel Güvenlik Kalkanları

1. **Model E Dinamik Tahsis:** 20 günlük oynaklığa göre dinamik pozisyon boyutlandırma (`clip(0.20 / sigma_20D, 0.40, 1.00)`).
2. **Portföy Kill-Switch (%4.50):** Zirve portföy değerinden %4.50'den fazla çekilme görüldüğünde otomatik olarak pozisyonları dondurur ve PPZ nakit savunması alarmı gönderir.
3. **Valör & Takas Entegrasyonu:** T+1 ve T+2 valör süreçlerini canlı simüle ederek nakit boşluğu oluşmasını engeller.
