# src/alerting/formatter.py
"""B3.4 Mod 2 — Telegram HTML + Discord plain text formatter.

Kısıtlar (DURUM §11 B3.4):
- N=(B): Telegram HTML + Discord plain text
- W=(B): Telegram HTML (html.escape zorunlu; sınırlı tag seti b/i/code/pre/a;
  bu modül yalnız b ve code üretir)
- Secret-mask zorunlu; tek nokta bu modül (tüm çıkışlar geçer)
- parse/format exception → parse_mode=None degrade (ulaşma > şıklık)
- TR dil
- Batch: header + her event 1 satır + AA dedup "xN son Wdk"

Stateless; global yok (Y-353). DI gerekmez.
"""
from __future__ import annotations

import html
import re
import time
from dataclasses import dataclass
from typing import Final, Sequence

_REDACTED: Final[str] = "[REDACTED]"

_DISCORD_WEBHOOK_RE: Final = re.compile(
    r"https://(?:ptb\.|canary\.)?discord(?:app)?\.com"
    r"/api/webhooks/\d+/[A-Za-z0-9_\-]+"
)
_TELEGRAM_TOKEN_RE: Final = re.compile(r"\b\d{6,}:[A-Za-z0-9_\-]{30,}\b")
_QUERY_TOKEN_RE: Final = re.compile(
    r"([?&](?:token|access_token|api_key|apikey)=)[^&\s\"'<>]+",
    re.IGNORECASE,
)
_BEARER_RE: Final = re.compile(
    r"\b(?:bearer|bot)\s+[A-Za-z0-9_\-\.]{20,}", re.IGNORECASE
)

_SECRET_PATTERNS: Final[tuple] = (
    _DISCORD_WEBHOOK_RE,
    _TELEGRAM_TOKEN_RE,
    _QUERY_TOKEN_RE,
    _BEARER_RE,
)

_TELEGRAM_PARSE_MODE: Final[str] = "HTML"
_SEVERITY_ORDER: Final[tuple] = ("CRITICAL", "WARNING", "INFO")


def _sub_mask(m: "re.Match") -> str:
    if m.re is _QUERY_TOKEN_RE:
        return m.group(1) + _REDACTED
    return _REDACTED


def mask_secrets(text: str) -> str:
    """Tek nokta secret maskeleme; tüm formatter çıkışından geçer."""
    if not text:
        return text
    out = text
    for pat in _SECRET_PATTERNS:
        out = pat.sub(_sub_mask, out)
    return out


@dataclass(frozen=True, slots=True)
class RenderedMessage:
    """Telegram için metin + parse_mode; degrade durumunda parse_mode None."""
    text: str
    parse_mode: str | None


def _fmt_time(ts_ms: int) -> str:
    return time.strftime("%H:%M:%S", time.gmtime(int(ts_ms) / 1000.0))


def _dup_suffix(dup_count: int, window_s: int | None) -> str:
    if dup_count is None or dup_count <= 1 or window_s is None:
        return ""
    w_min = max(1, int(window_s) // 60)
    return " [x{} son {}dk]".format(int(dup_count), w_min)


def _event_parts(ev: dict) -> tuple:
    event_type = str(ev["event_type"])
    severity = str(ev["severity"])
    symbol = str(ev.get("symbol") or "-")
    ts_ms = int(ev["ts_ms"])
    reason = ev.get("reason")
    reason_s = str(reason) if reason is not None else None
    return event_type, severity, symbol, ts_ms, reason_s


def _render_one_telegram(
    ev: dict, dup_count: int, window_s: int | None
) -> str:
    event_type, severity, symbol, ts_ms, reason_s = _event_parts(ev)
    head = "<b>[{}]</b> {} {}".format(
        html.escape(severity, quote=False),
        html.escape(event_type, quote=False),
        html.escape(symbol, quote=False),
    )
    tm = "<code>{}</code>".format(
        html.escape(_fmt_time(ts_ms), quote=False)
    )
    if reason_s:
        body = "{} {} — {}".format(
            head, tm, html.escape(reason_s, quote=False)
        )
    else:
        body = "{} {}".format(head, tm)
    return body + _dup_suffix(dup_count, window_s)


def _render_one_discord(
    ev: dict, dup_count: int, window_s: int | None
) -> str:
    event_type, severity, symbol, ts_ms, reason_s = _event_parts(ev)
    head = "[{}] {} {}".format(severity, event_type, symbol)
    tm = _fmt_time(ts_ms)
    if reason_s:
        body = "{} {} — {}".format(head, tm, reason_s)
    else:
        body = "{} {}".format(head, tm)
    return body + _dup_suffix(dup_count, window_s)


def render_telegram(
    ev: dict, dup_count: int = 1, dup_window_s: int | None = None
) -> RenderedMessage:
    """Tek event Telegram HTML. Format hatası → düz metin degrade (parse_mode=None)."""
    try:
        text = _render_one_telegram(ev, dup_count, dup_window_s)
        return RenderedMessage(
            text=mask_secrets(text), parse_mode=_TELEGRAM_PARSE_MODE
        )
    except Exception:
        try:
            fallback = _render_one_discord(ev, dup_count, dup_window_s)
        except Exception:
            fallback = "[format error]"
        return RenderedMessage(
            text=mask_secrets(fallback), parse_mode=None
        )


def render_discord(
    ev: dict, dup_count: int = 1, dup_window_s: int | None = None
) -> str:
    """Tek event Discord plain text."""
    try:
        text = _render_one_discord(ev, dup_count, dup_window_s)
    except Exception:
        text = "[format error]"
    return mask_secrets(text)


def _severity_counts(items: Sequence[tuple[dict, int]]) -> list:
    counts: dict = {}
    for ev, _ in items:
        sev = str(ev.get("severity") or "UNKNOWN")
        counts[sev] = counts.get(sev, 0) + 1
    ordered: list = []
    for k in _SEVERITY_ORDER:
        if k in counts:
            ordered.append((k, counts[k]))
    for k, v in counts.items():
        if k not in _SEVERITY_ORDER:
            ordered.append((k, v))
    return ordered


def _batch_header(items: Sequence[tuple[dict, int]]) -> tuple:
    ordered = _severity_counts(items)
    summary = " | ".join("{}: {}".format(k, v) for k, v in ordered)
    header = "MikoV2 Uyarı Grubu (N={})".format(len(items))
    return header, summary


def render_telegram_batch(
    items: Sequence[tuple[dict, int]], dup_window_s: int = 300
) -> RenderedMessage:
    """Batch HTML. Format hatası → plain degrade (parse_mode=None)."""
    try:
        if not items:
            return RenderedMessage(
                text=mask_secrets("MikoV2 Uyarı Grubu (N=0)"),
                parse_mode=_TELEGRAM_PARSE_MODE,
            )
        header, summary = _batch_header(items)
        lines = ["<b>{}</b>".format(html.escape(header, quote=False))]
        if summary:
            lines.append(html.escape(summary, quote=False))
        for i, (ev, cnt) in enumerate(items, 1):
            body = _render_one_telegram(ev, cnt, dup_window_s)
            lines.append("#{} {}".format(i, body))
        text = mask_secrets("\n".join(lines))
        return RenderedMessage(text=text, parse_mode=_TELEGRAM_PARSE_MODE)
    except Exception:
        try:
            plain = render_discord_batch(items, dup_window_s)
        except Exception:
            plain = "MikoV2 Uyarı Grubu (format error)"
        return RenderedMessage(text=mask_secrets(plain), parse_mode=None)


def render_discord_batch(
    items: Sequence[tuple[dict, int]], dup_window_s: int = 300
) -> str:
    """Batch plain text."""
    try:
        if not items:
            return mask_secrets("MikoV2 Uyarı Grubu (N=0)")
        header, summary = _batch_header(items)
        lines = [header]
        if summary:
            lines.append(summary)
        for i, (ev, cnt) in enumerate(items, 1):
            body = _render_one_discord(ev, cnt, dup_window_s)
            lines.append("#{} {}".format(i, body))
        return mask_secrets("\n".join(lines))
    except Exception:
        return mask_secrets("MikoV2 Uyarı Grubu (format error)")