from ..database import cursor


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
    return dict(zip(["name", "bio", "race", "gender", "species"], row)) if row else {}


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
    return dict(zip(["description", "lore", "rules"], row)) if row else {}
