from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class TileType(str, Enum):
    START = "start"
    PROPERTY = "property"
    TRANSPORT = "transport"
    TAX = "tax"
    CHANCE = "chance"
    JAIL = "jail"
    AUDIT = "audit"
    JACKPOT = "jackpot"


class GamePhase(str, Enum):
    WAITING_FOR_PLAYERS = "waiting_for_players"
    WAITING_FOR_ROLL = "waiting_for_roll"
    WAITING_FOR_ACTION = "waiting_for_action"
    AUCTION_ACTIVE = "auction_active"
    FINISHED = "finished"


class EventEffect(str, Enum):
    GAIN_MONEY = "gain_money"
    LOSE_MONEY = "lose_money"
    MOVE_TO_START = "move_to_start"
    MOVE_TO_TILE = "move_to_tile"
    ROLL_DICE = "roll_dice"
    ATTACK_PLAYER = "attack_player"
    GO_TO_JAIL = "go_to_jail"
    COLLECT_FROM_PLAYERS = "collect_from_players"
    PAY_PLAYERS = "pay_players"


class LoanLenderType(str, Enum):
    BANK = "bank"
    PLAYER = "player"


class LoanOfferStatus(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class TradeOfferStatus(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class DiceResult(BaseModel):
    first: int
    second: int
    total: int
    is_double: bool


class Loan(BaseModel):
    id: str
    lender_type: LoanLenderType
    lender_id: Optional[str] = None
    borrower_id: str
    amount: int
    interest: float
    term_turns: int = 10
    remaining_turns: int
    overdue_turns: int = 0
    overdue_applied: bool = False
    collateral_tile_id: Optional[int] = None
    collateral_tile_ids: list[int] = Field(default_factory=list)


class LoanOffer(BaseModel):
    id: str
    lender_id: str
    borrower_id: str
    amount: int
    interest: float = 0.10
    term_turns: int = 10
    collateral_tile_ids: list[int] = Field(default_factory=list)
    status: LoanOfferStatus = LoanOfferStatus.PENDING


class TradeOffer(BaseModel):
    id: str
    initiator_id: str
    recipient_id: str
    seller_id: str
    buyer_id: str
    tile_id: int
    price: int
    status: TradeOfferStatus = TradeOfferStatus.PENDING


class Player(BaseModel):
    id: str
    name: str
    money: int = 1500
    position: int = 0
    properties: list[int] = Field(default_factory=list)
    transport_count: int = 0
    in_jail: bool = False
    jail_turns: int = 0
    loans: list[Loan] = Field(default_factory=list)
    refusals_used: int = 0
    is_connected: bool = False
    is_active: bool = True


class Tile(BaseModel):
    id: int
    name: str
    type: TileType
    price: int = 0
    base_rent: int = 0
    group_id: Optional[str] = None
    owner_id: Optional[str] = None
    houses: int = 0

    @property
    def is_purchasable(self) -> bool:
        return self.type in {TileType.PROPERTY, TileType.TRANSPORT}


class EventCard(BaseModel):
    id: str
    title: str
    effect: EventEffect
    amount: int = 0
    target_position: Optional[int] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class Auction(BaseModel):
    tile_id: int
    initiator_id: str
    current_price: int
    participants: list[str] = Field(default_factory=list)
    passed_players: list[str] = Field(default_factory=list)
    current_winner: Optional[str] = None
    active: bool = True


class GameState(BaseModel):
    id: str
    name: str = "Новый стол"
    players: list[Player] = Field(default_factory=list)
    board: list[Tile]
    current_turn: int = 0
    dice: Optional[DiceResult] = None
    phase: GamePhase = GamePhase.WAITING_FOR_PLAYERS
    round: int = 0
    events_deck: list[EventCard] = Field(default_factory=list)
    auction: Optional[Auction] = None
    loan_offers: list[LoanOffer] = Field(default_factory=list)
    trade_offers: list[TradeOffer] = Field(default_factory=list)
    pending_tile_id: Optional[int] = None
    pending_tile_optional: bool = False
    last_event: Optional[str] = None
    max_players: int = 6
