# tests/shadow/runner.py
"""
MEXC Futures shadow runner (manual, live network).

Usage:
    python -m tests.shadow.runner --symbol BTC_USDT --duration 600 --db data/mikov2.sqlite

Bootstrap order:
  1. WS connect, subscribe depth + deal
  2. Wait for first depth push (up to 3s)
  3. Fetch REST snapshot
  4. Discard buffered pushes with version <= snapshot.version
  5. Apply remaining buffered in strict +1 order
  6. If still behind, use depth_commits bridge
  7. Live: depth -> L2Buffer -> 60s SQLite flush
           deal  -> 1s OHLCV USDT-normalized bucket -> SQLite flush
           ticker poll (60s) -> OI + mark + funding -> tickers_snapshot
  8. B3.2: MicroTrigger live evaluation (5s) + Strategy shadow
  9. B3.3: PaperPositionManager live paper trading

B3.3 integration points:
  - __init__: self._paper placeholder
  - _setup_db: PaperPositionManager init + setup_db()
  - _apply_push: on_ws_tick(mid)  [B3.3-B.3 freshness]
  - _on_ohlcv_1s: on_ohlcv(OhlcvSample)
  - _insert_ticker_snapshot: on_ticker(funding)
  - _micro_trigger_loop: current_position_qty (A.3) + on_entry
    on TRIGGER (B3.2-A preserves MicroTrigger as sole live
    decision-maker)
  - run(): on_startup (D.6) + finalize (N4: END_OF_BACKTEST)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import signal
import sqlite3
import time
from collections import deque
from pathlib import Path

import aiohttp

from src.data_layer.l2_buffer import L2Buffer
from src.data_layer.mexc_rest import MEXCRestClient
from src.data_layer.mexc_ws import MEXCWSClient
from src.data_layer.seq import SeqMode, SequenceValidator
from src.data_layer.obi import OBIComputer
from src.data_layer.constants import EXCLUDED_SYMBOLS
from src.data_layer.metrics_fetcher import FetcherConfig
from src.data_layer.universe_service import (
    UniverseService,
    RotationDecision,
    ScanResult,
)
from src.features.micro_trigger import (
    MicroTrigger,
    MicroTriggerConfig,
    MicroTriggerState,
)
from src.backtest.signal_detector import (
    SignalDetector,
    DetectorConfig,
    SignalKind,
    Signal,
)
from src.backtest.strategy import (
    Strategy,
    StrategyConfig,
    EntrySignal,
    Direction,
)
from src.backtest.replay_transport import OHLCVEvent, TickerEvent
from src.execution.paper_position_manager import (
    OhlcvSample,
    PaperPositionConfig,
    PaperPositionManager,
)
from src.alerting import run_migration as run_alert_migration
from src.alerting.agent import (
    AlertAgent,
    AlertConfig,
    config_from_env,
)
from src.observation import migrate_observation
from src.observation.state import (
    poll_stop_flag,
    load_state as load_observation_state,
    update_state as update_observation_state,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("shadow")


class ShadowMetrics:
    def __init__(self) -> None:
        self.buffered_pushes = 0
        self.pushes = 0
        self.gaps = 0
        self.resyncs = 0
        self.stale_drops = 0
        self.valid = 0
        self.obi_samples: list[float] = []
        self.max_bids_len = 0
        self.max_asks_len = 0
        self.trades_in = 0
        self.trades_dropped = 0
        self.trades_unknown_side = 0
        self.trades_late = 0
        self.ohlcv_flushed = 0
        self.tickers_polled = 0
        self.tickers_failed = 0
        self.contract_size = 0.0
        self.start_mono = time.monotonic()

    def uptime_s(self) -> float:
        return time.monotonic() - self.start_mono

    def to_dict(self, symbol: str) -> dict:
        obi_avg = (
            sum(self.obi_samples) / len(self.obi_samples)
            if self.obi_samples
            else 0.0
        )
        return {
            "symbol": symbol,
            "uptime_s": round(self.uptime_s(), 2),
            "pushes": self.pushes,
            "valid": self.valid,
            "gaps": self.gaps,
            "resyncs": self.resyncs,
            "stale_drops": self.stale_drops,
            "obi_samples": len(self.obi_samples),
            "obi_avg": round(obi_avg, 6),
            "max_bids_len": self.max_bids_len,
            "max_asks_len": self.max_asks_len,
            "buffered_pushes": self.buffered_pushes,
            "trades_in": self.trades_in,
            "trades_dropped": self.trades_dropped,
            "trades_unknown_side": self.trades_unknown_side,
            "trades_late": self.trades_late,
            "ohlcv_flushed": self.ohlcv_flushed,
            "tickers_polled": self.tickers_polled,
            "tickers_failed": self.tickers_failed,
            "contract_size": self.contract_size,
        }


class ShadowRunner:
    TICKERS_INTERVAL_S = 60.0

    def __init__(
        self,
        symbols: list[str],
        duration_s: int,
        db_path: Path | None = None,
        enable_rotation: bool = False,
        scan_interval_s: float = 30.0,
        rotation_interval_s: float = 300.0,
    ) -> None:
        self.db_path = db_path
        self._conn: sqlite3.Connection | None = None
        self.symbols: set[str] = set(symbols)
        self.duration_s = duration_s
        self.metrics = ShadowMetrics()

        self.books: dict = {}
        self.l2_buffer = L2Buffer(self.books)
        self.seq_validator = SequenceValidator({}, {}, mode=SeqMode.MEXC)
        self.obi = OBIComputer(depth=10)

        # B3.1: per-symbol state
        self.current_epoch: dict[str, int] = {s: 1 for s in self.symbols}
        self.synced: dict[str, bool] = {s: False for s in self.symbols}
        self.snapshot_version: dict[str, int] = {s: 0 for s in self.symbols}
        self.last_applied_version: dict[str, int] = {s: 0 for s in self.symbols}
        self.pending: dict[str, list[dict]] = {s: [] for s in self.symbols}

        self._ohlcv_buffer: dict[str, dict] = {}
        self._contract_size: dict[str, float] = {}
        self._shutdown_event = asyncio.Event()

        # B3.1 rotation (SORU B=D: iki timer)
        self._enable_rotation = enable_rotation
        self._scan_interval_s = scan_interval_s
        self._rotation_interval_s = rotation_interval_s
        self.universe: UniverseService | None = None
        self._latest_scan: ScanResult | None = None
        self._watch_symbols: set[str] = set()
        self._last_ws_data_mono: dict[str, float] = {}

        self.rest: MEXCRestClient | None = None
        self.ws: MEXCWSClient | None = None

        # B3.3: Paper position manager; _setup_db sonrası initialize edilir
        # (conn bağımlı). Bu satır None; _setup_db içinde set edilir.
        self._paper: PaperPositionManager | None = None

        # B3.4: Alert agent; config _setup_db'de valide edilir; agent
        # run() içinde session açıldıktan sonra init + start edilir.
        self._alert_agent: AlertAgent | None = None
        self._alert_config: AlertConfig | None = None

        # B3.2: MicroTrigger + Strategy shadow
        self._mt_config = MicroTriggerConfig()
        self._strategy_config = StrategyConfig(
            entry_window_ms=15000,
            min_whale_trust=0,
            require_sweep=True,
            require_mss=True,
            require_fvg=True,
            require_ote=False,
            cooldown_ms=60000,
        )
        self._detector_config = DetectorConfig(
            candle_seconds=5,
            sweep_lookback=20,
            sweep_wick_ratio=0.6,
            mss_lookback=10,
            fvg_min_size_pct=0.0005,
            ote_low=0.62,
            ote_high=0.79,
            ote_lookback=20,
            max_history=300,
        )
        self._mt_detectors: dict[str, SignalDetector] = {}
        self._micro_triggers: dict[str, MicroTrigger] = {}
        self._recent_signals: dict[str, deque] = {}
        self._last_mt_state: dict[str, MicroTriggerState] = {}
        self._shadow_strategies: dict[str, Strategy] = {}
        self._shadow_detectors: dict[str, SignalDetector] = {}
        self._last_price: dict[str, float] = {}
        self._last_exchange_ts: dict[str, int] = {}
        self._mt_loop_task: asyncio.Task | None = None

        # B3.5-H=C: stop-flag internal state (observation_state.observation_stop).
        # 5s micro-trigger loop'a piggyback; SLA <=10s. Ilk poll'a kadar False.
        self._observation_stopped: bool = False

        # Initialize per-symbol state for initial symbols
        for sym in self.symbols:
            self._init_symbol_state(sym)

    def _init_symbol_state(self, symbol: str) -> None:
        """Initialize B3.2 components for a symbol."""
        if symbol in self._mt_detectors:
            return
        self._mt_detectors[symbol] = SignalDetector(self._detector_config)
        # B3.4: symbol'ü closure ile enjekte et; MicroTrigger API değişmez.
        self._micro_triggers[symbol] = MicroTrigger(
            self._mt_config,
            lambda et, pl, s=symbol: self._emit_micro_event(
                et, {**pl, "symbol": s}
            ),
        )
        self._recent_signals[symbol] = deque(maxlen=200)
        self._last_mt_state[symbol] = MicroTriggerState.IDLE
        shadow_detector = SignalDetector(self._detector_config)
        self._shadow_detectors[symbol] = shadow_detector
        self._shadow_strategies[symbol] = Strategy(
            self._strategy_config, shadow_detector
        )
        self._last_price[symbol] = 0.0
        self._last_exchange_ts[symbol] = 0

    def _emit_micro_event(self, event_type: str, payload: dict) -> None:
        """Callback for MicroTrigger events (state transitions, deadlines).

        B3.4: alert agent aktifse event fire-and-forget olarak iletilir.
        Running loop yoksa (sync test ortamı) sessizce atlanır.
        """
        log_entry = {
            "event": event_type,
            "source": "MICRO_TRIGGER",
            **payload,
        }
        logger.info(json.dumps(log_entry))
        if self._alert_agent is None:
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        payload_with_source = dict(payload)
        payload_with_source.setdefault("source", "MICRO_TRIGGER")
        try:
            loop.create_task(
                self._alert_agent.emit(event_type, payload_with_source)
            )
        except Exception as e:
            logger.warning("alert emit failed: %s", e)

    def _log_entry_signal(
        self,
        source: str,
        symbol: str,
        direction: Direction,
        price: float,
        ts_ms: int,
        reason: str,
    ) -> None:
        log_entry = {
            "event": "ENTRY_SIGNAL",
            "source": source,
            "symbol": symbol,
            "direction": direction.value,
            "price": price,
            "ts_ms": ts_ms,
            "reason": reason,
        }
        logger.info(json.dumps(log_entry))

    def _determine_direction(
        self, symbol: str, recent: deque
    ) -> Direction | None:
        kinds = {s.kind for _, s in recent}
        if (
            SignalKind.SWEEP_DOWN in kinds
            and SignalKind.MSS_UP in kinds
            and SignalKind.FVG_BULLISH in kinds
        ):
            return Direction.LONG
        if (
            SignalKind.SWEEP_UP in kinds
            and SignalKind.MSS_DOWN in kinds
            and SignalKind.FVG_BEARISH in kinds
        ):
            return Direction.SHORT
        return None

    # ---------------------------------------------------------------- depth

    def _parse_diffs(self, data: dict) -> list[tuple[str, float, float]]:
        diffs: list[tuple[str, float, float]] = []
        for row in data.get("bids") or []:
            try:
                diffs.append(("bid", float(row[0]), float(row[1])))
            except Exception:
                continue
        for row in data.get("asks") or []:
            try:
                diffs.append(("ask", float(row[0]), float(row[1])))
            except Exception:
                continue
        return diffs

    def _apply_push(self, symbol: str, data: dict) -> None:
        book = self.l2_buffer.get_book(symbol)
        if book is None:
            return
        diffs = self._parse_diffs(data)
        if not diffs:
            return
        self.l2_buffer.apply_batch(
            symbol, diffs, batch_epoch=book.seq_epoch.get(symbol, 0)
        )
        self.metrics.max_bids_len = max(self.metrics.max_bids_len, book.bids_len)
        self.metrics.max_asks_len = max(self.metrics.max_asks_len, book.asks_len)
        try:
            self.metrics.obi_samples.append(self.l2_buffer.get_obi(symbol))
        except Exception:
            pass
        # B3.3: paper last_price (best bid/ask mid) güncelle.
        # B3.3-B.3: on_ws_tick her tick'te çağrılır; freshness böylece
        # paper_manager tarafında tazelenir.
        if self._paper is not None:
            try:
                if book.bids_len > 0 and book.asks_len > 0:
                    mid = (
                        float(book.bids_price[0])
                        + float(book.asks_price[0])
                    ) / 2.0
                    if mid > 0.0:
                        self._paper.on_ws_tick(symbol, mid)
            except Exception as e:
                logger.warning(
                    "paper on_ws_tick failed symbol=%s: %s", symbol, e
                )

    def _apply_snapshot(self, symbol: str, snap: dict) -> None:
        book = self.l2_buffer.create_book(symbol)
        n_bids = min(len(snap["bids"]), 5000)
        n_asks = min(len(snap["asks"]), 5000)
        for i in range(n_bids):
            book.bids_price[i] = snap["bids"][i][0]
            book.bids_qty[i] = snap["bids"][i][1]
        book.bids_len = n_bids
        for i in range(n_asks):
            book.asks_price[i] = snap["asks"][i][0]
            book.asks_qty[i] = snap["asks"][i][1]
        book.asks_len = n_asks

    # ---------------------------------------------------------------- ws callbacks

    async def on_depth(self, symbol: str, data: dict) -> None:
        if symbol not in self.symbols:
            return
        version = data.get("version")
        if version is None:
            return
        version = int(version)

        if not self.synced.get(symbol, False):
            self.pending.setdefault(symbol, []).append(
                {"version": version, "data": data}
            )
            self.metrics.buffered_pushes += 1
            return

        self.metrics.pushes += 1
        self._last_ws_data_mono[symbol] = time.monotonic()
        result = await self.seq_validator.validate(
            symbol, self.current_epoch.get(symbol, 1), first_u=version
        )
        if result.needs_resync:
            self.metrics.gaps += 1
            logger.warning(
                "gap live symbol=%s version=%d last=%d pending=%d",
                symbol,
                version,
                result.last_u,
                len(self.pending.get(symbol, [])),
            )
            try:
                await self._gap_recover(symbol)
            except Exception as e:
                logger.warning("gap recovery failed symbol=%s: %s", symbol, e)
            return
        if not result.is_valid:
            if result.is_gap:
                self.metrics.gaps += 1
            else:
                self.metrics.stale_drops += 1
            return

        self._apply_push(symbol, data)
        self.metrics.valid += 1
        self.last_applied_version[symbol] = version

    async def on_deal(self, symbol: str, trades: list) -> None:
        """Handle push.deal batch -> 1s OHLCV USDT-normalized aggregation."""
        if symbol not in self.symbols:
            return
        cs = self._contract_size.get(symbol, 0.0)
        if cs <= 0:
            self.metrics.trades_dropped += len(trades)
            return
        for t in trades:
            if not isinstance(t, dict):
                self.metrics.trades_dropped += 1
                continue
            try:
                price = float(t["p"])
                contracts = float(t["v"])
                side = int(t["T"])
                ts_ms = int(t["t"])
            except (KeyError, ValueError, TypeError):
                self.metrics.trades_dropped += 1
                continue

            if side not in (1, 2):
                self.metrics.trades_unknown_side += 1
                continue

            usdt_vol = contracts * cs * price
            if usdt_vol <= 0:
                self.metrics.trades_dropped += 1
                continue

            self.metrics.trades_in += 1
            self._update_ohlcv(symbol, price, usdt_vol, side, ts_ms)

    def _update_ohlcv(
        self, symbol: str, price: float, usdt_vol: float, side: int, ts_ms: int
    ) -> None:
        sec = ts_ms // 1000
        b = self._ohlcv_buffer.get(symbol)

        if b is not None and sec < b["sec"]:
            self.metrics.trades_late += 1
            return

        if b is None or b["sec"] != sec:
            if b is not None:
                self._flush_ohlcv_sync(symbol, b)
                self._on_ohlcv_1s(symbol, b)
            b = {
                "sec": sec,
                "open": price,
                "high": price,
                "low": price,
                "close": price,
                "buy_vol": 0.0,
                "sell_vol": 0.0,
                "count": 0,
            }
            self._ohlcv_buffer[symbol] = b

        if price > b["high"]:
            b["high"] = price
        if price < b["low"]:
            b["low"] = price
        b["close"] = price
        if side == 1:
            b["buy_vol"] += usdt_vol
        else:
            b["sell_vol"] += usdt_vol
        b["count"] += 1
        self._last_price[symbol] = price

    def _on_ohlcv_1s(self, symbol: str, b: dict) -> None:
        """Feed completed 1s OHLCV to detectors and shadow strategy."""
        ev = OHLCVEvent(
            sec=b["sec"],
            ts_ms=b["sec"] * 1000,
            open=b["open"],
            high=b["high"],
            low=b["low"],
            close=b["close"],
            buy_vol=b["buy_vol"],
            sell_vol=b["sell_vol"],
            trade_count=b["count"],
            symbol=symbol,
            source_seq=b["sec"],
        )
        # Feed to MicroTrigger detector
        mt_det = self._mt_detectors.get(symbol)
        if mt_det is not None:
            signals = mt_det.feed_ohlcv_1s(ev)
            for s in signals:
                self._recent_signals[symbol].append((s.ts_ms, s))
        # Feed to shadow Strategy
        strat = self._shadow_strategies.get(symbol)
        if strat is not None:
            entries = strat.on_ohlcv(ev)
            for entry in entries:
                self._log_entry_signal(
                    source="STRATEGY",
                    symbol=symbol,
                    direction=entry.direction,
                    price=entry.price,
                    ts_ms=entry.ts_ms,
                    reason=entry.reason,
                )
        self._last_exchange_ts[symbol] = ev.ts_ms
        self._last_price[symbol] = ev.close
        # B3.3: paper manager'a tamamlanmış 1s OHLCV besle.
        # paper_manager içeride 5s kova birleştirmesi yapar (parite).
        if self._paper is not None:
            try:
                self._paper.on_ohlcv(OhlcvSample(
                    symbol=symbol,
                    sec=b["sec"],
                    ts_ms=b["sec"] * 1000,
                    open=b["open"],
                    high=b["high"],
                    low=b["low"],
                    close=b["close"],
                ))
            except Exception as e:
                logger.warning(
                    "paper on_ohlcv failed symbol=%s: %s", symbol, e
                )

    def _flush_ohlcv_sync(self, symbol: str, b: dict) -> None:
        if self._conn is None:
            return
        try:
            self._conn.execute(
                """INSERT OR REPLACE INTO trades_ohlcv_1s
                (symbol, sec, open, high, low, close,
                 buy_vol, sell_vol, trade_count)
                VALUES (?,?,?,?,?,?,?,?,?)""",
                (
                    symbol,
                    b["sec"],
                    b["open"],
                    b["high"],
                    b["low"],
                    b["close"],
                    b["buy_vol"],
                    b["sell_vol"],
                    b["count"],
                ),
            )
            self._conn.commit()
            self.metrics.ohlcv_flushed += 1
        except Exception as e:
            logger.warning("flush_ohlcv failed sec=%d err=%s", b["sec"], e)

    # ---------------------------------------------------------------- tickers poll

    async def _tickers_poll_task(self) -> None:
        """Poll ticker + funding REST for Top5 ∪ watch every 60s."""
        assert self.rest is not None
        while not self._shutdown_event.is_set():
            # SORU D=A: Top5 WS + Top10 watch (REST ticker 60s)
            targets = set(self.symbols) | set(self._watch_symbols)
            for symbol in sorted(targets):
                try:
                    ticker = await self.rest.fetch_ticker(symbol)
                    funding = await self.rest.fetch_funding_rate(symbol)
                    cs = self._contract_size.get(symbol, 0.0)
                    oi_usdt = (
                        ticker["hold_vol"] * cs * ticker["last_price"]
                        if cs > 0 else 0.0
                    )
                    self._insert_ticker_snapshot(ticker, funding, oi_usdt)
                    self.metrics.tickers_polled += 1
                except Exception as e:
                    self.metrics.tickers_failed += 1
                    logger.warning("tickers poll failed symbol=%s: %s", symbol, e)

            try:
                await asyncio.wait_for(
                    self._shutdown_event.wait(),
                    timeout=self.TICKERS_INTERVAL_S,
                )
                return
            except asyncio.TimeoutError:
                pass

    def _insert_ticker_snapshot(
        self, ticker: dict, funding: dict, oi_usdt: float
    ) -> None:
        if self._conn is None:
            return
        try:
            self._conn.execute(
                """INSERT INTO tickers_snapshot
                (ts_ms, symbol, last_price, fair_price, index_price,
                 hold_vol, oi_usdt, funding_rate, next_settle_ms)
                VALUES (?,?,?,?,?,?,?,?,?)""",
                (
                    ticker["ts_ms"],
                    ticker["symbol"],
                    ticker["last_price"],
                    ticker["fair_price"],
                    ticker["index_price"],
                    ticker["hold_vol"],
                    oi_usdt,
                    funding["funding_rate"],
                    funding["next_settle_ms"],
                ),
            )
            self._conn.commit()
        except Exception as e:
            logger.warning("ticker insert failed: %s", e)

        # B3.2: feed ticker to shadow strategy
        symbol = ticker["symbol"]
        strat = self._shadow_strategies.get(symbol)
        if strat is not None:
            ev = TickerEvent(
                ts_ms=ticker["ts_ms"],
                last_price=ticker["last_price"],
                fair_price=ticker["fair_price"],
                index_price=ticker["index_price"],
                hold_vol=ticker["hold_vol"],
                oi_usdt=oi_usdt,
                funding_rate=funding["funding_rate"],
                next_settle_ms=funding["next_settle_ms"],
                symbol=symbol,
                source_seq=0,
            )
            strat.on_ticker(ev)
        # B3.3: paper manager'a funding rate besle
        if self._paper is not None:
            try:
                self._paper.on_ticker(
                    symbol, funding["funding_rate"], ticker["ts_ms"],
                )
            except Exception as e:
                logger.warning(
                    "paper on_ticker failed symbol=%s: %s", symbol, e
                )

    # ---------------------------------------------------------------- bootstrap

    async def _bootstrap(self) -> None:
        assert self.rest is not None
        deadline = time.monotonic() + 3.0
        while time.monotonic() < deadline and not any(self.pending.values()):
            await asyncio.sleep(0.05)
        total_buffered = sum(len(v) for v in self.pending.values())
        logger.info("buffered pushes before snapshot total=%d", total_buffered)

        # B3.1 Q4=B: seed UniverseService (yalnız süreç başlangıcı)
        if self.universe is not None:
            self.universe.seed_subscriptions(self.symbols)

        for symbol in sorted(self.symbols):
            await self._bootstrap_symbol(symbol)

    async def _bootstrap_symbol(self, symbol: str) -> None:
        assert self.rest is not None
        snap = await self.rest.fetch_snapshot(symbol)
        self.snapshot_version[symbol] = snap["version"]
        self.last_applied_version[symbol] = snap["version"]

        pending = self.pending.get(symbol, [])
        first_pending = pending[0]["version"] if pending else None
        last_pending = pending[-1]["version"] if pending else None
        logger.info(
            "snapshot symbol=%s version=%d first_pending=%s "
            "last_pending=%s buffered=%d",
            symbol,
            snap["version"],
            first_pending,
            last_pending,
            len(pending),
        )

        self._apply_snapshot(symbol, snap)
        await self.seq_validator.set_epoch(
            symbol, self.current_epoch.get(symbol, 1)
        )
        await self.seq_validator.set_last_u(symbol, snap["version"], 0)

        target_version = snap["version"] + 1
        applied_from_buffer = 0
        remaining: list[dict] = []
        for push in pending:
            v = push["version"]
            if v < target_version:
                continue
            if v == target_version:
                self._apply_push(symbol, push["data"])
                self.last_applied_version[symbol] = v
                target_version += 1
                applied_from_buffer += 1
            else:
                remaining.append(push)

        if remaining:
            logger.warning(
                "gap between snapshot and buffer symbol=%s", symbol
            )
            try:
                await self._gap_recover(symbol)
            except Exception as e:
                logger.warning("gap bridge failed symbol=%s: %s", symbol, e)
                if remaining:
                    oldest = remaining[0]["version"]
                    await self.seq_validator.set_last_u(
                        symbol, oldest - 1, 0
                    )
                    self.last_applied_version[symbol] = oldest - 1

            for push in remaining:
                v = push["version"]
                if v != self.last_applied_version[symbol] + 1:
                    continue
                self._apply_push(symbol, push["data"])
                self.last_applied_version[symbol] = v

        self.pending[symbol] = []
        self.synced[symbol] = True
        logger.info(
            "bootstrap complete symbol=%s last_applied=%d",
            symbol,
            self.last_applied_version[symbol],
        )

    async def _gap_recover(self, symbol: str) -> None:
        if self.rest is None:
            return
        commits = await self.rest.fetch_commits(symbol, limit=1000)
        if not commits:
            logger.warning("gap recovery: no commits returned symbol=%s", symbol)
            self.metrics.resyncs += 1
            return
        applied = 0
        for commit in commits:
            v = commit["version"]
            if v <= self.last_applied_version[symbol]:
                continue
            if v != self.last_applied_version[symbol] + 1:
                break
            book = self.l2_buffer.get_book(symbol)
            if book is None:
                break
            diffs: list[tuple[str, float, float]] = []
            for p, q in commit["bids"]:
                diffs.append(("bid", p, q))
            for p, q in commit["asks"]:
                diffs.append(("ask", p, q))
            if diffs:
                self.l2_buffer.apply_batch(
                    symbol,
                    diffs,
                    batch_epoch=book.seq_epoch.get(symbol, 0),
                )
            self.last_applied_version[symbol] = v
            applied += 1

        await self.seq_validator.set_last_u(
            symbol, self.last_applied_version[symbol], 0
        )
        self.metrics.resyncs += 1
        logger.info(
            "gap recovery symbol=%s applied=%d upto=%d",
            symbol,
            applied,
            self.last_applied_version[symbol],
        )

    # ---------------------------------------------------------------- flush

    async def _flush_snapshot(self) -> None:
        """Flush per-symbol L2 depth snapshot + active OHLCV buckets."""
        if self.db_path is None or self._conn is None:
            return

        snapshot_ts = int(time.time() * 1000)
        for symbol in sorted(self.symbols):
            book = self.l2_buffer.get_book(symbol)
            if book is None:
                continue
            version = self.last_applied_version.get(symbol, 0)
            bids = [
                (float(book.bids_price[i]), float(book.bids_qty[i]))
                for i in range(min(book.bids_len, 500))
            ]
            asks = [
                (float(book.asks_price[i]), float(book.asks_qty[i]))
                for i in range(min(book.asks_len, 500))
            ]
            try:
                self._conn.execute(
                    """INSERT INTO orderbook_snapshots
                    (timestamp_ms, symbol, version, bids_json, asks_json, depth)
                    VALUES (?, ?, ?, ?, ?, ?)""",
                    (
                        snapshot_ts,
                        symbol,
                        version,
                        json.dumps(bids),
                        json.dumps(asks),
                        len(bids),
                    ),
                )
                self._conn.commit()
            except Exception as e:
                logger.warning("flush depth failed symbol=%s: %s", symbol, e)

        for sym, b in list(self._ohlcv_buffer.items()):
            self._flush_ohlcv_sync(sym, b)

    # ---------------------------------------------------------------- main

    def _setup_db(self) -> None:
        if self.db_path is None:
            return
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path), timeout=5.0)
        try:
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA busy_timeout=5000")
        except Exception as e:
            logger.warning("pragma failed: %s", e)

        self._conn.execute(
            """CREATE TABLE IF NOT EXISTS orderbook_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp_ms INTEGER,
                symbol TEXT,
                version INTEGER,
                bids_json TEXT,
                asks_json TEXT,
                depth INTEGER
            )"""
        )
        self._conn.execute(
            """CREATE TABLE IF NOT EXISTS trades_ohlcv_1s (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                sec INTEGER NOT NULL,
                open REAL, high REAL, low REAL, close REAL,
                buy_vol REAL DEFAULT 0,
                sell_vol REAL DEFAULT 0,
                trade_count INTEGER DEFAULT 0,
                UNIQUE(symbol, sec)
            )"""
        )
        self._conn.execute(
            """CREATE TABLE IF NOT EXISTS tickers_snapshot (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts_ms INTEGER NOT NULL,
                symbol TEXT NOT NULL,
                last_price REAL,
                fair_price REAL,
                index_price REAL,
                hold_vol REAL,
                oi_usdt REAL,
                funding_rate REAL,
                next_settle_ms INTEGER
            )"""
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_ohlcv_symbol_sec "
            "ON trades_ohlcv_1s(symbol, sec)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_snapshots_ts "
            "ON orderbook_snapshots(timestamp_ms)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_tickers_ts "
            "ON tickers_snapshot(ts_ms)"
        )
        self._conn.commit()

        # B3.4: alerting migration. Order matters: alerting ve
        # observation ayni PRAGMA user_version'i paylasir; alerting
        # `current >= SCHEMA_VERSION` erken-donus kullanir. Observation
        # once calisirsa taze DB'de uv=1 olur ve alerting skip eder ->
        # alert_events hic olusmaz. AlertAgent.start() icinde de
        # cagriliyor; burada cagrilinca orada idempotent no-op olur.
        try:
            alert_ver = run_alert_migration(self._conn)
            logger.warning(
                "B3_4_ALERT_MIGRATION_OK user_version=%d", alert_ver
            )
        except Exception as e:
            logger.warning("alert migration failed: %s", e)
            raise

        # B3.5 Mod 2 (T1 wiring): observation_state migration. Idempotent
        # (CREATE TABLE IF NOT EXISTS + INSERT OR IGNORE + PRAGMA
        # user_version). Mid-phase schema freeze (B3.5-AI=A) korunur;
        # yalnizca cagri baglanir.
        try:
            obs_ver = migrate_observation(self._conn)
            logger.warning(
                "B3_5_OBSERVATION_MIGRATION_OK user_version=%d", obs_ver
            )
        except Exception as e:
            logger.warning("observation migration failed: %s", e)
            raise

        # B3.3: paper manager init (setup_db idempotent; C-PROD default)
        self._paper = PaperPositionManager(
            PaperPositionConfig(),
            self._conn,
        )
        self._paper.setup_db()
        logger.warning(
            "B3_3_PAPER_MANAGER_INIT profile=%s risk_pct=%.4f global=%d",
            self._paper._cfg.config_profile_tag,
            self._paper._cfg.risk_pct,
            self._paper._cfg.max_positions_global,
        )

        # B3.4: alert config validasyon (Ş2 fail-fast). Env yoksa
        # alert agent devre dışı; runner çalışmaya devam eder.
        try:
            self._alert_config = config_from_env()
            logger.warning(
                "B3_4_ALERT_CONFIG_OK tg=%s dc=%s rate=%ds batch=%d/%ds",
                self._alert_config.telegram_enabled,
                self._alert_config.discord_enabled,
                self._alert_config.rate_limit_s,
                self._alert_config.batch_size,
                self._alert_config.batch_window_s,
            )
        except ValueError as e:
            logger.warning("alert config invalid, disabled: %s", e)
            self._alert_config = None

    def _install_sigterm(self) -> None:
        try:
            loop = asyncio.get_event_loop()
            loop.add_signal_handler(signal.SIGTERM, self._shutdown_event.set)
        except (NotImplementedError, AttributeError, ValueError):
            pass

    async def _universe_scan_loop(self) -> None:
        """B3.1 SORU B=D: 30s tarama (liste tazeliği)."""
        assert self.universe is not None
        while not self._shutdown_event.is_set():
            try:
                self._latest_scan = await self.universe.scan()
                logger.info(
                    "universe scan top5=%s watch=%s",
                    self._latest_scan.top5,
                    self._latest_scan.top10[len(self._latest_scan.top5):],
                )
            except Exception as e:
                logger.warning("universe scan failed: %s", e)
            try:
                await asyncio.wait_for(
                    self._shutdown_event.wait(),
                    timeout=self._scan_interval_s,
                )
                return
            except asyncio.TimeoutError:
                pass

    async def _ws_rotation_loop(self) -> None:
        """B3.1 SORU B=D: 5dk WS rotasyonu (churn sönümleme)."""
        assert self.universe is not None
        while not self._shutdown_event.is_set():
            try:
                await asyncio.wait_for(
                    self._shutdown_event.wait(),
                    timeout=self._rotation_interval_s,
                )
                return
            except asyncio.TimeoutError:
                pass
            if self._latest_scan is None:
                continue
            try:
                decision = self.universe.apply_scan(
                    self._latest_scan, int(time.time() * 1000)
                )
                await self._apply_rotation(decision)
            except Exception as e:
                logger.warning("ws rotation failed: %s", e)

    async def _apply_rotation(self, decision: RotationDecision) -> None:
        if self.ws is None or self.rest is None:
            return
        for sym in decision.to_subscribe:
            try:
                ok = await self.ws.subscribe(sym)
                if not ok:
                    continue
                # Yeni sembol: snapshot çek + state kur
                snap = await self.rest.fetch_snapshot(sym)
                self.symbols.add(sym)
                self.current_epoch.setdefault(sym, 1)
                self.synced.setdefault(sym, False)
                self.snapshot_version.setdefault(sym, 0)
                self.last_applied_version.setdefault(sym, 0)
                self.pending.setdefault(sym, [])
                self._apply_snapshot(sym, snap)
                self.snapshot_version[sym] = snap["version"]
                self.last_applied_version[sym] = snap["version"]
                await self.seq_validator.set_epoch(sym, 1)
                await self.seq_validator.set_last_u(sym, snap["version"], 0)
                self.synced[sym] = True
                if sym not in self._contract_size:
                    try:
                        cs = await self.rest.fetch_contract_size(sym)
                        self._contract_size[sym] = cs
                    except Exception as e:
                        logger.warning(
                            "cs fetch failed symbol=%s: %s", sym, e
                        )
                # B3.2: init new symbol state
                self._init_symbol_state(sym)
                logger.warning("B3_1_SUBSCRIBE symbol=%s", sym)
            except Exception as e:
                logger.warning("subscribe failed symbol=%s: %s", sym, e)

        for sym in decision.to_unsubscribe:
            try:
                ok = await self.ws.unsubscribe(sym)
                if ok:
                    self.symbols.discard(sym)
                    self._last_ws_data_mono.pop(sym, None)
                    logger.warning("B3_1_UNSUBSCRIBE symbol=%s", sym)
            except Exception as e:
                logger.warning("unsubscribe failed symbol=%s: %s", sym, e)

        self._watch_symbols = set(decision.watch_symbols)

    async def _per_symbol_watchdog(self) -> None:
        """Per-symbol WS data starvation watchdog (90s)."""
        while not self._shutdown_event.is_set():
            await asyncio.sleep(15)
            now = time.monotonic()
            for sym in sorted(self.symbols):
                last = self._last_ws_data_mono.get(sym, 0.0)
                if last > 0 and now - last > 90.0:
                    logger.warning(
                        "WS data starvation symbol=%s age_s=%.1f",
                        sym,
                        now - last,
                    )
                    # WS global watchdog ayrıca çalışır; per-symbol log yeterli.
            if self.ws is not None:
                last = getattr(self.ws, "_last_data_mono", 0.0)
                if last > 0 and now - last > 90.0:
                    logger.warning(
                        "WS global data starvation age_s=%.1f; shutdown",
                        now - last,
                    )
                    self._shutdown_event.set()
                    return

    async def _poll_observation_stop(self) -> None:
        """B3.5-H=C + AC=A stop-flag poll + transition emit.

        5s micro-trigger loop'a piggyback; SLA <=10s (5s poll x 2).
        Exception halinde onceki state korunur; observation cokme yok.
        Q1=A: emit noktasi burasi (tek process, tek nokta).
        """
        if self._conn is None:
            return
        try:
            new_val = poll_stop_flag(self._conn)
        except Exception as e:
            logger.warning("observation stop-flag poll failed: %s", e)
            return
        prev = self._observation_stopped
        self._observation_stopped = new_val
        if prev == new_val:
            return
        await self._emit_observation_transition(new_val)

    async def _emit_observation_transition(self, stopped: bool) -> None:
        """B3.5-AC=A transition emit + persist.

        Q1=A: transition noktasi burasi.
        Q2=B: OBSERVATION_STOPPED / OBSERVATION_RESUMED WARNING (batch).
        Q4=B: last_transition_reason persistence (frozen schema).
        Ordering (GLM kaygi): emit -> sonra DB write. Aksi halde push
        basarisiz + restart tek bildirim kaybeder.
        """
        if self._conn is None:
            return
        event_type = (
            "OBSERVATION_STOPPED" if stopped else "OBSERVATION_RESUMED"
        )
        now_ms = int(time.time() * 1000)
        # 1) Emit (once)
        if self._alert_agent is not None:
            try:
                await self._alert_agent.emit(
                    event_type,
                    {
                        "symbol": "OBSERVATION",
                        "reason": event_type,
                        "source": "RUNNER",
                        "ts_ms": now_ms,
                        "source_seq": now_ms,
                    },
                )
            except Exception as e:
                logger.warning(
                    "observation transition emit failed: %s", e
                )
        # 2) Persist (sonra)
        try:
            update_observation_state(
                self._conn,
                last_transition_ms=now_ms,
                last_transition_reason=event_type,
            )
        except Exception as e:
            logger.warning(
                "observation transition persist failed: %s", e
            )
        logger.warning(
            "B3_5_OBSERVATION_TRANSITION type=%s stopped=%s",
            event_type, stopped,
        )

    def _sync_observation_state_on_startup(self) -> None:
        """B3.5-AC=A + AD=A: startup observation_state sync.

        Onceki marker'i logla (planned/unplanned ayrimi), sonra
        'unclean' yaz — surec calisirken beklenmedik cikis olursa
        bir sonraki startup bunu yakalar.
        """
        if self._conn is None:
            return
        try:
            st = load_observation_state(self._conn)
        except Exception as e:
            logger.warning("startup obs state read failed: %s", e)
            return
        self._observation_stopped = bool(st.observation_stop)
        prev_marker = st.clean_shutdown_marker
        if prev_marker == "clean":
            logger.warning("B3_5_PREV_SHUTDOWN clean (planned)")
        elif prev_marker == "unclean":
            logger.warning(
                "B3_5_PREV_SHUTDOWN unclean (kill -9/OOM/crash?)"
            )
        else:
            logger.warning(
                "B3_5_PREV_SHUTDOWN unknown marker=%r (first run?)",
                prev_marker,
            )
        logger.warning(
            "B3_5_STARTUP_OBS_STATE stopped=%s reason=%s prev_marker=%s",
            self._observation_stopped,
            st.last_transition_reason,
            prev_marker,
        )
        # B3.5-AD=A: su anda calisiyoruz; clean cikis olursa 'clean'
        # yazilacak, aksi halde 'unclean' kalir.
        try:
            update_observation_state(
                self._conn,
                clean_shutdown_marker="unclean",
                clean_shutdown_marker_ms=int(time.time() * 1000),
            )
        except Exception as e:
            logger.warning("startup marker write failed: %s", e)

    def _mark_clean_shutdown(self) -> None:
        """B3.5-AD=A: normal cikis sonrasi clean marker yaz."""
        if self._conn is None:
            return
        try:
            update_observation_state(
                self._conn,
                clean_shutdown_marker="clean",
                clean_shutdown_marker_ms=int(time.time() * 1000),
            )
            logger.warning("B3_5_CLEAN_SHUTDOWN_MARKER_WRITTEN")
        except Exception as e:
            logger.warning("clean shutdown marker write failed: %s", e)

    async def _handle_micro_trigger_entry(
        self,
        symbol: str,
        direction: Direction,
        price: float,
        ts_ms: int,
    ) -> None:
        """B3.2 TRIGGER handling: log entry signal + paper on_entry + alert.

        B3.5-H=C: stop-flag True ise yeni entry acilmaz; gozlem devam eder
        (entry signal log yine atilir; paper on_entry + ENTRY alert skip).
        """
        self._log_entry_signal(
            source="MICRO_TRIGGER",
            symbol=symbol,
            direction=direction,
            price=price,
            ts_ms=ts_ms,
            reason="micro_trigger",
        )
        if self._observation_stopped:
            logger.warning(
                "ENTRY_SKIPPED_STOP_FLAG symbol=%s direction=%s",
                symbol,
                direction.value,
            )
            return
        # B3.3: paper entry (Direction -> str for PaperPositionManager API)
        if self._paper is not None:
            try:
                await self._paper.on_entry(
                    symbol=symbol,
                    direction=direction.value,
                    signal_ts_ms=ts_ms,
                    last_price=price,
                )
            except Exception as e:
                logger.warning(
                    "paper on_entry failed symbol=%s: %s", symbol, e
                )
        # B3.4: ENTRY event (WARNING batch routing)
        if self._alert_agent is not None:
            try:
                await self._alert_agent.emit(
                    "ENTRY",
                    {
                        "symbol": symbol,
                        "direction": direction.value,
                        "price": price,
                        "ts_ms": ts_ms,
                        "source": "MICRO_TRIGGER",
                        "source_seq": ts_ms,
                    },
                )
            except Exception as e:
                logger.warning("alert emit ENTRY failed: %s", e)

    async def _micro_trigger_loop(self) -> None:
        """B3.2: evaluate MicroTrigger every timer_sleep_ms (5s).

        SORU B3.2-D: quarantined semboller atlanir; evaluate exception
        sembolu quarantine eder (global shutdown yok).

        B3.3: TRIGGER anında PaperPositionManager.on_entry çağrılır;
        current_position_qty paper manager'dan beslenir (A.3).

        B3.5-H=C: her turun basinda stop-flag poll (5s piggyback).
        """
        while not self._shutdown_event.is_set():
            try:
                await asyncio.wait_for(
                    self._shutdown_event.wait(),
                    timeout=self._mt_config.timer_sleep_ms / 1000.0,
                )
                return
            except asyncio.TimeoutError:
                pass
            now_ms = int(time.time() * 1000)
            now_mono = time.monotonic()
            # B3.5-H=C + AC=A: 5s poll (piggyback); SLA <=10s
            await self._poll_observation_stop()
            for symbol in sorted(self.symbols):
                if symbol not in self._micro_triggers:
                    continue
                # SORU B3.2-D: quarantined sembolu atla
                if self._micro_triggers[symbol].is_quarantined(symbol):
                    continue
                last_data = self._last_ws_data_mono.get(symbol, 0.0)
                is_valid = (now_mono - last_data) < 5.0 if last_data > 0 else False
                recent = self._recent_signals.get(symbol, deque())
                sweep_detected = any(
                    s.kind in (SignalKind.SWEEP_UP, SignalKind.SWEEP_DOWN)
                    and now_ms - s.ts_ms <= 10000
                    for _, s in recent
                )
                mss_detected = any(
                    s.kind in (SignalKind.MSS_UP, SignalKind.MSS_DOWN)
                    and now_ms - s.ts_ms <= self._mt_config.mss_timeout_ms
                    for _, s in recent
                )
                fvg_detected = any(
                    s.kind in (SignalKind.FVG_BULLISH, SignalKind.FVG_BEARISH)
                    and now_ms - s.ts_ms <= self._mt_config.fvg_timeout_ms
                    for _, s in recent
                )
                micro_confirmed = any(
                    s.kind in (SignalKind.OTE_LONG, SignalKind.OTE_SHORT)
                    and now_ms - s.ts_ms <= 30000
                    for _, s in recent
                )
                exchange_ts_ms = self._last_exchange_ts.get(symbol, 0)
                # B3.3-A.3: açık paper pozisyonu varsa geri besle.
                current_position_qty = 0.0
                if self._paper is not None:
                    try:
                        current_position_qty = (
                            self._paper.get_open_position_qty(symbol)
                        )
                    except Exception:
                        current_position_qty = 0.0
                try:
                    new_state = await self._micro_triggers[symbol].evaluate(
                        symbol,
                        is_valid=is_valid,
                        sweep_detected=sweep_detected,
                        mss_detected=mss_detected,
                        fvg_detected=fvg_detected,
                        micro_confirmed=micro_confirmed,
                        exchange_ts_ms=exchange_ts_ms,
                        current_position_qty=current_position_qty,
                    )
                except Exception as e:
                    logger.warning(
                        "micro_trigger evaluate failed symbol=%s: %s", symbol, e
                    )
                    # SORU B3.2-D: hata -> sembol bazli quarantine, global yok
                    self._micro_triggers[symbol].quarantine(
                        symbol, "evaluate_error"
                    )
                    continue
                prev_state = self._last_mt_state.get(
                    symbol, MicroTriggerState.IDLE
                )
                if (
                    new_state == MicroTriggerState.TRIGGER
                    and prev_state != MicroTriggerState.TRIGGER
                ):
                    direction = self._determine_direction(symbol, recent)
                    if direction is not None:
                        price = self._last_price.get(symbol, 0.0)
                        await self._handle_micro_trigger_entry(
                            symbol, direction, price, now_ms
                        )
                    self._micro_triggers[symbol]._reset_to_idle(symbol)
                    self._last_mt_state[symbol] = MicroTriggerState.IDLE
                else:
                    self._last_mt_state[symbol] = new_state

    def _check_top5_daralma(self) -> None:
        """SORU F=C: Top5→Top4 uyarı otomatik; daralma manuel onaylı."""
        n_ws = len(self.symbols)
        if n_ws < 5:
            logger.warning(
                "TOP5_DARALMA_ALERT ws_subscriptions=%d "
                "(S' gate riski; daralma manuel onay gerektirir)",
                n_ws,
            )

    def _aggregate_report(self) -> dict:
        """B3.1: aggregate metrics; rapor şeması B3.1 kapanışında DURUM §12."""
        report = self.metrics.to_dict(",".join(sorted(self.symbols)))
        report["ws_symbols"] = sorted(self.symbols)
        report["watch_symbols"] = sorted(self._watch_symbols)
        report["quarantined"] = sorted(self.universe._quarantine_until_ms.keys()) \
            if self.universe is not None else []
        # B3.3: paper metrics summary
        if self._paper is not None:
            try:
                report["paper_open_positions"] = (
                    self._paper.get_open_position_count()
                )
                report["paper_closed_trades"] = len(
                    self._paper.closed_trades
                )
                report["paper_equity"] = round(self._paper.equity, 4)
            except Exception:
                pass
        return report

    async def run(self) -> dict:
        timeout = aiohttp.ClientTimeout(total=5.0)
        self._setup_db()

        # B3.5-AC=A + AD=A: startup observation_state sync.
        self._sync_observation_state_on_startup()
        clean_exit = False

        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                # B3.4 P+S: alert agent _setup_db sonrası, paper
                # on_startup öncesi. Session gerektirir.
                if self._alert_config is not None:
                    try:
                        self._alert_agent = AlertAgent(
                            self._alert_config, self._conn, session
                        )
                        await self._alert_agent.start()
                        logger.warning("B3_4_ALERT_AGENT_STARTED")
                    except Exception as e:
                        logger.warning(
                            "alert agent start failed: %s", e
                        )
                        self._alert_agent = None

                # B3.3-D.6: startup rehydration (açık paper pozisyonlar)
                if self._paper is not None:
                    try:
                        loaded = self._paper.on_startup()
                        logger.warning(
                            "B3_3_PAPER_REHYDRATED count=%d", loaded
                        )
                    except Exception as e:
                        logger.warning(
                            "paper on_startup failed: %s", e
                        )

                self.rest = MEXCRestClient(session)

                # contract_size per symbol
                for symbol in sorted(self.symbols):
                    try:
                        cs = await self.rest.fetch_contract_size(symbol)
                        self._contract_size[symbol] = cs
                        logger.warning(
                            "contract_size symbol=%s size=%s", symbol, cs
                        )
                    except Exception as e:
                        logger.warning(
                            "fetch_contract_size failed symbol=%s: %s "
                            "-> default 0.0001",
                            symbol,
                            e,
                        )
                        self._contract_size[symbol] = 0.0001

                # B3.1: UniverseService (rotation opsiyonel)
                if self._enable_rotation:
                    self.universe = UniverseService(
                        rest=self.rest,
                        fetcher_config=FetcherConfig(),
                        contract_sizes=dict(self._contract_size),
                        always_include=tuple(sorted(self.symbols)),
                        excluded_symbols=EXCLUDED_SYMBOLS,
                    )

                self.ws = MEXCWSClient(
                    symbols=sorted(self.symbols),
                    on_depth=self.on_depth,
                    on_deal=self.on_deal,
                    ping_interval_s=12.0,
                    dead_timeout_s=30.0,
                )
                await self.ws.connect()
                await self._bootstrap()

                self._install_sigterm()

                # B3.1: background tasks
                bg_tasks: list[asyncio.Task] = []
                bg_tasks.append(asyncio.create_task(self._tickers_poll_task()))
                bg_tasks.append(asyncio.create_task(self._per_symbol_watchdog()))
                if self.universe is not None:
                    bg_tasks.append(
                        asyncio.create_task(self._universe_scan_loop())
                    )
                    bg_tasks.append(
                        asyncio.create_task(self._ws_rotation_loop())
                    )
                # B3.2: micro trigger loop
                bg_tasks.append(asyncio.create_task(self._micro_trigger_loop()))

                start = time.monotonic()
                last_flush = time.monotonic()
                try:
                    while (
                        self.duration_s == 0
                        or time.monotonic() - start < self.duration_s
                    ):
                        if self._shutdown_event.is_set():
                            logger.warning("shutdown signal received")
                            break
                        await asyncio.sleep(5.0)
                        logger.info(
                            "tick ws_subs=%d watch=%d pushes=%d valid=%d "
                            "gaps=%d resyncs=%d stale=%d trades=%d drop=%d "
                            "side_bad=%d late=%d ohlcv=%d tickers=%d "
                            "tickers_fail=%d paper_open=%d paper_closed=%d",
                            len(self.symbols),
                            len(self._watch_symbols),
                            self.metrics.pushes,
                            self.metrics.valid,
                            self.metrics.gaps,
                            self.metrics.resyncs,
                            self.metrics.stale_drops,
                            self.metrics.trades_in,
                            self.metrics.trades_dropped,
                            self.metrics.trades_unknown_side,
                            self.metrics.trades_late,
                            self.metrics.ohlcv_flushed,
                            self.metrics.tickers_polled,
                            self.metrics.tickers_failed,
                            self._paper.get_open_position_count()
                                if self._paper is not None else 0,
                            len(self._paper.closed_trades)
                                if self._paper is not None else 0,
                        )
                        # SORU F=C: Top5→Top4 uyarı otomatik
                        self._check_top5_daralma()

                        if time.monotonic() - last_flush >= 60.0:
                            await self._flush_snapshot()
                            last_flush = time.monotonic()
                            if self._conn is not None:
                                cutoff_ms = int(
                                    (time.time() - 7 * 24 * 3600) * 1000
                                )
                                cutoff_sec = int(time.time() - 7 * 24 * 3600)
                                try:
                                    self._conn.execute(
                                        "DELETE FROM orderbook_snapshots "
                                        "WHERE timestamp_ms < ?",
                                        (cutoff_ms,),
                                    )
                                    self._conn.execute(
                                        "DELETE FROM trades_ohlcv_1s "
                                        "WHERE sec < ?",
                                        (cutoff_sec,),
                                    )
                                    self._conn.execute(
                                        "DELETE FROM tickers_snapshot "
                                        "WHERE ts_ms < ?",
                                        (cutoff_ms,),
                                    )
                                    self._conn.commit()
                                except Exception as e:
                                    logger.warning("cleanup failed: %s", e)
                finally:
                    for t in bg_tasks:
                        t.cancel()
                    await asyncio.gather(*bg_tasks, return_exceptions=True)
                    await self._flush_snapshot()
                    if self.ws is not None:
                        await self.ws.close()
            clean_exit = True
        finally:
            # B3.5-AD=A: clean shutdown marker (yalniz normal cikis).
            # Exception veya kill -9 durumunda marker 'unclean' kalir;
            # sonraki startup planned/unplanned ayrimi yapar.
            if clean_exit:
                self._mark_clean_shutdown()
            # B3.3-N4: paper pozisyonları kapat (END_OF_BACKTEST).
            # Not: restart recovery bu yolu kullanmaz; on_startup kullanır.
            if self._paper is not None:
                try:
                    self._paper.finalize(
                        last_ts_ms=int(time.time() * 1000),
                        last_prices=dict(self._last_price),
                    )
                except Exception as e:
                    logger.warning("paper finalize failed: %s", e)
            # B3.4: alert agent drain task'ı durdur (pending DB'de kalır).
            if self._alert_agent is not None:
                try:
                    await self._alert_agent.stop()
                except Exception as e:
                    logger.warning("alert agent stop failed: %s", e)
            if self._conn is not None:
                self._conn.close()

        return self._aggregate_report()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--symbols", default="BTC_USDT",
        help="virgülle ayrılmış sembol listesi (örn: BTC_USDT,SOL_USDT)",
    )
    parser.add_argument(
        "--symbol", default=None,
        help="geriye uyum için tek sembol (--symbols'u ezer)",
    )
    parser.add_argument("--duration", type=int, default=600)
    parser.add_argument("--out", default="shadow_report.json")
    parser.add_argument("--db", default=None, help="SQLite DB path")
    parser.add_argument(
        "--enable-rotation", action="store_true",
        help="B3.1: UniverseService tabanlı WS rotasyonu aktif et",
    )
    args = parser.parse_args()

    if args.symbol:
        symbols = [args.symbol]
    else:
        symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]
    if not symbols:
        parser.error("en az bir sembol gerekli")

    db_path = Path(args.db) if args.db else None
    runner = ShadowRunner(
        symbols,
        args.duration,
        db_path=db_path,
        enable_rotation=args.enable_rotation,
    )
    report = asyncio.run(runner.run())

    out_path = Path(args.out)
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    logger.info("report written %s", out_path)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()