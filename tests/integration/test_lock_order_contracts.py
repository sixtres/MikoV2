"""
Lock order contracts for critical runtime paths.
AnaYasa Y-339, Y-350: her kritik kod yolu dogru sirada lock almali.

Bu test, runtime'da lock alan modulleri icin sozlesme dogrular.
Her path icin beklenen sira tanimli, validate_lock_order ile kontrol.
"""

import pytest

from src.utils.locks import LOCK_HIERARCHY, SEALED_LOCK_NAME, validate_lock_order


def _check_path(acquired_sequence):
    """
    acquired_sequence: sirali lock isimleri.
    Adim adim validate_lock_order cagirir, ters sira varsa RuntimeError.
    """
    acquired = []
    for name in acquired_sequence:
        validate_lock_order(acquired, name)
        acquired.append(name)
    return True


# === Runtime path contracts (gercek kod yollarina birebir) ===

def test_contract_emergency_close_sqlite_pacer_flush():
    """Y-350: emergency_close sqlite(3)->pacer(4)->flush(5)."""
    assert _check_path(["sqlite_lock", "pacer_lock", "flush_lock"]) is True


def test_contract_emergency_reverse_forbidden():
    """Ters sira deadlock riski: flush once -> sqlite sonra YASAK."""
    with pytest.raises(RuntimeError):
        _check_path(["flush_lock", "sqlite_lock"])


def test_contract_order_manager_fill_then_sqlite():
    """order_manager: fill(2) -> sqlite(3)."""
    assert _check_path(["fill_lock", "sqlite_lock"]) is True


def test_contract_order_manager_reverse_forbidden():
    with pytest.raises(RuntimeError):
        _check_path(["sqlite_lock", "fill_lock"])


def test_contract_l2_buffer_single_lock():
    """L2Buffer: sadece buffer_lock (RLock), tek basina."""
    assert _check_path(["buffer_lock"]) is True
    # buffer_lock sonrasi fill_lock yukari cikiyor, OK
    assert _check_path(["buffer_lock", "fill_lock"]) is True


def test_contract_buffer_after_sqlite_forbidden():
    with pytest.raises(RuntimeError):
        _check_path(["sqlite_lock", "buffer_lock"])


def test_contract_sealed_independent():
    """sealed_lock ayri, main hierarchy ile karismaz."""
    # sealed_lock once veya sonra olabilir
    assert _check_path(["sealed_lock"]) is True
    assert _check_path([SEALED_LOCK_NAME, "buffer_lock"]) is True
    assert _check_path(["fill_lock", SEALED_LOCK_NAME]) is True
    assert _check_path(["sqlite_lock", SEALED_LOCK_NAME, "pacer_lock"]) is True


def test_contract_full_ascending_path():
    """Tum hierarchy yukari yonde."""
    assert _check_path(list(LOCK_HIERARCHY)) is True


def test_contract_any_descending_forbidden():
    """Herhangi bir descending cift yasak."""
    hierarchy = list(LOCK_HIERARCHY)
    for i, higher in enumerate(hierarchy):
        for lower in hierarchy[:i]:
            with pytest.raises(RuntimeError):
                _check_path([higher, lower])


def test_contract_duplicate_same_level_forbidden():
    """Ayni seviye iki kez alinamaz (deadlock riski)."""
    with pytest.raises(RuntimeError):
        _check_path(["buffer_lock", "buffer_lock"])


def test_contract_unknown_lock_rejected():
    with pytest.raises(ValueError):
        _check_path(["buffer_lock", "not_a_real_lock"])


def test_contract_emergency_uses_sealed_at_end():
    """emergency: sqlite->pacer->flush ve sonra sealed yazma."""
    # sealed_lock bagimsiz, herhangi bir anda OK
    assert _check_path(["sqlite_lock", "pacer_lock", "flush_lock", SEALED_LOCK_NAME]) is True


def test_contract_ws_manager_only_uses_fill_chain():
    """
    WS process: data_layer + ws_manager. Sadece buffer + fill zinciri.
    pacer/flush/sqlite bu process'te yok (REST gateway'de).
    """
    # Simulated path: buffer -> fill (WS local)
    assert _check_path(["buffer_lock", "fill_lock"]) is True


def test_contract_rest_gateway_chain():
    """
    REST gateway: sqlite -> pacer -> flush zinciri.
    buffer/fill bu process'te yok.
    """
    assert _check_path(["sqlite_lock", "pacer_lock", "flush_lock"]) is True


def test_contract_no_reverse_between_process_boundary_locks():
    """
    WS process buffer(1) alir, REST gateway sqlite(3) alir.
    Cross-process ayni thread'de olmadigi icin deadlock yok.
    Ama tek process test ortaminda ikisi de alinirsa ascending olmali.
    """
    # If both processes merged for test: buffer -> fill -> sqlite -> pacer -> flush
    assert _check_path(
        ["buffer_lock", "fill_lock", "sqlite_lock", "pacer_lock", "flush_lock"]
    ) is True


def test_contract_six_levels_complete():
    assert len(LOCK_HIERARCHY) == 6
    assert LOCK_HIERARCHY == (
        "buffer_lock",
        "fill_lock",
        "sqlite_lock",
        "pacer_lock",
        "flush_lock",
        "telemetry_lock",
    )


def test_contract_sealed_not_in_main_hierarchy():
    assert SEALED_LOCK_NAME not in LOCK_HIERARCHY
    assert SEALED_LOCK_NAME == "sealed_lock"


def test_no_global_state():
    import src.utils.locks as mod

    for name in dir(mod):
        if name.startswith("__"):
            continue
        obj = getattr(mod, name)
        from src.utils.locks import HierarchicalLock

        if isinstance(obj, HierarchicalLock):
            raise AssertionError("global HierarchicalLock: %s" % name)