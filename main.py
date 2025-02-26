import os
from fastapi import FastAPI
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

openai_api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=openai_api_key)

app = FastAPI()

# GPT API 설정

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
    prompt = f"""
    당신은 {world['game_genre']}의 {npc['personality']} 성격을 가진 {npc['role']}입니다. 플레이어와의 관계는 {npc['relationship']} 상태입니다.
    시간은 {world['time']}이고 날씨는 {world['weather']}입니다.

    [현재 플레이어 발언]
    플레이어: {player_input}

    [NPC 답변]
    """

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
