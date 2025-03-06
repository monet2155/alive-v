from pydantic import BaseModel, UUID4


class DialogueRequest(BaseModel):
    player_input: str


class SessionRequest(BaseModel):
    universe_id: UUID4
    npc_id: UUID4
    player_id: UUID4


class SessionStartRequest(BaseModel):
    player_id: UUID4
