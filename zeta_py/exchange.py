from __future__ import annotations

import os
import statistics
from dataclasses import dataclass

import requests
from anchorpy import Idl
from solana.rpc.async_api import AsyncClient
from solana.rpc.types import TxOpts
from solders.pubkey import Pubkey
from solders.sysvar import CLOCK

from zeta_py import constants, pda
from zeta_py.accounts import Account, Clock
from zeta_py.market import Market
from zeta_py.types import Asset, Network
from zeta_py.zeta_client.accounts.pricing import Pricing
from zeta_py.zeta_client.accounts.state import State

idl_path = os.path.join(os.path.dirname(__file__), "idl/zeta.json")
with open(idl_path, "r") as f:
    idl = Idl.from_json(f.read())


# TODO: change to use attrs/cattrs
# TODO: add logging e.g. logger = logging.getLogger("pyserum.market.Market")
# TODO: change all to factory method init


@dataclass
class Exchange:
    # Initialize
    network: Network
    connection: AsyncClient
    program_id: Pubkey
    state: Account[State]
    pricing: Account[Pricing]
    markets: dict[Asset, Market] = None
    clock: Account[Clock] = None

    _serum_authority_address: Pubkey = None
    _mint_authority_address: Pubkey = None

    @classmethod
    async def load(
        cls,
        network: Network,
        connection: AsyncClient,
        assets: list[Asset] = Asset.all(),
        tx_opts: TxOpts = None,
        subscribe: bool = False,
        # load_from_store: bool,
        # callback: Optional[Callable[[Asset, EventType, Any], None]] = None,
    ) -> "Exchange":
        tx_opts = tx_opts or TxOpts(
            {
                "skip_preflight": False,
                "preflight_commitment": connection.commitment,
            }
        )
        # if loadConfig.network == "localnet" and loadConfig.loadFromStore:
        #     raise Exception("Cannot load localnet from store")
        program_id = constants.ZETA_PID[network]

        # Accounts
        state_address = pda.get_state_address(program_id)
        state = await Account[State].load(state_address, connection, State)

        pricing_address = pda.get_pricing_address(program_id)
        pricing = await Account[Pricing].load(pricing_address, connection, Pricing)

        # Addresses
        _serum_authority_address = pda.get_serum_authority_address(program_id)
        _mint_authority_address = pda.get_mint_authority_address(program_id)

        instance = cls(
            network=network,
            connection=connection,
            program_id=program_id,
            state=state,
            pricing=pricing,
            _serum_authority_address=_serum_authority_address,
            _mint_authority_address=_mint_authority_address,
        )

        instance.markets = {asset: await Market.load(asset, instance, subscribe) for asset in assets}

        # TODO add risk
        #   cls._riskCalculator = RiskCalculator(self.assets)

        # Load Clock
        instance.clock = await Account[Clock].load(CLOCK, connection, Clock)

        # TODO: Maybe disable polling/subscriptions by default and have helper to enable bulk
        if subscribe:
            instance.clock.subscribe(network, connection.commitment)
            instance.pricing.subscribe(network, connection.commitment)

        return instance

    @property
    def endpoint(self) -> str:
        return self.connection._provider.endpoint_uri

    @property
    def assets(self) -> list[Asset]:
        return list(self.markets.keys())

    # Priority Fees
    def toggle_auto_priority_fee(self):
        self._use_auto_priority_fee = not self._use_auto_priority_fee

    def update_auto_fee(self):
        account_list = []

        # Query the most written-to accounts
        # Note: getRecentPrioritizationFees() will account for global fees too if no one is writing to our accs
        for market in self.markets.values():
            account_list.append(market.address.perp_sync_queue_address)

        try:
            data = requests.post(
                self.endpoint,
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "getRecentPrioritizationFees",
                    "params": [[account_list]],
                },
            )

            fees = sorted(
                [obj["prioritizationFee"] for obj in data.json()["result"]],
                key=lambda x: x["slot"],
                reverse=True,
            )[
                :20
            ]  # Grab the latest 20

            median = statistics.median(fees)
            self.priority_fee = min(median, self._auto_priority_fee_upper_limit)
            print(f"AutoUpdate priority fee. New fee = {self.priority_fee} microlamports per compute unit")
        except Exception as e:
            print(f"updateAutoFee failed {e}")
