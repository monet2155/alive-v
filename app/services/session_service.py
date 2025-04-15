import json
import uuid
from ..database import get_connection, release_connection
from ..config import ai_client_delegate
from ..prompts import (
    load_prompt_template,
    load_long_memory_summary_prompt,
    load_important_memory_extract_prompt,
)
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


def start_session(universe_id, npc_id, player_id, event_id: str | None = None):
    print(f"세션 시작: {universe_id}, {npc_id}, {player_id}")
    conn = get_connection()
    print(f"DB 연결: {conn}")
    try:
        with conn.cursor() as cursor:
            session_id = str(uuid.uuid4())
            cursor.execute(
                """
                INSERT INTO "ConversationSession" (id, "universeId", "npcId", "playerId", "shortMemory", status, "eventId")
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
                (session_id, universe_id, npc_id, player_id, "[]", "active", event_id),
            )
            conn.commit()
        return session_id
    except Exception as e:
        conn.rollback()
        raise RuntimeError(f"세션 생성 실패: {e}")
    finally:
        release_connection(conn)


def build_messages(provider, system_prompt, short_memory, player_input):
    if provider == "openai":
        messages = [{"role": "system", "content": system_prompt}]
        messages += short_memory
        messages.append({"role": "user", "content": player_input})  # ✔️ 여기만 추가
        return messages

    elif provider == "claude":
        return build_claude_message(
            system_prompt, short_memory
        )  # ❌ player_input 다시 넣지 않음

    else:
        raise ValueError(f"지원하지 않는 provider: {provider}")


def build_claude_message(system_prompt, short_memory, player_input=None):
    history_str = ""
    for msg in short_memory:
        if msg["role"] == "user":
            history_str += f"\n플레이어: {msg['content']}"
        elif msg["role"] == "assistant":
            history_str += f"\n{msg['content']}"

    # ⚠️ 여기서 player_input은 이미 short_memory에 들어간 상태이므로 따로 추가하지 않음
    return [
        {
            "role": "user",
            "content": f"""{system_prompt}

# Current Role-play
{history_str}
""",
        }
    ]


def generate_npc_dialogue(session_id, player_input, provider="openai"):
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT "universeId", "npcId", "playerId", "shortMemory", "eventId"
                FROM "ConversationSession"
                WHERE id = %s AND status = 'active'
                """,
                (session_id,),
            )
            session = cursor.fetchone()
            if not session:
                return {"error": "세션이 존재하지 않거나 종료됨."}

            universe_id, npc_id, player_id, short_memory_json, event_id = session

            # 컨텍스트 데이터 조회
            npc = get_npc_profile(universe_id, npc_id)
            universe = get_universe_settings(universe_id)
            important_memories = get_important_memories(universe_id, npc_id, player_id)
            summary_memory = get_summary_memory(universe_id, npc_id, player_id)

            formatted_important_memories = (
                "\n".join(f"- {memory}" for memory in important_memories) or "없음"
            )

            # 프롬프트 템플릿 적용
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

            # 단기 기억 불러오기
            try:
                if isinstance(short_memory_json, str):
                    short_memory = json.loads(short_memory_json)
                elif isinstance(short_memory_json, list):
                    short_memory = short_memory_json
                else:
                    short_memory = []
            except (json.JSONDecodeError, TypeError):
                short_memory = []

            if event_id and len(short_memory) == 0:
                cursor.execute(
                    """
                    SELECT message, "speakerType", "speakerId"
                    FROM "EventStep"
                    WHERE "eventId" = %s
                    ORDER BY "order" ASC
                    """,
                    (str(event_id),),
                )
                step_rows = cursor.fetchall()
                if step_rows:
                    print(f"이벤트 메시지 {len(step_rows)}개 로드됨")
                    for step_row in step_rows:
                        event_message = step_row[0]
                        speaker_type = step_row[1]
                        speaker_id = step_row[2]
                        print(
                            f"이벤트 메시지: {speaker_type}({speaker_id}) {event_message}"
                        )
                        if speaker_type == "PLAYER":
                            short_memory.append(
                                {"role": "user", "content": event_message}
                            )
                        elif speaker_type == "NPC":
                            # NPC의 경우, NPC ID를 기반으로 NPC Name 확인하여 short_memory에 추가
                            npc_name = (
                                npc["name"] if speaker_id == npc_id else "알 수 없음"
                            )
                            event_message = f"{npc_name}: {event_message}"
                        else:
                            event_message = f"{speaker_type}: {event_message}"

                        short_memory.append(
                            {"role": "assistant", "content": event_message}
                        )

            print(f"단기 기억: {short_memory}")

            # 2. Claude일 경우 prompt 조립용으로 미리 복사 & append
            if provider == "claude":
                short_memory_for_prompt = short_memory.copy()
                short_memory_for_prompt.append(
                    {"role": "user", "content": player_input}
                )
            else:
                short_memory_for_prompt = short_memory.copy()

            # 3. 메시지 구성 (Claude에선 player_input 없이 메시지 구성됨)
            messages = build_messages(
                provider, system_prompt, short_memory_for_prompt, player_input
            )

            # 4. LLM 호출
            npc_response = generate_npc_dialogue_with_continue(
                messages, provider=provider
            )

            # 5. 최종 short_memory 저장용 업데이트 (공통)
            short_memory.append({"role": "user", "content": player_input})
            short_memory.append({"role": "assistant", "content": npc_response})

            if len(short_memory) > MAX_MEMORY_LENGTH:
                short_memory = short_memory[-MAX_MEMORY_LENGTH:]

            # DB에 업데이트
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


def generate_long_memory(short_memory_json, provider="openai"):
    if isinstance(short_memory_json, str):
        short_memory = json.loads(short_memory_json)
    else:
        short_memory = short_memory_json

    memory_text = "\n".join(
        f"{'플레이어' if msg['role'] == 'user' else 'NPC'}: {msg['content']}"
        for msg in short_memory
    )

    long_memory_prompt = load_long_memory_summary_prompt()
    summary_prompt = long_memory_prompt.format(conversation_history=memory_text)

    response = ai_client_delegate.generate_response(
        provider=provider,
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": summary_prompt}],
        max_tokens=300,
        temperature=0.5,
    )
    return response.choices[0].message.content


def extract_important_memory(short_memory_json, provider="openai"):
    if isinstance(short_memory_json, str):
        short_memory = json.loads(short_memory_json)
    else:
        short_memory = short_memory_json

    memory_text = "\n".join(
        f"{'플레이어' if msg['role'] == 'user' else 'NPC'}: {msg['content']}"
        for msg in short_memory
    )

    important_memory_prompt = load_important_memory_extract_prompt()
    important_prompt = important_memory_prompt.format(
        conversation_history=memory_text,
    )

    response = ai_client_delegate.generate_response(
        provider=provider,
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": important_prompt}],
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
