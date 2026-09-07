# FLOW RESEARCH - İZOLE VERİ VE ALFA ARAŞTIRMA MODÜLÜ
# =======================================================
# Bu modül HARMONY v2.2 canlı motorundan TAMAMEN İZOLEDİR.
# Amaç: 2024-2026 dönemi için Tedavüldeki Pay, Fon Toplam Değeri (AUM)
# ve Yatırımcı Sayısı verilerinin adli olarak toplanması, doğrulanması
# ve bağımsız forward-return testlerinin yapılmasıdır.

SCHEMA = {
    "tarih": "YYYY-MM-DD",
    "fon": "FON_KODU",
    "nav": "Birim Fiyat (TL)",
    "tedavuldeki_pay": "Tedavüldeki Katılma Payı Adedi",
    "fon_toplam_degeri": "Portföy / Fon Toplam Büyüklüğü (TL)",
    "yatirimci_sayisi": "Yatırımcı / Kişi Sayısı",
    # Denetim ve Adli Metadata
    "source": "TEFAS | KAP | TAKASBANK",
    "retrieved_at": "ISO-8601 Timestamp",
    "source_timestamp": "Kaynak Güncelleme Zamanı",
    "data_quality": "VERIFIED | ESTIMATED | INCOMPLETE",
    "is_point_in_time": True,
    "raw_hash": "SHA-256 Hash of raw response"
}
