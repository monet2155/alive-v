from fastapi import APIRouter, HTTPException
from uuid import UUID
from pydantic import UUID4
from ..models import DialogueRequest, SessionStartRequest
from ..services.session_service import start_session, generate_npc_dialogue, end_session

router = APIRouter()


@router.post("/npc/{universe_id}/start-session")
def start_npc_session(universe_id: UUID4, body: SessionStartRequest):
    print(
        f"Starting session for universe_id: {universe_id}, npc_ids: {body.npcs}, player_id: {body.player_id}"
    )
    if not body.npcs or not body.player_id:
        raise HTTPException(
            status_code=400, detail="NPCs and player ID must be provided."
        )
    if not isinstance(body.npcs, list):
        raise HTTPException(status_code=400, detail="NPCs must be a list.")
    if not all(isinstance(npc, UUID) for npc in body.npcs):
        raise HTTPException(status_code=400, detail="All NPCs must be UUID.")
    if not isinstance(body.player_id, UUID):
        raise HTTPException(status_code=400, detail="Player ID must be a UUID.")
    if body.event_id and not isinstance(body.event_id, UUID):
        raise HTTPException(status_code=400, detail="Event ID must be a UUID.")
    try:
        session_id = start_session(
            str(universe_id), body.npcs, str(body.player_id), body.event_id
        )
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
