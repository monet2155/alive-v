from ..database import get_connection, release_connection
from ..config import client


def get_npc_profile(universe_id, npc_id):
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT name, bio, race, gender, species
                FROM "Npc"
                WHERE "id" = %s AND "universeId" = %s
            """,
                (npc_id, universe_id),
            )
            row = cursor.fetchone()
            return (
                dict(zip(["name", "bio", "race", "gender", "species"], row))
                if row
                else {}
            )
    except Exception as e:
        raise RuntimeError(f"NPC 프로필 조회 실패: {e}")
    finally:
        release_connection(conn)


def get_universe_settings(universe_id):
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT description, lore, rules
                FROM "UniverseSetting"
                JOIN "Universe" ON "UniverseSetting"."universeId" = "Universe"."id"
                WHERE "Universe"."id" = %s
            """,
                (universe_id,),
            )
            row = cursor.fetchone()
            return dict(zip(["description", "lore", "rules"], row)) if row else {}
    except Exception as e:
        raise RuntimeError(f"세계관 설정 조회 실패: {e}")
    finally:
        release_connection(conn)


def generate_npc_dialogue_with_continue(messages, max_tokens=500, temperature=0.7):
    npc_response = ""
    finish_reason = "length"

    while finish_reason == "length":
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )

        chunk = response.choices[0].message.content
        finish_reason = response.choices[0].finish_reason

        npc_response += chunk
        messages.append({"role": "assistant", "content": chunk})

    return npc_response
