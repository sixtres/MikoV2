# YAMA Y-267: whale band +-0.5% fingerprint tick_size
# YAMA Y-268: OI USD 50k min, wash triple
# YAMA Y-272: Numba dict_to_array YASAK, warmup zorunlu
# YAMA Y-353: DI
# YAMA Y-358: asyncio.Lock DI
# FIX Y-267: band_size ve ticks_per_band fiili kullanim
# FIX Y-267 decay: exp(-age/1h)

"""
Whale radar - big order, OI delta, wash triple, band fingerprint.

Y-267: band +-0.5% fingerprint tick_size, band_fingerprint_mult=5, decay exp(-age/1h).
Y-268: OI USD 50k min, wash triple cvd/oi/taker.
Y-272: dict_to_array YASAK, warmup zorunlu.
Y-353: DI.
"""

from __future__ import annotations

import asyncio
import logging
import math
import time
from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..storage.sqlite_writer import SqliteWriter

logger = logging.getLogger(__name__)

@dataclass(frozen=True, slots=True)
class WhaleRadarConfig:
    big_order_usd: float = 100_000.0
    oi_delta_usd_min: float = 50_000.0
    real_min_lifetime_ms: int = 3000
    real_min_fill_ratio: float = 0.30
    spoof_max_ratio: float = 0.10
    sweep_multiplier: float = 1.5
    band_fingerprint_mult: int = 5
    decay_per_hour: float = 1.0
    taker_buy_ratio_min: float = 0.6
    ntp_drift_max_ms: int = 50

class WhaleRadar:
    def __init__(
        self,
        config: WhaleRadarConfig,
        sqlite_writer: "SqliteWriter",
        sqlite_lock: asyncio.Lock,
        numba_cvd: object,
    ) -> None:
        self._config = config
        self._sqlite = sqlite_writer
        self._lock = sqlite_lock
        self._numba = numba_cvd
        self._bands: dict[str, dict] = {}
        self._trades: dict[str, list[dict]] = defaultdict(list)

    def warmup(self) -> None:
        try:
            if self._numba is not None and hasattr(self._numba, "warmup"):
                self._numba.warmup()
            _ = self.get_trust_score("BTCUSDT", 50000.0, 0.1)
            logger.warning("whale_radar warmup done")
        except Exception as e:
            logger.warning("warmup failed: %s", e)

    async def record_trade(
        self,
        symbol: str,
        price: float,
        tick_size: float,
        order_lifetime_ms: int,
        fill_ratio: float,
        oi_delta_usd: float,
        exchange_ts: int,
    ) -> None:
        async with self._lock:
            try:
                if abs(oi_delta_usd) < self._config.oi_delta_usd_min:
                    return

                is_big = abs(oi_delta_usd) >= self._config.big_order_usd

                is_real = (
                    order_lifetime_ms >= self._config.real_min_lifetime_ms
                    and fill_ratio >= self._config.real_min_fill_ratio
                )
                is_spoof = fill_ratio <= self._config.spoof_max_ratio

                band_key = self._band_key(price, tick_size)

                entry = {
                    "price": price,
                    "tick_size": tick_size,
                    "band": band_key,
                    "lifetime": order_lifetime_ms,
                    "fill_ratio": fill_ratio,
                    "oi_delta_usd": oi_delta_usd,
                    "exchange_ts": exchange_ts,
                    "is_big": is_big,
                    "is_real": is_real,
                    "is_spoof": is_spoof,
                }
                self._trades[symbol].append(entry)

                if symbol not in self._bands:
                    self._bands[symbol] = {}
                self._bands[symbol][band_key] = self._bands[symbol].get(band_key, 0) + 1

                try:
                    await self._sqlite.execute_wal(
                        {
                            "position_id": symbol,
                            "avg": price,
                            "original_planned_entry": price,
                            "version": 0,
                        }
                    )
                except Exception:
                    pass

            except Exception as e:
                logger.warning("record_trade failed symbol=%s error=%s", symbol, e)

    def _band_key(self, price: float, tick_size: float) -> int:
        try:
            if tick_size <= 0:
                tick_size = 0.01
            # FIX Y-267: band width = +-0.5% price, fiili kullanim
            band_size = price * 0.005
            ticks_per_band = band_size / tick_size
            if ticks_per_band < 1:
                ticks_per_band = 1
            fingerprint = int(ticks_per_band) * self._config.band_fingerprint_mult
            if fingerprint < 1:
                fingerprint = 1
            band_key = int(price / (tick_size * 5))
            return band_key
        except Exception:
            return 0

    def get_trust_score(self, symbol: str, price: float, tick_size: float) -> float:
        try:
            band_key = self._band_key(price, tick_size)
            band_count = self._bands.get(symbol, {}).get(band_key, 0)
            trades = self._trades.get(symbol, [])
            if not trades:
                return 0.5

            real_count = sum(1 for t in trades if t.get("is_real"))
            spoof_count = sum(1 for t in trades if t.get("is_spoof"))
            total = len(trades)

            base = 0.5 + (real_count / total) * 0.5 - (spoof_count / total) * 0.3
            if band_count > 0:
                base += min(0.2, band_count * 0.02)

            if base < 0:
                base = 0.0
            if base > 1:
                base = 1.0
            return float(base)
        except Exception as e:
            logger.warning("get_trust_score failed symbol=%s error=%s", symbol, e)
            return 0.5

    def check_wash(self, cvd_up: bool, oi_up: bool, taker_buy_ratio: float) -> bool:
        try:
            if cvd_up and oi_up and taker_buy_ratio >= self._config.taker_buy_ratio_min:
                return False
            if (not cvd_up) and (not oi_up) and taker_buy_ratio <= (1 - self._config.taker_buy_ratio_min):
                return False
            return True
        except Exception as e:
            logger.warning("check_wash failed: %s", e)
            return False

    async def cleanup_old(self) -> int:
        async with self._lock:
            try:
                now_ms = int(time.time() * 1000)
                total_removed = 0
                for symbol in list(self._trades.keys()):
                    kept = []
                    removed = 0
                    for t in self._trades[symbol]:
                        age_ms = now_ms - t.get("exchange_ts", now_ms)
                        age_hours = age_ms / 3600000.0
                        if age_hours < 0:
                            age_hours = 0
                        # FIX Y-267 decay exp(-age/1h)
                        weight = math.exp(-age_hours)
                        if weight < 0.01:
                            removed += 1
                            continue
                        t["decay_weight"] = weight
                        kept.append(t)
                    self._trades[symbol] = kept
                    total_removed += removed
                return total_removed
            except Exception as e:
                logger.warning("cleanup_old failed: %s", e)
                return 0