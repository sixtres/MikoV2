# MEXC Futures REST client (public market data, no auth).
# Endpoints:
#   GET /api/v1/contract/depth/{symbol}?limit=1000
#   GET /api/v1/contract/depth_commits/{symbol}/{limit}
# Symbol format: BTC_USDT (underscore).
# Rate limit: 20 req/s per IP.

"""
MEXC Futures REST client - snapshot + gap recovery commits.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

MEXC_REST_BASE = "https://api.mexc.com"
DEFAULT_TIMEOUT_S = 3.5
MAX_DEPTH_LIMIT = 1000
MAX_COMMITS_LIMIT = 1000


class MEXCRestError(Exception):
    """Raised when MEXC REST returns non-success or unexpected shape."""


class MEXCRestClient:
    """
    Minimal MEXC Futures REST client.

    session: injected aiohttp.ClientSession
    """

    def __init__(
        self,
        session: Any,
        base_url: str = MEXC_REST_BASE,
        timeout_s: float = DEFAULT_TIMEOUT_S,
    ) -> None:
        self.session = session
        self.base_url = base_url
        self.timeout_s = timeout_s

    async def _get_json(self, path: str, params: dict | None = None) -> dict:
        import asyncio

        url = self.base_url + path
        try:
            async with self.session.get(
                url, params=params, timeout=self.timeout_s
            ) as resp:
                if resp.status != 200:
                    raise MEXCRestError(
                        "HTTP %s on %s" % (resp.status, url)
                    )
                payload = await resp.json()
        except MEXCRestError:
            raise
        except asyncio.TimeoutError as e:
            raise MEXCRestError("timeout on %s" % url) from e
        except Exception as e:
            raise MEXCRestError("request failed %s: %s" % (url, e)) from e

        if not isinstance(payload, dict):
            raise MEXCRestError("non-dict payload from %s" % url)
        if not payload.get("success", False):
            raise MEXCRestError(
                "success=false from %s code=%s" % (url, payload.get("code"))
            )
        return payload

    async def fetch_snapshot(
        self, symbol: str, limit: int = MAX_DEPTH_LIMIT
    ) -> dict:
        """
        Fetch depth snapshot.

        Returns:
            {"bids": [(price, qty), ...], "asks": [(price, qty), ...],
             "version": int, "ts": int}
        """
        if limit > MAX_DEPTH_LIMIT:
            limit = MAX_DEPTH_LIMIT
        path = "/api/v1/contract/depth/%s" % symbol
        payload = await self._get_json(path, params={"limit": limit})
        data = payload.get("data")
        if not isinstance(data, dict):
            raise MEXCRestError("missing data on snapshot %s" % symbol)

        raw_bids = data.get("bids") or []
        raw_asks = data.get("asks") or []
        version = data.get("version")
        ts = data.get("timestamp")

        if version is None:
            raise MEXCRestError("snapshot missing version %s" % symbol)

        return {
            "bids": self._to_pairs(raw_bids),
            "asks": self._to_pairs(raw_asks),
            "version": int(version),
            "ts": int(ts) if ts is not None else 0,
        }

    async def fetch_commits(
        self, symbol: str, limit: int = MAX_COMMITS_LIMIT
    ) -> list[dict]:
        """
        Fetch last N commits for gap recovery.

        Each commit: {"version": int, "cts": int,
                      "bids": [(price, qty), ...], "asks": [...]}
        Ordered by version ascending.
        """
        if limit > MAX_COMMITS_LIMIT:
            limit = MAX_COMMITS_LIMIT
        path = "/api/v1/contract/depth_commits/%s/%d" % (symbol, limit)
        payload = await self._get_json(path)
        data = payload.get("data") or []
        if not isinstance(data, list):
            raise MEXCRestError("commits data not list %s" % symbol)

        out: list[dict] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            version = item.get("version")
            if version is None:
                continue
            try:
                version_int = int(version)
            except (TypeError, ValueError):
                continue
            cts = item.get("cts")
            cts_int = 0
            if cts is not None:
                try:
                    cts_int = int(cts)
                except (TypeError, ValueError):
                    cts_int = 0
            out.append(
                {
                    "version": version_int,
                    "cts": cts_int,
                    "bids": self._to_pairs(item.get("bids") or []),
                    "asks": self._to_pairs(item.get("asks") or []),
                }
            )
        out.sort(key=lambda c: c["version"])
        return out

    @staticmethod
    def _to_pairs(raw: list) -> list[tuple[float, float]]:
        """Convert MEXC [price, vol, count] triples to (price, vol) pairs."""
        out: list[tuple[float, float]] = []
        for row in raw:
            if not isinstance(row, (list, tuple)):
                continue
            if len(row) < 2:
                continue
            try:
                out.append((float(row[0]), float(row[1])))
            except (TypeError, ValueError):
                continue
        return out

    async def fetch_contract_size(self, symbol: str) -> float:
        """
        Fetch contract size (base units per contract) for a symbol.

        Endpoint: GET /api/v1/contract/detail
        Returns float, e.g. 0.0001 for BTC_USDT (1 contract = 0.0001 BTC).
        """
        path = "/api/v1/contract/detail"
        payload = await self._get_json(path)
        data = payload.get("data") or []
        if not isinstance(data, list):
            raise MEXCRestError("contract detail not a list")
        for item in data:
            if not isinstance(item, dict):
                continue
            if item.get("symbol") == symbol:
                cs = item.get("contractSize")
                if cs is None:
                    raise MEXCRestError("no contractSize for %s" % symbol)
                return float(cs)
        raise MEXCRestError("symbol not found in contract detail: %s" % symbol)

    async def fetch_ticker(self, symbol: str) -> dict:
        """
        Fetch ticker for a symbol. Includes OI (holdVol).
        """
        path = "/api/v1/contract/ticker"
        payload = await self._get_json(path, params={"symbol": symbol})
        data = payload.get("data")
        if not isinstance(data, dict):
            raise MEXCRestError("ticker data not dict for %s" % symbol)
        return {
            "symbol": data.get("symbol"),
            "last_price": float(data.get("lastPrice", 0.0)),
            "fair_price": float(data.get("fairPrice", 0.0)),
            "index_price": float(data.get("indexPrice", 0.0)),
            "hold_vol": float(data.get("holdVol", 0.0)),
            "funding_rate": float(data.get("fundingRate", 0.0)),
            "ts_ms": int(data.get("timestamp", 0)),
        }

    async def fetch_funding_rate(self, symbol: str) -> dict:
        """
        Fetch funding rate + next settle time.
        """
        path = "/api/v1/contract/funding_rate/%s" % symbol
        payload = await self._get_json(path)
        data = payload.get("data")
        if not isinstance(data, dict):
            raise MEXCRestError("funding data not dict for %s" % symbol)
        return {
            "symbol": data.get("symbol"),
            "funding_rate": float(data.get("fundingRate", 0.0)),
            "next_settle_ms": int(data.get("nextSettleTime", 0)),
            "collect_cycle_h": int(data.get("collectCycle", 0)),
            "ts_ms": int(data.get("timestamp", 0)),
        }    