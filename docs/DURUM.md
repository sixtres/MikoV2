MikoV2 — DURUM
Versiyon: v2.4
Tarih: 2026-09-19
Durum: B2c öncesi analiz tamamlandı (config gevşetme deneyi + SWEEP yön fix'i, 717 test PASS). B2c (Position Simulator) aşamasına geçiliyor.
Amaç: Yeni sohbete başlarken bağlamı hızlıca aktarmak.
PO: Eser Göbekli
Önceki: REV7 (FAZ 6/7/8 kapanış) → REV9 (dashboard + universe + shadow collector + backtest B0.x-B1) → v2.0 (protokol entegrasyonu) → v2.1 (BAGLAM.txt entegrasyonu) → v2.2 (arşiv referansı temizliği) → v2.3 (B1/B2a/B2b doğrulama + DB transfer) → v2.4 (B2c öncesi analiz + SWEEP yön fix + protokol v2.3)

0. ÇALIŞMA YÖNTEMİ
MikoV2 — MEXC Futures (vadeli) kripto trading botu. Kağıt-öncelikli tasarım + test odaklı geliştirme.
Stack: Python 3.10 + asyncio + mp.Queue + Numba + SQLite WAL + Parquet + aiohttp.web
Runtime: Google Cloud VM (e2-micro, Always Free), 7/24.
Process model: 3x10 WS process + REST gateway single process + supervisor.
Python sürümü: VM 3.12, lokal 3.10. Hedef minimum: 3.10 (3.11+ syntax YASAK).
Geliştirme döngüsü: Local'de (Windows/PS) kodlama ve test (pytest), VM'de (eser_gobekli@mikov2-collector-1) çalıştırma.
GitHub base URL: https://github.com/sixtres/MikoV2 (dosya isteme protokolü için referans; SOHBET-KAPANIS §6)
Devir protokolü: SOHBET-KAPANIS-PROTOKOLU.md (v2.3, projeden bağımsız yöntem dökümanı). Devir sırasında bu dosya (DURUM.md) güncellenir; protokol sabit kalır.
DB yolu (VM): /home/eser_gobekli/MikoV2/data/mikov2.sqlite
DB şeması: orderbook_snapshots, trades_ohlcv_1s, tickers_snapshot

VM'DEN LOCAL'E DOSYA TRANSFERİ (BAĞLAYICI)
Google Cloud Console web SSH terminalinde scp çalışmıyor. Kullanılan yöntem:
    VM'de dosyayı sıkıştır: tar -czf dosya.tar.gz dosya
    curl -F "file=@dosya.tar.gz" https://tmpfiles.org/api/v1/upload
    Dönen URL'ye /dl/ ekle, tarayıcıdan indir.
    Local'de tar -xzf dosya.tar.gz ile aç.
Not: transfer.sh, 0x0.st kapalı/kısıtlı (2026-09-19 itibariyle).

PROJE ANAYASASI (kod kuralları, bağlayıcı)
Python 3.10 hedef — 3.11+ syntax YASAK (except*, TaskGroup).
Global state YASAK — DI zorunlu (Y-353).
f-string log YASAK — %s placeholder.
"from .." boşluklu zorunlu — syntax hatası önleme.
Test yazmadan önce syntax kontrol; her kod bloğundan sonra pytest.
Blind kabul YASAK; her satır sorgulanabilir.

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

2. TEST DURUMU
Toplam: 717 test PASS (unit 397 + integration 100 + chaos 61 + backtest/unit eklemeleri).
Komut: pytest tests/ -q --tb=no
Yakalanan kritik bug'lar: WS dead silent (pong data maskesi), mp.Queue blocking event loop, DROP_OLDEST -> DROP_NEWEST race, 429 circuit breaker eksikliği, SWEEP yön mapping tersliği (v2.4, detay §7).
Not: test_drop_oldest_preserves_newest full-suite yükü altında mp.Queue feeder timing kaynaklı tekil/transient FAIL üretebildi; izole koşuda (12/12) ve son full koşuda (717 PASS) temiz. İzlenmeye devam.

3. RUNTIME — VM'DE AKTİF OLAN
Shadow collector (systemctl status miko-collector):
tests/shadow/runner.py — servis olarak çalışıyor, Restart=always.
3 veri kanalı:
L2 depth — orderbook_snapshots (60s interval, 500 seviye)
Trade OHLCV 1s — trades_ohlcv_1s (USDT-normalized, CVD için)
Tickers — tickers_snapshot (60s interval, OI + funding)
WS data-starvation watchdog aktif (90s data gelmezse restart).
Veritabanı: /home/eser_gobekli/MikoV2/data/mikov2.sqlite (WAL mode)
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
| src/dashboard/app.py + routes.py|aiohttp.web server + 7 endpoint|
| src/dashboard/static/index.html|4 panel + Chart.js + SSE|
| src/backtest/replay_transport.py|SQLite 3-tablo merge -> stream|
| src/backtest/engine.py|Event dispatch engine|
| src/backtest/signal_detector.py|SWEEP/MSS/FVG/OTE tespiti (5s)|
| src/backtest/strategy.py|Sinyalleri entry kararına dönüştürür|
| tests/manual/backtest_run.py|Backtest CLI runner (v2.4: --no-require-sweep/-mss/-fvg override)|

5. UNIVERSE SCANNER KARARI
Sonuç: 1176 sembol -> 3 aşamalı filtre -> Top20.
Aşama 1 (Fatal): oi_usd > 1M + volume24 > 10M + 0.3 < spread < 20 bps.
Aşama 2 (Skor): volume %40 + OI %30 + funding %30.
Aşama 3 (Limit): Top5 WS bağlı, Top10 watch, Top20 takip.
Örnek Top5 (2026-09-17): BTC_USDT, SOL_USDT, XAUT_USDT, XRP_USDT, ONE_USDT. Not: XAUT emtia tokeni, §6.2 karar gereği exclude edilecek.

6. AÇIK SORUNLAR (FIX bekliyor)
6.1 Funding rate aşırı değerler "fırsat" olarak görülüyor
Sorun: ONE_USDT funding=-2%, LSK_USDT funding=-0.43% gibi değerler Top10'a giriyor. Tehlikeli — muhtemelen likidasyon kaskadı veya exchange-spesifik durum.
Karar: Skorlamada aşırı funding CEZA almalı:
    f_abs = abs(s.funding_rate)
    if f_abs > 0.005:  # 0.5% üstü = ceza
        f_score = -1.0
    else:
        f_score = f_abs / 0.005
Durum: Karar alındı, kod FAZ B2c'de güncellenecek.

6.2 Emtia token'ları universe'e sızıyor
Sorun: XAUT_USDT (Tether Gold), SILVER_USDT, UKOIL_USDT, USOIL_USDT, SPCXSTOCK_USDT gibi semboller kripto değil — tokenlaştırılmış emtia/hisse. Whale-radar mantığı bunlarda çalışmaz.
Karar: Exclude listesi eklenecek:
    EXCLUDED_EXACT = {
        "XAUT_USDT", "XAU_USDT", "XAG_USDT",
        "SILVER_USDT", "GOLD_USDT",
        "UKOIL_USDT", "USOIL_USDT",
        "SPCXSTOCK_USDT",
    }
Durum: Karar alındı, kod FAZ B2c'de güncellenecek.

7. BACKTEST İLERLEME
| İş|Durum|
| ---|---|
| B1 — ReplayTransport + engine|Doğrulandı (97.8 saat / 4.08s)|
| B2a — Signal detector|Doğrulandı (8 sinyal tipi)|
| B2b — Strategy adapter|Doğrulandı (SWEEP yön bug'ı v2.4'te fix'lendi, test 10/10)|
| B2c — Position simulator + PnL|SIRADAKİ|
| B2d — Backtest runner + rapor|Kısmi: CLI override bayrakları eklendi (v2.4)|
| B2e — Multi-symbol backtest|Bekliyor|

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
3. Küme etkisi: cooldown 60s < pencere 300s olduğundan 1 setup ~5-6 entry üretir; B2c'nin "max 1 pozisyon" kuralı bunu baskılar (entry sayısı != trade sayısı).
4. Yön flip'leri 2-6 saatte bir; kârlılığı B2c PnL yargılayacak.
KARAR (kilitli, SORU A: (A) + SORU B: (A)): B2c config = Varyant A: entry_window_ms=300000, require_sweep/mss/fvg=True, cooldown_ms=60000.

KRİTİK BUG — SWEEP YÖN MAPPING TERSLİĞİ (v2.4):
Belirti: test_strategy.py 4 test FAIL (assert 0 == 1).
Kök neden: strategy.py'da long_ok <- has_sweep_up, short_ok <- has_sweep_down (momentum yorumu). Oysa dedektör semantiği (sweep_wick_ratio=0.6 = rejection), test beklentileri ve AnaYasa micro_trigger (sweep -> MSS ters yön zinciri) şunu gerektirir: LONG <- SWEEP_DOWN (düşükler süpürülüp kapanış üstte), SHORT <- SWEEP_UP (yüksekler süpürülüp kapanış altta).
Düzeltme: strategy.py _try_entry içinde iki satır swap (fix forward). test_strategy.py 10/10, full suite 717 PASS.
Etki: Fix öncesi 230 entry'lik analiz geçersiz sayıldı; fix sonrası Varyant A yeniden koşuldu: 187 entry. Doğrulama: aynı ts'lerde yönler beklenen şekilde flip oldu (örn. 2026-09-16 20:54:10 LONG -> SHORT).

8. B2c — SIRADAKİ İŞ DETAYI
Dosyalar:
src/backtest/position_sim.py — entry -> pozisyon açma, TP/SL kontrol, kapanış.
tests/unit/test_position_sim.py — 10-12 test.
tests/manual/backtest_run.py — güncellenmiş rapor.
Girdi config (kilitli): --entry-window-ms 300000 (üç kapı True, cooldown 60s). Runner ayrıca --no-require-sweep/-mss/-fvg destekler.
Karar alınan tasarım:
Max 1 pozisyon per symbol (cluster engellenecek).
Multi-symbol concurrent (BTC long + ETH short aynı anda OK).
max_positions config'ten (TEST=3, PROD=2).
TP/SL exit: 5s OHLCV high/low ile.
Fee: taker 0.0002, maker 0.0, leverage-adjusted slippage.
Çıktı raporu:
Trade listesi (entry/exit/PnL/R).
Win rate.
Avg R-multiple.
Max drawdown.
Total return.

9. SIRADAKİ FAZLAR
B2c (öncelik): Position simulator + PnL ölçümü.
B2d: Backtest runner CLI genişletme (mevcut bayraklar: --db, --symbol, --entry-window-ms, --cooldown-ms, --require-ote, --no-require-sweep, --no-require-mss, --no-require-fvg; eklenecek: --report trades.json):
    python -m tests.manual.backtest_run \
      --db data/mikov2.sqlite \
      --symbol BTC_USDT \
      --entry-window-ms 300000 \
      --cooldown-ms 60000 \
      --report trades.json
B2e: Multi-symbol backtest + walk-forward.
Tüm Top20 sembolde aynı anda çalış.
3 ay train / 1 ay test rolling.

10. PROD İÇİN SONRAKİ ADIMLAR (B3)
Universe scanner'ı shadow runner'a bağla (otomatik Top5 rotasyon).
Micro-trigger'ı canlıya al (WS tick -> detector -> signal -> strategy).
Position manager'ı canlıya al (paper trading).
Alert entegrasyonu (Telegram/Discord).
Sigorta: 3-4 hafta paper trading -> gerçek para.

11. KİLİTLİ KARARLAR (Kümülatif)
Git/checkpoint:
Güvenilmeyen commit'ler local'de reset, remote'a force-push ile silinir. Önceki checkpoint: 7fb827848aee38897fcea9616d4ea898c294089a (REV9 DURUM + BAĞLAM, 2026-09-17).
Bu oturum checkpoint'i: <git rev-parse HEAD çıktısı — push sonrası bu satıra işlenecek> (içerik: strategy.py SWEEP yön fix + backtest_run.py CLI override + DURUM v2.4 + protokol v2.3; 717 test PASS ile doğrulandı).
Protokol = yöntem, DURUM = içerik. Devir sırasında sadece bu dosya güncellenir; SOHBET-KAPANIS-PROTOKOLU.md sabit kalır.
Mimari:
30 coin limit — bilinçli trade-off (100 coin için mimari değişiklik gerek).
30 değil 20 Top — 20 yeterli, top5 zaten işlem yapar.
Emtia/hisse exclude — bunlarda whale-radar mantığı çalışmaz.
Aşırı funding ceza — |funding| > 0.5% -> skor ceza.
Contract size cache — bulk detail bir kez çekilir (1176 sembol).
Max 1 pozisyon per symbol, multi-symbol concurrent.
TP/SL exit 5s OHLCV high/low; taker fee 0.0002.
Strategy config default'u katı kalır (require_sweep/mss/fvg=True, entry_window_ms=15000); gevşetme deneyleri CLI override ile yapılır, default koda gömülmez (SORU B: (B)).
B2c backtest config: entry_window_ms=300000, üç kapı True, cooldown_ms=60000 (SORU A: (A), SORU B: (A)).
SWEEP semantiği: LONG <- SWEEP_DOWN, SHORT <- SWEEP_UP (stop-hunt reversal; wick_ratio 0.6 = rejection). Testler bu semantiği belgeler.
Kod kuralları:
Python 3.10 hedef — 3.11+ syntax YASAK.
"from .." boşluklu — syntax hatası önleme.
f-string log YASAK — %s placeholder.
Global state YASAK — DI zorunlu (Y-353).
SOHBET-KAPANIS v2.3 format kuralları: her döküman/kod ayrı 4-backtick bloğu; blok içinde 3-backtick YASAK; kontrol checklist'i düz metin; kod değişikliği önerileri §7.7 şablonu (tam yol + eski hali + yeni hali + gerekçe) ile verilir.
PROTOKOL İHLALİ NOTU (2026-09-19, §7.4 gereği): asistan aynı sohbette 4-backtick kuralını 3 kez ihlal etti (checklist ve kod bloklarında 3-backtick kullandı); protokol §7.6 netleştirilerek (v2.2/v2.3) kapatıldı.

12. DOSYA KONUMLARI
docs/DURUM.md — bu dosya (proje içeriği, devir noktası).
docs/SOHBET-KAPANIS-PROTOKOLU.md — v2.3, projeden bağımsız yöntem.
docs/MikoV2-AnaYasa-REV5.md — 116 YAMA, kod kuralları (referans).
docs/MikoV2-Proje-Tum-Moduller-REV5.md — modül pseudo (referans).

13. YENİ SOHBET NASIL BAŞLAR
Verilecek dosyalar:
DURUM.md (bu, v2.4)
SOHBET-KAPANIS-PROTOKOLU.md (v2.3)
MikoV2-AnaYasa-REV5.md
MikoV2-Proje-Tum-Moduller-REV5.md
Açılış mesajı:
"DURUM.md'yi okudun mu? B2c'ye başla: §8 tasarıma göre src/backtest/position_sim.py iskeletini kur (max 1 pozisyon, TP/SL 5s OHLCV). Backtest config: --entry-window-ms 300000, üç kapı True. Testler 717 PASS."

14. UNFROZEN BEYANI
FROZEN YOK.
Her satır sorgulanabilir.
Yeni YAMA 369+ açık.
Blind kabul YASAK.

15. VERSİYON
v1.0 (REV9, 2026-09-17): Orijinal REV9 durum dökümanı. FAZ 0-9 kapandı, universe scanner + shadow collector + backtest B0.x-B1 tamamlandı. B2c sırada.
v2.0 (2026-09-19): Protokol entegrasyonu. SOHBET-KAPANIS v2.0 (projeden bağımsız) sisteme eklendi. Git checkpoint kararı ve güvenilmeyen B2c/B2d deneme commit'lerinin (f714665 -> 6199ae2) force-push ile temizlenmesi (checkpoint 7fb8278) kaydedildi.
v2.1 (2026-09-19): BAGLAM.txt entegrasyonu ve kaldırılması.
v2.2 (2026-09-19): Arşiv referansı temizliği.
v2.3 (2026-09-19): B1/B2a/B2b doğrulama + DB transfer yöntemi. Gerçek DB üzerinde test yapıldı (97.8 saat / 4.08s). SWEEP bug tespit edildi ve düzeltildi (push bekliyor). tmpfiles.org transfer yöntemi eklendi.
v2.4 (2026-09-19): B2c öncesi analiz tamamlandı. (1) Config gevşetme deneyleri: baz 5 entry -> Varyant A (300s pencere, 3 kapı) fix sonrası 187 entry (~31-37 setup); FVG'nin kalite kapısı olduğu kanıtlandı; B2c config kilitlendi (300s, 3 kapı, cooldown 60s). (2) SWEEP yön mapping tersliği bulundu ve fix forward ile düzeltildi (LONG <- SWEEP_DOWN, SHORT <- SWEEP_UP); 4 test FAIL -> 717 PASS. (3) backtest_run.py'ye --no-require-sweep/-mss/-fvg CLI override eklendi. (4) Protokol v2.3: her döküman/kod ayrı 4-backtick bloğu, checklist düz metin, §7.7 kod değişikliği şablonu; 4-backtick ihlali §7.4 gereği not edildi.

SON