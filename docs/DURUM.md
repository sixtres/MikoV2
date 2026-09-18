MikoV2 — DURUM
Versiyon: v2.2
Tarih: 2026-09-19
Durum: Backtest veri toplama VM'de aktif. B2c (Position Simulator)
hazirlik asamasindayiz. GitHub checkpoint: 7fb8278 (force-push ile
temizlendi). Protokol sistemi entegre edildi (SOHBET-KAPANIS v2.0).
Amaç: Yeni sohbete baslarken baglami hizlica aktarmak.
PO: Eser Göbekli
Önceki: REV7 (FAZ 6/7/8 kapanis) -> REV9 (dashboard + universe +
shadow collector + backtest B0.x-B1) -> v2.0 (protokol entegrasyonu)
-> v2.1 (BAGLAM.txt entegrasyonu ve kaldirilmasi)
-> v2.2 (arşiv referansi temizligi)

## 0. ÇALISMA YÖNTEMI

MikoV2 — MEXC Futures (vadeli) kripto trading botu. Kagıt-öncelikli
tasarim + test odakli gelistirme.

- Stack: Python 3.10 + asyncio + mp.Queue + Numba + SQLite WAL +
  Parquet + aiohttp.web
- Runtime: Google Cloud VM (e2-micro, Always Free), 7/24.
- Process model: 3x10 WS process + REST gateway single process +
  supervisor.
- Python sürümü: VM 3.12, lokal 3.10. Hedef minimum: 3.10
  (3.11+ syntax YASAK).
- Gelistirme döngüsü: Local'de (Windows/PS) kodlama ve test (pytest),
  VM'de (eser_gobekli@mikov2-collector-1) calistirma.
- **GitHub base URL:** https://github.com/sixtres/MikoV2
  (Dosya isteme protokolü için referans; SOHBET-KAPANIS §6)
- Devir protokolu: SOHBET-KAPANIS-PROTOKOLU.md (v2.0, projeden
  bagimsiz yöntem dökümani). Devir sirasinda bu dosya (DURUM.md)
  güncellenir; protokol sabit kalir.

## 1. TAMAMLANAN FAZLAR

| Faz   | Kapsam                                    | Durum     |
| ----- | ----------------------------------------- | --------- |
| FAZ 0 | Audit (116 YAMA, 245 bulgu)               | Kapandi   |
| FAZ 1 | Skeleton + DI (12 dosya)                  | Kapandi   |
| FAZ 2 | Data layer + WS manager                   | Kapandi   |
| FAZ 3 | Queue + rate limit + pacer                | Kapandi   |
| FAZ 4 | Execution + emergency + storage + risk    | Kapandi   |
| FAZ 5 | Implementation (397 test)                 | Kapandi   |
| FAZ 6 | Integration (100 test)                    | Kapandi   |
| FAZ 7 | Chaos (61 test)                           | Kapandi   |
| FAZ 8 | Shadow (live MEXC)                        | Kapandi   |
| FAZ 9 | Dashboard + eksik moduller                | Kapandi   |

## 2. TEST DURUMU

- Toplam: ~700+ test PASS (unit 397 + integration 100 + chaos 61 +
  son eklemeler).
- Komut: pytest tests/ -q --tb=no
- Yakalanan kritik bug'lar: WS dead silent (pong data maskesi),
  mp.Queue blocking event loop, DROP_OLDEST -> DROP_NEWEST race,
  429 circuit breaker eksikligi.

## 3. RUNTIME — VM'DE AKTIF OLAN

Shadow collector (systemctl status miko-collector):
- tests/shadow/runner.py — servis olarak calisiyor, Restart=always.
- 3 veri kanali:
  1. L2 depth — orderbook_snapshots (60s interval, 500 seviye)
  2. Trade OHLCV 1s — trades_ohlcv_1s (USDT-normalized, CVD için)
  3. Tickers — tickers_snapshot (60s interval, OI + funding)
- WS data-starvation watchdog aktif (90s data gelmezse restart).

Veritabani: ~/MikoV2/data/mikov2.sqlite (WAL mode)
Dashboard: http://<VM_IP>:8090/ (aiohttp.web, 7 endpoint, Chart.js)

## 4. KRITIK MODÜLLER

| Modül                          | Görev                                |
| ------------------------------ | ------------------------------------ |
| src/data_layer/mexc_ws.py      | sub.depth + sub.deal WS + watchdog   |
| src/data_layer/mexc_rest.py    | Snapshot + contract_size + funding   |
| src/data_layer/metrics_fetcher.py | 1176 sembol bulk filtre + skorlama |
| src/data_layer/universe_service.py | Universe scan orkestrasyonu       |
| src/storage/mark_price_cache.py | WS -> REST mark price cache         |
| src/storage/equity_tracker.py  | 60s + close-triggered equity snap    |
| src/dashboard/app.py + routes.py | aiohttp.web server + 7 endpoint    |
| src/dashboard/static/index.html | 4 panel + Chart.js + SSE            |
| src/backtest/replay_transport.py | SQLite 3-tablo merge -> stream     |
| src/backtest/engine.py         | Event dispatch engine                |
| src/backtest/signal_detector.py | SWEEP/MSS/FVG/OTE tespiti (5s)      |
| src/backtest/strategy.py       | Sinyalleri entry kararina dönüstürür |

## 5. UNIVERSE SCANNER KARARI

Sonuç: 1176 sembol -> 3 asamali filtre -> Top20.

- Asama 1 (Fatal): oi_usd > 1M + volume24 > 10M +
  0.3 < spread < 20 bps.
- Asama 2 (Skor): volume %40 + OI %30 + funding %30.
- Asama 3 (Limit): Top5 WS bagli, Top10 watch, Top20 takip.

Örnek Top5 (2026-09-17): BTC_USDT, SOL_USDT, XAUT_USDT, XRP_USDT,
ONE_USDT. Not: XAUT emtia tokeni, §6.2 karar geregi exclude edilecek.

## 6. AÇIK SORUNLAR (FIX bekliyor)

### 6.1 Funding rate asiri degerler "firsat" olarak görülüyor
- Sorun: ONE_USDT funding=-2%, LSK_USDT funding=-0.43% gibi degerler
  Top10'a giriyor. Tehlikeli — muhtemelen likidasyon kaskadi veya
  exchange-spesifik durum.
- Karar: Skorlamada asiri funding CEZA almali:

    f_abs = abs(s.funding_rate)
    if f_abs > 0.005:  # 0.5% üstü = ceza
        f_score = -1.0
    else:
        f_score = f_abs / 0.005

- Durum: Karar alindi, kod FAZ B2c'de güncellenecek.

### 6.2 Emtia token'lari universe'e siziyor
- Sorun: XAUT_USDT (Tether Gold), SILVER_USDT, UKOIL_USDT,
  USOIL_USDT, SPCXSTOCK_USDT gibi semboller kripto degil —
  tokenlastirilmis emtia/hisse. Whale-radar mantigi bunlarda çalismaz.
- Karar: Exclude listesi eklenecek:

    EXCLUDED_EXACT = {
        "XAUT_USDT", "XAU_USDT", "XAG_USDT",
        "SILVER_USDT", "GOLD_USDT",
        "UKOIL_USDT", "USOIL_USDT",
        "SPCXSTOCK_USDT",
    }

- Durum: Karar alindi, kod FAZ B2c'de güncellenecek.

## 7. BACKTEST ILERLEME

| Is                              | Durum                          |
| ------------------------------- | ------------------------------ |
| B1 — ReplayTransport + engine   | Tamamlandi (68 saat / 3.3 sn)  |
| B2a — Signal detector           | Tamamlandi (8 test)            |
| B2b — Strategy adapter          | Tamamlandi (9 test)            |
| B2c — Position simulator + PnL  | SIRADAKI                       |
| B2d — Backtest runner + rapor   | Bekliyor                       |
| B2e — Multi-symbol backtest     | Bekliyor                       |

Mevcut backtest sonucu (68h veri):
- Signal: SWEEP 73, MSS 931, FVG 33, OTE 2313.
- Entry (300s pencere): 21 adet.
- Ama 0 PnL ölçümü yok — position simulator yok.

Not: B2c/B2d için bir deneme dizisi commit'lendi (f714665 ->
6199ae2) ancak güvenilmez bulundu; 2026-09-19'da 7fb8278
checkpoint'ine force-push ile geri dönüldü. B2c sifirdan, temiz
ve test odakli yazilacak. Deneme commit'leri yedek branch'te
tutulabilir (git branch yedek-2026-09-19-b2c-deneme).

## 8. B2c — SIRADAKI IS DETAYI

Dosyalar:
- src/backtest/position_sim.py — entry -> pozisyon açma, TP/SL
  kontrol, kapanis.
- tests/unit/test_position_sim.py — 10-12 test.
- tests/manual/backtest_run.py — güncellenmis rapor.

Karar alinan tasarim:
- Max 1 pozisyon per symbol (cluster engellenecek).
- Multi-symbol concurrent (BTC long + ETH short ayni anda OK).
- max_positions config'ten (TEST=3, PROD=2).
- TP/SL exit: 5s OHLCV high/low ile.
- Fee: taker 0.0002, maker 0.0, leverage-adjusted slippage.

Çikti raporu:
- Trade listesi (entry/exit/PnL/R).
- Win rate.
- Avg R-multiple.
- Max drawdown.
- Total return.

## 9. SIRADAKI FAZLAR

B2c (öncelik): Position simulator + PnL ölçümü.
B2d: Backtest runner CLI genisletme:

    python -m tests.manual.backtest_run \
      --db data/mikov2.sqlite \
      --symbol BTC_USDT \
      --entry-window-ms 300000 \
      --cooldown-ms 60000 \
      --require-ote \
      --report trades.json

B2e: Multi-symbol backtest + walk-forward.
- Tüm Top20 sembolde ayni anda çalis.
- 3 ay train / 1 ay test rolling.

## 10. PROD IÇIN SONRAKI ADIMLAR (B3)

- Universe scanner'i shadow runner'a bagla (otomatik Top5 rotasyon).
- Micro-trigger'i canliya al (WS tick -> detector -> signal -> strategy).
- Position manager'i canliya al (paper trading).
- Alert entegrasyonu (Telegram/Discord).
- Sigorta: 3-4 hafta paper trading -> gerçek para.

## 11. KILITLI KARARLAR (Kümülatif)

Git/checkpoint:
- Güvenilmeyen commit'ler local'de reset, remote'a force-push ile
  silinir. Mevcut checkpoint: 7fb827848aee38897fcea9616d4ea898c294089a
  (REV9 DURUM + BAGLAM, 2026-09-17).
- Protokol = yöntem, DURUM = içerik. Devir sirasinda sadece bu dosya
  güncellenir; SOHBET-KAPANIS-PROTOKOLU.md sabit kalir.

Mimari:
- 30 coin limit — bilinçli trade-off (100 coin için mimari
  degisiklik gerek).
- 30 degil 20 Top — 20 yeterli, top5 zaten islem yapar.
- Emtia/hisse exclude — bunlarda whale-radar mantigi çalismaz.
- Asiri funding ceza — |funding| > 0.5% -> skor ceza.
- Contract size cache — bulk detail bir kez çekilir (1176 sembol).
- Max 1 pozisyon per symbol, multi-symbol concurrent.
- TP/SL exit 5s OHLCV high/low; taker fee 0.0002.

Kod kurallari:
- Python 3.10 hedef — 3.11+ syntax YASAK.
- "from .." bosluklu — syntax hatasi önleme.
- f-string log YASAK — %s placeholder.
- Global state YASAK — DI zorunlu (Y-353).

## 12. DOSYA KONUMLARI

- docs/DURUM.md — bu dosya (proje içerigi, devir noktasi).
- docs/SOHBET-KAPANIS-PROTOKOLU.md — v2.0, projeden bagimsiz yöntem.
- docs/MikoV2-AnaYasa-REV5.md — 116 YAMA, kod kurallari (referans).
- docs/MikoV2-Proje-Tum-Moduller-REV5.md — modül pseudo (referans).

## 13. YENI SOHBET NASIL BASLAR

Verilecek dosyalar:
- DURUM.md (bu, v2.2)
- SOHBET-KAPANIS-PROTOKOLU.md (v2.0)
- MikoV2-AnaYasa-REV5.md
- MikoV2-Proje-Tum-Moduller-REV5.md

Açilis mesaji:
"DURUM.md'yi okudun mu? B2c'ye basla."

Alternatif (bağlam yoğun açılış):
"MikoV2 projesine devam ediyoruz. B2c (Position Simulator)
asamasindayiz. AnaYasa kurallari ve baglam protokolü geçerli.
Ilk isimiz src/backtest/position_sim.py iskeletini kurmak."

## 14. UNFROZEN BEYANI

FROZEN YOK.
Her satir sorgulanabilir.
Yeni YAMA 369+ açik.
Blind kabul YASAK.

SON