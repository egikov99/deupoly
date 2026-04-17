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
