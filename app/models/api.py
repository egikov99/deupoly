from pydantic import BaseModel, Field


class CreateGameRequest(BaseModel):
    max_players: int = Field(default=4, ge=2, le=6)


class JoinGameRequest(BaseModel):
    name: str = Field(min_length=1, max_length=32)

