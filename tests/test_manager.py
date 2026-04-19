import asyncio

from app.models.domain import GamePhase
from app.models.messages import ClientAction, ClientMessage
from app.services.game_manager import GameManager
from app.storage.memory import MemoryGameStorage


class DummyWebSocket:
    def __init__(self) -> None:
        self.messages = []

    async def send_json(self, payload) -> None:
        self.messages.append(payload)


def test_game_manager_restores_state_from_storage() -> None:
    async def scenario() -> None:
        storage = MemoryGameStorage()
        await storage.initialize()

        manager = GameManager(storage=storage)
        created = await manager.create_game(user_id="user-1", player_name="Alice", max_players=4)
        game_id = created["game_id"]

        await manager.add_player(game_id, "user-2", "Bob")
        await manager.start_game(game_id, "user-1")
        state_before_restart = await manager.get_state(game_id)

        restored_manager = GameManager(storage=storage)
        restored_state = await restored_manager.get_state(game_id)
        current_player_id = restored_state["players"][restored_state["current_turn"]]["id"]

        assert restored_state["id"] == game_id
        assert len(restored_state["players"]) == 2
        assert restored_state == state_before_restart
        assert restored_state["players"][0]["is_connected"] is False

        await restored_manager.handle_message(
            game_id,
            current_player_id,
            ClientMessage(action=ClientAction.ROLL_DICE, payload={}),
        )

        reloaded_after_action = await storage.load_state(game_id)
        assert reloaded_after_action is not None
        assert reloaded_after_action["dice"] is not None

        summaries = await restored_manager.list_games("user-1")
        assert summaries[0]["joined"] is True
        assert summaries[0]["player_name"] == "Alice"

        await storage.close()

    asyncio.run(scenario())


def test_game_manager_reuses_existing_membership_on_rejoin() -> None:
    async def scenario() -> None:
        storage = MemoryGameStorage()
        await storage.initialize()

        manager = GameManager(storage=storage)
        created = await manager.create_game(user_id="user-1", player_name="Alice", max_players=4)
        game_id = created["game_id"]
        player_id = created["player"]["id"]

        rejoined = await manager.add_player(game_id=game_id, user_id="user-1", name="Alice 2")

        assert rejoined["player"]["id"] == player_id
        assert len(rejoined["state"]["players"]) == 1

        await storage.close()

    asyncio.run(scenario())


def test_finished_game_updates_stats_and_is_deleted_after_last_disconnect() -> None:
    async def scenario() -> None:
        storage = MemoryGameStorage()
        await storage.initialize()
        manager = GameManager(storage=storage)

        created = await manager.create_game(user_id="user-1", player_name="Alice", max_players=4)
        game_id = created["game_id"]
        player_one_id = created["player"]["id"]
        joined = await manager.add_player(game_id=game_id, user_id="user-2", name="Bob")
        player_two_id = joined["player"]["id"]

        session = await manager.get_session(game_id)
        session.engine.game.phase = GamePhase.FINISHED
        session.engine.game.players[0].is_active = True
        session.engine.game.players[1].is_active = False
        await manager._persist_session(session)
        await manager._store_results_if_finished(session)

        ws1 = DummyWebSocket()
        ws2 = DummyWebSocket()
        await manager.register(game_id=game_id, user_id="user-1", websocket=ws1)
        await manager.register(game_id=game_id, user_id="user-2", websocket=ws2)

        await manager.unregister(game_id=game_id, player_id=player_one_id, websocket=ws1)
        assert await storage.load_state(game_id) is not None

        await manager.unregister(game_id=game_id, player_id=player_two_id, websocket=ws2)
        assert await storage.load_state(game_id) is None

        alice_stats = await storage.get_user_stats("user-1")
        bob_stats = await storage.get_user_stats("user-2")

        assert alice_stats["games_played"] == 1
        assert alice_stats["wins"] == 1
        assert bob_stats["games_played"] == 1
        assert bob_stats["losses"] == 1

        await storage.close()

    asyncio.run(scenario())
