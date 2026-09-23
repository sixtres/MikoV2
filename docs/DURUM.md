MikoV2 — DURUM
Versiyon: v2.18
Tarih: 2026-09-23
Durum: B3.3 kapandı. Paper position manager canlı canlı paper trading
       aktif (MicroTrigger TRIGGER -> PaperPositionManager.on_entry
       -> TP/SL/END exit; SQLite paper_positions + paper_events
       kalıcı). SORU B3.3-A/B/C/D/E/F kilitli (§11). 914 PASS
       (+7 runner integration; toplam yeni B3.3 = 30 + 7 = 37).
       Tek commit B3.3 kapanışında atılacak. PROTOKOL.md v3.3
       yürürlükte.
Sıradaki: B3.4 — Alert entegrasyonu (Telegram/Discord).
          SORU SS=C sırası: B3.4 → B3.5.
Amaç: Yeni sohbete başlarken bağlamı hızlıca aktarmak.
PO: Eser Göbekli
Önceki: REV7 (FAZ 6/7/8 kapanış) → REV9 (dashboard + universe + shadow
collector + backtest B0.x-B1) → v2.0 (protokol entegrasyonu) → v2.1
(BAGLAM.txt entegrasyonu) → v2.2 (arşiv referansı temizliği) → v2.3
(B1/B2a/B2b doğrulama + DB transfer) → v2.4 (B2c öncesi analiz + SWEEP
yön fix) → v2.5 (protokol entegrasyonu) → v2.6 (SSOT temizliği) → v2.7
(B2c başlangıç kriterleri kilitlendi) → v2.8 (B2c kapanış + SORU G/H +
async telemetry notu) → v2.9 (B2d kapanış: reporting.py + --config-a/b +
--equity-csv; 750 PASS) → v2.10 (B2e planı kilitli: SORU A′–W; kod
BAŞLAMADI) → v2.11 (B2e.−1 + B2e.0 kapandı; 783 PASS; SORU X açıldı) →
v2.12 (B2e tüm alt fazlar kapandı; 842 PASS; CLI --mode single|multi|
walkforward + --data-quality-profile; multi_report.py G′ şeması) →
v2.13 (B3.1 plan Mod 1'de onaylandı; SORU A–G kilitli) → v2.14 (B3.1
kapandı: mexc_ws dinamik sub; universe_service rotation Q1–Q5; runner
çok-sembol; iki timer; watch REST ticker; per-symbol watchdog;
856 PASS + 1 bilinen transient FAIL; §6.8 yeni ihlal notu) → v2.15
(B3.2 planı Mod 1'de onaylandı; SORU B3.2-A/B/C/D/E kilitlendi) →
v2.16 (protokol dökümanı geçişi: SOHBET-KAPANIS-PROTOKOLU.md v2.6 →
PROTOKOL.md v3.3) → v2.17 (B3.2 kapandı: MicroTrigger canlı +
Strategy shadow + per-symbol quarantine; 877 PASS; SORU B3.2-C
telemetry revize; SSOT temizliği) → v2.18 (B3.3 kapandı: paper
position manager canlı; paper_positions + paper_events kalıcı;
src/trading/paper_math.py ortak math çekirdeği; 914 PASS; §12
manager.py → order_manager.py bayat atıf düzeltmesi)

0. ÇALIŞMA YÖNTEMİ
MikoV2 — MEXC Futures (vadeli) kripto trading botu. Kağıt-öncelikli
tasarım + test odaklı geliştirme.
Stack: Python 3.10 + asyncio + mp.Queue + Numba + SQLite WAL + Parquet
+ aiohttp.web
Runtime: Google Cloud VM (e2-micro, Always Free), 7/24.
Process model: 3x10 WS process + REST gateway single process +
supervisor.
Python sürümü: Bkz AnaYasa REV5 §0. VARSAYIM: AnaYasa Python 3.11
diyor, ancak runtime 3.10 hedefli ve 3.11+ syntax yasaklı. PO onayı
gerekiyor.
Geliştirme döngüsü: Local'de (Windows/PS) kodlama ve test (pytest),
VM'de (eser_gobekli@mikov2-collector-1) çalıştırma.
GitHub base URL: https://github.com/sixtres/MikoV2 (dosya isteme
protokolü için referans).
DB yolu (VM): /home/eser_gobekli/MikoV2/data/mikov2.sqlite
DB şeması: orderbook_snapshots (id PK), trades_ohlcv_1s (sec PK),
tickers_snapshot (id PK), paper_positions (position_id PK),
paper_events (id PK)
Kod kuralları: Bkz AnaYasa REV5 §0.

VM'DEN LOCAL'E DOSYA TRANSFERİ (BAĞLAYICI)
Google Cloud Console web SSH terminalinde scp çalışmıyor. Kullanılan
yöntem:
    VM'de dosyayı sıkıştır: tar -czf dosya.tar.gz dosya
    curl -F "file=@dosya.tar.gz" https://tmpfiles.org/api/v1/upload
    Dönen URL'ye /dl/ ekle, tarayıcıdan indir.
    Local'de tar -xzf dosya.tar.gz ile aç.
Not: transfer.sh, 0x0.st kapalı/kısıtlı (2026-09-19 itibariyle).

1. TAMAMLANAN FAZLAR
| Faz|Kapsam|Durum|
| ---|---|---|
| FAZ 0|Audit (116 YAMA, 245 bulgu)|Kapandı|
| FAZ 1|Skeleton + DI (12 dosya)|Kapandı|
| FAZ 2|Data layer + WS manager|Kapandı|
| FAZ 3|Queue + rate limit + pacer|Kapandı|
| FAZ 4|Execution + emergency + storage + risk|Kapandı|
| FAZ 5|Implementation (397 test)|Kapandı|
| FAZ 6|Integration (100 test)|Kapandı|
| FAZ 7|Chaos (61 test)|Kapandı|
| FAZ 8|Shadow (live MEXC)|Kapandı|
| FAZ 9|Dashboard + eksik modüller|Kapandı|
| B2c|Position simulator + PnL (16 test)|Kapandı|
| B2d|Backtest raporlama (17 test)|Kapandı|
| B2e.−1|§6.1 funding ceza + §6.2 emtia exclude (15 test)|Kapandı|
| B2e.0|Multi-symbol altyapı (18 test)|Kapandı|
| B2e.1|Interleaved runner (11 test)|Kapandı|
| B2e.1S|Synthetic multi-symbol validation (8 test)|Kapandı|
| B2e.2|Walk-forward (11 test)|Kapandı|
| B2e.2S|Synthetic walk-forward (4 test)|Kapandı|
| B2e.3|Rapor (G′ şeması + profiller + CLI) (24 test)|Kapandı|
| B2e kapanış|Tek commit|Kapandı (2026-09-22)|
| B3.1|Çok-sembol kolektör (Top5 WS + Top10 watch)|Kapandı (2026-09-22)|
| B3.2|Micro-trigger canlı + Strategy shadow + quarantine|Kapandı (2026-09-23)|
| B3.3|Position manager paper (canlı canlı paper trading)|Kapandı (2026-09-23)|
| B2e.real|Gerçek çok sembol gate (S′)|Veri birikimine bağlı (≥30 gün)|
| B3.4|Alert entegrasyonu (Telegram/Discord)|Sırada|
| B3.5|Sigorta: 3-4 hafta paper → gerçek para|Sırada|

2. TEST DURUMU
Toplam: 914 PASS.
Alt faz dağılımı: B2d 17; B2e.−1 15; B2e.0 18; B2e.1 11; B2e.1S 8;
B2e.2 11; B2e.2S 4; B2e.3 24; B3.1 15 (8 unit + 7 integration);
B3.2 20 (13 micro_trigger + 7 runner integration); B3.3 37
(17 paper_math + 13 paper_manager + 7 runner integration).
§7.7.2 karşılaştırması: 877 (B3.2) → 907 (delivery 1: +30) →
907 (delivery 2: 0) → 914 (delivery 3: +7). Tüm farklar yeni
dosya kaynaklı.
Komut: pytest tests/ -q --tb=short --maxfail=1
Bilinen transient FAIL (tests/chaos/test_queue_full.py:168) B3.3
koşusunda gözlenmedi. §6.3'te belgelenen mp.Queue feeder timing
kaynaklı; izlenmeye devam.
Yakalanan kritik bug'lar: WS dead silent (pong data maskesi), mp.Queue
blocking event loop, DROP_OLDEST -> DROP_NEWEST race, 429 circuit
breaker eksikliği, SWEEP yön mapping tersliği (Bkz §7), SORU G/H
slippage/SL floor (B2c, Bkz §7), B2e.0 `PositionSimulator.finalize`
imza değişikliği sonrası `backtest_run.py` çağrısı kırıldı (B2e.3'te
düzeltildi), B3.1 adım 1 `...` işaretleyicisi kaynaklı `__init__`
attribute kaybı (Bkz §6.8), B3.2 test mock async/sync karışıklığı
(Bkz §6.9), B3.3 test 5s kova kapanış sınırı (sec_after+1 → +5;
kaynak değişmedi; kayıt §6.11'de).

3. RUNTIME — VM'DE AKTİF OLAN
Shadow collector (systemctl status miko-collector):
tests/shadow/runner.py — servis olarak çalışıyor, Restart=always.
3 veri kanalı:
L2 depth — orderbook_snapshots (60s interval, 500 seviye)
Trade OHLCV 1s — trades_ohlcv_1s (USDT-normalized, CVD için)
Tickers — tickers_snapshot (60s interval, OI + funding)
WS data-starvation watchdog aktif (90s data gelmezse restart).
B3.2: MicroTrigger canlı (5s evaluate) + shadow Strategy paralel.
B3.3: PaperPositionManager canlı (paper trading). paper_positions +
paper_events tabloları WAL üzerinden aynı DB'ye yazılır.
Veritabanı: Bkz §0 (WAL mode).
Dashboard: http://<VM_IP>:8090/ (aiohttp.web, 7 endpoint, Chart.js)
Not: Kolektör şu an tek sembol (BTC_USDT). Çok-sembol genişleme B3.1
Mod 2'de kod olarak hazır; VM'de aktivasyon `--enable-rotation`
flag'ine bağlı; aktivasyon kararı B3.2 öncesi PO onayına tabi.

DB MEVCUT DURUM (2026-09-21):
- trades_ohlcv_1s: BTC_USDT tek sembol, 332216 satır, span 347517 sn
  (~97.8h).
- orderbook_snapshots: 8729 satır / 8729 distinct timestamp_ms
  (duplicate yok; beklenen ~5868 → %149, 60s'den sık yazılmış).
- tickers_snapshot: 4621 satır BTC_USDT (60s beklenen ~5868, %79).
- OHLCV veri kalitesi: 423 gap, max gap 14572 sn (~4.05h), toplam
  15297 sn eksik, completeness ≈ %95.6.

4. KRİTİK MODÜLLER
| Modül|Görev|
| ---|---|
| src/data_layer/mexc_ws.py|sub.depth + sub.deal WS + watchdog; B3.1: dinamik subscribe/unsubscribe/subscribed_symbols|
| src/data_layer/mexc_rest.py|Snapshot + contract_size + funding|
| src/data_layer/metrics_fetcher.py|1176 sembol bulk filtre + skorlama (§6.1 funding ceza; excluded_symbols DI)|
| src/data_layer/universe_service.py|Universe scan orkestrasyonu (§6.2 exclude + ScanResult.excluded_symbols); B3.1: RotationDecision + hysteresis + flap (round-trip) + üstel quarantine + 7 gün stabil reset|
| src/data_layer/l2_buffer.py|Çok-sembol L2 book buffer (L2Book per symbol)|
| src/data_layer/constants.py|EXCLUDED_SYMBOLS + EXCLUDED_SYMBOLS_VERSION (§6.2 kanonik liste)|
| src/storage/mark_price_cache.py|WS -> REST mark price cache|
| src/storage/equity_tracker.py|60s + close-triggered equity snap|
| src/dashboard/app.py + routes.py|aiohttp.web server (Bkz §3: URL + endpoint)|
| src/dashboard/static/index.html|4 panel + Chart.js + SSE|
| src/backtest/replay_transport.py|SQLite 3-tablo merge -> stream; stream_multi; collect_ohlcv_secs / collect_ticker_secs / collect_depth_secs (B2e.3 coverage)|
| src/backtest/engine.py|Event dispatch engine|
| src/backtest/signal_detector.py|SWEEP/MSS/FVG/OTE tespiti (5s)|
| src/backtest/strategy.py|Sinyalleri entry kararına dönüştürür; SORU X — last_rejection_reason (additive)|
| src/backtest/position_sim.py|B2c entry/TP/SL + PnL; B2e.0 per-symbol state + finalize dict + MTM; SORU N — window_id/fold_id|
| src/backtest/multi_symbol_runner.py|B2e.1 MultiSymbolRunner (interleaved); B2e.2 WalkForwardRunner + WalkForwardConfig + FoldWindow + FoldResult + WalkForwardResult|
| src/backtest/multi_report.py|B2e.3 — G′ rapor şeması; SCHEMA_VERSION=1; CLAIM_* enum; build_report saf fonksiyon; data_quality{profile, by_symbol, aggregate}; dropped_entries_by_reason/by_symbol (SORU A3); excluded_symbols{all, effective, version} (SORU BB′)|ateşledi|
| src/backtest/reporting.py|B2d — genişletilmiş rapor (Sharpe, PF, expectancy, equity curve)|
| src/backtest/data_quality.py|B2e.0 — gap/completeness detection; B2e.3 — ticker/depth coverage da bu fonksiyonla (SORU XX)|
| tests/shadow/runner.py|Shadow collector — B3.1: çok-sembol state + iki timer (30s scan / 5dk WS rotasyon) + watch REST ticker + per-symbol watchdog + Top5→Top4 uyarı + --enable-rotation. B3.2: MicroTrigger canlı (5s evaluate) + shadow Strategy paralel + TRIGGER → EntrySignal JSON log + per-symbol quarantine skip + _init_symbol_state (rotasyon tetikler). B3.3: PaperPositionManager bağlaması (on_ws_tick, on_ohlcv, on_ticker, TRIGGER → on_entry, A.3 current_position_qty geri besleme, on_startup rehydration, finalize)|
| src/features/micro_trigger.py|Per-symbol MicroTrigger state machine (IDLE->SWEEP->MSS->FVG_OTE->MICRO_CONFIRM->TRIGGER); paused_ms, hard deadline 600s, quarantine, next_candle, per-symbol asyncio.Lock. B3.2: quarantine_until_ms + is_quarantined() + quarantine(symbol, reason) + MICRO_TRIGGER_QUARANTINE event|
| src/trading/paper_math.py|B3.3 — ortak math çekirdeği (saf fonksiyonlar); backtest ve paper manager paylaşır. entry slippage, SL/TP mesafesi, qty, fee, R, ATR, funding delta, next_funding_ts_ms|
| src/execution/paper_position_manager.py|B3.3 — PaperPositionManager (canlı paper trading). on_entry (global asyncio.Lock + stale_price + ATR guard); on_ohlcv (5s kova exit; SL önce; entry_bucket_sec atlanır); on_ws_tick (last_price freshness); on_ticker (funding); on_startup (DB rehydration); finalize (END_OF_BACKTEST); SQLite paper_positions + paper_events (UNIQUE idempotency); get_open_position_qty (A.3)|
| tests/manual/backtest_run.py|Backtest CLI: --symbol (single); --symbols + --mode (multi|walkforward); --train-ms/--test-ms/--step-ms; --data-quality-profile (legacy|lenient|strict); --config-a/b; --equity-csv; --report|

5. UNIVERSE SCANNER KARARI
Sonuç: 1176 sembol -> 3 aşamalı filtre -> Top20 (operasyonel limit;
mimari üst sınır 30 coin için Bkz §11).
Aşama 1 (Fatal): oi_usd > 1M + volume24 > 10M + 0.3 < spread < 20 bps.
Aşama 2 (Skor): volume %40 + OI %30 + funding %30. Funding skoru:
|f|>0.005 ceza (-1.0); aksi |f|/0.005 (B2e.−1).
Aşama 3 (Limit): Top5 WS bağlı, Top10 watch, Top20 takip.
Exclude: EXCLUDED_SYMBOLS (constants.py, §6.2) skorlama ve
normalizasyondan önce uygulanır.
Örnek Top5 (2026-09-17): BTC_USDT, SOL_USDT, XAUT_USDT, XRP_USDT,
ONE_USDT. Not: XAUT artık exclude (§6.2).

6. AÇIK SORUNLAR
6.1 Funding rate aşırı değerler "fırsat" olarak görülüyor
Sorun: ONE_USDT funding=-2%, LSK_USDT funding=-0.43% gibi değerler
Top10'a giriyor. Tehlikeli — muhtemelen likidasyon kaskadı veya
exchange-spesifik durum.
Karar: Skorlamada aşırı funding CEZA almalı:
    f_abs = abs(s.funding_rate)
    if f_abs > 0.005:  # 0.5% üstü = ceza
        f_score = -1.0
    else:
        f_score = f_abs / 0.005
Durum: UYGULANDI (B2e.−1). Test: tests/unit/test_b2e_minus1_compliance.py.

6.2 Emtia token'ları universe'e sızıyor
Sorun: XAUT_USDT (Tether Gold), SILVER_USDT, UKOIL_USDT, USOIL_USDT,
SPCXSTOCK_USDT gibi semboller kripto değil — tokenlaştırılmış
emtia/hisse. Whale-radar mantığı bunlarda çalışmaz.
Karar: Exclude listesi (kanonik, versiyonlu):
    src/data_layer/constants.py
    EXCLUDED_SYMBOLS_VERSION = 1
    EXCLUDED_SYMBOLS = frozenset({
        "XAUT_USDT", "XAU_USDT", "XAG_USDT",
        "SILVER_USDT", "GOLD_USDT",
        "UKOIL_USDT", "USOIL_USDT",
        "SPCXSTOCK_USDT",
    })
Uygulama: BulkMetricsFetcher candidate loop (normalizasyondan önce) +
UniverseService ScanResult.excluded_symbols. Regex YOK (SORU O).
Durum: UYGULANDI (B2e.−1).

6.3 async_telemetry_queue _bridge_loop DROP_NEWEST sapması
Sorun: threaded_bridge=True yolunda mp_queue.put queue.Full dönerse,
item deque(maxlen) başına appendleft edilirken deque sağdan (en yeni)
eleman tahliye eder. DROP_OLDEST semantiği dar bir yarış penceresinde
DROP_NEWEST davranışına sapar.
Etki alanı: Sadece threaded_bridge=True (production default). Testler
threaded_bridge=False kullandığı için bu yol test kapsamı dışı.
Karar: FAZ sonrası — B2c/B2d/B2e/B3 kapsamı dışı, ayrı commit.
Doğrulama: KOD İNCELEME (2026-09-20).
Durum: Not edildi, FAZ sonrasına bırakıldı. B3.2 ve B3.3 koşularında
transient FAIL gözlenmedi.

6.4 SORU X — K′′ diagnostics (KAPANDI)
Karar: (A) — Strategy + PositionSimulator'a additive
last_rejection_reason alanı; cooldown_active / per_symbol_max_position
/ global_limit_full reason'ları set edilir.
Durum: KAPANDI (B2e.1, 2026-09-21).

6.5 B2e kapanış commit'i
Sorun: B2e plan kararları PO kısıtı gereği tek final commit istiyordu.
Durum: KAPANDI — tek commit atıldı (2026-09-22).

6.6 PROTOKOL İHLALİ NOTU (2026-09-22)
Asistan, dış-ajan prompt mesajında PROTOKOL.md §7.1 ihlali yaptı: çıktı
bloğu (4-backtick prompt) checklist'ten ÖNCE verildi. §7.1 "checklist
kodun/dökümanın üstünde" der; §7.3 format örneği aynı sırayı ima eder.
PO ihlali fark etti; asistan kabul etti; çıktı doğru sırayla yeniden
verildi. Protokol hatası DEĞİL; asistan sıralama hatası. Kayıt amacıyla
not edildi. (§10.1 — Mod 1, PO yazdı.)

6.7 Proje dosya seti (SSOT)
Proje dosya seti: DURUM.md + PROTOKOL.md +
MikoV2-AnaYasa-REV5.md (ANAYASA rolü) + MikoV2-Proje-Tum-
Moduller-REV5.md (mimari referans, opsiyonel).
PROTOKOL.md sabittir; devir sırasında güncellenmez.
Durum: UYGULANDI.

6.8 PROTOKOL İHLALİ NOTU (2026-09-22, B3.1 Mod 2)
Asistan, B3.1 adım 1 mexc_ws.py tesliminde "Yeni hali" patch bloğunda
`...` işaretleyicisi kullandı. PO patch'i literal uyguladığı için
MEXCWSClient.__init__ içindeki 6 attribute ataması (on_depth, url,
ping_interval_s, dead_timeout_s, _read_task, _ping_task) düştü; 7 test
FAIL (test_mexc_ws 4, test_ws_ping_timeout 3). Asistan hatayı kabul
etti; mexc_ws.py tam dosya olarak yeniden teslim edildi. Ders: kısmi
patch'te `...` yerine gerçek satırlar yazılmalı veya tam dosya
verilmeli. (§10.1 — Mod 1, asistan.)

6.9 PROTOKOL İHLALİ NOTU (2026-09-23, B3.2 Mod 2)
Asistan, B3.2 runner integration test tesliminde `test_on_ohlcv_1s_
feeds_detector_to_recent_signals` içinde `feed_ohlcv_1s` mock'unu
yanlışlıkla `async def` yazdı; kaynak metod senkron olduğundan
`TypeError: 'coroutine' object is not iterable` FAIL üretti. Asistan
hatayı kabul etti; mock senkron `def`'e çevrildi. Ders: mock imzası
hedef metodun senkron/async niteliğiyle bire bir eşleşmeli. (§10.1 —
Mod 1, asistan.)

6.10 PROTOKOL İHLALİ NOTU (2026-09-23, B3.2 Mod 2)
Asistan, test mock düzeltmesi tesliminde "Eski hali" bloğundan önce
dosya yolunu yazmadı (§7.6.2 ihlali). §6.8'deki eski PO kararını
§7.6.2 ile çelişkili sanıp §6.8'i üstün tuttu; oysa §7.6.2 zaten
düzeltilmişti ve sahibi PROTOKOL'dü. Bağlam güncellenmedi. Kayıt
için not edildi. (§10.1 — Mod 1, asistan.)

6.11 PROTOKOL İHLALİ NOTU (2026-09-23, B3.3 Mod 2)
Asistan, B3.3 delivery 1 test düzeltmesinde 4 ayrı test
fonksiyonundan parça parça "eski/yeni" bloğu verdi ve aralara
başlık yorumları koydu; PO eski halini dosyada bulamadı (§7.6.2
ihlali — patch bağlamı ve indent karışıklığı). Asistan hatayı
kabul etti; düzeltme tam dosya olarak yeniden teslim edildi
(delivery 1 revize). Ders: çoklu küçük patch yerine tek tam
dosya tercih edilmeli; başlık yorumları eski/yeni bloklarına
gömülmemeli. Kaynak koda dokunulmadı; yalnız test sınırı
düzeltildi. (§10.1 — Mod 1, asistan.)

7. BACKTEST İLERLEME
| İş|Durum|
| ---|---|
| B1 — ReplayTransport + engine|Doğrulandı (97.8 saat / 4.08s)|
| B2a — Signal detector|Doğrulandı (8 sinyal tipi)|
| B2b — Strategy adapter|Doğrulandı (SWEEP yön bug'ı fix'lendi)|
| B2c — Position simulator + PnL|Kapandı (16 test)|
| B2d — Backtest runner + rapor|Kapandı (17 test)|
| B2e.−1 — §6.1/§6.2 compliance|Kapandı (15 test)|
| B2e.0 — Multi-symbol altyapı|Kapandı (18 test)|
| B2e.1 — Interleaved runner|Kapandı (11 test)|
| B2e.1S — Synthetic multi-symbol|Kapandı (8 test)|
| B2e.2 — Walk-forward|Kapandı (11 test)|
| B2e.2S — Synthetic walk-forward|Kapandı (4 test)|
| B2e.3 — Rapor (G′/N/diagnostics)|Kapandı (24 test)|
| B2e kapanış — Tek commit|Kapandı (2026-09-22)|
| B3.1 — Çok-sembol kolektör|Kapandı (2026-09-22)|
| B3.2 — Micro-trigger canlı + Strategy shadow|Kapandı (2026-09-23)|
| B3.3 — Paper position manager|Kapandı (2026-09-23)|
| B2e.real — Gerçek çok sembol gate (S′)|Veri birikimine bağlı (≥30 gün)|

B3.3 kapsamı (kapandı): ShadowRunner'a PaperPositionManager
entegrasyonu; on_ws_tick (best bid/ask mid) her depth push'unda;
on_ohlcv her tamamlanan 1s OHLCV'de (paper içeride 5s kova birleştirir);
on_ticker funding güncellemesinde; MicroTrigger TRIGGER transition'da
on_entry (global asyncio.Lock; stale_price_ms=5000; ATR guard);
on_ohlcv 5s kova kapanışında exit kontrolü (SL önce; entry_bucket_sec
atlanır); on_startup ile DB'deki OPEN paper pozisyonlar in-memory'ye
yüklenir; finalize ile END_OF_BACKTEST exit; SQLite paper_positions +
paper_events (UNIQUE(position_id, event_type, source_seq) idempotency);
config izlenebilirliği (config_profile_tag, risk_pct,
max_positions_global/per_symbol, initial_equity, entry_slippage_bps).

CLI örnek kullanımı:
    # Single
    python -m tests.manual.backtest_run --db data/mikov2.sqlite \
        --symbol BTC_USDT --entry-window-ms 300000 --cooldown-ms 60000 \
        --report b2e3_single.json
    # Walk-forward
    python -m tests.manual.backtest_run --db data/mikov2.sqlite \
        --mode walkforward --symbols BTC_USDT \
        --train-ms 172800000 --test-ms 86400000 \
        --report wf_b2e3.json
    # Strict profil (fail-fast)
    python -m tests.manual.backtest_run --db data/mikov2.sqlite \
        --symbol BTC_USDT --data-quality-profile strict \
        --report should_fail.json
    # Shadow (B3.1 çok-sembol + rotation + B3.2 micro-trigger +
    # B3.3 paper manager)
    python -m tests.shadow.runner --symbols BTC_USDT,SOL_USDT \
        --db data/mikov2.sqlite --enable-rotation

B2e.3 çıktı örnekleri (BTC_USDT 97.8h, 2026-09-21):
- single mode → 44 trade, -%17.98; data_quality.aggregate.completeness
  ≈ 0.956; ticker_coverage ≈ %79; depth_coverage distinct ≈ %100
  (raw %149 — collector_rate_anomaly=True); walk_forward_claim =
  capable.
- walkforward mode (train=48h, test=24h) → 2 fold, 2 combined trade,
  1 combined drop; walk_forward_claim = single_symbol_real.
- strict profil → RuntimeError:
  'strict_violated:completeness=0.9152,max_gap_ms=14572000'.

B2c SONRASI ANALİZ (2026-09-20, BTC_USDT, 97.8 saat):
187 entry → 44 tamamlanan trade. 9 TP / 34 SL / 1 END_OF_BACKTEST.
win_rate = %20.45. avg_r_multiple = -0.3761. max_drawdown_pct =
%20.08. total_return_pct = -%17.98. Funding etkisi ≈ 0 USDT.
BULGU: Bu örneklemde strateji kârlı değil. Breakeven %33.3; ölçülen
%20.45 altında.
YORUM: Sample size küçük (44 trade), tek rejim, tek sembol. B2e
sonuçları: tek sembol walk-forward 2 fold, 2 trade, hepsi SL —
örneklem çok küçük; B3.1 çok-sembol kolektör ile veri birikince
B2e.real gate karar verecek.

B2c SORU G/H:
SORU G: (C) min_sl_distance_pct=0.002 floor.
SORU H: (A) entry_slippage_bps=2.0.

B2d SONUÇLARI (kilitli):
SORU A: (B) §6.1/§6.2 B2d'de uygulanmadı → v2.10'da SORU A′ ile revize.
SORU B: (A) --config-a / --config-b; tek --report JSON'unda config_a +
config_b + comparison.
SORU C: (B) Equity curve JSON + CSV (--equity-csv); PNG yok.
Yeni dosya: src/backtest/reporting.py.

8. B2e — FAZ KIRILIMI VE DURUM
TÜM ALT FAZLAR KAPANDI (2026-09-22):
- B2e.−1: §6.1 + §6.2 compliance (15 test).
- B2e.0: Altyapı (18 test).
- B2e.1: Multi-symbol davranış — MultiSymbolRunner (11 test).
- B2e.1S: Synthetic multi-symbol validation (8 test).
- B2e.2: Walk-forward — WalkForwardRunner (11 test).
- B2e.2S: Synthetic walk-forward (4 test).
- B2e.3: Rapor (24 test).
- B2e kapanış: Tek commit atıldı.
- B2e.real: Gerçek çok sembol gate (S′) — veri birikimine bağlı.

Commit politikası: PO kısıtı gereği B2e tek final commit. Yeni
fazlarda (B3.1, B3.2, B3.3) yine tek commit.

9. SIRADAKİ FAZLAR
B3.4 (Mod 2 sırada) → B3.5 → B2e.real (S′ gate, 30 gün veri
birikiminden sonra otomatik değerlendirme).
B3.4 sonrası: alert entegrasyonu tamamlanmadan gerçek para kararı
verilmez (SORU SS=C). B3.5: 3-4 hafta paper trading sonrası sigorta.
Strateji parametre optimizasyonu B2e.real sonuçlarına göre; kârlılık
negatif kalırsa öncelik strateji adayı iterasyonuna kayar (B3
gerçek-para adımı bloklanır).

10. PROD İÇİN SONRAKİ ADIMLAR (B3)
SORU SS (C) sırası:
B3.1 — Çok-sembol kolektör: Top5 WS bağlı (tam depth + OHLCV +
ticker), Top10 watch. Universe scanner mevcut (Top20); rotasyonda
WS abonelik güncellenir. Hysteresis 5m/flap 3 yumuşatıcı. e2-micro
CPU/RAM/DB ilk hafta izlenir; aşılırsa Top5→Top4 daralması S′ ≥4
koşuluyla uyumlu. (KAPANDI 2026-09-22.)
B3.2 — Micro-trigger canlı (WS tick -> detector -> signal ->
strategy). (KAPANDI 2026-09-23.)
B3.3 — Position manager paper (canlı canlı paper trading).
(KAPANDI 2026-09-23.)
B3.4 — Alert entegrasyonu (Telegram/Discord). MicroTrigger ham
state event telemetry B3.4'te alert routing ile birleştirilecek
(§11 B3.3 KARARLARI E=B+ kararı).
B3.5 — Sigorta: 3-4 hafta paper trading -> gerçek para (alert
entegrasyonu tamamlanmadan gerçek para kararı verilmez).

11. KİLİTLİ KARARLAR (Kümülatif)
Git/checkpoint:
Güvenilmeyen commit'ler local'de reset, remote'a force-push ile
silinir. Önceki checkpoint: 7fb827848aee38897fcea9616d4ea898c294089a
(REV9 DURUM + BAĞLAM, 2026-09-17).
Bu oturum checkpoint'i: <COMMIT_HASH> (B3.3 kapanış, 2026-09-23).
Protokol = yöntem, DURUM = içerik. Devir sırasında sadece bu dosya
güncellenir; PROTOKOL.md sabit kalır.
B2d çoklu config: --config-a / --config-b.
B2d equity curve: JSON + CSV; PNG yok (SORU C: (B)).
§6.1 funding ceza + §6.2 emtia exclude: UYGULANDI (B2e.−1).
B2e plan kararları (SORU A′–W, tam liste §16): B2e.0/1/1S/2/2S/3/real
faz kırılımı; commit tek.
SORU X: KAPANDI (A) — Strategy + PositionSimulator.last_rejection_reason.
SORU Z: KAPANDI (B) — SORU R senaryo listesi B2e.1S'de önerildi.
SORU Y: KAPANDI — test sayısı tutarlılık yanılgısı.
SORU 3 (dış ajan): sentetik doğrulama minimum + B3.1 paralel + B2e.2
odak.
SORU LL (A): B2e.2S 4 senaryo.
SORU A1 (A): step≤0 → test_ms default.
SORU MM (A): CLI diff için PO backtest_run.py paylaşır.
SORU NN (A): tek --report JSON.
SORU OO (B): strict = S′ (≥%95, ≤30dk, fail-fast); lenient = ≥%85,
≤60dk (WARNING); legacy = eşik yok.
SORU A2 (A): 3 profil — strict/lenient/legacy.
SORU PP (C): dropped_entries raw + reason×symbol sayımı.
SORU A3 (B): dropped_entries_by_reason + dropped_entries_by_symbol.
SORU QQ (A): B2e kapanış kriteri = capable + synthetic validated +
single-symbol real walk-forward (SORU T).
SORU RR (A): B3.1 çok-sembol kolektör — Top5 WS + Top10 watch.
SORU SS (C): B3.2–4 sırası micro-trigger → position manager → alert.
SORU TT (B): --mode single|multi|walkforward.
SORU UU (A): build_report saf fonksiyon.
SORU VV (A): SCHEMA_VERSION = 1.
SORU WW (C): data_quality{profile, by_symbol, aggregate}.
SORU XX (B): coverage = analyze_ohlcv_secs(secs, expected_interval_sec).
SORU YY (A): strict fail-fast tüm koşu.
SORU ZZ (A): walk_forward_claim enum.
SORU AA′ (A): --data-quality-profile legacy|lenient|strict; default
legacy.
SORU BB′ (C): excluded_symbols{all, effective, version}.
SORU T davranışı: single_symbol_real_walkforward_executed yalnızca
mode=walkforward + 1 sembol ile True.

B3.2 KARARLARI (SORU B3.2-A/B/C/D/E, 2026-09-22 → C revize 2026-09-23,
KİLİTLİ — Mod 1 onay + 3 dış-ajan karşılaştırması):
A) MicroTrigger/Strategy rol dağılımı: (A) MicroTrigger ana canlı
   karar mercii; TRIGGER state'inde EntrySignal üretilir. Strategy
   canlı ana akışta yer almaz. UYGULANDI.
B) Evaluate sıklığı: (A) 5s (mevcut timer_sleep_ms=5000); 5s mum
   kapanışıyla hizalı. UYGULANDI.
C) EntrySignal sonrası aksiyon: (A) Sadece structured JSON log +
   telemetry; DB'ye yazılmaz. REVİZE (2026-09-23): telemetry B3.3'e
   ertelendi; B3.2 kapsamı sadece structured JSON log. Telemetry
   B3.3 (position manager paper) ile birlikte değerlendirilecek.
   B3.3'te E=B+ kararı ile paper trades + paper_events telemetry
   uygulandı; MicroTrigger ham state event telemetry B3.4'e kaldı.
D) Hata davranışı: (A) Sembol bazlı devre dışı bırakma (quarantine)
   + log; global shutdown yok. UYGULANDI (is_quarantined /
   quarantine / MICRO_TRIGGER_QUARANTINE).
E) Strategy shadow parite kontrolü: (A) B3.2.3 uygulanır — Strategy
   her sembol için paralel çalışır, EntrySignal üretir, structured
   JSON log'a yazılır. Emir/pozisyon üretilmez. MicroTrigger
   TRIGGER'ları ile aynı log dosyasında karşılaştırma alanı bulunur.
   UYGULANDI.

3 dış-ajan karşıt görüşü (kayıt için): Strategy canlıdan tamamen
soyutlanırsa backtest-live parite borcu oluşur. SORU B3.2-E=(A)
bu borcu B3.3'e taşımadan B3.2 içinde ölçmeyi seçti.

B3.3 KARARLARI (SORU B3.3-A/B/C/D/E/F, 2026-09-23, KİLİTLİ — 5
dış-ajan karşılaştırması + asistan revize):
A) Paper position manager mimari konumu: (A) + A.1–A.4. Ayrı dosya
   src/execution/paper_position_manager.py; backtest PositionSimulator
   ve gerçek OrderManager dışarıda. A.1 ortak math çekirdeği
   (src/trading/paper_math.py); A.2 entry kararı global asyncio.Lock;
   A.3 current_position_qty geri beslemesi (get_open_position_qty);
   A.4 startup rehydration (on_startup). UYGULANDI.
B) Entry parite: (A) + B.1–B.3. 2 bps slippage; B.1 yön (LONG yukarı,
   SHORT aşağı); B.2 sizing entry_fill üzerinden; B.3 stale_price_ms
   =5000 -> "stale_price" reddi. UYGULANDI.
C) Exit tetikleme: (A′) 5s OHLCV high/low; entry_bucket_sec atlanır;
   aynı mumda TP+SL -> SL önce (konservatif). Tick exit B3.3 sonrası
   tech-debt (kayıt). UYGULANDI.
D) State persistence: (B) + D.1–D.6. SQLite paper_positions +
   paper_events; D.1 commit->memory; D.2 sync write (trade-off;
   to_thread refactor B3.3 sonrası); D.3 UNIQUE(position_id,
   event_type, source_seq); D.4 config izlenebilirliği
   (config_profile_tag, risk_pct, max_positions_*); D.5 WAL +
   busy_timeout=5000; D.6 startup rehydration. UYGULANDI.
E) B3.2-C telemetry kapsamı: (B+) paper trades (paper_positions) +
   paper_events (REJECT + lifecycle). MicroTrigger ham state event
   telemetry B3.4'e. UYGULANDI.
F) Sizing + limit + funding parite: (C-PROD) ayrı paper config bloğu;
   default PROD (risk_pct=0.006, max_positions_global=2); CLI ile
   TEST override (0.008/3). config_profile_tag pozisyon satırında
   saklanır. UYGULANDI.

B3.3 kapanış kaydı:
- Teslim 1: src/trading/__init__.py, src/trading/paper_math.py,
  src/execution/paper_position_manager.py,
  tests/unit/test_b3_3_paper_manager.py (30 test).
- Teslim 1 düzeltme: test 5s kova kapanış sınırı (sec_after+1 → +5;
  kaynak değişmedi). 907 PASS.
- Teslim 2: tests/shadow/runner.py bağlaması (10 nokta:
  _setup_db init, _apply_push on_ws_tick, _on_ohlcv_1s on_ohlcv,
  _insert_ticker_snapshot on_ticker, _micro_trigger_loop A.3
  geri besleme + TRIGGER → on_entry, run() on_startup + finalize).
  907 PASS.
- Teslim 3: tests/shadow/test_b3_3_runner_integration.py (7 test).
  914 PASS.
- Commit: tek, B3.3 kapanışında.

B3.3 kayıt notları (kilitli karar değil):
N1. tests/shadow/runner.py tests/ altında üretim orkestratörü;
    B3.4 öncesi taşıma kararı ayrı soru.
N2. B3.2 JSON EntrySignal log'u ile B3.3 DB arasında signal_id yok;
    log şemasına signal_id eklenmesi ayrı commit adayı.
N3. Contract size quantization (order_manager.quantize_qty) paper'da
    uygulanmaz; B3.5 planlamasında ele alınacak.
N4. paper finalize END_OF_BACKTEST üretir; restart recovery
    on_startup kullanır (finalize çağrılmaz).
N5. quarantine altında açık pozisyon exit akışı DEVAM eder; entry
    kontrolü runner'ın sorumluluğunda.

B3.3 dış-ajan dağılımı (kayıt): A 5/5 (A); B 5/5 (A ruhu); C 3/5 (A)
+ 1 kısmi + 1 hayır (tick); D 5/5 (B); E 4/5 (B) + 1 kısmi (B+);
F 2/5 (A) + 3 kısmi (PROD). Asistan önerisi: C=A′, E=B+, F=C-PROD
uygulandı.

B3.1 Q1–Q5 ALT PARAMETRE KARARLARI (2026-09-22, KİLİTLİ —
dış-ajan sentezi, 3 ajan karşılaştırması):
Q1 (B): Flap penceresi = 1 saat. 5dk rotasyon × 12 döngü; ilk ceza
        kademesi (1h) ile simetrik. Uzun pencere = geç quarantine
        (churn devam); kısa = erken donma.
Q2 (B): Flap sayım birimi = round-trip. Top5 gir-çık = 1 birim; tek
        yönlü giriş sayılmaz. Spec "gir-çık" tanımıyla uyumlu;
        tek yönlü ağ gürültüsünü filtreler.
Q3 (B): Karantina reset = 7 gün karantinasız stabilite sonrası
        level 1 (fresh start). Kalıcı damga eligible havuzunu
        küçültüp S'≥4'ü bozar; kademeli düşüş state karmaşıklığını
        artırır.
Q4 (B): seed_subscriptions yalnız süreç başlangıcında; state
        in-memory (restart affı flap penceresi 1h ile kısa sürede
        kendini düzeltir). WS reconnect'te seed TEKRAR çağrılmaz;
        mevcut _subscribed set korunur.
Q5 (A): Watch (top10 - top5) state tutulmaz; yalnız REST ticker.
        Top5 transition'ları flap/hysteresis state'ine girer;
        5 sembol için ek RAM/CPU yok.

Asistan öneri revizyonları (dış ajan karşılaştırması, 2026-09-22):
- A: (D) → (C) — kronik flapper sönümleme; 3 ajan bağımsız işaret etti.
- G: (A) → (C) — faz geçişinde "kesintisiz" tanımı revize.
- F: azınlık pozisyonu (B)'ye karşı (C) korundu (S′ risk önceliği).
- Q1: 3h → 1h — ajan 2/3 uzlaşı (5dk rotasyon × 12 döngü simetri).
- Q2: tek yönlü çıkış → round-trip — 2/3 uzlaşı (spec "gir-çık").
- Q4: her reconnect → yalnız süreç başlangıcı — restart affı flap
  penceresi ile kendini düzeltir.

Mimari:
Mimari 30 coin limit + Top20 operasyonel limit — bilinçli trade-off.
Not: B3.1'de tek WS process aktif (3x10 kapasite); ölçek B3.2+ için
ayrılmış.
Emtia/hisse exclude — constants.py EXCLUDED_SYMBOLS (Bkz §6.2).
Aşırı funding ceza — Bkz §6.1.
Contract size cache — bulk detail bir kez çekilir (1176 sembol).
Per-symbol max 1 pozisyon + multi-symbol concurrent; global concurrent
config'ten TEST=3, PROD=2.
TP/SL exit 5s OHLCV high/low; taker fee 0.0002.
Strategy config default'u katı kalır (require_sweep/mss/fvg=True,
entry_window_ms=15000); gevşetme CLI override ile.
B2c backtest config: entry_window_ms=300000, üç kapı True,
cooldown_ms=60000.
B2c TP/SL hesabı: SL = entry ∓ 0.5×ATR(14, 5s), TP = 2R.
B2c position sizing: risk-based, PROD=0.006 / TEST=0.008.
B2c entry price: signal bar close + slippage.
B2c çakışma çözümü: SL önce (konservatif).
B2c funding: opsiyonel bayrak, varsayılan kapalı.
B2c min SL floor: min_sl_distance_pct = 0.002×entry.
B2c fill slippage: entry_slippage_bps = 2.0.
B2c rapor: --report JSON.
B2d rapor şeması: { config{strategy,sim}, summary, metrics,
equity_curve, engine, signal_counts, trades }.
B2d metrikleri: sharpe_annualized, profit_factor, expectancy_r,
avg_holding_sec, max_consecutive_losses.
B2e.0 event modeli: tüm event'ler symbol + source_seq taşır.
B2e.0 stream_multi: J′ tie-break (ts_ms, event_type_rank, symbol,
source_seq).
B2e.0 source_seq kaynağı: trades_ohlcv_1s.sec; orderbook_snapshots.id;
tickers_snapshot.id.
B2e.0 PositionSimulator: per-symbol state dict; finalize(last_ts_ms,
last_prices: dict); MTM equity.
B2e.0 MTM semantiği: exit fee tahmini yok; entry_fee + funding_paid +
unrealized gross.
B2e.1 MultiSymbolRunner: interleaved; per-symbol Strategy +
SignalDetector; tek PositionSimulator.
B2e.2 WalkForwardRunner: her fold bağımsız sıfırdan; warmup = train
penceresi; test trades entry_ts_ms ≥ test_start_ms; fail-fast.
B2e.3 multi_report.build_report: saf fonksiyon; strict/lenient/legacy;
G′ şeması + A3 aggregation + BB′ excluded + ZZ claim.
SWEEP semantiği: LONG <- SWEEP_DOWN, SHORT <- SWEEP_UP (stop-hunt
reversal; wick_ratio 0.6).
B3.1 mexc_ws dinamik sub: subscribe/unsubscribe idempotent; _running
false ise no-op; reconnect yeni instance varsayımı.
B3.1 universe_service rotation: apply_scan sync (I/O yok); state
in-memory; excluded filtre belt-and-suspenders.
B3.1 runner: rotation arka planda iki timer; --enable-rotation
opsiyonel; daralma manuel onay.
B3.3 paper_math: saf fonksiyonlar; backtest ve paper manager paylaşır.
B3.3 paper_position_manager: entry global asyncio.Lock; exit sync;
SQLite WAL + busy_timeout=5000 (shadow collector ile aynı desen).
B3.3 config default: PROD (0.006/2); CLI override ile TEST (0.008/3).

Kod kuralları: Bkz AnaYasa REV5 §0.

PROTOKOL İHLALİ NOTU (2026-09-19): asistan aynı sohbette 4-backtick
kuralını 3 kez ihlal etti; protokol format kuralı netleştirilerek
kapatıldı.

PROTOKOL İHLALİ NOTU (2026-09-21): PO'nun ilettiği "974 pass" beyanı
DURUM §2'deki 783 PASS ile karşılaştırılmadan doğru kabul edildi.
Doğru sayı 794 PASS (783 + 11 B2e.1 testi). 974 beyanı PO tarafından
geri çekildi. B2e.1 sonucu etkilenmedi. Kayıt amacıyla not edildi.
(§10.1 — Mod 1, PO yazdı.)

PROTOKOL İHLALİ NOTU (2026-09-22): asistan dış-ajan prompt mesajında
PROTOKOL.md §7.1 ihlali yaptı (checklist bloğun altında verildi). PO
fark etti; çıktı doğru sırayla yeniden verildi. Kayıt için §6.6'da.
(§10.1 — Mod 1, PO yazdı.)

PROTOKOL İHLALİ NOTU (2026-09-22, B3.1 Mod 2): `...` işaretleyicisi
kaynaklı __init__ attribute kaybı. Kayıt için §6.8'de. (§10.1 —
Mod 1, asistan.)

PROTOKOL İHLALİ NOTU (2026-09-23, B3.2 Mod 2): test mock async/sync
karışıklığı → TypeError FAIL. Kayıt için §6.9'da. (§10.1 — Mod 1,
asistan.)

PROTOKOL İHLALİ NOTU (2026-09-23, B3.2 Mod 2): Eski hali bloğundan
önce dosya yolu yazılmadı (§7.6.2 ihlali). Kayıt için §6.10'da.
(§10.1 — Mod 1, asistan.)

PROTOKOL İHLALİ NOTU (2026-09-23, B3.3 Mod 2): çoklu parça patch
eski/yeni bloğu karışıklığı (§7.6.2 ihlali). Kayıt için §6.11'de.
(§10.1 — Mod 1, asistan.)

12. DOSYA KONUMLARI
docs/DURUM.md — bu dosya.
docs/PROTOKOL.md — yöntem dökümanı (sabit; evrensel).
docs/MikoV2-AnaYasa-REV5.md — 116 YAMA, kod kuralları (ANAYASA rolü).
docs/MikoV2-Proje-Tum-Moduller-REV5.md — modül pseudo (mimari
referans).

BAYAT ATIF DÜZELTMESİ (2026-09-23): önceki sürümlerde
src/execution/manager.py referansı vardı; gerçek dosya
src/execution/order_manager.py. §4 modül tablosu ve bu §12
güncellendi.

B2e.1 değişen/yeni:
src/backtest/multi_symbol_runner.py (YENİ) — MultiSymbolRunner.
src/backtest/strategy.py (DEĞİŞTİ) — last_rejection_reason + property.
src/backtest/position_sim.py (DEĞİŞTİ) — last_rejection_reason +
property.
tests/unit/test_backtest_multi.py (YENİ) — 11 test.

B2e.1S değişen/yeni:
tests/unit/test_backtest_multi_symbol_synthetic.py (YENİ) — 8 test.

B2e.2 değişen/yeni:
src/backtest/multi_symbol_runner.py (DEĞİŞTİ) — WalkForwardConfig +
FoldWindow + FoldResult + WalkForwardResult + WalkForwardRunner.
src/backtest/position_sim.py (DEĞİŞTİ) — Trade.window_id/fold_id.
src/backtest/replay_transport.py (DEĞİŞTİ) — collect_ohlcv_secs.
tests/unit/test_backtest_walkforward.py (YENİ) — 11 test.
tests/manual/backtest_run.py (DEĞİŞTİ) — --mode + --symbols +
--train-ms/--test-ms/--step-ms; KRİTİK FIX sim.finalize.

B2e.2S değişen/yeni:
tests/unit/test_backtest_walkforward.py (DEĞİŞTİ) — +4 test.

B2e.3 değişen/yeni:
src/backtest/multi_report.py (YENİ) — SCHEMA_VERSION, CLAIM_*,
build_report, _coverage_report, _dropped_aggregation, _apply_profile,
_excluded_report, _compute_claim.
src/backtest/replay_transport.py (DEĞİŞTİ) — collect_ticker_secs +
collect_depth_secs.
tests/manual/backtest_run.py (DEĞİŞTİ) — --data-quality-profile;
build_report entegrasyonu; _collect_coverage_secs.
tests/unit/test_backtest_multi_report.py (YENİ) — 24 test.

B3.1 değişen/yeni:
src/data_layer/mexc_ws.py (DEĞİŞTİ) — dinamik subscribe/unsubscribe +
subscribed_symbols(); _subscribed set; close() _subscribed.clear().
src/data_layer/universe_service.py (DEĞİŞTİ) — RotationDecision +
hysteresis (zaman) + flap (sayı, Q2=B round-trip) + üstel quarantine
(SORU A) + Q3=B 7 gün stabil reset; _consume_flap_slot SİLİNDİ.
src/data_layer/constants.py (mevcut) — EXCLUDED_SYMBOLS kullanımı.
tests/shadow/runner.py (DEĞİŞTİ) — çok-sembol state; iki timer
(_universe_scan_loop 30s + _ws_rotation_loop 5dk); watch REST ticker;
per-symbol watchdog; Top5→Top4 daralma uyarı; seed_subscriptions
(Q4=B); --symbols + --enable-rotation CLI.
tests/unit/test_b3_1_rotation.py (YENİ) — 8 test.
tests/shadow/test_rotation_integration.py (YENİ) — 7 test.

B3.2 değişen/yeni:
src/features/micro_trigger.py (DEĞİŞTİ) — SymbolTriggerState.
quarantine_until_ms; MicroTrigger.is_quarantined() + quarantine(symbol,
reason); MICRO_TRIGGER_QUARANTINE event; evaluate() başında quarantine
kontrolü; _reset_to_idle quarantine'i sıfırlamaz (ortogonal).
tests/shadow/runner.py (DEĞİŞTİ) — MicroTrigger canlı entegrasyonu
(_micro_trigger_loop 5s); per-symbol SignalDetector + MicroTrigger +
shadow Strategy; _on_ohlcv_1s detektör + shadow besleme; _init_symbol_
state (rotasyon tetikler); _emit_micro_event + _log_entry_signal JSON;
_determine_direction; quarantine skip + exception quarantine.
tests/shadow/test_b3_2_micro_trigger.py (YENİ) — 13 test.
tests/shadow/test_b3_2_runner_integration.py (YENİ) — 7 test.

B3.3 değişen/yeni:
src/trading/__init__.py (YENİ) — package marker.
src/trading/paper_math.py (YENİ) — saf math çekirdeği.
src/execution/paper_position_manager.py (YENİ) —
  PaperPositionManager + PaperPositionConfig + OhlcvSample +
  PaperTradeResult.
tests/unit/test_b3_3_paper_manager.py (YENİ) — 30 test.
tests/shadow/test_b3_3_runner_integration.py (YENİ) — 7 test.
tests/shadow/runner.py (DEĞİŞTİ) — paper manager bağlaması
  (10 nokta; bkz §11 B3.3 kapanış kaydı).

13. YENİ SOHBET NASIL BAŞLAR
Verilecek dosyalar:
DURUM.md (bu, v2.18)
PROTOKOL.md (evrensel)
MikoV2-AnaYasa-REV5.md
MikoV2-Proje-Tum-Moduller-REV5.md
İlk mesajda Mod 2 için istenen dosyalar (B3.4 uygulama için):
- tests/shadow/runner.py (B3.3 hedefi — mevcut hali)
- src/features/micro_trigger.py (mevcut hali)
- src/dashboard/app.py (mevcut hali)
- src/dashboard/routes.py (mevcut hali)
- src/dashboard/static/index.html (mevcut hali)
- src/data_layer/mexc_rest.py (mevcut hali)
- tests/shadow/test_b3_3_runner_integration.py (B3.3 test kalıbı)
- tests/shadow/test_b3_2_micro_trigger.py (B3.2 test kalıbı)
Açılış mesajı:
"MikoV2 projesine devam ediyoruz. B3.4'ten başlıyoruz. Mod: 1
(planlama) → sonra Mod 2 (kod). DURUM.md v2.18'i okudun mu? B3.3
kapandı (914 PASS; SORU B3.3-A/B/C/D/E/F kilitli; tek commit
atıldı). PROTOKOL.md v3.3 yürürlükte. SORU SS=C sırası: B3.4 →
B3.5. B3.4 kapsamı: Alert entegrasyonu (Telegram/Discord). Açık
not: B3.2-C'de ertelenen MicroTrigger ham state event telemetry
B3.4 alert routing ile birleştirilecek (§11 B3.3 KARARLARI E=B+
kararı). Kısıtlar: commit B3.4 kapanışında tek; SORU A′–W +
B3.1/B3.2/B3.3 tüm kilitli kararlar geçerli; yeniden sorma; §6.3
async_telemetry transient B3.4 kapsamı dışı; Python 3.10; §7.6
şablon + §7.7 test kapısı + §7.8 öz-uyum. B3.4 için Mod 1: alert
kanal(ları), event routing tablosu, rate limit, batch stratejisi,
dashboard entegrasyonu kararlarını sor."

14. UNFROZEN BEYANI
FROZEN YOK.
Her satır sorgulanabilir.
Yeni YAMA 369+ açık.
Blind kabul YASAK.

15. VERSİYON
v1.0 (REV9, 2026-09-17): Orijinal REV9 durum dökümanı.
v2.0 (2026-09-19): Protokol entegrasyonu. Git checkpoint.
v2.1 (2026-09-19): BAGLAM.txt entegrasyonu ve kaldırılması.
v2.2 (2026-09-19): Arşiv referansı temizliği.
v2.3 (2026-09-19): B1/B2a/B2b doğrulama + DB transfer yöntemi.
v2.4 (2026-09-19): B2c öncesi analiz; SWEEP yön fix; CLI override;
protokol format kuralı.
v2.5 (2026-09-20): Protokol entegrasyonu (SSOT, teslim modları, bağlam,
soru formatı, test kapısı, öz-uyum).
v2.6 (2026-09-20): SSOT temizliği; versiyon atıf yasağı; protokol uyum.
v2.7 (2026-09-20): B2c başlangıç kriterleri (SORU A–F) kilitlendi.
v2.8 (2026-09-20): B2c kapandı; SORU G/H; 733 test PASS; async
telemetry notu.
v2.9 (2026-09-20): B2d kapandı; reporting.py + CLI genişlemesi; 750
PASS.
v2.10 (2026-09-21): B2e planı kilitli; SORU A′–W (§16); kod başlamadı.
v2.11 (2026-09-21): B2e.−1 + B2e.0 kapandı; SORU X yeni açıldı; 783
PASS.
v2.12 (2026-09-21): B2e tüm alt fazlar kapandı — B2e.1 (11) + B2e.1S
(8) + B2e.2 (11) + B2e.2S (4) + B2e.3 (24). Toplam 842 PASS. SORU X
kapandı (A). SORU Z/Y/3/LL/MM/NN/OO/PP/QQ/RR/SS/TT/UU/VV/WW/XX/YY/ZZ/
AA′/BB′/A1/A2/A3 kilitli. CLI: --mode + --data-quality-profile.
multi_report.py (G′ şeması). Kritik fix: backtest_run.py sim.finalize
imza uyumu. B2e kapanış commit'i atıldı.
v2.13 (2026-09-22): B3.1 uygulama planı Mod 1'de ONAYLANDI. SORU A–G
alt parametre kararları kilitlendi. §6.6 yeni PROTOKOL İHLALİ NOTU
(2026-09-22, §7.1 ihlali). §6.7 proje dosya seti. Mod 2 için dosya
istekleri sırada. B2e kapanış commit'i atıldı.
v2.14 (2026-09-22): B3.1 kapandı (856 PASS + 1 bilinen transient
FAIL). mexc_ws dinamik sub; universe_service rotation (SORU A–G +
Q1–Q5 dış-ajan sentezi); runner çok-sembol; iki timer (30s scan /
5dk rotasyon); watch REST ticker; per-symbol watchdog; Top5→Top4
manuel onay uyarısı. §6.8 yeni PROTOKOL İHLALİ NOTU (`...`
işaretleyicisi; PO kararı: `...` yasak, Eski/Yeni hali bloklarında
dosya yolu yok). Tek commit B3.1 kapanış. Not: v2.14 içinde
PROTOKOL.md → SOHBET-KAPANIS-PROTOKOLU.md referans düzeltmesi (PO
kararı 2026-09-22); versiyon numarası değiştirilmedi.
v2.15 (2026-09-22): B3.2 planı Mod 1'de ONAYLANDI. SORU B3.2-A/B/C/D/E
kilitlendi (§11). A=(A) MicroTrigger ana karar mercii; B=(A) 5s
evaluate; C=(A) JSON log + telemetry; D=(A) sembol bazlı quarantine;
E=(A) Strategy shadow parite kontrolü (B3.2.3). Kod BAŞLAMADI.
v2.16 (2026-09-22): Protokol dökümanı geçişi — SOHBET-KAPANIS-
PROTOKOLU.md v2.6 → PROTOKOL.md v3.3 (evrensel). Tüm canlı atıflar
PROTOKOL.md'ye çevrildi; protokol bölüm numarası kaymaları
yansıtıldı (blok format §7.5, kod değişikliği şablonu §7.6, test
kapısı §7.7, öz-uyum §7.8). İçerik (faz/karar/test) değişmedi;
sadece atıf ve konum güncellemesi. Protokol versiyonu v3.3;
DURUM v2.15 → v2.16 (PO onayına tabi, §11.1).
v2.17 (2026-09-23): B3.2 kapandı — MicroTrigger canlı entegrasyonu
(5s evaluate, TRIGGER → EntrySignal JSON log); shadow Strategy
paralel parite kontrolü; MicroTrigger quarantine API
(is_quarantined / quarantine / MICRO_TRIGGER_QUARANTINE); per-symbol
quarantine skip + exception quarantine; _init_symbol_state rotasyon
tetikler. SORU B3.2-C REVİZE: telemetry B3.3'e ertelendi; B3.2
kapsamı sadece structured JSON log. 877 PASS (B3.2 +20 test; +1
transient çözümü). §6.9 + §6.10 yeni PROTOKOL İHLALİ NOTLARI
(async/sync mock + Eski hali dosya yolu). SSOT temizliği: PROTOKOL'e
ait tekrar eden satırlar silindi (§0 devir-protokolü; §11 kontrol
checklisti üstte + `...` yasak + Eski/Yeni blok dosya yolu notu).
Protokol = yöntem, DURUM = içerik ilkesi uygulandı.
v2.18 (2026-09-23): B3.3 kapandı — paper position manager canlı
canlı paper trading; src/trading/paper_math.py ortak math çekirdeği;
src/execution/paper_position_manager.py + SQLite paper_positions +
paper_events (UNIQUE idempotency, config izlenebilirliği); runner
bağlaması (10 nokta; A.3 current_position_qty geri beslemesi dahil).
SORU B3.3-A/B/C/D/E/F kilitli (5 dış-ajan karşılaştırması: A 5/5,
B 5/5, C 3/5+1 kısmi+1 hayır → A′ uygulandı, D 5/5, E 4/5+1 kısmi
→ B+ uygulandı, F 2/5+3 kısmi → C-PROD uygulandı). 914 PASS (B3.3
toplam 37: 17 paper_math + 13 paper_manager + 7 runner integration).
§6.11 yeni PROTOKOL İHLALİ NOTU (test 5s kova kapanış sınırı; kaynak
değişmedi). §12 bayat atıf düzeltmesi: manager.py → order_manager.py.
Protokol = yöntem, DURUM = içerik ilkesi uygulandı.

16. SORU A′–W PLAN KARARLARI (KİLİTLİ)
Bu bölüm B2e plan kararlarının SSOT sahibidir. Diğer bölümler bu
bölüme atıf yapar.
Bağımsız doğrulama geçmişi: 4 tur bağımsız ajan değerlendirmesi. SORU
C revize (Interleaved); SORU L revize (sıra + MTM); SORU K risk notu;
SORU Q′ çok katmanlı.

SORU A′ — §6.1/§6.2 fix'lerinin konumu: B2e.−1'de kodlanır ve test
edilir; commit B2e kapanışında tek. UYGULANDI.
SORU B — PositionSimulator multi-symbol: (A) gerçek multi-symbol;
per-symbol dict; finalize dict; funding per-symbol. UYGULANDI.
SORU C (REVİZE) — Topoloji: (A) Interleaved (heapq.merge, tek
engine.run, per-symbol strategy/detector, tek sim). UYGULANDI (B2e.1).
SORU D — Walk-forward pencere ölçeği: (A) Parametrik (train_ms/test_ms/
step_ms CLI). UYGULANDI (B2e.2).
SORU E — Top20 kaynağı: (A) DB'de mevcut semboller; CLI --symbols;
§6.2 exclude önce. UYGULANDI.
SORU F — Dosya yolları: multi_symbol_runner.py, multi_report.py,
test_backtest_multi.py, test_backtest_walkforward.py; CLI mevcut
backtest_run.py genişler. Ek test dosyaları:
test_b2e_minus1_compliance.py (B2e.−1), test_b2e0_infrastructure.py
(B2e.0), test_backtest_multi_symbol_synthetic.py (B2e.1S),
test_backtest_multi_report.py (B2e.3). UYGULANDI.
SORU G′ — Rapor şeması: iki katmanlı + diagnostics. UYGULANDI (B2e.3).
SORU H — Global limit drop: (A) FIFO; ts_ms ASC; tie-break
(event_type_rank, symbol, source_seq); exit önce işlenir. UYGULANDI.
SORU I — Walk-forward fold: I.1=(B) ≥1 fold; I.2=(A) step_ms default
= test_ms; I.3=(A) fail-fast. UYGULANDI (B2e.2).
SORU J′ — Merge determinizmi: (A) (ts_ms, event_type_rank, symbol,
source_seq); OHLCV=0/Depth=1/Ticker=2. UYGULANDI (B2e.0).
SORU K′′ — Global limit reject: attempt-based cooldown; risk notu:
canlı parity backtest-only assumption. UYGULANDI (B2e.1).
SORU L′′ — Equity/funding sözleşmesi: L.1=(B) her OHLCV close'unda
portföy MTM; L.2=(A) finalize son fiyat + WARNING; L.3=(A) funding
per-symbol timeline, ticker event günceller. İşlem sırası: exit/TP/SL
→ funding → MTM → entry sizing → entry execution. UYGULANDI (B2e.0).
SORU M — Train = warmup. UYGULANDI (B2e.2).
SORU N — Trade/rapor şeması: additive; window_id + fold_id. UYGULANDI
(B2e.2).
SORU O — §6.2 exclude listesi: explicit (constants.py); versiyonlanır;
universe_service + CLI. UYGULANDI (B2e.−1).
SORU P — KAPATILDI: içeriği SORU T + B2e.2S'ye dağıtıldı (v2.12).
SORU Q′ — Veri kalitesi: çok katmanlı; profiller strict/lenient/legacy.
UYGULANDI (B2e.3).
SORU R (v1) — Synthetic fixture: 18 senaryo; B2e.1S'ye 14 (v1) kabul
edildi; minimum alt kümesi (8) B2e.1S'de; kalan 6 B2e.2S'ye
ertelendi. 4 senaryo B2e.2S'de (LL=A).
SORU S′ — Gerçek multi-symbol gate: ≥4 sembol, ≥30 gün, completeness
≥%95, max gap ≤30dk, max_concurrent ≥3, dropped>0, fold≥2, ticker
doğrulanmış, exclude geçmiş.
SORU T — B2e kapanış tanımı: "capable + synthetic validated +
single-symbol real walk-forward". B2e.real ayrı gate. UYGULANDI
(B2e.3 claim türetme).
SORU U — source_seq kaynağı: DB rowid. UYGULANDI (B2e.0).
SORU V — Funding rate kaynağı: tickers_snapshot.funding_rate.
UYGULANDI (B2e.0).
SORU W — DURUM güncelleme: plan snapshot.

16b. SORU X–BB′ EK KARARLAR (KİLİTLİ — B2e.1'den B2e.3'e)
SORU X (A): Strategy + PositionSimulator.last_rejection_reason
additive alan. UYGULANDI (B2e.1).
SORU Y: KAPANDI — test sayısı tutarlılık yanılgısı.
SORU Z (B): SORU R senaryo listesi v1 kabul edildi.
SORU 3 (dış ajan): sentetik doğrulama minimum + B3.1 paralel + B2e.2
odak. UYGULANDI.
SORU LL (A): B2e.2S 4 senaryo.
SORU A1 (A): step≤0 → test_ms default (I.2 uyumlu).
SORU MM (A): CLI diff için PO backtest_run.py paylaşır. UYGULANDI.
SORU NN (A): tek --report JSON.
SORU OO (B): strict (S′), lenient (≥%85, ≤60dk), legacy (eşik yok).
SORU A2 (A): üç profil; default legacy.
SORU PP (C): dropped_entries raw + reason×symbol; oran ertelenir.
SORU A3 (B): dropped_entries_by_reason + dropped_entries_by_symbol;
schema_version bump.
SORU QQ (A): B2e kapanış kriteri (SORU T).
SORU RR (A): B3.1 çok-sembol kolektör — Top5 WS + Top10 watch.
SORU SS (C): B3.2–4 sırası micro-trigger → position manager → alert.
SORU TT (B): --mode single|multi|walkforward.
SORU UU (A): build_report saf fonksiyon.
SORU VV (A): SCHEMA_VERSION = 1.
SORU WW (C): data_quality{profile, by_symbol, aggregate}.
SORU XX (B): coverage = analyze_ohlcv_secs(secs, expected_interval_sec);
caller sorted(set(secs)).
SORU YY (A): strict fail-fast tüm koşu; tarama fold üretiminden önce.
SORU ZZ (A): walk_forward_claim enum; bayraklardan türetilir.
SORU AA′ (A): --data-quality-profile legacy|lenient|strict; default
legacy.
SORU BB′ (C): excluded_symbols{all, effective, version}.

SON