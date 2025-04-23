import json
import uuid
from ..database import get_connection, release_connection
from ..config import ai_client_delegate
from ..prompts import (
    load_prompt_template,
    load_multi_character_prompt_template,
    load_long_memory_summary_prompt,
    load_important_memory_extract_prompt,
    load_character_prompt,
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


# 단일 세션 시작
def start_session(universe_id, npcs, player_id, event_id: uuid.UUID | None = None):
    print(f"세션 시작: {universe_id}, {npcs}, {player_id}, {event_id}")
    conn = get_connection()
    print(f"DB 연결: {conn}")
    try:
        with conn.cursor() as cursor:
            session_id = str(uuid.uuid4())
            cursor.execute(
                """
                INSERT INTO "ConversationSession" (id, "universeId", "playerId", "shortMemory", status, "eventId")
                VALUES (%s, %s, %s, %s, %s, %s)
            """,
                (
                    session_id,
                    universe_id,
                    player_id,
                    "[]",
                    "active",
                    str(event_id) if event_id is not None else None,
                ),
            )
            for npc_id in npcs:
                # NPC 세션 생성
                cursor.execute(
                    """
                        INSERT INTO "ConversationSessionNpc" (id, "conversationSessionId", "npcId")
                        VALUES (%s, %s, %s)
                        """,
                    (str(uuid.uuid4()), session_id, str(npc_id)),
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
    # Claude API 메시지 포맷 구성
    messages = []

    # 대화 기록 추가
    for msg in short_memory:
        if msg["role"] == "user":
            messages.append({"role": "user", "content": msg["content"]})
        elif msg["role"] == "assistant":
            messages.append({"role": "assistant", "content": msg["content"]})

    # 플레이어 입력이 있으면 추가
    if player_input:
        messages.append({"role": "user", "content": player_input})

    # system 프롬프트를 ephemeral로 설정
    system = [
        {"type": "text", "text": system_prompt, "cache_control": {"type": "ephemeral"}}
    ]

    return {"system": system, "messages": messages}


def generate_single_npc_dialogue(session_id, player_input, provider="openai"):
    print("generate_single_npc_dialogue")
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT "universeId", "playerId", "shortMemory", "eventId"
                FROM "ConversationSession"
                WHERE id = %s AND status = 'active'
                """,
                (session_id,),
            )
            session = cursor.fetchone()
            if not session:
                return {"error": "세션이 존재하지 않거나 종료됨."}

            cursor.execute(
                """
                    SELECT "npcId"
                    FROM "ConversationSessionNpc"
                    WHERE "conversationSessionId" = %s
                """,
                (session_id,),
            )
            npc_ids = cursor.fetchall()
            if not npc_ids or len(npc_ids) != 1:
                return {"error": "단일 NPC 세션이 아님 (NPC 수가 1이 아님)."}

            npc_id = npc_ids[0][0]

            universe_id, player_id, short_memory_json, event_id = session
            print(f"세션 정보: {session}")

            event_goal_description = None
            event_goal_trigger = None
            if event_id:
                cursor.execute(
                    """
                    SELECT "goalDescription", "goalTrigger"
                    FROM "Event"
                    WHERE id = %s
                    """,
                    (event_id,),
                )
                row = cursor.fetchone()
                if row and row[0]:
                    event_goal_description = row[0]
                    event_goal_trigger = row[1]

            # 컨텍스트 데이터 조회
            npc = get_npc_profile(universe_id, npc_id)
            universe = get_universe_settings(universe_id)
            important_memories = get_important_memories(universe_id, npc_id, player_id)
            summary_memory = get_summary_memory(universe_id, npc_id, player_id)

            formatted_important_memories = (
                "\n".join(f"- {memory}" for memory in important_memories) or "없음"
            )

            npc_prompt_template = load_character_prompt()
            npc_prompt = npc_prompt_template.format(
                npc_name=npc["name"],
                npc_bio=npc["bio"],
                npc_race=npc["race"],
                npc_gender=npc["gender"],
                npc_species=npc["species"],
                summary_memory=summary_memory,
                important_memories=formatted_important_memories,
            )
            # 프롬프트 템플릿 적용
            prompt_template = load_prompt_template()
            system_prompt = prompt_template.format(
                universe_name=universe.get("name", "알 수 없음"),
                universe_description=universe.get("description", "알 수 없음"),
                universe_lore=universe.get("lore", "알 수 없음"),
                universe_rules=universe.get("rules", "없음"),
                player_input=player_input,
                npc_prompt=npc_prompt,
                dialogue_examples="없음",  # FIXME: 대화 예시 추가
                event_goal=event_goal_description or "없음",  # 추가
                goal_trigger=event_goal_trigger or "없음",  # 추가
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

            # EventStep 적용 (단기기억이 없고, event가 연결된 경우)
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

            # Claude 대응: 메시지 구성용 복사본
            if provider == "claude":
                short_memory_for_prompt = short_memory.copy()
                short_memory_for_prompt.append(
                    {"role": "user", "content": player_input}
                )
            else:
                short_memory_for_prompt = short_memory.copy()

            # 메시지 구성
            messages = build_messages(
                provider, system_prompt, short_memory_for_prompt, player_input
            )

            # LLM 호출
            npc_response = generate_npc_dialogue_with_continue(
                messages, provider=provider
            )

            # 메모리 업데이트
            short_memory.append({"role": "user", "content": player_input})
            short_memory.append({"role": "assistant", "content": npc_response})

            if len(short_memory) > MAX_MEMORY_LENGTH:
                short_memory = short_memory[-MAX_MEMORY_LENGTH:]

            # DB 반영
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
        print(f"대화 생성 실패: {e}")
        raise RuntimeError(f"대화 생성 실패: {e}")
    finally:
        release_connection(conn)


def generate_multi_npc_dialogue(session_id, player_input, provider="openai"):
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            # 세션 기본 정보 조회
            cursor.execute(
                """
                SELECT "universeId", "playerId", "shortMemory", "eventId"
                FROM "ConversationSession"
                WHERE id = %s AND status = 'active'
                """,
                (session_id,),
            )
            session = cursor.fetchone()
            if not session:
                return {"error": "세션이 존재하지 않거나 종료됨."}

            # 다중 NPC 조회
            cursor.execute(
                """
                    SELECT "npcId"
                    FROM "ConversationSessionNpc"
                    WHERE "conversationSessionId" = %s
                """,
                (session_id,),
            )
            npc_ids = cursor.fetchall()
            if not npc_ids or len(npc_ids) < 2:
                return {"error": "다중 NPC 세션이 아님 (NPC 수가 2 미만)."}
            universe_id, player_id, short_memory_json, event_id = session

            event_goal_description = None
            event_goal_trigger = None
            if event_id:
                cursor.execute(
                    """
                    SELECT "goalDescription", "goalTrigger"
                    FROM "Event"
                    WHERE id = %s
                    """,
                    (event_id,),
                )
                row = cursor.fetchone()
                if row and row[0]:
                    event_goal_description = row[0]
                    event_goal_trigger = row[1]

            # NPC 리스트 구성
            npcs = []
            for npc_id in npc_ids:
                npc = get_npc_profile(universe_id, npc_id)
                npc["id"] = npc_id[0]  # NPC ID 추가
                npcs.append(npc)
            if not npcs:
                return {"error": "NPC 정보를 불러오는 데 실패했습니다."}

            # Universe 정보
            universe = get_universe_settings(universe_id)
            # NPC별 기억 정보 조회
            npc_prompt_template = load_character_prompt()
            npc_profiles = []
            for npc in npcs:
                npc_id = npc["id"]
                summary_memory = get_summary_memory(universe_id, npc_id, player_id)
                important_memories = get_important_memories(
                    universe_id, npc_id, player_id
                )
                formatted_important_memories = (
                    "\n".join(f"- {memory}" for memory in important_memories) or "없음"
                )
                # NPC 프로필 생성
                npc_prompt = npc_prompt_template.format(
                    npc_name=npc["name"],
                    npc_bio=npc["bio"],
                    npc_race=npc["race"],
                    npc_gender=npc["gender"],
                    npc_species=npc["species"],
                    summary_memory=summary_memory,
                    important_memories=formatted_important_memories,
                )
                npc_profiles.append(npc_prompt)

            # 프롬프트 템플릿 적용 (다중 캐릭터용)
            prompt_template = load_multi_character_prompt_template()

            system_prompt = prompt_template.format(
                universe_name=universe.get("name", "알 수 없음"),
                universe_description=universe.get("description", ""),
                universe_lore=universe.get("lore", ""),
                universe_rules=universe.get("rules", ""),
                npc_profiles="\n\n".join(npc_profiles),
                player_input=player_input,
                dialogue_examples="없음",  # FIXME: 대화 예시 추가
                event_goal=event_goal_description or "없음",  # 추가
                goal_trigger=event_goal_trigger or "없음",  # 추가
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

            # 이벤트 스텝 적용 (shortMemory 비어있고 이벤트 연결된 경우)
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
                            # npcs에서 npc_id를 찾고, 해당 npc의 이름을 가져옴
                            npc_name = "알 수 없음"
                            for npc in npcs:
                                if npc["id"] == speaker_id:
                                    npc_name = npc["name"]
                                    break
                            event_message = f"{npc_name}: {event_message}"
                            short_memory.append(
                                {"role": "assistant", "content": event_message}
                            )
                        else:
                            event_message = f"{speaker_type}: {event_message}"
                            short_memory.append(
                                {"role": "assistant", "content": event_message}
                            )

            # Claude용 복사
            if provider == "claude":
                short_memory_for_prompt = short_memory.copy()
                short_memory_for_prompt.append(
                    {"role": "user", "content": player_input}
                )
            else:
                short_memory_for_prompt = short_memory.copy()

            # 메시지 구성 및 호출
            messages = build_messages(
                provider, system_prompt, short_memory_for_prompt, player_input
            )
            response = generate_npc_dialogue_with_continue(messages, provider=provider)

            # 메모리 갱신
            short_memory.append({"role": "user", "content": player_input})
            short_memory.append({"role": "assistant", "content": response})

            if len(short_memory) > MAX_MEMORY_LENGTH:
                short_memory = short_memory[-MAX_MEMORY_LENGTH:]

            cursor.execute(
                """
                UPDATE "ConversationSession"
                SET "shortMemory" = %s
                WHERE id = %s
                """,
                (json.dumps(short_memory), session_id),
            )
            conn.commit()

        return response

    except Exception as e:
        conn.rollback()
        raise RuntimeError(f"다중 대화 생성 실패: {e}")
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


def generate_npc_dialogue(session_id, player_input, provider="openai"):
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                    SELECT COUNT(*) FROM "ConversationSessionNpc"
                    WHERE "conversationSessionId" = %s
                """,
                (session_id,),
            )
            npc_count = cursor.fetchone()[0]
            if npc_count == 1:
                return generate_single_npc_dialogue(session_id, player_input, provider)
            elif npc_count > 1:
                return generate_multi_npc_dialogue(session_id, player_input, provider)
            else:
                return {"error": "세션에 포함된 NPC가 없습니다."}
    except Exception as e:
        conn.rollback()
        raise RuntimeError(f"대화 생성 실패: {e}")
    finally:
        release_connection(conn)
