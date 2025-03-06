import json
import uuid
from datetime import datetime
from ..database import cursor, conn
from ..config import client
from ..prompts import load_prompt_template
from .npc_service import get_npc_profile, get_universe_settings
from .memory_service import get_important_memories, get_summary_memory


def start_session(universe_id, npc_id, player_id):
    session_id = str(uuid.uuid4())
    cursor.execute(
        """
        INSERT INTO "ConversationSession" (id, "universeId", "npcId", "playerId", "shortMemory", status)
        VALUES (%s, %s, %s, %s, %s, %s)
    """,
        (session_id, universe_id, npc_id, player_id, "[]", "active"),
    )
    conn.commit()
    return session_id


def generate_npc_dialogue(session_id, player_input):
    cursor.execute(
        """
        SELECT "universeId", "npcId", "playerId", "shortMemory"
        FROM "ConversationSession"
        WHERE id = %s AND status = 'active'
    """,
        (session_id,),
    )
    session = cursor.fetchone()
    if not session:
        return {"error": "세션이 존재하지 않거나 종료됨."}

    universe_id, npc_id, player_id, short_memory_json = session
    npc = get_npc_profile(universe_id, npc_id)
    universe = get_universe_settings(universe_id)
    important_memories = get_important_memories(universe_id, npc_id, player_id)
    summary_memory = get_summary_memory(universe_id, npc_id, player_id)

    formatted_important_memories = (
        "\n".join(f"- {memory}" for memory in important_memories) or "없음"
    )
    prompt_template = load_prompt_template()
    system_prompt = prompt_template.format(
        universe_name=universe.get("name", "알 수 없음"),
        universe_description=universe.get("description", "알 수 없음"),
        universe_lore=universe.get("lore", "알 수 없음"),
        universe_rules=universe.get("rules", "없음"),
        npc_name=npc["name"],
        npc_bio=npc["bio"],
        npc_race=npc["race"],
        npc_gender=npc["gender"],
        npc_species=npc["species"],
        player_input=player_input,
        summary_memory=summary_memory,
        important_memories=formatted_important_memories,
    )

    short_memory = json.loads(short_memory_json)
    short_memory.append({"role": "user", "content": player_input})

    messages = [{"role": "system", "content": system_prompt}] + short_memory

    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=messages,
        max_tokens=100,
        temperature=0.7,
    )

    npc_response = response.choices[0].message.content
    short_memory.append({"role": "assistant", "content": npc_response})

    cursor.execute(
        """
        UPDATE "ConversationSession"
        SET "shortMemory" = %s
        WHERE id = %s
    """,
        (json.dumps(short_memory), session_id),
    )
    conn.commit()

    return npc_response
