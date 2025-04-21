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
        complete_response = ""
        stop_reason = "max_tokens"
        working_messages = messages.copy()

        # stop_reason이 max_tokens인 경우 계속 응답을 생성합니다
        while stop_reason == "max_tokens":
            response = ai_client_delegate.generate_response(
                provider=provider,
                messages=working_messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )

            # 응답 추출
            new_content = response.content[0].text
            stop_reason = response.stop_reason

            # 공백 제거 - 끝에 있는 공백 문자 제거
            new_content = new_content.rstrip()

            # 전체 응답에 추가
            complete_response += new_content

            # 다음 요청을 위해 메시지 업데이트 (원본 메시지는 유지)
            if stop_reason == "max_tokens":
                # 마지막 메시지가 assistant인지 확인
                assistant_exists = False
                for i in range(len(working_messages) - 1, -1, -1):
                    if working_messages[i]["role"] == "assistant":
                        # 기존 assistant 메시지 업데이트
                        working_messages[i]["content"] = complete_response
                        assistant_exists = True
                        break

                if not assistant_exists:
                    # assistant 메시지가 없으면 새로 추가
                    working_messages.append(
                        {"role": "assistant", "content": complete_response}
                    )

            # 디버깅용 로그 (필요시)
            print(f"Stop reason: {stop_reason}, Added {len(new_content)} chars")

        return complete_response

    else:
        raise ValueError(f"지원하지 않는 provider: {provider}")
