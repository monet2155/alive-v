import os
from dotenv import load_dotenv
from openai import OpenAI
from claude_sonnet import ClaudeSonnet  # Claude Sonnet 모듈 추가

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")
CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY")  # Claude Sonnet API 키 추가

if not OPENAI_API_KEY or not DATABASE_URL or not CLAUDE_API_KEY:
    raise ValueError("환경변수 설정이 잘못되었습니다.")

client = OpenAI(api_key=OPENAI_API_KEY)
claude_client = ClaudeSonnet(api_key=CLAUDE_API_KEY)  # Claude Sonnet 클라이언트 추가
