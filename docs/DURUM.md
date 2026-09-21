MikoV2 — DURUM
Versiyon: v2.12
Tarih: 2026-09-21
Durum: B2e TÜM ALT FAZLAR KAPANDI. B2e.1 (11 test) + B2e.1S (8 test) +
       B2e.2 (11 test) + B2e.2S (4 test) + B2e.3 (24 test) tamamlandı.
       Toplam 842 PASS. B2e kapanış commit'i bekliyor (tek commit).
       Sıradaki: B3.1 (çok-sembol kolektör — Top5 WS + Top10 watch).
Sıradaki: B3.1 + B2e kapanış commit'i. B3.1 B2e.2 ile paralel
          başlatılabilir; 30 günlük veri birikim saati B2e.real gate
          için (SORU S′) gerekli.
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
BAŞLAMADI) → v2.11 (B2e.−1 + B2e.0 kapandı: §6.1/§6.2 compliance +
multi-symbol altyapı; 783 PASS; SORU X açıldı) → v2.12 (B2e tüm alt
fazlar kapandı: B2e.1 + B2e.1S + B2e.2 + B2e.2S + B2e.3; 842 PASS;
CLI --mode single|multi|walkforward + --data-quality-profile;
multi_report.py G′ şeması; SORU X/Z/Y/3/LL/MM/NN/OO/PP/QQ/RR/SS/TT/
UU/VV/WW/XX/YY/ZZ/AA′/BB′/A1/A2/A3 kilitli)

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
protokolü için referans; Bkz Protokol §6).
Devir protokolü: SOHBET-KAPANIS-PROTOKOLU.md (projeden bağımsız yöntem
dökümanı; detay için Bkz Protokol §6). Devir sırasında sadece bu dosya
(DURUM.md) güncellenir; protokol sabit kalır.
DB yolu (VM): /home/eser_gobekli/MikoV2/data/mikov2.sqlite
DB şeması: orderbook_snapshots (id PK), trades_ohlcv_1s (sec PK),
tickers_snapshot (id PK)
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
| B2e.0|Multi-symbol altyapı: event symbol + source_seq + stream_multi + per-symbol sim state + finalize dict + MTM + data_quality (18 test)|Kapandı|
| B2e.1|Interleaved runner (MultiSymbolRunner) + J′ + K′′ drops + per-symbol strategy/detector + last_rejection_reason (SORU X) (11 test)|Kapandı|
| B2e.1S|Synthetic multi-symbol validation (8 test)|Kapandı|
| B2e.2|Walk-forward (WalkForwardRunner, SORU D/I/M/Q′) + window_id/fold_id (11 test)|Kapandı|
| B2e.2S|Synthetic walk-forward (fold aritmetiği, 4 test)|Kapandı|
| B2e.3|Rapor (multi_report.py, G′ şeması + data_quality profilleri + dropped aggregation + excluded_symbols) + CLI --data-quality-profile (24 test)|Kapandı|
| B2e kapanış|Tek commit (tüm alt fazlar)|SIRADAKİ|
| B3.1|Çok-sembol kolektör (Top5 WS + Top10 watch)|Sırada|
| B2e.real|Gerçek çok sembol gate (S′)|Veri birikimine bağlı (≥30 gün)|
| B3.2–4|Micro-trigger canlı + position manager (paper) + alert (SORU SS=C)|Sırada|

2. TEST DURUMU
Toplam: 842 test PASS.
Alt faz dağılımı: B2d 17; B2e.−1 15; B2e.0 18; B2e.1 11; B2e.1S 8;
B2e.2 11; B2e.2S 4; B2e.3 24.
Komut: pytest tests/ -q --tb=short --maxfail=1
Yakalanan kritik bug'lar: WS dead silent (pong data maskesi), mp.Queue
blocking event loop, DROP_OLDEST -> DROP_NEWEST race, 429 circuit
breaker eksikliği, SWEEP yön mapping tersliği (Bkz §7), SORU G/H
slippage/SL floor (B2c, Bkz §7), B2e.0 `PositionSimulator.finalize`
imza değişikliği sonrası `backtest_run.py` çağrısı kırıldı (B2e.3'te
düzeltildi).
Not: test_drop_oldest_preserves_newest ve
test_telemetry_1_by_1_eviction (tests/chaos/test_queue_full.py) full-
suite yükü altında mp.Queue feeder timing kaynaklı tekil/transient
FAIL üretebiliyor (Bkz §6.3). İzole koşularda ve son full koşularda
temiz. İzlenmeye devam.

3. RUNTIME — VM'DE AKTİF OLAN
Shadow collector (systemctl status miko-collector):
tests/shadow/runner.py — servis olarak çalışıyor, Restart=always.
3 veri kanalı:
L2 depth — orderbook_snapshots (60s interval, 500 seviye)
Trade OHLCV 1s — trades_ohlcv_1s (USDT-normalized, CVD için)
Tickers — tickers_snapshot (60s interval, OI + funding)
WS data-starvation watchdog aktif (90s data gelmezse restart).
Veritabanı: Bkz §0 (WAL mode).
Dashboard: http://<VM_IP>:8090/ (aiohttp.web, 7 endpoint, Chart.js)
Not: Kolektör şu an tek sembol (BTC_USDT). Çok-sembol genişleme B3.1.

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
| src/data_layer/mexc_ws.py|sub.depth + sub.deal WS + watchdog|
| src/data_layer/mexc_rest.py|Snapshot + contract_size + funding|
| src/data_layer/metrics_fetcher.py|1176 sembol bulk filtre + skorlama (§6.1 funding ceza; excluded_symbols DI)|
| src/data_layer/universe_service.py|Universe scan orkestrasyonu (§6.2 exclude + ScanResult.excluded_symbols)|
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
| src/backtest/multi_symbol_runner.py|B2e.1 — MultiSymbolRunner (interleaved); B2e.2 — WalkForwardRunner + WalkForwardConfig + FoldWindow + FoldResult + WalkForwardResult|
| src/backtest/multi_report.py|B2e.3 — G′ rapor şeması; SCHEMA_VERSION=1; CLAIM_* enum; build_report saf fonksiyon; data_quality{profile, by_symbol, aggregate}; dropped_entries_by_reason/by_symbol (SORU A3); excluded_symbols{all, effective, version} (SORU BB′)|
| src/backtest/reporting.py|B2d — genişletilmiş rapor (Sharpe, PF, expectancy, equity curve)|
| src/backtest/data_quality.py|B2e.0 — gap/completeness detection; B2e.3 — ticker/depth coverage da bu fonksiyonla (SORU XX)|
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
Karar: FAZ sonrası — B2c/B2d/B2e kapsamı dışı, ayrı commit.
Doğrulama: KOD İNCELEME (2026-09-20).
Durum: Not edildi, FAZ sonrasına bırakıldı. Full suite koşularında
test_drop_oldest_preserves_newest ve test_telemetry_1_by_1_eviction
ara sıra FAIL (transient). İzole koşularda temiz. B2e kapsamı dışı.

6.4 SORU X — K′′ diagnostics (KAPANDI)
Karar: (A) — Strategy + PositionSimulator'a additive
last_rejection_reason alanı; cooldown_active / per_symbol_max_position
/ global_limit_full reason'ları set edilir.
Durum: KAPANDI (B2e.1, 2026-09-21). Test: tests/unit/test_backtest_multi.py.

6.5 B2e kapanış commit'i
Sorun: B2e plan kararları (SORU A′–W) PO kısıtı gereği tek final
commit istiyor. Alt fazlarda commit YOK.
Durum: Bekliyor — B2e.1 + B2e.1S + B2e.2 + B2e.2S + B2e.3 kapandı,
commit sırada. Commit mesajı tüm alt fazları listeleyecek.

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
| B2e kapanış — Tek commit|SIRADAKİ|
| B3.1 — Çok-sembol kolektör|Sırada|
| B2e.real — Gerçek çok sembol gate (S′)|Veri birikimine bağlı (≥30 gün)|

B2e.1 kapsamı (kapandı):
- src/backtest/multi_symbol_runner.py (YENİ): MultiSymbolRunner
  (interleaved, SORU C); per-symbol Strategy/SignalDetector; tek
  PositionSimulator; K′′ dropped_entries (reason + symbol + ts_ms)
  toplama; cooldown_active transition-only kayıt (epizod başı).
- strategy.py + position_sim.py: SORU X — last_rejection_reason
  additive alan + property.
- tests/unit/test_backtest_multi.py (YENİ, 11 test): interleaved
  determinizm, J′ tie-break (ts_ms, event_type_rank, symbol,
  source_seq), global limit drop, per-symbol izolasyon, K′′ reason'ları.

B2e.1S kapsamı (kapandı):
- tests/unit/test_backtest_multi_symbol_synthetic.py (YENİ, 8 test):
  sentetik minimum (SORU 3=B); SORU R 1–14'ün kritik alt kümesi.
  Kalan 6 senaryo B2e.2S'ye ertelendi.

B2e.2 kapsamı (kapandı):
- multi_symbol_runner.py: WalkForwardConfig, FoldWindow, FoldResult,
  WalkForwardResult, WalkForwardRunner (SORU D/I/M + AA/BB/CC/DD/JJ).
- position_sim.py: Trade'a window_id + fold_id (SORU N); PositionSimulator
  constructor'a window_id/fold_id.
- multi_symbol_runner.py: MultiSymbolRunner._seen_ohlcv_secs (fold
  data_quality için).
- tests/unit/test_backtest_walkforward.py (YENİ, 11 test): fold üretimi,
  ≥1 fold, fail-fast (exception + callback_errors), determinizm.

B2e.2S kapsamı (kapandı):
- test_backtest_walkforward.py (+4 test): LL senaryoları — step>test,
  step≤0 default (SORU A1=A / I.2=A), çok-fold determinizm,
  boundary-gap algılama.

B2e.3 kapsamı (kapandı):
- src/backtest/multi_report.py (YENİ): SCHEMA_VERSION=1;
  CLAIM_CAPABLE/SYNTHETIC_VALIDATED/SINGLE_SYMBOL_REAL/
  MULTI_SYMBOL_REAL enum; build_report(payloads, *, schema_version,
  profile, symbols, synthetic_validated, excluded_symbols_all,
  excluded_symbols_version, requested_symbols, ohlcv_secs_by_symbol,
  ticker_secs_by_symbol, depth_secs_by_symbol) → dict; profil eşikleri
  (strict=S′, lenient=%85/60dk, legacy=eşik yok); strict fail-fast →
  RuntimeError; coverage için analyze_ohlcv_secs caller sözleşmesi
  (sorted(set(secs))); G′ şeması + A3 dropped aggregation + BB′
  excluded_symbols; source passthrough (payloads).
- src/backtest/replay_transport.py: collect_ticker_secs +
  collect_depth_secs (B2e.3).
- src/backtest/position_sim.py: SORU N — Trade.window_id +
  Trade.fold_id; PositionSimulator(*, window_id, fold_id).
- tests/manual/backtest_run.py:
    * KRİTİK FIX: sim.finalize(last_prices={symbol: price}) — B2e.0
      imza değişikliği sonrası kırılmıştı.
    * --mode single|multi|walkforward (SORU TT=B)
    * --symbols, --train-ms, --test-ms, --step-ms (SORU II=A)
    * --data-quality-profile legacy|lenient|strict (SORU AA′=A)
    * build_report entegrasyonu (single + multi + walkforward)
    * _collect_coverage_secs (ohlcv + ticker + depth)
- tests/unit/test_backtest_multi_report.py (YENİ, 24 test):
  sabitler, build_report temel, dropped aggregation, coverage XX,
  profiller YY, excluded BB′, claim ZZ, gaps budama.

CLI örnek kullanımı:
    # Single (B2c/B2d emsali; geriye uyumlu)
    python -m tests.manual.backtest_run --db data/mikov2.sqlite \
        --symbol BTC_USDT --entry-window-ms 300000 --cooldown-ms 60000 \
        --report b2e3_single.json
    # Walk-forward (SORU T kapanış kriteri)
    python -m tests.manual.backtest_run --db data/mikov2.sqlite \
        --mode walkforward --symbols BTC_USDT \
        --train-ms 172800000 --test-ms 86400000 \
        --report wf_b2e3.json
    # Strict profil (fail-fast)
    python -m tests.manual.backtest_run --db data/mikov2.sqlite \
        --symbol BTC_USDT --data-quality-profile strict \
        --report should_fail.json

B2e.3 çıktı örnekleri (BTC_USDT 97.8h, 2026-09-21):
- single mode → 44 trade, -%17.98; data_quality.aggregate.completeness
  ≈ 0.956; ticker_coverage ≈ %79; depth_coverage distinct ≈ %100
  (raw %149 — collector_rate_anomaly=True); walk_forward_claim =
  capable.
- walkforward mode (train=48h, test=24h) → 2 fold, 2 combined trade,
  1 combined drop; walk_forward_claim = single_symbol_real
  (SORU T).
- strict profil → RuntimeError:
  'strict_violated:completeness=0.9152,max_gap_ms=14572000'
  (BTC_USDT max gap 4.05h > 30 dk).

B2c SONRASI ANALİZ (2026-09-20, BTC_USDT, 97.8 saat):
Config: --entry-window-ms 300000 --cooldown-ms 60000 (üç kapı True).
Sonuç: 187 entry → 44 tamamlanan trade.
Exit dağılımı: 9 TP (R=+2.00) / 34 SL (R=-1.00) / 1 END_OF_BACKTEST
(R=-0.55).
win_rate = %20.45 (9/44).
avg_r_multiple = -0.3761.
max_drawdown_pct = %20.08.
total_return_pct = -%17.98 (final_equity 8201.82 / initial 10000).
Funding etkisi (--include-funding): ≈ 0 USDT.
BULGU: Bu 97.8 saatlik BTC örneklemde strateji kârlı değil. Breakeven
%33.3; ölçülen %20.45 altında.
YORUM: Sample size küçük (44 trade), tek rejim, tek sembol. B2e
(multi-symbol walk-forward) karar için gerekli. B2e sonuçları: tek
sembol walk-forward 2 fold, 2 trade, hepsi SL — örneklem çok küçük;
B3.1 çok-sembol kolektör ile veri birikince B2e.real gate karar
verecek.

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
- B2e.−1 — §6.1 + §6.2 compliance. KAPANDI (15 test).
- B2e.0 — Altyapı. KAPANDI (18 test).
- B2e.1 — Multi-symbol davranış: MultiSymbolRunner (interleaved),
  SORU X (A) last_rejection_reason, K′′ drops. KAPANDI (11 test).
- B2e.1S — Synthetic multi-symbol validation (minimum; SORU 3=B).
  KAPANDI (8 test).
- B2e.2 — Walk-forward: WalkForwardRunner, SORU D/I/M/Q′, window_id/
  fold_id. KAPANDI (11 test).
- B2e.2S — Synthetic walk-forward (fold aritmetiği, LL 4 senaryo).
  KAPANDI (4 test).
- B2e.3 — Rapor: multi_report.py (G′ + diagnostics + data_quality
  profilleri + A3 aggregation + BB′ excluded + ZZ claim).
  KAPANDI (24 test).
- B2e kapanış — Tek commit. SIRADAKİ.
- B2e.real — Gerçek çok sembol gate (S′); veri birikimine bağlı.

Commit politikası: PO kısıtı gereği tek final commit (B2e kapanışında).
Alt faz sonlarında commit YOK. Final commit mesajı B2e.−1 + B2e.0 +
B2e.1 + B2e.1S + B2e.2 + B2e.2S + B2e.3'ü listeleyecek.

9. SIRADAKİ FAZLAR
B2e kapanış commit'i → B3.1 (çok-sembol kolektör, Top5 WS + Top10
watch) → B3.2–4 (micro-trigger canlı + position manager paper + alert,
SORU SS=C sırası) → B2e.real (S′ gate, 30 gün veri birikiminden sonra
otomatik değerlendirme).
B2e sonrası: strateji parametre optimizasyonu — B2e.real sonuçlarına
göre. Kârlılık negatif kalırsa öncelik strateji adayı iterasyonuna
kayar (B3 gerçek-para adımı bloklanır).

Örnek kullanım (B2e.3 CLI):
    python -m tests.manual.backtest_run --db data/mikov2.sqlite \
        --symbol BTC_USDT --entry-window-ms 300000 --cooldown-ms 60000 \
        --report b2e3_single.json
    python -m tests.manual.backtest_run --db data/mikov2.sqlite \
        --mode walkforward --symbols BTC_USDT \
        --train-ms 172800000 --test-ms 86400000 \
        --report wf_b2e3.json

10. PROD İÇİN SONRAKİ ADIMLAR (B3)
SORU SS (C) sırası:
B3.1 — Çok-sembol kolektör: Top5 WS bağlı (tam depth + OHLCV + ticker),
Top10 watch. Universe scanner mevcut (Top20); rotasyonda WS abonelik
güncellenir. Hysteresis 5m/flap 3 yumuşatıcı. e2-micro CPU/RAM/DB
ilk hafta izlenir; aşılırsa Top5→Top4 daralması S′ ≥4 koşuluyla uyumlu.
B3.2 — Micro-trigger canlı (WS tick -> detector -> signal -> strategy).
B3.3 — Position manager paper (canlı canlı paper trading).
B3.4 — Alert entegrasyonu (Telegram/Discord).
B3.5 — Sigorta: 3-4 hafta paper trading -> gerçek para (alert
entegrasyonu tamamlanmadan gerçek para kararı verilmez).

11. KİLİTLİ KARARLAR (Kümülatif)
Git/checkpoint:
Güvenilmeyen commit'ler local'de reset, remote'a force-push ile
silinir. Önceki checkpoint: 7fb827848aee38897fcea9616d4ea898c294089a
(REV9 DURUM + BAĞLAM, 2026-09-17).
Bu oturum checkpoint'i: <COMMIT_HASH> (B2e kapanışı; commit henüz
atılmadı).
Protokol = yöntem, DURUM = içerik. Devir sırasında sadece bu dosya
güncellenir; SOHBET-KAPANIS-PROTOKOLU.md sabit kalır.
B2d çoklu config: --config-a / --config-b.
B2d equity curve: JSON + CSV; PNG yok (SORU C: (B)).
§6.1 funding ceza + §6.2 emtia exclude: UYGULANDI (B2e.−1).
B2e plan kararları (SORU A′–W, tam liste §16): B2e.0/1/1S/2/2S/3/real
faz kırılımı; commit tek.
SORU X: KAPANDI (A) — Strategy + PositionSimulator.last_rejection_reason
(additive).
SORU Z: KAPANDI (B) — SORU R senaryo listesi B2e.1S'de önerildi;
içerik kilitli §16'ya eklendi (v1).
SORU Y: KAPANDI — test sayısı tutarlılık yanılgısı; doğru sayı
arşivlendi.
SORU 3 (dış ajan): sentetik doğrulama minimum + B3.1 paralel + B2e.2
odak.
SORU LL (A): B2e.2S 4 senaryo — step>test / step≤0 default / çok-fold
determinizm / boundary-gap.
SORU A1 (A): step≤0 → test_ms default (I.2 uyumlu; fail-fast değil).
SORU MM (A): CLI diff için PO backtest_run.py paylaşır.
SORU NN (A): tek --report JSON (EE=A uyumlu).
SORU OO (B): strict = S′ (≥%95, ≤30dk, fail-fast); lenient = ≥%85,
≤60dk (WARNING); legacy = eşik yok.
SORU A2 (A): 3 profil — strict (S′, B2e.real gate), lenient (WARNING),
legacy (eşik yok; BTC_USDT kapanışı legacy ile koşar).
SORU PP (C): dropped_entries raw + reason×symbol sayımı; oran ertelenir.
SORU A3 (B): dropped_entries_by_reason + dropped_entries_by_symbol
üst anahtar; schema_version bump.
SORU QQ (A): B2e kapanış kriteri = capable + synthetic validated +
single-symbol real walk-forward (SORU T).
SORU RR (A): B3.1 çok-sembol kolektör — Top5 WS + Top10 watch.
SORU SS (C): B3.2–4 sırası micro-trigger → position manager → alert.
SORU TT (B): --mode single|multi|walkforward (açık anahtarlama).
SORU UU (A): build_report saf fonksiyon.
SORU VV (A): SCHEMA_VERSION = 1 (modül sabiti; additive değişiklikte
artır).
SORU WW (C): data_quality{profile, by_symbol, aggregate}; profile
aggregate'te tek kez.
SORU XX (B): coverage = analyze_ohlcv_secs(secs, expected_interval_sec);
caller sorted(set(secs)) verir; duplicate → collector_rate_anomaly=True.
SORU YY (A): strict fail-fast tüm koşu RuntimeError; tarama fold
üretiminden ÖNCE.
SORU ZZ (A): walk_forward_claim enum (capable / synthetic_validated /
single_symbol_real / multi_symbol_real); bayraklardan türetilir.
SORU AA′ (A): --data-quality-profile legacy|lenient|strict; default
legacy.
SORU BB′ (C): excluded_symbols{all, effective, version}.
SORU T davranışı: single_symbol_real_walkforward_executed yalnızca
mode=walkforward + 1 sembol ile True (kapanış kriteri).

Mimari:
Mimari 30 coin limit + Top20 operasyonel limit — bilinçli trade-off.
Emtia/hisse exclude — constants.py EXCLUDED_SYMBOLS (Bkz §6.2).
Aşırı funding ceza — Bkz §6.1.
Contract size cache — bulk detail bir kez çekilir (1176 sembol).
Per-symbol max 1 pozisyon + multi-symbol concurrent; global concurrent
config'ten TEST=3, PROD=2.
TP/SL exit 5s OHLCV high/low; taker fee 0.0002.
Strategy config default'u katı kalır (require_sweep/mss/fvg=True,
entry_window_ms=15000); gevşetme CLI override ile (SORU B: (B)).
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
equity_curve, engine, signal_counts, trades }; çoklu config:
{ config_a, config_b, comparison }.
B2d metrikleri: sharpe_annualized, profit_factor (kayıpsız → null),
expectancy_r, avg_holding_sec, max_consecutive_losses.
B2d equity curve: JSON + CSV.
B2e.0 event modeli: tüm event'ler symbol + source_seq taşır (default
geriye uyumlu).
B2e.0 stream_multi: J′ tie-break (ts_ms, event_type_rank, symbol,
source_seq).
B2e.0 source_seq kaynağı: trades_ohlcv_1s.sec; orderbook_snapshots.id;
tickers_snapshot.id.
B2e.0 PositionSimulator: per-symbol state dict; finalize(last_ts_ms,
last_prices: dict); MTM equity.
B2e.0 MTM semantiği: exit fee tahmini yok; sadece entry_fee +
funding_paid + unrealized gross.
B2e.1 MultiSymbolRunner: interleaved; per-symbol Strategy +
SignalDetector; tek PositionSimulator; dropped_entries transition-
only cooldown kaydı.
B2e.2 WalkForwardRunner: her fold bağımsız sıfırdan (Strategy/
Detector/Sim yeniden); warmup = train penceresi; test trades
entry_ts_ms ≥ test_start_ms; fail-fast exception + callback_errors>0;
step_ms None/≤0 → test_ms (I.2=A).
B2e.3 multi_report.build_report: saf fonksiyon; profil eşikleri
strict/lenient/legacy; G′ şeması + A3 aggregation + BB′ excluded +
ZZ claim türetme + source passthrough.
SWEEP semantiği: LONG <- SWEEP_DOWN, SHORT <- SWEEP_UP (stop-hunt
reversal; wick_ratio 0.6).

Kod kuralları: Bkz AnaYasa REV5 §0.

SOHBET-KAPANIS format kuralları: her döküman/kod ayrı 4-backtick
bloğu; blok içinde 3-backtick YASAK; kontrol checklist'i düz metin;
kod değişikliği önerileri Protokol §7.4 şablonu (tam yol + eski hali +
yeni hali + gerekçe) ile verilir. Test kapısı Bkz Protokol §7.5;
öz-uyum Bkz Protokol §7.6; format Bkz Protokol §7.3.

PROTOKOL İHLALİ NOTU (2026-09-19): asistan aynı sohbette 4-backtick
kuralını 3 kez ihlal etti; protokol format kuralı netleştirilerek
kapatıldı.

PROTOKOL İHLALİ NOTU (2026-09-21): PO'nun ilettiği "974 pass" beyanı
DURUM §2'deki 783 PASS ile karşılaştırılmadan doğru kabul edildi; fark
+191 mantıksız iken §7.2 Kontrol 5 (sayı tutarlılığı) ve §7.9.1
(VARSAYIM etiketi) uygulanmadı. Doğru sayı 794 PASS (783 + 11 B2e.1
testi). 974 beyanı PO tarafından geri çekildi. B2e.1 sonucu
etkilenmedi. Kayıt amacıyla not edildi. (§10.1 — Mod 1, PO yazdı.)

12. DOSYA KONUMLARI
docs/DURUM.md — bu dosya.
docs/SOHBET-KAPANIS-PROTOKOLU.md — yöntem dökümanı (sabit).
docs/MikoV2-AnaYasa-REV5.md — 116 YAMA, kod kuralları.
docs/MikoV2-Proje-Tum-Moduller-REV5.md — modül pseudo.

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
FoldWindow + FoldResult + WalkForwardResult + WalkForwardRunner;
MultiSymbolRunner window_id/fold_id + _seen_ohlcv_secs.
src/backtest/position_sim.py (DEĞİŞTİ) — Trade.window_id/fold_id;
PositionSimulator(*, window_id, fold_id).
src/backtest/replay_transport.py (DEĞİŞTİ) — collect_ohlcv_secs.
tests/unit/test_backtest_walkforward.py (YENİ) — 11 test (B2e.2).
tests/manual/backtest_run.py (DEĞİŞTİ) — --mode + --symbols +
--train-ms/--test-ms/--step-ms; KRİTİK FIX sim.finalize.

B2e.2S değişen/yeni:
tests/unit/test_backtest_walkforward.py (DEĞİŞTİ) — +4 test (LL
senaryoları).

B2e.3 değişen/yeni:
src/backtest/multi_report.py (YENİ) — SCHEMA_VERSION, CLAIM_*,
build_report, _coverage_report, _dropped_aggregation, _apply_profile,
_excluded_report, _compute_claim.
src/backtest/replay_transport.py (DEĞİŞTİ) — collect_ticker_secs +
collect_depth_secs.
tests/manual/backtest_run.py (DEĞİŞTİ) — --data-quality-profile;
build_report entegrasyonu (single + multi + walkforward);
_collect_coverage_secs.
tests/unit/test_backtest_multi_report.py (YENİ) — 24 test.

13. YENİ SOHBET NASIL BAŞLAR
Verilecek dosyalar:
DURUM.md (bu)
SOHBET-KAPANIS-PROTOKOLU.md
MikoV2-AnaYasa-REV5.md
MikoV2-Proje-Tum-Moduller-REV5.md
Açılış mesajı:
"DURUM.md v2.12'yi okudun mu? B2e tüm alt fazlar kapandı (842 PASS).
İki iş var: (1) B2e kapanış commit'i — PO atacak, tek commit; (2) B3.1
çok-sembol kolektör — kapsam SORU RR (A): Top5 WS + Top10 watch.
B3.1'e başlamadan önce SORU RR'nin detay planını onaylat; sonra
universe_service.py + runner'a WS abonelik rotasyonu ekle.
Commit B2e kapanışında tek; şimdi commit atma. SORU A′–W ve
LL/MM/NN/OO/PP/QQ/RR/SS/TT/UU/VV/WW/XX/YY/ZZ/AA′/BB′/A1/A2/A3/X/Z/3
kilitli; yeniden sorma."

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
v2.6 (2026-09-20): SSOT temizliği; versiyon atıf yasağı; protokol v3.2
uyum.
v2.7 (2026-09-20): B2c başlangıç kriterleri (SORU A–F) kilitlendi.
v2.8 (2026-09-20): B2c kapandı; SORU G/H; 733 test PASS; async
telemetry notu.
v2.9 (2026-09-20): B2d kapandı; reporting.py + CLI genişlemesi; 750
PASS.
v2.10 (2026-09-21): B2e planı kilitli; SORU A′–W (§16); kod başlamadı.
v2.11 (2026-09-21): B2e.−1 + B2e.0 kapandı; SORU X yeni açıldı; 783
PASS.
v2.12 (2026-09-21): B2e tüm alt fazlar kapandı — B2e.1 (11 test) +
B2e.1S (8) + B2e.2 (11) + B2e.2S (4) + B2e.3 (24). Toplam 842 PASS.
SORU X kapandı (A). SORU Z/Y/3/LL/MM/NN/OO/PP/QQ/RR/SS/TT/UU/VV/WW/XX/
YY/ZZ/AA′/BB′/A1/A2/A3 kilitli. CLI: --mode single|multi|walkforward +
--data-quality-profile. multi_report.py (G′ şeması). Kritik fix:
backtest_run.py sim.finalize imza uyumu. SORU T claim davranışı
düzeltildi (single_symbol_real_walkforward_executed yalnız walkforward
modda). B2e kapanış commit'i sırada.

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
backtest_run.py genişler. Ek test dosyaları: test_b2e_minus1_compliance.py
(B2e.−1), test_b2e0_infrastructure.py (B2e.0),
test_backtest_multi_symbol_synthetic.py (B2e.1S),
test_backtest_multi_report.py (B2e.3). UYGULANDI.
SORU G′ — Rapor şeması: iki katmanlı + diagnostics (schema_version,
multi_symbol_capable, synthetic_multi_symbol_validated,
real_multi_symbol_validated, single_symbol_real_walkforward_executed,
real_data_symbols, data_quality{profile,completeness,max_gap_ms,gaps},
ticker_coverage, depth_coverage, global_limit_exercised,
dropped_entries_count, dropped_entries, excluded_symbols, fold_count,
single_fold_warning, walk_forward_claim, fold_windows). UYGULANDI
(B2e.3).
SORU H — Global limit drop: (A) FIFO; ts_ms ASC; tie-break
(event_type_rank, symbol, source_seq); exit önce işlenir. UYGULANDI.
SORU I — Walk-forward fold: I.1=(B) ≥1 fold; I.2=(A) step_ms default
= test_ms; I.3=(A) fail-fast. UYGULANDI (B2e.2).
SORU J′ — Merge determinizmi: (A) (ts_ms, event_type_rank, symbol,
source_seq); OHLCV=0/Depth=1/Ticker=2. UYGULANDI (B2e.0).
SORU K′′ — Global limit reject: attempt-based cooldown; reason:
global_limit_full / per_symbol_max_position / cooldown_active; risk
notu: canlı parity backtest-only assumption. UYGULANDI (B2e.1).
SORU L′′ — Equity/funding sözleşmesi: L.1=(B) her OHLCV close'unda
portföy MTM; L.2=(A) finalize son fiyat + WARNING; L.3=(A) funding
per-symbol timeline, ticker event günceller. İşlem sırası: exit/TP/SL
→ funding → MTM → entry sizing → entry execution. UYGULANDI (B2e.0).
SORU M — Train = warmup. UYGULANDI (B2e.2).
SORU N — Trade/rapor şeması: additive; window_id + fold_id. UYGULANDI
(B2e.2).
SORU O — §6.2 exclude listesi: explicit (constants.py); versiyonlanır;
universe_service + CLI. UYGULANDI (B2e.−1).
SORU P — KAPATILDI: içeriği SORU T + B2e.2S'ye dağıtıldı (v2.12, SORU
KK=A).
SORU Q′ — Veri kalitesi: çok katmanlı (fail-fast / WARNING /
strict-lenient). UYGULANDI (B2e.3) — profiller strict/lenient/legacy.
SORU R (v1) — Synthetic fixture: 18 senaryo; B2e.1S'ye 14 (v1) kabul
edildi; bunların minimum alt kümesi (8) B2e.1S'de; kalan 6 B2e.2S'ye
ertelendi. 4 senaryo B2e.2S'de (LL=A). Liste:
  G1 J′ determinizm (3): aynı ts'de OHLCV<Depth<Ticker; aynı ts+tip'te
      sembol alfabetik; aynı ts+tip+sembol'de source_seq artan.
  G2 Interleaved (2): iki sembolün 1s OHLCV'leri serpişir + candle
      sayıları ayrı doğru; bir sembolde out-of-order drop diğerini
      etkilemez.
  G3 Per-symbol izolasyon (3): ATR bağımsız; _next_funding_ms
      bağımsız; _last_price bağımsız.
  G4 K′′ drops (3): per_symbol_max_position; global_limit_full;
      cooldown_active transition-only.
  G5 MTM + finalize (2): iki açık pozisyon equity = realized + 2×upnl
      − funding; finalize({}) son fiyatları sim state'ten okur.
  G6 Determinizm (1): aynı girdi + config → trades/drops/stats
      birebir.
  B2e.2S ek (LL=A): step>test; step≤0 default; çok-fold determinizm;
      boundary-gap.
SORU S′ — Gerçek multi-symbol gate: ≥4 sembol, ≥30 gün, completeness
≥%95, max gap ≤30dk, max_concurrent ≥3, dropped>0, fold≥2, ticker
doğrulanmış, exclude geçmiş.
SORU T — B2e kapanış tanımı: "capable + synthetic validated +
single-symbol real walk-forward". B2e.real ayrı gate. UYGULANDI
(B2e.3 claim türetme).
SORU U — source_seq kaynağı: DB rowid (orderbook_snapshots.id,
tickers_snapshot.id, trades_ohlcv_1s.sec). UYGULANDI (B2e.0).
SORU V — Funding rate kaynağı: tickers_snapshot.funding_rate.
UYGULANDI (B2e.0).
SORU W — DURUM güncelleme: plan snapshot.

16b. SORU X–BB′ EK KARARLAR (KİLİTLİ — B2e.1'den B2e.3'e)
SORU X (A): K′′ diagnostics için Strategy + PositionSimulator
last_rejection_reason additive alan. UYGULANDI (B2e.1).
SORU Y: KAPANDI — test sayısı tutarlılık yanılgısı.
SORU Z (B): SORU R senaryo listesi B2e.1S'de önerildi; kabul edildi
(v1, §16'ya eklendi).
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