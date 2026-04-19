from typing import Optional

from pydantic import BaseModel, Field


class UserCredentialsRequest(BaseModel):
    username: str = Field(min_length=3, max_length=32)
    password: str = Field(min_length=6, max_length=128)


class UserPublic(BaseModel):
    id: str
    username: str
    is_admin: bool = False


class UserStats(BaseModel):
    games_played: int = 0
    current_games: int = 0
    wins: int = 0
    losses: int = 0


class UserProfile(UserPublic):
    stats: UserStats


class AuthResponse(BaseModel):
    user: UserProfile


class AdminCreateUserRequest(UserCredentialsRequest):
    is_admin: bool = False


class CreateGameRequest(BaseModel):
    max_players: int = Field(default=4, ge=2, le=6)
    player_name: Optional[str] = Field(default=None, min_length=1, max_length=32)


class JoinGameRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=32)


class GameSummary(BaseModel):
    game_id: str
    phase: str
    round: int
    player_count: int
    max_players: int
    players: list[str]
    joined: bool
    player_id: Optional[str] = None
    player_name: Optional[str] = None
    can_join: bool
    can_start: bool
    updated_at: Optional[str] = None


class UserSummary(UserProfile):
    pass
