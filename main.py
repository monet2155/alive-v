import os
import psycopg2
from fastapi import FastAPI
from openai import OpenAI
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware

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


# 외부 파일에서 Prompt 로드
def load_prompt_template():
    with open("prompt_template.txt", "r", encoding="utf-8") as file:
        return file.read()


# universe 정보 가져오기
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


# NPC 프로필 가져오기
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


# 대화 히스토리 임시 저장소
conversation_history = {}


# NPC 대화 생성
def generate_npc_dialogue(universe_id, npc_id, player_input):
    universe = get_universe_settings(universe_id)
    npc = get_npc_profile(universe_id, npc_id)

    if not npc:
        return {"error": "NPC not found"}

    prompt_template = load_prompt_template()

    history = conversation_history.get(f"{universe_id}_{npc_id}", [])[:]
    formatted_history = ""
    for h in history:
        formatted_history += f"플레이어: {h['player']}\nNPC: {h['npc']}\n"

    prompt = prompt_template.format(
        universe_name=universe.get("name", "알 수 없음"),
        universe_description=universe.get("description", "알 수 없음"),
        universe_lore=universe.get("lore", "알 수 없음"),
        universe_rules=universe.get("rules", "없음"),
        npc_name=npc["name"],
        npc_bio=npc["bio"],
        npc_race=npc["race"],
        npc_gender=npc["gender"],
        npc_species=npc["species"],
        previous_conversation=formatted_history,
        player_input=player_input,
    )

    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=100,
        temperature=0.7,
    )

    npc_response = response.choices[0].message.content

    # 대화 히스토리에 저장
    key = f"{universe_id}_{npc_id}"
    conversation_history.setdefault(key, []).append(
        {"player": player_input, "npc": npc_response}
    )

    return npc_response


@app.get("/npc/{universe_id}/{npc_id}/dialogue")
def get_npc_dialogue(universe_id: str, npc_id: str, player_input: str):
    dialogue = generate_npc_dialogue(universe_id, npc_id, player_input)
    return {"universe_id": universe_id, "npc_id": npc_id, "dialogue": dialogue}
