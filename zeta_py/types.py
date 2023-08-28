from dataclasses import dataclass, field
from enum import Enum, IntEnum
from typing import Optional

from solders.hash import Hash
from zeta_py.zeta_client.types import order_type

from zeta_py.zeta_client.types import side, asset


class Asset(Enum):
    SOL = 0
    BTC = 1
    ETH = 2
    APT = 3
    ARB = 4
    UNDEFINED = 5

    def to_index(self):
        return self.value

    def to_string(self):
        return self.name

    def to_program_type(self):
        return asset.from_decoded({self.name: self.value})

    @staticmethod
    def all():
        return [a for a in Asset if a != Asset.UNDEFINED]

    def __str__(self) -> str:
        return self.name


class Network(Enum):
    LOCALNET = "localnet"
    DEVNET = "devnet"
    TESTNET = "testnet"
    MAINNET = "mainnet_beta"

    def __str__(self) -> str:
        return self.name


class OrderType(IntEnum):
    LIMIT = 0
    POSTONLY = 1
    FILLORKILL = 2
    IMMEDIATEORCANCEL = 3
    POSTONLYSLIDE = 4

    def to_program_type(self):
        return order_type.from_decoded({self.name.title(): self.value})


class Side(Enum):
    """Side of the orderbook to trade."""

    BID = 0
    """"""
    ASK = 1
    """"""

    def to_program_type(self) -> side.SideKind:
        return side.from_decoded({self.name.title(): self.value})


class SelfTradeBehavior(Enum):
    DECREMENT_TAKE = 0
    CANCEL_PROVIDE = 1
    ABORT_TRANSACTION = 2


@dataclass
class Position:
    size: float
    cost_of_trades: float


@dataclass
class TIFOptions:
    expiry_offset: Optional[int] = None
    expiry_ts: Optional[int] = None


@dataclass
class OrderOptions:
    tif_options: TIFOptions = field(default_factory=TIFOptions)
    order_type: Optional[OrderType] = OrderType.LIMIT
    client_order_id: Optional[int] = None
    tag: Optional[str] = "SDK"
    blockhash: Optional[Hash] = None
