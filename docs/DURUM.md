# DURUM — REV9 — 2026-09-17
# PO: Eser Göbekli
# Önceki: REV7 (FAZ 6/7/8 kapanış) → REV9 (dashboard + universe + shadow collector + backtest B0.x-B1)

## 1. Proje Özeti

MikoV2 — MEXC Futures (vadeli) kripto trading botu.
- **Stack:** Python 3.10 + asyncio + mp.Queue + Numba + SQLite WAL + Parquet + aiohttp.web
- **Runtime:** Google Cloud VM (e2-micro, Always Free)
- **Process model:** 3x10 WS process + REST gateway single process + supervisor
- **Python sürümü:** VM 3.12, lokal 3.10. Hedef minimum: 3.10 (3.11+ syntax YASAK)

## 2. Tamamlanan Fazlar

| Faz | Kapsam | Durum |
|-----|--------|-------|
| FAZ 0 | Audit (116 YAMA, 245 bulgu) | ✅ Kapandı |
| FAZ 1 | Skeleton + DI (12 dosya) | ✅ |
| FAZ 2 | Data layer + WS manager | ✅ |
| FAZ 3 | Queue + rate limit + pacer | ✅ |
| FAZ 4 | Execution + emergency + storage + risk | ✅ |
| FAZ 5 | Implementation (397 test) | ✅ |
| FAZ 6 | Integration (100 test) | ✅ |
| FAZ 7 | Chaos (61 test) | ✅ |
| FAZ 8 | Shadow (live MEXC) | ✅ |
| FAZ 9 | Dashboard + eksik modüller | ✅ |

## 3. Test Durumu

- **Toplam:** ~700+ test PASS (unit 397 + integration 100 + chaos 61 + son eklemeler)
- **Komut:** `pytest tests/ -q --tb=no`
- **Yakalanan kritik bug'lar:** WS dead silent (pong data maskesi), mp.Queue blocking event loop, DROP_OLDEST→DROP_NEWEST race, 429 circuit breaker eksikliği

## 4. Runtime — VM'de Aktif Olan

**Shadow collector** (`systemctl status miko-collector`)
- `tests/shadow/runner.py` — servis olarak çalışıyor, `Restart=always`
- 3 veri kanalı:
  1. **L2 depth** — `orderbook_snapshots` (60s interval, 500 seviye)
  2. **Trade OHLCV 1s** — `trades_ohlcv_1s` (USDT-normalized, CVD hesabı için)
  3. **Tickers** — `tickers_snapshot` (60s interval, OI + funding)
- **WS data-starvation watchdog** aktif (90s data gelmezse restart)

**Veritabanı:** `~/MikoV2/data/mikov2.sqlite` (WAL mode)

**Dashboard:** `http://<VM_IP>:8090/` (aiohttp.web, 7 endpoint, Chart.js frontend)

## 5. Bugün Eklenen Kritik Modüller

| Modül | Görev |
|-------|-------|
| `src/data_layer/mexc_ws.py` | `sub.depth` + `sub.deal` WS client + starvation watchdog |
| `src/data_layer/mexc_rest.py` | Snapshot + commits + contract_size + ticker + funding |
| `src/data_layer/metrics_fetcher.py` | 1176 sembol bulk filtre + skorlama |
| `src/data_layer/universe_service.py` | Universe scan orkestrasyon |
| `src/storage/mark_price_cache.py` | WS→REST mark price cache |
| `src/storage/equity_tracker.py` | 60s + close-triggered equity snapshot |
| `src/dashboard/app.py` + `routes.py` | aiohttp.web server + 7 endpoint |
| `src/dashboard/static/index.html` | 4 panel + Chart.js + SSE |
| `src/backtest/replay_transport.py` | SQLite 3-tablo merge → chronological stream |
| `src/backtest/engine.py` | Event dispatch engine |
| `src/backtest/signal_detector.py` | SWEEP/MSS/FVG/OTE tespiti (5s candles) |
| `src/backtest/strategy.py` | Sinyalleri entry kararına dönüştürür |
| `src/data_layer/metrics_fetcher.py` | (yukarıda) |

## 6. Universe Scanner Kararı

**Sonuç:** 1176 sembol → 3 aşamalı filtre → Top20

**Aşama 1 (Fatal):** `oi_usd > 1M` + `volume24 > 10M` + `0.3 < spread < 20 bps`
**Aşama 2 (Skor):** volume %40 + OI %30 + funding %30
**Aşama 3 (Limit):** Top5 WS bağlı, Top10 watch, Top20 takip

**Örnek Top5 (2026-09-17):** BTC_USDT, SOL_USDT, XAUT_USDT, XRP_USDT, ONE_USDT

## 7. Açık Sorunlar (FIX bekliyor)

### 7.1 Funding rate aşırı değerler "fırsat" olarak görülüyor

**Sorun:** `ONE_USDT funding=-2%`, `LSK_USDT funding=-0.43%` gibi değerler Top10'a giriyor. Bu **tehlikeli** — muhtemelen likidasyon kaskadı veya exchange-spesifik durum.

**Karar:** Skorlamada aşırı funding CEZA almalı:
#python
f_abs = abs(s.funding_rate)
if f_abs > 0.005:  # 0.5% üstü = ceza
    f_score = -1.0
else:
    f_score = f_abs / 0.005
Durum: Karar alındı, kod FAZ B2c'de güncellenecek.

7.2 Emtia token'ları universe'e sızıyor
Sorun: XAUT_USDT (Tether Gold), SILVER_USDT, UKOIL_USDT, USOIL_USDT, SPCXSTOCK_USDT gibi semboller kripto değil — tokenlaştırılmış emtia/hisse. Whale-radar mantığı bunlarda çalışmaz.

Karar: Exclude listesi eklenecek:

python
EXCLUDED_EXACT = {
    "XAUT_USDT", "XAU_USDT", "XAG_USDT",
    "SILVER_USDT", "GOLD_USDT",
    "UKOIL_USDT", "USOIL_USDT",
    "SPCXSTOCK_USDT",
}
Durum: Karar alındı, kod FAZ B2c'de güncellenecek.

8. Backtest İlerleme
İş	Durum
B1 — ReplayTransport + engine	✅ 68 saat / 3.3 saniye işleme
B2a — Signal detector	✅ 8 test
B2b — Strategy adapter	✅ 9 test
B2c — Position simulator + PnL	⏳ SIRADAKİ
B2d — Backtest runner + rapor	⏳
B2e — Multi-symbol backtest	⏳
Mevcut backtest sonucu (68h veri):

Signal: SWEEP 73, MSS 931, FVG 33, OTE 2313

Entry (300s pencere): 21 adet

Ama 0 PnL ölçümü yok — position simulator yok

9. B2c — Sıradaki İş Detayı
Dosyalar:

src/backtest/position_sim.py — entry → pozisyon açma, TP/SL kontrol, kapanış

tests/unit/test_position_sim.py — 10-12 test

tests/manual/backtest_run.py — güncellenmiş rapor

Karar alınan tasarım:

Max 1 pozisyon per symbol (cluster engellenecek)

Multi-symbol concurrent (BTC long + ETH short aynı anda OK)

max_positions config'ten (TEST=3, PROD=2)

TP/SL exit: 5s OHLCV high/low ile

Fee: taker 0.0002, maker 0.0, leverage-adjusted slippage

Çıktı raporu:

Trade listesi (entry/exit/PnL/R)

Win rate

Avg R-multiple

Max drawdown

Total return

10. Sıradaki 3 Faz
B2c (yarın)
Position simulator + PnL ölçümü

B2d (2 gün sonra)
Backtest runner CLI genişletme:

bash
python -m tests.manual.backtest_run \
  --db data/mikov2.sqlite \
  --symbol BTC_USDT \
  --entry-window-ms 300000 \
  --cooldown-ms 60000 \
  --require-ote \
  --report trades.json
B2e (1 hafta sonra)
Multi-symbol backtest + walk-forward

Tüm Top20 sembolde aynı anda çalış

3 ay train / 1 ay test rolling

11. Prod İçin Sonraki Adımlar (B3)
Universe scanner'ı shadow runner'a bağla (otomatik Top5 rotasyon)

Micro-trigger'ı canlıya al (WS tick → detector → signal → strategy)

Position manager'ı canlıya al (paper trading)

Alert entegrasyonu (Telegram/Discord)

Sigorta: 3-4 hafta paper trading → gerçek para

12. Kritik Kararlar (Kümülatif)
30 coin limit — bilinçli trade-off (100 coin için mimari değişiklik gerek)

30 değil 20 Top — 20 yeterli, top5 zaten işlem yapar

Emtia/hisse exclude — bunlarda whale-radar mantığı çalışmaz

Aşırı funding ceza — |funding| > 0.5% → skor ceza

Contract size cache — bulk detail bir kez çekilir (1176 sembol)

Python 3.10 hedef — 3.11+ syntax YASAK

from .. boşluklu — syntax hatası önleme

f-string log YASAK — %s placeholder

Global state YASAK — DI zorunlu (Y-353)

13. Dosya Konumları
Aktif: docs/rev5/ (AnaYasa + TumModuller — referans)
Arşiv: docs/archive/rev7/ (FAZ 6-7-8 kapanış)
Bu döküman: docs/rev9/
Yeni sohbet başlangıcı: docs/rev9/BAĞLAM.txt

14. UNFROZEN Beyanı
FROZEN YOK

Her satır sorgulanabilir

Yeni YAMA 369+ açık

Blind kabul YASAK