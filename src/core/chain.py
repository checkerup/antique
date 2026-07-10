"""On-chain wallet monitoring + early-buyer discovery for EVM networks.

Focused on **Robinhood Chain** (an Arbitrum Orbit Ethereum L2, chain id 4663,
ETH gas, launched July 2026) but works with any EVM chain that exposes a
standard JSON-RPC endpoint and, optionally, a Blockscout REST API. The same
network is what gmgn surfaces under "Robinhood EVM"; we talk to it directly via
its public RPC / explorer rather than through gmgn.

Design for testability (mirrors core/automation.py):

- All network access goes through two injectable callables on ``ChainClient``:
    * ``rpc_transport(method, params) -> result``      (JSON-RPC ``result`` field)
    * ``explorer_transport(path, params) -> dict``     (parsed Blockscout JSON)
  Real transports are built lazily with httpx; unit tests inject fakes so no
  network is touched.
- The parsing/aggregation logic (``parse_early_buyers``,
  ``summarize_wallet_activity``, hex/address helpers) is pure and unit-tested
  directly with fixture data.

What it does:

- Wallet monitoring: ETH balance, nonce (tx count), and recent transaction
  history per address, aggregated into a compact summary.
- Early buyers: given a token contract, read its ERC-20 ``Transfer`` events
  from the earliest blocks forward and return the first distinct receiving
  wallets (the "early buyers"), excluding the zero address, the token contract
  itself, and any caller-supplied addresses (LPs/routers/deployer).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ZERO_ADDRESS = "0x" + "0" * 40

# keccak256("Transfer(address,address,uint256)") — the ERC-20/721 Transfer topic.
TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"


# ---------------------------------------------------------------------------
# Chain configuration + presets
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ChainConfig:
    """Static config for an EVM network."""

    name: str
    chain_id: int
    rpc_url: str
    explorer_api: str = ""      # Blockscout base, e.g. https://host (no trailing /api)
    currency: str = "ETH"
    is_testnet: bool = False


# Public endpoints (rate-limited; fine for monitoring, swap for a provider key
# in production). Source: docs.robinhood.com/chain/connecting.
ROBINHOOD_MAINNET = ChainConfig(
    name="Robinhood Chain",
    chain_id=4663,
    rpc_url="https://rpc.mainnet.chain.robinhood.com",
    explorer_api="https://robinhoodchain.blockscout.com",
    currency="ETH",
    is_testnet=False,
)

ROBINHOOD_TESTNET = ChainConfig(
    name="Robinhood Chain Testnet",
    chain_id=46630,
    rpc_url="https://rpc.testnet.chain.robinhood.com",
    explorer_api="https://explorer.testnet.chain.robinhood.com",
    currency="ETH",
    is_testnet=True,
)

_PRESETS: Dict[str, ChainConfig] = {
    "robinhood": ROBINHOOD_MAINNET,
    "robinhood-mainnet": ROBINHOOD_MAINNET,
    "robinhood-testnet": ROBINHOOD_TESTNET,
}


def get_chain(name: str) -> ChainConfig:
    """Look up a built-in chain preset by name (case-insensitive)."""
    key = (name or "").strip().lower()
    if key not in _PRESETS:
        raise ValueError(
            f"unknown chain {name!r}; known: {', '.join(sorted(_PRESETS))}"
        )
    return _PRESETS[key]


def supported_chains() -> List[str]:
    return sorted(_PRESETS)


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


def hex_to_int(value: Any) -> int:
    """Parse a hex-quantity ('0x..') or int/decimal-string into an int."""
    if value is None:
        return 0
    if isinstance(value, int):
        return value
    s = str(value).strip()
    if s == "":
        return 0
    if s.lower().startswith("0x"):
        return int(s, 16)
    return int(s)


def wei_to_eth(wei: Any, decimals: int = 18) -> float:
    """Convert a wei amount (int or hex) to a float token amount."""
    return hex_to_int(wei) / (10 ** decimals)


def normalize_address(addr: str) -> str:
    """Lowercase + 0x-prefix an address. Does not compute EIP-55 checksum."""
    if not addr:
        return ""
    a = str(addr).strip().lower()
    if not a.startswith("0x"):
        a = "0x" + a
    return a


def is_zero_address(addr: str) -> bool:
    return normalize_address(addr) == ZERO_ADDRESS


def is_valid_address(addr: str) -> bool:
    """True if ``addr`` looks like a 20-byte hex address."""
    a = normalize_address(addr)
    if len(a) != 42:
        return False
    try:
        int(a, 16)
        return True
    except ValueError:
        return False


def topic_to_address(topic: str) -> str:
    """Extract a 20-byte address from a 32-byte log topic (last 40 hex chars)."""
    if not topic:
        return ""
    t = str(topic).lower().replace("0x", "")
    if len(t) < 40:
        return ""
    return "0x" + t[-40:]


# ---------------------------------------------------------------------------
# Early-buyer parsing (pure)
# ---------------------------------------------------------------------------


@dataclass
class Buyer:
    address: str
    block_number: int
    tx_hash: str = ""
    amount: float = 0.0
    log_index: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "address": self.address,
            "block_number": self.block_number,
            "tx_hash": self.tx_hash,
            "amount": self.amount,
            "log_index": self.log_index,
        }


def parse_early_buyers(
    logs: List[Dict[str, Any]],
    *,
    token: str = "",
    exclude: Optional[List[str]] = None,
    decimals: int = 18,
    limit: int = 20,
) -> List[Buyer]:
    """Given raw ``eth_getLogs`` Transfer events, return the earliest distinct
    *receiving* wallets (early buyers), ordered by (block, log index).

    Each log is expected in standard JSON-RPC shape:
        {topics: [TRANSFER_TOPIC, from_topic, to_topic], data, blockNumber,
         transactionHash, logIndex}

    Rules:
      - Only Transfer logs are considered (topic0 == TRANSFER_TOPIC).
      - The recipient (``to``, topic[2]) is the buyer.
      - The zero address, the token contract, and any ``exclude`` address
        (LP pair / router / deployer) are skipped.
      - Each address counted once, at its FIRST receive.
    """
    excluded = {normalize_address(a) for a in (exclude or [])}
    excluded.add(ZERO_ADDRESS)
    if token:
        excluded.add(normalize_address(token))

    # Sort ascending so "first receive" is deterministic even if logs arrive
    # unordered.
    def _key(log: Dict[str, Any]):
        return (hex_to_int(log.get("blockNumber")), hex_to_int(log.get("logIndex")))

    seen: set = set()
    buyers: List[Buyer] = []
    for log in sorted(logs, key=_key):
        topics = log.get("topics") or []
        if len(topics) < 3:
            continue
        # topic0 must be the Transfer event signature.
        if str(topics[0]).lower() != TRANSFER_TOPIC:
            continue
        to_addr = normalize_address(topic_to_address(topics[2]))
        if not to_addr or to_addr in excluded or to_addr in seen:
            continue
        seen.add(to_addr)
        buyers.append(Buyer(
            address=to_addr,
            block_number=hex_to_int(log.get("blockNumber")),
            tx_hash=str(log.get("transactionHash", "")),
            amount=wei_to_eth(log.get("data", "0x0"), decimals),
            log_index=hex_to_int(log.get("logIndex")),
        ))
        if len(buyers) >= limit:
            break
    return buyers


# ---------------------------------------------------------------------------
# Wallet activity summary (pure)
# ---------------------------------------------------------------------------


@dataclass
class WalletSummary:
    address: str
    eth_balance: float = 0.0
    tx_count: int = 0
    first_seen_block: Optional[int] = None
    last_seen_block: Optional[int] = None
    sent_count: int = 0
    received_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "address": self.address,
            "eth_balance": self.eth_balance,
            "tx_count": self.tx_count,
            "first_seen_block": self.first_seen_block,
            "last_seen_block": self.last_seen_block,
            "sent_count": self.sent_count,
            "received_count": self.received_count,
        }


def summarize_wallet_activity(
    address: str,
    transactions: List[Dict[str, Any]],
    *,
    eth_balance: float = 0.0,
) -> WalletSummary:
    """Aggregate a list of Blockscout/RPC transaction dicts for one address.

    Each tx dict may use Blockscout v2 shape (``from``/``to`` as objects with
    ``hash``, ``block_number``) or flat RPC shape (``from``/``to`` strings,
    ``blockNumber``). Both are handled.
    """
    me = normalize_address(address)
    summary = WalletSummary(address=me, eth_balance=eth_balance, tx_count=len(transactions))
    blocks: List[int] = []
    for tx in transactions:
        blk = tx.get("block_number", tx.get("blockNumber"))
        blk_int = hex_to_int(blk) if blk is not None else None
        if blk_int is not None:
            blocks.append(blk_int)
        frm = _addr_field(tx.get("from"))
        to = _addr_field(tx.get("to"))
        if frm == me:
            summary.sent_count += 1
        if to == me:
            summary.received_count += 1
    if blocks:
        summary.first_seen_block = min(blocks)
        summary.last_seen_block = max(blocks)
    return summary


def _addr_field(value: Any) -> str:
    """Extract a normalized address from a string or a Blockscout {hash:..} obj."""
    if value is None:
        return ""
    if isinstance(value, dict):
        return normalize_address(value.get("hash", value.get("address", "")))
    return normalize_address(value)


# ---------------------------------------------------------------------------
# Chain client (network access via injectable transports)
# ---------------------------------------------------------------------------


class ChainError(RuntimeError):
    """Raised when an RPC/explorer call fails."""


class ChainClient:
    """Talks to an EVM chain over JSON-RPC + Blockscout.

    Args:
        config: a :class:`ChainConfig` (use ``get_chain('robinhood')``).
        rpc_transport: optional ``(method, params) -> result`` callable. If
            omitted, a default httpx-based transport is built lazily.
        explorer_transport: optional ``(path, params) -> dict`` callable for
            Blockscout REST. If omitted, a default httpx transport is used.
        timeout: network timeout in seconds for the default transports.
    """

    def __init__(
        self,
        config: ChainConfig,
        *,
        rpc_transport: Optional[Callable[[str, list], Any]] = None,
        explorer_transport: Optional[Callable[[str, dict], dict]] = None,
        timeout: float = 15.0,
    ):
        self.config = config
        self.timeout = timeout
        self._rpc = rpc_transport or self._default_rpc
        self._explorer = explorer_transport or self._default_explorer
        self._rpc_id = 0

    # ---- default transports (lazy httpx) ----

    def _default_rpc(self, method: str, params: list) -> Any:
        import httpx
        self._rpc_id += 1
        payload = {"jsonrpc": "2.0", "id": self._rpc_id, "method": method, "params": params}
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(self.config.rpc_url, json=payload)
                resp.raise_for_status()
                data = resp.json()
        except Exception as exc:  # pragma: no cover - network path
            raise ChainError(f"RPC {method} failed: {exc}") from exc
        if "error" in data and data["error"]:
            raise ChainError(f"RPC {method} error: {data['error']}")
        return data.get("result")

    def _default_explorer(self, path: str, params: dict) -> dict:
        if not self.config.explorer_api:
            raise ChainError("no explorer_api configured for this chain")
        import httpx
        url = self.config.explorer_api.rstrip("/") + path
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.get(url, params=params)
                resp.raise_for_status()
                return resp.json()
        except Exception as exc:  # pragma: no cover - network path
            raise ChainError(f"explorer GET {path} failed: {exc}") from exc

    # ---- JSON-RPC reads ----

    def block_number(self) -> int:
        return hex_to_int(self._rpc("eth_blockNumber", []))

    def chain_id(self) -> int:
        return hex_to_int(self._rpc("eth_chainId", []))

    def get_balance_wei(self, address: str) -> int:
        if not is_valid_address(address):
            raise ValueError(f"invalid address: {address!r}")
        return hex_to_int(self._rpc("eth_getBalance", [normalize_address(address), "latest"]))

    def get_eth_balance(self, address: str) -> float:
        return wei_to_eth(self.get_balance_wei(address))

    def get_transaction_count(self, address: str) -> int:
        if not is_valid_address(address):
            raise ValueError(f"invalid address: {address!r}")
        return hex_to_int(self._rpc("eth_getTransactionCount", [normalize_address(address), "latest"]))

    def get_logs(
        self,
        *,
        address: Optional[str] = None,
        topics: Optional[list] = None,
        from_block: Any = "earliest",
        to_block: Any = "latest",
    ) -> List[Dict[str, Any]]:
        params = {
            "fromBlock": from_block if isinstance(from_block, str) else hex(int(from_block)),
            "toBlock": to_block if isinstance(to_block, str) else hex(int(to_block)),
        }
        if address:
            params["address"] = normalize_address(address)
        if topics:
            params["topics"] = topics
        result = self._rpc("eth_getLogs", [params])
        return result or []

    # ---- Blockscout reads ----

    def address_transactions(self, address: str, *, limit: int = 50) -> List[Dict[str, Any]]:
        """Recent transactions for an address (Blockscout v2)."""
        if not is_valid_address(address):
            raise ValueError(f"invalid address: {address!r}")
        data = self._explorer(f"/api/v2/addresses/{normalize_address(address)}/transactions", {})
        items = data.get("items", []) if isinstance(data, dict) else []
        return items[:limit]

    def token_transfers(self, token: str, *, limit: int = 100) -> List[Dict[str, Any]]:
        """Recent ERC-20 transfers for a token (Blockscout v2)."""
        if not is_valid_address(token):
            raise ValueError(f"invalid token address: {token!r}")
        data = self._explorer(f"/api/v2/tokens/{normalize_address(token)}/transfers", {})
        items = data.get("items", []) if isinstance(data, dict) else []
        return items[:limit]

    # ---- High-level operations ----

    def monitor_wallet(self, address: str, *, tx_limit: int = 50) -> WalletSummary:
        """Full snapshot for one wallet: balance + tx history summary."""
        balance = self.get_eth_balance(address)
        try:
            txs = self.address_transactions(address, limit=tx_limit)
        except ChainError:
            txs = []  # explorer optional — balance still returned
        return summarize_wallet_activity(address, txs, eth_balance=balance)

    def monitor_wallets(self, addresses: List[str], *, tx_limit: int = 50) -> List[WalletSummary]:
        """Snapshot a batch of wallets."""
        return [self.monitor_wallet(a, tx_limit=tx_limit) for a in addresses]

    def early_buyers(
        self,
        token: str,
        *,
        from_block: Any = "earliest",
        to_block: Any = "latest",
        exclude: Optional[List[str]] = None,
        decimals: int = 18,
        limit: int = 20,
    ) -> List[Buyer]:
        """Find the earliest distinct buyers of a token via its Transfer logs.

        Reads ``Transfer`` events filtered to the token contract and returns the
        first distinct recipients. Uses ``eth_getLogs`` (works on any standard
        RPC); for very large ranges, narrow ``from_block``/``to_block``.
        """
        if not is_valid_address(token):
            raise ValueError(f"invalid token address: {token!r}")
        logs = self.get_logs(
            address=token,
            topics=[TRANSFER_TOPIC],
            from_block=from_block,
            to_block=to_block,
        )
        return parse_early_buyers(
            logs, token=token, exclude=exclude, decimals=decimals, limit=limit
        )
