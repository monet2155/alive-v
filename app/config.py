import os
from dotenv import load_dotenv
from openai import OpenAI
import anthropic
import logging

# 로깅 설정
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")
CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY")  # Claude Sonnet API 키 추가

if not OPENAI_API_KEY or not DATABASE_URL or not CLAUDE_API_KEY:
    raise ValueError("환경변수 설정이 잘못되었습니다.")

client = OpenAI(api_key=OPENAI_API_KEY)
claude_client = anthropic.Anthropic(
    api_key=CLAUDE_API_KEY
)  # Claude Sonnet 클라이언트 추가


class AIClientDelegate:
    def __init__(self, openai_client, claude_client):
        self.openai_client = openai_client
        self.claude_client = claude_client

    def generate_response(self, provider, **kwargs):
        print(f"AI 제공자: {provider}")
        print(f"요청 파라미터: {kwargs}")
        try:
            if provider == "openai":
                return self.openai_client.chat.completions.create(
                    **kwargs,
                    model="gpt-4-turbo",
                )
            elif provider == "claude":
                return self.claude_client.messages.create(
                    **kwargs,
                    model="claude-3-7-sonnet-20250219",
                )
            else:
                raise ValueError("지원되지 않는 AI 제공자입니다.")
        except Exception as e:
            logger.error(f"API 호출 오류 발생 - 제공자: {provider}, 오류: {str(e)}")
            raise  # 원본 예외를 다시 발생시켜 상위 코드에서 처리할 수 있도록 함


ai_client_delegate = AIClientDelegate(client, claude_client)
