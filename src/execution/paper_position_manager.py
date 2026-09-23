# src/execution/paper_position_manager.py
# B3.3 — Paper position manager (canlı canlı paper trading).
#
# SORU B3.3-A: (A) ayrı dosya; backtest PositionSimulator ve gerçek
#   OrderManager bu akıştan ayrı tutulur.
# SORU B3.3-A.1: matematik çekirdeği src/trading/paper_math.py'den
#   import edilir; hiçbir formül burada tekrar yazılmaz.
# SORU B3.3-A.2: entry kritik bölgesi tek global asyncio.Lock.
# SORU B3.3-A.3: get_open_position_qty() — MicroTrigger.evaluate
#   current_position_qty geri beslemesi için.
# SORU B3.3-A.4 / D.6: on_startup() DB'deki OPEN pozisyonları yükler.
# SORU B3.3-B: entry 2 bps slippage; B.1 yön; B.2 sizing entry_fill
#   üzerinden; B.3 stale_price_ms=5000 -> "stale_price" reddi.
# SORU B3.3-C: (A') 5s OHLCV high/low exit; entry_bucket_sec atlanır;
#   aynı mumda TP+SL -> SL önce (konservatif).
# SORU B3.3-D: (B) SQLite paper_positions + paper_events;
#   D.1 commit->memory; D.3 UNIQUE idempotency; D.4 config
#   izlenebilirliği; D.5 WAL + busy_timeout; D.6 startup recovery.
# SORU B3.3-E: (B+) ENTRY/EXIT -> paper_positions; REJECT +
#   lifecycle events -> paper_events.
# SORU B3.3-F: (C-PROD) default PROD (0.006/2); config_profile_tag
#   position satırına yazılır.
# N5: quarantine altında açık pozisyon exit akışı DEVAM eder; entry
#   kontrolü çağıranın (runner) sorumluluğundadır.

from __future__ import annotations

import asyncio
import logging
import math
import sqlite3
import time
from collections import deque
from dataclasses import dataclass
from typing import Callable

from src.trading import paper_math as pm

logger = logging.getLogger(__name__)

_CANDLE_SEC = 5
_FUNDING_HOURS_UTC = (0, 8, 16)


# ----------------------------------------------------------------- config


@dataclass(frozen=True, slots=True)
class PaperPositionConfig:
    initial_equity: float = 10_000.0
    # C-PROD default; CLI/çağrı ile TEST override mümkün.
    risk_pct: float = 0.006
    atr_period: int = 14
    sl_atr_multiplier: float = 0.5
    tp_r_multiple: float = 2.0
    max_sl_distance_pct: float = 0.025
    min_sl_distance_pct: float = 0.002
    entry_slippage_bps: float = 2.0
    fee_taker: float = 0.0002
    fee_maker: float = 0.0
    include_funding: bool = False
    max_positions_per_symbol: int = 1
    max_positions_global: int = 2  # PROD
    # B.3: son fiyat bu süreden eskiyse entry reddedilir.
    stale_price_ms: int = 5_000
    # D.4: hangi profilde koştuğunu kayıt altına alır.
    config_profile_tag: str = "PAPER_PROD"
    candle_cap_min: int = 100


# ----------------------------------------------------------------- inputs


@dataclass(frozen=True, slots=True)
class OhlcvSample:
    """Runner, backtest OHLCVEvent'i bu hafif tipe map eder.
    Paper manager backtest tiplerine bağımlı değildir (A.1)."""
    symbol: str
    sec: int
    ts_ms: int
    open: float
    high: float
    low: float
    close: float


@dataclass(slots=True)
class _Candle5s:
    sec: int
    ts_ms: int
    open: float
    high: float
    low: float
    close: float


@dataclass(slots=True)
class _PaperPosition:
    position_id: str
    symbol: str
    direction: str
    entry_ts_ms: int
    entry_bucket_sec: int
    entry_price: float
    qty: float
    sl_price: float
    tp_price: float
    entry_fee: float
    funding_paid: float = 0.0


@dataclass(slots=True)
class PaperTradeResult:
    position_id: str
    symbol: str
    direction: str
    entry_ts_ms: int
    entry_price: float
    qty: float
    sl_price: float
    tp_price: float
    exit_ts_ms: int
    exit_price: float
    exit_reason: str
    fee_paid: float
    funding_paid: float
    pnl_gross: float
    pnl_net: float
    r_multiple: float
    entry_bucket_sec: int

    def to_dict(self) -> dict:
        return {
            "position_id": self.position_id,
            "symbol": self.symbol,
            "direction": self.direction,
            "entry_ts_ms": self.entry_ts_ms,
            "entry_price": self.entry_price,
            "qty": self.qty,
            "sl_price": self.sl_price,
            "tp_price": self.tp_price,
            "exit_ts_ms": self.exit_ts_ms,
            "exit_price": self.exit_price,
            "exit_reason": self.exit_reason,
            "fee_paid": round(self.fee_paid, 8),
            "funding_paid": round(self.funding_paid, 8),
            "pnl_gross": round(self.pnl_gross, 8),
            "pnl_net": round(self.pnl_net, 8),
            "r_multiple": round(self.r_multiple, 4),
            "entry_bucket_sec": self.entry_bucket_sec,
        }


# ----------------------------------------------------------------- manager


class PaperPositionManager:
    """
    B3.3 — paper position lifecycle.

    Runner bağlar (delivery 2):
      - on_ws_tick(symbol, price, mono_ms)   her tick (last_price izleme)
      - on_ohlcv(OhlcvSample)                 her tamamlanan 1s OHLCV
      - on_ticker(symbol, funding_rate, ts)  funding rate güncellemesi
      - await on_entry(symbol, direction, signal_ts_ms, last_price,
                       mono_ms)               MicroTrigger TRIGGER'da
      - finalize(last_ts_ms, last_prices)     shutdown öncesi
      - on_startup()                          boot sonrası, rehydration
    """

    def __init__(
        self,
        config: PaperPositionConfig,
        conn: sqlite3.Connection,
        *,
        mono_ms_fn: Callable[[], int] | None = None,
        wall_ms_fn: Callable[[], int] | None = None,
    ) -> None:
        self._cfg = config
        self._conn = conn
        self._mono_ms_fn = mono_ms_fn or (lambda: int(time.monotonic() * 1000))
        self._wall_ms_fn = wall_ms_fn or (lambda: int(time.time() * 1000))

        self._global_lock = asyncio.Lock()  # A.2

        self._positions: dict[str, _PaperPosition] = {}
        self._candles: dict[str, deque[_Candle5s]] = {}
        self._active: dict[str, _Candle5s] = {}
        self._last_price: dict[str, float] = {}
        self._last_price_mono_ms: dict[str, int] = {}
        self._last_funding_rate: dict[str, float] = {}
        self._next_funding_ms: dict[str, int] = {}

        self._realized_equity = float(config.initial_equity)
        self._closed_trades: list[PaperTradeResult] = []
        self._last_rejection_reason: str | None = None

        self._candle_cap = max(config.atr_period * 4, config.candle_cap_min)

    # ------------------------------------------------------------ accessors

    @property
    def equity(self) -> float:
        """MTM: realized + unrealized (entry_fee + funding_paid + gross).
        Mirror of position_sim.equity property semantics."""
        eq = self._realized_equity
        for sym, pos in self._positions.items():
            px = self._last_price.get(sym)
            if px is None:
                continue
            if pos.direction == pm.LONG:
                upnl = (px - pos.entry_price) * pos.qty
            else:
                upnl = (pos.entry_price - px) * pos.qty
            eq += upnl - pos.funding_paid
        return eq

    @property
    def open_positions(self) -> dict[str, _PaperPosition]:
        return dict(self._positions)

    @property
    def closed_trades(self) -> list[PaperTradeResult]:
        return list(self._closed_trades)

    @property
    def last_rejection_reason(self) -> str | None:
        return self._last_rejection_reason

    def get_open_position_qty(self, symbol: str) -> float:
        """A.3: MicroTrigger.evaluate(current_position_qty=...) için."""
        pos = self._positions.get(symbol)
        return pos.qty if pos is not None else 0.0

    def get_open_position_count(self) -> int:
        return len(self._positions)

    # ------------------------------------------------------------ schema

    def setup_db(self) -> None:
        """D.5: WAL + busy_timeout (runner zaten aynı deseni kullanıyor).
        Bu metot çağrıldığında tablolar oluşturulur; idempotenttir."""
        try:
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA busy_timeout=5000")
        except Exception as e:
            logger.warning("paper setup_db pragma failed: %s", e)

        self._conn.execute(
            """CREATE TABLE IF NOT EXISTS paper_positions (
                position_id TEXT PRIMARY KEY,
                symbol TEXT NOT NULL,
                direction TEXT NOT NULL,
                entry_ts_ms INTEGER NOT NULL,
                entry_price REAL NOT NULL,
                qty REAL NOT NULL,
                sl_price REAL NOT NULL,
                tp_price REAL NOT NULL,
                entry_fee REAL NOT NULL,
                funding_paid REAL NOT NULL DEFAULT 0.0,
                entry_bucket_sec INTEGER NOT NULL,
                status TEXT NOT NULL,
                exit_ts_ms INTEGER,
                exit_price REAL,
                exit_reason TEXT,
                exit_fee REAL,
                pnl_gross REAL,
                pnl_net REAL,
                r_multiple REAL,
                config_profile_tag TEXT NOT NULL,
                risk_pct REAL NOT NULL,
                max_positions_global INTEGER NOT NULL,
                max_positions_per_symbol INTEGER NOT NULL,
                initial_equity REAL NOT NULL,
                entry_slippage_bps REAL NOT NULL,
                created_at_ms INTEGER NOT NULL,
                closed_at_ms INTEGER
            )"""
        )
        self._conn.execute(
            """CREATE TABLE IF NOT EXISTS paper_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                position_id TEXT,
                symbol TEXT NOT NULL,
                event_type TEXT NOT NULL,
                reason TEXT,
                source_seq INTEGER,
                ts_ms INTEGER NOT NULL,
                created_at_ms INTEGER NOT NULL,
                UNIQUE(position_id, event_type, source_seq)
            )"""
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_paper_positions_status "
            "ON paper_positions(status)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_paper_events_symbol_ts "
            "ON paper_events(symbol, ts_ms)"
        )
        self._conn.commit()

    # ------------------------------------------------------------ startup

    def on_startup(self) -> int:
        """D.6: DB'de OPEN paper pozisyonları in-memory'ye yükle.
        Dönen değer yüklenen pozisyon sayısı (telemetry için).
        Candles/funding state sıfırdan başlar; SL/TP/entry_bucket_sec
        pozisyon satırından gelir (ATR warmup gerekmez)."""
        try:
            cur = self._conn.execute(
                "SELECT position_id, symbol, direction, entry_ts_ms, "
                "entry_price, qty, sl_price, tp_price, entry_fee, "
                "funding_paid, entry_bucket_sec "
                "FROM paper_positions WHERE status='OPEN'"
            )
            rows = list(cur)
        except Exception as e:
            logger.warning("paper on_startup read failed: %s", e)
            return 0
        loaded = 0
        for row in rows:
            try:
                pos = _PaperPosition(
                    position_id=str(row[0]),
                    symbol=str(row[1]),
                    direction=str(row[2]),
                    entry_ts_ms=int(row[3]),
                    entry_price=float(row[4]),
                    qty=float(row[5]),
                    sl_price=float(row[6]),
                    tp_price=float(row[7]),
                    entry_fee=float(row[8]),
                    funding_paid=float(row[9]),
                    entry_bucket_sec=int(row[10]),
                )
            except Exception as e:
                logger.warning("paper on_startup row parse failed: %s", e)
                continue
            self._positions[pos.symbol] = pos
            loaded += 1
        if loaded:
            logger.warning(
                "paper on_startup rehydrated %d open position(s)", loaded
            )
        return loaded

    # ------------------------------------------------------------ feeds

    def on_ws_tick(self, symbol: str, price: float, mono_ms: int | None = None) -> None:
        """B.3: last_price + freshness takibi. Her WS tick'te çağrılır."""
        if price is None or price <= 0.0 or not math.isfinite(price):
            return
        self._last_price[symbol] = float(price)
        self._last_price_mono_ms[symbol] = (
            mono_ms if mono_ms is not None else self._mono_ms_fn()
        )

    def on_ticker(self, symbol: str, funding_rate: float, ts_ms: int) -> None:
        """Funding rate güncellemesi (position_sim.on_ticker paritesi)."""
        try:
            self._last_funding_rate[symbol] = float(funding_rate or 0.0)
        except (TypeError, ValueError):
            self._last_funding_rate[symbol] = 0.0

    def on_ohlcv(self, sample: OhlcvSample) -> None:
        """Tamamlanan 1s OHLCV -> 5s mum birleştirme + exit kontrolü.
        C=5s ve SL-önceliği B2c kilitli. entry_bucket_sec atlanır.
        SORU B3.3-D.1: exit yazımı commit -> memory sırasıyla yapılır.
        """
        cfg = self._cfg
        symbol = sample.symbol
        if sample.close <= 0.0 or not math.isfinite(sample.close):
            return

        bucket_sec = (sample.sec // _CANDLE_SEC) * _CANDLE_SEC
        active = self._active.get(symbol)

        if active is None:
            self._active[symbol] = _Candle5s(
                sec=bucket_sec,
                ts_ms=bucket_sec * 1000,
                open=sample.open,
                high=sample.high,
                low=sample.low,
                close=sample.close,
            )
        elif bucket_sec > active.sec:
            # mum kapandı; exit kontrolü yapılır
            self._finalize_active(symbol)
            self._active[symbol] = _Candle5s(
                sec=bucket_sec,
                ts_ms=bucket_sec * 1000,
                open=sample.open,
                high=sample.high,
                low=sample.low,
                close=sample.close,
            )
        elif bucket_sec == active.sec:
            if sample.high > active.high:
                active.high = sample.high
            if sample.low < active.low:
                active.low = sample.low
            active.close = sample.close
        # else: out-of-order 1s, drop

        # funding kontrolü (position_sim.on_ohlcv paritesi)
        if symbol not in self._next_funding_ms:
            self._next_funding_ms[symbol] = pm.next_funding_ts_ms(sample.ts_ms)
        while sample.ts_ms >= self._next_funding_ms[symbol]:
            if cfg.include_funding:
                self._apply_funding(symbol)
            self._next_funding_ms[symbol] = pm.next_funding_ts_ms(
                self._next_funding_ms[symbol] + 1
            )

        self._last_price[symbol] = float(sample.close)
        self._last_price_mono_ms.setdefault(
            symbol, self._mono_ms_fn()
        )

    def _finalize_active(self, symbol: str) -> None:
        b = self._active.pop(symbol, None)
        if b is None:
            return
        dq = self._candles.get(symbol)
        if dq is None:
            dq = deque(maxlen=self._candle_cap)
            self._candles[symbol] = dq
        dq.append(b)
        self._check_exits_on_candle(b, symbol)

    def _apply_funding(self, symbol: str) -> None:
        pos = self._positions.get(symbol)
        if pos is None:
            return
        rate = self._last_funding_rate.get(symbol, 0.0)
        notional = pos.entry_price * pos.qty
        pos.funding_paid += pm.compute_funding_delta(
            rate, notional, pos.direction
        )

    # ------------------------------------------------------------ entry

    async def on_entry(
        self,
        symbol: str,
        direction: str,
        signal_ts_ms: int,
        last_price: float,
        *,
        mono_ms: int | None = None,
    ) -> bool:
        """MicroTrigger TRIGGER'dan çağrılır.
        Dönüş True: pozisyon açıldı; False: reddedildi
        (last_rejection_reason doludur).
        A.2: entry kararı global lock altında (cross-symbol).
        N5: bu metot quarantine kontrolü YAPMAZ; çağıran (runner)
        quarantine'de entry çağırmaz, exit bağımsız devam eder.
        """
        self._last_rejection_reason = None
        cfg = self._cfg
        now_mono = mono_ms if mono_ms is not None else self._mono_ms_fn()

        # B.3 stale price
        last_mono = self._last_price_mono_ms.get(symbol)
        if last_mono is None:
            self._last_rejection_reason = "stale_price"
            self._write_event(
                position_id=None, symbol=symbol, event_type="REJECT",
                reason="stale_price", source_seq=signal_ts_ms,
                ts_ms=signal_ts_ms,
            )
            return False
        if now_mono - last_mono > cfg.stale_price_ms:
            self._last_rejection_reason = "stale_price"
            self._write_event(
                position_id=None, symbol=symbol, event_type="REJECT",
                reason="stale_price", source_seq=signal_ts_ms,
                ts_ms=signal_ts_ms,
            )
            return False

        if last_price is None or last_price <= 0.0 or not math.isfinite(last_price):
            self._last_rejection_reason = "invalid_price"
            self._write_event(
                position_id=None, symbol=symbol, event_type="REJECT",
                reason="invalid_price", source_seq=signal_ts_ms,
                ts_ms=signal_ts_ms,
            )
            return False

        async with self._global_lock:
            # limits
            if symbol in self._positions:
                self._last_rejection_reason = "per_symbol_max_position"
                self._write_event(
                    position_id=None, symbol=symbol, event_type="REJECT",
                    reason="per_symbol_max_position",
                    source_seq=signal_ts_ms, ts_ms=signal_ts_ms,
                )
                return False
            if len(self._positions) >= cfg.max_positions_global:
                self._last_rejection_reason = "global_limit_full"
                self._write_event(
                    position_id=None, symbol=symbol, event_type="REJECT",
                    reason="global_limit_full",
                    source_seq=signal_ts_ms, ts_ms=signal_ts_ms,
                )
                return False
            if cfg.max_positions_per_symbol < 1:
                self._last_rejection_reason = "per_symbol_max_position"
                self._write_event(
                    position_id=None, symbol=symbol, event_type="REJECT",
                    reason="per_symbol_max_position",
                    source_seq=signal_ts_ms, ts_ms=signal_ts_ms,
                )
                return False

            # ATR
            dq = self._candles.get(symbol)
            candles_list = list(dq) if dq is not None else []
            atr = pm.compute_atr(candles_list, cfg.atr_period)
            if atr is None or atr <= 0.0:
                self._last_rejection_reason = "atr_not_ready"
                self._write_event(
                    position_id=None, symbol=symbol, event_type="REJECT",
                    reason="atr_not_ready",
                    source_seq=signal_ts_ms, ts_ms=signal_ts_ms,
                )
                return False

            # B.1 + B.2: entry_fill -> sizing -> SL/TP
            entry_fill = pm.apply_entry_slippage(
                last_price, direction, cfg.entry_slippage_bps
            )
            if entry_fill <= 0.0:
                self._last_rejection_reason = "invalid_price"
                return False
            sl_distance = pm.compute_sl_distance(
                atr,
                entry_fill,
                sl_atr_multiplier=cfg.sl_atr_multiplier,
                max_sl_distance_pct=cfg.max_sl_distance_pct,
                min_sl_distance_pct=cfg.min_sl_distance_pct,
            )
            if sl_distance <= 0.0:
                self._last_rejection_reason = "invalid_sl_distance"
                self._write_event(
                    position_id=None, symbol=symbol, event_type="REJECT",
                    reason="invalid_sl_distance",
                    source_seq=signal_ts_ms, ts_ms=signal_ts_ms,
                )
                return False

            sl_price = pm.compute_sl_price(entry_fill, sl_distance, direction)
            tp_price = pm.compute_tp_price(
                entry_fill, sl_distance, cfg.tp_r_multiple, direction
            )
            equity_mtm = self.equity
            qty = pm.compute_qty(equity_mtm, cfg.risk_pct, sl_distance)
            if qty <= 0.0:
                self._last_rejection_reason = "invalid_qty"
                self._write_event(
                    position_id=None, symbol=symbol, event_type="REJECT",
                    reason="invalid_qty",
                    source_seq=signal_ts_ms, ts_ms=signal_ts_ms,
                )
                return False

            entry_fee = pm.compute_entry_fee(
                entry_fill, qty, cfg.fee_taker
            )
            bucket_sec = (signal_ts_ms // 1000 // _CANDLE_SEC) * _CANDLE_SEC

            position_id = f"paper-{symbol}-{signal_ts_ms}"
            pos = _PaperPosition(
                position_id=position_id,
                symbol=symbol,
                direction=direction,
                entry_ts_ms=signal_ts_ms,
                entry_bucket_sec=bucket_sec,
                entry_price=entry_fill,
                qty=qty,
                sl_price=sl_price,
                tp_price=tp_price,
                entry_fee=entry_fee,
            )

            # D.1: once DB commit, sonra memory
            ok = self._write_position_open(pos)
            if not ok:
                self._last_rejection_reason = "db_write_failed"
                return False
            self._positions[symbol] = pos
            self._write_event(
                position_id=position_id, symbol=symbol,
                event_type="ENTRY", reason=None,
                source_seq=signal_ts_ms, ts_ms=signal_ts_ms,
            )
            logger.warning(
                "PAPER_ENTRY symbol=%s dir=%s entry=%.8f qty=%.8f "
                "sl=%.8f tp=%.8f",
                symbol, direction, entry_fill, qty, sl_price, tp_price,
            )
            return True

    # ------------------------------------------------------------ exit

    def _check_exits_on_candle(self, c: _Candle5s, symbol: str) -> None:
        pos = self._positions.get(symbol)
        if pos is None:
            return
        # B2c: entry bucket atlanir (look-ahead onleme)
        if c.sec <= pos.entry_bucket_sec:
            return
        if pos.direction == pm.LONG:
            hit_sl = c.low <= pos.sl_price
            hit_tp = c.high >= pos.tp_price
            if hit_sl:
                self._close_position(
                    symbol, c.ts_ms, pos.sl_price, pm.SL
                )
            elif hit_tp:
                self._close_position(
                    symbol, c.ts_ms, pos.tp_price, pm.TP
                )
        else:
            hit_sl = c.high >= pos.sl_price
            hit_tp = c.low <= pos.tp_price
            if hit_sl:
                self._close_position(
                    symbol, c.ts_ms, pos.sl_price, pm.SL
                )
            elif hit_tp:
                self._close_position(
                    symbol, c.ts_ms, pos.tp_price, pm.TP
                )

    def _close_position(
        self,
        symbol: str,
        ts_ms: int,
        exit_price: float,
        reason: str,
    ) -> None:
        pos = self._positions.get(symbol)
        if pos is None:
            return
        cfg = self._cfg
        pnl_gross = pm.compute_pnl_gross(
            pos.entry_price, exit_price, pos.qty, pos.direction
        )
        exit_fee = pm.compute_exit_fee(
            exit_price, pos.qty, cfg.fee_taker, cfg.fee_maker, reason
        )
        total_fee = pos.entry_fee + exit_fee
        pnl_net = pnl_gross - total_fee - pos.funding_paid
        r_mult = pm.compute_r_multiple(
            pos.entry_price, exit_price, pos.sl_price, pos.direction
        )

        trade = PaperTradeResult(
            position_id=pos.position_id,
            symbol=symbol,
            direction=pos.direction,
            entry_ts_ms=pos.entry_ts_ms,
            entry_price=pos.entry_price,
            qty=pos.qty,
            sl_price=pos.sl_price,
            tp_price=pos.tp_price,
            exit_ts_ms=ts_ms,
            exit_price=exit_price,
            exit_reason=reason,
            fee_paid=total_fee,
            funding_paid=pos.funding_paid,
            pnl_gross=pnl_gross,
            pnl_net=pnl_net,
            r_multiple=r_mult,
            entry_bucket_sec=pos.entry_bucket_sec,
        )

        # D.1: once DB commit, sonra memory
        ok = self._write_position_close(trade, exit_fee=exit_fee)
        if not ok:
            logger.warning(
                "paper close DB write failed position_id=%s; "
                "memory state guncellenmedi",
                pos.position_id,
            )
            return
        del self._positions[symbol]
        self._closed_trades.append(trade)
        self._realized_equity += pnl_net
        self._write_event(
            position_id=trade.position_id, symbol=symbol,
            event_type="EXIT", reason=reason,
            source_seq=ts_ms // 1000, ts_ms=ts_ms,
        )
        logger.warning(
            "PAPER_EXIT symbol=%s reason=%s exit=%.8f pnl_net=%.8f "
            "r=%.4f",
            symbol, reason, exit_price, pnl_net, r_mult,
        )

    # ------------------------------------------------------------ finalize

    def finalize(
        self, last_ts_ms: int, last_prices: dict[str, float]
    ) -> None:
        """Shutdown oncesi tum acik pozisyonlari kapatir.
        N4: bu metot END_OF_BACKTEST cikisi uretir; restart recovery
        tarafindan CAGRILMAZ (on_startup kullanilir)."""
        for symbol in list(self._active.keys()):
            self._finalize_active(symbol)
        for symbol in list(self._positions.keys()):
            px = last_prices.get(symbol)
            if px is None or px <= 0.0:
                px = self._last_price.get(symbol)
            if px is None:
                logger.warning(
                    "paper finalize: no price for %s; using entry price",
                    symbol,
                )
                px = self._positions[symbol].entry_price
            self._close_position(
                symbol, last_ts_ms, px, pm.END_OF_BACKTEST
            )

    # ------------------------------------------------------------ db writes

    def _write_position_open(self, pos: _PaperPosition) -> bool:
        try:
            self._conn.execute(
                """INSERT OR IGNORE INTO paper_positions (
                    position_id, symbol, direction, entry_ts_ms,
                    entry_price, qty, sl_price, tp_price, entry_fee,
                    funding_paid, entry_bucket_sec, status,
                    config_profile_tag, risk_pct, max_positions_global,
                    max_positions_per_symbol, initial_equity,
                    entry_slippage_bps, created_at_ms
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    pos.position_id, pos.symbol, pos.direction,
                    pos.entry_ts_ms, pos.entry_price, pos.qty,
                    pos.sl_price, pos.tp_price, pos.entry_fee,
                    pos.funding_paid, pos.entry_bucket_sec, "OPEN",
                    self._cfg.config_profile_tag, self._cfg.risk_pct,
                    self._cfg.max_positions_global,
                    self._cfg.max_positions_per_symbol,
                    self._cfg.initial_equity,
                    self._cfg.entry_slippage_bps,
                    self._wall_ms_fn(),
                ),
            )
            self._conn.commit()
            return True
        except Exception as e:
            logger.warning("paper open write failed: %s", e)
            return False

    def _write_position_close(
        self, trade: PaperTradeResult, *, exit_fee: float
    ) -> bool:
        try:
            self._conn.execute(
                """UPDATE paper_positions SET
                    status='CLOSED', exit_ts_ms=?, exit_price=?,
                    exit_reason=?, exit_fee=?, pnl_gross=?, pnl_net=?,
                    r_multiple=?, closed_at_ms=?
                WHERE position_id=? AND status='OPEN'""",
                (
                    trade.exit_ts_ms, trade.exit_price, trade.exit_reason,
                    exit_fee, trade.pnl_gross, trade.pnl_net,
                    trade.r_multiple, self._wall_ms_fn(),
                    trade.position_id,
                ),
            )
            self._conn.commit()
            return True
        except Exception as e:
            logger.warning("paper close write failed: %s", e)
            return False

    def _write_event(
        self,
        *,
        position_id: str | None,
        symbol: str,
        event_type: str,
        reason: str | None,
        source_seq: int | None,
        ts_ms: int,
    ) -> None:
        try:
            self._conn.execute(
                """INSERT OR IGNORE INTO paper_events (
                    position_id, symbol, event_type, reason,
                    source_seq, ts_ms, created_at_ms
                ) VALUES (?,?,?,?,?,?,?)""",
                (
                    position_id, symbol, event_type, reason,
                    source_seq, ts_ms, self._wall_ms_fn(),
                ),
            )
            self._conn.commit()
        except Exception as e:
            logger.warning("paper event write failed: %s", e)