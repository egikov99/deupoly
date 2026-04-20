import asyncio

import pytest

from app.core.exceptions import ConflictError, InvalidActionError
from app.services.auth_service import AuthService
from app.storage.memory import MemoryGameStorage


def test_auth_service_registers_and_restores_session() -> None:
    async def scenario() -> None:
        storage = MemoryGameStorage()
        await storage.initialize()
        auth = AuthService(storage=storage, session_ttl_days=30)

        registered = await auth.register(username="alice", password="password123")
        logged_in, session_token, _ = await auth.login(username="alice", password="password123")
        restored = await auth.get_user_by_session(session_token)

        assert registered["username"] == "alice"
        assert logged_in["id"] == registered["id"]
        assert restored == logged_in

        await auth.logout(session_token)
        assert await auth.get_user_by_session(session_token) is None

        await storage.close()

    asyncio.run(scenario())


def test_auth_service_bootstraps_admin_and_lists_users() -> None:
    async def scenario() -> None:
        storage = MemoryGameStorage()
        await storage.initialize()
        auth = AuthService(storage=storage, session_ttl_days=30)

        admin = await auth.ensure_admin("admin", "adminpass123")
        await auth.register(username="bob", password="password123")
        users = await auth.list_users()

        assert admin is not None
        assert admin["is_admin"] is True
        assert any(user["username"] == "admin" and user["is_admin"] for user in users)
        assert any(user["username"] == "bob" and user["stats"]["games_played"] == 0 for user in users)

        await storage.close()

    asyncio.run(scenario())


def test_auth_service_admin_updates_resets_and_deletes_users() -> None:
    async def scenario() -> None:
        storage = MemoryGameStorage()
        await storage.initialize()
        auth = AuthService(storage=storage, session_ttl_days=30)

        admin = await auth.ensure_admin("admin", "adminpass123")
        user = await auth.register(username="bob", password="password123")
        _logged_in, session_token, _ = await auth.login(username="bob", password="password123")

        assert admin is not None
        updated = await auth.update_user(
            user_id=user["id"],
            username="bobby",
            is_admin=True,
            actor_user_id=admin["id"],
        )
        assert updated["username"] == "bobby"
        assert updated["is_admin"] is True

        await auth.reset_user_password(user_id=user["id"], password="newpass123")
        assert await auth.get_user_by_session(session_token) is None

        relogged, _new_session, _ = await auth.login(username="bobby", password="newpass123")
        assert relogged["id"] == user["id"]

        await auth.delete_user(user_id=user["id"], actor_user_id=admin["id"])
        users = await auth.list_users()
        assert all(item["id"] != user["id"] for item in users)

        await storage.close()

    asyncio.run(scenario())


def test_auth_service_admin_user_guards() -> None:
    async def scenario() -> None:
        storage = MemoryGameStorage()
        await storage.initialize()
        auth = AuthService(storage=storage, session_ttl_days=30)

        admin = await auth.ensure_admin("admin", "adminpass123")
        user = await auth.register(username="bob", password="password123")

        assert admin is not None
        with pytest.raises(ConflictError):
            await auth.update_user(
                user_id=user["id"],
                username="admin",
                is_admin=False,
                actor_user_id=admin["id"],
            )

        with pytest.raises(InvalidActionError, match="текущего администратора"):
            await auth.delete_user(user_id=admin["id"], actor_user_id=admin["id"])

        with pytest.raises(InvalidActionError, match="последнего администратора"):
            await auth.update_user(
                user_id=admin["id"],
                username="admin",
                is_admin=False,
                actor_user_id=admin["id"],
            )

        await storage.close()

    asyncio.run(scenario())
