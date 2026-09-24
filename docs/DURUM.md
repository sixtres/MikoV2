# MikoV2 — DURUM
Durum: B3.5 Round 5 kapandı. B3.5-AI=A kilit (observation_state
       wide fixed-schema + CHECK(id=1); mid-phase schema freeze
       yürürlükte). B3.5-AJ=B kilit (iki katmanlı rehearsal
       go/no-go; hard FAIL = NO-GO; soft WARN = PO onayı).
       B3.5 Mod 2 T1..T6 kapandı (migration + state + schema
       freeze absorb + rehearsal). T7 iptal (PO kararı;
       checklist içeriği T6 JSON + §11'de).
Sıradaki: B3.5 Mod 2 alt turları (rotasyon aktivasyonu + gözlem
       metrikleri + inert mode + stop-flag + AD/AE/U). Tek commit
       B3.5 kapanışında.
Amaç: Yeni sohbete başlarken bağlamı hızlıca aktarmak.
PO: Eser Göbekli
Önceki: REV7 (FAZ 6/7/8 kapanış) → REV9 (dashboard + universe +
shadow collector + backtest B0.x-B1) → protokol entegrasyonu →
BAGLAM.txt entegrasyonu → arşiv referansı temizliği → B1/B2a/B2b
doğrulama + DB transfer → B2c öncesi analiz + SWEEP yön fix →
protokol entegrasyonu → SSOT temizliği → B2c başlangıç kriterleri
kilitlendi → B2c kapanış → B2d kapanış → B2e planı kilitlendi →
B2e.−1 + B2e.0 kapandı → B2e tüm alt fazlar kapandı → B3.1 plan
onaylandı → B3.1 kapandı → B3.2 plan onaylandı → protokol dökümanı
geçişi (PROTOKOL.md yürürlükte) → B3.2 kapandı → B3.3 kapandı →
B3.4 Mod 1 kapandı → B3.4 Mod 2 kapandı → B3.5 Mod 1 plan
snapshot'ı 4 tur STORM ile kapandı (23 karar A–AH) → B3.5 Round 5
kapandı (AI=A, AJ=B) → B3.5 Mod 2 T1..T6 kapandı (migration +
state + schema freeze + rehearsal; 35 yeni test) → T7 iptal.

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
paper_events (id PK), micro_trigger_events (B3.4), alert_events
(B3.4, delivery_status 5-durumlu: pending/sending/delivered/
failed/expired), observation_state (B3.5, single-row id=1,
wide fixed-schema).
Kod kuralları: Bkz AnaYasa REV5 §0.

STORM Protokolü: Çoklu bağımsız LLM ile karar doğrulama
uygulanıyorsa STORM-PROTOKOL.md yürürlüktedir. PROTOKOL.md §0.7
bu dosyaya atıf yapar; SSOT STORM-PROTOKOL.md'dedir.

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
| B3.4 Mod 1|Alert entegrasyonu planı (37 madde kilitli)|Kapandı (2026-09-23)|
| B3.4 Mod 2|Alert entegrasyonu kod (agent + formatter + migration + event_catalog + dashboard + runner)|Kapandı (2026-09-23)|
| B3.5 Mod 1|Çok sembol paper gözlem planı (4 tur STORM review; 23 karar A–AH)|Kapandı (2026-09-23)|
| B3.5 Round 5|Schema freeze (AI=A) + rehearsal go/no-go (AJ=B)|Kapandı (2026-09-23)|
| B3.5 Mod 2 T1|observation_state migration (9 test)|Kapandı (2026-09-24)|
| B3.5 Mod 2 T2+T4|observation_state single-row access + testleri (11 test)|Kapandı (2026-09-24)|
| B3.5 Mod 2 T3|test_observation_migration (T1 ile birlikte)|Kapandı (2026-09-24)|
| B3.5 Mod 2 T5|schema freeze absorb (9 karar; 15 test)|Kapandı (2026-09-24)|
| B3.5 Mod 2 T6|rehearsal_b3_5.py (JSON-only; 7 adım hard/soft)|Kapandı (2026-09-24)|
| B3.5 Mod 2 T7|B3.5_REHEARSAL_CHECKLIST.md|İPTAL (PO kararı 2026-09-24)|
| B3.5 Mod 2 (kalan)|rotasyon + metrik + inert mode + stop-flag + AD/AE/U|Sıradaki|
| B2e.real|Gerçek çok sembol gate (S′)|Veri birikimine bağlı (≥30 gün)|

2. TEST DURUMU
Toplam: 1036 PASS.
Alt faz dağılımı: B2d 17; B2e.−1 15; B2e.0 18; B2e.1 11; B2e.1S 8;
B2e.2 11; B2e.2S 4; B2e.3 24; B3.1 15 (8 unit + 7 integration);
B3.2 20 (13 micro_trigger + 7 runner integration); B3.3 37
(17 paper_math + 13 paper_manager + 7 runner integration);
B3.4 Mod 2 87 (12 migration + 29 event_catalog + 18 formatter
+ 21 agent + 7 runner integration); B3.5 Mod 2 35 (9 migration
+ 11 state + 15 schema_freeze).
Komut: pytest tests/ -q --tb=short --maxfail=1
Bilinen transient FAIL (tests/chaos/test_queue_full.py:168) B3.3
ve B3.4 koşularında gözlenmedi. §6.3'te belgelenen mp.Queue feeder
timing kaynaklı; izlenmeye devam.
Yakalanan kritik bug'lar: WS dead silent (pong data maskesi),
mp.Queue blocking event loop, DROP_OLDEST -> DROP_NEWEST race,
429 circuit breaker eksikliği, SWEEP yön mapping tersliği
(Bkz §7), SORU G/H slippage/SL floor (B2c, Bkz §7), B2e.0
`PositionSimulator.finalize` imza değişikliği sonrası
`backtest_run.py` çağrısı kırıldı (B2e.3'te düzeltildi), B3.1
adım 1 `...` işaretleyicisi kaynaklı `__init__` attribute kaybı,
B3.2 test mock async/sync karışıklığı, B3.3 test 5s kova kapanış
sınırı (sec_after+1 → +5), B3.4 `_half_open_test` SQL'i
`alert_events.reason` kolonunu sorguladı (T1 şemasında yok;
payload JSON'dan parse ile düzeltildi), B3.5 Mod 2 T2
`test_no_or_replace_in_module_source` docstring/yorum kaynaklı
kırılganlık (ast walk'a çevrildi), T5 kolon sayımı (20→21).

3. RUNTIME — VM'DE AKTİF OLAN
Shadow collector (systemctl status miko-collector):
tests/shadow/runner.py — servis olarak çalışıyor, Restart=always.
Deployment: systemd (KANONİK, B3.4 X=(C) sonrası); Docker
opsiyonel, test edilmemiş (B3.5'e ertelendi).
3 veri kanalı:
L2 depth — orderbook_snapshots (60s interval, 500 seviye)
Trade OHLCV 1s — trades_ohlcv_1s (USDT-normalized, CVD için)
Tickers — tickers_snapshot (60s interval, OI + funding)
WS data-starvation watchdog aktif (90s data gelmezse restart).
B3.2: MicroTrigger canlı (5s evaluate) + shadow Strategy paralel.
B3.3: PaperPositionManager canlı (paper trading). paper_positions +
paper_events tabloları WAL üzerinden aynı DB'ye yazılır.
B3.4: AlertAgent canlı (env-gated). Env yoksa devre dışı; sistem
çalışmaya devam eder. P+S startup sırası: _setup_db (migration +
PRAGMA user_version) → AlertAgent init+start (session sonrası)
→ paper on_startup (rehydration) → run loop. Migration alert_events
+ micro_trigger_events tabloları aynı DB'ye yazılır.
B3.5 Mod 2 (lokal): observation_state migration + state.py +
schema freeze testleri + rehearsal script'i. VM'de migration
henüz çalıştırılmadı; sistem deploy rotasyon aktivasyonu ile
birlikte yapılacak (sonraki turlar).
Veritabanı: Bkz §0 (WAL mode).
Dashboard: http://<VM_IP>:8090/ (aiohttp.web, 10 endpoint, Chart.js)
B3.4 E=B' panel: alert counter + history pull + test button +
status panel (SSE YOK). U=(D): tüm /api/* Authorization header
zorunlu; SSE query param deprecated fallback (EventSource custom
header gönderemez). Endpoint'ler: /api/v2/alerts,
/api/v2/alerts/status, /api/v2/alert_test (POST).
Not: Kolektör şu an tek sembol (BTC_USDT). Çok-sembol genişleme B3.1
Mod 2'de kod olarak hazır; VM'de aktivasyon `--enable-rotation`
flag'ine bağlı; B3.5 Mod 2'de aktif edilecek (PO onayı ile).

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
| src/dashboard/app.py + routes.py|aiohttp.web server; B3.4: auth middleware (/api/* Authorization zorunlu) + 3 alert endpoint (alerts/status/alert_test)|
| src/dashboard/static/index.html|4 panel + Chart.js + SSE; B3.4: 5. panel (Alerts — counter/history/test button/status); token localStorage|
| src/backtest/replay_transport.py|SQLite 3-tablo merge -> stream; stream_multi; collect_ohlcv_secs / collect_ticker_secs / collect_depth_secs (B2e.3 coverage)|
| src/backtest/engine.py|Event dispatch engine|
| src/backtest/signal_detector.py|SWEEP/MSS/FVG/OTE tespiti (5s)|
| src/backtest/strategy.py|Sinyalleri entry kararına dönüştürür; SORU X — last_rejection_reason (additive)|
| src/backtest/position_sim.py|B2c entry/TP/SL + PnL; B2e.0 per-symbol state + finalize dict + MTM; SORU N — window_id/fold_id|
| src/backtest/multi_symbol_runner.py|B2e.1 MultiSymbolRunner (interleaved); B2e.2 WalkForwardRunner + WalkForwardConfig + FoldWindow + FoldResult + WalkForwardResult|
| src/backtest/multi_report.py|B2e.3 — G′ rapor şeması; SCHEMA_VERSION=1; CLAIM_* enum; build_report saf fonksiyon; data_quality{profile, by_symbol, aggregate}; dropped_entries_by_reason/by_symbol (SORU A3); excluded_symbols{all, effective, version} (SORU BB′)| 
| src/backtest/reporting.py|B2d — genişletilmiş rapor (Sharpe, PF, expectancy, equity curve)|
| src/backtest/data_quality.py|B2e.0 — gap/completeness detection; B2e.3 — ticker/depth coverage da (SORU XX)|
| tests/shadow/runner.py|Shadow collector — B3.1: çok-sembol state + iki timer (30s scan / 5dk WS rotasyon) + watch REST ticker + per-symbol watchdog + Top5→Top4 uyarı + --enable-rotation. B3.2: MicroTrigger canlı (5s evaluate) + shadow Strategy paralel + TRIGGER → EntrySignal JSON log + per-symbol quarantine skip + _init_symbol_state. B3.3: PaperPositionManager bağlaması (on_ws_tick, on_ohlcv, on_ticker, TRIGGER → on_entry, A.3 current_position_qty geri besleme, on_startup rehydration, finalize). B3.4: AlertAgent bağlaması (P+S startup sırası); _emit_micro_event fire-and-forget yönlendirme; MicroTrigger callback closure ile symbol enjeksiyonu; TRIGGER → ENTRY event emit; finally'de agent.stop()|
| src/features/micro_trigger.py|Per-symbol MicroTrigger state machine (IDLE->SWEEP->MSS->FVG_OTE->MICRO_CONFIRM->TRIGGER); paused_ms, hard deadline 600s, quarantine, next_candle, per-symbol asyncio.Lock. B3.2: quarantine_until_ms + is_quarantined() + quarantine(symbol, reason) + MICRO_TRIGGER_QUARANTINE event|
| src/trading/paper_math.py|B3.3 — ortak math çekirdeği (saf fonksiyonlar); backtest ve paper manager paylaşır|
| src/execution/paper_position_manager.py|B3.3 — PaperPositionManager (canlı paper trading). on_entry (global asyncio.Lock + stale_price + ATR guard); on_ohlcv (5s kova exit; SL önce; entry_bucket_sec atlanır); on_ws_tick; on_ticker (funding); on_startup (DB rehydration); finalize (END_OF_BACKTEST); SQLite paper_positions + paper_events (UNIQUE idempotency); get_open_position_qty (A.3)|
| tests/manual/backtest_run.py|Backtest CLI: --symbol (single); --symbols + --mode (multi|walkforward); --train-ms/--test-ms/--step-ms; --data-quality-profile; --config-a/b; --equity-csv; --report|
| src/alerting/__init__.py (B3.4)|Paket marker; migration public API export|
| src/alerting/migration.py (B3.4)|Tek migration bloğu (Y=(D)): alert_events (5-durumlu delivery_status) + micro_trigger_events + 4 index + PRAGMA user_version; chunked_delete_older_than rowid alt-sorgu (AJ); retention sabitleri (micro 3 gün / alert 7 gün)|
| src/alerting/event_catalog.py (B3.4)|R 22-satır event→seviye eşleme sözlüğü (literal tabloyla uyum); EXIT reason-aware; bilinmeyen event_type → WARNING + "uncataloged" log|
| src/alerting/formatter.py (B3.4)|Telegram HTML (sınırlı tag seti: b/code; html.escape) + Discord plain text; TR dil; secret-mask tek nokta (4 regex); parse/format exception → parse_mode=None degrade; batch header "MikoV2 Uyarı Grubu (N=…)"; AA dedup "xN son Wdk"|
| src/alerting/agent.py (B3.4)|Telegram + Discord config-driven; rate limit 30s; batch 5/5s; PriorityQueue CRITICAL bypass; dedup sembol+event_type 60s + sayıyla birleştirme; circuit breaker (5 ardışık alert-başına nihai fail → OPEN 60s → HALF_OPEN 1 test); retry 3; pending TTL 10dk startup sweep; AB4 optimistic lock; S=(D) alert_events tek doğruluk; Z=(C) network sırasında DB txn açık tutulmaz; Ş2 fail-fast; Ş3 DI; config_from_env (MIKOV2_ALERT_*; Y-269 int whitelist)|
| src/observation/__init__.py (B3.5)|Paket marker; migration public API export|
| src/observation/migration.py (B3.5)|observation_state tek migration bloğu: wide fixed-schema (21 kolon: id + 20 alan), CHECK(id=1), NOT NULL DEFAULT, INSERT OR IGNORE (id=1), PRAGMA user_version=1. alerting/migration.py deseni; retention yok — tek satır|
| src/observation/state.py (B3.5)|ObservationState frozen dataclass (typed read/write); load_state tek statement whole-row SELECT (torn-read yok); update_state selective UPDATE + INSERT OR IGNORE; poll_stop_flag/set_stop_flag (5s watchdog API, H=C); alan adı whitelist (SQL injection önleme); OR-REPLACE yok|
| tests/manual/rehearsal_b3_5.py (B3.5)|B3.5-AJ=B pre-day-0 rehearsal; 7 adım (4 HARD + 3 SOFT); DI callable; hard FAIL = NO-GO; soft WARN = PO onayı; sessiz downgrade sınırı (S3 %80 disk projeksiyonu VEYA SLA marjı ≤ 0 → hard'a terfi); JSON-only çıktı (rehearsal_report.json)|

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
Karar: FAZ sonrası — B3.4 kapsamı dışı, ayrı commit.
Doğrulama: KOD İNCELEME (2026-09-20).
Durum: Not edildi, FAZ sonrasına bırakıldı. B3.2/B3.3/B3.4
koşularında transient FAIL gözlenmedi.

6.4 SORU X — K′′ diagnostics (KAPANDI)
Karar: (A) — Strategy + PositionSimulator'a additive
last_rejection_reason alanı; cooldown_active / per_symbol_max_position
/ global_limit_full reason'ları set edilir.
Durum: KAPANDI (B2e.1, 2026-09-21).

6.5 B2e kapanış commit'i
Sorun: B2e plan kararları PO kısıtı gereği tek final commit istiyordu.
Durum: KAPANDI — tek commit atıldı (2026-09-22).

6.6 Proje dosya seti (SSOT)
Proje dosya seti: DURUM.md + PROTOKOL.md +
MikoV2-AnaYasa-REV5.md (ANAYASA rolü) + MikoV2-Proje-Tum-
Moduller-REV5.md (mimari referans, opsiyonel) + STORM-PROTOKOL.md.
PROTOKOL.md sabittir; devir sırasında güncellenmez.
Durum: UYGULANDI.

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
| B3.4 Mod 1 — Alert plan snapshot|Kapandı (2026-09-23)|
| B3.4 Mod 2 — Alert entegrasyonu kod|Kapandı (2026-09-23)|
| B3.5 Mod 1 — Çok sembol paper gözlem planı (4 tur STORM)|Kapandı (2026-09-23)|
| B3.5 Round 5 — Schema freeze (AI=A) + rehearsal (AJ=B)|Kapandı (2026-09-23)|
| B3.5 Mod 2 T1..T6 — observation_state migration + state + schema freeze + rehearsal|Kapandı (2026-09-24)|
| B3.5 Mod 2 T7 — Rehearsal checklist|İPTAL (PO kararı 2026-09-24)|
| B3.5 Mod 2 kalan — rotasyon + metrik + inert mode + stop-flag + AD/AE/U|Sıradaki|
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

B3.4 Mod 2 kapsamı (kapandı): src/alerting/ paketi (agent,
formatter, migration, event_catalog); alert_events + micro_trigger_events
tabloları (T1 migration, PRAGMA user_version); R 22-satır event→seviye
kataloğu; Telegram HTML + Discord plain text; secret-mask tek nokta;
config-driven (Telegram primary, Discord opt-in); katmanlı routing
(CRITICAL bypass / WARNING batch 5/5s / INFO log+DB); AA dedup + sayıyla
birleştirme; circuit breaker (5 ardışık alert-başına nihai fail → OPEN
60s → HALF_OPEN 1 test; AH 3 semantik); retry 3; pending TTL 10dk
startup sweep; AB4 optimistic lock (UPDATE ... WHERE id=? AND
delivery_status='pending'); startup sırası P+S (migration → alert agent
init → cache → paper on_startup → drain loop); dashboard E=B' panel
(counter + history pull + test button + status); U=(D) tüm /api/*
Authorization header + SSE query param deprecated fallback; runner
entegrasyonu (MicroTrigger callback closure symbol enjeksiyonu;
_emit_micro_event fire-and-forget; TRIGGER → ENTRY event emit;
finally'de agent.stop()); AnaYasa §0 systemd EnvironmentFile 0600
kanonik güncellemesi.

B3.5 Mod 1 kapsamı (kapandı): 4 tur STORM cross-agent review
(Round 1 A–O, Round 2 P–T + H-confirm, Round 3 U–AB, Round 4
AC–AH). 23 karar kilitli. AG Round 4 A oybirliği Round 5'te
GLM-5.3 adversarial appeal ile B'ye revize edildi (kanıt kalitesi
> oybirliği emsali).

B3.5 Mod 2 T1..T6 kapsamı (kapandı 2026-09-24):
- T1: src/observation/__init__.py + migration.py — wide fixed-schema
  observation_state tek migration bloğu (21 kolon: id + 20 alan),
  CHECK(id=1), NOT NULL DEFAULT, INSERT OR IGNORE (id=1), PRAGMA
  user_version=1. alerting/migration.py deseni; retention yok.
  Test: tests/unit/test_observation_migration.py (9 PASS).
- T2+T4: src/observation/state.py — ObservationState frozen dataclass;
  load_state tek statement whole-row SELECT (torn-read yok);
  update_state selective UPDATE + INSERT OR IGNORE; poll_stop_flag/
  set_stop_flag (H=C 5s poll API); alan adı whitelist (SQL injection
  önleme). Test: tests/unit/test_observation_state.py (11 PASS).
- T5: tests/unit/test_b3_5_ai_schema_freeze.py — 9 kilitli karar
  (H,K,T,R,AB,W,AD,AE,S) kolon absorb + enum check + mid-phase ALTER
  regresyonu. 21 kolon freeze. (15 PASS).
- T6: tests/manual/rehearsal_b3_5.py — B3.5-AJ=B pre-day-0 rehearsal;
  7 adım (H1..H4 HARD + S1..S3 SOFT); DI callable; hard FAIL=NO-GO;
  soft WARN=PO onayı; sessiz downgrade sınırı (S3 disk projeksiyon
  %80 VEYA SLA marjı ≤ 0 → hard terfi). JSON-only çıktı.
  pytest kapsamı dışı (manuel).
- T7: docs/B3.5_REHEARSAL_CHECKLIST.md — İPTAL (PO kararı
  2026-09-24). Gerekçe: checklist içeriği T6 JSON (durum_evidence)
  + §11'de yaşar; ayrı doküman SSOT'u böler. PO sign-off formalite
  katmanı gereksiz (tek PO = Eser Göbekli).

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
    # B3.3 paper manager + B3.4 alert agent)
    python -m tests.shadow.runner --symbols BTC_USDT,SOL_USDT \
        --db data/mikov2.sqlite --enable-rotation
    # B3.5 rehearsal (manuel; PO callable'ları sağlar)
    python -m tests.manual.rehearsal_b3_5 --out rehearsal_report.json

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
SORU A: (B) §6.1/§6.2 B2d'de uygulanmadı → SORU A′ ile revize.
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
fazlarda (B3.1, B3.2, B3.3, B3.4, B3.5) yine tek commit.

9. SIRADAKİ FAZLAR
B3.5 Mod 2 — kalan alt turlar (PO onayı 2026-09-23, Round 5 kapandı;
T1..T6 kapandı 2026-09-24):
- Rotasyon aktivasyonu: systemd ExecStart'a --enable-rotation eklenir
  (B3.5-A=A); runner kodu değişmez. VM'de kolektör çok-sembol
  (Top5 WS + Top10 watch) olarak çalışmaya başlar.
- Gözlem metrikleri (M=B): dashboard 6. panel + /api/v2/observation
  endpoint.
- Inert mode (AC=A): GET-only allowlist; POST/PUT/DELETE blok;
  /health status=observation_stopped; OBSERVATION_STOPPED tek emit.
- Stop-flag (H=C): 5s micro-trigger loop'a piggyback (SLA ≤10s);
  observation_state.observation_stop poll.
- clean_shutdown_marker (AD=A); auto-finalize (AE=A);
  OBSERVATION_DAILY_SUMMARY R satırı (U=A).
- Canlı para ile işlem açmak YOK.
- Yakalanan tüm sinyaller paper pozisyon olarak açılmış/kapanmış
  gibi not edilir (paper_positions + paper_events çok sembolde
  çalışır); B3.5-F=C PROD risk 0.006 + max_positions_global=3.
- 30 gün checkpoint + 60 gün final (B3.5-B=B); B2e.real manuel
  tetik (B3.5-G=B); walk-forward environment = temp GCP instance
  from Z=B snapshot (B3.5-AG=B).
- Alert: OBSERVATION_DAILY_SUMMARY additive R satırı + Telegram
  route (B3.5-U=A); EXIT forward O=A; stop-flag C + inert mode V
  + 5s piggyback X + 0600 perms W; clean_shutdown_marker AD;
  auto-finalize AE; offline maintenance AF; restore test AH.
- observation_state: B3.5-AI=A — wide fixed-schema + CHECK(id=1);
  9 kilitli karar (H,K,T,R,AB,W,AD,AE,S) tek tabloda; NOT NULL
  DEFAULT; INSERT OR IGNORE (id=1); OR REPLACE YASAK; mid-phase
  ALTER TABLE YASAK. Detay §11. UYGULANDI (T1..T5).
- Rehearsal: B3.5-AJ=B — iki katmanlı hard/soft go/no-go. Detay §11.
  UYGULANDI (T6); T7 checklist İPTAL.
- B2e.real (S′ gate, ≥30 gün veri) B3.5 sürecinde paralel.
- Süre boyunca üretilen datalar, işlemler, kârlılık, R-multiple,
  win_rate, drawdown, sembol bazlı performans karşılıklı
  değerlendirilir.
B3.5 sonunda: gerçek para kararı (ayrı karar; SORU SS=C).

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
B3.4 — Alert entegrasyonu (Telegram/Discord). Mod 1 plan KAPANDI
(2026-09-23); Mod 2 kod KAPANDI (2026-09-23).
B3.5 — Çok sembol paper gözlem + gerçek para öncesi 1-2 ay
değerlendirme. Mod 1 plan KAPANDI; Round 5 KAPANDI (AI=A, AJ=B);
Mod 2 T1..T6 KAPANDI (2026-09-24); kalan alt turlar SIRADAKİ.

11. KİLİTLİ KARARLAR (Kümülatif)
Git/checkpoint:
Güvenilmeyen commit'ler local'de reset, remote'a force-push ile
silinir. Önceki checkpoint: 7fb827848aee38897fcea9616d4ea898c294089a
(REV9 DURUM + BAĞLAM, 2026-09-17).
Bu oturum checkpoint'i: <COMMIT_HASH> (B3.5 Mod 2 T1..T6 kapanışı).
Protokol = yöntem, DURUM = içerik. Devir sırasında sadece bu dosya
güncellenir; PROTOKOL.md sabit kalır.
B2d çoklu config: --config-a / --config-b.
B2d equity curve: JSON + CSV; PNG yok (SORU C: (B)).
§6.1 funding ceza + §6.2 emtia exclude: UYGULANDI (B2e.−1).
B2e plan kararları (SORU A′–W, tam liste §15): B2e.0/1/1S/2/2S/3/real
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
   ertelendi; B3.2 kapsamı sadece structured JSON log. B3.3'te
   E=B+ kararı ile paper trades + paper_events telemetry uygulandı;
   MicroTrigger ham state event telemetry B3.4'e kaldı. B3.4 Mod 1'de
   R 22-satır tablosu + micro_trigger_events kararı ile kapandı.
D) Hata davranışı: (A) Sembol bazlı devre dışı bırakma (quarantine)
   + log; global shutdown yok. UYGULANDI.
E) Strategy shadow parite kontrolü: (A) B3.2.3 uygulanır — Strategy
   her sembol için paralel çalışır, EntrySignal üretir, structured
   JSON log'a yazılır. Emir/pozisyon üretilmez. UYGULANDI.

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
   telemetry B3.4'e. B3.4 Mod 1'de kapandı. UYGULANDI.
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
- Teslim 2: tests/shadow/runner.py bağlaması (10 nokta). 907 PASS.
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

B3.4 KARARLARI (SORU B3.4-A–AJ, 2026-09-23, KİLİTLİ — 5 dış-ajan +
1 2-kat-değerli ajan; tüm turlar tamamlandı)

Tur 1 (A–G): A=(D) config-driven (Telegram default, Discord
opt-in); B=(D) katmanlı routing; C=(C) CRITICAL bypass +
per-channel 30s; D=(C) batch 5/5s; E=(B') counter + history
(pull) + test button + status panel, SSE YOK; F=(D) retry 3 +
breaker 5 fail→60s→half-open 1 test; G=(D) Docker secrets +
env fallback.

Tur 2 (H–Q): H=(D) micro_trigger_events + async batch writer
(DROP_OLDEST); I=S'ye bağlı (S=(D) seçildiği için I tek
kaynağa indi: alert_events + delivery_status); J=(B) batch
flush 30s rate limit kuyruğuna girer (worst-case 35s
WARNING); K=(B) systemd kanonik, AnaYasa §0 güncellenir;
L=(A) alert_events aynı DB + ro connection + 7 gün
retention; M=(B) sembol+event_type 60s dedup + sayıyla
birleştirme; N=(B) Telegram HTML + Discord plain text;
O=(B) test button rate limit bypass YOK, token gerekli;
P=(A) alert agent _setup_db sonrası, on_startup öncesi;
Q=(B) kod+test + manuel test alert bir kez canlı.

Tur 3 (R–X): R=(C) kod içinde kilitli sözlük + test matrisi
+ 22-satır event→seviye tablosu; S=(D) alert_events
+ delivery_status tek doğruluk kaynağı + in-memory cache;
T=(C) pending boyut 100/TTL 10dk/expired + "CRITICAL gönderimi
30s WARNING penceresini resetlemez" yazılı kural + test;
U=(D) tüm endpoint'ler Authorization header + mevcut SSE için
query param deprecated fallback; V=(C) micro_trigger 3 gün +
alert 7 gün + in-process günlük janitor + startup cleanup +
chunked DELETE; W=(B) Telegram HTML (html.escape); X=(C)
AnaYasa §0 güncellenir, systemd kanonik + Docker opsiyonel
B3.5'e ertelenir.

Tur 4 (Y–AA): Y=(D) tek migration fonksiyonu + idempotent
CREATE IF NOT EXISTS + PRAGMA user_version check; Z=(C) alert
ro connection + status UPDATE kısa senkron writer txn + 3 şart;
AA=(C) dedup + sayıyla birleştirme + pencere ≥ 30s yazılı
kural + test.

Ek (Ş2, Ş3): Ş2=(B) startup config validasyonu fail-fast
(dedup_window_s ≥ rate_limit_s) + unit test; Ş3=(D) tek
global writer asyncio.Lock + yazılı sahiplik kuralı (DI
zorunlu, Y-353 uyumlu).

Tur 5 (AC–AJ): AC=(A) QUARANTINE=WARNING + AA dedup ×N;
ENTRY/EXIT reason-aware (SL/TP=WARNING, END=INFO); AD=(A)
AB1–AB5 Mod 2 zorunlu; AE=(A) EnvironmentFile 0600
kanonik; AF=(C)+SENDING enum (5-durum) — AB4 optimistic
lock şema gereği; AG=(B) + exchange_ts_ms + source_seq;
AH=(A)+3 semantik; AI=(B) MIKOV2_ALERT_* + Y-269 int
whitelist + Ş2 invariant; AJ=(C)+ rowid alt-sorgu.

AB1–AB5 (Mod 2 zorunlu):
AB1 history endpoint L=(A) ro bağlantı + status panel
    breaker/drop/error sayaçları
AB2 systemd EnvironmentFile 0600 seçimi (K=B + AE=A)
AB3 400 hata → F breaker sayacına sayılır
AB4 drain double-send önleme: UPDATE ... SET
    delivery_status='sending' WHERE id=? AND status='pending'
    optimistic lock; SELECT döngü başına ≤20
AB5 Ş3 DI: connection sahibi batch writer; drain lock'u
    ve connection'ı DI ile alır (Y-353)

B3.4 Mod 2 kapanış kaydı (teslimler):
- T1: src/alerting/__init__.py, src/alerting/migration.py,
  tests/unit/test_alerting_migration.py (12 PASS).
- T2: src/alerting/event_catalog.py,
  tests/unit/test_alerting_event_catalog.py (29 PASS;
  başlık 25→22 düzeltmesi; literal 22 benzersiz event_type).
- T3: src/alerting/formatter.py,
  tests/unit/test_alerting_formatter.py (18 PASS).
- T4: src/alerting/agent.py,
  tests/unit/test_alerting_agent.py (21 PASS).
  - T4 rev1: _half_open_test SQL'inden reason kolonu
    çıkarıldı (T1 şemasında yok; payload JSON'dan parse).
  - T4 rev2: test_half_open_failure_reopens_breaker — yeni
    pending CRITICAL emit edilir; breaker davranışı doğru.
- T5: src/dashboard/routes.py, src/dashboard/app.py,
  src/dashboard/static/index.html (994 PASS).
- T6: tests/shadow/runner.py (alert agent bağlaması;
  994 PASS).
- T7: tests/shadow/test_alerting_runner_integration.py
  (7 PASS).
  - T7 rev1: test_micro_trigger_loop_skips_quarantined —
    quarantine emit clear edildi.
  - T7 rev2: aynı test — fire-and-forget timing için
    sleep(0.05) clear öncesi.
  - T7 rev3: aynı test — is_quarantined spy; false-positive
    yolu kapatıldı.
- T8: docs/MikoV2-AnaYasa-REV5.md §0 satırı (Mod 1 manuel,
  PO onaylı).
- Toplam: 1001 PASS (914 + 87 yeni).
- Commit: tek, B3.4 kapanışında.

B3.4 Mod 2 hedef dosya listesi (§12'de tam liste).

STORM PROTOKOLÜ (yürürlükte):
Çoklu bağımsız LLM ile karar doğrulama uygulanır. SSOT:
STORM-PROTOKOL.md. PROTOKOL.md §0.7 atıf. Ağırlık tablosu:
asistan=1.25, GLM-5.3=2.0, Qwen3.8=1.5, GPT-5/Gemini-2.5-pro/
Muse Spark 1.1=1.0. Karar eşiği ≥%75 ağırlık → kilit. Asistan
oy hakkı tabloda; agregasyona dahildir (STORM §2).
Tek ajan azınlıkta kalırsa ve yeni sandbox kanıt sunarsa
adversarial appeal opsiyonu (AG vakası emsal).

B3.5 MOD 1 KİLİTLİ KARARLAR (Round 1–5; Round 5 kapanış):
Round 1 (A–O):
  A=A  systemd ExecStart --enable-rotation; runner kodu değişmez
  B=B  30 gün checkpoint (B2e.real) + 60 gün final
  C=B  OHLCV 90g; orderbook/tickers 30g; paper_* süresiz
  D=A  Açık paper pozisyon varken WS unsubscribe ertelenir
  E=A  TOP5_DARALMA_ALERT alert agent'a emit; otomatik aksiyon yok
  F=C  B3.5 profili: risk_pct=0.006 + max_positions_global=3
       (S' gate max_concurrent≥3 uyumu; B3.3-F default korunur)
  G=B  Manuel day-30 walk-forward; DURUM §7 kaydı
  H=C  DB flag observation_stop + watchdog poll
  I=B  Günlük OBSERVATION_DAILY_SUMMARY INFO event
  J=C  observation_daily DB tablosu
  K=B  Tek-satır observation_state tablosu
  L=A  paper_math.quantize_qty (per-symbol contractSize + stepSize)
  M=B  6. dashboard paneli + /api/v2/observation endpoint
  N=D  Final rapor: JSON + CSV + Markdown
  O=A  Paper EXIT event'leri alert agent'a forward
Round 2 (P–T):
  P=C  X saat sonra WARNING; defer süresiz
  Q=C  CRITICAL alert + adaptive retention fallback
  R=A  CHECKPOINT_DUE WARNING via alert agent
  S=A  Startup + daily refresh; retain-last-valid timestamped
  T=A  Gözlem devam; outage metrikleri; S' gate karar verir
Round 3 (U–AB):
  U=A  Additive R-table: OBSERVATION_DAILY_SUMMARY INFO + Telegram
       route (PO sign-off; mevcut 22 satır değişmez)
  V=A  Inert live mode after stop; dashboard/health live
  W=A  0600 DB perms + single-row UPDATE convention + transition
       WARNING alert
  X=C  Stop-flag check 5s micro-trigger loop'a piggyback (SLA ≤10s)
  Y=A  Tek outage >15dk VEYA kümülatif >60dk → WARNING
  Z=B  GCP scheduled disk snapshots (hypervisor-level, zero guest CPU)
  AA=A No VACUUM; SQLite page reuse; free-page ratio raporu
  AB=A Düşürülmüş retention kalıcı; transition observation_state'e
Round 4 (AC–AH):
  AC=A Inert mode GET-only allowlist; POST/PUT/DELETE blok;
       /health status=observation_stopped; OBSERVATION_STOPPED
       tek emit
  AD=A clean_shutdown_marker (SIGTERM finalize'da yazılır; startup'ta
       okunur+temizlenir; planned/unplanned ayrımı)
  AE=A target_days ulaşınca auto-finalize (END_OF_BACKTEST exit'ler;
       inert mode; OBSERVATION_COMPLETED)
  AF=A Phase-close offline: integrity_check → VACUUM → final
       walk-forward (free-space precheck; VACUUM INTO fallback)
  AG=B  Walk-forward env = temp larger GCP instance booted from
       Z=B snapshot (Round 5 revizyon; Round 4 A oybirliği GLM
       yeni kanıtı sonrası B'ye döndü; A fallback clause)
  AH=A Pre-day-0 tek restore testi (temp VM + integrity_check +
       row-count verify + DURUM kaydı)

Round 5 (2026-09-23, KAPANDI):
  AI=A  observation_state schema freeze — WIDE FIXED-SCHEMA +
        CHECK(id=1). Tüm 9 yük (H,K,T,R,AB,W,AD,AE,S) tek
        tabloda açık kolon (INTEGER ms / TEXT enum / 0-1 flag);
        NOT NULL DEFAULT; INSERT OR IGNORE (id=1) tek atış;
        OR REPLACE YASAK; tek migration blok CREATE TABLE IF
        NOT EXISTS + PRAGMA user_version (alerting/migration.py
        deseni); mid-phase ALTER TABLE YASAK; 10. alan ihtiyacı
        B3.5+1/B4.0'a. Ağırlıklı oy %87.10 (asistan dahil).
        Azınlık: Gemini-2.5-pro (D).
  AJ=B  Pre-day-0 rehearsal formal go/no-go — İKİ KATMAN:
        HARD (deploy Z=B, pytest full suite, stop-flag SLA ≤10s,
        AH restore integrity_check + row-count) herhangi FAIL =
        NO-GO; SOFT (Z snapshot doğrulama, AG dry-run,
        cadence + snapshot bytes ölçümü) WARN ile geçebilir;
        PO sign-off. AG fallback clause (temp VM→manuel scp)
        fallback path üzerinden PASS; yazılı workaround +
        PO sign-off. Sessiz downgrade sınırı: soft WARN Q=C
        %80 disk projeksiyonu VEYA SLA marjı aşımı → hard'a
        terfi; aynı WARN iki rehearsal'da tekrarlarsa otomatik
        hard. Ağırlıklı oy %74.19 (asistan dahil); split →
        PO nihai karar (B seçildi; GLM-5.3 sandbox_test
        belirleyici). Azınlık: GPT-5, Gemini-2.5-pro (D).

B3.5 MOD 2 KİLİTLİ KARARLAR (2026-09-24):
  T7=İPTAL  B3.5_REHEARSAL_CHECKLIST.md üretilmedi. Gerekçe:
            checklist içeriği T6 JSON (durum_evidence) + §11'de
            yaşar; ayrı doküman SSOT'u böler (§0.4). PO sign-off
            formalite katmanı gereksiz (tek PO = Eser Göbekli).
            T6 rev1: rehearsal_report.md üretimi kaldırıldı;
            yalnız JSON çıktı (rehearsal_report.json).
            PO kararı: 2026-09-24.

AG REVİZYON KAYDI (2026-09-23, Round 5):
Round 4 kazananı A (5 ajan + asistan, 6.75x/7.75x). GLM-5.3
adversarial appeal sundu: (i) Round-4 en zayıf argümanını (scp
crypto CPU) retract etti; (ii) sandbox TEST 2+3 ile "streaming
escape yok" + "naive live-copy 11/12 corrupt" kanıtları; (iii)
locked AH=A zaten temp-VM boot-from-snapshot lifecycle gerektiriyor
→ B'nin net yeni yüzeyi ~1 ssh + teardown; (iv) fallback
subsumption (B→A düşebilir, A→B düşemez). DURUM §3 verileriyle
çapraz kontrol: day-30 DB tahmini 5-9 GB (GLM 3 GB flip-trigger
üstü). PO kararı: AG=B kabul (Seçenek 1). A fallback clause:
temp instance başarısız olursa PO manuel scp'ye düşer (B3.5-AJ
rehearsal'da doğrulanır). Azınlık/kanıt kalitesi STORM prensibi
uygulandı.

12. DOSYA KONUMLARI
docs/DURUM.md — bu dosya.
docs/PROTOKOL.md — yöntem dökümanı (sabit; evrensel).
docs/STORM-PROTOKOL.md — çoklu LLM karar doğrulama (SSOT).
docs/MikoV2-AnaYasa-REV5.md — 116 YAMA, kod kuralları (ANAYASA
rolü); B3.4 X=(C)+AE=(A) sonrası §0 Secret satırı güncellendi
(systemd EnvironmentFile 0600 kanonik).
docs/MikoV2-Proje-Tum-Moduller-REV5.md — modül pseudo (mimari
referans).

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
shadow Strategy; _on_ohlcv_1s detektör + shadow besleme;
_init_symbol_state; _emit_micro_event + _log_entry_signal JSON;
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
tests/shadow/runner.py (DEĞİŞTİ) — paper manager bağlaması.

B3.4 Mod 2 değişen/yeni:
src/alerting/__init__.py (YENİ) — paket marker + migration API export.
src/alerting/migration.py (YENİ) — tek migration bloğu (Y=(D));
  alert_events + micro_trigger_events + index + PRAGMA user_version;
  chunked_delete_older_than (AJ).
src/alerting/event_catalog.py (YENİ) — R 22-satır sözlük;
  reason-aware EXIT; uncataloged → WARNING + log.
src/alerting/formatter.py (YENİ) — Telegram HTML + Discord plain;
  secret-mask tek nokta; degrade fallback; AA dedup "xN son Wdk".
src/alerting/agent.py (YENİ) — config-driven; rate limit; batch;
  PriorityQueue CRITICAL bypass; dedup; breaker (AH 3 semantik);
  retry 3; pending TTL; AB4 optimistic lock; S=(D); Z=(C);
  Ş2 fail-fast; Ş3 DI; config_from_env.
src/dashboard/app.py (DEĞİŞTİ) — auth middleware; 3 yeni endpoint.
src/dashboard/routes.py (DEĞİŞTİ) — alert_history / alert_status /
  alert_test; alert_agent DI.
src/dashboard/static/index.html (DEĞİŞTİ) — 5. panel (Alerts);
  token localStorage; auth header'lı fetchJson; test button.
tests/shadow/runner.py (DEĞİŞTİ) — alert agent bağlaması (P+S
  startup sırası; _emit_micro_event forward; MicroTrigger callback
  closure; TRIGGER → ENTRY event; finally agent.stop()).
tests/unit/test_alerting_migration.py (YENİ) — 12 test.
tests/unit/test_alerting_event_catalog.py (YENİ) — 29 test.
tests/unit/test_alerting_formatter.py (YENİ) — 18 test.
tests/unit/test_alerting_agent.py (YENİ) — 21 test.
tests/shadow/test_alerting_runner_integration.py (YENİ) — 7 test.
docs/MikoV2-AnaYasa-REV5.md §0 (DEĞİŞTİ) — systemd EnvironmentFile
  0600 kanonik; Docker secrets opsiyonel/test edilmemiş B3.5
  (Mod 1 manuel).

B3.5 Mod 1 (Round 1–5 STORM):
Mod 1 tur 1-4: STORM-PROTOKOL.md oluşturuldu ve kalibre edildi.
23 karar kilitli (A–AH). Round 5 kapandı (AI=A, AJ=B). Mod 2
kod sıradaki.

B3.5 Mod 2 T1..T6 değişen/yeni (2026-09-24):
src/observation/__init__.py (YENİ) — paket marker; migration
  public API export.
src/observation/migration.py (YENİ) — observation_state tek
  migration bloğu (wide fixed-schema, 21 kolon); CHECK(id=1);
  NOT NULL DEFAULT; INSERT OR IGNORE (id=1); PRAGMA
  user_version=1.
src/observation/state.py (YENİ) — ObservationState frozen
  dataclass; load_state / update_state / poll_stop_flag /
  set_stop_flag; alan adı whitelist; OR-REPLACE yok.
tests/unit/test_observation_migration.py (YENİ) — 9 test.
tests/unit/test_observation_state.py (YENİ) — 11 test.
tests/unit/test_b3_5_ai_schema_freeze.py (YENİ) — 15 test.
tests/manual/rehearsal_b3_5.py (YENİ) — B3.5-AJ=B rehearsal;
  7 adım (H1..H4 + S1..S3); DI callable; JSON-only çıktı.

13. YENİ SOHBET NASIL BAŞLAR
Verilecek dosyalar:
DURUM.md (bu)
PROTOKOL.md
STORM-PROTOKOL.md
MikoV2-AnaYasa-REV5.md (§0 systemd EnvironmentFile 0600)
MikoV2-Proje-Tum-Moduller-REV5.md

İlk mesaj:
"MikoV2 projesine devam ediyoruz. B3.5 Mod 2 T1..T6 kapandı
(2026-09-24). T7 iptal (PO kararı). B3.5 Mod 2 kalan alt
turlar sıradaki.

Mod: Mod 2 (kod üretimi).

Kalan turlar (B3.5 Mod 2; sıra PO kararına tabi):
- Rotasyon aktivasyonu: systemd ExecStart --enable-rotation
  eklenir; runner kodu değişmez (B3.5-A=A).
- Gözlem metrikleri (M=B): dashboard 6. panel +
  /api/v2/observation endpoint.
- Inert mode (AC=A): GET-only allowlist; /health
  status=observation_stopped; OBSERVATION_STOPPED tek emit.
- Stop-flag (H=C) 5s piggyback (SLA ≤10s).
- clean_shutdown_marker (AD=A); auto-finalize (AE=A);
  OBSERVATION_DAILY_SUMMARY R satırı (U=A).

Kısıtlar:
- Canlı para YOK.
- Tek commit B3.5 kapanışında (alt faz kırılımı PO onayına tabi).
- Python 3.10 (3.11+ syntax yasak).
- §7.5 çıktı kataloğu + §7.6 kod şablonu + §7.7 test kapısı +
  §7.8 öz-uyum zorunlu.
- B3.5 kilitli kararlar (Round 1–5, A–AJ) geçerli; yeniden sorma.
- §6.3 async_telemetry transient FAIL B3.5 kapsamı DIŞI.
- observation_state schema mid-phase değişiklik YASAK
  (B3.5-AI=A kilit).
- T7 iptal (2026-09-24); B3.5_REHEARSAL_CHECKLIST.md yok.
- STORM protokolü uygulanır (gerekirse).

İlk tur: rotasyon aktivasyonu teslimi için hazırla."

14. UNFROZEN BEYANI
FROZEN YOK.
Her satır sorgulanabilir.
Yeni YAMA 369+ açık.
Blind kabul YASAK.

15. SORU A′–W PLAN KARARLARI (KİLİTLİ)
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
SORU P — KAPATILDI: içeriği SORU T + B2e.2S'ye dağıtıldı.
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

15b. SORU X–BB′ EK KARARLAR (KİLİTLİ — B2e.1'den B2e.3'e)
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