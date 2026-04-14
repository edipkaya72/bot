import asyncio
import logging
from datetime import datetime
from web3 import Web3
from gql import gql, Client
from gql.transport.aiohttp import AIOHTTPTransport
import json

logger = logging.getLogger(__name__)

BETTING_ABI = json.loads('[{"inputs":[{"internalType":"uint256","name":"conditionId","type":"uint256"},{"internalType":"uint64","name":"outcomeId","type":"uint64"},{"internalType":"uint128","name":"amount","type":"uint128"},{"internalType":"uint64","name":"deadline","type":"uint64"},{"internalType":"uint64","name":"minOdds","type":"uint64"},{"internalType":"address","name":"affiliate","type":"address"}],"name":"bet","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"nonpayable","type":"function"}]')

USDC_ABI = json.loads('[{"inputs":[{"internalType":"address","name":"spender","type":"address"},{"internalType":"uint256","name":"amount","type":"uint256"}],"name":"approve","outputs":[{"internalType":"bool","name":"","type":"bool"}],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"internalType":"address","name":"account","type":"address"}],"name":"balanceOf","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"}]')

QUERY_TEMPLATE = """
query GetMarkets {
  conditions(
    first: 200
    where: {
      state: Created
      game_: {
        sport_in: ["Basketball", "Tennis"]
        startsAt_gt: "TIMESTAMP_HERE"
      }
    }
    orderBy: createdAt
    orderDirection: desc
  ) {
    id
    conditionId
    odds {
      outcomeId
      currentOdds
    }
    game {
      id
      title
      startsAt
      sport { name }
      league { name }
    }
    state
  }
}
"""

class AzuroArbitrage:
    def __init__(self, config):
        self.config = config
        self.w3 = Web3(Web3.HTTPProvider(config.RPC_URL))
        self.bet_history = []
        self.total_bets = 0
        self.total_won = 0
        self.net_profit = 0.0
        self.daily_bets = 0
        self.daily_loss = 0.0
        self.last_reset = datetime.now().date()

        if config.PRIVATE_KEY and config.WALLET_ADDRESS:
            self.account = self.w3.eth.account.from_key(config.PRIVATE_KEY)
            self.usdc = self.w3.eth.contract(
                address=Web3.to_checksum_address(config.USDC_ADDRESS),
                abi=USDC_ABI
            )
            self.betting_engine = self.w3.eth.contract(
                address=Web3.to_checksum_address(config.AZURO_CORE_ADDRESS),
                abi=BETTING_ABI
            )

    def _reset_daily_if_needed(self):
        today = datetime.now().date()
        if today != self.last_reset:
            self.daily_bets = 0
            self.daily_loss = 0.0
            self.last_reset = today

    def _odds_to_probability(self, odds):
        if odds <= 0:
            return 0
        return 1.0 / odds

    def _analyze_market(self, condition):
        try:
            odds_list = condition.get('odds', [])
            if not odds_list:
                return None

            game = condition.get('game', {})
            sport_name = game.get('sport', {}).get('name', '')

            if sport_name not in ['Basketball', 'Tennis']:
                return None

            best_option = None
            best_prob = 0

            for outcome in odds_list:
                odds_raw = float(outcome.get('currentOdds', 0))
                odds = odds_raw / 1e9 if odds_raw > 100 else odds_raw

                if odds < self.config.MIN_ODDS or odds > self.config.MAX_ODDS:
                    continue

                prob = self._odds_to_probability(odds)

                if self.config.MIN_WIN_PROBABILITY <= prob <= self.config.MAX_WIN_PROBABILITY:
                    if prob > best_prob:
                        best_prob = prob
                        best_option = {
                            'condition_id': condition['conditionId'],
                            'outcome_id': outcome['outcomeId'],
                            'odds': odds,
                            'win_prob': prob * 100,
                            'sport': sport_name,
                            'match': game.get('title', 'Bilinmiyor'),
                            'starts_at': game.get('startsAt', ''),
                            'amount': self.config.BET_AMOUNT_USDC
                        }

            return best_option
        except Exception as e:
            logger.error(f"Market analiz hatası: {e}")
            return None

    async def scan_markets(self):
        self._reset_daily_if_needed()

        if self.daily_bets >= self.config.MAX_DAILY_BETS:
            logger.info("Günlük bahis limitine ulaşıldı.")
            return []

        if self.daily_loss >= self.config.MAX_DAILY_LOSS:
            logger.info("Günlük kayıp limitine ulaşıldı.")
            return []

        try:
            now_ts = str(int(datetime.now().timestamp()))
            query_str = QUERY_TEMPLATE.replace("TIMESTAMP_HERE", now_ts)
            transport = AIOHTTPTransport(url=self.config.AZURO_GRAPHQL)

            async with Client(transport=transport, fetch_schema_from_transport=False) as session:
                result = await session.execute(gql(query_str))

            conditions = result.get('conditions', [])
            logger.info(f"{len(conditions)} market bulundu.")

            opportunities = []
            seen_matches = set()

            for condition in conditions:
                match_id = condition.get('game', {}).get('id', '')
                if match_id in seen_matches:
                    continue
                opp = self._analyze_market(condition)
                if opp:
                    opportunities.append(opp)
                    seen_matches.add(match_id)

            opportunities.sort(key=lambda x: x['win_prob'], reverse=True)
            return opportunities[:3]

        except Exception as e:
            logger.error(f"Market tarama hatası: {e}")
            return []

    async def get_balance(self):
        try:
            balance_raw = self.usdc.functions.balanceOf(
                Web3.to_checksum_address(self.config.WALLET_ADDRESS)
            ).call()
            return balance_raw / 1e6
        except Exception as e:
            logger.error(f"Bakiye hatası: {e}")
            return 0.0

    async def place_bet(self, opportunity):
        try:
            amount_usdc = int(opportunity['amount'] * 1e6)
            deadline = int(datetime.now().timestamp()) + 300

            approve_tx = self.usdc.functions.approve(
                Web3.to_checksum_address(self.config.AZURO_CORE_ADDRESS),
                amount_usdc
            ).build_transaction({
                'from': self.account.address,
                'nonce': self.w3.eth.get_transaction_count(self.account.address),
                'gas': 100000,
                'gasPrice': self.w3.eth.gas_price,
            })

            signed_approve = self.w3.eth.account.sign_transaction(approve_tx, self.config.PRIVATE_KEY)
            approve_hash = self.w3.eth.send_raw_transaction(signed_approve.raw_transaction)
            self.w3.eth.wait_for_transaction_receipt(approve_hash)

            min_odds = int(opportunity['odds'] * 1e9 * 0.99)

            bet_tx = self.betting_engine.functions.bet(
                int(opportunity['condition_id']),
                int(opportunity['outcome_id']),
                amount_usdc,
                deadline,
                min_odds,
                "0x0000000000000000000000000000000000000000"
            ).build_transaction({
                'from': self.account.address,
                'nonce': self.w3.eth.get_transaction_count(self.account.address),
                'gas': 300000,
                'gasPrice': self.w3.eth.gas_price,
            })

            signed_bet = self.w3.eth.account.sign_transaction(bet_tx, self.config.PRIVATE_KEY)
            bet_hash = self.w3.eth.send_raw_transaction(signed_bet.raw_transaction)
            receipt = self.w3.eth.wait_for_transaction_receipt(bet_hash)

            if receipt.status == 1:
                self.total_bets += 1
                self.daily_bets += 1
                self.bet_history.append({
                    **opportunity,
                    'tx_hash': bet_hash.hex(),
                    'time': datetime.now().isoformat(),
                    'won': False,
                    'resolved': False
                })
                return True
            return False

        except Exception as e:
            logger.error(f"Bahis oynama hatası: {e}")
            return False
