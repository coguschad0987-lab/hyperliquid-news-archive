"""
Hyperliquid filtering configuration.

Contains keywords for filtering Hyperliquid-related news and
priority accounts that should always be included in results.
"""

# Priority accounts - these accounts' posts are always included in the final results
# Format: username (without @)
PRIORITY_ACCOUNTS = [
    "stevenyuntcap",      # steven.hl
    "HyperliquidNews",    # Hyperliquid News
    "GLC_Research",       # GLC
    "0xBroze",            # Charlie.hl
    "mlmabc",             # MLM
    "HyperliquidR",       # Hyperliquid Research Collective (HRC)
    "qwantifyio",         # Qwantify
]

# Keywords for filtering Hyperliquid-related content
# All matching is case-insensitive
# Duplicates have been removed
HYPERLIQUID_KEYWORDS = [
    # Core Hyperliquid terms
    "hyperliquid",
    "hyperliquid ecosystem",
    "hyperliquid strategies",
    "hl",
    "hype",
    "hyper",
    "hyperps",

    # Protocol & Technology
    "hyperbft",
    "hyperevm",
    "hypercore",
    "l1",
    "clob",
    "fully onchain",
    "high-performance",
    "consensus",
    "validator",
    "node",
    "rpc",
    "precompile",
    "oracle",
    "order book",
    "orderbook",
    "permissionless",
    "dual block",

    # Trading terms
    "perp",
    "perpetual",
    "dex",
    "exchange",
    "cex",
    "derivatives",
    "leverage",
    "trade",
    "margin",
    "cross margin",
    "isolated margin",
    "portfolio margin",
    "funding",
    "fee",
    "open interest",
    "oi",
    "slippage",
    "liquidity",
    "order",
    "market order",
    "limit order",
    "take profit",
    "stop loss",
    "entry price",
    "liquidation",
    "insurance fund",
    "assistant fund",
    "assistance fund",
    "af",
    "position management",
    "risk engine",
    "quote asset",
    "adl",
    "auto-deleveraging",
    "delist",
    "market making",

    # Tokens & Economics
    "native token",
    "tge",
    "airdrop",
    "tokenomics",
    "emission",
    "supply schedule",
    "staking",
    "stake",
    "unstake",
    "fee sharing",
    "points",
    "point",
    "leaderboard",
    "incentive",
    "referral",
    "buyback",
    "native markets",
    "stablecoin",

    # Ecosystem tokens
    "purr",
    "hlp",
    "hypurr",
    "hypurrfi",
    "sthype",
    "khype",
    "usdh",
    "usde",
    "usdt",
    "usdc",
    "ubtc",

    # Metrics
    "tvl",
    "market share",
    "volume",
    "growth mode",
    "dau",

    # Governance
    "proposal",
    "vote",
    "governance",
    "hip",
    "hip-1",
    "hip-2",
    "hip-3",
    "hip1",
    "hip2",
    "hip3",

    # Ecosystem projects & tools
    "vault",
    "jeff",
    "hyena",
    "based",
    "pre-ipo",
    "swap",
    "multisig",
    "audit",
    "portfolio",
    "native",
    "phantom",
    "metamask",
    "builder codes",
    "builder code",
    "house all of finance",
    "house of all finance",
    "dreamcash",
    "usa500",
    "s&p500",
    "selini",
    "tether",
    "circle",
    "tsla",
    "tesla",
    "hyperlend",
    "evm",
    "core",
    "markets",
    "kntq",
    "kinetiq",
    "commodity",
    "equity",
    "stock",
    "gold",
    "silver",
    "ventuals",
    "defi",
    "prjx",
    "project x",
    "hsi",
    "hypd",
    "felix",
    "hyperdrive",
    "zero vc",
    "hypurrcollective",
    "hypurrco",
    "valantis",
    "trade.xyz",
    "kaiko",
    "neura vaults",
    "option",
    "covered call",
    "rysk",
    "silhouette",
    "earn",
    "hypurrscan",
    "borrow",
    "lend",
    "auction",
    "bridge",
    "application",
    "dexari",
    "lootbase",
    "rabby",
    "unit",
    "morpho",
    "hyperbeat",
    "pendle",
    "veda",
    "mev capital",
    "upshift",
    "looping collective",
    "liminal",
    "sentiment",
    "hyperswap",
    "midas",
    "d2 finance",
    "harmonix",
    "mlm",
    "otc",
    "alber blanc",
    "bug bounty",
    "gas fee",
]

# Number of posts to collect before filtering
INITIAL_COLLECTION_COUNT = 100

# Number of final posts after Hyperliquid filtering
FINAL_POST_COUNT = 30


def get_keywords_set() -> set[str]:
    """Return keywords as a lowercase set for efficient lookup."""
    return {kw.lower() for kw in HYPERLIQUID_KEYWORDS}


def get_priority_accounts_set() -> set[str]:
    """Return priority accounts as a lowercase set for efficient lookup."""
    return {acc.lower() for acc in PRIORITY_ACCOUNTS}
