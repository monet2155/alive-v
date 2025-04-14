from fastapi import APIRouter, HTTPException
from ..services.event_service import get_event_by_id

router = APIRouter()


@router.get("/event/{event_id}")
def get_event(event_id: str):
    try:
        event = get_event_by_id(event_id)
        if not event:
            raise HTTPException(status_code=404, detail="Event not found")
        return event
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
