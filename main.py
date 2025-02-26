import os
from fastapi import FastAPI
from openai import OpenAI
from dotenv import load_dotenv
import json

load_dotenv()

openai_api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=openai_api_key)

app = FastAPI()

# 외부 파일에서 Prompt 로드
def load_prompt_template():
    with open('prompt_template.txt', 'r', encoding='utf-8') as file:
        return file.read()

# 임시 게임 세계 설정 함수
def get_world_settings():
    return {
        "game_genre": "판타지 게임",
        "time": "오후",
        "weather": "맑음",
        "location": "중앙 마을"
    }

# NPC 프로필 임시 데이터 함수
def get_npc_profile(npc_id):
    npc_profiles = {
        "npc_001": {
            "name": "엘리나",
            "role": "여관 주인",
            "personality": "친절하고 따뜻함",
            "relationship": "좋음"
        }
    }
    return npc_profiles.get(npc_id, {})

# NPC 대화 생성 함수
def generate_npc_dialogue(npc, player_input):
    world = get_world_settings()

    prompt_template = load_prompt_template()

    prompt = prompt_template.format(
        game_genre=world["game_genre"],
        personality=npc["personality"],
        role=npc["role"],
        relationship=npc["relationship"],
        time=world["time"],
        weather=world["weather"],
        player_input=player_input
    )

    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=100,
        temperature=0.7
    )

    return response.choices[0].message.content

@app.get("/npc/{npc_id}/dialogue")
def get_npc_dialogue(npc_id: str, player_input: str):
    npc = get_npc_profile(npc_id)
    world = get_world_settings()

    if not npc:
        return {"error": "NPC not found"}

    dialogue = generate_npc_dialogue(npc, player_input)
    return {"npc_id": npc_id, "dialogue": dialogue}
