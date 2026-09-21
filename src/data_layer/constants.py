# B2e.-1 §6.2: emtia/hisse token exclude listesi
# SORU O: explicit liste (regex YOK), versiyonlanir; PO kesfettikce genisletir.

EXCLUDED_SYMBOLS_VERSION: int = 1

# DURUM §6.2 kanonik 8 sembol. Yeni sembol eklenirse
# EXCLUDED_SYMBOLS_VERSION arttirilir ve DURUM §6.2 guncellenir.
EXCLUDED_SYMBOLS: frozenset[str] = frozenset({
    "XAUT_USDT",
    "XAU_USDT",
    "XAG_USDT",
    "SILVER_USDT",
    "GOLD_USDT",
    "UKOIL_USDT",
    "USOIL_USDT",
    "SPCXSTOCK_USDT",
})