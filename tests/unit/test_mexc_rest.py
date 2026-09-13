"""
Tests for src.data_layer.mexc_rest
No real network. Fake session via async context manager.
"""

import pytest

from src.data_layer.mexc_rest import (
    MAX_COMMITS_LIMIT,
    MAX_DEPTH_LIMIT,
    MEXCRestClient,
    MEXCRestError,
)


class _FakeResponse:
    def __init__(self, status, payload):
        self.status = status
        self._payload = payload

    async def json(self):
        return self._payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _FakeSession:
    def __init__(self, status=200, payload=None):
        self.status = status
        self.payload = payload
        self.last_url = None
        self.last_params = None

    def get(self, url, params=None, timeout=None):
        self.last_url = url
        self.last_params = params
        return _FakeResponse(self.status, self.payload)


def _client(status=200, payload=None):
    sess = _FakeSession(status, payload)
    return MEXCRestClient(sess), sess


def test_defaults():
    c, _ = _client()
    assert c.base_url == "https://api.mexc.com"
    assert c.timeout_s == 3.5


def test_no_global_state():
    assert not hasattr(MEXCRestClient, "_session")


@pytest.mark.asyncio
async def test_fetch_snapshot_happy_path():
    payload = {
        "success": True,
        "code": 0,
        "data": {
            "bids": [[108779.1, 3240, 1], [108779.0, 500, 2]],
            "asks": [[108779.2, 3240, 1]],
            "version": 28111438870,
            "timestamp": 1761879567135,
        },
    }
    c, sess = _client(payload=payload)
    snap = await c.fetch_snapshot("BTC_USDT")
    assert snap["version"] == 28111438870
    assert snap["ts"] == 1761879567135
    assert snap["bids"] == [(108779.1, 3240.0), (108779.0, 500.0)]
    assert snap["asks"] == [(108779.2, 3240.0)]
    assert sess.last_url.endswith("/api/v1/contract/depth/BTC_USDT")
    assert sess.last_params == {"limit": 1000}


@pytest.mark.asyncio
async def test_fetch_snapshot_limit_capped():
    payload = {"success": True, "code": 0, "data": {
        "bids": [], "asks": [], "version": 1, "timestamp": 0}}
    c, sess = _client(payload=payload)
    await c.fetch_snapshot("BTC_USDT", limit=99999)
    assert sess.last_params == {"limit": MAX_DEPTH_LIMIT}


@pytest.mark.asyncio
async def test_fetch_snapshot_missing_version_raises():
    payload = {"success": True, "code": 0, "data": {
        "bids": [], "asks": [], "timestamp": 0}}
    c, _ = _client(payload=payload)
    with pytest.raises(MEXCRestError):
        await c.fetch_snapshot("BTC_USDT")


@pytest.mark.asyncio
async def test_fetch_snapshot_missing_data_raises():
    payload = {"success": True, "code": 0}
    c, _ = _client(payload=payload)
    with pytest.raises(MEXCRestError):
        await c.fetch_snapshot("BTC_USDT")


@pytest.mark.asyncio
async def test_fetch_snapshot_http_error():
    c, _ = _client(status=429, payload={})
    with pytest.raises(MEXCRestError):
        await c.fetch_snapshot("BTC_USDT")


@pytest.mark.asyncio
async def test_fetch_snapshot_success_false():
    payload = {"success": False, "code": 500}
    c, _ = _client(payload=payload)
    with pytest.raises(MEXCRestError):
        await c.fetch_snapshot("BTC_USDT")


@pytest.mark.asyncio
async def test_fetch_commits_happy_path():
    payload = {
        "success": True,
        "code": 0,
        "data": [
            {"version": 100, "cts": 1, "bids": [[1.0, 2.0, 1]], "asks": []},
            {"version": 101, "cts": 2, "bids": [], "asks": [[1.5, 3.0, 1]]},
        ],
    }
    c, sess = _client(payload=payload)
    commits = await c.fetch_commits("BTC_USDT", limit=100)
    assert len(commits) == 2
    assert commits[0]["version"] == 100
    assert commits[1]["version"] == 101
    assert commits[0]["bids"] == [(1.0, 2.0)]
    assert sess.last_url.endswith("/api/v1/contract/depth_commits/BTC_USDT/100")


@pytest.mark.asyncio
async def test_fetch_commits_limit_capped():
    payload = {"success": True, "code": 0, "data": []}
    c, sess = _client(payload=payload)
    await c.fetch_commits("BTC_USDT", limit=99999)
    assert sess.last_url.endswith("/depth_commits/BTC_USDT/%d" % MAX_COMMITS_LIMIT)


@pytest.mark.asyncio
async def test_fetch_commits_sorted_ascending():
    payload = {
        "success": True,
        "code": 0,
        "data": [
            {"version": 105, "cts": 0, "bids": [], "asks": []},
            {"version": 103, "cts": 0, "bids": [], "asks": []},
            {"version": 104, "cts": 0, "bids": [], "asks": []},
        ],
    }
    c, _ = _client(payload=payload)
    commits = await c.fetch_commits("BTC_USDT")
    versions = [c["version"] for c in commits]
    assert versions == [103, 104, 105]


@pytest.mark.asyncio
async def test_fetch_commits_skips_bad_entries():
    payload = {
        "success": True,
        "code": 0,
        "data": [
            {"version": 100, "bids": [[1.0, 2.0, 1]], "asks": []},
            "not a dict",
            {"cts": 1},  # no version
            {"version": 101, "bids": [[1.5, 3.0, 1]], "asks": []},
        ],
    }
    c, _ = _client(payload=payload)
    commits = await c.fetch_commits("BTC_USDT")
    assert [c["version"] for c in commits] == [100, 101]


def test_to_pairs_handles_triples():
    pairs = MEXCRestClient._to_pairs([[1.0, 2.0, 3], [4.5, 5.5, 1]])
    assert pairs == [(1.0, 2.0), (4.5, 5.5)]


def test_to_pairs_skips_short_rows():
    pairs = MEXCRestClient._to_pairs([[1.0], [2.0, 3.0, 4], "x"])
    assert pairs == [(2.0, 3.0)]


def test_to_pairs_skips_bad_floats():
    pairs = MEXCRestClient._to_pairs([["bad", 1.0], [1.0, "bad"], [2.0, 3.0]])
    assert pairs == [(2.0, 3.0)]