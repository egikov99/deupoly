import asyncio

from app.models.messages import ClientAction, ClientMessage
from app.services.game_manager import GameManager
from app.storage.memory import MemoryGameStorage


def test_game_manager_restores_state_from_storage() -> None:
    async def scenario() -> None:
        storage = MemoryGameStorage()
        await storage.initialize()

        manager = GameManager(storage=storage)
        created = await manager.create_game(max_players=4)
        game_id = created["game_id"]

        await manager.add_player(game_id, "Alice")
        await manager.add_player(game_id, "Bob")
        await manager.start_game(game_id)
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

        await storage.close()

    asyncio.run(scenario())
