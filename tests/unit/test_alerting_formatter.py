# tests/unit/test_alerting_formatter.py
"""B3.4 Mod 2 — formatter testleri (T3)."""
from __future__ import annotations

from src.alerting.formatter import (
    RenderedMessage,
    mask_secrets,
    render_discord,
    render_discord_batch,
    render_telegram,
    render_telegram_batch,
)


def _ev(**over):
    base = {
        "event_type": "TRIGGER",
        "severity": "WARNING",
        "symbol": "BTC_USDT",
        "ts_ms": 1_700_000_000_000,
    }
    base.update(over)
    return base


# ----- mask_secrets

def test_mask_telegram_token():
    s = "auth failed token 123456789:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw"
    out = mask_secrets(s)
    assert "123456789:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw" not in out
    assert "[REDACTED]" in out


def test_mask_discord_webhook():
    s = "post https://discord.com/api/webhooks/123456789/abcdef-XYZ_123"
    out = mask_secrets(s)
    assert "discord.com/api/webhooks" not in out
    assert "[REDACTED]" in out


def test_mask_query_token_keeps_key():
    s = "GET /x?token=secrettoken123&other=ok"
    out = mask_secrets(s)
    assert "secrettoken123" not in out
    assert "token=[REDACTED]" in out
    assert "other=ok" in out


def test_mask_bearer():
    s = "Authorization: Bearer abcdef0123456789ABCDEF"
    out = mask_secrets(s)
    assert "abcdef0123456789ABCDEF" not in out
    assert "[REDACTED]" in out


def test_mask_empty_returns_same():
    assert mask_secrets("") == ""


# ----- render_telegram

def test_render_telegram_basic():
    msg = render_telegram(_ev())
    assert isinstance(msg, RenderedMessage)
    assert msg.parse_mode == "HTML"
    assert "TRIGGER" in msg.text
    assert "BTC_USDT" in msg.text
    assert "[WARNING]" in msg.text
    assert "<b>" in msg.text
    assert "<code>" in msg.text


def test_render_telegram_escapes_html():
    msg = render_telegram(_ev(reason="<script>alert(1)</script>"))
    assert "<script>" not in msg.text
    assert "&lt;script&gt;" in msg.text


def test_render_telegram_dup_suffix():
    msg = render_telegram(_ev(), dup_count=3, dup_window_s=300)
    assert "[x3 son 5dk]" in msg.text


def test_render_telegram_no_suffix_when_window_none():
    msg = render_telegram(_ev(), dup_count=3, dup_window_s=None)
    assert "[x3" not in msg.text


def test_render_telegram_degrade_on_bad_ts():
    msg = render_telegram(_ev(ts_ms="not-an-int"))
    assert msg.parse_mode is None
    assert "<b>" not in msg.text


# ----- render_discord

def test_render_discord_basic():
    text = render_discord(_ev())
    assert isinstance(text, str)
    assert "TRIGGER" in text
    assert "BTC_USDT" in text
    assert "[WARNING]" in text


def test_render_discord_no_html_tags():
    text = render_discord(_ev())
    assert "<b>" not in text
    assert "<code>" not in text


def test_render_discord_dup_suffix():
    text = render_discord(_ev(), dup_count=2, dup_window_s=600)
    assert "[x2 son 10dk]" in text


# ----- batch

def test_batch_telegram_header():
    items = [(_ev(severity="CRITICAL"), 1), (_ev(severity="WARNING"), 1)]
    msg = render_telegram_batch(items)
    assert msg.parse_mode == "HTML"
    assert "N=2" in msg.text
    assert "CRITICAL: 1" in msg.text
    assert "WARNING: 1" in msg.text


def test_batch_telegram_lines_and_dedup():
    items = [
        (_ev(event_type="TRIGGER"), 1),
        (_ev(event_type="ENTRY"), 3),
    ]
    msg = render_telegram_batch(items, dup_window_s=300)
    assert "#1" in msg.text
    assert "#2" in msg.text
    assert "[x3 son 5dk]" in msg.text


def test_batch_discord_plain():
    items = [(_ev(severity="INFO"), 1)]
    text = render_discord_batch(items)
    assert "<b>" not in text
    assert "N=1" in text
    assert "#1" in text


def test_batch_empty():
    tg = render_telegram_batch([])
    assert "N=0" in tg.text
    dc = render_discord_batch([])
    assert "N=0" in dc


# ----- mask applied on output

def test_render_telegram_masks_token_in_reason():
    ev = _ev(reason="auth 123456789:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw")
    msg = render_telegram(ev)
    assert "123456789:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw" not in msg.text
    assert "[REDACTED]" in msg.text