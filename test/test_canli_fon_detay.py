import requests
import json

def get_fon_bilgisi(fon_kodu):
    url = "https://www.tefas.gov.tr/api/funds/fonBilgiGetir"
    headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://www.tefas.gov.tr/"}
    try:
        r = requests.post(url, json={"fonKodu": fon_kodu, "dil": "TR"}, headers=headers, timeout=5)
        res = r.json().get("resultList", [])
        return res[0] if res else None
    except Exception as e:
        print("Hata:", e)
        return None

if __name__ == "__main__":
    for f in ["SOS", "MTD", "GPG"]:
        info = get_fon_bilgisi(f)
        if info:
            print(f"=== {f} CANLI VERİSİ ===")
            print(f"  Son Fiyat         : {info['sonFiyat']} TL")
            print(f"  Günlük Getiri     : %{info['gunlukGetiri']}")
            print(f"  Tedavüldeki Pay   : {info['payAdet']:,} Adet")
            print(f"  Fon Toplam Değeri : {info['portBuyukluk']:,.2f} TL")
            print(f"  Yatırımcı Sayısı  : {info['yatirimciSayi']} Kişi")
            print(f"  Kategori Derecesi : {info['kategoriDerece']} / {info['kategoriFonSay']}")
            print(f"  Pazar Payı        : %{info['pazarPayi']}")
            print()
