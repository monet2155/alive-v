from ..database import cursor
from datetime import datetime
import uuid


def get_important_memories(universe_id, npc_id, player_id):
    cursor.execute(
        """
        SELECT content FROM "ImportantMemory"
        WHERE "universeId" = %s AND "npcId" = %s AND "playerId" = %s
        ORDER BY "createdAt" ASC LIMIT 5
    """,
        (universe_id, npc_id, player_id),
    )
    return [row[0] for row in cursor.fetchall()]


def get_summary_memory(universe_id, npc_id, player_id):
    cursor.execute(
        """
        SELECT content
        FROM "SummaryMemory"
        WHERE "universeId" = %s AND "npcId" = %s AND "playerId" = %s
    """,
        (universe_id, npc_id, player_id),
    )
    row = cursor.fetchone()
    return row[0] if row else "없음"
