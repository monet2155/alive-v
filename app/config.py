import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")

if not OPENAI_API_KEY or not DATABASE_URL:
    raise ValueError("환경변수 설정이 잘못되었습니다.")

client = OpenAI(api_key=OPENAI_API_KEY)
