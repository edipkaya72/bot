import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
    PRIVATE_KEY = os.getenv("PRIVATE_KEY", "")
    WALLET_ADDRESS = os.getenv("WALLET_ADDRESS", "")
    RPC_URL = os.getenv("RPC_URL", "https://polygon-rpc.com")
    AZURO_GRAPHQL = "https://thegraph.com/hosted-service/subgraph/azuro-protocol/azuro-api-polygon-v3"
    AZURO_CORE_ADDRESS = "0x7f3F3f19c4e4015fd9Db2f22e653c766154091EF"
    USDC_ADDRESS = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
    BET_AMOUNT_USDC = float(os.getenv("BET_AMOUNT_USDC", "5"))
    MIN_WIN_PROBABILITY = float(os.getenv("MIN_WIN_PROBABILITY", "0.60"))
    MAX_WIN_PROBABILITY = float(os.getenv("MAX_WIN_PROBABILITY", "0.75"))
    MIN_ODDS = float(os.getenv("MIN_ODDS", "1.3"))
    MAX_ODDS = float(os.getenv("MAX_ODDS", "1.7"))
    MAX_DAILY_BETS = int(os.getenv("MAX_DAILY_BETS", "20"))
    MAX_DAILY_LOSS = float(os.getenv("MAX_DAILY_LOSS", "50"))
