MikoV2 — DURUM
Versiyon: v2.9
Tarih: 2026-09-20
Durum: B2d kapandı (750 test PASS). reporting.py (Sharpe, PF, expectancy, equity curve JSON+CSV) + --config-a/b + --equity-csv + genişletilmiş --report şeması. §6.1/§6.2 B2d'de uygulanmadı; B2e öncesi/sırasında ayrı commit olarak ele alınacak. Sıradaki: B2e (multi-symbol + walk-forward).
Amaç: Yeni sohbete başlarken bağlamı hızlıca aktarmak.
PO: Eser Göbekli
Önceki: REV7 (FAZ 6/7/8 kapanış) → REV9 (dashboard + universe + shadow collector + backtest B0.x-B1) → v2.0 (protokol entegrasyonu) → v2.1 (BAGLAM.txt entegrasyonu) → v2.2 (arşiv referansı temizliği) → v2.3 (B1/B2a/B2b doğrulama + DB transfer) → v2.4 (B2c öncesi analiz + SWEEP yön fix) → v2.5 (protokol entegrasyonu) → v2.6 (SSOT temizliği) → v2.7 (B2c başlangıç kriterleri kilitlendi) → v2.8 (B2c kapanış + SORU G/H kilitli karar + async telemetry notu) → v2.9 (B2d kapanış: reporting.py + --config-a/b + --equity-csv + genişletilmiş --report; 750 test PASS)

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
DB şeması: orderbook_snapshots, trades_ohlcv_1s, tickers_snapshot
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

2. TEST DURUMU
Toplam: 750 test PASS (unit 430 + integration 100 + chaos 61 + backtest 159 = 750). (B2d: 17 yeni test.)
Komut: pytest tests/ -q --tb=no
Yakalanan kritik bug'lar: WS dead silent (pong data maskesi), mp.Queue blocking event loop, DROP_OLDEST -> DROP_NEWEST race, 429 circuit breaker eksikliği, SWEEP yön mapping tersliği (Bkz §7), SORU G/H slippage/SL floor (B2c, Bkz §7).
Not: test_drop_oldest_preserves_newest full-suite yükü altında mp.Queue feeder timing kaynaklı tekil/transient FAIL üretebildi; izole koşuda (12/12) ve son full koşuda (750 PASS) temiz. Test, polling + 0.5s deadline ile düzeltildi (Bkz §6.3 notu). İzlenmeye devam.

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

4. KRİTİK MODÜLLER
| Modül|Görev|
| ---|---|
| src/data_layer/mexc_ws.py|sub.depth + sub.deal WS + watchdog|
| src/data_layer/mexc_rest.py|Snapshot + contract_size + funding|
| src/data_layer/metrics_fetcher.py|1176 sembol bulk filtre + skorlama|
| src/data_layer/universe_service.py|Universe scan orkestrasyonu|
| src/storage/mark_price_cache.py|WS -> REST mark price cache|
| src/storage/equity_tracker.py|60s + close-triggered equity snap|
| src/dashboard/app.py + routes.py|aiohttp.web server (Bkz §3: URL + endpoint)|
| src/dashboard/static/index.html|4 panel + Chart.js + SSE|
| src/backtest/replay_transport.py|SQLite 3-tablo merge -> stream|
| src/backtest/engine.py|Event dispatch engine|
| src/backtest/signal_detector.py|SWEEP/MSS/FVG/OTE tespiti (5s)|
| src/backtest/strategy.py|Sinyalleri entry kararına dönüştürür|
| src/backtest/position_sim.py|B2c — entry/TP/SL simülasyon + PnL|
| src/backtest/reporting.py|B2d — genişletilmiş rapor (Sharpe, PF, expectancy, equity curve)|
| tests/manual/backtest_run.py|Backtest CLI runner (CLI override: --no-require-sweep/-mss/-fvg; B2c: --report, --include-funding; B2d: --config-a/b, --equity-csv)|

5. UNIVERSE SCANNER KARARI
Sonuç: 1176 sembol -> 3 aşamalı filtre -> Top20 (operasyonel limit; mimari üst sınır 30 coin için Bkz §11).
Aşama 1 (Fatal): oi_usd > 1M + volume24 > 10M + 0.3 < spread < 20 bps.
Aşama 2 (Skor): volume %40 + OI %30 + funding %30.
Aşama 3 (Limit): Top5 WS bağlı, Top10 watch, Top20 takip.
Örnek Top5 (2026-09-17): BTC_USDT, SOL_USDT, XAUT_USDT, XRP_USDT, ONE_USDT. Not: XAUT emtia tokeni, Bkz §6.2 karar gereği exclude edilecek.

6. AÇIK SORUNLAR (FIX bekliyor)
6.1 Funding rate aşırı değerler "fırsat" olarak görülüyor
Sorun: ONE_USDT funding=-2%, LSK_USDT funding=-0.43% gibi değerler Top10'a giriyor. Tehlikeli — muhtemelen likidasyon kaskadı veya exchange-spesifik durum.
Karar: Skorlamada aşırı funding CEZA almalı:
    f_abs = abs(s.funding_rate)
    if f_abs > 0.005:  # 0.5% üstü = ceza
        f_score = -1.0
    else:
        f_score = f_abs / 0.005
Durum: Karar alındı, B2c'de uygulanmadı, B2d'de uygulanmadı. Sıradaki iş B2e; bu fix B2e öncesi/sırasında ayrı commit olarak ele alınacak (PO kararı bekliyor; önceki SORU A=(B) "B2d sonrası" revize edildi).

6.2 Emtia token'ları universe'e sızıyor
Sorun: XAUT_USDT (Tether Gold), SILVER_USDT, UKOIL_USDT, USOIL_USDT, SPCXSTOCK_USDT gibi semboller kripto değil — tokenlaştırılmış emtia/hisse. Whale-radar mantığı bunlarda çalışmaz.
Karar: Exclude listesi eklenecek:
    EXCLUDED_EXACT = {
        "XAUT_USDT", "XAU_USDT", "XAG_USDT",
        "SILVER_USDT", "GOLD_USDT",
        "UKOIL_USDT", "USOIL_USDT",
        "SPCXSTOCK_USDT",
    }
Durum: Karar alındı, B2c'de uygulanmadı, B2d'de uygulanmadı. Sıradaki iş B2e; bu fix B2e öncesi/sırasında ayrı commit olarak ele alınacak (PO kararı bekliyor; önceki SORU A=(B) "B2d sonrası" revize edildi).

6.3 async_telemetry_queue _bridge_loop DROP_NEWEST sapması
Sorun: threaded_bridge=True yolunda mp_queue.put queue.Full dönerse, item deque(maxlen) başına appendleft edilirken deque sağdan (en yeni) eleman tahliye eder. DROP_OLDEST semantiği dar bir yarış penceresinde DROP_NEWEST davranışına sapar.
Etki alanı: Sadece threaded_bridge=True (production default). Testler threaded_bridge=False kullandığı için bu yol test kapsamı dışı.
Karar: FAZ sonrası — B2c/B2d kapsamı dışı, ayrı commit.
Doğrulama: KOD İNCELEME (2026-09-20).
Durum: Not edildi, FAZ sonrasına bırakıldı.

7. BACKTEST İLERLEME
| İş|Durum|
| ---|---|
| B1 — ReplayTransport + engine|Doğrulandı (97.8 saat / 4.08s)|
| B2a — Signal detector|Doğrulandı (8 sinyal tipi)|
| B2b — Strategy adapter|Doğrulandı (SWEEP yön bug'ı fix'lendi, test 10/10; semantik Bkz §11)|
| B2c — Position simulator + PnL|Kapandı (16 test, SORU G/H sonrası 44 trade)|
| B2d — Backtest runner + rapor|Kapandı (17 test; reporting.py + --config-a/b + --equity-csv + genişletilmiş --report)|
| B2e — Multi-symbol backtest + walk-forward|Sıradaki|

Baz test sonuçları (2026-09-19, BTC_USDT, 97.8 saat):
Events: 169,205
OHLCV: 161,573
Depth: 5,855
Ticker: 1,777
Entries: 5 (baz config: 15s pencere, 3 kapı — referans değeri)
Signals: MSS_DOWN 1474, MSS_UP 1512, FVG_BEARISH 89, FVG_BULLISH 110, OTE_LONG 3349, OTE_SHORT 3598, SWEEP_UP 116, SWEEP_DOWN 108
Time: 4.08s

B2c ÖNCESİ ANALİZ (2026-09-19, tamamlandı):
Problem: Baz config (require_sweep+mss+fvg=True, entry_window_ms=15000) sadece 5 entry üretti.
Yöntem: strategy.py default'ları katı bırakıldı; gevşetme deneyleri backtest_run.py'ye eklenen CLI override ile yapıldı (--no-require-sweep / --no-require-mss / --no-require-fvg).
Deney sonuçları (BTC_USDT, 97.8 saat):
| Varyant|Config|Entry (fix öncesi)|Entry (SWEEP yön fix sonrası)|
| ---|---|---|---|
| Baz|15s, 3 kapı|5|tekrar koşulmadı (referans)|
| A|300s, 3 kapı|230|187 (~31-37 setup)|
| B|300s, FVG kapalı|1123|tekrar koşulmadı (elenmiş varyant)|
Bulgular:
1. Darboğaz pencereydi: 15s -> 300s entry sayısını ~46x artırdı.
2. FVG gerçek kalite kapısı: FVG kapalıyken ~224 sweep'in neredeyse hepsi setup'a dönüştü (1123 entry); FVG kapısı setup'ları ~%80 filtreledi.
3. Küme etkisi: cooldown 60s < pencere 300s olduğundan 1 setup ~5-6 entry üretir; B2c'nin per-symbol "max 1 pozisyon" kuralı bunu baskılar (entry sayısı != trade sayısı).
4. Yön flip'leri 2-6 saatte bir; kârlılığı B2c PnL yargılayacak.
KARAR (kilitli, SORU A: (A) + SORU B: (A)): B2c config = Varyant A: entry_window_ms=300000, require_sweep/mss/fvg=True, cooldown_ms=60000.

KRİTİK BUG — SWEEP YÖN MAPPING TERSLİĞİ:
Belirti: test_strategy.py 4 test FAIL (assert 0 == 1).
Kök neden: strategy.py'da long_ok <- has_sweep_up, short_ok <- has_sweep_down (momentum yorumu). Oysa SWEEP semantiği (Bkz §11), test beklentileri ve AnaYasa micro_trigger ters yön zinciri gerektirir.
Düzeltme: strategy.py _try_entry içinde iki satır swap (fix forward). test_strategy.py 10/10, full suite 733 PASS.
Etki: Fix öncesi 230 entry'lik analiz geçersiz sayıldı; fix sonrası Varyant A yeniden koşuldu: 187 entry. Doğrulama: aynı ts'lerde yönler beklenen şekilde flip oldu (örn. 2026-09-16 20:54:10 LONG -> SHORT).

B2c SONRASI ANALİZ (2026-09-20, BTC_USDT, 97.8 saat):
Config: --entry-window-ms 300000 --cooldown-ms 60000 (üç kapı True).
Sonuç: 187 entry → 44 tamamlanan trade.
Exit dağılımı: 9 TP (R=+2.00) / 34 SL (R=-1.00) / 1 END_OF_BACKTEST (R=-0.55).
win_rate = %20.45 (9/44).
avg_r_multiple = -0.3761.
max_drawdown_pct = %20.08.
total_return_pct = -%17.98 (final_equity 8201.82 / initial 10000).
Funding etkisi (--include-funding): ≈ 0 USDT (LONG/SHORT flip'leri birbirini siliyor).
BULGU: Bu 97.8 saatlik BTC örneklemde strateji kârlı değil. 2R/1R setup için breakeven win_rate %33.3; ölçülen %20.45 bu eşiğin altında.
YORUM: Sample size küçük (44 trade), tek rejim, tek sembol. B2e (multi-symbol walk-forward) karar için gerekli. Strateji revizyonu bu fazın kapsamı dışında.

B2c SORU G/H (B2c sırasında kilitlenen ek kararlar):
SORU G: (C) min_sl_distance_pct=0.002 floor — ATR 5s zaman diliminde çok küçük olduğu için (BTC'de ~5.84 USD, SL mesafesi 2.92 USD) fill slippage > SL mesafesi oluyordu; SL floor ile alt sınır konuldu. AnaYasa kilitli kararı (sl_buffer_atr=0.5) revize edilmez; alt sınır üstüne katman eklenir.
SORU H: (A) entry_slippage_bps=2.0 — fill kayması bps tabanlı; AnaYasa entry_guard 0.25% bir REDDETME eşiğidir (limit emir iptal), fill kayması değildir. Önceki kod entry_guard_pct=0.0025'i slippage olarak kullanıyordu (bug), düzeltildi.

B2d SONUÇLARI (2026-09-20, kilitli):
SORU A: (B) §6.1/§6.2 B2d'de uygulanmadı; B2e öncesi/sırasında ayrı commit (revize; PO kararı bekliyor).
SORU B: (A) Çoklu config karşılaştırma --config-a / --config-b (flat JSON override); tek --report JSON'unda config_a + config_b + comparison blokları.
SORU C: (B) Equity curve JSON (rapor içinde) + CSV (--equity-csv); PNG yok.
Yeni dosya: src/backtest/reporting.py
  - compute_metrics(trades, initial_equity) → ExtendedMetrics (sharpe_annualized, profit_factor, expectancy_r, avg_holding_sec, max_consecutive_losses)
  - build_equity_curve(trades, initial_equity) → list[EquityPoint]
  - write_equity_csv(path, curve)
Yeni test dosyası: tests/unit/test_backtest_reporting.py (17 test)
Genişletilmiş --report şeması (tek config):
  { config{strategy,sim}, summary, metrics, equity_curve, engine, signal_counts, trades }
Çoklu config:
  { config_a{...}, config_b{...}, comparison{delta_*} }
VARSAYIM (PO teyidi bekleniyor):
  - Sharpe yıllıklandırma: trades_per_year = n / span_years, risk_free_rate=0.0
  - profit_factor tanımsız (kayıp yok) → null (JSON uyumlu; Infinity yazılmaz)
  - Config override flat JSON: StrategyConfig ve PositionSimConfig alan adları; bilinmeyen alan → hata (SystemExit)

8. B2e — SIRADAKİ İŞ DETAYI

Kapsam: Multi-symbol backtest (Top20) + walk-forward (3 ay train / 1 ay test rolling).
Ön koşul: §6.1/§6.2 fix'lerinin B2e öncesi/sırasında ayrı commit olarak kapatılması (PO kararı bekliyor).

B2e KAPSAMI:
- Multi-symbol: Top20 sembol üzerinde aynı anda backtest.
- Walk-forward: 3 ay train / 1 ay test rolling.
- Config: B2c'den miras (entry_window_ms=300000, cooldown_ms=60000, üç kapı True) baz alınır; varyantlar B2e içinde denenir.
- Reuse: ReplayTransport, BacktestEngine, SignalDetector, Strategy, PositionSimulator, reporting.py.
- Rapor: reporting.py metrikleri sembol başına + toplam + karşılaştırma.

B2e DIŞI (B2e sonrası planlanacak):
- Strateji parametre optimizasyonu (grid/random search vb.) — B2e sonrası ayrı faz.
- Canlıya geçiş (B3, Bkz §10).

Uygulama tasarımı (devralınan, B2c/B2d'den):
- Per-symbol limit 1 pozisyon; global concurrent TEST=3, PROD=2.
- TP/SL exit: 5s OHLCV high/low; çakışma çözümü SORU D (SL önce).
- Fee: taker 0.0002, maker 0.0.
- Slippage: 2 bps (SORU H).
- Min SL floor: 0.002×entry (SORU G).
- Funding: opsiyonel (SORU E).

9. SIRADAKİ FAZLAR
B2e (sıradaki): Multi-symbol backtest + walk-forward (Bkz §8).
Örnek kullanım (mevcut CLI):
    python -m tests.manual.backtest_run --db data/mikov2.sqlite --symbol BTC_USDT --entry-window-ms 300000 --cooldown-ms 60000 --report b2d_single.json --equity-csv b2d_single_eq.csv
Çoklu config:
    python -m tests.manual.backtest_run --db data/mikov2.sqlite --symbol BTC_USDT --config-a '{"entry_window_ms":300000}' --config-b '{"entry_window_ms":15000}' --report b2d_cmp.json
B2e sonrası: strateji parametre optimizasyonu — B2e sonuçlarına göre planlanacak.

10. PROD İÇİN SONRAKİ ADIMLAR (B3)
Universe scanner'ı shadow runner'a bağla (otomatik Top5 rotasyon).
Micro-trigger'ı canlıya al (WS tick -> detector -> signal -> strategy).
Position manager'ı canlıya al (paper trading).
Alert entegrasyonu (Telegram/Discord).
Sigorta: 3-4 hafta paper trading -> gerçek para.

11. KİLİTLİ KARARLAR (Kümülatif)
Git/checkpoint:
Güvenilmeyen commit'ler local'de reset, remote'a force-push ile silinir. Önceki checkpoint: 7fb827848aee38897fcea9616d4ea898c294089a (REV9 DURUM + BAĞLAM, 2026-09-17).
Bu oturum checkpoint'i: <COMMIT_HASH> (B2d kapanış; reporting.py + backtest_run.py wiring + test_backtest_reporting.py; 750 test PASS ile doğrulandı).
Protokol = yöntem, DURUM = içerik. Devir sırasında sadece bu dosya güncellenir; SOHBET-KAPANIS-PROTOKOLU.md sabit kalır.
B2d çoklu config: --config-a / --config-b (flat JSON override); tek --report JSON'unda config_a + config_b + comparison (SORU B: (A)).
B2d equity curve: JSON + CSV; PNG yok (SORU C: (B)).
§6.1 funding ceza + §6.2 emtia exclude: B2d'de uygulanmadı; B2e öncesi/sırasında ayrı commit (SORU A: (B) revize; PO kararı bekliyor).

Mimari:
Mimari 30 coin limit + Top20 operasyonel limit — bilinçli trade-off (100 coin için mimari değişiklik gerek; Top20 seçimi için Bkz §5).
Emtia/hisse exclude — Bkz §6.2.
Aşırı funding ceza — Bkz §6.1.
Contract size cache — bulk detail bir kez çekilir (1176 sembol).
Per-symbol max 1 pozisyon + multi-symbol concurrent; global concurrent config'ten TEST=3, PROD=2 (Bkz §8).
TP/SL exit 5s OHLCV high/low; taker fee 0.0002.
Strategy config default'u katı kalır (require_sweep/mss/fvg=True, entry_window_ms=15000); gevşetme deneyleri CLI override ile yapılır, default koda gömülmez (SORU B: (B)).
B2c backtest config: entry_window_ms=300000, üç kapı True, cooldown_ms=60000 (SORU A: (A), SORU B: (A)).
B2c TP/SL hesabı: SL = entry ∓ 0.5×ATR(14, 5s), TP = 2R (Bkz §7 SORU A: (A)).
B2c position sizing: risk-based, PROD=0.006 / TEST=0.008 (Bkz §7 SORU B: (A)).
B2c entry price: signal bar close + slippage (Bkz §7 SORU C: (A)).
B2c çakışma çözümü: SL önce (konservatif) (Bkz §7 SORU D: (A)).
B2c funding: opsiyonel bayrak, varsayılan kapalı (Bkz §7 SORU E: (C)).
B2c min SL floor: min_sl_distance_pct = 0.002×entry — SL mesafesi ATR tabanlı hesaptan sonra floor uygulanır (Bkz §7 SORU G: (C)).
B2c fill slippage: entry_slippage_bps = 2.0 — fill kayması bps tabanlı; AnaYasa entry_guard 0.25% reddetme eşiğidir, fill kayması değildir (Bkz §7 SORU H: (A)).
B2c rapor: --report JSON (summary + engine + signal_counts + trades). Alanlar: initial_equity, final_equity, total_trades, win_rate, avg_r_multiple, max_drawdown_pct, total_return_pct.
B2d rapor şeması: { config{strategy,sim}, summary, metrics, equity_curve, engine, signal_counts, trades } (tek config); { config_a, config_b, comparison } (çoklu config).
B2d metrikleri: sharpe_annualized, profit_factor (kayıpsız → null), expectancy_r, avg_holding_sec, max_consecutive_losses.
B2d equity curve: JSON (raporda) + CSV (--equity-csv); çoklu config'te <stem>.config_a.csv / <stem>.config_b.csv.
SWEEP semantiği: LONG <- SWEEP_DOWN, SHORT <- SWEEP_UP (stop-hunt reversal; wick_ratio 0.6 = rejection). Testler bu semantiği belgeler.

Kod kuralları: Bkz AnaYasa REV5 §0.

SOHBET-KAPANIS format kuralları: her döküman/kod ayrı 4-backtick bloğu; blok içinde 3-backtick YASAK; kontrol checklist'i düz metin; kod değişikliği önerileri Protokol §7.4 şablonu (tam yol + eski hali + yeni hali + gerekçe) ile verilir. Test kapısı Bkz Protokol §7.5; öz-uyum Bkz Protokol §7.6; format Bkz Protokol §7.3.

PROTOKOL İHLALİ NOTU (2026-09-19): asistan aynı sohbette 4-backtick kuralını 3 kez ihlal etti (checklist ve kod bloklarında 3-backtick kullandı); protokol format kuralı (Bkz Protokol §7.3) netleştirilerek kapatıldı.

12. DOSYA KONUMLARI
docs/DURUM.md — bu dosya (proje içeriği, devir noktası).
docs/SOHBET-KAPANIS-PROTOKOLU.md — projeden bağımsız yöntem dökümanı.
docs/MikoV2-AnaYasa-REV5.md — 116 YAMA, kod kuralları (referans).
docs/MikoV2-Proje-Tum-Moduller-REV5.md — modül pseudo (referans).
src/backtest/reporting.py — B2d genişletilmiş raporlama (Sharpe, PF, expectancy, equity curve).
tests/unit/test_backtest_reporting.py — B2d raporlama unit testleri (17 test).

13. YENİ SOHBET NASIL BAŞLAR
Verilecek dosyalar:
DURUM.md (bu)
SOHBET-KAPANIS-PROTOKOLU.md
MikoV2-AnaYasa-REV5.md
MikoV2-Proje-Tum-Moduller-REV5.md
Açılış mesajı:
"DURUM.md'yi okudun mu? B2e'ye başla: §8 tasarıma göre multi-symbol backtest + walk-forward yap. Ön koşul: §6.1/§6.2 fix'leri (B2e öncesi/sırasında ayrı commit). Reuse: ReplayTransport, BacktestEngine, SignalDetector, Strategy, PositionSimulator, reporting.py. Testler 750 PASS."

14. UNFROZEN BEYANI
FROZEN YOK.
Her satır sorgulanabilir.
Yeni YAMA 369+ açık.
Blind kabul YASAK.

15. VERSİYON
v1.0 (REV9, 2026-09-17): Orijinal REV9 durum dökümanı. FAZ 0-9 kapandı, universe scanner + shadow collector + backtest B0.x-B1 tamamlandı. B2c sırada.
v2.0 (2026-09-19): Protokol entegrasyonu. SOHBET-KAPANIS (projeden bağımsız) sisteme eklendi. Git checkpoint kararı ve güvenilmeyen B2c/B2d deneme commit'lerinin (f714665 -> 6199ae2) force-push ile temizlenmesi (checkpoint 7fb8278) kaydedildi.
v2.1 (2026-09-19): BAGLAM.txt entegrasyonu ve kaldırılması.
v2.2 (2026-09-19): Arşiv referansı temizliği.
v2.3 (2026-09-19): B1/B2a/B2b doğrulama + DB transfer yöntemi. Gerçek DB üzerinde test yapıldı (97.8 saat / 4.08s). SWEEP bug tespit edildi ve düzeltildi (push bekliyor). tmpfiles.org transfer yöntemi eklendi.
v2.4 (2026-09-19): B2c öncesi analiz tamamlandı. (1) Config gevşetme deneyleri: baz 5 entry -> Varyant A (300s pencere, 3 kapı) fix sonrası 187 entry (~31-37 setup); FVG'nin kalite kapısı olduğu kanıtlandı; B2c config kilitlendi (300s, 3 kapı, cooldown 60s). (2) SWEEP yön mapping tersliği bulundu ve fix forward ile düzeltildi (LONG <- SWEEP_DOWN, SHORT <- SWEEP_UP); 4 test FAIL -> 717 PASS. (3) backtest_run.py'ye --no-require-sweep/-mss/-fvg CLI override eklendi. (4) Protokol format kuralları: her döküman/kod ayrı 4-backtick bloğu, checklist düz metin, kod değişikliği şablonu; 4-backtick ihlali not edildi.
v2.5 (2026-09-20): Protokol entegrasyonu (SSOT, teslim modları, bağlam takibi, soru formatı, dosya isteme, test kapısı, öz-uyum, kaçırma kalıbı, protokol bakımı) DURUM.md'ye atıflarla eklendi.
v2.6 (2026-09-20): SSOT temizliği, versiyon atıf yasağı düzeltmesi, test hesabı ve checkpoint placeholder fix, protokol v3.2 ile uyum.
v2.7 (2026-09-20): B2c başlangıç kriterleri netleştirildi. §8'e 6 kilitli karar işlendi (SORU A-F): TP/SL hesabı (0.5×ATR SL, 2R TP), position sizing (risk-based PROD=0.006/TEST=0.008), entry price (signal bar close + slippage), TP/SL çakışma (SL önce konservatif), funding (opsiyonel bayrak --include-funding), multi-symbol kapsamı (tasarım destekler, test tek-sembol). §11 kilitli kararlara ilgili maddeler eklendi. B2d CLI planı --include-funding ile güncellendi.
v2.8 (2026-09-20): B2c kapandı. src/backtest/position_sim.py + 16 test eklendi. SORU G (min_sl_distance_pct=0.002) + SORU H (entry_slippage_bps=2.0) B2c sırasında tespit edilen slippage/SL floor bug'ları için kilitlendi. Gerçek DB koşusu (BTC_USDT, 97.8h): 44 trade, win_rate %20.45, avg_R -0.3761, MDD %20.08, total_return -%17.98 — bu örneklemde strateji kârlı değil (breakeven %33.3 altı). 733 test PASS. async_telemetry _bridge_loop DROP_NEWEST sapması §6.3'e eklendi (FAZ sonrası, B2c kapsamı dışı). async_telemetry testi polling + 0.5s deadline ile düzeltildi. §8 B2d detayına geçti.
v2.9 (2026-09-20): B2d kapandı. src/backtest/reporting.py + tests/unit/test_backtest_reporting.py (17 test) + backtest_run.py genişletildi (--config-a/--config-b flat JSON override, --equity-csv, genişletilmiş --report: config + metrics + equity_curve). SORU A: (B) §6.1/§6.2 B2d sonrası ayrı commit — PO B2e'ye geçiyor, fix'ler B2e öncesi/sırasında ele alınacak (revize). SORU B: (A) tek JSON'da config_a + config_b + comparison. SORU C: (B) equity curve JSON+CSV; PNG yok. 750 test PASS. §9 sıradaki faz B2e. §13 açılış mesajı B2e'ye güncellendi.

SON