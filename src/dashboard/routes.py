# YAMA Y-269: _ms int whitelist
# YAMA Y-345: SSE auth token
# YAMA Y-353: DI, no global
# YAMA Y-358: asyncio.Lock DI
# REV7: DB-backed routes

"""
Dashboard routes - business logic. aiohttp handlers call these.
"""

from __future__ import annotations

import asyncio
import logging
import sqlite3
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..storage.sqlite_writer import SqliteWriter

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class RoutesConfig:
    auth_token: str = ""
    sse_throttle_normal_ms: int = 1000
    sse_throttle_emergency_ms: int = 100
    replay_buffer_size: int = 100
    alive_threshold_pct: float = 0.80
    equity_window_ms: int = 24 * 3600 * 1000
    equity_max_points: int = 2000


class DashboardRoutes:
    def __init__(
        self,
        config: RoutesConfig,
        sqlite_writer: "SqliteWriter",
        sqlite_lock: asyncio.Lock,
        telemetry_queue: Any | None = None,
        started_mono: float | None = None,
        alert_agent: Any | None = None,
        *,
        conn: sqlite3.Connection | None = None,
    ) -> None:
        self._config = config
        self._sqlite = sqlite_writer
        self._lock = sqlite_lock
        self._telemetry_queue = telemetry_queue
        self._started_mono = started_mono or time.monotonic()
        self._event_buffer: list[dict] = []
        self._event_id_counter: int = 0
        self._alert_agent = alert_agent
        # B3.5 M=B: observation_state okuma icin DI (Y-353).
        # Alert agent env-gated olabilir; observation ondan bagimsiz
        # calisir (inert mode AC=A / stop-flag H=C).
        self._conn = conn

    # --------------------------------------------------------------- auth

    def validate_token(self, token: str) -> bool:
        expected = self._config.auth_token
        if not expected:
            return True
        return token == expected

    # --------------------------------------------------------------- health

    async def health(self) -> tuple[int, dict]:
        try:
            async with self._lock:
                rows = await self._sqlite.fetch(
                    "SELECT COUNT(*) FROM positions WHERE status IN ('open','partial')"
                )
            open_count = int(rows[0][0]) if rows else 0
            uptime_s = time.monotonic() - self._started_mono
            body = {
                "status": "ok",
                "open_positions": open_count,
                "uptime_s": round(uptime_s, 1),
                "alive_pct": 1.0,
            }
            return 200, body
        except Exception as e:
            logger.warning("health failed: %s", e)
            return 503, {"status": "error", "reason": str(e)}

    # --------------------------------------------------------------- positions

    async def positions(self, limit: int = 100) -> dict:
        try:
            async with self._lock:
                open_rows = await self._sqlite.list_open_positions()
                closed_rows = await self._sqlite.list_closed_positions(limit=limit)

            open_list = [self._row_to_position(r, is_open=True) for r in open_rows or []]
            closed_list = [
                self._row_to_position(r, is_open=False) for r in closed_rows or []
            ]
            return {
                "open": open_list,
                "closed": closed_list,
                "count_open": len(open_list),
                "count_closed": len(closed_list),
            }
        except Exception as e:
            logger.warning("positions failed: %s", e)
            return {"open": [], "closed": [], "error": str(e)}

    def _row_to_position(self, row: tuple, is_open: bool) -> dict:
        if is_open:
            return {
                "position_id": row[0],
                "symbol": row[1],
                "side": row[2],
                "opened_at_ms": row[3],
                "avg": row[4],
                "qty_open": row[5],
                "qty_remaining": row[6],
                "current_tp_shifted": row[7],
                "current_sl_shifted": row[8],
                "be_active": bool(row[9]),
                "trailing_active": bool(row[10]),
                "whale_trust_score": row[11],
                "universe_status": row[12],
                "version": row[13],
                "emergency_pending": bool(row[14]),
            }
        return {
            "position_id": row[0],
            "symbol": row[1],
            "side": row[2],
            "opened_at_ms": row[3],
            "closed_at_ms": row[4],
            "close_reason": row[5],
            "avg": row[6],
            "realized_pnl": row[7],
            "fee_total": row[8],
            "r_multiple": row[9],
        }

    # --------------------------------------------------------------- whales

    async def whales(self, limit: int = 50) -> dict:
        try:
            async with self._lock:
                rows = await self._sqlite.list_recent_whales(limit=limit)
            items = [
                {
                    "id": r[0],
                    "symbol": r[1],
                    "band_key": r[2],
                    "price": r[3],
                    "oi_delta_usd": r[4],
                    "fill_ratio": r[5],
                    "order_lifetime_ms": r[6],
                    "is_real": bool(r[7]),
                    "is_spoof": bool(r[8]),
                    "trust_score": r[9],
                    "exchange_ts_ms": r[10],
                    "created_at_ms": r[11],
                }
                for r in rows or []
            ]
            return {"whales": items, "count": len(items)}
        except Exception as e:
            logger.warning("whales failed: %s", e)
            return {"whales": [], "error": str(e)}

    # --------------------------------------------------------------- equity

    async def equity(self) -> dict:
        try:
            since_ms = int(time.time() * 1000) - self._config.equity_window_ms
            async with self._lock:
                rows = await self._sqlite.list_equity_snapshots(
                    since_ms=since_ms, limit=self._config.equity_max_points
                )
            points = [
                {
                    "ts_ms": r[0],
                    "balance": r[1],
                    "equity": r[2],
                    "unrealized_pnl": r[3],
                    "realized_today": r[4],
                    "drawdown_pct": r[5],
                    "open_positions": r[6],
                }
                for r in rows or []
            ]
            latest = points[-1] if points else None
            return {"points": points, "latest": latest, "count": len(points)}
        except Exception as e:
            logger.warning("equity failed: %s", e)
            return {"points": [], "latest": None, "error": str(e)}

    # --------------------------------------------------------------- pnl

    async def pnl(self) -> dict:
        try:
            from datetime import datetime, timezone

            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            async with self._lock:
                today_row = await self._sqlite.get_daily_stats(today)
                closed_rows = await self._sqlite.list_closed_positions(limit=500)

            wins = 0
            losses = 0
            total_pnl = 0.0
            total_fees = 0.0
            r_sum = 0.0
            r_count = 0
            for r in closed_rows or []:
                pnl_val = float(r[7] or 0.0)
                fee_val = float(r[8] or 0.0)
                r_val = r[9]
                total_pnl += pnl_val
                total_fees += fee_val
                if pnl_val > 0:
                    wins += 1
                elif pnl_val < 0:
                    losses += 1
                if r_val is not None:
                    try:
                        r_sum += float(r_val)
                        r_count += 1
                    except (TypeError, ValueError):
                        pass

            total = wins + losses
            win_rate = (wins / total) if total > 0 else 0.0
            avg_r = (r_sum / r_count) if r_count > 0 else 0.0

            today_dict = None
            if today_row is not None:
                today_dict = {
                    "date_utc": today_row[0],
                    "start_equity": today_row[1],
                    "end_equity": today_row[2],
                    "realized_pnl": today_row[3],
                    "fees": today_row[4],
                    "trades_count": today_row[5],
                    "win_count": today_row[6],
                    "loss_count": today_row[7],
                }

            return {
                "today": today_dict,
                "all_time": {
                    "total_pnl": total_pnl,
                    "total_fees": total_fees,
                    "wins": wins,
                    "losses": losses,
                    "trades": total,
                    "win_rate": round(win_rate, 4),
                    "avg_r_multiple": round(avg_r, 3),
                },
            }
        except Exception as e:
            logger.warning("pnl failed: %s", e)
            return {"today": None, "all_time": {}, "error": str(e)}

    # --------------------------------------------------------------- metrics

    async def metrics(self) -> dict:
        try:
            uptime_s = time.monotonic() - self._started_mono
            async with self._lock:
                rows = await self._sqlite.fetch(
                    "SELECT COUNT(*) FROM positions"
                )
            total_pos = int(rows[0][0]) if rows else 0
            return {
                "uptime_s": round(uptime_s, 1),
                "total_positions": total_pos,
                "tick_rate": 0,
                "gaps": 0,
                "resyncs": 0,
                "latency_ms": 0,
            }
        except Exception as e:
            logger.warning("metrics failed: %s", e)
            return {"error": str(e)}

    # --------------------------------------------------------------- sse

    async def sse_stream(self, last_event_id: int | None, auth_token: str):
        """Async generator yielding SSE dicts."""
        if not self.validate_token(auth_token):
            raise PermissionError("invalid token")

        if last_event_id is not None:
            for ev in self._replay_events(last_event_id):
                yield ev

        # Emit a keepalive comment event every throttle interval
        while True:
            await asyncio.sleep(self._config.sse_throttle_normal_ms / 1000.0)
            self._event_id_counter += 1
            yield {
                "id": self._event_id_counter,
                "event": "keepalive",
                "data": '{"ts": %d}' % int(time.time() * 1000),
            }

    def push_event(self, event_type: str, data: dict) -> None:
        """Called by supervisor when telemetry event arrives."""
        self._event_id_counter += 1
        self._event_buffer.append(
            {"id": self._event_id_counter, "event": event_type, "data": data}
        )
        if len(self._event_buffer) > self._config.replay_buffer_size:
            self._event_buffer = self._event_buffer[-self._config.replay_buffer_size:]

    def _replay_events(self, last_event_id: int) -> list[dict]:
        limit = self._config.replay_buffer_size
        out: list[dict] = []
        for ev in self._event_buffer:
            if ev["id"] > last_event_id:
                out.append(ev)
                if len(out) >= limit:
                    break
        return out

    # --------------------------------------------------------------- alerts

    async def alert_history(self, limit: int = 100) -> dict:
        """B3.4 E=B': alert history pull (SSE YOK)."""
        if self._alert_agent is None:
            return {
                "events": [],
                "count": 0,
                "error": "agent_not_configured",
            }
        try:
            conn = self._alert_agent._conn
            rows = conn.execute(
                "SELECT id, ts_ms, event_type, severity, symbol,"
                " delivery_status, correlation_id, attempts, last_error"
                " FROM alert_events ORDER BY id DESC LIMIT ?",
                (int(limit),),
            ).fetchall()
        except Exception as e:
            logger.warning("alert_history failed: %s", e)
            return {"events": [], "count": 0, "error": str(e)}
        events = [
            {
                "id": r[0],
                "ts_ms": r[1],
                "event_type": r[2],
                "severity": r[3],
                "symbol": r[4],
                "delivery_status": r[5],
                "correlation_id": r[6],
                "attempts": r[7],
                "last_error": r[8],
            }
            for r in rows or []
        ]
        return {"events": events, "count": len(events)}

    async def alert_status(self) -> dict:
        """B3.4 E=B': counter + breaker + status panel verisi."""
        if self._alert_agent is None:
            return {"enabled": False}
        agent = self._alert_agent
        pending = 0
        try:
            row = agent._conn.execute(
                "SELECT COUNT(*) FROM alert_events"
                " WHERE delivery_status='pending'"
            ).fetchone()
            pending = int(row[0]) if row else 0
        except Exception as e:
            logger.warning("alert_status pending count failed: %s", e)
        try:
            channels = {
                "telegram": agent.config.telegram_enabled,
                "discord": agent.config.discord_enabled,
            }
            metrics = dict(agent.metrics)
        except Exception as e:
            logger.warning("alert_status metrics failed: %s", e)
            channels = {}
            metrics = {}
        return {
            "enabled": True,
            "breaker_state": agent.breaker_state,
            "breaker_consecutive_fails": int(
                getattr(agent, "_breaker_consecutive_fails", 0)
            ),
            "pending": pending,
            "channels": channels,
            "metrics": metrics,
        }

    async def alert_test(self) -> dict:
        """B3.4 O=(B): test button; rate limit bypass YOK; token zorunlu."""
        if self._alert_agent is None:
            return {"ok": False, "error": "agent_not_configured"}
        try:
            event_id = await self._alert_agent.emit(
                "CRITICAL_ALERT",
                {
                    "symbol": "TEST",
                    "reason": "manual_test_button",
                    "source": "dashboard",
                    "ts_ms": int(time.time() * 1000),
                },
            )
            return {"ok": True, "event_id": event_id}
        except Exception as e:
            logger.warning("alert_test failed: %s", e)
            return {"ok": False, "error": str(e)}

    # --------------------------------------------------------------- observation

    async def observation(self) -> dict:
        """B3.5 M=B: observation_state tek-satir okuma (salt-okuma).

        DB baglantisi DI ile gelir (Y-353). Alert agent env-gated
        olabilir; observation ondan bagimsiz calisir. status alani
        observation_stop / auto_finalize_done'dan turetilir.
        """
        if self._conn is None:
            return {"error": "no_db_connection"}
        try:
            # Lazy import: dashboard modulu observation'a hard-bagimli
            # olmasin (test mock kolayligi + FAZ 5b wiring beklenir).
            from ..observation.state import load_state as _load
            st = _load(self._conn)
        except Exception as e:
            logger.warning("observation load failed: %s", e)
            return {"error": str(e)}

        if st.observation_stop:
            status = "stopped"
        elif st.auto_finalize_done:
            status = "completed"
        else:
            status = "active"

        return {
            "status": status,
            "observation_stop": st.observation_stop,
            "observation_started_at_ms": st.observation_started_at_ms,
            "last_refresh_attempt_ms": st.last_refresh_attempt_ms,
            "last_refresh_success_ms": st.last_refresh_success_ms,
            "last_valid_timestamp_ms": st.last_valid_timestamp_ms,
            "checkpoint_due_ms": st.checkpoint_due_ms,
            "checkpoint_due_emitted": st.checkpoint_due_emitted,
            "outage_count": st.outage_count,
            "outage_total_ms": st.outage_total_ms,
            "last_outage_start_ms": st.last_outage_start_ms,
            "last_outage_end_ms": st.last_outage_end_ms,
            "retention_mode": st.retention_mode,
            "retention_transition_ms": st.retention_transition_ms,
            "last_transition_ms": st.last_transition_ms,
            "last_transition_reason": st.last_transition_reason,
            "clean_shutdown_marker": st.clean_shutdown_marker,
            "clean_shutdown_marker_ms": st.clean_shutdown_marker_ms,
            "target_days": st.target_days,
            "auto_finalize_done": st.auto_finalize_done,
            "observation_completed_ms": st.observation_completed_ms,
        }