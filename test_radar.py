import sys, os
base_dir = os.path.dirname(os.path.abspath(__file__))
os.environ["TELEGRAM_BOT_TOKEN"] = "123456:dummy_token_for_test"
os.environ["TELEGRAM_CHAT_ID"] = "123456"
sys.path.insert(0, base_dir)

from telegram_harmony_bot import get_latest_radar



r = get_latest_radar()
def clean(s):
    return str(s).encode('ascii', 'ignore').decode('ascii')

print("Tarih:", clean(r.get('tarih')))
print("Rejim:", clean(r.get('rejim')))
print("Lider Fon:", clean(r.get('lider_fon')))
print(f"Piyasa Genisligi: %{r.get('breadth'):.1f}")
print(f"Model E Tahsisi: %{r.get('w_pct'):.0f} {clean(r.get('lider_fon'))} + %{r.get('ppz_pct'):.0f} PPZ")
print(f"20G Oynaklik: %{r.get('vol_val'):.1f}")
print("\nTop Siralamasi:")
for item in r.get('top_funds', []):
    print(f"{item.get('sira')}. {clean(item.get('fon'))} | Skor: {item.get('skor'):.3f} | 20G: %{item.get('r20'):+.2f} | 63G: %{item.get('r63'):+.2f}")


