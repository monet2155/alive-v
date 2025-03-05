import os
import json
import uuid
import psycopg2
from fastapi import FastAPI, HTTPException
from openai import OpenAI
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

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


def generate_npc_dialogue(session_id: str, player_input: str):
    cursor.execute(
        """
        SELECT "universeId", "npcId", "playerId", "shortMemory"
        FROM "ConversationSession"
        WHERE id = %s AND status = 'active'
        """,
        (session_id,),
    )
    print(2)
    session = cursor.fetchone()
    print(3)
    if not session:
        return {"error": "세션이 존재하지 않거나 종료됨."}

    universe_id, npc_id, player_id, short_memory_json = session

    universe = get_universe_settings(universe_id)
    npc = get_npc_profile(universe_id, npc_id)

    if not npc:
        return {"error": "NPC not found"}

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
        long_term_memory="",  # TODO:
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
        SELECT "shortMemory"
        FROM "ConversationSession"
        WHERE id = %s AND status = 'active'
        """,
        (session_id,),
    )
    session = cursor.fetchone()
    if not session:
        raise HTTPException(status_code=404, detail="세션이 존재하지 않거나 종료됨.")

    if isinstance(session[0], str):
        short_memory = json.loads(session[0])
    else:
        short_memory = session[0]

    # 대화 전체 요약 프롬프트 생성
    summary_prompt = (
        "다음 대화를 한글로 간단히 요약해줘. 중요한 사건, 관계 변화 중심으로:\n"
    )
    summary_prompt += "\n".join(
        [f"{msg['role']}: {msg['content']}" for msg in short_memory]
    )

    # GPT로 요약 생성
    summary_response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": summary_prompt}],
        max_tokens=300,
        temperature=0.5,
    )
    long_memory = summary_response.choices[0].message.content

    # 세션 종료 처리
    cursor.execute(
        """
        UPDATE "ConversationSession"
        SET status = 'ended', "longMemory" = %s, "endedAt" = NOW()
        WHERE id = %s
        """,
        (long_memory, session_id),
    )
    conn.commit()

    return {"status": "ended", "long_memory": long_memory}
