# MikoV2 ROADMAP — REV5 (FAZ 0 kapandı)

## Faz Haritası (10 faz)

FAZ 0 — BOOTSTRAP & AUDIT ✅ KAPANDI (116 YAMA, 245 bulgu)
FAZ 1 — SKELETON & DI
FAZ 2 — CORE DATA LAYER & WS MANAGER
FAZ 3 — QUEUE, RATE LIMIT & PACER
FAZ 4 — EXECUTION, EMERGENCY, STORAGE & RISK
FAZ 5 — UNIT TESTS (116 YAMA)
FAZ 6 — INTEGRATION & LOCK HIERARCHY
FAZ 7 — MONKEY / FUZZ / CHAOS
FAZ 8 — SHADOW TEST
FAZ 9 — DASHBOARD, SUPERVISOR & MAIN

## Modül → Faz Eşlemesi (38 dosya)

### FAZ 1 (12)
- src/__init__.py
- src/config/__init__.py
- src/config/settings.py       # Y-269 _ms whitelist, FATAL check
- src/config/validation.py     # Y-353 DI validation
- src/config/di.py             # Y-353 Dependencies dataclass
- src/config/secrets.py        # Docker secrets, mask
- src/utils/__init__.py
- src/utils/decimal.py         # Y-323, Y-271 str(Decimal) ROUND_DOWN
- src/utils/time.py            # Y-257, Y-281 next_candle max(0)+5000
- src/utils/locks.py           # Y-358 asyncio.Lock, Y-339 6-seviye hierarchy
- src/utils/events.py          # Y-345 CRITICAL_ALERT bypass telemetry
- src/utils/logging.py         # Y-348 rate-limited trim WARNING

### FAZ 2 (9)
- src/data_layer/__init__.py
- src/data_layer/seq.py
- src/data_layer/l2_buffer.py       # Y-332, Y-317a, Y-348, Y-360
- src/data_layer/obi.py             # Y-344 aktif len
- src/data_layer/token_bucket.py    # Y-275 SINGLE GLOBAL 8/15
- src/ws_manager/__init__.py
- src/ws_manager/manager.py         # Y-305 epoch+seq, Y-352 append
- src/ws_manager/snapshot.py
- src/ws_manager/funding_scheduler.py  # Y-331

### FAZ 3 (6)
- src/data_layer/queues/__init__.py
- src/data_layer/queues/async_state_queue.py      # Y-357 bridge
- src/data_layer/queues/async_telemetry_queue.py  # Y-276 DROP_OLDEST
- src/execution/__init__.py
- src/execution/pacer.py                          # Y-330, Y-343, Y-355, Y-358
- src/execution/rest_gateway.py                   # Y-359 outer 3.5s

### FAZ 4 (14)
- src/storage/__init__.py
- src/storage/sqlite_writer.py       # Y-341 WAL 2s fallback
- src/storage/orderbook_store.py
- src/storage/sealed.py              # Y-354, Y-336, Y-361
- src/storage/archiver.py
- src/execution/order_manager.py
- src/execution/flush_controller.py  # Y-356, Y-362, Y-368
- src/emergency/__init__.py
- src/emergency/close.py             # Y-260, Y-350
- src/emergency/persist.py           # Y-351 Future pre-insert
- src/emergency/journal.py
- src/risk/__init__.py
- src/risk/portfolio_risk.py
- src/risk/whale_radar.py
- src/risk/funding.py

### FAZ 5-8
- tests/unit/, tests/integration/, tests/chaos/, tests/shadow/

### FAZ 9
- src/dashboard/__init__.py, app.py, routes.py, static/chart.min.js
- src/backtest/__init__.py, fill_model.py
- src/supervisor.py
- src/main.py

## Process Model

**REST Gateway (1)** — execution/*, emergency/*, storage/*, risk/portfolio_risk.py, risk/funding.py, config/*, utils/*

**WS Process (3 × max 10 coin)** — data_layer/*, ws_manager/*, risk/whale_radar.py

**Supervisor (1)** — supervisor.py, main.py, dashboard/*, alerting/agent.py

**IPC** — WS→REST: mp.Queue DROP_NEVER 200 | REST→WS: mp.Queue DROP_OLDEST 1000

## Kritik Kural

- Global state YASAK (Y-353) — Dependencies dataclass ile DI
- Monolit YASAK — 38 dosya, tek sorumluluk
- Kilit sırası: BUFFER(1) > FILL(2) > SQLITE(3) > PACER(4) > FLUSH(5) > TELEMETRY(6)