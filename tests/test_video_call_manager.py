import asyncio

from app.services.video_call_manager import VideoCallManager


class DummyWebSocket:
    def __init__(self) -> None:
        self.messages = []

    async def send_json(self, payload) -> None:
        self.messages.append(payload)


def test_video_call_manager_connects_and_relays_signal() -> None:
    async def scenario() -> None:
        manager = VideoCallManager()
        ws1 = DummyWebSocket()
        ws2 = DummyWebSocket()
        user1 = {"id": "u1", "username": "alice"}
        user2 = {"id": "u2", "username": "bob"}
        player1 = {"player_id": "p1", "player_name": "Alice"}
        player2 = {"player_id": "p2", "player_name": "Bob"}

        existing_for_first = await manager.connect("game-1", user1, player1, ws1)
        existing_for_second = await manager.connect("game-1", user2, player2, ws2)

        assert existing_for_first == []
        assert existing_for_second == [
            {"user_id": "u1", "player_id": "p1", "username": "alice", "player_name": "Alice"}
        ]
        assert ws1.messages[-1]["type"] == "participant_joined"

        await manager.relay_signal("game-1", user1, "u2", {"description": {"type": "offer"}})
        assert ws2.messages[-1]["type"] == "signal"
        assert ws2.messages[-1]["from_user_id"] == "u1"

        await manager.disconnect("game-1", "u2", ws2)
        assert ws1.messages[-1] == {"type": "participant_left", "user_id": "u2"}

    asyncio.run(scenario())
