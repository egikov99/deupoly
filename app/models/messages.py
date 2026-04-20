from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class ClientAction(str, Enum):
    ROLL_DICE = "roll_dice"
    BUY_PROPERTY = "buy_property"
    DECLINE_PROPERTY = "decline_property"
    START_AUCTION = "start_auction"
    PLACE_BID = "place_bid"
    PASS_AUCTION = "pass_auction"
    END_TURN = "end_turn"
    LEAVE_JAIL = "leave_jail"
    TAKE_BANK_LOAN = "take_bank_loan"
    REPAY_LOAN = "repay_loan"
    PROPOSE_PLAYER_LOAN = "propose_player_loan"
    ACCEPT_PLAYER_LOAN = "accept_player_loan"
    REJECT_PLAYER_LOAN = "reject_player_loan"
    PROPOSE_TRADE = "propose_trade"
    ACCEPT_TRADE = "accept_trade"
    REJECT_TRADE = "reject_trade"


class ServerEventType(str, Enum):
    GAME_STATE_UPDATE = "game_state_update"
    DICE_RESULT = "dice_result"
    AUCTION_UPDATE = "auction_update"
    TURN_CHANGE = "turn_change"
    INFO = "info"
    ERROR = "error"


class ClientMessage(BaseModel):
    action: ClientAction
    payload: dict[str, Any] = Field(default_factory=dict)


class ServerEvent(BaseModel):
    type: ServerEventType
    game_id: str
    payload: dict[str, Any] = Field(default_factory=dict)
    state: Optional[dict[str, Any]] = None
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
