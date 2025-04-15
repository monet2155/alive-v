from fastapi import APIRouter, HTTPException
from pydantic import UUID4
from ..services.universe_service import get_npcs_by_universe_id

router = APIRouter()


@router.get("/universe/{universe_id}/npcs")
def get_npcs(universe_id: UUID4):
    try:
        npcs = get_npcs_by_universe_id(str(universe_id))
        if not npcs:
            raise HTTPException(status_code=404, detail="No NPCs found")
        return {"npcs": npcs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
