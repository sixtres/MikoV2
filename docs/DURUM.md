MikoV2 — DURUM
Versiyon: v2.11
Tarih: 2026-09-21
Durum: B2e.−1 kapandı (765 PASS). B2e.0 kapandı (783 PASS). B2e.1 SIRADAKİ.
       B2e plan kararları §16 KİLİTLİ (SORU A′–W); SORU X yeni açıldı (§6.4).
       B2e kod BAŞLAMADI denemez — alt fazlar yürüyor; commit B2e kapanışında TEK.
Sıradaki: B2e.1 (§8) — interleaved runner + J′ determinizmi + K′′ drop + per-symbol
          strategy/detector. Başlamadan önce SORU X onayı gerekli.
Amaç: Yeni sohbete başlarken bağlamı hızlıca aktarmak.
PO: Eser Göbekli
Önceki: REV7 (FAZ 6/7/8 kapanış) → REV9 (dashboard + universe + shadow collector + backtest B0.x-B1) → v2.0 (protokol entegrasyonu) → v2.1 (BAGLAM.txt entegrasyonu) → v2.2 (arşiv referansı temizliği) → v2.3 (B1/B2a/B2b doğrulama + DB transfer) → v2.4 (B2c öncesi analiz + SWEEP yön fix) → v2.5 (protokol entegrasyonu) → v2.6 (SSOT temizliği) → v2.7 (B2c başlangıç kriterleri kilitlendi) → v2.8 (B2c kapanış + SORU G/H kilitli karar + async telemetry notu) → v2.9 (B2d kapanış: reporting.py + --config-a/b + --equity-csv + genişletilmiş --report; 750 test PASS) → v2.10 (B2e planı kilitli: SORU A′–W; 4 tur bağımsız doğrulama; kod BAŞLAMADI) → v2.11 (B2e.−1 + B2e.0 kapandı: §6.1/§6.2 compliance + multi-symbol altyapı; 783 test PASS)

0. ÇALIŞMA YÖNTEMİ
MikoV2 — MEXC Futures (vadeli) kripto trading botu. Kağıt-öncelikli tasarım + test odaklı geliştirme.
Stack: Python 3.10 + asyncio + mp.Queue + Numba + SQLite WAL + Parquet + aiohttp.web
Runtime: Google Cloud VM (e2-micro, Always Free), 7/24.
Process model: 3x10 WS process + REST gateway single process + supervisor.
Python sürümü: Bkz AnaYasa REV5 §0. VARSAYIM: AnaYasa Python 3.11 diyor, ancak runtime 3.10 hedefli ve 3.11+ syntax yasaklı. PO onayı gerekiyor.
Geliştirme döngüsü: Local'de (Windows/PS) kodlama ve test (pytest), VM'de (eser_gobekli@mikov2-collector-1) çalıştırma.
GitHub base URL: https://github.com/sixtres/MikoV2 (dosya isteme protokolü için referans; Bkz Protokol §6).
Devir protokolü: SOHBET-KAPANIS-PROTOKOLU.md (projeden bağımsız yöntem dökümanı; detay için Bkz Protokol §6). Devir sırasında sadece bu dosya (DURUM.md) güncellenir; protokol sabit kalır.
DB yolu (VM): /home/eser_gobekli/MikoV2/data/mikov2.sqlite
DB şeması: orderbook_snapshots (id PK), trades_ohlcv_1s (sec PK), tickers_snapshot (id PK)
Kod kuralları: Bkz AnaYasa REV5 §0.

VM'DEN LOCAL'E DOSYA TRANSFERİ (BAĞLAYICI)
Google Cloud Console web SSH terminalinde scp çalışmıyor. Kullanılan yöntem:
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
| B2e.1|Interleaved runner + J′ + K′′ + per-symbol strategy/detector|SIRADAKİ (SORU X onayı bekliyor)|
| B2e.1S|Synthetic multi-symbol validation|Sırada|
| B2e.2|Walk-forward (D/I/M/Q′)|Sırada|
| B2e.2S|Synthetic walk-forward validation|Sırada|
| B2e.3|Rapor (G′ + N + diagnostics + data_quality)|Sırada|
| B2e.real|Gerçek çok sembol gate (S′)|Veri birikimine bağlı|

2. TEST DURUMU
Toplam: 783 test PASS.
(B2d: 17; B2e.−1: 15; B2e.0: 18 yeni test.)
Komut: pytest tests/ -q --tb=short --maxfail=1
Yakalanan kritik bug'lar: WS dead silent (pong data maskesi), mp.Queue blocking event loop, DROP_OLDEST -> DROP_NEWEST race, 429 circuit breaker eksikliği, SWEEP yön mapping tersliği (Bkz §7), SORU G/H slippage/SL floor (B2c, Bkz §7).
Not: test_drop_oldest_preserves_newest full-suite yükü altında mp.Queue feeder timing kaynaklı tekil/transient FAIL üretebildi; izole koşuda ve son full koşuda (783 PASS) temiz. Test, polling + 0.5s deadline ile düzeltildi (Bkz §6.3 notu). İzlenmeye devam.

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

DB MEVCUT DURUM (2026-09-21):
- trades_ohlcv_1s: BTC_USDT tek sembol, 332216 satır, span 347517 sn (~97.8h).
- orderbook_snapshots: 8729 satır / 8729 distinct timestamp_ms (duplicate yok).
- tickers_snapshot: 4621 satır BTC_USDT (60s beklenen ~5868, %79).
- OHLCV veri kalitesi: 423 gap, max gap 14572 sn (~4.05h), toplam 15297 sn eksik, completeness ≈ %95.6.

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
| src/backtest/replay_transport.py|SQLite 3-tablo merge -> stream (symbol + source_seq; stream_multi)|
| src/backtest/engine.py|Event dispatch engine|
| src/backtest/signal_detector.py|SWEEP/MSS/FVG/OTE tespiti (5s)|
| src/backtest/strategy.py|Sinyalleri entry kararına dönüştürür|
| src/backtest/position_sim.py|B2c — entry/TP/SL simülasyon + PnL; B2e.0 per-symbol state + finalize dict + MTM equity|
| src/backtest/reporting.py|B2d — genişletilmiş rapor (Sharpe, PF, expectancy, equity curve)|
| src/backtest/data_quality.py|B2e.0 — gap/completeness detection (SORU Q′ temel; eşik/profil B2e.3)|
| tests/manual/backtest_run.py|Backtest CLI runner (B2c: --report, --include-funding; B2d: --config-a/b, --equity-csv)|

5. UNIVERSE SCANNER KARARI
Sonuç: 1176 sembol -> 3 aşamalı filtre -> Top20 (operasyonel limit; mimari üst sınır 30 coin için Bkz §11).
Aşama 1 (Fatal): oi_usd > 1M + volume24 > 10M + 0.3 < spread < 20 bps.
Aşama 2 (Skor): volume %40 + OI %30 + funding %30. Funding skoru: |f|>0.005 ceza (-1.0); aksi |f|/0.005 (B2e.−1).
Aşama 3 (Limit): Top5 WS bağlı, Top10 watch, Top20 takip.
Exclude: EXCLUDED_SYMBOLS (constants.py, §6.2) skorlama ve normalizasyondan önce uygulanır.
Örnek Top5 (2026-09-17): BTC_USDT, SOL_USDT, XAUT_USDT, XRP_USDT, ONE_USDT. Not: XAUT artık exclude (§6.2).

6. AÇIK SORUNLAR
6.1 Funding rate aşırı değerler "fırsat" olarak görülüyor
Sorun: ONE_USDT funding=-2%, LSK_USDT funding=-0.43% gibi değerler Top10'a giriyor. Tehlikeli — muhtemelen likidasyon kaskadı veya exchange-spesifik durum.
Karar: Skorlamada aşırı funding CEZA almalı:
    f_abs = abs(s.funding_rate)
    if f_abs > 0.005:  # 0.5% üstü = ceza
        f_score = -1.0
    else:
        f_score = f_abs / 0.005
Durum: UYGULANDI (B2e.−1, 2026-09-21). metrics_fetcher.py içinde `f_score` hesaplanıyor; testler: tests/unit/test_b2e_minus1_compliance.py.

6.2 Emtia token'ları universe'e sızıyor
Sorun: XAUT_USDT (Tether Gold), SILVER_USDT, UKOIL_USDT, USOIL_USDT, SPCXSTOCK_USDT gibi semboller kripto değil — tokenlaştırılmış emtia/hisse. Whale-radar mantığı bunlarda çalışmaz.
Karar: Exclude listesi eklenecek (kanonik, versiyonlu):
    src/data_layer/constants.py
    EXCLUDED_SYMBOLS_VERSION = 1
    EXCLUDED_SYMBOLS = frozenset({
        "XAUT_USDT", "XAU_USDT", "XAG_USDT",
        "SILVER_USDT", "GOLD_USDT",
        "UKOIL_USDT", "USOIL_USDT",
        "SPCXSTOCK_USDT",
    })
Uygulama: BulkMetricsFetcher candidate loop (normalizasyondan önce) + UniverseService ScanResult.excluded_symbols. Regex YOK (SORU O).
Durum: UYGULANDI (B2e.−1, 2026-09-21). Testler: tests/unit/test_b2e_minus1_compliance.py.

6.3 async_telemetry_queue _bridge_loop DROP_NEWEST sapması
Sorun: threaded_bridge=True yolunda mp_queue.put queue.Full dönerse, item deque(maxlen) başına appendleft edilirken deque sağdan (en yeni) eleman tahliye eder. DROP_OLDEST semantiği dar bir yarış penceresinde DROP_NEWEST davranışına sapar.
Etki alanı: Sadece threaded_bridge=True (production default). Testler threaded_bridge=False kullandığı için bu yol test kapsamı dışı.
Karar: FAZ sonrası — B2c/B2d/B2e kapsamı dışı, ayrı commit.
Doğrulama: KOD İNCELEME (2026-09-20).
Durum: Not edildi, FAZ sonrasına bırakıldı. Full suite koşusunda test_drop_oldest_preserves_newest ara sıra FAIL (transient). İzole koşuda temiz. B2e kapsamı dışı.

6.4 SORU X — K′′ diagnostics için minimal alan (B2e.1 başlangıcı öncesi)
Bağlam: SORU K′′ (§16) reason'ları (global_limit_full / per_symbol_max_position / cooldown_active) şu an kodda yok; diagnostics toplamak için Strategy ve PositionSimulator'a minimal state gerekiyor.
Seçenekler: (A) last_rejection_reason alanı (additive, API imzası değişmez) / (B) observer katman (SSOT zayıf) / (C) cooldown'u B2e.3'e ertele.
Öneri: (A). Durum: BEKLEMEDE (PO onayı, B2e.1 açılışında).

7. BACKTEST İLERLEME
| İş|Durum|
| ---|---|
| B1 — ReplayTransport + engine|Doğrulandı (97.8 saat / 4.08s)|
| B2a — Signal detector|Doğrulandı (8 sinyal tipi)|
| B2b — Strategy adapter|Doğrulandı (SWEEP yön bug'ı fix'lendi)|
| B2c — Position simulator + PnL|Kapandı (16 test)|
| B2d — Backtest runner + rapor|Kapandı (17 test)|
| B2e.−1 — §6.1/§6.2 compliance|Kapandı (15 test)|
| B2e.0 — Multi-symbol altyapı|Kapandı (18 test; 783 PASS)|
| B2e.1 — Interleaved runner|SIRADAKİ (SORU X onayı)|
| B2e.1S — Synthetic multi-symbol|Sırada|
| B2e.2 — Walk-forward|Sırada|
| B2e.2S — Synthetic walk-forward|Sırada|
| B2e.3 — Rapor (G′/N/diagnostics)|Sırada|
| B2e.real — Gerçek çok sembol gate (S′)|Veri birikimine bağlı|

B2e.0 kapsamı (kapandı):
- replay_transport.py: OHLCVEvent/DepthEvent/TickerEvent → symbol + source_seq alanları (default korunur, geriye uyumlu).
- stream_multi(symbols, ts_from, ts_to): heapq.merge tie-break (ts_ms, event_type_rank, symbol, source_seq); event_type_rank OHLCV=0/Depth=1/Ticker=2 (SORU J′).
- source_seq kaynağı (SORU U): trades_ohlcv_1s.sec; orderbook_snapshots.id; tickers_snapshot.id.
- position_sim.py: per-symbol `_candles`/`_active`/`_next_funding_ms`/`_last_funding_rate`/`_last_price` dict'leri; `on_ohlcv(ev)` ev.symbol okur; `finalize(last_ts_ms, last_prices: dict)`; MTM equity (`_realized_equity` + unrealized; SORU L′′); entry sizing MTM equity ile.
- data_quality.py (yeni): analyze_ohlcv_secs → DataQualityReport (span, sample, expected, completeness, gap_count, max_gap_sec, gaps). Eşik/profil B2e.3.
- Test: test_position_sim.py `_ohlcv`/`_warm` sembol parametreli; `test_global_concurrent_limit` üç sembolü ısıtıyor (SORU B per-symbol ATR).
- VARSAYIM: MTM'de exit fee tahmini yok (sadece entry_fee + funding_paid + unrealized gross).

B2c SONRASI ANALİZ (2026-09-20, BTC_USDT, 97.8 saat):
Config: --entry-window-ms 300000 --cooldown-ms 60000 (üç kapı True).
Sonuç: 187 entry → 44 tamamlanan trade.
Exit dağılımı: 9 TP (R=+2.00) / 34 SL (R=-1.00) / 1 END_OF_BACKTEST (R=-0.55).
win_rate = %20.45 (9/44).
avg_r_multiple = -0.3761.
max_drawdown_pct = %20.08.
total_return_pct = -%17.98 (final_equity 8201.82 / initial 10000).
Funding etkisi (--include-funding): ≈ 0 USDT.
BULGU: Bu 97.8 saatlik BTC örneklemde strateji kârlı değil. Breakeven %33.3; ölçülen %20.45 altında.
YORUM: Sample size küçük (44 trade), tek rejim, tek sembol. B2e (multi-symbol walk-forward) karar için gerekli.

B2c SORU G/H (B2c sırasında kilitlenen ek kararlar):
SORU G: (C) min_sl_distance_pct=0.002 floor.
SORU H: (A) entry_slippage_bps=2.0.

B2d SONUÇLARI (2026-09-20, kilitli):
SORU A: (B) §6.1/§6.2 B2d'de uygulanmadı → v2.10'da SORU A′ ile revize.
SORU B: (A) --config-a / --config-b; tek --report JSON'unda config_a + config_b + comparison.
SORU C: (B) Equity curve JSON + CSV (--equity-csv); PNG yok.
Yeni dosya: src/backtest/reporting.py; tests/unit/test_backtest_reporting.py (17 test).

8. B2e — FAZ KIRILIMI VE DURUM
- B2e.−1 — §6.1 + §6.2 compliance fix + testleri. KAPANDI (2026-09-21, 15 test).
- B2e.0 — Altyapı: event symbol, stream_multi + J′ tie-break, source_seq (SORU U), sim multi-state + finalize dict + MTM (SORU B + L′′), data_quality temel, 750 regression. KAPANDI (2026-09-21, 18 test; 783 PASS).
- B2e.1 — Multi-symbol davranış: multi_symbol_runner.py (interleaved), J′ determinizmi testleri, K′′ global limit + drop diagnostics, per-symbol strategy/detector. SIRADAKİ. Ön koşul: SORU X onayı (§6.4).
- B2e.1S — Synthetic multi-symbol validation (SORU R 1–14).
- B2e.2 — Walk-forward: D parametrik pencere, I fold üretimi, M train warmup, Q′ gap politikası.
- B2e.2S — Synthetic walk-forward validation (SORU R 7, 8).
- B2e.3 — Rapor: G′ + N + diagnostics + data_quality (profile, thresholds).
- B2e.real — Gerçek çok sembol gate (S′); veri birikimine bağlı.

Commit politikası: PO kısıtı gereği tek final commit (B2e kapanışında). İş ve test sırası fazlara göre ayrı; final commit mesajı tüm alt fazları listeler. Alt faz sonlarında commit YOK.

9. SIRADAKİ FAZLAR
B2e.1 (SORU X onayı sonrası) → B2e.1S → B2e.2 → B2e.2S → B2e.3 → B2e kapanışı → TEK commit.
B2e sonrası: strateji parametre optimizasyonu — B2e sonuçlarına göre.
B2e.real: çok sembol verisi birikince (SORU S′ kriterleri).

Örnek kullanım (mevcut CLI, B2d):
    python -m tests.manual.backtest_run --db data/mikov2.sqlite --symbol BTC_USDT --entry-window-ms 300000 --cooldown-ms 60000 --report b2d_single.json --equity-csv b2d_single_eq.csv
B2e CLI parametreleri (planlanan, B2e.1+): --symbols CSV, --train-ms, --test-ms, --step-ms, --data-quality-profile strict|lenient, --include-synthetic.

10. PROD İÇİN SONRAKİ ADIMLAR (B3)
Universe scanner'ı shadow runner'a bağla (otomatik Top5 rotasyon).
Micro-trigger'ı canlıya al (WS tick -> detector -> signal -> strategy).
Position manager'ı canlıya al (paper trading).
Alert entegrasyonu (Telegram/Discord).
Sigorta: 3-4 hafta paper trading -> gerçek para.

11. KİLİTLİ KARARLAR (Kümülatif)
Git/checkpoint:
Güvenilmeyen commit'ler local'de reset, remote'a force-push ile silinir. Önceki checkpoint: 7fb827848aee38897fcea9616d4ea898c294089a (REV9 DURUM + BAĞLAM, 2026-09-17).
Bu oturum checkpoint'i: <COMMIT_HASH> (B2e kapanışı; commit henüz atılmadı).
Protokol = yöntem, DURUM = içerik. Devir sırasında sadece bu dosya güncellenir; SOHBET-KAPANIS-PROTOKOLU.md sabit kalır.
B2d çoklu config: --config-a / --config-b.
B2d equity curve: JSON + CSV; PNG yok (SORU C: (B)).
§6.1 funding ceza + §6.2 emtia exclude: UYGULANDI (B2e.−1, 2026-09-21).
B2e plan kararları (SORU A′–W, tam liste §16): B2e.0/1/1S/2/2S/3/real faz kırılımı; commit tek.
SORU X (yeni): K′′ diagnostics için Strategy + PositionSimulator `last_rejection_reason` alanı (önerilen: (A)); onay bekliyor.

Mimari:
Mimari 30 coin limit + Top20 operasyonel limit — bilinçli trade-off.
Emtia/hisse exclude — constants.py EXCLUDED_SYMBOLS (Bkz §6.2).
Aşırı funding ceza — Bkz §6.1.
Contract size cache — bulk detail bir kez çekilir (1176 sembol).
Per-symbol max 1 pozisyon + multi-symbol concurrent; global concurrent config'ten TEST=3, PROD=2.
TP/SL exit 5s OHLCV high/low; taker fee 0.0002.
Strategy config default'u katı kalır (require_sweep/mss/fvg=True, entry_window_ms=15000); gevşetme CLI override ile (SORU B: (B)).
B2c backtest config: entry_window_ms=300000, üç kapı True, cooldown_ms=60000 (SORU A: (A), SORU B: (A)).
B2c TP/SL hesabı: SL = entry ∓ 0.5×ATR(14, 5s), TP = 2R.
B2c position sizing: risk-based, PROD=0.006 / TEST=0.008.
B2c entry price: signal bar close + slippage.
B2c çakışma çözümü: SL önce (konservatif).
B2c funding: opsiyonel bayrak, varsayılan kapalı.
B2c min SL floor: min_sl_distance_pct = 0.002×entry.
B2c fill slippage: entry_slippage_bps = 2.0.
B2c rapor: --report JSON.
B2d rapor şeması: { config{strategy,sim}, summary, metrics, equity_curve, engine, signal_counts, trades }; çoklu config: { config_a, config_b, comparison }.
B2d metrikleri: sharpe_annualized, profit_factor (kayıpsız → null), expectancy_r, avg_holding_sec, max_consecutive_losses.
B2d equity curve: JSON + CSV.
B2e.0 event modeli: tüm event'ler symbol + source_seq taşır (default geriye uyumlu).
B2e.0 stream_multi: J′ tie-break (ts_ms, event_type_rank, symbol, source_seq).
B2e.0 source_seq kaynağı: trades_ohlcv_1s.sec; orderbook_snapshots.id; tickers_snapshot.id.
B2e.0 PositionSimulator: per-symbol state dict; finalize(last_ts_ms, last_prices: dict); MTM equity (SORU L′′).
B2e.0 MTM semantiği (VARSAYIM): exit fee tahmini yok; sadece entry_fee + funding_paid + unrealized gross.
B2e.0 data_quality: gap_count = her delta > expected_interval (docs); eşik/profil B2e.3.
SWEEP semantiği: LONG <- SWEEP_DOWN, SHORT <- SWEEP_UP (stop-hunt reversal; wick_ratio 0.6).

Kod kuralları: Bkz AnaYasa REV5 §0.

SOHBET-KAPANIS format kuralları: her döküman/kod ayrı 4-backtick bloğu; blok içinde 3-backtick YASAK; kontrol checklist'i düz metin; kod değişikliği önerileri Protokol §7.4 şablonu (tam yol + eski hali + yeni hali + gerekçe) ile verilir. Test kapısı Bkz Protokol §7.5; öz-uyum Bkz Protokol §7.6; format Bkz Protokol §7.3.

PROTOKOL İHLALİ NOTU (2026-09-19): asistan aynı sohbette 4-backtick kuralını 3 kez ihlal etti; protokol format kuralı netleştirilerek kapatıldı.

12. DOSYA KONUMLARI
docs/DURUM.md — bu dosya.
docs/SOHBET-KAPANIS-PROTOKOLU.md — yöntem dökümanı (sabit).
docs/MikoV2-AnaYasa-REV5.md — 116 YAMA, kod kuralları.
docs/MikoV2-Proje-Tum-Moduller-REV5.md — modül pseudo.

B2e.−1 değişen/yeni:
src/data_layer/constants.py (YENİ) — EXCLUDED_SYMBOLS + EXCLUDED_SYMBOLS_VERSION.
src/data_layer/metrics_fetcher.py (DEĞİŞTİ) — funding ceza; excluded_symbols DI; candidate loop exclude.
src/data_layer/universe_service.py (DEĞİŞTİ) — ScanResult.excluded_symbols; EXCLUDED_SYMBOLS default; always_include exclude-koruması.
tests/unit/test_b2e_minus1_compliance.py (YENİ) — 15 test.

B2e.0 değişen/yeni:
src/backtest/replay_transport.py (DEĞİŞTİ) — event symbol + source_seq; stream_multi.
src/backtest/position_sim.py (DEĞİŞTİ) — per-symbol state; finalize dict; MTM equity.
src/backtest/data_quality.py (YENİ) — DataQualityReport + analyze_ohlcv_secs.
tests/unit/test_b2e0_infrastructure.py (YENİ) — 18 test.
tests/unit/test_position_sim.py (DEĞİŞTİ) — _ohlcv/_warm symbol param; test_global_concurrent_limit üç sembol ısıtıyor.

B2e.1 planlanan:
src/backtest/multi_symbol_runner.py (YENİ).
src/backtest/strategy.py (DEĞİŞECEK — SORU X sonrası last_rejection_reason).
src/backtest/position_sim.py (DEĞİŞECEK — SORU X sonrası last_rejection_reason).
tests/unit/test_backtest_multi.py (YENİ).

B2e.3 planlanan:
src/backtest/multi_report.py (YENİ).
tests/unit/test_backtest_walkforward.py (YENİ — B2e.2 + B2e.2S).

13. YENİ SOHBET NASIL BAŞLAR
Verilecek dosyalar:
DURUM.md (bu)
SOHBET-KAPANIS-PROTOKOLU.md
MikoV2-AnaYasa-REV5.md
MikoV2-Proje-Tum-Moduller-REV5.md
Açılış mesajı:
"DURUM.md v2.11'i okudun mu? B2e.1'den devam ediyoruz. İlk adım: SORU X (§6.4) — K′′ diagnostics için Strategy + PositionSimulator'a `last_rejection_reason` alanı (önerilen (A)). Onaylandıktan sonra multi_symbol_runner.py + strategy/position_sim minimal diff + tests/unit/test_backtest_multi.py üret. Sonra pytest tests/ -q --tb=short --maxfail=1 çalıştır; 783 PASS mevcut. Commit B2e kapanışında tek teslim; şimdi commit atma. SORU A′–W'yi yeniden sorma; SORU X yeni açıldı."

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
v2.4 (2026-09-19): B2c öncesi analiz; SWEEP yön fix; CLI override; protokol format kuralı.
v2.5 (2026-09-20): Protokol entegrasyonu (SSOT, teslim modları, bağlam, soru formatı, test kapısı, öz-uyum).
v2.6 (2026-09-20): SSOT temizliği; versiyon atıf yasağı; protokol v3.2 uyum.
v2.7 (2026-09-20): B2c başlangıç kriterleri (SORU A–F) kilitlendi.
v2.8 (2026-09-20): B2c kapandı; SORU G/H; 733 test PASS; async telemetry notu.
v2.9 (2026-09-20): B2d kapandı; reporting.py + CLI genişlemesi; 750 PASS.
v2.10 (2026-09-21): B2e planı kilitli; SORU A′–W (§16); kod başlamadı.
v2.11 (2026-09-21): B2e.−1 kapandı (constants.py + funding ceza + exclude; 15 test). B2e.0 kapandı (replay_transport symbol/source_seq/stream_multi + position_sim per-symbol + finalize dict + MTM + data_quality.py; 18 test). Toplam 783 PASS. SORU X yeni açıldı (§6.4) — B2e.1 öncesi onay bekliyor. Test sayısı düzeltmesi: B2e.0 dosyası 15 değil, 18 test; B2e.−1 dosyası 13 değil, 15 test.

16. B2e PLAN KARARLARI (KİLİTLİ — SORU A′–W)
Bu bölüm B2e plan kararlarının SSOT sahibidir. Diğer bölümler bu bölüme atıf yapar.
Bağımsız doğrulama geçmişi: 4 tur bağımsız ajan değerlendirmesi. SORU C revize (Interleaved); SORU L revize (sıra + MTM); SORU K risk notu; SORU Q′ çok katmanlı.

SORU A′ — §6.1/§6.2 fix'lerinin konumu: B2e.−1'de kodlanır ve test edilir; commit B2e kapanışında tek. UYGULANDI (§6.1, §6.2).
SORU B — PositionSimulator multi-symbol: (A) gerçek multi-symbol; per-symbol dict; finalize dict; funding per-symbol. UYGULANDI (B2e.0).
SORU C (REVİZE) — Topoloji: (A) Interleaved (heapq.merge, tek engine.run, per-symbol strategy/detector, tek sim). B2e.1'de runner olarak kodlanır.
SORU D — Walk-forward pencere ölçeği: (A) Parametrik (train_ms/test_ms/step_ms CLI).
SORU E — Top20 kaynağı: (A) DB'de mevcut semboller; CLI --symbols; §6.2 exclude önce.
SORU F — Dosya yolları: multi_symbol_runner.py, multi_report.py, test_backtest_multi.py, test_backtest_walkforward.py; CLI mevcut backtest_run.py genişler. NOT: B2e.−1 için ek test dosyası (test_b2e_minus1_compliance.py) ve B2e.0 için test_b2e0_infrastructure.py eklendi (faz ayrımı korunur).
SORU G′ — Rapor şeması: iki katmanlı + diagnostics (schema_version, multi_symbol_capable, synthetic_multi_symbol_validated, real_multi_symbol_validated, single_symbol_real_walkforward_executed, real_data_symbols, data_quality{profile,completeness,max_gap_ms,gaps}, ticker_coverage, depth_coverage, global_limit_exercised, dropped_entries_count, dropped_entries(reason+symbol+ts), excluded_symbols, fold_count, single_fold_warning, walk_forward_claim, fold_windows).
SORU H — Global limit drop: (A) FIFO; ts_ms ASC; tie-break (event_type_rank, symbol, source_seq); exit önce işlenir.
SORU I — Walk-forward fold: I.1=(B) ≥1 fold; I.2=(A) step_ms default = test_ms; I.3=(A) fail-fast.
SORU J′ — Merge determinizmi: (A) (ts_ms, event_type_rank, symbol, source_seq); OHLCV=0/Depth=1/Ticker=2. UYGULANDI (B2e.0 stream_multi).
SORU K′′ — Global limit reject: attempt-based cooldown; reason: global_limit_full / per_symbol_max_position / cooldown_active; risk notu: canlı parity backtest-only assumption. B2e.1'de kodlanır (SORU X onayı sonrası).
SORU L′′ — Equity/funding sözleşmesi: L.1=(B) her OHLCV close'unda portföy MTM; L.2=(A) finalize son fiyat + WARNING; L.3=(A) funding per-symbol timeline, ticker event günceller. İşlem sırası: exit/TP/SL → funding → MTM → entry sizing → entry execution. UYGULANDI (B2e.0 position_sim).
SORU M — Train = warmup.
SORU N — Trade/rapor şeması: additive; window_id + fold_id.
SORU O — §6.2 exclude listesi: explicit (constants.py); versiyonlanır; universe_service + CLI. UYGULANDI (B2e.−1).
SORU P — Tek sembollü veriyle doğrulama: (E) karma.
SORU Q′ — Veri kalitesi: çok katmanlı (fail-fast / WARNING / strict-lenient). B2e.0 temel algılama; eşikler B2e.3.
SORU R — Synthetic fixture: 18 senaryo.
SORU S′ — Gerçek multi-symbol gate: ≥4 sembol, ≥30 gün, completeness ≥%95, max gap ≤30dk, max_concurrent ≥3, dropped>0, fold≥2, ticker doğrulanmış, exclude geçmiş.
SORU T — B2e kapanış tanımı: "capable + synthetic validated + single-symbol real walk-forward". B2e.real ayrı gate.
SORU U — source_seq kaynağı: DB rowid (orderbook_snapshots.id, tickers_snapshot.id, trades_ohlcv_1s.sec). UYGULANDI (B2e.0).
SORU V — Funding rate kaynağı: tickers_snapshot.funding_rate. UYGULANDI (B2e.0 per-symbol).
SORU W — DURUM güncelleme: plan snapshot. (B2e.−1 ve B2e.0 kapanışında v2.11 güncellemesi yapıldı; commit hâlâ B2e kapanışında tek.)

SON