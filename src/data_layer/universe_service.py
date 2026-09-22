# src/data_layer/universe_service.py
# YAMA Y-353: DI, no global
# REV8: universe service - direct fetcher ranking (scanner disabled for now)
# B3.1: RotationDecision + hysteresis + flap (round-trip) + exponential
#       quarantine + stable reset (SORU A=C, B=D, C=A, RR=A; DURUM §11)
#
# Q1=B: flap penceresi 1 saat
# Q2=B: Top5 gir-çık (round-trip) = 1 flap birimi
# Q3=B: 7 gün karantinasız stabilite → quarantine level 1
# Q4=B: seed yalnız süreç başlangıcında; state in-memory, restart'ta sıfırlanır
# Q5=A: watch (top10 - top5) state tutulmaz; yalnız Top5 transition'ları sayılır

"""
Universe service - direct use of BulkMetricsFetcher ranking.
B3.1: Top5 WS aboneliği için rotation manager.

Sorumluluk:
  - scan()                    : mevcut Top5/Top10/Top20 üretir (fetcher)
  - seed_subscriptions()      : bootstrap; hysteresis beklemeden ilk kurulum
  - apply_scan(scan, now_ms)  : scan sonucunu rotation state'ine uygular,
                                WS diff kararı döner
  - current_subscriptions()   : mevcut WS abonelik seti (kopya)

Karar kilitleri (DURUM §11):
  A) flap quarantine üstel (1h → 4h → 24h); per-symbol sayaç + son_ceza_süresi
  B) scan 30s / WS rotasyon 5dk (iki timer runner tarafında)
  C) hysteresis (zaman) ve flap (sayı) AYRI state
  RR) Top5 WS + Top10 watch

Q1–Q5 alt parametreler (dış-ajan sentezi onaylı):
  Q1=B  flap penceresi 1 saat
  Q2=B  round-trip = 1 flap birimi (tek yönlü giriş sayılmaz)
  Q3=B  7 gün karantinasız stabilite → level 1
  Q4=B  seed yalnız süreç başlangıcında; state in-memory
        (restart affı flap penceresi ile kendini düzeltir)
  Q5=A  watch state tutulmaz; yalnız Top5 transition'ları sayılır

Not: apply_scan sync — I/O yok, sadece state mutasyonu ve karar üretimi.
WS subscribe/unsubscribe çağrıları runner tarafındadır.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Iterable

from .constants import EXCLUDED_SYMBOLS
from .metrics_fetcher import BulkMetricsFetcher, FetcherConfig, RankedSymbol

if TYPE_CHECKING:
    from .mexc_rest import MEXCRestClient

logger = logging.getLogger(__name__)


# B3.1 kilitli varsayılanlar
DEFAULT_HYSTERESIS_MS = 300_000                       # 5 dk
DEFAULT_FLAP_THRESHOLD = 3                            # flap 3
DEFAULT_FLAP_WINDOW_MS = 3_600_000                    # Q1=B: 1 saat
DEFAULT_QUARANTINE_RESET_STABLE_MS = 604_800_000      # Q3=B: 7 gün
DEFAULT_QUARANTINE_STEPS_MS = (                       # SORU A: üstel 1h→4h→24h
    3_600_000,      # 1h
    14_400_000,     # 4h
    86_400_000,     # 24h
)


@dataclass(frozen=True, slots=True)
class ScanResult:
    top5: list[str]
    top10: list[str]
    top20: list[str]
    ranked: list[RankedSymbol]
    excluded_symbols: list[str]


@dataclass(frozen=True, slots=True)
class RotationDecision:
    """
    B3.1: UniverseService.apply_scan() çıktısı.

    to_subscribe / to_unsubscribe: runner'ın WS client'ına uygulayacağı diff.
    watch_symbols: Top10 - Top5; runner bunları REST ticker ile poll eder (SORU D=A).
    quarantined: o an aktif karantinada olan semboller (bilgi amaçlı).
    subscribed_after: karar sonrası tam WS abonelik seti (kopya).
    scan_ms: kararın uygulandığı zaman (state machine ile uyumlu).
    """
    to_subscribe: tuple[str, ...]
    to_unsubscribe: tuple[str, ...]
    watch_symbols: tuple[str, ...]
    quarantined: tuple[str, ...]
    scan_ms: int
    subscribed_after: tuple[str, ...]


class UniverseService:
    def __init__(
        self,
        rest: "MEXCRestClient",
        fetcher_config: FetcherConfig,
        contract_sizes: dict[str, float],
        always_include: tuple[str, ...] = ("BTC_USDT",),
        excluded_symbols: frozenset[str] = EXCLUDED_SYMBOLS,
        hysteresis_ms: int = DEFAULT_HYSTERESIS_MS,
        flap_threshold: int = DEFAULT_FLAP_THRESHOLD,
        flap_window_ms: int = DEFAULT_FLAP_WINDOW_MS,
        quarantine_steps_ms: tuple[int, ...] = DEFAULT_QUARANTINE_STEPS_MS,
        quarantine_reset_stable_ms: int = DEFAULT_QUARANTINE_RESET_STABLE_MS,
    ) -> None:
        # §6.2: exclude -- always_include ile cakisirsa exclude kazanir
        safe_always = tuple(s for s in always_include if s not in excluded_symbols)
        if len(safe_always) != len(always_include):
            dropped = sorted(set(always_include) - set(safe_always))
            logger.warning("EXCLUDED_SYMBOL_IN_ALWAYS_INCLUDE symbols=%s", dropped)

        self._fetcher = BulkMetricsFetcher(
            rest,
            fetcher_config,
            contract_sizes,
            excluded_symbols=excluded_symbols,
        )
        self._always = safe_always
        self._excluded = excluded_symbols
        self._last_result: ScanResult | None = None

        # --- B3.1 rotation config ---
        self._hysteresis_ms = hysteresis_ms
        self._flap_threshold = flap_threshold
        self._flap_window_ms = flap_window_ms
        if not quarantine_steps_ms:
            raise ValueError("quarantine_steps_ms must not be empty")
        self._quarantine_steps_ms = tuple(quarantine_steps_ms)
        self._quarantine_reset_stable_ms = quarantine_reset_stable_ms

        # --- B3.1 rotation state ---
        # SORU C=A: hysteresis (zaman state) ve flap (sayı state) AYRI dict'lerde.
        #   Farklı sorgu desenleri; birleştirme yanlış poz/neg üretir.

        # hysteresis (zaman):
        self._subscribed: set[str] = set()
        self._pending_target: dict[str, bool] = {}
        self._pending_since_ms: dict[str, int] = {}

        # flap (sayı) — Q2=B round-trip
        self._last_target_state: dict[str, bool] = {}
        self._flap_window_start_ms: dict[str, int] = {}
        self._flap_count: dict[str, int] = {}

        # quarantine (üstel ceza):
        self._quarantine_until_ms: dict[str, int] = {}
        self._quarantine_level: dict[str, int] = {}

    # ------------------------------------------------------------ fetcher

    async def scan(self) -> ScanResult:
        ranked = await self._fetcher.fetch_and_rank()
        ordered: list[str] = list(self._always)
        for r in ranked:
            if r.symbol not in ordered:
                ordered.append(r.symbol)

        top5 = ordered[:5]
        top10 = ordered[:10]
        top20 = ordered[:20]

        result = ScanResult(
            top5=top5,
            top10=top10,
            top20=top20,
            ranked=ranked,
            excluded_symbols=sorted(self._excluded),
        )
        self._last_result = result
        return result

    @property
    def last_result(self) -> ScanResult | None:
        return self._last_result

    # ------------------------------------------------------------ B3.1 rotation

    def seed_subscriptions(self, symbols: Iterable[str]) -> None:
        """
        Bootstrap: ilk taramada WS aboneliğini hysteresis beklemeden kur.

        Q4=B: Yalnız süreç başlangıcında çağrılır. Sonraki tüm rotasyon
        apply_scan() ile. Aynı süreç içinde WS reconnect olduğunda bile
        seed TEKRAR çağrılmaz; mevcut _subscribed set'i korunur.

        Excluded semboller yine de filtrelenir (§6.2 belt-and-suspenders).
        """
        added: list[str] = []
        for s in symbols:
            if s in self._excluded:
                continue
            if s not in self._subscribed:
                self._subscribed.add(s)
                added.append(s)
        if added:
            logger.warning("B3_1_SEED_SUBSCRIPTIONS symbols=%s", added)

    def apply_scan(self, scan: ScanResult, now_ms: int) -> RotationDecision:
        """
        Scan sonucunu rotation state'ine uygula; WS diff kararını döndür.

        Kurallar:
          - Hysteresis: pending target en az hysteresis_ms sürmeden flip yok.
            (WS aboneliği Top5 değişimine 5dk gecikme ile uyar.)
          - Flap (Q2=B): Top5 gir-çık (round-trip) = 1 flap birimi.
            Pencere (Q1=B, 1h) içinde threshold (3) aşılırsa anında
            quarantine (üstel: 1h → 4h → 24h, SORU A).
          - Karantina aktifken subscribe denenmez; pending kalır, sonraki
            scan'de karantina dolmuşsa tekrar denenir.
          - Karantina seviyesi (Q3=B): karantina bitiminden 7 gün yeni ceza
            almazsa level 1'e döner (fresh start).
          - Excluded semboller rotasyona asla girmez.
          - Watch (top10 - top5) state'e girmez (Q5=A).
        """
        target_top5 = set(scan.top5)
        target_watch = set(scan.top10) - target_top5

        to_sub: list[str] = []
        to_unsub: list[str] = []

        # Q2=B: Top5 gir-çık = 1 flap birimi (round-trip)
        # Q5=A: yalnız Top5 transition'ları; watch state'e girmez
        relevant = set(self._last_target_state.keys()) | target_top5
        for sym in sorted(relevant):
            if sym in self._excluded:
                continue
            prev = self._last_target_state.get(sym)
            curr = sym in target_top5
            if prev is True and curr is False:
                self._record_flap_round_trip(sym, now_ms)
            self._last_target_state[sym] = curr

        # Q3=B: 7 gün karantinasız stabilite → level 1
        for sym in sorted(self._quarantine_level.keys()):
            self._maybe_stable_reset(sym, now_ms)

        # İlgilendiğimiz tüm semboller: abone + hedef + pending
        interested = set(self._subscribed)
        interested |= target_top5
        interested |= set(self._pending_target.keys())
        interested -= self._excluded

        for symbol in sorted(interested):
            current = symbol in self._subscribed
            target = symbol in target_top5

            if current == target:
                # stabil — pending temizle
                self._pending_target.pop(symbol, None)
                self._pending_since_ms.pop(symbol, None)
                continue

            pending = self._pending_target.get(symbol)
            if pending is not target:
                # yeni pending penceresi başladı; hysteresis bekle
                self._pending_target[symbol] = target
                self._pending_since_ms[symbol] = now_ms
                continue

            elapsed = now_ms - self._pending_since_ms[symbol]
            if elapsed < self._hysteresis_ms:
                continue

            # hysteresis doldu — aksiyon zamanı
            if target:
                if self._is_quarantined(symbol, now_ms):
                    # karantina aktif; pending kalsın, sonraki scan'de tekrar
                    continue
                # Q2=B: flap slot tüketimi kaldırıldı; quarantine
                # _record_flap_round_trip içinde anında tetiklenir.
                self._subscribed.add(symbol)
                to_sub.append(symbol)
                logger.warning("B3_1_ROTATION_SUB symbol=%s", symbol)
            else:
                self._subscribed.discard(symbol)
                to_unsub.append(symbol)
                logger.warning("B3_1_ROTATION_UNSUB symbol=%s", symbol)

            # aksiyon sonrası pending temizle
            self._pending_target.pop(symbol, None)
            self._pending_since_ms.pop(symbol, None)

        quarantined = tuple(sorted(
            s for s, until in self._quarantine_until_ms.items()
            if until > now_ms
        ))

        return RotationDecision(
            to_subscribe=tuple(to_sub),
            to_unsubscribe=tuple(to_unsub),
            watch_symbols=tuple(sorted(target_watch)),
            quarantined=quarantined,
            scan_ms=now_ms,
            subscribed_after=tuple(sorted(self._subscribed)),
        )

    def current_subscriptions(self) -> frozenset[str]:
        """Kopya döner; iç state sızdırılmaz."""
        return frozenset(self._subscribed)

    # --- flap / quarantine (sayı state; SORU C=A) ---

    def _record_flap_round_trip(self, symbol: str, now_ms: int) -> None:
        """
        Q2=B: Top5'e giriş-çıkış (round-trip) = 1 flap birimi.
        Tek yönlü giriş sayılmaz; yalnız True → False geçişi.
        Pencere yenilenir; threshold aşılırsa anında quarantine tetiklenir.
        """
        start = self._flap_window_start_ms.get(symbol, 0)
        if start == 0 or now_ms - start > self._flap_window_ms:
            self._flap_window_start_ms[symbol] = now_ms
            self._flap_count[symbol] = 0
        self._flap_count[symbol] = self._flap_count.get(symbol, 0) + 1
        if (self._flap_count[symbol] >= self._flap_threshold
                and not self._is_quarantined(symbol, now_ms)):
            self._enter_quarantine(symbol, now_ms)

    def _is_quarantined(self, symbol: str, now_ms: int) -> bool:
        return self._quarantine_until_ms.get(symbol, 0) > now_ms

    def _enter_quarantine(self, symbol: str, now_ms: int) -> None:
        level = self._quarantine_level.get(symbol, 0)
        idx = min(level, len(self._quarantine_steps_ms) - 1)
        duration = self._quarantine_steps_ms[idx]
        self._quarantine_until_ms[symbol] = now_ms + duration
        self._quarantine_level[symbol] = level + 1
        # flap penceresini sıfırla; karantina sonrası yeniden sayılır
        self._flap_window_start_ms.pop(symbol, None)
        self._flap_count[symbol] = 0
        logger.warning(
            "B3_1_QUARANTINE symbol=%s level=%d duration_ms=%d",
            symbol,
            level,
            duration,
        )

    def _maybe_stable_reset(self, symbol: str, now_ms: int) -> None:
        """
        Q3=B: karantina bitiminden sonra 7 gün yeni ceza almazsa
        level 1'e döner (fresh start). Aksi halde mevcut seviye korunur.
        """
        if self._is_quarantined(symbol, now_ms):
            return
        until = self._quarantine_until_ms.get(symbol, 0)
        if until == 0:
            return
        if now_ms - until < self._quarantine_reset_stable_ms:
            return
        level = self._quarantine_level.get(symbol, 0)
        if level > 1:
            self._quarantine_level[symbol] = 1
            logger.warning("B3_1_QUARANTINE_RESET symbol=%s", symbol)