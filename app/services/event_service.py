from ..database import get_connection, release_connection


def get_event_by_id(event_id):
    conn = get_connection()
    try:
        # 기본 이벤트 정보 조회
        event_data = {}
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, "universeId", name, type, scope, "isRepeatable", "isActive", "createdAt"
                FROM "Event"
                WHERE id = %s
                """,
                (event_id,),
            )
            row = cursor.fetchone()
            if not row:
                return {}

            event_data = dict(
                zip(
                    [
                        "id",
                        "universeId",
                        "name",
                        "type",
                        "scope",
                        "isRepeatable",
                        "isActive",
                        "createdAt",
                    ],
                    row,
                )
            )

            # 트리거 정보 조회
            cursor.execute(
                """
                SELECT id, "eventId", type, config, "createdAt"
                FROM "EventTrigger"
                WHERE "eventId" = %s
                """,
                (event_id,),
            )
            triggers = [
                dict(zip(["id", "eventId", "type", "config", "createdAt"], row))
                for row in cursor.fetchall()
            ]
            event_data["triggers"] = triggers

            # 이벤트 효과 정보 조회
            cursor.execute(
                """
                SELECT id, "eventId", type, config, "order", "createdAt"
                FROM "EventEffect"
                WHERE "eventId" = %s
                ORDER BY "order"
                """,
                (event_id,),
            )
            effects = [
                dict(
                    zip(["id", "eventId", "type", "config", "order", "createdAt"], row)
                )
                for row in cursor.fetchall()
            ]
            event_data["effects"] = effects

            # 플레이어 이벤트 상태 정보 조회
            cursor.execute(
                """
                SELECT id, "eventId", "playerId", status, "updatedAt"
                FROM "PlayerEventState"
                WHERE "eventId" = %s
                """,
                (event_id,),
            )
            player_states = [
                dict(zip(["id", "eventId", "playerId", "status", "updatedAt"], row))
                for row in cursor.fetchall()
            ]
            event_data["playerStates"] = player_states

            # 이벤트 단계 정보 조회
            cursor.execute(
                """
                SELECT id, "eventId", "order", message, "speakerType", "speakerId"
                FROM "EventStep"
                WHERE "eventId" = %s
                ORDER BY "order"
                """,
                (event_id,),
            )
            steps = [
                dict(
                    zip(
                        [
                            "id",
                            "eventId",
                            "order",
                            "message",
                            "speakerType",
                            "speakerId",
                        ],
                        row,
                    )
                )
                for row in cursor.fetchall()
            ]
            event_data["steps"] = steps

            return event_data
    except Exception as e:
        raise RuntimeError(f"이벤트 조회 실패: {e}")
    finally:
        release_connection(conn)
