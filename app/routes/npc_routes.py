from fastapi import APIRouter, HTTPException
from pydantic import UUID4
from ..models import DialogueRequest, SessionStartRequest
from ..services.session_service import start_session, generate_npc_dialogue, end_session

router = APIRouter()


@router.post("/npc/{universe_id}/{npc_id}/start-session")
def start_npc_session(universe_id: UUID4, npc_id: UUID4, body: SessionStartRequest):
    print(
        f"Starting session for universe_id: {universe_id}, npc_id: {npc_id}, player_id: {body.player_id}"
    )
    try:
        session_id = start_session(str(universe_id), str(npc_id), str(body.player_id))
        return {"session_id": session_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/npc/{session_id}/dialogue")
def dialogue_npc(session_id: UUID4, body: DialogueRequest, provider: str = "openai"):
    try:
        dialogue = generate_npc_dialogue(
            str(session_id), body.player_input, provider=provider
        )
        if isinstance(dialogue, dict) and dialogue.get("error"):
            raise HTTPException(status_code=404, detail=dialogue["error"])
        return {"session_id": str(session_id), "dialogue": dialogue}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/npc/{session_id}/end-session")
def end_npc_session(session_id: UUID4, provider: str = "openai"):
    try:
        result = end_session(str(session_id), provider=provider)
        return result
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
