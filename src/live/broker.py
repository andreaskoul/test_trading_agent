"""Broker adapter layer for Phase K (Tier B: broker-paper).

Design goals
------------
* No hard dependency on a specific vendor SDK. We use the stdlib (urllib)
  to talk to REST endpoints so the codebase stays installable without
  ``alpaca-py``/``alpaca-trade-api``.
* A small ``BrokerAdapter`` Protocol abstracts the four operations the
  paper engine needs: ``submit_order``, ``cancel_order``, ``get_position``,
  ``get_account``.
* ``AlpacaBroker`` is a thin REST client against the Alpaca paper-trading
  endpoint (https://paper-api.alpaca.markets). It uses idempotency keys so
  retried orders cannot double-fill.
* ``MockBroker`` is an in-memory stub used by tests and as a safe default
  when no API credentials are configured.
* ``submit_order_with_retry`` adds exponential backoff on transient
  errors (network timeout, 429, 5xx).
* ``reconcile_positions`` is the startup hook: it compares the local
  ``TradeStore`` open position (one per asset) against the broker's view
  and returns a list of mismatches the operator must resolve.

The cockpit imports the adapter only if ``ui.broker.enabled: true`` in
the YAML config. Replay/paper-only mode never instantiates a broker.
"""

from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from threading import Lock
from typing import Optional, Protocol

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class OrderRequest:
    """One order to submit to the broker."""

    symbol: str
    qty: float
    side: str               # "buy" | "sell"
    order_type: str = "market"
    time_in_force: str = "day"
    client_order_id: Optional[str] = None    # idempotency key

    def __post_init__(self) -> None:
        if self.side not in ("buy", "sell"):
            raise ValueError(f"side must be buy|sell, got {self.side!r}")
        if self.qty <= 0:
            raise ValueError(f"qty must be > 0, got {self.qty}")


@dataclass
class OrderResult:
    """Broker's response to an order submission."""

    order_id: str
    client_order_id: Optional[str]
    status: str             # "accepted" | "filled" | "rejected" | ...
    filled_qty: float = 0.0
    filled_avg_price: float = 0.0
    raw: dict = field(default_factory=dict)


@dataclass
class BrokerPosition:
    """One open position as the broker sees it."""

    symbol: str
    qty: float              # signed: + long, - short
    avg_entry_price: float
    market_value: float = 0.0
    unrealized_pl: float = 0.0


@dataclass
class BrokerAccount:
    """Account-level snapshot."""

    equity: float
    cash: float
    buying_power: float


# ---------------------------------------------------------------------------
# Adapter Protocol
# ---------------------------------------------------------------------------

class BrokerAdapter(Protocol):
    """Minimal interface every broker implementation must satisfy."""

    def submit_order(self, req: OrderRequest) -> OrderResult: ...
    def cancel_order(self, order_id: str) -> bool: ...
    def get_position(self, symbol: str) -> Optional[BrokerPosition]: ...
    def get_account(self) -> BrokerAccount: ...


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_client_order_id(run_id: str, entry_idx: int) -> str:
    """Idempotency key: stable per (run, bar) pair so retries cannot double-fill."""
    safe_run = run_id.replace("=", "-").replace("/", "-")
    return f"{safe_run}-e{int(entry_idx)}"


def submit_order_with_retry(
    broker: BrokerAdapter,
    req: OrderRequest,
    max_attempts: int = 4,
    base_delay: float = 2.0,
) -> OrderResult:
    """Submit an order with exponential backoff on transient errors.

    Backoff schedule: 2s, 4s, 8s. A 4xx response other than 429 is a
    permanent failure and is not retried.
    """
    last_exc: Optional[Exception] = None
    for attempt in range(max_attempts):
        try:
            return broker.submit_order(req)
        except TransientBrokerError as exc:
            last_exc = exc
            if attempt == max_attempts - 1:
                break
            delay = base_delay * (2 ** attempt)
            log.warning(
                "broker submit attempt %d/%d failed (%s); retrying in %.1fs",
                attempt + 1, max_attempts, exc, delay,
            )
            time.sleep(delay)
        except PermanentBrokerError:
            raise
    raise last_exc if last_exc else PermanentBrokerError("unknown broker error")


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class BrokerError(Exception):
    """Base class for broker errors."""


class TransientBrokerError(BrokerError):
    """Network/server error that is safe to retry."""


class PermanentBrokerError(BrokerError):
    """4xx (non-429) — bad request, will not be retried."""


# ---------------------------------------------------------------------------
# Mock broker (default when broker disabled)
# ---------------------------------------------------------------------------

class MockBroker:
    """In-memory broker for tests and dry-runs.

    Fills market orders instantly at ``last_price`` (settable per symbol)
    and tracks one position per symbol.
    """

    def __init__(self, equity: float = 100_000.0) -> None:
        self._account = BrokerAccount(equity=equity, cash=equity, buying_power=equity)
        self._positions: dict[str, BrokerPosition] = {}
        self._orders: dict[str, OrderResult] = {}
        self._last_prices: dict[str, float] = {}
        self._submitted_client_ids: dict[str, str] = {}    # idempotency
        self._lock = Lock()
        self._fail_next: int = 0
        self._fail_kind: str = ""

    # ---- test helpers ----
    def set_price(self, symbol: str, price: float) -> None:
        self._last_prices[symbol] = float(price)

    def set_position(self, pos: BrokerPosition) -> None:
        self._positions[pos.symbol] = pos

    def fail_next(self, n: int = 1, kind: str = "transient") -> None:
        """Make the next ``n`` ``submit_order`` calls raise the chosen error."""
        self._fail_next = int(n)
        self._fail_kind = kind

    # ---- adapter interface ----
    def submit_order(self, req: OrderRequest) -> OrderResult:
        with self._lock:
            if self._fail_next > 0:
                self._fail_next -= 1
                if self._fail_kind == "permanent":
                    raise PermanentBrokerError("mock permanent failure")
                raise TransientBrokerError("mock transient failure")

            # Idempotency: replay-safe.
            cid = req.client_order_id
            if cid and cid in self._submitted_client_ids:
                existing_id = self._submitted_client_ids[cid]
                return self._orders[existing_id]

            price = self._last_prices.get(req.symbol, 0.0)
            order_id = f"mock-{len(self._orders) + 1}"
            signed_qty = req.qty if req.side == "buy" else -req.qty

            cur = self._positions.get(req.symbol)
            if cur is None:
                self._positions[req.symbol] = BrokerPosition(
                    symbol=req.symbol, qty=signed_qty, avg_entry_price=price,
                )
            else:
                new_qty = cur.qty + signed_qty
                if abs(new_qty) < 1e-9:
                    self._positions.pop(req.symbol, None)
                else:
                    cur.qty = new_qty

            result = OrderResult(
                order_id=order_id,
                client_order_id=cid,
                status="filled",
                filled_qty=req.qty,
                filled_avg_price=price,
                raw={"mock": True},
            )
            self._orders[order_id] = result
            if cid:
                self._submitted_client_ids[cid] = order_id
            return result

    def cancel_order(self, order_id: str) -> bool:
        with self._lock:
            return self._orders.pop(order_id, None) is not None

    def get_position(self, symbol: str) -> Optional[BrokerPosition]:
        return self._positions.get(symbol)

    def get_account(self) -> BrokerAccount:
        return self._account


# ---------------------------------------------------------------------------
# Alpaca REST adapter (no SDK dependency)
# ---------------------------------------------------------------------------

class AlpacaBroker:
    """Thin REST client for Alpaca paper-trading.

    Notes
    -----
    * Endpoint defaults to https://paper-api.alpaca.markets (paper).
    * We do NOT depend on the alpaca-py SDK — keeps install slim and avoids
      breakage when the SDK changes.
    * 429 / 5xx are mapped to ``TransientBrokerError``; other 4xx to
      ``PermanentBrokerError``.
    * In sandbox environments without outbound network, every call raises
      ``TransientBrokerError`` after a urllib timeout — caller must decide
      how to surface that to the operator.
    """

    DEFAULT_BASE_URL = "https://paper-api.alpaca.markets"

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        base_url: Optional[str] = None,
        timeout: float = 5.0,
    ) -> None:
        if not api_key or not api_secret:
            raise ValueError("AlpacaBroker requires api_key and api_secret")
        self._key = api_key
        self._secret = api_secret
        self._base = (base_url or self.DEFAULT_BASE_URL).rstrip("/")
        self._timeout = float(timeout)

    def _request(self, method: str, path: str, body: Optional[dict] = None) -> dict:
        url = f"{self._base}{path}"
        data = json.dumps(body).encode("utf-8") if body is not None else None
        req = urllib.request.Request(
            url=url,
            data=data,
            method=method,
            headers={
                "APCA-API-KEY-ID": self._key,
                "APCA-API-SECRET-KEY": self._secret,
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                payload = resp.read().decode("utf-8")
                return json.loads(payload) if payload else {}
        except urllib.error.HTTPError as exc:
            text = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
            if exc.code == 429 or 500 <= exc.code < 600:
                raise TransientBrokerError(f"HTTP {exc.code}: {text}") from exc
            raise PermanentBrokerError(f"HTTP {exc.code}: {text}") from exc
        except urllib.error.URLError as exc:
            raise TransientBrokerError(f"network error: {exc.reason}") from exc
        except (TimeoutError, OSError) as exc:
            raise TransientBrokerError(f"timeout/socket error: {exc}") from exc

    def submit_order(self, req: OrderRequest) -> OrderResult:
        body = {
            "symbol": req.symbol,
            "qty": str(req.qty),
            "side": req.side,
            "type": req.order_type,
            "time_in_force": req.time_in_force,
        }
        if req.client_order_id:
            body["client_order_id"] = req.client_order_id
        raw = self._request("POST", "/v2/orders", body)
        return OrderResult(
            order_id=str(raw.get("id", "")),
            client_order_id=raw.get("client_order_id"),
            status=str(raw.get("status", "")),
            filled_qty=float(raw.get("filled_qty") or 0.0),
            filled_avg_price=float(raw.get("filled_avg_price") or 0.0),
            raw=raw,
        )

    def cancel_order(self, order_id: str) -> bool:
        try:
            self._request("DELETE", f"/v2/orders/{order_id}")
            return True
        except PermanentBrokerError:
            return False

    def get_position(self, symbol: str) -> Optional[BrokerPosition]:
        try:
            raw = self._request("GET", f"/v2/positions/{symbol}")
        except PermanentBrokerError as exc:
            # Alpaca returns 404 when no position exists.
            if "404" in str(exc):
                return None
            raise
        return BrokerPosition(
            symbol=raw["symbol"],
            qty=float(raw.get("qty", 0.0)),
            avg_entry_price=float(raw.get("avg_entry_price", 0.0)),
            market_value=float(raw.get("market_value", 0.0)),
            unrealized_pl=float(raw.get("unrealized_pl", 0.0)),
        )

    def get_account(self) -> BrokerAccount:
        raw = self._request("GET", "/v2/account")
        return BrokerAccount(
            equity=float(raw.get("equity", 0.0)),
            cash=float(raw.get("cash", 0.0)),
            buying_power=float(raw.get("buying_power", 0.0)),
        )


# ---------------------------------------------------------------------------
# Position reconciliation
# ---------------------------------------------------------------------------

@dataclass
class ReconcileResult:
    """One asset's reconciliation outcome."""

    symbol: str
    local_qty: float        # signed; from PaperEngine local state
    broker_qty: float       # signed; from broker
    matched: bool
    detail: str = ""


def reconcile_positions(
    broker: BrokerAdapter,
    local_positions: dict[str, float],
) -> list[ReconcileResult]:
    """Compare local engine positions to broker positions.

    Parameters
    ----------
    broker:
        Adapter instance.
    local_positions:
        ``{symbol: signed_qty}`` from the cockpit's PaperEngine state.
        ``signed_qty`` uses the same convention as ``BrokerPosition.qty``
        (positive = long, negative = short, 0 = flat).

    Returns
    -------
    One ``ReconcileResult`` per symbol. Mismatches must be resolved by
    the operator before the cockpit accepts new signals — we never
    auto-correct because doing so during a stale-broker outage would
    double-trade.
    """
    out: list[ReconcileResult] = []
    seen: set[str] = set()
    for sym, local_qty in local_positions.items():
        seen.add(sym)
        bp = broker.get_position(sym)
        broker_qty = bp.qty if bp else 0.0
        matched = abs(local_qty - broker_qty) < 1e-6
        detail = "ok" if matched else f"local={local_qty} broker={broker_qty}"
        out.append(ReconcileResult(
            symbol=sym, local_qty=float(local_qty),
            broker_qty=float(broker_qty), matched=matched, detail=detail,
        ))
    return out


# ---------------------------------------------------------------------------
# Operator alert webhook
# ---------------------------------------------------------------------------

def post_alert(
    webhook_url: str,
    event: str,
    payload: dict,
    timeout: float = 3.0,
) -> bool:
    """POST a JSON alert to an operator webhook.

    Used on kill-switch halt, reconciliation mismatch, broker outage etc.
    Returns True on 2xx response, False otherwise. Errors are logged but
    never raised — alerts must not break the trading loop.
    """
    if not webhook_url:
        return False
    body = json.dumps({"event": event, **payload}).encode("utf-8")
    req = urllib.request.Request(
        url=webhook_url, data=body, method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            ok = 200 <= resp.status < 300
            if not ok:
                log.warning("alert webhook returned %s for event=%s", resp.status, event)
            return ok
    except Exception as exc:
        log.warning("alert webhook failed for event=%s: %s", event, exc)
        return False
