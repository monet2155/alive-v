from fastapi import APIRouter, HTTPException
from ..models import DialogueRequest
from ..services.session_service import start_session, generate_npc_dialogue
from ..database import cursor, conn

router = APIRouter()


@router.post("/npc/{universe_id}/{npc_id}/start-session")
def start_npc_session(universe_id: str, npc_id: str, player_id: str):
    session_id = start_session(universe_id, npc_id, player_id)
    return {"session_id": session_id}


@router.post("/npc/{session_id}/dialogue")
def dialogue_npc(session_id: str, body: DialogueRequest):
    player_input = body.player_input
    dialogue = generate_npc_dialogue(session_id, player_input)
    if isinstance(dialogue, dict) and dialogue.get("error"):
        raise HTTPException(status_code=404, detail=dialogue["error"])
    return {"session_id": session_id, "dialogue": dialogue}


@router.post("/npc/{session_id}/end-session")
def end_npc_session(session_id: str):
    cursor.execute(
        """
        UPDATE "ConversationSession"
        SET status = 'ended', "endedAt" = NOW()
        WHERE id = %s
    """,
        (session_id,),
    )
    conn.commit()
    return {"status": "ended"}
