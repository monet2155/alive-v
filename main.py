import os
import json
import uuid
import psycopg2
from fastapi import FastAPI, HTTPException
from openai import OpenAI
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime

load_dotenv()

openai_api_key = os.getenv("OPENAI_API_KEY")
database_url = os.getenv("DATABASE_URL")

client = OpenAI(api_key=openai_api_key)
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 개발 중에는 모든 출처 허용
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# PostgreSQL 연결
conn = psycopg2.connect(database_url)
cursor = conn.cursor()


def load_prompt_template():
    with open("prompt_template.txt", "r", encoding="utf-8") as file:
        return file.read()


def get_universe_settings(universe_id):
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
    if row:
        return {
            "description": row[0],
            "lore": row[1],
            "rules": row[2],
        }
    return {}


def get_npc_profile(universe_id, npc_id):
    cursor.execute(
        """
        SELECT name, bio, race, gender, species
        FROM "Npc"
        WHERE "id" = %s AND "universeId" = %s
    """,
        (npc_id, universe_id),
    )
    row = cursor.fetchone()
    if row:
        return {
            "name": row[0],
            "bio": row[1],
            "race": row[2],
            "gender": row[3],
            "species": row[4],
        }
    return {}


def get_important_memories(universe_id, npc_id, player_id):
    cursor.execute(
        """
        SELECT content
        FROM "ImportantMemory"
        WHERE "universeId" = %s AND "npcId" = %s AND "playerId" = %s
        ORDER BY "createdAt" ASC
        LIMIT 5
        """,
        (universe_id, npc_id, player_id),
    )
    rows = cursor.fetchall()
    return [row[0] for row in rows]


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


def generate_npc_dialogue(session_id: str, player_input: str):
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
    if not npc:
        return {"error": "NPC not found"}

    universe = get_universe_settings(universe_id)
    important_memories = get_important_memories(universe_id, npc_id, player_id)
    summary_memory = get_summary_memory(universe_id, npc_id, player_id)

    # 중요 기억 포맷팅
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

    if isinstance(short_memory_json, str):
        short_memory = json.loads(short_memory_json)
    else:
        short_memory = short_memory_json

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


def update_summary_memory(universe_id, npc_id, player_id):
    # 최근 longMemory 5개 가져오기
    cursor.execute(
        """
        SELECT "longMemory"
        FROM "ConversationSession"
        WHERE "universeId" = %s AND "npcId" = %s AND "playerId" = %s AND "longMemory" != ''
        ORDER BY "endedAt" DESC
        LIMIT 5
        """,
        (universe_id, npc_id, player_id),
    )
    rows = cursor.fetchall()
    memories = [row[0] for row in rows]

    if not memories:
        return

    prompt = "다음 대화 요약들을 바탕으로 플레이어와의 관계와 분위기를 한 문장으로 요약해줘:\n" + "\n".join(
        memories
    )

    summary_response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=150,
        temperature=0.5,
    )
    new_summary = summary_response.choices[0].message.content

    # 현재 시간
    now = datetime.utcnow()

    # SummaryMemory 업데이트 또는 생성
    cursor.execute(
        """
        INSERT INTO "SummaryMemory" (id, "universeId", "npcId", "playerId", content, "updatedAt")
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT ("universeId", "npcId", "playerId")
        DO UPDATE SET content = EXCLUDED.content, "updatedAt" = NOW()
        """,
        (str(uuid.uuid4()), universe_id, npc_id, player_id, new_summary, now),
    )
    conn.commit()


@app.post("/npc/{universe_id}/{npc_id}/start-session")
def start_session(universe_id: str, npc_id: str, player_id: str):
    session_id = str(uuid.uuid4())
    cursor.execute(
        """
        INSERT INTO "ConversationSession" (id, "universeId", "npcId", "playerId", "shortMemory", status)
        VALUES (%s, %s, %s, %s, %s, %s)
        """,
        (session_id, universe_id, npc_id, player_id, "[]", "active"),
    )
    conn.commit()
    return {"session_id": session_id}


class DialogueRequest(BaseModel):
    player_input: str


@app.post("/npc/{session_id}/dialogue")
def chat_with_npc(session_id: str, body: DialogueRequest):
    player_input = body.player_input
    dialogue = generate_npc_dialogue(session_id, player_input)
    if isinstance(dialogue, dict) and dialogue.get("error"):
        raise HTTPException(status_code=404, detail=dialogue["error"])
    return {"session_id": session_id, "dialogue": dialogue}


@app.post("/npc/{session_id}/end-session")
def end_session(session_id: str):
    # 세션 조회
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
        raise HTTPException(status_code=404, detail="세션이 존재하지 않거나 종료됨.")

    universe_id, npc_id, player_id, short_memory = session

    # 요약용 프롬프트 생성
    memory_text = "\n".join(
        [
            f"{'플레이어' if msg['role'] == 'user' else 'NPC'}: {msg['content']}"
            for msg in short_memory
        ]
    )

    # ✅ 1️⃣ longMemory 생성
    summary_prompt = (
        "다음 대화를 한글로 간단히 요약해줘. 중요한 사건, 관계 변화 중심으로:\n"
        + memory_text
    )
    summary_response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": summary_prompt}],
        max_tokens=300,
        temperature=0.5,
    )
    long_memory = summary_response.choices[0].message.content

    # ✅ 2️⃣ 중요 기억 추출
    important_prompt = (
        "다음 대화에서 중요한 사건이나 관계 변화가 있었나요?\n"
        "있다면 한 문장으로 요약해줘.\n"
        "없다면 'false'이라고 답해.\n\n" + memory_text
    )
    important_response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": important_prompt}],
        max_tokens=150,
        temperature=0.5,
    )
    important_memory = important_response.choices[0].message.content.strip()

    # ✅ 3️⃣ 중요 기억 저장 (있을 때만)
    if important_memory != "false":
        cursor.execute(
            """
            INSERT INTO "ImportantMemory" (id, "universeId", "npcId", "playerId", content)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (str(uuid.uuid4()), universe_id, npc_id, player_id, important_memory),
        )

    # ✅ 4️⃣ 세션 종료 처리
    cursor.execute(
        """
        UPDATE "ConversationSession"
        SET status = 'ended', "longMemory" = %s, "endedAt" = NOW()
        WHERE id = %s
        """,
        (long_memory, session_id),
    )
    conn.commit()

    # ✅ summaryMemory 갱신
    update_summary_memory(universe_id, npc_id, player_id)

    return {
        "status": "ended",
        "long_memory": long_memory,
        "important_memory": important_memory if important_memory != "없음" else None,
    }
