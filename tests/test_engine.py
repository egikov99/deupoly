import pytest

from app.core.exceptions import InvalidActionError
from app.core.engine import GameEngine
from app.models.domain import DiceResult, GamePhase
from app.models.messages import ClientAction


def test_player_can_buy_unowned_property() -> None:
    engine = GameEngine(game_id="game-buy")
    first = engine.add_player("Alice")
    engine.add_player("Bob")
    engine.game.phase = GamePhase.WAITING_FOR_ROLL
    engine.game.round = 1
    engine.game.current_turn = 0
    first.position = 39

    engine._make_dice = lambda: DiceResult(first=1, second=1, total=2, is_double=True)  # type: ignore[method-assign]
    engine.process_action(first.id, ClientAction.ROLL_DICE)

    assert engine.game.pending_tile_id == 1
    assert engine.game.phase == GamePhase.WAITING_FOR_ACTION

    engine.process_action(first.id, ClientAction.BUY_PROPERTY)

    bought_tile = engine.game.board[1]
    assert bought_tile.owner_id == first.id
    assert bought_tile.id in first.properties
    assert first.money == 1580


def test_player_pays_rent_to_owner() -> None:
    engine = GameEngine(game_id="game-rent")
    owner = engine.add_player("Alice")
    visitor = engine.add_player("Bob")
    engine.game.phase = GamePhase.WAITING_FOR_ROLL
    engine.game.round = 1
    engine.game.current_turn = 1

    tile = engine.game.board[1]
    tile.owner_id = owner.id
    owner.properties.append(tile.id)
    visitor.position = 0

    engine._make_dice = lambda: DiceResult(first=1, second=2, total=3, is_double=False)  # type: ignore[method-assign]
    visitor.position = 0
    engine._move_player(visitor, 1)

    assert visitor.money == 1500 - tile.base_rent
    assert owner.money == 1500 + tile.base_rent


def test_auction_assigns_tile_to_winner() -> None:
    engine = GameEngine(game_id="game-auction")
    initiator = engine.add_player("Alice")
    bidder = engine.add_player("Bob")
    engine.game.phase = GamePhase.WAITING_FOR_ACTION
    engine.game.round = 1
    engine.game.current_turn = 0
    engine.game.pending_tile_id = 1

    tile = engine.game.board[1]
    engine.process_action(initiator.id, ClientAction.START_AUCTION)
    engine.process_action(bidder.id, ClientAction.PLACE_BID, {"bid": 130})

    assert tile.owner_id == bidder.id
    assert tile.id in bidder.properties
    assert bidder.money == 1500 - 130
    assert initiator.money == 1501
    assert engine.game.auction is None


def test_player_can_buy_after_declining_if_tile_stays_free() -> None:
    engine = GameEngine(game_id="game-decline-rebuy")
    player = engine.add_player("Alice")
    engine.add_player("Bob")
    engine.game.phase = GamePhase.WAITING_FOR_ACTION
    engine.game.round = 1
    engine.game.current_turn = 0
    engine.game.pending_tile_id = 1

    engine.process_action(player.id, ClientAction.DECLINE_PROPERTY)

    assert engine.game.pending_tile_id == 1
    assert engine.game.pending_tile_optional is True

    engine.process_action(player.id, ClientAction.BUY_PROPERTY)

    assert engine.game.board[1].owner_id == player.id
    assert engine.game.pending_tile_id is None


def test_player_can_buy_after_auction_without_sale() -> None:
    engine = GameEngine(game_id="game-auction-rebuy")
    initiator = engine.add_player("Alice")
    bidder = engine.add_player("Bob")
    engine.game.phase = GamePhase.WAITING_FOR_ACTION
    engine.game.round = 1
    engine.game.current_turn = 0
    engine.game.pending_tile_id = 1

    engine.process_action(initiator.id, ClientAction.START_AUCTION)
    engine.process_action(bidder.id, ClientAction.PASS_AUCTION)

    assert engine.game.auction is None
    assert engine.game.pending_tile_id == 1
    assert engine.game.pending_tile_optional is True

    engine.process_action(initiator.id, ClientAction.BUY_PROPERTY)

    assert engine.game.board[1].owner_id == initiator.id


def test_bank_loan_can_be_repaid_early_with_reduced_interest() -> None:
    engine = GameEngine(game_id="game-bank-loan")
    player = engine.add_player("Alice")
    engine.add_player("Bob")
    engine.game.phase = GamePhase.WAITING_FOR_ACTION
    engine.game.round = 1

    engine.process_action(player.id, ClientAction.TAKE_BANK_LOAN, {"amount": 1000})

    loan = player.loans[0]
    loan.remaining_turns = 5
    engine.process_action(player.id, ClientAction.REPAY_LOAN, {"loan_id": loan.id})

    assert player.money == 1425
    assert player.loans == []


def test_bank_loan_can_only_be_taken_on_player_turn() -> None:
    engine = GameEngine(game_id="game-bank-turn")
    current = engine.add_player("Alice")
    other = engine.add_player("Bob")
    engine.game.phase = GamePhase.WAITING_FOR_ACTION
    engine.game.round = 1
    engine.game.current_turn = 0

    with pytest.raises(InvalidActionError, match="только в свой ход"):
        engine.process_action(other.id, ClientAction.TAKE_BANK_LOAN, {"amount": 100})

    engine.process_action(current.id, ClientAction.TAKE_BANK_LOAN, {"amount": 100})

    assert current.money == 1600
    assert len(current.loans) == 1


def test_bank_loan_overdue_extends_once_then_bankrupts_player() -> None:
    engine = GameEngine(game_id="game-bank-overdue")
    player = engine.add_player("Alice")
    engine.add_player("Bob")
    engine.game.phase = GamePhase.WAITING_FOR_ACTION
    engine.game.round = 1

    engine.process_action(player.id, ClientAction.TAKE_BANK_LOAN, {"amount": 1000})
    loan = player.loans[0]
    player.money = 0
    loan.remaining_turns = 1

    engine._process_loans(player)

    assert player.is_active is True
    assert loan.overdue_applied is True
    assert loan.remaining_turns == 4
    assert player.loans == [loan]

    loan.remaining_turns = 1
    engine._process_loans(player)

    assert player.is_active is False
    assert player.loans == []


def test_player_loan_requires_collateral_and_transfers_it_on_default() -> None:
    engine = GameEngine(game_id="game-player-loan")
    borrower = engine.add_player("Alice")
    lender = engine.add_player("Bob")
    engine.game.phase = GamePhase.WAITING_FOR_ACTION
    engine.game.round = 1
    engine.game.board[1].owner_id = borrower.id
    engine.game.board[2].owner_id = borrower.id
    engine._refresh_player_assets()

    engine.process_action(
        borrower.id,
        ClientAction.PROPOSE_PLAYER_LOAN,
        {"lender_id": lender.id, "amount": 300, "collateral_tile_ids": [1, 2]},
    )
    offer = engine.game.loan_offers[0]
    engine.process_action(lender.id, ClientAction.ACCEPT_PLAYER_LOAN, {"offer_id": offer.id})

    assert lender.money == 1200
    assert borrower.money == 1800
    assert engine.game.loan_offers == []
    assert borrower.loans[0].collateral_tile_ids == [1, 2]

    borrower.money = 0
    borrower.loans[0].remaining_turns = 1
    engine._process_loans(borrower)

    assert borrower.loans == []
    assert engine.game.board[1].owner_id == lender.id
    assert engine.game.board[2].owner_id == lender.id
    assert 1 not in borrower.properties
    assert 2 not in borrower.properties
    assert 1 in lender.properties
    assert 2 in lender.properties


def test_player_loan_rejects_missing_foreign_or_pledged_collateral() -> None:
    engine = GameEngine(game_id="game-player-loan-validation")
    borrower = engine.add_player("Alice")
    lender = engine.add_player("Bob")
    engine.game.phase = GamePhase.WAITING_FOR_ACTION
    engine.game.round = 1
    engine.game.board[1].owner_id = borrower.id
    engine.game.board[2].owner_id = lender.id
    engine._refresh_player_assets()

    with pytest.raises(InvalidActionError, match="нужен залог"):
        engine.process_action(
            borrower.id,
            ClientAction.PROPOSE_PLAYER_LOAN,
            {"lender_id": lender.id, "amount": 100},
        )

    with pytest.raises(InvalidActionError, match="только свой актив"):
        engine.process_action(
            borrower.id,
            ClientAction.PROPOSE_PLAYER_LOAN,
            {"lender_id": lender.id, "amount": 100, "collateral_tile_ids": [2]},
        )

    engine.process_action(
        borrower.id,
        ClientAction.PROPOSE_PLAYER_LOAN,
        {"lender_id": lender.id, "amount": 100, "collateral_tile_ids": [1]},
    )

    with pytest.raises(InvalidActionError, match="уже используется"):
        engine.process_action(
            borrower.id,
            ClientAction.PROPOSE_PLAYER_LOAN,
            {"lender_id": lender.id, "amount": 100, "collateral_tile_ids": [1]},
        )


def test_trade_buy_offer_transfers_asset_when_owner_accepts() -> None:
    engine = GameEngine(game_id="game-trade-buy")
    buyer = engine.add_player("Alice")
    seller = engine.add_player("Bob")
    engine.game.phase = GamePhase.WAITING_FOR_ACTION
    engine.game.round = 1
    engine.game.current_turn = 0
    engine.game.board[1].owner_id = seller.id
    engine._refresh_player_assets()

    engine.process_action(
        buyer.id,
        ClientAction.PROPOSE_TRADE,
        {"direction": "buy", "recipient_id": seller.id, "tile_id": 1, "price": 250},
    )
    offer = engine.game.trade_offers[0]
    engine.process_action(seller.id, ClientAction.ACCEPT_TRADE, {"offer_id": offer.id})

    assert engine.game.board[1].owner_id == buyer.id
    assert buyer.money == 1250
    assert seller.money == 1750
    assert engine.game.trade_offers == []


def test_trade_sell_offer_transfers_asset_when_buyer_accepts() -> None:
    engine = GameEngine(game_id="game-trade-sell")
    seller = engine.add_player("Alice")
    buyer = engine.add_player("Bob")
    engine.game.phase = GamePhase.WAITING_FOR_ACTION
    engine.game.round = 1
    engine.game.current_turn = 0
    engine.game.board[1].owner_id = seller.id
    engine._refresh_player_assets()

    engine.process_action(
        seller.id,
        ClientAction.PROPOSE_TRADE,
        {"direction": "sell", "recipient_id": buyer.id, "tile_id": 1, "price": 220},
    )
    offer = engine.game.trade_offers[0]
    engine.process_action(buyer.id, ClientAction.ACCEPT_TRADE, {"offer_id": offer.id})

    assert engine.game.board[1].owner_id == buyer.id
    assert seller.money == 1720
    assert buyer.money == 1280


def test_trade_can_only_be_initiated_on_current_turn_and_not_for_pledged_asset() -> None:
    engine = GameEngine(game_id="game-trade-validation")
    current = engine.add_player("Alice")
    other = engine.add_player("Bob")
    engine.game.phase = GamePhase.WAITING_FOR_ACTION
    engine.game.round = 1
    engine.game.current_turn = 0
    engine.game.board[1].owner_id = current.id
    engine._refresh_player_assets()

    with pytest.raises(InvalidActionError, match="только в свой ход"):
        engine.process_action(
            other.id,
            ClientAction.PROPOSE_TRADE,
            {"direction": "buy", "recipient_id": current.id, "tile_id": 1, "price": 100},
        )

    engine.process_action(
        current.id,
        ClientAction.PROPOSE_PLAYER_LOAN,
        {"lender_id": other.id, "amount": 100, "collateral_tile_ids": [1]},
    )

    with pytest.raises(InvalidActionError, match="залог или в другой сделке"):
        engine.process_action(
            current.id,
            ClientAction.PROPOSE_TRADE,
            {"direction": "sell", "recipient_id": other.id, "tile_id": 1, "price": 100},
        )


def test_turn_end_expires_current_player_loan_and_trade_offers() -> None:
    engine = GameEngine(game_id="game-offer-expiration")
    current = engine.add_player("Alice")
    other = engine.add_player("Bob")
    engine.game.phase = GamePhase.WAITING_FOR_ACTION
    engine.game.round = 1
    engine.game.current_turn = 0
    engine.game.board[1].owner_id = current.id
    engine.game.board[3].owner_id = other.id
    engine._refresh_player_assets()

    engine.process_action(
        current.id,
        ClientAction.PROPOSE_TRADE,
        {"direction": "buy", "recipient_id": other.id, "tile_id": 3, "price": 100},
    )
    engine.process_action(
        current.id,
        ClientAction.PROPOSE_PLAYER_LOAN,
        {"lender_id": other.id, "amount": 100, "collateral_tile_ids": [1]},
    )

    assert len(engine.game.trade_offers) == 1
    assert len(engine.game.loan_offers) == 1

    engine.process_action(current.id, ClientAction.END_TURN)

    assert engine.game.trade_offers == []
    assert engine.game.loan_offers == []
