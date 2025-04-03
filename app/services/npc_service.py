from ..database import get_connection, release_connection
from ..config import client, ai_client_delegate  # 대리자 추가


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


def generate_npc_dialogue_with_continue(
    messages, provider="openai", max_tokens=500, temperature=0.7
):
    if provider == "openai":
        npc_response = ""
        finish_reason = "length"

        while finish_reason == "length":
            response = ai_client_delegate.generate_response(
                provider=provider,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )

            chunk = response.choices[0].message.content
            finish_reason = response.choices[0].finish_reason

            npc_response += chunk
            messages.append({"role": "assistant", "content": chunk})

        return npc_response

    elif provider == "claude":
        response = ai_client_delegate.generate_response(
            provider=provider,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )

        # Claude 응답 구조 예시: {"content": [{"type": "text", "text": "..."}]}
        contents = response.content  # 이건 Claude SDK 기준임
        text_chunks = [c.text for c in contents if c.type == "text"]
        npc_response = "".join(text_chunks)

        return npc_response

    else:
        raise ValueError(f"지원하지 않는 provider: {provider}")
