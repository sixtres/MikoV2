# MICO v2 — AnaYasa REV5 — FAZ 0 KAPANDI
# REV5 — 116 YAMA (110 + 6 yeni: 362,363,364,365,367,368 — 366 açılmadı) — FAZ 0 KAPANDI 2026-09-12
# PO: Eser Göbekli — Her satır sorgulanabilir, blind kabul YASAK
# Önceki: REV4.9.9 FINAL-v4 (110 YAMA, 239 bulgu, 12 runtime fix) → REV5 (116 YAMA, 245 bulgu, 12 tasarım onaylı / 4+1 kısmi kodda / 7 FAZ2-4)
# KURAL: Hiçbir satır kilitli değil, her satır DISTINCT/CONFLICT/SIDE_EFFECT/NECESSITY/LOOP açısından sorgulanacak
# FAZ 0 KAPANIŞ: 8 madde kick-back kapandı, Y-356/Y-359/Y-360/Y-259-273/Y-355/Y-353/Y-354/Y-364 düzeltildi


0. STACK & FOLDER — REV5 UNFROZEN — KİLİT YOK — 116 YAMA

Language: Python 3.11 + asyncio + mp.Queue + Numba
Queue Model: STATE mp.Queue maxsize 200 DROP_NEVER blocking put via AsyncStateQueue bridge (Y-329 asyncio.Queue(200) + single writer task -> mp.Queue, Y-357 to_thread+Semaphore(8) deadlock fix, ayrı executor YASAK, drain() SIGTERM zorunlu, Y-337) + Telemetry mp.Queue maxsize 1000 DROP_OLDEST put_nowait DROP via AsyncTelemetryQueue (telemetry only) — state_queue için put_nowait DROP YASAK, force-flush put_nowait DROP sadece telemetry (Y-276)
Storage: SQLite WAL sadece STATE (positions, orders, version, sealed_at_ms, emergency_pending) + Parquet snappy live 7d archive 365d
Buffer: preallocated numpy float64[5000] hard cap, low-water mark 4000 (S-04 corrected), tetikleyici bids_len+batch_bids >= 5000, trim hedefi 4000'e 1000'lik blok (Y-317a sondan kes, min guard), internal trim C memmove sadece sınırda, Python for/list.sort FATAL (internal), external diff iteration allowed, TEK SAYAÇ batch_bids/batch_asks (Y-332), find_price np.searchsorted O(log n) (Y-360 list comp YASAK), trim rate-limited (Y-348)
Search: bids `searchsorted(-price)`, asks `searchsorted(price)` np.searchsorted O(log n) (Y-252 + Y-360 list comp YASAK), torn read YASAK, memoryview leak YASAK, get_obi_safe_sync tek lock copy-on-read no await, pre_sync_queue append var filter var (Y-352 ekleme YOK bug fix), global DI YASAK zorunlu constructor injection (Y-353), price_set array sync (SE-15)
OBI: aktif len (Y-344) — fixed 5000 varsayımı YASAK
Session: aiohttp ClientSession TCPConnector 100 keepalive 60, aiohttp.request FATAL, persistent session gateway tek process
RateLimit: TokenBucket REAL SINGLE GLOBAL bucket rate 8 burst 15 (Y-275), REST gateway TEK PROCESS mp.Queue istek, per-IP 15 burst semaphore, per-symbol defaultdict 2 semaphore ayrı, acquire 2.0s outer 3.5s, pacer_delay_ms CRITICAL 2 NORMAL 20 REBUILD 50 (min-spacing Y-330, Y-343 nominal 2ms max 5ms emergency tolere, Y-355 _last_dispatch base_prio asimetri not edildi, tasarım amacı belirsiz, KEEP), pacer_priority 0 CRITICAL 1 NORMAL 2 REBUILD distinct (Y-304), sem_emergency 3 + sem_normal 9 (Y-342 ayrı havuz), single-flight same symbol, global_consecutive_429 reset on success decay 60s per-symbol circuit half-open 60s test 1 (Y-261), bypass YASAK FATAL (Y-263)
Emergency: slippage leverage_adjusted `min(3%,10%/lev)` 20x=0.5% (Y-260), emergency_MAX_RETRY 1 (market close) reduce_only True true_market_sweep verified_qty>epsilon min_lot/2 dust sweep, verified qty fresh cache TTL 500ms, store_flush_suspended single counter (Y-356 çift sayaç YASAK + Y-368 REVISE: assert >=0 prod crash YASAK, WARNING+clamp 0, Y-346 uyumlu) +Lock refcount _flush_suspend_counter +=1/-=1 clear only if counter==0 (Y-264 REVISE + Y-310), counter underflow WARNING (Y-346), FlushController async-safe call_soon_threadsafe YASAK direct Event (Y-350 hierarchy fix), telemetry suspend'te DROP (Y-325), emergency_tasks dict Future pre-insert single-flight race fix (Y-351), pop in done_callback try/finally (Y-266 + Y-311), lock order sqlite(3)->pacer(4)->flush(5) hierarchy ihlali YASAK (Y-350), RuntimeError catch + _direct_market_post fallback (Y-338, None handle), emergency state persist = SQLite WAL direct 2s timeout fallback journal + exchange_ts age check (Y-341 + Y-361), signal SIGTERM emergency_close_all 30s grace Docker stop_grace 35s
Locks: hierarchy buffer>fill>sqlite>pacer>flush>telemetry (Y-339 + Y-350 emergency 3->4->5), sealed_lock ayrı (Y-265), reentrant owner check CI assert, fill_lock asyncio.Lock single writer per process, buffer_lock single RLock (Y-253), pacer_lock asyncio.Lock (Y-358 threading.Lock YASAK), leaf: token_bucket, _state_sem, _seq_lock
WS: ping 15s pong 5s timeout 3 fail reconnect jitter ±20%, expected_seq per-symbol seq_epoch reconnect epoch++ reset after snapshot same lock + pre_sync_queue clear seq<=snapshot.seq (Y-254), out-of-order drop `incoming_ts <= last_applied_ts`, seq gap -> snapshot resync, snapshot gecikme → batch drop + metric (Y-340, replay YASAK)
State Machine: ACTIVE|WAITING_TICK|STALE|INVALID priority INVALID>STALE>WAITING>ACTIVE single transition() func, fresh_tick_event dict per-symbol defaultdict(Event) safe get not KeyError cleanup on DROPPED set()+clear() (Y-256), paused_ms float not int per-tick accumulate even when is_valid=False (Y-255), breach_start_ms only is_valid True, pause'da FVG arama YASAK, stale>5s only new setup TP/SL devam, max_pending 600000 hard deadline FVG_EXPIRED_HARD_DEADLINE event + telegram WARNING quarantine 60s max 3 retry -> INVALIDATED, reset sırası: emit → reset_to_idle → cleanup_telemetry → continue (Y-306 + Fix 6)
Partial: filled_by_order = max(existing,new) monotonic flip sign assert same sign reduce_only True, sealed_orders OrderedDict TTL 300s dict value {sealed_at_local_ms, exchange_ts_ms, version} (Y-315), expire local now_ms + exchange_ts age check (Y-361), reuse exchange_ts_ms None guard (Y-336), TTL cleanup break YASAK full scan (Y-354 full scan OK, redundant absorption var, Y-365 note), epsilon symbol based min_lot/2 not 0.001 fixed (Y-260), original_planned_entry original_tp original_sl IMMUTABLE version optimistic, TP/SL shift original+delta, BE monotonic new_sl = max(current_sl,candidate) LONG min SHORT, net fee R:R 1.4999 buffer isclose 1e-9 fee taker/maker ayrı (Y-258) fee_fallback 0.0003 cache WARNING
Exchange: position_mode ONE_WAY|HEDGE zorunlu FATAL yoksa REST fetch, margin_mode ISOLATED default CROSS YASAK, target_leverage 5 set_leverage startup zorunlu, order_type LIMIT_IOC -> {type:LIMIT, timeInForce:IOC} via _map_order_type() (Fix 4.5), price_precision qty_precision ayrı Decimal quantize `str(Decimal.quantize)` not f-string float (Y-271 partial + Y-323 ROUND_DOWN), symbol STATUS HALTED/BREAK 5m check INVALIDATE emergency close, fee_taker 0.0002 funding_max 0.0008
Storage: batch 500 flush 5000, force-flush daemon 2 bounded 5 put_nowait DROP telemetry only zero-disk (state_queue 200 DROP_NEVER blocking ayrı, telemetry_queue 1000 DROP_OLDEST put_nowait DROP ayrı) (Y-276), archiver asyncio.to_thread atomic .tmp->rename two-phase rotation _closed orphan recovery 5m .deleted 1h sil lock file PID+timestamp orphan override PID check, snappy live1 speed archive9 size dynamic, read lock copy-on-read, trim() WARNING rate-limited (Y-348)
Crash: reconciliation exchange=truth fetch_position DB update STATE_RECONCILIATION alert fetch_open_orders cancel/match WAL replay WS paused startup_complete event emergency_pending flag DB
Health: per-coin %80 alive 200 else 503 last_tick_age<30s archiver<25h sqlite<10s
Secret: systemd EnvironmentFile 0600 kanonik (service kullanıcısı owner); Docker secrets opsiyonel/test edilmemiş B3.5; logs mask, DNS not IP hardcode, TZ=UTC assert, API key trade only withdrawal disabled IP whitelist
Time: all UTC monotonic intervals time.time only log, funding 00/08/16 UTC daily_reset UTC weekly MONDAY UTC, next_candle extrapolate `last_exchange_ts + max(0,mono_now-last_mono)` (Y-257) + 5000 buffer (Y-281), isclose epsilon 1e-9 NaN/Inf sanitize drop oi_usd=oi_contract*mark, funding_scheduler ayrı task (Y-331)
Config: all *_ms int whitelist, minutes YASAK FATAL (Y-269), Decimal quantize separate, dashboard inline CSS + /static/chart.min.js cached 31536000 CDN FATAL npm node_modules FATAL (Y-270), Numba dict_to_array forbidden typed List np array (Y-272)
Retry Katman Tablosu (Y-334): emergency 1, execution 3, reconciliation 2, status check 5
Alias'lar (Y-334/Y-335 — REVISION NOTICE + Alias format):
  - B-42=B-59 alias of S-09/S-02/S-07/S-10/S-12/S-16/S-17/S-19.1/S-04/S-11/S-08
  - A-36..A-60 alias of B-36..B-60
Event bypass (Y-345): CRITICAL_ALERT + FVG_EXPIRED_HARD_DEADLINE emit_event sync log + emit_event_async alert; telemetry_queue bypass
Pacer (Y-322a + Y-329 contract + Y-330 + Y-347): statik priority heap, lock altında heappush/heappop, lock dışı sleep(0), min-spacing per-prio, recursion YASAK

src/miko_v2/
  config.py / config.yaml
  data_layer/ws_manager.py
  data_layer/rest_client.py
  data_layer/sqlite_writer.py
  storage/orderbook_store.py
  features/whale_radar.py
  features/micro_trigger.py
  risk/portfolio_risk.py
  execution/manager.py
  execution/emergency_close.py
  backtest/
  dashboard/routes.py / index.html / static/chart.min.js
  supervisor.py / main.py

1. AMAÇ & UNIVERSE
Universe Top5 scanner 30s hysteresis 5m max_pending 10m flap 3 DROPPED ghost reset timer cancel paused_ms float cleanup sealed TTL trim 4000 low-water invalid only seq-id epoch. Timer cancellable per-symbol Event discard on pause fresh window WAITING_FOR_FRESH_TICK gap quarantine 60s stale only new setup Ghost breach_start only valid. Whale trust OI USD 50k min (Y-268) + sweep 1.5x cleanup decay exp(-age/1h) band ±0.5% fingerprint tick_size (Y-267) + wash triple check OI+CVD+taker ratio.

2. ANAYASA — 60 KURAL REV5 UNFROZEN DRAFT
1-35 REV4.7 korundu (DEFERRED, REV4.7 dokümanı gerekli)
36 Position Mode ONE_WAY required FATAL
37 Margin ISOLATED default CROSS YASAK
38 Leverage set startup zorunlu target 5
39 Decimal quantize price/qty separate str(Decimal)
40 Symbol STATUS 5m HALTED INVALIDATE emergency close
41 Exchange truth reconciliation
42 Lock hierarchy buffer>fill>sqlite + sealed_lock ayrı
43 TokenBucket REAL SINGLE GLOBAL bucket rate8 burst15, no separate buckets, pacer_delay_ms 2/20/50 (min-spacing), pacer_priority 0/1/2 distinct, bypass=token acquire atlama YASAK FATAL
44 Expected seq epoch reset same lock pre_sync_queue clear per-symbol
45 Ping/Pong 15s/5s 3 fail jitter
46 Sealed TTL 300 OrderedDict + version optimistic + dict value {sealed_at_local_ms, exchange_ts_ms, version}
47 Epsilon symbol min_lot/2 dust sweep
48 Fee fallback 0.0003 cache taker/maker ayrı
49 Slippage leverage adjusted
50 State queue 200 DROP_NEVER blocking + telemetry 1000 DROP_OLDEST put_nowait DROP telemetry only
51 SIGTERM emergency 30s grace + tasks cleanup try/finally pop
52 Health per-coin %80
53 Secret Docker secrets
54 Config parse FATAL all _ms int minutes YASAK
55 Float isclose epsilon 1e-9 + Decimal
56 Buffer Management fixed 5000 hard cap, low-water 4000, atomic loop
57 Timer paused_ms float accumulate even invalid + fresh_tick_event safe
58 PriorityQueue pacer not FIFO single-flight
59 Store flush suspended counter+Lock refcount==0 ise clear ALWAYS
60 Whale band ±0.5% OI 50k wash triple

3. RUNTIME
TEST risk 0.008 max_pos 3 daily -0.04 0.036<=0.04 PASS
PROD risk 0.006 max_pos 2 daily -0.02 0.018<=0.02 PASS
pause 24h/48h REST_BLINDNESS POST_MARKET emergency slippage leverage adjusted MAX_RETRY 1 reduce_only True true sweep verified qty epsilon dust sweep funding UTC daily UTC weekly MONDAY all UTC monotonic risk math fixed net fee 1.4999 zero-disk state_queue Decimal symbol STATUS leverage set reconciliation

4. CONFIG — REV5 UNFROZEN — KİLİT YOK — 116 YAMA
exchange: position_mode ONE_WAY required FATAL margin_mode ISOLATED default target_leverage 5 set_leverage true, ws_reconnect_backoff_ms [1000,2000,5000,10000,30000] cap 60000 jitter ±20%, rate_limit token_bucket_real SINGLE GLOBAL bucket rate 8 burst 15 header fallback local min() max_req_per_sec 8 burst 15 sem_per_ip 15 per_symbol defaultdict 2 sem_emergency 3 sem_normal 9 acquire_timeout_ms 2000 outer 3500 pacer_delay_ms CRITICAL 2 NORMAL 20 REBUILD 50 pacer_priority 0/1/2 distinct sem_critical merged into sem_emergency 3 single-flight same symbol global_consecutive_429 per-symbol decay 60s circuit half-open 60s per-symbol, time_sync NTP drift <50 else spoof disable, max_ws_per_process 10 process_model 3*10 REST gateway single mp.Queue state DROP_NEVER, emergency_market_max_slippage_pct leverage_adjusted min(3%,10%/leverage) MAX_RETRY 1 reduce_only true true_market_sweep true verified_qty epsilon dust sweep min_lot/2 cache TTL 500ms, set_leverage true set_margin_mode true symbol_status_check_ms 300000, order_type_mapping LIMIT_IOC->{LIMIT IOC} via _map_order_type(), price_precision qty_precision separate Decimal quantize str(Decimal), fee_fallback 0.0003 fee_from_rest true fee_cache true taker/maker ayrı
database: WAL true retention 0 l2_mp_queue_forbidden true state_queue_maxsize 200 DROP_NEVER telemetry 1000 DROP_OLDEST
storage: live 7 archive 365 moves_to_archive atomic to_thread .tmp->rename two-phase rotation _closed orphan recovery 5m .deleted 1h lock_file PID timestamp PID check, batch 500 flush 5000 snappy live1 archive9, buffer preallocated 5000 fixed trim 4000 low-water atomic loop C memmove searchsorted -price bids vs asks ayrı torn read YASAK MAX_BUFFER fixed invalid only seq-id epoch executor optional lock hierarchy buffer>fill>sqlite>pacer>flush>telemetry sealed_lock ayrı read_lock copy-on-read memoryview no leak force_flush daemon 2 bounded 5 put_nowait DROP zero-disk state_queue separate store_flush_suspended true triggers [EMERGENCY,CIRCUIT,SIGINT] archive_method asyncio.to_thread atomic .tmp->rename, pre_sync_queue true seq_id expected_seq epoch reset same lock ping 15s pong 5s 3 fail, sealed_orders TTL 300 OrderedDict dict value version optimistic, epsilon symbol dust sweep, trim WARNING rate-limited
universe: max 5 scanner 30000 min_spread_bps 5 max 20 min_oi_usd 50_000_000 always [BTCUSDT] scoring oi_change 0.30 liq 0.30 squeeze 0.20 funding 0.10 spread 0.10 hysteresis 300000 max_pending 600000 flap 3 ghost_reset_on_dropped true breach_pause true reset_on_new_fvg true reset_on_dropped true stale 5000 waiting_for_fresh_tick true gap 60s quarantine 3 retry, trim farthest true trim_to 4000 invalid_only_seq_gap epoch true cleanup_telemetry true sealed TTL band ±0.5% fingerprint tick_size
whale_radar: big_order_usd 100k spoof_timeout_ms 800 real_min_lifetime 3000 real_min_fill_ratio 0.30 spoof_max 0.10 absorption 2.5 price_move 0.05 obi 0.40 depth 0.2 cvd 120 divergence 0.10 ipc mp_queue_only_state_trade buffer preallocated 5000 numba obi forbidden cvd allowed dict_to_array forbidden typed array warmup true bounds_check true MAX_BUFFER 5000 fixed trim 4000 atomic loop lock hierarchy read_lock copy-on-read torn read searchsorted bids vs asks ayrı batch vectorized bulk C-slice trust min_real_count 3 requires_absorption true requires_cvd true requires_oi_delta true requires_taker_ratio true min_score 2 min_oi_delta_usd 50000 second_requires_trust true cleanup 3600000 decay exp(-age/1h) band ±0.5% fingerprint tick_size wash_detection triple OI USD spoof_disable NTP fail
micro_trigger: sweep_equal 0.08% wick_ratio 0.6 mss_timeout 90000 fvg_timeout 180000 fvg_ote 0.62-0.79 tolerance 0.015 min_size 0.05% oi_change_5m 3.0% funding_max 0.0008 squeeze bb 20 std2 bandwidth_p5 true lookback_bars 180 hard_gates [SWEEP,MSS,FVG_OTE] AND weighted 0.65 soft_score fvg_invalidation time_breach_15s_or_micro_candle_5s breach_ms 15000 micro_candle_ms 5000 time_source exchange_timestamp last_local_tick_monotonic true lag_formula elapsed=(now-breach_start)-lag-paused float timer_loop sleep 5000 cancellable per-symbol Event safe get close_source mark_price ws_independent pause_on_invalid resume_on_valid skip_forbidden paused_ms float defaultdict reset_on_new_fvg reset_on_dropped price_monitor_on_pause stale 5000 waiting_for_fresh_tick gap quarantine 60s discard_on_pause fresh_window max_pending 600000 hard_deadline FVG_EXPIRED_HARD_DEADLINE event telegram lock hierarchy read_lock monotonic cleanup_telemetry next_candle extrapolate max(0,mono_now-last_mono)+5000
risk: sl_buffer_atr 0.5 atr 14 be_at_R 1.0 trail_at_R 1.5 correlation_threshold 0.85 correlation_window_ms 3600000 min_samples 30 directional true long_short_hedge_allowed true max_sl_distance 0.025 second_enabled true size_mult 0.5 cooldown 3600000 second_bypass correlation_same_id true max_positions_same_id true partial_fill qty_update filled_qty new_active_qty=filled_qty max() monotonic flip assert same sign reduce_only order_type LIMIT_IOC PARTIAL_CLOSED seal sealed_at_ms sealed_orders TTL 300 dict value version optimistic original immutable avg weighted TP shift original SL shift BE monotonic max/min BE never below RR 1.5 net_fee 1.4999 fee taker/maker ayrı fallback 0.0003 old_trail None min_lot epsilon symbol/2 dust sweep idempotency startup sync fill_lock hierarchy sealed_lock startup WS paused, trust second_min_score 2 requires_oi_delta true retention live 7 archive 365 moves atomic to_thread .tmp->rename, max_risk_per_day_validation true TEST 0.036 PROD 0.018 funding interval 28800000 daily includes funding true UTC, position_mode ONE_WAY margin_mode ISOLATED leverage 5
execution: entry LIMIT_IOC exit LIMIT_IOC entry_guard 0.25% exit 0.5% emergency 2.0% emergency_market_max_slippage leverage_adjusted emergency_market_fallback true true_market_sweep true reduce_only true limit_ioc 3500 fee_maker 0 fee_taker 0.0002 fee_from_rest true fee_cache true fee_fallback 0.0003 funding 8h partial true execution_max_retries 3 slippage_reject mark_vs_limit_guard_breach orphan_rest_fetch true post_market_rest_fetch true critical_bypass false gateway true per_ip 15 per_symbol 2 acquire 2000 outer 3500 pacer_delay_ms 2/20/50 pacer_priority 0/1/2 distinct sem_emergency 3 sem_normal 9 single-flight global_429 per-symbol reset decay half-open emergency_MAX_RETRY 1 force_flush daemon 2 bounded 5 put_nowait DROP telemetry only zero-disk state_queue 200 DROP_NEVER blocking separate telemetry_queue 1000 DROP_OLDEST partial_fill weighted_avg qty_filled_qty max() monotonic PARTIAL_CLOSED sealed TTL 300 dict value version optimistic original immutable TP shift SL shift BE monotonic BE never below RR 1.5 net_fee 1.4999 old_trail None min_lot epsilon symbol/2 dust sweep idempotency startup sync fill_lock hierarchy sealed_lock WS paused remaining_qty DELETE Decimal quantize str(Decimal) price_precision qty_precision separate, emergency_slippage leverage_adjusted max_retry 1 reduce_only true true_market_sweep true verified_qty epsilon dust sweep cache TTL 500ms action FORCE_LIQUIDATED_BY_SYSTEM not STILL_OPEN_MANUAL task done_callback pop retry 1 attempt keyboard store_flush_suspended clear ALWAYS, order_type_map _map_order_type() LIMIT_IOC->{LIMIT IOC}

5. VALIDATION — REV5 MINIMAL
FATAL if: position_mode missing, margin_mode missing, leverage not set, config parse fail, entry>=exit>=emergency, max_ws>10, l2_mp_queue true, orderbook_l2 no read_lock, aiohttp.request used, bypass true, minutes field exists, qty=remaining_qty exists, tp_fixed/sl_fixed exists, original_planned_entry missing, PARTIAL_CLOSED missing, MAX_BUFFER !=5000, searchsorted -price not separate for bids/asks, torn read, Python loop for buffer, state_queue not DROP_NEVER, per-IP !=15, acquire !=2.0s outer !=3.5s, pacer not PriorityQueue, max_retry !=1 reduce_only false, epsilon not symbol based, fee fallback !=0.0003, slippage not leverage adjusted, token bucket not REAL single gateway, expected_seq epoch reset not same lock, ping pong not 15s/5s 3 fail, sealed TTL !=300, store_flush_suspended clear not ALWAYS, dashboard CDN/npm present, S-20 hem Stack hem Config anahtarıyla eşleşiyor, execution config B-61 dışında ID'ye bağlı, trim() içinde self.bids_price[trim_n:self.bids_len] var, tek while + AND var, Decimal('1.' + ...) var, trim() side param yok sayıyor, sealed_orders value scalar not dict, sealed["exchange_ts_ms"] None guard yok, emergency_close state_queue.put çağırıyor, emergency_persist_state timeout yok, is_emergency ve priority=CRITICAL aynı değişken, pacer_min_delay[0] > 5ms, OBI hesabı sabit 5000 varsayımı, bids_price[:5000] doğrudan kullanılıyor, emit_event içinde await var, CRITICAL_ALERT telemetry_queue üzerinden gidiyor, counter underflow WARNING yok, sleep(0) lock altında, pop recursion var, trim sessiz, trim log rate-limited değil, revision notice format yanlış, state_queue is asyncio.Queue, buffer_l2_nonblocking mp.Queue.put doğrudan, ayrı executor _state_executor, emergency token bypass, sem_emergency ve sem_normal aynı, Pacer sınıfı 2'den fazla tanımlı, Lock hierarchy ters sıra, reconciliation ve emergency_close_all paralel, emergency_persist_state journal fallback yok
WARNING if: numba warmup missing, fee cache fallback missing, snappy live1 archive9 missing, to_thread .tmp->rename missing, pre_sync_queue missing, ghost_reset false, stale false, gap quarantine false, discard false, cancellable per-symbol false, max pending missing, flap 3 missing, sealed TTL cleanup missing

--- YAMA 303-312 NUMERICAL ENTEGRE ---
303: seq_epoch hardcoded BTCUSDT fix -> per-symbol defaultdict + symbol param
304: pacer priority collapse fix -> prio 0 CRITICAL, 1 NORMAL, 2 REBUILD
305: aging gateway init çöküş fix -> per-request enqueue ts bazlı aging
306: hard deadline continue öncesi fix rev2 — YAMA 280'in tam fixi + reset sırası
307: trim double count fix -> bids_new azaltma kaldırıldı
308: price in numpy O(n) fix -> searchsorted found flag + set lookup
309: sealed_orders local vs exchange clock fix rev2 -> exchange_ts_ms
310: store_flush_suspended refcount fix -> counter + Lock + underflow WARNING
311: done_callback task leak fix rev2 -> try/finally pop garanti
312: fill_lock network await fix -> lock DIŞINDA

--- YAMA 313-328 REV5 ---
313: on_snapshot seq_epoch tek artırım
314: L2Buffer.__init__ pre_sync_queue + _seq_lock + expected_seq
315: Y-309 fill_event → fill düzeltmesi + TTL/reuse ayrı dict
316: S-20 kategori konumu → B-61 taşındı, S-20 kaldırıldı
317a: trim() sondan kes + min guard
318a: apply_batch iki ayrı loop side-aware
320a: FlushController async-safe binding
321a: RestGateway.acquire IP→symbol sıra + timeout
322a: Pacer heap statik priority + heappush
322b: CRITICAL full queue fail-fast
323: quantize_price Decimal basamak + ROUND_DOWN
325: FlushController suspend'te telemetry DROP, WAIT değil
326: RestGateway.acquire await token_bucket.acquire()
327: Pacer.pop recursion YASAK, while loop
328: Pacer.enqueue heapq.heappush, heapify YASAK

--- YAMA 329-340 (Pass 1/2/3 fix'leri) ---
329: AsyncStateQueue = mp.Queue + asyncio.to_thread adapter
330: Pacer rate-shaping = per-priority minimum-spacing (last_dispatch dict)
331: Funding scheduler = ayrı asyncio task, supervisor TaskGroup
332: Buffer sayaç ismi = batch_bids/batch_asks (tek)
333: Retry katman tablosu (emergency 1, execution 3, reconciliation 2, status 5)
334: REVISION NOTICE format (SUPERSEDED BY / AUTHORITATIVE)
335: Alias format (B-XX=alias of S-XX, A-XX=alias of B-XX)
336: sealed_orders dict okuma — sealed["exchange_ts_ms"] None guard
337: state_queue ayrı executor YASAK, semaphore(8) + to_thread + drain()
338: _direct_market_post token bucket kullanır, sadece pacer bypass; None dönüş + CRITICAL_ALERT
339: Lock hierarchy buffer>fill>sqlite>pacer>flush>telemetry; leaf: token_bucket, _state_sem, _seq_lock
340: Snapshot gecikme → batch drop + metric; replay YASAK

--- YAMA 341-349 (Pass 3 genişletilmiş fix'leri) ---
341: Emergency state persist = SQLite WAL direct 2s timeout + fallback journal; state_queue bypass
342: sem_emergency 3 + sem_normal 9 ayrı havuz; is_emergency ≠ priority=CRITICAL
343: Pacer CRITICAL min-spacing nominal 2ms max 5ms; emergency tolere (Y-330 per-priority min-spacing ile uyumlu)
344: OBI = aktif len; fixed 5000 varsayımı YASAK; get_obi() merkezi
345: CRITICAL_ALERT + FVG_EXPIRED_HARD_DEADLINE bypass telemetry_queue; emit_event sync + emit_event_async
346: FlushController counter underflow WARNING zorunlu
347: Pacer.pop lock altında heappop/heappush, lock dışı sleep(0); recursion YASAK
348: trim WARNING rate-limited (her 100 trim'de 1); log flooding YASAK
349: REVISION NOTICE format zorunlu; her SUPERSEDED YAMA AUTHORITATIVE belirtmeli


--- YAMA 350-361 (REV5 12 runtime fix, side-effect-safe) ---
350: Lock hierarchy ihlali fix — emergency_close sırası sqlite(3)->pacer(4)->flush(5) olmalı, 5->3->4 YASAK (Y-339 ihlali), call_soon_threadsafe YASAK direct Event
351: emergency_close single-flight race fix — Future pre-insert, if+create_task arası await YASAK, TOCTOU fix
352: pre_sync_queue append eksik fix — filter var ama append YOK, apply_batch içinde gap durumunda append zorunlu
353: Global instance referansları fix — db, alerting_agent, compute_obi, write_emergency_journal, _numba_cvd tanımsız, dependency injection zorunlu, NameError fix
354: TTL loop break yanlış fix — OrderedDict insertion != timestamp, break YASAK full scan zorunlu
355: Pacer _last_dispatch[effective] fix — effective aging sonrası prio, base_prio olmalı, aksi halde NORMAL aged item CRITICAL slot bloke eder
356: FlushController çift sayaç fix — _counter + _counter_original_count senkron değil, tek sayaç + assert >=0, çift sayaç YASAK
357: AsyncStateQueue deadlock fix — mp.Queue + to_thread + Semaphore(8) blocking, asyncio.Queue(200) bridge + single writer task, deadlock fix
358: Pacer busy loop + yanlış Lock fix — threading.Lock YASAK, asyncio.Lock zorunlu, while True sleep(0) busy loop YASAK sleep(remaining) zorunlu
359: RestGateway acquire timeout fix — ip 2.0 + symbol 1.5 + main 2.0 =5.5s outer 3.5s ihlali, single outer wait_for(3.5s) zorunlu
360: L2Buffer find_price O(n) fix — [-p for p in arr] list comp O(n) YASAK, np.searchsorted O(log n) zorunlu (Y-308 amacı)
361: sealed_check_reuse exchange_ts age fix — sadece local TTL değil exchange_ts_ms age de kontrol, eski exchange_ts reuse YASAK

--- TOPLAM YAMA REV5 ---
251-273: 23 loop red team
274-276: 3 Claude
277-302: 26 numerical
303-312: 10 distinct
313-316: 4 fix-üstü-fix
317a-323: 7 side-effect-safe fix
325-328: 4 yeni fix
329-340: 12 Pass fix
341-349: 9 Pass 3 genişletilmiş fix
350-361: 12 runtime fix tasarım onaylı, koda girmiş 4+1 kısmi (354,355,360,361 + 356 kısmi), 7 FAZ2-4 (350,351,352,353,357,358,359) (Y-364)
Toplam: 116 YAMA (110+6 yeni 362,363,364,365,367,368)



--- YAMA 277-302 NUMERICAL ---
277: qty=0 yok-sil no-op
278: on_snapshot size guard >5000 truncate/reject
279: bids_inserts sadece yeni fiyat sayar (alias batch_bids)
280: hard deadline is_valid=False iken de tetiklenir
281: next_candle_target_ms max(mono*1000+5000, computed)
282: fresh_tick_event.clear() KOŞULSUZ YASAK
283: FLIP tespitinde emergency_close zorunlu
284: sealed_orders clock exchange_ts_ms
285: optimistic retry loop max 3
286: REVISION NOTICE → Y-322a
287: pacer PriorityQueue maxsize=200
288: emergency finally success=False init
289: ONE_WAY positionSide BOTH zorunlu
290: get_verified_position_qty 2x None -> raise Catastrophic
291: dust false-positive CLOSED_DUST YASAK
292: apply_batch epoch guard
293: fresh_tick_event spin-loop güvenli clear after seq check
294: reset_to_idle paused_ms last_seen_tick_seq
295: FLIP fill_lock deadlock fix lock dışına
296: sealed TTL birim ms (partial KEEP)
297: retry+filled_by_order advance after commit
298: REVISION NOTICE → Y-322a
299: queue full token waste refund
300: REVISION NOTICE → Y-311
301: position_mode_side ONE_WAY belirsiz fix
302: dust <min_lot DUST_ACKNOWLEDGED

--- CLAUDE FIXES 274-276 ---
274: L2Buffer ask side mutation side-aware fix
275: REBUILD bucket -> SINGLE GLOBAL bucket rate8 burst15
276: state_queue DROP_NEVER blocking

--- REVISION NOTICE'LAR ---
Y-286: SUPERSEDED BY Y-322a | REASON statik priority + heappush | AUTHORITATIVE Y-322a
Y-296: PARTIAL KEEP | TTL now_ms geçerli | exchange ts → Y-315
Y-298: SUPERSEDED BY Y-322a | REASON tuple yapı birleşti | AUTHORITATIVE Y-322a
Y-300: SUPERSEDED BY Y-311 | REASON try/finally üstüne | AUTHORITATIVE Y-311
Y-303: SUPERSEDED BY Y-313 | REASON tek artırım | AUTHORITATIVE Y-313
Y-305: SUPERSEDED BY Y-322a | REASON per-request heap içinde | AUTHORITATIVE Y-322a
Y-306: SUPERSEDED BY Y-280 | REASON hard deadline en üstte | AUTHORITATIVE Y-280
Y-309: SUPERSEDED BY Y-315 | REASON dict yapısı | AUTHORITATIVE Y-315
Y-310: KEEP + Y-320a | counter+Lock + async-safe
Y-271: PARTIAL KEEP | f-string yasağı | quantize → Y-323
Y-264: REVISE | refcount zorunlu, tek Event YASAK | AUTHORITATIVE Y-310

--- ALIAS'LAR ---
B-42=alias of S-09
B-43=alias of S-07
B-44=alias of S-10
B-45=alias of S-10
B-46=alias of S-12
B-47=alias of S-12
B-49=alias of S-08
B-50=alias of S-02
B-52=alias of S-16
B-53=alias of S-17
B-54=alias of S-19.1
B-56=alias of S-04
B-57=alias of S-11
B-58=alias of S-07
B-59=alias of S-08
A-36..A-60=alias of B-36..B-60

---
## UNFROZEN BEYANI
- FROZEN YOK — REV5 116 YAMA (110+6 yeni 362,363,364,365,367,368)
- Her satır sorgulanabilir, blind kabul YASAK
- Yeni YAMA 362+ açık (fakat mevcut satırlar stabil)
- ROLLBACK adayları dahil her satır KEEP/FIX/MERGE/REVISE/ROLLBACK alabilir
- Pass 1/2/3 + runtime toplam 239 bulgu kapatıldı (227 + 12)

# END AnaYasa REV5 — 116 YAMA (110+6 yeni 362,363,364,365,367,368) — 239 bulgu

--- YAMA 362-368 (REV5 FAZ 0 kapanış — 6 yeni, 366 açılmadı) ---
362: FlushController resume() max(0) underflow gizleme + truthy bug fix — def resume: _counter -=1, if _counter<0: logger.warning FLUSH_COUNTER_UNDERFLOW (Y-346 uyumlu), _counter=0, if _counter==0: _async_event.set() — assert prod YASAK, WARNING+clamp (Y-368 ile REVISE)
363: DURUM timeout sayı düzeltme — kod L266 1.0 + L268 2.0 + L270 1.5 =4.5s, DURUM eski 5.5s yanlış (main 2.0s pool 1.0s olmuş), hedef single outer wait_for 3.5s, iç timeoutlar kaldırılacak FAZ2
364: Dokümantasyon sayı tutarsızlığı — 8 CONFLICT +1 PARTIAL vs 7+2 vs 7+1+4=12 doğru — 7 CONFLICT (350,351,352,353,357,358,359) +1 PARTIAL (356→362/368) +4 OK (354,355,360,361) =12, Tablo 8 yanlış DoD 7 doğru
365: Y-354 redundant note — L652 local_expired or exch_expired or exch_ts is None and local_expired — or öncesi 2 terim var, 3. terim redundant absorption ile çalışır ama redundant, KEEP + note
367: Yanıltıcı cümle fix — "12 runtime fix side-effect-safe onaylandı" → "12 fix tasarım onaylı DURUM'da side-effect-safe, TumModuller'de koda uygulanmış 4 adet (354,355,360,361) +1 kısmi (356), kalan 7'si FAZ2-4'te uygulanacak"
368: Y-356 assert REVISE — Y-356 "tek sayaç + assert >=0" prod crash FATAL, Y-346 WARNING zorunlu ile çelişir — REVISE: prod'da WARNING+clamp 0, assert sadece test/CI, _counter -=1 sonra if <0 warning clamp, Y-346 uyumlu

--- REV5 src/ 38 dosya tam ağaç (FAZ0-SRC-STRUCTURE, gizleme YASAK) ---
src/
  __init__.py
  main.py
  supervisor.py
  config/__init__.py, settings.py, validation.py, di.py, secrets.py (Y-353 DI zorunlu, global YASAK)
  data_layer/__init__.py, l2_buffer.py, obi.py, token_bucket.py, queues/async_state_queue.py, async_telemetry_queue.py, seq.py
  ws_manager/__init__.py, manager.py, snapshot.py, funding_scheduler.py
  execution/__init__.py, pacer.py, rest_gateway.py, order_manager.py, flush_controller.py (Y-362/Y-368 fix)
  storage/__init__.py, sqlite_writer.py, orderbook_store.py, archiver.py, sealed.py (Y-354/Y-365)
  emergency/__init__.py, close.py, persist.py, journal.py (Y-350,Y-351,Y-353)
  risk/__init__.py, portfolio_risk.py, whale_radar.py, funding.py
  utils/__init__.py, decimal.py, time.py, locks.py (Y-358), events.py, logging.py
  dashboard/__init__.py, app.py, routes.py, static/chart.min.js
  backtest/__init__.py, fill_model.py
tests/unit/test_yama_251_273.py ... test_yama_350_361.py + test_yama_362_368.py
tests/integration/test_lock_hierarchy.py, test_ws_seq_epoch.py, test_snapshot_gap.py
tests/chaos/test_queue_full.py, test_429_storm.py, test_deadlock.py

--- REV5 DoD ---
- [x] 116 YAMA (110+6), 366 açılmadı
- [x] Y-356 REVISE Y-368: assert kaldır WARNING+clamp, Y-346 uyumlu
- [x] Y-359 4.5s hesaplandı DURUM 5.5s yanlış Y-363
- [x] Y-355 asimetri not edildi KEEP
- [x] Y-354 redundant KEEP Y-365
- [x] 7 CONFLICT +1 PARTIAL +4 OK =12 doğru Y-364
- [x] 12 tasarım onaylı, koda girmiş 4+1 kısmi, 7 FAZ2-4 Y-367
- [x] src/ 38 dosya tam ağaç gizleme YOK
- [x] Global YASAK DI zorunlu Y-353 vurgu
- FAZ 0 KAPANDI — FAZ 1'e geçiş onaylandı