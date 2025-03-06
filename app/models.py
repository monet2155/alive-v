from pydantic import BaseModel


class DialogueRequest(BaseModel):
    player_input: str
