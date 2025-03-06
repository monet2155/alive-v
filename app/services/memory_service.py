import uuid
from datetime import datetime
from ..database import get_connection, release_connection
from ..config import client


def get_important_memories(universe_id, npc_id, player_id):
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT content FROM "ImportantMemory"
                WHERE "universeId" = %s AND "npcId" = %s AND "playerId" = %s
                ORDER BY "createdAt" ASC LIMIT 5
            """,
                (universe_id, npc_id, player_id),
            )
            return [row[0] for row in cursor.fetchall()]
    except Exception as e:
        raise RuntimeError(f"중요 기억 조회 실패: {e}")
    finally:
        release_connection(conn)


def get_summary_memory(universe_id, npc_id, player_id):
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT content FROM "SummaryMemory"
                WHERE "universeId" = %s AND "npcId" = %s AND "playerId" = %s
            """,
                (universe_id, npc_id, player_id),
            )
            row = cursor.fetchone()
            return row[0] if row else "없음"
    except Exception as e:
        raise RuntimeError(f"요약 기억 조회 실패: {e}")
    finally:
        release_connection(conn)


def update_summary_memory(universe_id, npc_id, player_id):
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT "longMemory"
                FROM "ConversationSession"
                WHERE "universeId" = %s AND "npcId" = %s AND "playerId" = %s
                AND "longMemory" != ''
                ORDER BY "endedAt" DESC
                LIMIT 5
            """,
                (universe_id, npc_id, player_id),
            )
            memories = [row[0] for row in cursor.fetchall()]

            if not memories:
                return

            prompt = "다음 대화 요약들을 바탕으로 플레이어와의 관계와 분위기를 한 문장으로 요약해줘:\n" + "\n".join(
                memories
            )

            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=150,
                temperature=0.5,
            )
            new_summary = response.choices[0].message.content

            now = datetime.utcnow()
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
    except Exception as e:
        conn.rollback()
        raise RuntimeError(f"요약 메모리 업데이트 실패: {e}")
    finally:
        release_connection(conn)
