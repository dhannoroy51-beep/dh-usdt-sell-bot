import os

# ====== Bot Token & Admin ======
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

# ====== Payment Settings ======
BYBIT_UID = os.getenv("BYBIT_UID")
BEP20_ADDRESS = os.getenv("BEP20_ADDRESS")

# ====== Support & Channel ======
SUPPORT_USERNAME = os.getenv("SUPPORT_USERNAME", "@dhLiveChat_bot")
CHANNEL_LINK = os.getenv("CHANNEL_LINK", "https://t.me/dhusdtsell1")

# ====== Rates ======
RATES = {
    "0.1-0.99": 122,
    "1-1.49": 125,
    "1.5-10": 128
}
MIN_SELL = float(os.getenv("MIN_SELL", "0.1"))
MAX_SELL = float(os.getenv("MAX_SELL", "10"))
DATA_FILE = "orders.json"
