# MICO v2 — Proje Tüm Modüller REV5 — FAZ 0 KAPANDI
# REV5 — 116 YAMA (110 + 6 yeni: 362,363,364,365,367,368 — 366 açılmadı) — 38 dosya tam ağaç
# PO: Eser Göbekli — 2026-09-12 — FAZ 0 8 madde kick-back kapandı
# Önceki: REV4.9.9 FINAL-v4 (110 YAMA) → REV5 (116 YAMA, 12 tasarım onaylı / 4+1 kısmi kodda / 7 FAZ2-4)
# KURAL: src/ gizleme YASAK, her dosya listelenecek

================================================================================
00 — Foundation — REV5
================================================================================
Stack: Python 3.11 asyncio + mp.Queue STATE DROP_NEVER 200 blocking via AsyncStateQueue bridge (Y-329 asyncio.Queue(200) + single writer task -> mp.Queue Y-357 to_thread deadlock fix, ayrı executor YASAK Y-337, drain() SIGTERM zorunlu) + Telemetry DROP_OLDEST 1000 via AsyncTelemetryQueue + Numba CVD warmup dummy typed array + SQLite WAL STATE positions orders version sealed_at_ms emergency_pending + Parquet snappy live 7d archive 365d archiver asyncio.to_thread atomic .tmp->rename two-phase rotation _closed orphan 5m .deleted 1h lock PID timestamp PID check + DDL original_planned_entry original_tp original_sl IMMUTABLE current_tp_shifted current_sl_shifted version optimistic sealed_at_ms + force-flush daemon 2 bounded 5 put_nowait DROP telemetry only zero-disk (state_queue 200 DROP_NEVER blocking ayrı) + read lock single RLock copy-on-read memoryview no leak torn read YASAK searchsorted bids -price asks price ayrı + preallocated 5000 hard cap low-water 4000 atomic loop while batch C memmove Python loop FATAL + persistent ClientSession TCPConnector 100 keepalive 60 aiohttp.request FATAL + TokenBucket REAL SINGLE GLOBAL bucket rate 8 burst 15 (separate buckets silindi Y-275) SINGLE GLOBAL no bypass REST gateway SINGLE mp.Queue state DROP_NEVER + per-IP 15 per-symbol defaultdict 2 + sem_emergency 3 + sem_normal 9 (Y-342 ayrı havuz) acquire 2.0s outer 3.5s [Y-359 kod 1.0+2.0+1.5=4.5s, DURUM eski 5.5s yanlış → 4.5s Y-363] pacer PriorityQueue min-spacing CRITICAL 2ms NORMAL 20ms REBUILD 50ms (Y-330) pacer_priority 0/1/2 distinct (Y-304) single-flight same symbol global_429 per-symbol decay 60s half-open 60s test 1 + emergency_MAX_RETRY 1 reduce_only True true sweep verified qty epsilon dust sweep min_lot/2 cache TTL 500ms + slippage leverage adjusted min(3%,10%/lev) 20x=0.5% + position_mode ONE_WAY|HEDGE required FATAL margin_mode ISOLATED target_leverage 5 set_leverage startup + exchange_info Decimal quantize str(Decimal) price_precision qty_precision ayrı + symbol STATUS HALTED/BREAK 5m check INVALIDATE emergency + order_type LIMIT_IOC->{LIMIT IOC} via _map_order_type() + WS ping 15s pong 5s 3 fail reconnect jitter ±20% + expected_seq per-symbol seq_epoch reconnect epoch++ reset after snapshot same lock pre_sync_queue clear seq<=snapshot + out-of-order drop ts<=last + seq gap resync + process model 3 process max_ws 10 each coin single process L2 process-local mp.Queue broadcast + fresh_tick_event defaultdict(Event) safe get cleanup DROPPED set+clear not del + state machine ACTIVE|WAITING_TICK|STALE|INVALID priority INVALID>STALE>WAITING>ACTIVE transition() + max_pending 600000 hard deadline FVG_EXPIRED_HARD_DEADLINE event telegram WARNING quarantine 60s max 3 retry INVALIDATED + paused_ms float accumulate even invalid (Y-255) + breach_start_ms only valid + stale>5s only new setup TP/SL devam + filled_by_order max() monotonic flip assert same sign reduce_only + sealed_orders OrderedDict TTL 300s dict value {sealed_at_local_ms, exchange_ts_ms, version} (Y-315) expire local now_ms reuse exchange_ts_ms None guard (Y-336) + epsilon symbol min_lot/2 dust sweep + fee_fallback 0.0003 cache taker/maker ayrı + funding UTC 00/08/16 scheduler ayrı task (Y-331) monotonic next_candle extrapolate max(0,mono_now-last_mono) (Y-257) + crash reconciliation exchange=truth fetch_position DB update WAL replay WS paused startup_complete emergency_pending flag + lock file PID+timestamp orphan override PID check + lock hierarchy buffer>fill>sqlite>pacer>flush>telemetry (Y-339) sealed_lock ayrı CI assert reentrant owner check + mp.Queue state blocking + SIGTERM emergency_close_all 30s grace Docker stop_grace 35s tasks pop done_callback (Y-266) + force-flush daemon 2 bounded 5 put_nowait DROP telemetry only zero-disk store_flush_suspended counter+Lock refcount==0 ise clear ALWAYS (Y-264 REVISE + Y-310) counter underflow WARNING (Y-346) + health per-coin %80 alive 200 else 503 last_tick_age<30s archiver<25h sqlite<10s + secret Docker secrets logs mask + DNS not IP hardcode TZ=UTC assert + API key trade only + dashboard auth token SSE + float isclose epsilon 1e-9 + R:R buffer 1.4999 + NaN/Inf sanitize drop + oi_usd = oi_contract*mark + min_lot skip log + token bucket header fallback local min() + PriorityQueue not FIFO (Y-262) + OBI aktif len (Y-344) + event bypass telemetry (Y-345)

================================================================================
01 — Config & Runtime — REV5
================================================================================
Config Kritik: position_mode ONE_WAY required FATAL margin_mode ISOLATED default target_leverage 5 set_leverage startup, TEST risk 0.008 max 3 daily -0.04 0.036<=0.04 PASS PROD 0.006 max 2 daily -0.02 0.018<=0.02 PASS, hysteresis 5m max_pending 10m flap 3, _ms whitelist all *_ms int minutes YASAK FATAL (Y-269) sleep_ms/1000, emergency slippage leverage adjusted min(3%,10%/lev) MAX_RETRY 1 reduce_only True true sweep verified qty epsilon dust sweep min_lot/2 cache TTL 500ms store_flush_suspended counter+Lock refcount==0 ise clear ALWAYS underflow WARNING emergency_tasks pop try/finally, whale trust OI USD 50k sweep 1.5x cleanup decay exp(-age/1h) band ±0.5% fingerprint tick_size (Y-267) wash triple OI+CVD+taker ratio (Y-268), retention 7/365 atomic to_thread .tmp->rename, breach pause float accumulate even invalid cancellable per-symbol WAITING gap quarantine 60s hard deadline 10m next_candle extrapolate max(0)+5000, tp_shift sl_shift be_trail original immutable version net fee 1.4999 taker/maker ayrı min_lot epsilon dust sweep old_trail None, prealloc 5000 hard cap low-water 4000 fixed trim atomic loop C memmove searchsorted bids -price asks price ayrı torn read YASAK executor optional main YASAK, snappy live1 archive9 gzip YASAK, force-flush daemon 2 bounded 5 put_nowait DROP zero-disk state_queue DROP_NEVER telemetry DROP_OLDEST store_flush_suspended clear ALWAYS, read lock single RLock copy-on-read memoryview no leak, per-IP 15 per-symbol defaultdict 2 sem_emergency 3 sem_normal 9 acquire 2.0s outer 3.5s [Y-359 kod 1.0+2.0+1.5=4.5s, DURUM eski 5.5s yanlış → 4.5s Y-363] pacer min-spacing 2/20/50 sem_critical merged single-flight global 429 per-symbol decay half-open SINGLE GLOBAL bucket rate 8 burst 15 SINGLE GLOBAL no separate buckets (Y-275 FIX), funding 8h UTC scheduler ayrı task daily UTC weekly MONDAY UTC all UTC monotonic, correlation window 3600000 min_samples 30 directional hedge, risk math fixed Decimal quantize str(Decimal) price_precision qty_precision separate, archive to_thread .tmp->rename lock PID check, pre_sync_queue seq_id expected_seq epoch reset same lock clear seq<=snapshot ping 15s pong 5s 3 fail, sealed_orders TTL 300 dict value version optimistic, epsilon symbol dust sweep, fee_fallback 0.0003 taker/maker ayrı, process model 3*10 REST gateway single state DROP_NEVER, lock hierarchy buffer>fill>sqlite>pacer>flush>telemetry sealed_lock ayrı, signal handler 30s grace tasks pop, health per-coin %80, secret DNS TZ UTC isclose R:R 1.4999 NaN oi_usd dashboard inline CSS chart.min.js cached CDN/npm FATAL

Validation minimal: position_mode margin_mode leverage set FATAL, config parse FATAL all _ms int, entry<exit<emergency, max_req<=10, l2_mp_queue false, obi_numba false, hysteresis minutes YASAK, fvg method time_breach değil hata, partial new_active_qty!=filled_qty max() yoksa WARNING, qty=remaining_qty FATAL, tp_fixed sl_fixed FATAL, original yoksa FATAL PARTIAL_CLOSED yoksa WARNING sealed TTL yoksa WARNING, MAX_BUFFER 5000 değil WARNING trim 4000 low-water değil WARNING searchsorted bids vs asks ayrı değil WARNING torn read leak FATAL Python loop FATAL list.sort FATAL, ghost_reset false hata breach_pause false hata skip true hata reset false WARNING stale false WARNING waiting_for_fresh_tick gap quarantine false WARNING discard false WARNING cancellable per-symbol false WARNING max pending yoksa WARNING flap 3 yoksa WARNING sealed TTL false WARNING, critical_bypass true FATAL bypass true FATAL persistent session false WARNING per_ip 15 değil WARNING per_symbol defaultdict değil WARNING acquire 2.0s değil WARNING outer 3.5s değil WARNING pacer PriorityQueue değil WARNING sem_emergency/sem_normal aynı WARNING global 429 per-symbol değil WARNING max_retry 1 değil WARNING reduce_only false FATAL true sweep false WARNING verified qty false WARNING epsilon false WARNING store_flush_suspended clear ALWAYS değil WARNING underflow WARNING yok WARNING, time_source exchange_timestamp değil hata last_local_tick_monotonic false WARNING next_candle extrapolate max(0) değil WARNING, force_flush false daemon false hata workers 2 değil WARNING bounded 5 değil WARNING put_nowait false WARNING zero-disk false WARNING state_queue DROP_NEVER değil FATAL snappy live1 archive9 değil WARNING to_thread .tmp->rename değil WARNING pre_sync_queue false WARNING seq_id expected_seq epoch false WARNING ping 15s false WARNING, inline CSS değil CDN FATAL npm FATAL cached chart yoksa WARNING, _ms whitelist dışı REJECT, timer loop yoksa hata, OBI sabit 5000 varsayımı FATAL, CRITICAL_ALERT telemetry_queue FATAL, emit_event içinde await FATAL, trim sessiz FATAL, trim log rate-limited değil FATAL, revision notice format yanlış FATAL, emergency_close state_queue.put FATAL, emergency_persist_state timeout yok FATAL, is_emergency ve priority=CRITICAL aynı FATAL, pacer_min_delay[0] > 5ms FATAL, sleep(0) lock altında FATAL, pop recursion FATAL, Pacer sınıfı 2+ tanımlı FATAL, Lock hierarchy ters sıra FATAL, reconciliation ve emergency paralel FATAL, ayrı executor _state_executor FATAL, sealed_orders scalar not dict FATAL, sealed None guard yok FATAL, state_queue is asyncio.Queue FATAL

================================================================================
02 — Data Layer — REV5
================================================================================
ws_manager: preallocated 5000 hard cap low-water 4000 fixed trim atomic loop while batch bulk C memmove searchsorted bids -price asks price ayrı + Lock hierarchy single RLock buffer> + read lock copy-on-read memoryview no leak torn read YASAK no await in copy + exchange ts + last_local_tick_monotonic + breach pause float accumulate even invalid cancellable per-symbol Event safe get + batch vectorized diff outside lock bulk C-slice inside + pre_sync_queue snapshot seq_id expected_seq epoch reset same lock clear seq<=snapshot + out-of-order drop ts<=last + seq gap snapshot resync + snapshot gecikme batch drop + metric replay YASAK (Y-340) + ping 15s pong 5s 3 fail reconnect jitter ±20% + process-local L2 buffer max_ws 10 3 process + fresh_tick_event defaultdict(Event) safe get cleanup DROPPED set+clear + state machine ACTIVE|WAITING|STALE|INVALID priority transition() + hard deadline 10m next_candle extrapolate max(0)+5000 + quarantine 60s 3 retry + sealed_orders TTL dict value version.

Pseudo REV5:

# Buffer Management Fixed 5000 Hard Cap Low-water 4000 (Y-251 + S-04)
class L2Buffer:
  def __init__(self):
    self.bids_price = np.zeros(5000, dtype=np.float64)
    self.bids_qty = np.zeros(5000, dtype=np.float64)
    self.asks_price = np.zeros(5000, dtype=np.float64)
    self.asks_qty = np.zeros(5000, dtype=np.float64)
    self.bids_len = 0
    self.asks_len = 0
    self.lock = threading.RLock()                # Y-253
    self.seq_epoch = defaultdict(int)            # Y-314
    self.expected_seq = {}                       # Y-314
    self.pre_sync_queue = defaultdict(list)      # Y-314 + Y-352 append fix
    self._seq_lock = threading.Lock()            # Y-314
    self._trim_count = 0
    self._trim_log_counter = defaultdict(int)    # Y-348

  def apply_batch(self, diffs, batch_epoch, symbol):
        # Y-352 pre_sync_queue append fix — filter var append YOK bug
    with self.lock:
      if batch_epoch != self.seq_epoch.get(symbol, 0):
        return
      # Y-332: TEK SAYAÇ İSMİ batch_bids/batch_asks (Y-335 değil, düzeltilmiş)
      batch_bids = 0
      batch_asks = 0
      for side, price, qty in diffs:
        if qty == 0.0: continue
        if side == 'bid':
          idx_tmp = np.searchsorted(-self.bids_price[:self.bids_len], -price) if self.bids_len > 0 else 0
          found_tmp = self.bids_len > 0 and idx_tmp < self.bids_len and self.bids_price[idx_tmp] == price
          if not found_tmp: batch_bids += 1
        else:
          idx_tmp_a = np.searchsorted(self.asks_price[:self.asks_len], price) if self.asks_len > 0 else 0
          found_tmp_a = self.asks_len > 0 and idx_tmp_a < self.asks_len and self.asks_price[idx_tmp_a] == price
          if not found_tmp_a: batch_asks += 1
      # Y-318a: iki ayrı loop
      while self.bids_len + batch_bids >= 5000:
        self.trim('bids', batch_bids)
      while self.asks_len + batch_asks >= 5000:
        self.trim('asks', batch_asks)
      for side, price, qty in diffs:
        if side == 'bid':
          idx = np.searchsorted(-self.bids_price[:self.bids_len], -price)
          found = self.bids_len > 0 and idx < self.bids_len and self.bids_price[idx] == price
          if found:
            if qty == 0.0:
              self.bids_price[idx:self.bids_len-1] = self.bids_price[idx+1:self.bids_len]
              self.bids_qty[idx:self.bids_len-1] = self.bids_qty[idx+1:self.bids_len]
              self.bids_len -= 1
            else:
              self.bids_qty[idx] = qty
          else:
            if qty == 0.0: continue
            if idx < 5000:
              self.bids_price[idx+1:self.bids_len+1] = self.bids_price[idx:self.bids_len]
              self.bids_qty[idx+1:self.bids_len+1] = self.bids_qty[idx:self.bids_len]
              self.bids_price[idx] = price
              self.bids_qty[idx] = qty
              if self.bids_len < 5000: self.bids_len += 1
        else:
          idx = np.searchsorted(self.asks_price[:self.asks_len], price)
          found = self.asks_len > 0 and idx < self.asks_len and self.asks_price[idx] == price
          if found:
            if qty == 0.0:
              self.asks_price[idx:self.asks_len-1] = self.asks_price[idx+1:self.asks_len]
              self.asks_qty[idx:self.asks_len-1] = self.asks_qty[idx+1:self.asks_len]
              self.asks_len -= 1
            else:
              self.asks_qty[idx] = qty
          else:
            if qty == 0.0: continue
            if idx < 5000:
              self.asks_price[idx+1:self.asks_len+1] = self.asks_price[idx:self.asks_len]
              self.asks_qty[idx+1:self.asks_len+1] = self.asks_qty[idx:self.asks_len]
              self.asks_price[idx] = price
              self.asks_qty[idx] = qty
              if self.asks_len < 5000: self.asks_len += 1

  def trim(self, side, batch_new):                # Y-317a + Y-348
    trimmed = 0
    arr_len = self.bids_len if side == 'bids' else self.asks_len
    while arr_len + batch_new >= 5000:
      trim_n = min(1000, arr_len)
      if trim_n == 0: break
      arr_len -= trim_n
      trimmed += trim_n
    if trimmed > 0:
      self._trim_log_counter[side] += 1
      if self._trim_log_counter[side] % 100 == 0:  # Y-348 rate-limited
        logger.warning("BUFFER_TRIM", side=side, count=self._trim_log_counter[side], trimmed=trimmed)
    if side == 'bids': self.bids_len = arr_len
    else: self.asks_len = arr_len

  def get_obi(self):                              # Y-344
    # aktif len — fixed 5000 varsayımı YASAK
    return compute_obi(
      self.bids_price[:self.bids_len], self.bids_qty[:self.bids_len],
      self.asks_price[:self.asks_len], self.asks_qty[:self.asks_len]
    )

  def get_obi_safe_sync(self):
    with self.lock:
      return (self.bids_price[:self.bids_len].copy(), self.bids_qty[:self.bids_len].copy(),
              self.asks_price[:self.asks_len].copy(), self.asks_qty[:self.asks_len].copy())

  def on_snapshot(self, snapshot, symbol):        # Y-274 + 278 + 313
    with self.lock:
      if len(snapshot.bids) > 5000 or len(snapshot.asks) > 5000:
        snapshot.bids = snapshot.bids[:5000]
        snapshot.asks = snapshot.asks[:5000]
      # Y-313: tek artırım snapshot başına bir kez
      self.seq_epoch[symbol] += 1
      self.bids_price[:len(snapshot.bids)] = snapshot.bids_price
      self.bids_qty[:len(snapshot.bids)] = snapshot.bids_qty
      self.bids_len = len(snapshot.bids)
      self.asks_price[:len(snapshot.asks)] = snapshot.asks_price
      self.asks_qty[:len(snapshot.asks)] = snapshot.asks_qty
      self.asks_len = len(snapshot.asks)
      self.expected_seq[symbol] = snapshot.seq + 1
      with self._seq_lock:
        self.pre_sync_queue[symbol] = [
          d for d in self.pre_sync_queue[symbol]
          if d['seq'] > snapshot.seq and d['epoch'] == self.seq_epoch[symbol]
        ]


# Y-329 + Y-337: AsyncStateQueue — mp.Queue + semaphore(8) + to_thread (ayrı executor YASAK)
_state_sem = asyncio.Semaphore(8)

class AsyncStateQueue:
  def __init__(self, maxsize=200):
    self._q = mp.Queue(maxsize=maxsize)
  async def put(self, item):
    async with _state_sem:
      await asyncio.to_thread(self._q.put, item)
  async def get(self):
    return await asyncio.to_thread(self._q.get)
  def put_nowait(self, item):
    try: self._q.put_nowait(item)
    except mp.QueueFull: pass
  async def drain(self):                          # Y-337 SIGTERM zorunlu
    while not self._q.empty():
      await asyncio.sleep(0)

class AsyncTelemetryQueue:
  def __init__(self, maxsize=1000):
    self._q = mp.Queue(maxsize=maxsize)
  def put_nowait(self, item):
    try: self._q.put_nowait(item)
    except mp.QueueFull:
      try: self._q.get_nowait()
      except mp.QueueEmpty: pass
      try: self._q.put_nowait(item)
      except mp.QueueFull: pass

state_queue = AsyncStateQueue(maxsize=200)
telemetry_queue = AsyncTelemetryQueue(maxsize=1000)


rest_client: persistent ClientSession TCPConnector 100 keepalive 60 timeout 3.5 aiohttp.request FATAL + TokenBucket REAL SINGLE GLOBAL bucket rate 8 burst 15 SINGLE GLOBAL (Y-275) + REST gateway single process mp.Queue + per-IP 15 per-symbol defaultdict 2 + sem_emergency 3 + sem_normal 9 acquire 2.0s outer 3.5s [Y-359 kod 1.0+2.0+1.5=4.5s, DURUM eski 5.5s yanlış → 4.5s Y-363] pacer PriorityQueue min-spacing 2/20/50 (Y-330) nominal CRITICAL 2ms max 5ms emergency tolere (Y-343) sem_critical merged single-flight same symbol + global 429 per-symbol decay half-open + emergency_MAX_RETRY 1 reduce_only True true sweep verified qty epsilon dust sweep + slippage leverage adjusted + position_mode margin_mode leverage set + Decimal quantize str(Decimal) + symbol STATUS 5m + order_type mapping + fee cache fallback 0.0003 taker/maker ayrı + PriorityQueue not FIFO.

class TokenBucket:
  def __init__(self, rate=8, burst=15):
    self.tokens = burst; self.rate = rate; self.last = monotonic(); self.burst = burst
    assert rate == 8 and burst == 15, "SINGLE GLOBAL rate8 burst15"
  async def acquire(self):
    while True:
      now = monotonic()
      self.tokens = min(self.burst, self.tokens + (now - self.last) * self.rate)
      self.last = now
      if self.tokens >= 1: self.tokens -= 1; return True
      await asyncio.sleep((1 - self.tokens) / self.rate)

import heapq

# Pacer — Y-322a + Y-329 + Y-330 + Y-343 + Y-347
class Pacer:
  def __init__(self):
    self._heap = []                              # (base_prio, seq, enqueue_ts, payload)
    self._seq = itertools.count()
    self._lock = threading.Lock()                # Y-322a
    self._last_dispatch = {0: 0.0, 1: 0.0, 2: 0.0}   # Y-330
    self._min_delay = {0: 0.002, 1: 0.020, 2: 0.050}  # Y-343 2ms tolere

  async def enqueue(self, base_prio, payload):   # Y-332 sync yapıldı
    assert base_prio in (0, 1, 2), "pacer_priority 0/1/2 distinct"
    if base_prio == 0 and len(self._heap) >= 200:
      raise RuntimeError("CRITICAL pacer full — emergency fallback")  # Y-322b
    item = (base_prio, next(self._seq), time.time(), payload)
    with self._lock:
      heapq.heappush(self._heap, item)           # Y-328 heapify YASAK

  async def pop(self):                           # Y-327 + Y-347
    while True:
      with self._lock:
        if not self._heap:
          return None
        base, seq, ts, payload = heapq.heappop(self._heap)
        age_bonus = int((time.time() - ts) // 1)
        effective = max(0, base - age_bonus)
        if effective < base:
          heapq.heappush(self._heap, (effective, seq, ts, payload))
          wait = True
        else:
          now = time.monotonic()
          since = now - self._last_dispatch[base_prio]  # Y-355 fix
          gap = self._min_delay[effective] - since
          if gap > 0:
            heapq.heappush(self._heap, (effective, seq, ts, payload))
            wait = True
          else:
            self._last_dispatch[base_prio] = now  # Y-355 base_prio olmalı
            wait = False
            result = payload
      if wait:
        await asyncio.sleep(0)                   # Y-347 lock dışı yield
        continue
      return result


# Y-321a + Y-326 + Y-338 + Y-342: RestGateway
class RestGateway:
  def __init__(self):
    self.token_bucket = TokenBucket(8, 15)
    self.critical_bypass = False
    self.per_ip_sem = defaultdict(lambda: asyncio.Semaphore(15))
    self.per_symbol_sem = defaultdict(lambda: asyncio.Semaphore(2))
    self.sem_emergency = asyncio.Semaphore(3)    # Y-342
    self.sem_normal = asyncio.Semaphore(9)       # Y-342
    self.pacer = Pacer()

  async def acquire(self, ip, symbol, is_emergency=False):
        # Y-359 outer 3.5s single wait_for, iç içe 5.5s YASAK [eski 5.5s yanlış, gerçek 4.5s Y-363]
    if self.critical_bypass:
      raise RuntimeError("FATAL if bypass var")
    ip_sem = self.per_ip_sem[ip]
    sym_sem = self.per_symbol_sem[symbol]
    pool = self.sem_emergency if is_emergency else self.sem_normal
    try:
      await asyncio.wait_for(pool.acquire(), timeout=1.0)     # Y-342
      try:
        await asyncio.wait_for(ip_sem.acquire(), timeout=2.0)
        try:
          await asyncio.wait_for(sym_sem.acquire(), timeout=1.5)
        except asyncio.TimeoutError:
          ip_sem.release(); pool.release(); raise
      except asyncio.TimeoutError:
        pool.release(); raise
    except asyncio.TimeoutError:
      raise
    if not await self.token_bucket.acquire():    # Y-326
      sym_sem.release(); ip_sem.release(); pool.release(); return False
    return True

  def release(self, ip, symbol, is_emergency=False):
    self.per_symbol_sem[symbol].release()
    self.per_ip_sem[ip].release()
    (self.sem_emergency if is_emergency else self.sem_normal).release()

  async def post_market_order(self, payload, priority=0):
    try:
      return await self.pacer.enqueue(priority, payload)
    except RuntimeError:
      emit_event(CRITICAL_ALERT, {msg: "PACER_CRITICAL_FULL_FALLBACK"})
      return await self._direct_market_post(payload["symbol"], reduce_only=True)

  async def _direct_market_post(self, symbol, reduce_only=True):  # Y-338
    """Emergency — pacer bypass, token bucket respected, NO RAISE"""
    for attempt in (1, 2):
      if await self.token_bucket.acquire():
        return await self._exchange_post(symbol, reduce_only=reduce_only)
      await asyncio.sleep(0.5)
    emit_event(CRITICAL_ALERT, {msg: "EMERGENCY_BUCKET_EXHAUSTED", symbol: symbol})
    return None


sqlite_writer: WAL STATE positions orders version sealed_at_ms emergency_pending + state_queue DROP_NEVER 200 blocking put via AsyncStateQueue telemetry 1000 DROP_OLDEST via AsyncTelemetryQueue + DDL original immutable version tp_fixed DELETE sealed_at_ms sealed_orders TTL dict value version optimistic + idempotency max() flip assert + net fee 1.4999 taker/maker ayrı + Decimal str(Decimal) + fill_lock + sealed_lock ayrı.

storage/orderbook_store.py: Parquet snappy live1 archive9 live 7 archive 365 + archiver to_thread atomic .tmp->rename two-phase .closed rotation orphan recovery 5m .deleted 1h lock PID timestamp PID check + 00:00 .lock + batch 500 flush 5000 + force-flush daemon 2 bounded 5 put_nowait DROP telemetry only zero-disk store_flush_suspended counter+Lock refcount==0 ise clear ALWAYS (Y-264 + Y-310) underflow WARNING (Y-346) + pre_sync_queue seq_id expected_seq epoch ping pong + read lock single RLock + disk full 90% oldest delete + next_candle extrapolate max(0)

# FlushController — Y-320a + Y-325 + Y-346
class FlushController:
  def __init__(self):
    self._counter = 0
    self._lock = threading.Lock()
    self._async_event = asyncio.Event()
    self._async_event.set()

  def suspend(self):
    with self._lock:
      self._counter += 1
      if self._counter == 1:
        try: asyncio.get_event_loop().call_soon_threadsafe(self._async_event.clear)
        except Exception: self._async_event.clear()

  def resume(self):
    with self._lock:
      self._counter -= 1
      if self._counter < 0:
        logger.warning("FLUSH_COUNTER_UNDERFLOW", current=self._counter)
        self._counter = 0
      if self._counter == 0:
        try: asyncio.get_event_loop().call_soon_threadsafe(self._async_event.set)
        except Exception: self._async_event.set()

  def is_suspended(self):
    with self._lock:
      return self._counter > 0

flush_controller = FlushController()

async def buffer_l2_nonblocking(data, is_state=False):   # Y-320a + Y-325
  # Y-325: telemetry suspend'te DROP, WAIT değil
  if not is_state and flush_controller.is_suspended():
    return
  if is_state:
    await state_queue.put(data)              # Y-329 AsyncStateQueue
  else:
    telemetry_queue.put_nowait(data)         # Y-329 AsyncTelemetryQueue

async def archiver_task():
  while True:
    await sleep_until_00_00()
    await asyncio.to_thread(_blocking_archive_sync)

def _blocking_archive_sync():
  for f in live_path.glob("*.parquet"):
    if f.stat().st_mtime < time.time()-300: f.rename(f.with_suffix("._closed.parquet"))
  for f in live_path.glob("*._closed.parquet"):
    tmp = archive_path/(f.name+".tmp")
    shutil.copy(f, tmp)
    if verify_checksum(f, tmp):
      os.rename(tmp, archive_path/f.name.replace("._closed",""))
      f.unlink()
  for f in archive_path.glob("*.parquet"):
    if f.stat().st_mtime < time.time()-365*86400:
      f.rename(f.with_suffix(".deleted"))
  for f in archive_path.glob("*.deleted"):
    if f.stat().st_mtime < time.time()-3600: f.unlink()

================================================================================
03 — Features — REV5
================================================================================
whale_radar: preallocated + Lock single RLock + Numba warmup boot typed array + SADECE CVD + trust OI USD 50k delta cross + sweep 1.5x + cleanup decay exp(-age/1h) band ±0.5% fingerprint tick_size + spoof_timeout exchange ts fallback local NTP drift <50 else disable + OI USD + wash triple OI+CVD+taker ratio.

Pseudo OI USD 50k band ±0.5% tick_size:

def warmup(): _numba_cvd(np.zeros((100,3), dtype=np.float64))

if order_lifetime_ms > 3000 and fill_ratio >= 0.30:
  if current_oi_delta_usd > 50000:
    band_key = f"{symbol}_{int(price / (tick_size*5))}"
    whale_trust_score[band_key] += 1
  else: emit_event(SPOOF_WASH_DETECTED)

trust_score = sum(exp(-(now-ts)/3600) for ts in whale_times[band])
if not (cvd_up and oi_up and taker_buy_ratio > 0.6): emit_event(SPOOF_WASH_DETECTED)

micro_trigger: State Machine IDLE->SWEEP->MSS->FVG_OTE->MICRO_CONFIRM->TRIGGER + hysteresis max pending 10m flap 3 + timer cancellable per-symbol Event safe get + discard on pause fresh window + WAITING gap quarantine 60s + stale only new setup + Ghost + exchange ts + breach_start only valid + paused_ms float accumulate even invalid + hard deadline 10m next_candle extrapolate max(0)+5000 + TP shift original version + net fee 1.4999 taker/maker ayrı + trailing None check + min_lot epsilon symbol dust sweep + OI delta + incremental OBI aktif len (Y-344).

paused_ms = defaultdict(float)
pause_start = {}
fresh_tick_event = defaultdict(asyncio.Event)
expected_seq = {}
seq_epoch = defaultdict(int)
sealed_orders = OrderedDict()

async def cancellable_sleep(symbol, timeout_ms):
  event = fresh_tick_event.get(symbol)
  if event is None: event = fresh_tick_event[symbol]
  try: await asyncio.wait_for(event.wait(), timeout=timeout_ms/1000)
  except asyncio.TimeoutError: pass

def transition(symbol, new_state, reason):
  priority = {"INVALID": 4, "STALE": 3, "WAITING_TICK": 2, "ACTIVE": 1}
  if priority[new_state] >= priority[current_state[symbol]]:
    current_state[symbol] = new_state
    emit_event(new_state, reason)

# Y-306 + Fix 6: reset sırası ZORUNLU
if paused_ms[symbol] >= 600000:
  emit_event(FVG_EXPIRED_HARD_DEADLINE, {symbol})
  reset_to_idle(symbol)                      # Y-294 içinde fresh_tick_event.clear
  cleanup_telemetry(symbol)
  continue                                   # redundant clear silindi

if not is_valid:
  now_m = monotonic()
  if symbol not in pause_start: pause_start[symbol] = now_m
  else:
    paused_ms[symbol] += (now_m - pause_start[symbol]) * 1000
    pause_start[symbol] = now_m
  stale = now_m - last_local_tick_monotonic[symbol]
  if stale > 5.0 and current_position_qty == 0:
    emit_event(FVG_INVALIDATED, {reason: STALE})
    transition(symbol, "STALE", reason)
    reset_to_idle(symbol)
  await cancellable_sleep(symbol, self.sleep_ms)
  continue
else:
  if symbol in pause_start:
    paused_ms[symbol] += (monotonic() - pause_start[symbol]) * 1000
    del pause_start[symbol]
  if waiting_for_fresh_tick[symbol]:
    if last_update_ms > reconnect_ms_local:
      waiting_for_fresh_tick[symbol] = False
      if self._was_breached_during_gap(symbol):
        if self._fetch_gap_snapshot_with_timeout():
          emit_event(FVG_INVALIDATED, {reason: BREACHED_DURING_WS_GAP})
        else:
          transition(symbol, "WAITING_TICK", "QUARANTINE")
          await asyncio.sleep(60)
      reset_to_idle(symbol)
      continue
    else:
      await cancellable_sleep(symbol, self.sleep_ms)
      continue
  if was_paused:
    current_micro_candle.reset()
    next_candle_target_ms = last_exchange_ts + max(0, monotonic() - last_local_mono) * 1000 + 5000
    continue

if fvg_detected and is_valid:
  breach_start_ms[symbol] = exchange_timestamp()

if old_trail is not None:
  trail_delta = old_trail - original_planned_entry
  new_trail = new_avg + trail_delta
else: new_trail = None

new_sl_candidate = original_sl + (new_avg - original_planned_entry)
new_sl = max(current_sl, new_sl_candidate) if LONG else min(current_sl, new_sl_candidate)
if be_active:
  new_sl = max(new_sl, current_be) if LONG else min(new_sl, current_be)

================================================================================
04 — Risk & Execution — REV5
================================================================================
portfolio_risk: bias majority + max SL 2.5% + second OI USD trust 50k + second bypass same id + hysteresis max pending + partial PARTIAL_CLOSED sealed TTL version optimistic original immutable + TP/SL shift original version + net fee 1.4999 taker/maker ayrı + trailing None monotonic BE never below + min_lot epsilon symbol dust sweep + risk math fixed + funding UTC + correlation window 1h min 30 + position_mode margin_mode leverage + Decimal str(Decimal).

original = get_original(position_id)
entry_delta = new_avg - original.entry
new_tp = original.tp + entry_delta
new_sl_candidate = original.sl + entry_delta
new_sl = max(current_sl, new_sl_candidate) if LONG else min(current_sl, new_sl_candidate)
if be_active: new_sl = max(new_sl, current_be) if LONG else min(new_sl, current_be)
new_be = new_avg

total_fee = new_avg * fee_taker + new_tp * fee_maker
net_reward = abs(new_tp - new_avg) - total_fee
net_risk = abs(new_avg - new_sl) + total_fee
if net_risk <= 0 or net_reward / net_risk < 1.4999:
  emit_event(TRADE_REJECTED_FEE_DRAG)
  await graceful_exit()

max_risk_day = risk * max_pos * (1 + second_mult)

epsilon = min_lot / 2
if abs(target_qty) < epsilon: emit_event(SECOND_ENTRY_SKIPPED, {BELOW_MIN_LOT}); return False

existing = filled_by_order.get(oid, 0)
if math.isclose(new_fill, 0, abs_tol=1e-9): return
if existing != 0 and (existing > 0) != (new_fill > 0):
  emit_event(CRITICAL, {FLIP_DETECTED}); await emergency_close(symbol); return
filled_by_order[oid] = max(existing, new_fill) if existing != 0 else new_fill
new_active_qty = filled_by_order[oid]


# emergency_close REV5 (Y-315 + Y-336 + Y-338 + Y-341)
async def emergency_close_with_retry(symbol):
  if symbol in emergency_tasks: return await emergency_tasks[symbol]
  async def _emergency():
    success = False
    order_id = None
    fill = None
    current_position_version = 0
    flush_controller.suspend()
    try:
      # Y-341: emergency state persist SQLite WAL direct
      await emergency_persist_state(symbol, {"phase": "start"})
      for attempt in (1, 2):
        pos_qty = await get_verified_position_qty(symbol)
        if pos_qty is None:
          await asyncio.sleep(0.5); continue
        if abs(pos_qty) < min_lot / 2:
          if abs(pos_qty) < min_lot * 0.1:
            emit_event(DUST_POSITION_REMAINING, {symbol, qty: pos_qty})
            return "DUST_ACKNOWLEDGED"
        pos_side = "BOTH" if position_mode == "ONE_WAY" else position_mode_side(symbol)
        qty_str = quantize_qty_str(pos_qty)
        payload = {"symbol": symbol, "quantity": qty_str, "side": "CLOSE",
                   "type": "MARKET", "reduceOnly": True, "positionSide": pos_side}
        fill = await post_market_order(payload, priority=CRITICAL)
        if fill is None or fill.executedQty == 0:
          raise CatastrophicExecutionError("SILENT_REJECT")
        if abs(fill.slippage) > leverage_adjusted_slippage(symbol):
          if attempt == 1:
            await asyncio.sleep(0.2); continue
          else:
            await post_true_market_sweep(symbol, qty=pos_qty, reduceOnly=True)
            success = True
            return "FORCE_LIQUIDATED_BY_SYSTEM"
        success = True
        return "CLOSED"
      raise CatastrophicExecutionError("VERIFY_FAILED_STILL_OPEN")
    except (aiohttp.ClientError, asyncio.TimeoutError):
      verified = await fetch_verified_position_risk_direct(symbol)
      if verified.qty is not None and abs(verified.qty) >= min_lot / 2:
        emit_event(CRITICAL_ALERT, {msg: "EMERGENCY FAILED STILL ACTIVE"})
        raise CatastrophicExecutionError("POSITION_STILL_OPEN")
    except RuntimeError as e:                  # Y-338
      result = await self._direct_market_post(symbol, reduce_only=True)
      if result is None:
        return "EMERGENCY_FAILED_POSITION_OPEN"
      success = True
      return "FORCE_LIQUIDATED_BY_SYSTEM"
    finally:
      flush_controller.resume()
      if success:
        # Y-315: dict value {sealed_at_local_ms, exchange_ts_ms, version}
        local_now_ms = int(time.time() * 1000)
        exchange_ts_ms = fill.exchange_ts_ms if fill else None
        sealed_orders[order_id or symbol] = {
          "sealed_at_local_ms": local_now_ms,
          "exchange_ts_ms": exchange_ts_ms,
          "version": current_position_version,
        }
  task = asyncio.create_task(_emergency())
  emergency_tasks[symbol] = task
  def _cb(t):
    try:
      if t.exception() is not None:
        emit_event(CRITICAL_ALERT, {msg: "EMERGENCY_TASK_EXCEPTION", err: str(t.exception())})
      handle_emergency_result(t)
    except Exception as e:
      emit_event(CRITICAL_ALERT, {msg: "HANDLE_RESULT_EXCEPTION", err: str(e)})
    finally:
      emergency_tasks.pop(symbol, None)
  task.add_done_callback(_cb)
  return await task


# Y-341: emergency state persist
sqlite_emergency_lock = asyncio.Lock()

async def emergency_persist_state(symbol, payload):
  try:
    async with sqlite_emergency_lock:
      await asyncio.wait_for(db.execute_wal(payload), timeout=2.0)
  except asyncio.TimeoutError:
    await write_emergency_journal(symbol, payload)
    emit_event(CRITICAL_ALERT, {msg: "EMERGENCY_JOURNAL_FALLBACK", symbol: symbol})


# Y-323 + Y-271: Decimal quantize
from decimal import Decimal, ROUND_DOWN

def quantize_qty_str(qty):
  d = Decimal(str(qty))
  q = Decimal(f'1e-{qty_decimals}')
  return str(d.quantize(q, rounding=ROUND_DOWN))

def quantize_price(price, precision):
  d = Decimal(str(price))
  q = Decimal(f'1e-{precision}')
  return str(d.quantize(q, rounding=ROUND_DOWN))


# Y-345: emit_event bypass telemetry
def emit_event(event_type, payload):
  """Sync — sadece log. CRITICAL_ALERT ayrıca alerting_agent.send_direct çağırır."""
  if event_type in {CRITICAL_ALERT, FVG_EXPIRED_HARD_DEADLINE}:
    logger.warning(event_type, payload)
  else:
    telemetry_queue.put_nowait((event_type, payload))

async def emit_event_async(event_type, payload):
  """Async — CRITICAL_ALERT alert gönderimi."""
  if event_type in {CRITICAL_ALERT, FVG_EXPIRED_HARD_DEADLINE}:
    logger.warning(event_type, payload)
    await alerting_agent.send_direct(event_type, payload)
  else:
    telemetry_queue.put_nowait((event_type, payload))


# Fix 4.5: order_type mapping
_ORDER_TYPE_MAP = {
  "LIMIT_IOC": {"type": "LIMIT", "timeInForce": "IOC"},
  "MARKET":    {"type": "MARKET"},
}

def map_order_type(order_type):
  if order_type not in _ORDER_TYPE_MAP:
    raise ValueError(f"Unmapped order_type: {order_type}")
  return _ORDER_TYPE_MAP[order_type].copy()

================================================================================
05 — Backtest & Fill Model — REV5
================================================================================
engine: Parquet snappy live1 archive9 archive 365 to_thread .tmp->rename + latency max(0,normal(100,50)) + fee 0.0002 cache fallback 0.0003 taker/maker ayrı + Taker Depth + Partial PARTIAL_CLOSED sealed TTL version optimistic original immutable net fee 1.4999 + buffer Lock single RLock read lock + breach pause float accumulate even invalid cancellable per-symbol safe get discard gap quarantine + trust OI USD 50k band ±0.5% + snappy + zero-disk state_queue + Decimal str(Decimal) + PriorityQueue + store_flush_suspended clear ALWAYS.

fill_model: Taker Depth + Partial PARTIAL_CLOSED sealed TTL version optimistic original immutable net fee 1.4999 taker/maker ayrı min_lot epsilon dust sweep old_trail None + emergency slippage leverage adjusted + per-IP 15 defaultdict pacer PriorityQueue + persistent gateway single + read lock single RLock + archive atomic .tmp->rename + latency max(0) + OI USD 50k + Decimal str(Decimal) + isclose epsilon + PriorityQueue + tasks pop.

filled_by_order = {}
sealed_orders = OrderedDict()
fill_lock = asyncio.Lock()
sealed_lock = asyncio.Lock()

async def on_startup():
  async with fill_lock:
    partials = await db.fetch("SELECT order_id, filled_qty, version FROM orders WHERE status='PARTIAL'")
    for p in partials: filled_by_order[p.order_id] = p.filled_qty

async def on_fill_event(event):
  async with sealed_lock:
    now_ms = int(time.time() * 1000)
    for oid in list(sealed_orders.keys()):
      sealed = sealed_orders[oid]
      # Y-354 break YASAK, Y-336 dict okuma + Y-361 exchange_ts age check
      # OrderedDict insertion != timestamp, full scan zorunlu
      local_expired = now_ms - sealed["sealed_at_local_ms"] > 300_000
      exch_ts = sealed.get("exchange_ts_ms")
      exch_expired = exch_ts is not None and now_ms - exch_ts > 300_000  # Y-361
      if local_expired or exch_expired or exch_ts is None and local_expired:
        sealed_orders.pop(oid)
      # break YOK — Y-354 fix
    if event.order_id in sealed_orders:
      # Y-336: exchange_ts_ms None guard
      exch_ts = sealed_orders[event.order_id].get("exchange_ts_ms")
      if exch_ts is not None and event.ts < exch_ts - 2000:
        return
  flip_detected = False
  async with fill_lock:
    existing = filled_by_order.get(event.order_id, 0)
    if math.isclose(event.fill_qty, 0, abs_tol=1e-9): return
    if existing != 0 and (existing > 0) != (event.fill_qty > 0):
      emit_event(CRITICAL, {FLIP_DETECTED})
      flip_detected = True
    else:
      new_fill = max(existing, event.fill_qty) if existing != 0 else event.fill_qty
      inc = new_fill - existing
      if inc <= 0: return
  if flip_detected:
    await emergency_close(symbol); return
  for retry in range(3):
    async with fill_lock:
      existing = filled_by_order.get(event.order_id, 0)
      new_fill = max(existing, event.fill_qty) if existing != 0 else event.fill_qty
      inc = new_fill - existing
      if inc <= 0: return
      current_version = await db.get_version(event.position_id)
      new_avg = (current_qty * current_avg + inc * event.price) / (current_qty + inc)
      entry_delta = new_avg - original_planned_entry
      new_tp = original_tp + entry_delta
      new_sl_candidate = original_sl + entry_delta
      new_sl = max(current_sl, new_sl_candidate) if LONG else min(current_sl, new_sl_candidate)
      try:
        await db.update_position_versioned(event.position_id, new_avg, new_tp, new_sl, current_version + 1)
        filled_by_order[event.order_id] = new_fill
        break
      except VersionConflict:
        continue

================================================================================
06 — File Registry & Event Catalog & Logging — REV5
================================================================================
File Registry ONE FILE ONE OWNER + lock hierarchy buffer>fill>sqlite>pacer>flush>telemetry (Y-339) sealed_lock ayrı + state_queue DROP_NEVER blocking via AsyncStateQueue

Events: PARTIAL_FILLED idempotency max() sealed TTL version optimistic epsilon dust sweep, ARCHIVER_TASK to_thread .tmp->rename two-phase rotation _closed orphan 5m .deleted 1h lock PID check, WHALE_TRUST_CLEANUP decay band ±0.5% fingerprint tick_size OI USD 50k wash triple OI+CVD+taker ratio, EMERGENCY_SLIPPAGE_RETRY leverage adjusted MAX_RETRY 1 reduce_only true sweep verified qty epsilon dust sweep task done_callback pop, BREACH_PAUSE_RESET new FVG/DROPPED float accumulate even invalid cancellable per-symbol safe get discard gap quarantine next_candle extrapolate max(0), READ_LOCK_COPY single RLock copy-on-read memoryview no leak torn read no await searchsorted bids vs asks ayrı batch vectorized bulk C-slice, PRICE_MONITOR_ON_PAUSE stale only new setup gap quarantine, PARTIAL_FILL_IDEMPOTENCY startup WS paused fill_lock max() sealed TTL version, IP_BAN_DETECTED per-IP 15 per-symbol defaultdict sem_emergency 3 sem_normal 9 acquire 2.0s outer 3.5s [Y-359 kod 1.0+2.0+1.5=4.5s, DURUM eski 5.5s yanlış → 4.5s Y-363] pacer PriorityQueue single-flight global 429 per-symbol separate buckets no bypass gateway single, FORCE_FLUSH_BOUNDED daemon 2 bounded 5 put_nowait DROP zero-disk state_queue separate store_flush_suspended clear ALWAYS telemetry, SWEEP_VOLUME_CONF OI USD 50k, FUNDING_DAILY_LOSS UTC scheduler ayrı task, CORRELATION_DIRECTIONAL window 1h min 30, BE_TRAIL_SHIFT original new_avg monotonic BE never below, DASHBOARD_CACHE cached 1y CDN/npm FATAL, RISK_MATH_VALIDATION TEST 0.036 PROD 0.018, ARCHIVE_ATOMIC to_thread .tmp->rename rotation _closed orphan .deleted lock PID check, HYSTERESIS_MAX_PENDING 10m flap 3 sealed TTL cleanup, SECOND_ENTRY_BYPASS same id, BOUNDED_QUEUE state 200 DROP_NEVER blocking telemetry 1000 DROP_OLDEST put_nowait, BATCH_ALERT 5 emergency, LATENCY_DISTRIBUTION max(0,normal), ADAPTIVE_BUFFER fixed trim 4000 low-water atomic loop C memmove searchsorted bids vs asks ayrı, SSE_REPLAY last_event_id dynamic throttle auth token, WAITING_FOR_FRESH_TICK per-symbol quarantine 60s safe get, STALE_PRICE_AUTO_INVALID 5s only new setup, ORIGINAL_PLANNED_ENTRY immutable version, MONOTONIC_PAUSE float accumulate even invalid, ACQUIRE_TIMEOUT 2.0s outer 3.5s pacer PriorityQueue, SNAPPY_CODEC live1 archive9, FILL_LOCK hierarchy + sealed_lock ayrı, STARTUP_SYNC WS paused, SEARCHSORTED_NEGATIVE bids vs asks ayrı, TORN_READ_FORBIDDEN single RLock no await, BATCH_VECTORIZED_DIFF, BULK_C_SLICE, NUMBA_WARMUP typed array dict_to_array forbidden, CANCELLABLE_SLEEP per-symbol safe get, DISCARD_ON_PAUSE fresh window, GAP_BREACHED_CHECK quarantine, PARTIAL_CLOSED sealed TTL version optimistic, NET_FEE_RR 1.4999 taker/maker ayrı isclose, OLD_TRAIL_NONE_CHECK, MIN_LOT_EPSILON symbol/2 dust sweep, PERSISTENT_SESSION gateway single, DEFAULTDICT cleanup set+clear not del, TO_THREAD_ARCHIVER .tmp->rename, REDUCE_ONLY_TRUE, TRUE_MARKET_SWEEP leverage_adjusted dust sweep, VERIFIED_QTY_EPSILON_TTL 500ms, ZERO_DISK_STATE_QUEUE, PUT_NOWAIT_DROP, TRIM_FARTHEST atomic loop, CLEANUP_TELEMETRY sealed TTL, OI_DELTA_CROSS_CHECK USD 50k, WASH_DETECTION triple band ±0.5% fingerprint tick_size, POSITION_MODE ONE_WAY required, MARGIN_MODE ISOLATED, LEVERAGE_SET, DECIMAL_QUANTIZE str(Decimal) not f-string, SYMBOL_STATUS 5m, RECONCILIATION exchange truth, TOKEN_BUCKET_REAL gateway no bypass, EXPECTED_SEQ epoch reset same lock clear, PING_PONG 15s/5s 3 fail, SEALED_ORDERS TTL 300 dict value version optimistic, EPSILON_SYMBOL dust sweep, FEE_FALLBACK 0.0003 taker/maker ayrı, SLIPPAGE_LEVERAGE_ADJUSTED, STATE_QUEUE_DROP_NEVER blocking, SIGNAL_HANDLER 30s grace tasks pop, HEALTH_PER_COIN %80, SECRET, DNS, TZ UTC, ISCLOSE, NAN_SANITIZE, OI_USD, MIN_LOT_SKIP_LOG, PRIORITY_QUEUE not FIFO, STORE_FLUSH_SUSPENDED clear ALWAYS, TASKS_POP leak fix, ASYNC_STATE_QUEUE mp adapter, PACER_RATE_SHAPING min-spacing, FUNDING_SCHEDULER ayrı task, EMERGENCY_SQLITE_WAL direct, SEM_EMERGENCY_NORMAL ayrı, OBI_AKTIF_LEN, EVENT_BYPASS telemetry, COUNTER_UNDERFLOW WARNING, POP_LOCK_DISI_SLEEP, TRIM_LOG rate-limited, REVISION_NOTICE format

Logging: structured JSON correlation_id UUID4 auth token + non-blocking QueueHandler + disk full 90% oldest archive delete + state_queue DROP_NEVER blocking telemetry DROP_OLDEST + batch alert + snappy + zero-disk state_queue + secret mask + Decimal str(Decimal) + PriorityQueue + clear ALWAYS

================================================================================
07 — Alerting & Monitoring — REV5
================================================================================
alerting/agent.py Telegram/Discord rate limit 30s + batch 5 emergency timeout 5s + non-blocking + priority queue EMERGENCY>ORPHAN + snappy + zero-disk state_queue + auth + secret mask + daily summary WARNING dashboard only + PriorityQueue + tasks pop.

Events->Alert: ARCHIVER_TASK INFO to_thread .tmp->rename rotation orphan .deleted lock PID check, WHALE_TRUST_CLEANUP INFO decay band ±0.5% OI USD 50k wash triple, EMERGENCY_SLIPPAGE_RETRY CRITICAL leverage adjusted MAX_RETRY 1 reduce_only true sweep verified qty epsilon dust sweep task callback pop, BREACH_PAUSE_RESET INFO float accumulate even invalid cancellable per-symbol safe get discard gap quarantine next_candle extrapolate max(0), READ_LOCK_COPY INFO single RLock memoryview no leak torn read no await searchsorted bids vs asks ayrı batch bulk, PRICE_MONITOR_ON_PAUSE INFO stale only new setup gap quarantine, PARTIAL_FILL_IDEMPOTENCY INFO startup WS paused max() sealed TTL version, IP_BAN_DETECTED CRITICAL gateway single separate buckets per-IP 15 defaultdict acquire 2.0s pacer PriorityQueue sem_emergency 3 sem_normal 9 single-flight global 429 per-symbol, FORCE_FLUSH_BOUNDED INFO daemon 2 bounded 5 put_nowait DROP zero-disk state_queue clear ALWAYS, SWEEP_VOLUME_CONF INFO OI USD 50k, RISK_MATH_VALIDATION CRITICAL TEST 0.036 PROD 0.018, ARCHIVE_ATOMIC INFO to_thread .tmp->rename rotation _closed orphan .deleted lock PID check, HYSTERESIS_MAX_PENDING INFO 10m flap 3 sealed TTL cleanup, SECOND_ENTRY_BYPASS INFO, BOUNDED_QUEUE INFO state 200 DROP_NEVER blocking telemetry 1000 DROP_OLDEST, BATCH_ALERT INFO timeout 5s, LATENCY_DISTRIBUTION INFO max(0,normal), ADAPTIVE_BUFFER INFO fixed trim 4000 low-water atomic loop C memmove searchsorted bids vs asks ayrı, SSE_REPLAY INFO auth token dynamic throttle, FUNDING INFO UTC scheduler, CORRELATION_DIR INFO window 1h min 30 hedge, BE_TRAIL INFO monotonic BE never below old_trail None dust sweep, DASHBOARD_CACHE INFO cached 1y CDN/npm FATAL, WAITING_FOR_FRESH_TICK INFO per-symbol quarantine 60s safe get, STALE_AUTO_INVALID INFO only new setup, ORIGINAL_PLANNED_ENTRY INFO immutable version, ACQUIRE_TIMEOUT INFO 2.0s outer 3.5s pacer PriorityQueue, SNAPPY_CODEC INFO live1 archive9, FILL_LOCK INFO hierarchy + sealed_lock ayrı, STARTUP_SYNC INFO WS paused, SEARCHSORTED_NEGATIVE INFO bids vs asks ayrı, TORN_READ_FORBIDDEN INFO single RLock no await, BATCH_DIFF INFO bulk C-slice, NUMBA_WARMUP INFO typed array dict_to_array forbidden, CANCELLABLE_SLEEP INFO per-symbol safe get, DISCARD_ON_PAUSE INFO fresh window, GAP_BREACHED_CHECK INFO quarantine, PARTIAL_CLOSED INFO sealed TTL version optimistic, NET_FEE_RR INFO 1.4999 taker/maker ayrı isclose, OLD_TRAIL_NONE_CHECK INFO, MIN_LOT_EPSILON INFO symbol/2 dust sweep, PERSISTENT_SESSION INFO gateway single, DEFAULTDICT cleanup set+clear INFO, TO_THREAD_ARCHIVER INFO .tmp->rename, REDUCE_ONLY_TRUE INFO, TRUE_MARKET_SWEEP INFO leverage_adjusted dust sweep, VERIFIED_QTY_EPSILON_TTL 500ms INFO, ZERO_DISK_STATE_QUEUE INFO clear ALWAYS, PUT_NOWAIT_DROP INFO, TRIM_FARTHEST INFO atomic loop, CLEANUP_TELEMETRY INFO sealed TTL, OI_DELTA_CROSS_CHECK INFO USD 50k, WASH_DETECTION INFO triple band ±0.5% tick_size, POSITION_MODE INFO ONE_WAY, MARGIN_MODE INFO ISOLATED, LEVERAGE_SET INFO 5, DECIMAL_QUANTIZE INFO str(Decimal) separate string, SYMBOL_STATUS INFO 5m HALTED, RECONCILIATION INFO exchange truth, TOKEN_BUCKET_REAL INFO gateway no bypass, EXPECTED_SEQ INFO epoch reset same lock clear, PING_PONG INFO 15s/5s 3 fail, SEALED_ORDERS INFO TTL 300 dict value version optimistic, EPSILON_SYMBOL INFO dust sweep, FEE_FALLBACK INFO 0.0003 taker/maker ayrı, SLIPPAGE_LEVERAGE_ADJUSTED INFO, STATE_QUEUE_DROP_NEVER INFO blocking, SIGNAL_HANDLER INFO 30s grace tasks pop, HEALTH_PER_COIN INFO %80, SECRET INFO Docker secrets, DNS INFO, TZ UTC INFO, ISCLOSE INFO, NAN_SANITIZE INFO, OI_USD INFO, MIN_LOT_SKIP_LOG INFO, PRIORITY_QUEUE INFO not FIFO, STORE_FLUSH_SUSPENDED INFO clear ALWAYS, TASKS_POP INFO leak fix, ASYNC_STATE_QUEUE INFO, PACER_RATE_SHAPING INFO, FUNDING_SCHEDULER INFO, EMERGENCY_SQLITE_WAL INFO, SEM_EMERGENCY_NORMAL INFO, OBI_AKTIF_LEN INFO, EVENT_BYPASS INFO, COUNTER_UNDERFLOW WARNING, POP_LOCK_DISI_SLEEP INFO, TRIM_LOG INFO rate-limited, REVISION_NOTICE INFO

Health Dashboard: health metrics + archiver_count + trust_cleanup_count + emergency_retry_count + breach_reset_count + read_lock_count + price_monitor_count + idempotency_count + ip_ban_count + force_flush_bounded_count + sweep_volume_count + risk_math_count + archive_atomic_count + hysteresis_max_pending_count + second_bypass_count + bounded_queue_count + batch_alert_count + latency_dist_count + adaptive_buffer_count + sse_replay_count + funding_count + correlation_dir_count + be_trail_count + dashboard_cache_count + waiting_for_fresh_tick_count + stale_auto_invalid_count + original_planned_entry_count + acquire_timeout_count + snappy_count + fill_lock_count + startup_sync_count + searchsorted_negative_count + torn_read_count + batch_diff_count + bulk_slice_count + numba_warmup_count + cancellable_sleep_count + discard_on_pause_count + gap_breached_count + partial_closed_count + net_fee_rr_count + old_trail_none_count + min_lot_epsilon_count + persistent_session_count + defaultdict_count + to_thread_count + reduce_only_count + true_market_sweep_count + verified_qty_count + zero_disk_count + put_nowait_count + trim_count + cleanup_telemetry_count + oi_delta_count + wash_detection_count + position_mode_count + margin_mode_count + leverage_set_count + decimal_quantize_count + symbol_status_count + reconciliation_count + token_bucket_real_count + expected_seq_count + ping_pong_count + sealed_orders_count + epsilon_symbol_count + fee_fallback_count + slippage_leverage_adjusted_count + state_queue_drop_never_count + signal_handler_count + health_per_coin_count + secret_count + dns_count + tz_utc_count + isclose_count + nan_sanitize_count + oi_usd_count + min_lot_skip_log_count + priority_queue_count + store_flush_suspended_count + tasks_pop_count + async_state_queue_count + pacer_rate_shaping_count + funding_scheduler_count + emergency_sqlite_wal_count + sem_emergency_normal_count + obi_aktif_len_count + event_bypass_count + counter_underflow_count + pop_lock_disi_sleep_count + trim_log_count + revision_notice_count

================================================================================
08 — Dashboard Frontend + Process Manager + Test + Deployment — REV5
================================================================================
Dashboard Frontend 4 Panel + widget — inline CSS kritik + Chart.js /static/chart.min.js cached 1y + CDN YASAK npm YASAK package.json YASAK + SSE ONLY auth token dynamic throttle normal 1000 emergency 100 + last_event_id replay 100 + snappy + zero-disk state_queue + put_nowait + persistent gateway single + secret mask + auth + Decimal str(Decimal) + PriorityQueue + clear ALWAYS.

Backend API: universe + hysteresis max pending flap 3 cleanup sealed TTL trim 4000 low-water atomic loop, whale_events + trust OI USD 50k decay band ±0.5% fingerprint tick_size wash triple + cleanup, positions open/closed + partial PARTIAL_CLOSED sealed TTL version optimistic original immutable net fee 1.4999 taker/maker ayrı old_trail None monotonic BE never below min_lot epsilon dust sweep reduce_only verified qty + idempotency max() flip assert startup WS paused + BE Trail original + risk math TEST/PROD fixed + trust OI USD 50k + Decimal str(Decimal) + position_mode margin_mode leverage set + symbol STATUS + reconciliation, metrics + latency max(0,normal) fee 0.0002 fallback 0.0003 taker/maker ayrı funding UTC scheduler + risk math net fee 1.4999 + Decimal str(Decimal), health + read lock single RLock torn read no await searchsorted bids vs asks ayrı batch bulk + price monitor gap quarantine stale only new setup + ip ban gateway single global 429 per-symbol reset half-open pacer PriorityQueue sem_emergency single-flight + force flush bounded zero-disk state_queue clear ALWAYS + archiver to_thread .tmp->rename rotation orphan .deleted lock PID check + trust cleanup decay band ±0.5% wash triple + emergency retry leverage adjusted reduce_only true sweep verified qty epsilon dust sweep task callback pop + breach reset float accumulate even invalid cancellable per-symbol safe get discard gap quarantine hard deadline next_candle extrapolate max(0) + etc, replay + archiver atomic idempotency max() sealed TTL version + sealed_orders + Decimal str(Decimal), storage + archiver to_thread .tmp->rename rotation _closed orphan .deleted force flush bounded zero-disk state_queue clear ALWAYS read lock single RLock snappy live1 archive9 batch vectorized bulk C-slice pre_sync_queue expected_seq epoch clear ping pong + sealed TTL version optimistic, hysteresis max pending, depth_model C memmove searchsorted bids vs asks ayrı torn read YASAK no await, post_market_rest gateway PriorityQueue, ipc_numba warmup typed array dict_to_array forbidden, partial_fill PARTIAL_CLOSED sealed TTL version optimistic original immutable net fee 1.4999 taker/maker ayrı old_trail None monotonic BE never below min_lot epsilon dust sweep, buffer_overflow fixed trim 4000 low-water atomic loop C memmove searchsorted bids vs asks ayrı, ghost_reset breach pause float accumulate even invalid cancellable per-symbol safe get discard gap quarantine stale only new setup, bypass gateway single per-IP 15 defaultdict pacer PriorityQueue sem_emergency 3 single-flight global 429 per-symbol no bypass FATAL, lag_correction price monitor gap quarantine, force_flush bounded zero-disk state_queue clear ALWAYS, zero_dep cached, ms_suffix whitelist all _ms int minutes YASAK, timer_loop cancellable per-symbol Event safe get discard gap quarantine hard deadline stale only new setup read lock float accumulate even invalid next_candle extrapolate max(0), ddl qty fix PARTIAL_CLOSED sealed TTL version optimistic original immutable tp_fixed DELETE remaining_qty DELETE sealed_at_ms net fee 1.4999 taker/maker ayrı old_trail None monotonic BE never below min_lot epsilon dust sweep reduce_only verified qty epsilon, tp_shift sl_shift be_trail original version net fee 1.4999 monotonic, breach_pause float accumulate even invalid cancellable per-symbol safe get discard gap quarantine next_candle extrapolate max(0), retention moves_to_archive atomic to_thread .tmp->rename rotation, emergency_slippage leverage adjusted MAX_RETRY 1 reduce_only true sweep verified qty epsilon dust sweep task callback pop signal handler clear ALWAYS + tasks pop, trust_score OI USD 50k decay band ±0.5% fingerprint tick_size wash triple cleanup, archiver move to_thread .tmp->rename rotation _closed orphan .deleted lock PID check, whale_trust_cleanup decay band ±0.5% wash triple, emergency_retry leverage adjusted reduce_only true sweep verified qty epsilon dust sweep, breach_pause_reset float accumulate even invalid cancellable per-symbol safe get discard gap quarantine next_candle extrapolate max(0), read_lock_copy single RLock memoryview no leak torn read no await searchsorted bids vs asks ayrı batch bulk, price_monitor_pause stale only new setup gap quarantine, idempotency startup WS paused max() sealed TTL version optimistic -2s window, ip_ban gateway single global 429 per-symbol reset half-open pacer PriorityQueue, force_flush_bounded zero-disk state_queue clear ALWAYS, sweep_volume OI USD 50k, risk_math TEST 0.036 PROD 0.018 net fee 1.4999 taker/maker ayrı, archive_atomic to_thread .tmp->rename rotation _closed orphan .deleted lock PID check, hysteresis_max_pending sealed TTL cleanup, second_bypass, bounded_queue state DROP_NEVER blocking telemetry DROP_OLDEST put_nowait, batch_alert timeout 5s, latency_dist max(0,normal), adaptive_buffer fixed trim 4000 low-water atomic loop C memmove searchsorted bids vs asks ayrı, sse_replay auth token dynamic throttle, funding UTC scheduler, correlation_dir window 1h min 30 hedge, be_trail original monotonic BE never below old_trail None dust sweep, dashboard_cache cached 1y CDN/npm FATAL, original immutable version, monotonic pause float accumulate even invalid, acquire timeout 2.0s outer 3.5s pacer PriorityQueue, snappy live1 archive9 gzip YASAK, fill_lock hierarchy + sealed_lock ayrı, startup sync WS paused, waiting_for_fresh_tick per-symbol quarantine 60s safe get, stale auto invalid 5s only new setup discard, PARTIAL_CLOSED sealed TTL version optimistic -2s window, net fee 1.4999 taker/maker ayrı isclose, old_trail None monotonic, min_lot epsilon symbol/2 dust sweep, persistent gateway single, defaultdict cleanup set+clear not del, to_thread archiver .tmp->rename rotation _closed orphan .deleted, reduce_only true sweep leverage_adjusted dust sweep verified qty epsilon, zero-disk state_queue clear ALWAYS, put_nowait, trim farthest atomic loop, cleanup telemetry sealed TTL, OI delta cross USD 50k wash triple decay band ±0.5% fingerprint tick_size, numba warmup typed array dict_to_array forbidden, cancellable per-symbol safe get, discard gap quarantine.

SSE /api/v2/sse canlı stream auth token throttle dynamic normal 1000 emergency 100 + last_event_id replay 100 + widget.

Frontend 4 Panel: 1 Kasa Risk balance daily UTC weekly MONDAY open 1/2 circuit REST_BLINDNESS POST_MARKET buffer overflow fixed trim 4000 low-water atomic loop C memmove searchsorted bids vs asks ayrı torn read YASAK no await ghost reset breach pause float accumulate even invalid cancellable per-symbol safe get discard gap quarantine stale only new setup trust OI USD 50k decay band ±0.5% wash triple cleanup emergency retry leverage adjusted ip ban gateway single global 429 per-symbol reset half-open pacer PriorityQueue sem_emergency single-flight force flush zero-disk state_queue clear ALWAYS archiver move to_thread .tmp->rename rotation _closed orphan .deleted lock PID check risk math TEST/PROD fixed net fee 1.4999 taker/maker ayrı isclose zero-disk state_queue Decimal str(Decimal) position_mode margin_mode leverage set symbol STATUS reconciliation PriorityQueue tasks pop, 2 Pozisyonlar open second_entry OI USD trust>=2 decay band ±0.5% sl_distance depth bar guard_check post_market_rest partial PARTIAL_CLOSED sealed TTL version optimistic -2s window original immutable net fee 1.4999 taker/maker ayrı old_trail None monotonic BE never below min_lot epsilon dust sweep reduce_only verified qty + weighted avg max() flip assert idempotency startup WS paused + BE Trail original monotonic + rr_min net fee 1.4999 ddl version sealed + Decimal str(Decimal), 3 Balina Likidite whale son 50 REAL/SPOOFED/ABSORPTION OI USD 50k Universe Top5 hysteresis IN_TOP5 yeşil IN_TOP10 sarı OUTSIDE_PENDING turuncu max pending 10m flap 3 timer DROPPED kırmızı ghost reset breach pause float accumulate even invalid cancellable per-symbol safe get discard gap quarantine stale only new setup waiting_for_fresh_tick per-symbol gap quarantine safe get trust OI USD 50k decay band ±0.5% fingerprint tick_size wash triple sweep volume decay, 4 Health Metrics Chart.js cached equity drawdown health ws_valid is_valid lag_ms depth_available emergency post_market_rest hysteresis drop_timer_ms max_pending_ms flap_count ipc bottleneck numba warmup typed array fvg_method slippage leverage_adjusted buffer_type adaptive fixed trim 4000 low-water atomic loop buffer_size resize_count ghost_reset_count bypass gateway single per-IP per-symbol lag_ms force_flush bounded zero-disk state_queue clear ALWAYS put_nowait partial_fill_count tp_shift_count breach_pause_count retention_archive_count emergency_slippage_count trust_score_count whitelist_count partial_fill_ddl_count ms_suffix_validation_count timer_loop_count zero_dep_validation archiver_count trust_cleanup_count emergency_retry_count breach_reset_count read_lock_count price_monitor_count idempotency_count ip_ban_count force_flush_bounded_count sweep_volume_count risk_math_count archive_atomic_count hysteresis_max_pending_count second_bypass_count bounded_queue_count batch_alert_count latency_dist_count adaptive_buffer_count sse_replay_count funding_count correlation_dir_count be_trail_count dashboard_cache_count waiting_for_fresh_tick_count stale_auto_invalid_count original_planned_entry_count acquire_timeout_count snappy_count fill_lock_count startup_sync_count searchsorted_negative_count torn_read_count batch_diff_count bulk_slice_count numba_warmup_count cancellable_sleep_count discard_on_pause_count gap_breached_count partial_closed_count net_fee_rr_count old_trail_none_count min_lot_epsilon_count persistent_session_count defaultdict_count to_thread_count reduce_only_count true_market_sweep_count verified_qty_count zero_disk_count put_nowait_count trim_count cleanup_telemetry_count oi_delta_count wash_detection_count position_mode_count margin_mode_count leverage_set_count decimal_quantize_count symbol_status_count reconciliation_count token_bucket_real_count expected_seq_count ping_pong_count sealed_orders_count epsilon_symbol_count fee_fallback_count slippage_leverage_adjusted_count state_queue_drop_never_count signal_handler_count health_per_coin_count secret_count dns_count tz_utc_count isclose_count nan_sanitize_count oi_usd_count min_lot_skip_log_count priority_queue_count store_flush_suspended_count tasks_pop_count async_state_queue_count pacer_rate_shaping_count funding_scheduler_count emergency_sqlite_wal_count sem_emergency_normal_count obi_aktif_len_count event_bypass_count counter_underflow_count pop_lock_disi_sleep_count trim_log_count revision_notice_count

Process Manager: config validation position_mode margin_mode leverage set required FATAL parse FATAL all _ms int minutes YASAK risk math fixed TEST 0.036 PROD 0.018 + supervisor TaskGroup + funding_scheduler ayrı task (Y-331) + backoff [5000,10000,30000,60000] + adaptive fixed trim 4000 low-water atomic loop C memmove searchsorted bids vs asks ayrı + bounded queue state DROP_NEVER blocking telemetry DROP_OLDEST put_nowait zero-disk state_queue clear ALWAYS + batch alert timeout 5s + latency max(0,normal) + SSE replay auth token + hysteresis max pending sealed TTL + second bypass + funding UTC scheduler all UTC monotonic next_candle extrapolate max(0) + correlation window 1h min 30 + BE Trail original monotonic BE never below + net fee 1.4999 taker/maker ayrı isclose + old_trail None + min_lot epsilon dust sweep + reduce_only + true sweep leverage adjusted dust sweep + verified qty epsilon + cached chart + risk math + archive atomic .tmp->rename rotation _closed orphan .deleted lock PID check + read lock single RLock torn read no await + per-IP 15 defaultdict pacer PriorityQueue sem_emergency 3 sem_normal 9 single-flight global 429 per-symbol no bypass gateway single + trust OI USD 50k decay band ±0.5% fingerprint tick_size wash triple + archiver move to_thread .tmp->rename rotation + non-blocking logging + disk full oldest delete + snappy live1 archive9 + zero-disk state_queue clear ALWAYS put_nowait + pre_sync_queue expected_seq epoch clear ping pong + cancellable per-symbol safe get discard gap quarantine + PARTIAL_CLOSED sealed TTL version optimistic -2s window + net fee 1.4999 taker/maker ayrı + min_lot epsilon dust sweep + old_trail None monotonic + persistent gateway single + defaultdict cleanup set+clear not del + to_thread .tmp->rename + reduce_only true sweep leverage_adjusted dust sweep + verified qty epsilon dust sweep + zero-disk state_queue clear ALWAYS + put_nowait + trim atomic loop + cleanup sealed TTL + OI USD 50k + numba warmup typed array dict_to_array forbidden + cancellable per-symbol safe get + discard gap quarantine + reconciliation exchange truth + startup WS paused + fill_lock hierarchy sealed_lock ayrı + signal handler 30s grace tasks pop + health per-coin + secret + DNS + TZ UTC + isclose + NaN + Decimal str(Decimal) + PriorityQueue + store_flush_suspended clear ALWAYS + tasks pop + async_state_queue + pacer_rate_shaping + funding_scheduler + emergency_sqlite_wal + sem_emergency_normal + obi_aktif_len + event_bypass + counter_underflow + pop_lock_disi_sleep + trim_log + revision_notice.

Tests: pytest -k yama251-349
  - Buffer overflow batch loop while len+batch>=5000
  - searchsorted bids vs asks ayrı
  - single RLock torn read
  - expected_seq epoch same lock clear seq<=snapshot
  - fresh_tick_event defaultdict safe get not KeyError
  - paused_ms accumulate even invalid hard deadline
  - next_candle extrapolate max(0)+5000 not negative
  - fee taker/maker ayrı R:R
  - sealed TTL -2s window version optimistic dict value
  - epsilon dust sweep true_market_sweep
  - TokenBucket SINGLE GLOBAL rate 8 burst 15
  - PriorityQueue not FIFO starve
  - global 429 per-symbol half-open 60s emergency block
  - store_flush_suspended clear ALWAYS
  - tasks pop leak
  - whale band ±0.5% fingerprint tick_size bypass
  - OI 50k wash triple
  - _ms whitelist minutes YASAK sleep_ms/1000
  - dashboard npm CDN FATAL
  - Decimal str(Decimal) ROUND_DOWN
  - Numba typed array dict_to_array forbidden
  - lock hierarchy buffer>fill>sqlite>pacer>flush>telemetry CI assert
  - sealed_orders dict okuma None guard
  - emergency_close RuntimeError catch fallback
  - Pacer rate-shaping per-prio min-spacing
  - AsyncStateQueue semaphore(8) to_thread drain
  - emergency SQLite WAL direct 2s timeout fallback
  - sem_emergency 3 + sem_normal 9 ayrı havuz
  - OBI aktif len fixed 5000 YASAK
  - CRITICAL_ALERT emit_event bypass telemetry
  - FlushController counter underflow WARNING
  - Pacer.pop lock dışı sleep(0)
  - trim WARNING rate-limited
  - REVISION NOTICE format SUPERSEDED BY AUTHORITATIVE
  - _map_order_type LIMIT_IOC -> {LIMIT IOC}

Deployment Dockerfile python 3.11-slim ENV TZ=UTC requirements COPY src + static/chart.min.js CMD python main.py docker-compose volumes ./data:/app/data ./data/archive:/app/data/historical_l2_archive ./logs:/app/logs env MIKO_ENV=TEST|PROD required FATAL TELEGRAM_BOT_TOKEN secret DISCORD_WEBHOOK secret restart on-failure:5 backoff_delay healthcheck per-coin %80 503 stop_grace_period 35s.

================================================================================
YAMA 341-349 (REV5 Pass 3 genişletilmiş fix'ler)
================================================================================
341: Emergency state persist = SQLite WAL direct 2s timeout + fallback journal; state_queue bypass
342: sem_emergency 3 + sem_normal 9 ayrı havuz; is_emergency ≠ priority=CRITICAL
343: Pacer CRITICAL min-spacing nominal 2ms max 5ms; emergency tolere (Y-330 ile uyumlu, Foundation 2/20/50 nominal)
344: OBI = aktif len; fixed 5000 varsayımı YASAK; get_obi() merkezi
345: CRITICAL_ALERT + FVG_EXPIRED_HARD_DEADLINE bypass telemetry_queue; emit_event sync log + emit_event_async alert
346: FlushController counter underflow WARNING zorunlu
347: Pacer.pop lock altında heappop/heappush, lock dışı sleep(0); recursion YASAK
348: trim WARNING rate-limited (her 100 trim'de 1); log flooding YASAK
349: REVISION NOTICE format zorunlu; her SUPERSEDED YAMA AUTHORITATIVE belirtmeli

================================================================================
YAMA 336-340 (Pass 2 fix'ler)
================================================================================
336: sealed_orders dict okuma — sealed["exchange_ts_ms"] None guard
337: state_queue ayrı executor YASAK, semaphore(8) + to_thread + drain()
338: _direct_market_post token bucket kullanır, sadece pacer bypass; None dönüş + CRITICAL_ALERT
339: Lock hierarchy buffer>fill>sqlite>pacer>flush>telemetry; leaf: token_bucket, _state_sem, _seq_lock
340: Snapshot gecikme → batch drop + metric; replay YASAK

================================================================================
TOPLAM YAMA REV5
================================================================================
251-273: 23 loop red team
274-276: 3 Claude
277-302: 26 numerical
303-312: 10 distinct
313-316: 4 fix-üstü-fix
317a-323: 7 side-effect-safe fix
325-328: 4 yeni fix
329-340: 12 Pass fix
341-349: 9 Pass 3 genişletilmiş fix
Toplam: 98 YAMA

REV5 Pass kapanış özeti:
- Pass 1 DISTINCT: 100 FAIL → 93 text + 7 yapısal fix
- Pass 2 CONFLICT: 77 conflict → 11 fix + 4 YAMA (332-335)
- Pass 3 SIDE_EFFECT+NECESSITY+LOOP: 31 SE + 12 RD + 2 HR + 5 MISMATCH → 5 fix + 9 YAMA (341-349)
- Toplam 227 bulgu kapatıldı

# END — REV5 — 116 YAMA

---
## UNFROZEN BEYANI
- FROZEN YOK — REV5 116 YAMA
- Her satır sorgulanabilir, blind kabul YASAK
- Yeni YAMA 350+ açık (mevcut satırlar stabil)
- ROLLBACK adayları dahil her satır KEEP/FIX/MERGE/REVISE/ROLLBACK alabilir
- Pass 1/2/3 toplam 227 bulgu kapatıldı

--- YAMA 362-368 REV5 — FAZ 0 kapanış (detaylı) ---

Y-362: FlushController resume() underflow gizleme + truthy bug
  BEFORE L326-L330:
    self._counter = max(0, self._counter -1)
    if self._counter  # truthy bug
  AFTER REV5:
    def resume(self):
        with self._lock:
            self._counter -= 1  # Y-356 tek sayaç
            if self._counter < 0:  # Y-362
                logger.warning("FLUSH_COUNTER_UNDERFLOW", current=self._counter)  # Y-346
                self._counter = 0  # Y-362 clamp
            if self._counter == 0:
                try: asyncio.get_event_loop().call_soon_threadsafe(self._async_event.set)
                except Exception: self._async_event.set()
  Kanıt: L326-L330 max(0) gizleme kaldırıldı, truthy düzeltildi, WARNING eklendi, clamp eklendi
  Uyum: Y-346 WARNING zorunlu, Y-356 tek sayaç, Y-368 assert kaldır

Y-363: DURUM sayı düzeltme Y-359
  Kod: L266 timeout=1.0 + L268 timeout=2.0 + L270 timeout=1.5 =4.5s
  DURUM eski: 5.5s (main 2.0s pool 1.0s varsaymış)
  Doğru: 4.5s
  Hedef: FAZ2'de single outer wait_for 3.5s, iç wait_forlar kaldırılacak

Y-364: Dokümantasyon tutarsızlık düzeltme
  Eski: 8 CONFLICT +1 PARTIAL vs 7+2 vs Tablo 8
  Doğru: 7 CONFLICT (350,351,352,353,357,358,359) +1 PARTIAL (356→362/368) +4 OK (354,355,360,361) =12
  Y-367 ile cümle düzeltildi

Y-365: Y-354 redundant note
  L652: if local_expired or exch_expired or exch_ts is None and local_expired:
  Analiz: or öncesi 2 terim, 3. terim (exch_ts is None and local_expired) redundant absorption ile zaten kapsanıyor, çalışır ama redundant
  Karar: KEEP + note, logic doğru

Y-367: Yanıltıcı cümle fix
  Eski: "12 runtime fix side-effect-safe onaylandı"
  Yeni: "12 fix tasarım onaylı DURUM'da side-effect-safe, TumModuller'de koda uygulanmış 4 adet (354,355,360,361) +1 kısmi (356→362/368), kalan 7'si FAZ2-4'te uygulanacak"
  Gerekçe: 12'si de koda girmiş gibi anlaşılıyordu, gerçek 4+1

Y-368: Y-356 REVISE — assert kaldır
  BEFORE Y-356: tek sayaç + assert self._counter>=0
  PROBLEM: prod'da crash FATAL, Y-346 WARNING zorunlu ile çelişir
  AFTER Y-368: prod'da WARNING+clamp 0, assert sadece test/CI'da
  Kod yukarıdaki Y-362 ile aynı
  Yeni DoD: Y-356 prod assert YASAK

--- REV5 src/ 38 dosya tam ağaç (gizleme YASAK, FAZ0-SRC-STRUCTURE) ---
src/__init__.py
src/main.py
src/supervisor.py
src/config/__init__.py
src/config/settings.py
src/config/validation.py
src/config/di.py  # Y-353 DI zorunlu, global YASAK
src/config/secrets.py
src/data_layer/__init__.py
src/data_layer/l2_buffer.py  # Y-317a, Y-332 tek sayaç, Y-348 rate-limited, Y-360 searchsorted
src/data_layer/obi.py  # Y-344 aktif len
src/data_layer/token_bucket.py  # Y-275 GLOBAL SINGLE 8/15, Y-304 distinct prio
src/data_layer/queues/__init__.py
src/data_layer/queues/async_state_queue.py  # Y-329 bridge 200 + Y-357 to_thread Sem8
src/data_layer/queues/async_telemetry_queue.py  # Y-276 DROP_OLDEST 1000
src/data_layer/seq.py
src/ws_manager/__init__.py
src/ws_manager/manager.py  # Y-305 epoch+seq
src/ws_manager/snapshot.py
src/ws_manager/funding_scheduler.py
src/execution/__init__.py
src/execution/pacer.py  # Y-330, Y-343, Y-355 asimetri KEEP, Y-358 asyncio.Lock
src/execution/rest_gateway.py  # Y-342 sem ayrı, Y-275 single bucket
src/execution/order_manager.py
src/execution/flush_controller.py  # Y-356/Y-362/Y-368 fixed resume()
src/storage/__init__.py
src/storage/sqlite_writer.py  # Y-341 WAL 2s fallback
src/storage/orderbook_store.py
src/storage/archiver.py
src/storage/sealed.py  # Y-354/Y-365 full scan OK, Y-336 None guard, Y-361 age check
src/emergency/__init__.py
src/emergency/close.py  # Y-260 slippage min(3%,10%/lev), Y-350 call_soon_threadsafe
src/emergency/persist.py  # Y-351 pre-insert Future
src/emergency/journal.py
src/risk/__init__.py
src/risk/portfolio_risk.py
src/risk/whale_radar.py
src/risk/funding.py
src/utils/__init__.py
src/utils/decimal.py
src/utils/time.py
src/utils/locks.py  # Y-358 threading.Lock YASAK asyncio.Lock
src/utils/events.py
src/utils/logging.py
src/dashboard/__init__.py
src/dashboard/app.py
src/dashboard/routes.py
src/dashboard/static/chart.min.js
src/backtest/__init__.py
src/backtest/fill_model.py
tests/unit/test_yama_251_273.py ... test_yama_361.py
tests/unit/test_yama_362_368.py  # YENİ REV5
tests/integration/test_lock_hierarchy.py
tests/integration/test_ws_seq_epoch.py
tests/integration/test_snapshot_gap.py
tests/chaos/test_queue_full.py
tests/chaos/test_429_storm.py
tests/chaos/test_deadlock.py

--- REV5 DoD FAZ 0 KAPANDI ---
- 116 YAMA, 366 açılmadı, 362-368 eklendi
- Y-356 REVISE Y-368 WARNING+clamp
- Y-359 4.5s Y-363
- Y-355 asimetri KEEP
- Y-354 redundant KEEP Y-365
- 7+1+4=12 Y-364
- 12 tasarım onaylı 4+1 kodda 7 FAZ2-4 Y-367
- 38 dosya tam ağaç
- FAZ 0 KAPANDI 2026-09-12
