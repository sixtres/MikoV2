# src/alerting/agent.py
"""B3.4 Mod 2 — AlertAgent.

Kilitli kararlar (DURUM §11 B3.4):
- A=(D) config-driven; Telegram primary, Discord opt-in.
- B=(D) katmanlı routing: CRITICAL bypass / WARNING batch / INFO log+DB.
- C=(C) CRITICAL bypass + per-channel 30s rate limit (rate_limit_s).
- D=(C) batch 5/5s (batch_size / batch_window_s).
- F=(D) retry 3 (retry_max); breaker 5 ardışık nihai fail → OPEN 60s
  → HALF_OPEN 1 test.
- M/AA=(C) dedup sembol+event_type 60s + sayıyla birleştirme (in-buffer).
- S=(D) alert_events tek doğruluk kaynağı.
- T=(C) pending TTL 10dk; startup sweep → 'expired'.
- Z=(C) network sırasında DB txn açık değil; UPDATE kısa senkron.
- AH 3 semantik: (i) HALF_OPEN testi gerçek pending CRITICAL;
  (ii) breaker alert-başına nihai sonuç sayar (retry_max tamamlanmadan
  artmaz); (iii) 429 Retry-After saygı → breaker'a fail yazılmaz.
- AI=(B) MIKOV2_ALERT_* + int whitelist; Ş2 fail-fast invariant.
- AB4: UPDATE ... WHERE id=? AND delivery_status='pending' optimistic lock.
- Ş3=(D) DI: connection sahibi çağıran; drain lock'u dışarıdan yönetilir.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import sqlite3
import time
from collections import deque
from dataclasses import dataclass
from typing import Any, Callable, Final, Optional

import aiohttp

from .event_catalog import (
    SEVERITY_CRITICAL,
    SEVERITY_INFO,
    SEVERITY_WARNING,
    get_severity,
)
from .formatter import (
    render_discord,
    render_discord_batch,
    render_telegram,
    render_telegram_batch,
)
from .migration import run_migration

logger = logging.getLogger("alerting.agent")

_BREAKER_CLOSED: Final = "closed"
_BREAKER_OPEN: Final = "open"
_BREAKER_HALF_OPEN: Final = "half_open"

_STATUS_PENDING: Final = "pending"
_STATUS_SENDING: Final = "sending"
_STATUS_DELIVERED: Final = "delivered"
_STATUS_FAILED: Final = "failed"
_STATUS_EXPIRED: Final = "expired"


def _json_safe(obj: Any) -> str:
    try:
        return json.dumps(obj, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        return json.dumps({"error": "unserializable"})


@dataclass(frozen=True, slots=True)
class AlertConfig:
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    discord_webhook_url: str = ""
    rate_limit_s: int = 30
    batch_size: int = 5
    batch_window_s: int = 5
    dedup_window_s: int = 60
    dedup_batch_window_s: int = 300
    pending_max: int = 100
    pending_ttl_s: int = 600
    retry_max: int = 3
    breaker_fail_threshold: int = 5
    breaker_open_s: int = 60

    def validate(self) -> None:
        if self.dedup_window_s < self.rate_limit_s:
            raise ValueError(
                "AlertConfig: dedup_window_s ({}) must be >= rate_limit_s ({})"
                .format(self.dedup_window_s, self.rate_limit_s)
            )
        if not (self.telegram_bot_token and self.telegram_chat_id) \
                and not self.discord_webhook_url:
            raise ValueError("AlertConfig: at least one channel required")
        for name in ("rate_limit_s", "batch_size", "batch_window_s",
                     "dedup_window_s", "dedup_batch_window_s",
                     "pending_max", "pending_ttl_s", "retry_max",
                     "breaker_fail_threshold", "breaker_open_s"):
            v = getattr(self, name)
            if not isinstance(v, int) or v < 0:
                raise ValueError(
                    "AlertConfig: {} must be non-negative int".format(name)
                )

    @property
    def telegram_enabled(self) -> bool:
        return bool(self.telegram_bot_token and self.telegram_chat_id)

    @property
    def discord_enabled(self) -> bool:
        return bool(self.discord_webhook_url)


def config_from_env(env: Optional[dict] = None) -> AlertConfig:
    if env is None:
        env = dict(os.environ)

    def _int(key: str, default: int) -> int:
        v = env.get(key)
        if v is None or v == "":
            return default
        try:
            return int(v)
        except (TypeError, ValueError) as e:
            raise ValueError("{} must be int".format(key)) from e

    cfg = AlertConfig(
        telegram_bot_token=env.get("MIKOV2_ALERT_TELEGRAM_TOKEN", ""),
        telegram_chat_id=env.get("MIKOV2_ALERT_TELEGRAM_CHAT_ID", ""),
        discord_webhook_url=env.get("MIKOV2_ALERT_DISCORD_WEBHOOK", ""),
        rate_limit_s=_int("MIKOV2_ALERT_RATE_LIMIT_S", 30),
        batch_size=_int("MIKOV2_ALERT_BATCH_SIZE", 5),
        batch_window_s=_int("MIKOV2_ALERT_BATCH_WINDOW_S", 5),
        dedup_window_s=_int("MIKOV2_ALERT_DEDUP_WINDOW_S", 60),
        dedup_batch_window_s=_int("MIKOV2_ALERT_DEDUP_BATCH_WINDOW_S", 300),
        pending_max=_int("MIKOV2_ALERT_PENDING_MAX", 100),
        pending_ttl_s=_int("MIKOV2_ALERT_PENDING_TTL_S", 600),
        retry_max=_int("MIKOV2_ALERT_RETRY_MAX", 3),
        breaker_fail_threshold=_int("MIKOV2_ALERT_BREAKER_FAIL_THRESHOLD", 5),
        breaker_open_s=_int("MIKOV2_ALERT_BREAKER_OPEN_S", 60),
    )
    cfg.validate()
    return cfg


class AlertAgent:
    """Config-driven Telegram + Discord alert agent.

    DI: connection ve session dışarıdan gelir (Ş3=Y-353). Sahte
    clock/sleep_fn test amaçlı enjekte edilebilir.
    """

    def __init__(
        self,
        config: AlertConfig,
        conn: sqlite3.Connection,
        session: aiohttp.ClientSession,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleep_fn: Callable[[float], Any] = asyncio.sleep,
    ) -> None:
        config.validate()
        self._cfg = config
        self._conn = conn
        self._session = session
        self._clock = clock
        self._sleep = sleep_fn

        self._critical_queue: deque = deque()
        self._warning_buffer: list = []
        self._batch_start_mono: Optional[float] = None
        self._dedup_index: dict = {}

        self._drain_wake = asyncio.Event()
        self._drain_task: Optional[asyncio.Task] = None
        self._stopped = False

        self._breaker_state: str = _BREAKER_CLOSED
        self._breaker_consecutive_fails: int = 0
        self._breaker_open_until_mono: float = 0.0
        self._half_open_in_flight: bool = False

        self.metrics: dict = {
            "emitted": 0,
            "critical_queued": 0,
            "warning_queued": 0,
            "info_logged": 0,
            "delivered": 0,
            "failed": 0,
            "expired": 0,
            "breaker_open_count": 0,
            "dedup_merged": 0,
        }

    # ------------------------------------------------------------ props

    @property
    def breaker_state(self) -> str:
        return self._breaker_state

    @property
    def config(self) -> AlertConfig:
        return self._cfg

    # ------------------------------------------------------------ lifecycle

    async def start(self) -> None:
        run_migration(self._conn)
        self._startup_expired_sweep()
        self._drain_task = asyncio.create_task(self._drain_loop())

    async def stop(self) -> None:
        self._stopped = True
        self._drain_wake.set()
        if self._drain_task is not None:
            self._drain_task.cancel()
            try:
                await self._drain_task
            except (asyncio.CancelledError, Exception):
                pass
            self._drain_task = None

    # ------------------------------------------------------------ emit

    async def emit(self, event_type: str, payload: dict) -> Optional[int]:
        reason = payload.get("reason") if isinstance(payload, dict) else None
        severity = get_severity(event_type, reason)
        self.metrics["emitted"] += 1

        ts_ms = int(payload.get("ts_ms") or int(time.time() * 1000))

        if severity == SEVERITY_INFO:
            event_id = self._insert_event(
                event_type, severity, payload, ts_ms
            )
            self._update_status(event_id, _STATUS_DELIVERED)
            self.metrics["info_logged"] += 1
            logger.info("alert.info event_type=%s", event_type)
            return event_id

        if severity == SEVERITY_CRITICAL:
            event_id = self._insert_event(
                event_type, severity, payload, ts_ms
            )
            ev_dict = self._to_event_dict(
                event_type, severity, payload, ts_ms
            )
            self._critical_queue.append((event_id, ev_dict))
            self.metrics["critical_queued"] += 1
            self._drain_wake.set()
            return event_id

        # WARNING
        deduped = self._try_dedup_merge(event_type, payload, ts_ms)
        if deduped is not None:
            self.metrics["dedup_merged"] += 1
            self._drain_wake.set()
            return deduped

        event_id = self._insert_event(event_type, severity, payload, ts_ms)
        ev_dict = self._to_event_dict(event_type, severity, payload, ts_ms)
        self._warning_buffer.append((event_id, ev_dict, 1))
        self._dedup_index[(payload.get("symbol"), event_type)] = (
            event_id, self._clock(), 1
        )
        if self._batch_start_mono is None:
            self._batch_start_mono = self._clock()
        self.metrics["warning_queued"] += 1
        if len(self._warning_buffer) >= self._cfg.batch_size:
            self._drain_wake.set()
        return event_id

    async def send_direct(self, event_type: str, payload: dict) -> None:
        await self.emit(event_type, payload)
        try:
            await self._drain_once()
        except Exception as e:
            logger.warning("send_direct drain failed: %s", e)

    # ------------------------------------------------------------ DB ops

    def _insert_event(
        self, event_type: str, severity: str, payload: dict, ts_ms: int
    ) -> int:
        symbol = payload.get("symbol")
        source = payload.get("source")
        source_seq = payload.get("source_seq")
        corr = payload.get("correlation_id") or "{}:{}".format(
            source or "?", source_seq if source_seq is not None else 0
        )
        cur = self._conn.execute(
            """INSERT INTO alert_events
            (ts_ms, event_type, severity, symbol, payload,
             delivery_status, correlation_id, source_seq, exchange_ts_ms,
             created_at_ms, attempts)
            VALUES (?,?,?,?,?,?,?,?,?,?,0)""",
            (
                int(ts_ms), event_type, severity, symbol,
                _json_safe(payload),
                _STATUS_PENDING, corr, source_seq,
                payload.get("exchange_ts_ms"),
                int(time.time() * 1000),
            ),
        )
        self._conn.commit()
        return int(cur.lastrowid)

    def _update_status(
        self,
        event_id: int,
        status: str,
        attempts_delta: int = 0,
        last_error: Optional[str] = None,
    ) -> int:
        cur = self._conn.execute(
            """UPDATE alert_events
               SET delivery_status=?, attempts=attempts+?,
                   last_error=COALESCE(?, last_error)
             WHERE id=?""",
            (status, int(attempts_delta), last_error, int(event_id)),
        )
        self._conn.commit()
        return cur.rowcount

    def _optimistic_sending(self, event_id: int) -> bool:
        cur = self._conn.execute(
            "UPDATE alert_events SET delivery_status='sending'"
            " WHERE id=? AND delivery_status='pending'",
            (int(event_id),),
        )
        self._conn.commit()
        return cur.rowcount == 1

    def _startup_expired_sweep(self) -> None:
        cutoff_ms = int(time.time() * 1000) - self._cfg.pending_ttl_s * 1000
        try:
            cur = self._conn.execute(
                "UPDATE alert_events SET delivery_status='expired'"
                " WHERE delivery_status='pending' AND ts_ms < ?",
                (cutoff_ms,),
            )
            self._conn.commit()
            if cur.rowcount > 0:
                self.metrics["expired"] += cur.rowcount
                logger.warning(
                    "ALERT_PENDING_EXPIRED_SWEEP count=%d", cur.rowcount
                )
        except sqlite3.Error as e:
            logger.warning("expired sweep failed: %s", e)

    # ------------------------------------------------------------ dedup

    def _try_dedup_merge(
        self, event_type: str, payload: dict, ts_ms: int
    ) -> Optional[int]:
        key = (payload.get("symbol"), event_type)
        entry = self._dedup_index.get(key)
        if entry is None:
            return None
        event_id, last_mono, count = entry
        if self._clock() - last_mono > self._cfg.dedup_window_s:
            return None
        for i, (eid, evd, c) in enumerate(self._warning_buffer):
            if eid == event_id:
                self._warning_buffer[i] = (eid, evd, c + 1)
                self._dedup_index[key] = (
                    event_id, self._clock(), c + 1
                )
                return event_id
        return None

    # ------------------------------------------------------------ drain

    async def _drain_loop(self) -> None:
        while not self._stopped:
            try:
                await asyncio.wait_for(self._drain_wake.wait(), timeout=1.0)
            except asyncio.TimeoutError:
                pass
            self._drain_wake.clear()
            try:
                await self._drain_once()
            except Exception as e:
                logger.warning("drain loop error: %s", e)

    async def _drain_once(self) -> None:
        if self._breaker_state == _BREAKER_OPEN:
            if self._clock() < self._breaker_open_until_mono:
                return
            self._breaker_state = _BREAKER_HALF_OPEN
            self._half_open_in_flight = False

        if self._breaker_state == _BREAKER_HALF_OPEN:
            await self._half_open_test()
            return

        while self._critical_queue:
            event_id, ev_dict = self._critical_queue.popleft()
            if not self._optimistic_sending(event_id):
                continue
            await self._send_alert(event_id, [ev_dict])

        if self._warning_buffer:
            ready = (
                len(self._warning_buffer) >= self._cfg.batch_size
                or (
                    self._batch_start_mono is not None
                    and self._clock() - self._batch_start_mono
                    >= self._cfg.batch_window_s
                )
            )
            if ready:
                await self._flush_warning_batch()

    async def _flush_warning_batch(self) -> None:
        batch = self._warning_buffer[: self._cfg.batch_size]
        self._warning_buffer = self._warning_buffer[self._cfg.batch_size:]
        if not self._warning_buffer:
            self._batch_start_mono = None
        else:
            self._batch_start_mono = self._clock()

        items = [(evd, cnt) for _, evd, cnt in batch]
        ids: list = []
        for event_id, _, _ in batch:
            if self._optimistic_sending(event_id):
                ids.append(event_id)
        if not ids:
            return
        await self._send_alert_batch(ids, items)

    async def _half_open_test(self) -> None:
        # AB4 + AH: en eski pending CRITICAL satırı bul.
        # payload JSON içinden reason çıkarılır (T1 şemasında ayrı kolon yok).
        cur = self._conn.execute(
            "SELECT id, ts_ms, event_type, severity, symbol, payload"
            " FROM alert_events"
            " WHERE delivery_status='pending' AND severity='CRITICAL'"
            " ORDER BY ts_ms ASC LIMIT 1"
        )
        row = cur.fetchone()
        if row is None:
            return
        event_id = int(row[0])
        if not self._optimistic_sending(event_id):
            return
        self._half_open_in_flight = True
        try:
            ev_dict = self._row_to_event_dict(row)
            await self._send_alert(event_id, [ev_dict])
        finally:
            self._half_open_in_flight = False

    # ------------------------------------------------------------ send

    def _to_event_dict(
        self, event_type: str, severity: str, payload: dict, ts_ms: int
    ) -> dict:
        return {
            "event_type": event_type,
            "severity": severity,
            "symbol": payload.get("symbol"),
            "ts_ms": int(payload.get("ts_ms") or ts_ms),
            "reason": payload.get("reason"),
        }

    def _row_to_event_dict(self, row: tuple) -> dict:
        # row: id, ts_ms, event_type, severity, symbol, payload(json)
        reason = None
        raw_payload = row[5]
        if raw_payload:
            try:
                parsed = json.loads(raw_payload)
                if isinstance(parsed, dict):
                    reason = parsed.get("reason")
            except (TypeError, ValueError):
                reason = None
        return {
            "event_type": row[2],
            "severity": row[3],
            "symbol": row[4],
            "ts_ms": int(row[1]),
            "reason": reason,
        }

    async def _send_alert(
        self, event_id: int, ev_dicts: list
    ) -> None:
        ok, final_status, error = await self._attempt_with_retry(ev_dicts)
        if ok:
            self._update_status(event_id, _STATUS_DELIVERED)
            self.metrics["delivered"] += 1
            self._on_success()
        else:
            attempts = self._cfg.retry_max
            self._update_status(
                event_id, _STATUS_FAILED,
                attempts_delta=attempts, last_error=error,
            )
            self.metrics["failed"] += 1
            self._on_final_fail()

    async def _send_alert_batch(
        self, ids: list, items: list
    ) -> None:
        ok, final_status, error = await self._attempt_with_retry_batch(items)
        if ok:
            for event_id in ids:
                self._update_status(event_id, _STATUS_DELIVERED)
            self.metrics["delivered"] += len(ids)
            self._on_success()
        else:
            for event_id in ids:
                self._update_status(
                    event_id, _STATUS_FAILED,
                    attempts_delta=self._cfg.retry_max,
                    last_error=error,
                )
            self.metrics["failed"] += len(ids)
            self._on_final_fail()

    # ------------------------------------------------------------ retry loop

    async def _attempt_with_retry(self, ev_dicts: list):
        return await self._attempt(
            items_single=ev_dicts,
            items_batch=None,
        )

    async def _attempt_with_retry_batch(self, items: list):
        return await self._attempt(
            items_single=None,
            items_batch=items,
        )

    async def _attempt(self, items_single, items_batch):
        parse_mode = "HTML"
        last_status: Optional[int] = None
        last_error: Optional[str] = None

        for _ in range(self._cfg.retry_max):
            ok, status, err, retry_after = await self._post_all(
                items_single, items_batch, parse_mode
            )
            if ok:
                return True, status, None

            last_status, last_error = status, err

            if status == 429 and retry_after is not None:
                await self._sleep(float(retry_after))
                continue

            if status == 400 and parse_mode is not None:
                parse_mode = None
                continue

            continue

        return False, last_status, last_error

    async def _post_all(
        self, items_single, items_batch, parse_mode: Optional[str]
    ):
        if items_single is not None:
            ev = items_single[0]
            tg = render_telegram(
                ev, dup_count=1,
                dup_window_s=self._cfg.dedup_batch_window_s,
            )
            tg_text, tg_pm = tg.text, (tg.parse_mode if parse_mode else None)
            dc_text = render_discord(
                ev, dup_count=1,
                dup_window_s=self._cfg.dedup_batch_window_s,
            )
        else:
            tg = render_telegram_batch(
                items_batch,
                dup_window_s=self._cfg.dedup_batch_window_s,
            )
            tg_text, tg_pm = tg.text, (tg.parse_mode if parse_mode else None)
            dc_text = render_discord_batch(
                items_batch,
                dup_window_s=self._cfg.dedup_batch_window_s,
            )

        if self._cfg.telegram_enabled:
            ok, status, retry_after = await self._post_telegram(
                tg_text, tg_pm
            )
            if not ok:
                return False, status, "telegram status={}".format(status), retry_after

        if self._cfg.discord_enabled:
            ok, status, retry_after = await self._post_discord(dc_text)
            if not ok:
                return False, status, "discord status={}".format(status), retry_after

        return True, 200, None, None

    # ------------------------------------------------------------ channels

    async def _post_telegram(self, text: str, parse_mode: Optional[str]):
        url = (
            "https://api.telegram.org/bot{}/sendMessage"
            .format(self._cfg.telegram_bot_token)
        )
        body: dict = {
            "chat_id": self._cfg.telegram_chat_id,
            "text": text,
            "disable_web_page_preview": True,
        }
        if parse_mode:
            body["parse_mode"] = parse_mode
        try:
            async with self._session.post(
                url, json=body, timeout=5.0
            ) as resp:
                status = int(resp.status)
                retry_after = None
                if status == 429:
                    ra = None
                    try:
                        ra = resp.headers.get("Retry-After")
                    except Exception:
                        ra = None
                    try:
                        retry_after = int(ra) if ra else None
                    except (TypeError, ValueError):
                        retry_after = None
                return (200 <= status < 300, status, retry_after)
        except asyncio.TimeoutError:
            return (False, 0, None)
        except aiohttp.ClientError:
            return (False, 0, None)

    async def _post_discord(self, text: str):
        url = self._cfg.discord_webhook_url
        body = {"content": text}
        try:
            async with self._session.post(
                url, json=body, timeout=5.0
            ) as resp:
                status = int(resp.status)
                retry_after = None
                if status == 429:
                    ra = None
                    try:
                        ra = resp.headers.get("Retry-After")
                    except Exception:
                        ra = None
                    try:
                        retry_after = int(ra) if ra else None
                    except (TypeError, ValueError):
                        retry_after = None
                return (200 <= status < 300, status, retry_after)
        except asyncio.TimeoutError:
            return (False, 0, None)
        except aiohttp.ClientError:
            return (False, 0, None)

    # ------------------------------------------------------------ breaker

    def _on_success(self) -> None:
        self._breaker_consecutive_fails = 0
        if self._breaker_state != _BREAKER_CLOSED:
            self._breaker_state = _BREAKER_CLOSED
            self._half_open_in_flight = False

    def _on_final_fail(self) -> None:
        self._breaker_consecutive_fails += 1
        if (
            self._breaker_state == _BREAKER_HALF_OPEN
            or self._breaker_consecutive_fails
            >= self._cfg.breaker_fail_threshold
        ):
            self._breaker_state = _BREAKER_OPEN
            self._breaker_open_until_mono = (
                self._clock() + self._cfg.breaker_open_s
            )
            self._half_open_in_flight = False
            self.metrics["breaker_open_count"] += 1
            logger.warning(
                "ALERT_BREAKER_OPEN fails=%d open_s=%d",
                self._breaker_consecutive_fails,
                self._cfg.breaker_open_s,
            )