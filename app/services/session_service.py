import json
import uuid
from ..database import get_connection, release_connection
from ..config import client
from ..prompts import load_prompt_template
from .npc_service import (
    get_npc_profile,
    get_universe_settings,
    generate_npc_dialogue_with_continue,
)
from .memory_service import (
    get_important_memories,
    get_summary_memory,
    update_summary_memory,
)

MAX_MEMORY_LENGTH = 20


def start_session(universe_id, npc_id, player_id):
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
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
    except Exception as e:
        conn.rollback()
        raise RuntimeError(f"세션 생성 실패: {e}")
    finally:
        release_connection(conn)


def generate_npc_dialogue(session_id, player_input):
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
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

            try:
                if isinstance(short_memory_json, str):
                    short_memory = json.loads(short_memory_json)
                elif isinstance(short_memory_json, list):
                    short_memory = short_memory_json
                else:
                    short_memory = []
            except (json.JSONDecodeError, TypeError):
                short_memory = []

            short_memory.append({"role": "user", "content": player_input})

            if len(short_memory) > MAX_MEMORY_LENGTH:
                short_memory = short_memory[-MAX_MEMORY_LENGTH:]

            messages = [{"role": "system", "content": system_prompt}] + short_memory

            npc_response = generate_npc_dialogue_with_continue(messages)

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
    except Exception as e:
        conn.rollback()
        raise RuntimeError(f"대화 생성 실패: {e}")
    finally:
        release_connection(conn)


def generate_long_memory(short_memory_json):
    if isinstance(short_memory_json, str):
        short_memory = json.loads(short_memory_json)
    else:
        short_memory = short_memory_json

    memory_text = "\n".join(
        f"{'플레이어' if msg['role'] == 'user' else 'NPC'}: {msg['content']}"
        for msg in short_memory
    )

    prompt = (
        "다음 대화를 한글로 간단히 요약해줘. 중요한 사건, 관계 변화 중심으로:\n"
        + memory_text
    )

    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=300,
        temperature=0.5,
    )
    return response.choices[0].message.content


def extract_important_memory(short_memory_json):
    if isinstance(short_memory_json, str):
        short_memory = json.loads(short_memory_json)
    else:
        short_memory = short_memory_json

    memory_text = "\n".join(
        f"{'플레이어' if msg['role'] == 'user' else 'NPC'}: {msg['content']}"
        for msg in short_memory
    )

    prompt = (
        "다음 대화에서 중요한 사건이나 관계 변화가 있었나요?\n"
        "있다면 한 문장으로 요약해줘.\n"
        "없다면 'false'라고 답해.\n\n" + memory_text
    )

    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=150,
        temperature=0.5,
    )
    return response.choices[0].message.content.strip()


def end_session(session_id):
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT "universeId", "npcId", "playerId", "shortMemory"
                FROM "ConversationSession"
                WHERE id = %s AND status = 'active'
            """,
                (str(session_id),),
            )
            session = cursor.fetchone()
            if not session:
                raise ValueError("세션이 존재하지 않거나 종료됨.")

            universe_id, npc_id, player_id, short_memory_json = session

            long_memory = generate_long_memory(short_memory_json)
            important_memory = extract_important_memory(short_memory_json)

            if important_memory != "false":
                cursor.execute(
                    """
                    INSERT INTO "ImportantMemory" (id, "universeId", "npcId", "playerId", content)
                    VALUES (%s, %s, %s, %s, %s)
                """,
                    (
                        str(uuid.uuid4()),
                        str(universe_id),
                        str(npc_id),
                        str(player_id),
                        important_memory,
                    ),
                )

            cursor.execute(
                """
                UPDATE "ConversationSession"
                SET status = 'ended', "longMemory" = %s, "endedAt" = NOW()
                WHERE id = %s
            """,
                (long_memory, str(session_id)),
            )
            conn.commit()

            update_summary_memory(str(universe_id), str(npc_id), str(player_id))

        return {
            "status": "ended",
            "long_memory": long_memory,
            "important_memory": (
                important_memory if important_memory != "false" else None
            ),
        }
    except Exception as e:
        conn.rollback()
        raise RuntimeError(f"세션 종료 실패: {e}")
    finally:
        release_connection(conn)
