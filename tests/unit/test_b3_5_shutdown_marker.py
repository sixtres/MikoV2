# tests/unit/test_b3_5_shutdown_marker.py
"""B3.5-AD=A clean_shutdown_marker testleri.

Kapsam:
- startup: prev marker log (clean/unclean/unknown) + 'unclean' yaz
- normal cikis: 'clean' yaz
- _conn None: no-op
"""
from __future__ import annotations

from src.observation.state import load_state, update_state


def _make_runner(tmp_path):
    from tests.shadow.runner import ShadowRunner

    runner = ShadowRunner(
        symbols=["BTC_USDT"],
        duration_s=0,
        db_path=tmp_path / "r.sqlite",
    )
    runner._setup_db()
    return runner


def test_startup_writes_unclean_marker(tmp_path):
    runner = _make_runner(tmp_path)
    runner._sync_observation_state_on_startup()
    st = load_state(runner._conn)
    assert st.clean_shutdown_marker == "unclean"
    assert st.clean_shutdown_marker_ms > 0
    runner._conn.close()


def test_startup_reads_prev_clean_then_writes_unclean(tmp_path):
    runner = _make_runner(tmp_path)
    # Onceki "clean" kapanis simule et
    update_state(
        runner._conn,
        clean_shutdown_marker="clean",
        clean_shutdown_marker_ms=12345,
    )
    runner._sync_observation_state_on_startup()
    st = load_state(runner._conn)
    # Simdi 'unclean' olmali (bu surec calisiyor)
    assert st.clean_shutdown_marker == "unclean"
    assert st.clean_shutdown_marker_ms > 12345
    runner._conn.close()


def test_startup_reads_prev_unclean(tmp_path):
    runner = _make_runner(tmp_path)
    update_state(
        runner._conn,
        clean_shutdown_marker="unclean",
        clean_shutdown_marker_ms=12345,
    )
    runner._sync_observation_state_on_startup()
    st = load_state(runner._conn)
    assert st.clean_shutdown_marker == "unclean"
    runner._conn.close()


def test_mark_clean_shutdown(tmp_path):
    runner = _make_runner(tmp_path)
    runner._sync_observation_state_on_startup()
    runner._mark_clean_shutdown()
    st = load_state(runner._conn)
    assert st.clean_shutdown_marker == "clean"
    assert st.clean_shutdown_marker_ms > 0
    runner._conn.close()


def test_mark_clean_no_conn(tmp_path):
    runner = _make_runner(tmp_path)
    runner._conn.close()
    runner._conn = None
    # no-op, exception yok
    runner._mark_clean_shutdown()


def test_sync_reads_observation_stop_flag(tmp_path):
    runner = _make_runner(tmp_path)
    update_state(runner._conn, observation_stop=1)
    runner._sync_observation_state_on_startup()
    assert runner._observation_stopped is True
    runner._conn.close()