from decimal import Decimal

import pytest

from src.backtest.fill_model import (
    FillModel,
    FillModelConfig,
    FillResult,
    FillStatus,
)


def _make_model(**kwargs):
    cfg = FillModelConfig(**kwargs)
    return FillModel(cfg), cfg


def test_config_defaults():
    cfg = FillModelConfig()
    assert cfg.fee_taker == 0.0002
    assert cfg.fee_maker == 0.0
    assert cfg.fee_fallback == 0.0003
    assert cfg.leverage == 5
    assert cfg.latency_mean_ms == 100.0
    assert cfg.latency_std_ms == 50.0
    assert cfg.sealed_ttl_ms == 300000
    assert cfg.rr_min == 1.4999
    assert cfg.depth_levels == 10


def test_slippage_pct_5x():
    _, cfg = _make_model(leverage=5)
    assert abs(cfg.slippage_pct - 0.02) < 1e-9


def test_slippage_pct_20x():
    _, cfg = _make_model(leverage=20)
    assert abs(cfg.slippage_pct - 0.005) < 1e-9


def test_slippage_pct_30x():
    _, cfg = _make_model(leverage=30)
    assert abs(cfg.slippage_pct - 0.10 / 30) < 1e-9


def test_slippage_pct_3x_ceiling():
    _, cfg = _make_model(leverage=3)
    assert abs(cfg.slippage_pct - 0.03) < 1e-9


def test_compute_fill_full():
    model, _ = _make_model(leverage=5)
    depth = [(Decimal("100"), Decimal("1")), (Decimal("101"), Decimal("1"))]
    result = model.compute_fill("buy", Decimal("2"), Decimal("100"), depth)
    assert result.status == FillStatus.FILLED
    assert result.filled_qty == Decimal("2")
    assert result.fee > Decimal("0")


def test_compute_fill_partial_closed():
    model, _ = _make_model()
    depth = [(Decimal("100"), Decimal("0.5"))]
    result = model.compute_fill("buy", Decimal("2"), Decimal("100"), depth)
    assert result.status == FillStatus.PARTIAL_CLOSED
    assert result.filled_qty == Decimal("0.5")


def test_compute_fill_empty_depth_rejected():
    model, _ = _make_model()
    result = model.compute_fill("buy", Decimal("1"), Decimal("100"), [])
    assert result.status == FillStatus.REJECTED
    assert result.reason == "EMPTY_DEPTH"


def test_compute_fill_zero_qty_rejected():
    model, _ = _make_model()
    depth = [(Decimal("100"), Decimal("1"))]
    result = model.compute_fill("buy", Decimal("0"), Decimal("100"), depth)
    assert result.status == FillStatus.REJECTED
    assert result.reason == "ZERO_QTY"


def test_check_rr_pass():
    model, _ = _make_model()
    entry = Decimal("100")
    tp = Decimal("103")
    sl = Decimal("99")
    ft = Decimal("0.0002")
    fm = Decimal("0.0")
    passes, rr = model.check_rr(entry, tp, sl, ft, fm)
    assert passes is True
    assert rr >= Decimal("1.4999")


def test_check_rr_fail():
    model, _ = _make_model()
    entry = Decimal("100")
    tp = Decimal("100.5")
    sl = Decimal("99.5")
    ft = Decimal("0.0002")
    fm = Decimal("0.0")
    passes, rr = model.check_rr(entry, tp, sl, ft, fm)
    assert passes is False


def test_check_rr_short():
    model, _ = _make_model()
    entry = Decimal("100")
    tp = Decimal("97")
    sl = Decimal("101")
    ft = Decimal("0.0002")
    fm = Decimal("0.0")
    passes, rr = model.check_rr(entry, tp, sl, ft, fm)
    assert passes is True


def test_apply_slippage_buy_up():
    model, cfg = _make_model(leverage=5)
    result = model.apply_slippage(Decimal("100"), "buy")
    assert result > Decimal("100")


def test_apply_slippage_sell_down():
    model, cfg = _make_model(leverage=5)
    result = model.apply_slippage(Decimal("100"), "sell")
    assert result < Decimal("100")


def test_sample_latency_non_negative():
    model, _ = _make_model()
    for _ in range(20):
        lat = model.sample_latency()
        assert isinstance(lat, int)
        assert lat >= 0


def test_is_sealed_expired_true():
    model, cfg = _make_model(sealed_ttl_ms=300000)
    assert model.is_sealed_expired(1000, 1000 + 400000) is True


def test_is_sealed_expired_false():
    model, cfg = _make_model(sealed_ttl_ms=300000)
    assert model.is_sealed_expired(1000, 1000 + 100000) is False


def test_no_global_state():
    assert not hasattr(FillModel, "_config")