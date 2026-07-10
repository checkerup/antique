"""Tests for on-chain wallet monitoring + early-buyer discovery (Robinhood Chain).

No network is touched: the ChainClient's RPC/explorer transports are injected
with fakes, and the pure parsing/aggregation helpers are tested directly.
"""
import pytest

from src.core.chain import (
    ROBINHOOD_MAINNET,
    ROBINHOOD_TESTNET,
    TRANSFER_TOPIC,
    ZERO_ADDRESS,
    Buyer,
    ChainClient,
    ChainConfig,
    WalletSummary,
    get_chain,
    hex_to_int,
    is_valid_address,
    is_zero_address,
    normalize_address,
    parse_early_buyers,
    summarize_wallet_activity,
    supported_chains,
    topic_to_address,
    wei_to_eth,
)


# ---------------------------------------------------------------------------
# Presets
# ---------------------------------------------------------------------------


def test_robinhood_mainnet_preset():
    assert ROBINHOOD_MAINNET.chain_id == 4663
    assert ROBINHOOD_MAINNET.currency == "ETH"
    assert ROBINHOOD_MAINNET.rpc_url.startswith("https://")
    assert not ROBINHOOD_MAINNET.is_testnet


def test_robinhood_testnet_preset():
    assert ROBINHOOD_TESTNET.chain_id == 46630
    assert ROBINHOOD_TESTNET.is_testnet


def test_get_chain_aliases():
    assert get_chain("robinhood").chain_id == 4663
    assert get_chain("ROBINHOOD-MAINNET").chain_id == 4663
    assert get_chain("robinhood-testnet").chain_id == 46630


def test_get_chain_unknown_raises():
    with pytest.raises(ValueError, match="unknown chain"):
        get_chain("dogecoin")


def test_supported_chains_lists_robinhood():
    assert "robinhood" in supported_chains()


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


def test_hex_to_int():
    assert hex_to_int("0x10") == 16
    assert hex_to_int("0x0") == 0
    assert hex_to_int(255) == 255
    assert hex_to_int("42") == 42
    assert hex_to_int(None) == 0
    assert hex_to_int("") == 0


def test_wei_to_eth():
    assert wei_to_eth(10**18) == 1.0
    assert wei_to_eth("0xde0b6b3a7640000") == 1.0  # 1e18 in hex
    assert wei_to_eth(5 * 10**17) == 0.5


def test_normalize_address():
    assert normalize_address("ABC") == "0xabc"
    assert normalize_address("0xDeAdBeef") == "0xdeadbeef"
    assert normalize_address("") == ""


def test_is_zero_address():
    assert is_zero_address(ZERO_ADDRESS)
    assert is_zero_address("0x0000000000000000000000000000000000000000")
    assert not is_zero_address("0x1111111111111111111111111111111111111111")


def test_is_valid_address():
    assert is_valid_address("0x" + "a" * 40)
    assert is_valid_address("0x1234567890abcdef1234567890abcdef12345678")
    assert not is_valid_address("0x123")            # too short
    assert not is_valid_address("0x" + "z" * 40)     # non-hex
    assert not is_valid_address("")


def test_topic_to_address():
    topic = "0x000000000000000000000000" + "a" * 40
    assert topic_to_address(topic) == "0x" + "a" * 40
    assert topic_to_address("") == ""
    assert topic_to_address("0x1234") == ""  # too short


# ---------------------------------------------------------------------------
# Early buyers (pure)
# ---------------------------------------------------------------------------


def _transfer_log(to_addr, block, log_index=0, frm="0x" + "f" * 40, amount_wei=10**18):
    return {
        "topics": [
            TRANSFER_TOPIC,
            "0x000000000000000000000000" + normalize_address(frm)[2:],
            "0x000000000000000000000000" + normalize_address(to_addr)[2:],
        ],
        "data": hex(amount_wei),
        "blockNumber": hex(block),
        "logIndex": hex(log_index),
        "transactionHash": "0x" + "1" * 64,
    }


def test_parse_early_buyers_orders_and_dedupes():
    a = "0x" + "a" * 40
    b = "0x" + "b" * 40
    logs = [
        _transfer_log(b, block=105, log_index=1),
        _transfer_log(a, block=100, log_index=0),
        _transfer_log(a, block=110, log_index=0),  # duplicate buyer, later
    ]
    buyers = parse_early_buyers(logs, limit=10)
    assert [x.address for x in buyers] == [a, b]  # ordered by block, deduped
    assert buyers[0].block_number == 100


def test_parse_early_buyers_excludes_zero_and_token():
    token = "0x" + "c" * 40
    good = "0x" + "a" * 40
    logs = [
        _transfer_log(ZERO_ADDRESS, block=100),
        _transfer_log(token, block=101),
        _transfer_log(good, block=102),
    ]
    buyers = parse_early_buyers(logs, token=token, limit=10)
    assert [x.address for x in buyers] == [good]


def test_parse_early_buyers_honors_exclude_list():
    lp = "0x" + "d" * 40
    good = "0x" + "a" * 40
    logs = [_transfer_log(lp, block=100), _transfer_log(good, block=101)]
    buyers = parse_early_buyers(logs, exclude=[lp], limit=10)
    assert [x.address for x in buyers] == [good]


def test_parse_early_buyers_respects_limit():
    logs = [_transfer_log("0x" + f"{i:040x}", block=100 + i) for i in range(1, 11)]
    buyers = parse_early_buyers(logs, limit=3)
    assert len(buyers) == 3


def test_parse_early_buyers_skips_non_transfer_topics():
    good = "0x" + "a" * 40
    bad_topic_log = _transfer_log(good, block=100)
    bad_topic_log["topics"][0] = "0x" + "e" * 64  # not a Transfer event
    buyers = parse_early_buyers([bad_topic_log], limit=10)
    assert buyers == []


def test_buyer_to_dict():
    b = Buyer(address="0xabc", block_number=100, tx_hash="0xdef", amount=1.5, log_index=2)
    d = b.to_dict()
    assert d["address"] == "0xabc"
    assert d["amount"] == 1.5


# ---------------------------------------------------------------------------
# Wallet summary (pure)
# ---------------------------------------------------------------------------


def test_summarize_wallet_activity_flat_shape():
    me = "0x" + "a" * 40
    other = "0x" + "b" * 40
    txs = [
        {"from": me, "to": other, "blockNumber": "0x64"},    # sent (100)
        {"from": other, "to": me, "blockNumber": "0x6e"},    # received (110)
    ]
    s = summarize_wallet_activity(me, txs, eth_balance=2.5)
    assert s.tx_count == 2
    assert s.sent_count == 1
    assert s.received_count == 1
    assert s.first_seen_block == 100
    assert s.last_seen_block == 110
    assert s.eth_balance == 2.5


def test_summarize_wallet_activity_blockscout_shape():
    me = "0x" + "a" * 40
    other = "0x" + "b" * 40
    txs = [
        {"from": {"hash": me}, "to": {"hash": other}, "block_number": 200},
        {"from": {"hash": other}, "to": {"hash": me}, "block_number": 210},
    ]
    s = summarize_wallet_activity(me, txs)
    assert s.sent_count == 1
    assert s.received_count == 1
    assert s.first_seen_block == 200
    assert s.last_seen_block == 210


def test_summarize_empty():
    s = summarize_wallet_activity("0x" + "a" * 40, [])
    assert s.tx_count == 0
    assert s.first_seen_block is None


# ---------------------------------------------------------------------------
# ChainClient with injected fake transports (no network)
# ---------------------------------------------------------------------------


class FakeRpc:
    """Records calls, returns canned results keyed by method."""

    def __init__(self, results):
        self.results = results
        self.calls = []

    def __call__(self, method, params):
        self.calls.append((method, params))
        val = self.results.get(method)
        return val(params) if callable(val) else val


@pytest.fixture
def cfg():
    return get_chain("robinhood")


def test_client_block_number(cfg):
    client = ChainClient(cfg, rpc_transport=FakeRpc({"eth_blockNumber": "0x1a"}))
    assert client.block_number() == 26


def test_client_chain_id(cfg):
    client = ChainClient(cfg, rpc_transport=FakeRpc({"eth_chainId": hex(4663)}))
    assert client.chain_id() == 4663


def test_client_get_eth_balance(cfg):
    client = ChainClient(cfg, rpc_transport=FakeRpc({"eth_getBalance": hex(10**18)}))
    assert client.get_eth_balance("0x" + "a" * 40) == 1.0


def test_client_balance_rejects_bad_address(cfg):
    client = ChainClient(cfg, rpc_transport=FakeRpc({}))
    with pytest.raises(ValueError):
        client.get_balance_wei("0x123")


def test_client_monitor_wallet_combines_balance_and_txs(cfg):
    me = "0x" + "a" * 40
    other = "0x" + "b" * 40
    rpc = FakeRpc({"eth_getBalance": hex(3 * 10**18)})
    def explorer(path, params):
        assert me[2:] in path.lower()
        return {"items": [{"from": {"hash": me}, "to": {"hash": other}, "block_number": 5}]}
    client = ChainClient(cfg, rpc_transport=rpc, explorer_transport=explorer)
    s = client.monitor_wallet(me)
    assert s.eth_balance == 3.0
    assert s.tx_count == 1
    assert s.sent_count == 1


def test_client_monitor_wallet_survives_explorer_failure(cfg):
    from src.core.chain import ChainError
    def explorer(path, params):
        raise ChainError("explorer down")
    client = ChainClient(
        cfg,
        rpc_transport=FakeRpc({"eth_getBalance": hex(10**18)}),
        explorer_transport=explorer,
    )
    s = client.monitor_wallet("0x" + "a" * 40)
    assert s.eth_balance == 1.0
    assert s.tx_count == 0  # explorer failed, balance still returned


def test_client_early_buyers_via_getlogs(cfg):
    token = "0x" + "c" * 40
    a = "0x" + "a" * 40
    b = "0x" + "b" * 40
    logs = [_transfer_log(a, block=100), _transfer_log(b, block=101)]
    rpc = FakeRpc({"eth_getLogs": logs})
    client = ChainClient(cfg, rpc_transport=rpc)
    buyers = client.early_buyers(token, limit=10)
    assert [x.address for x in buyers] == [a, b]
    # Verify the filter was built correctly.
    method, params = rpc.calls[0]
    assert method == "eth_getLogs"
    assert params[0]["address"] == token
    assert params[0]["topics"] == [TRANSFER_TOPIC]


def test_client_early_buyers_bad_token(cfg):
    client = ChainClient(cfg, rpc_transport=FakeRpc({}))
    with pytest.raises(ValueError):
        client.early_buyers("0xnope")


def test_client_get_logs_hexifies_int_blocks(cfg):
    rpc = FakeRpc({"eth_getLogs": []})
    client = ChainClient(cfg, rpc_transport=rpc)
    client.get_logs(from_block=100, to_block=200)
    _, params = rpc.calls[0]
    assert params[0]["fromBlock"] == "0x64"
    assert params[0]["toBlock"] == "0xc8"


# ---------------------------------------------------------------------------
# MCP exposure
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mcp_lists_chain_tools():
    from src.mcp.server import MCPServer
    server = MCPServer()
    resp = await server.handle_request({
        "jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {},
    })
    names = [t["name"] for t in resp["result"]["tools"]]
    assert "chain_monitor_wallets" in names
    assert "chain_early_buyers" in names
