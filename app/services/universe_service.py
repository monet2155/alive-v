from ..database import get_connection, release_connection


# get npcs
def get_npcs_by_universe_id(universe_id):
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                    SELECT *
                    FROM "Npc"
                    WHERE "universeId" = %s
                """,
                (universe_id,),
            )
            rows = cursor.fetchall()
            if not rows:
                return []

            # 컬럼명 가져오기
            columns = [desc[0] for desc in cursor.description]

            # 각 행을 컬럼명과 매핑하여 딕셔너리 생성
            npcs = []
            for row in rows:
                npc = dict(zip(columns, row))
                npcs.append(npc)

            return npcs

    except Exception as e:
        raise RuntimeError(f"NPC 조회 실패: {e}")
    finally:
        release_connection(conn)
