import os
import sqlite3

from config import CHARACTERS, COSMETICS


APP_DIR = os.path.join(os.getenv("APPDATA") or os.path.expanduser("~"), "NN League")
DB_PATH = os.path.join(APP_DIR, "save.db")

ACHIEVEMENT_DEFS = {
    "rookie": {
        "name": "Estreia",
        "description": "Jogue 1 partida com este personagem.",
        "icon": "shoe",
    },
    "winner": {
        "name": "Primeira Vitoria",
        "description": "Venca 1 partida com este personagem.",
        "icon": "trophy",
    },
    "scorer_10": {
        "name": "Cestinha",
        "description": "Faca 10 cestas com este personagem.",
        "icon": "ball",
    },
    "level_5": {
        "name": "Em Evolucao",
        "description": "Chegue ao level 5 com este personagem.",
        "icon": "star",
    },
    "main_10": {
        "name": "Main Declarado",
        "description": "Jogue 10 partidas com este personagem.",
        "icon": "crown",
    },
    "henrique_dash": {
        "name": "Roubo Relampago",
        "description": "Use o dash do Henrique em uma partida.",
        "icon": "shoe",
        "character": "Henrique",
    },
    "natan_ghost": {
        "name": "Ninguem Viu",
        "description": "Use a invisibilidade do Natan em uma partida.",
        "icon": "star",
        "character": "Natan",
    },
    "press_wall": {
        "name": "Muralha de Orelha",
        "description": "Use as orelhas do Presscinotti em uma partida.",
        "icon": "shield",
        "character": "Presscinotti",
    },
    "rafael_arc": {
        "name": "Mira Perfeita",
        "description": "Use a habilidade de forca e trajetoria do Rafael.",
        "icon": "target",
        "character": "Rafael",
    },
    "miguel_shadow": {
        "name": "Sombra em Quadra",
        "description": "Invoque o clone do Miguel.",
        "icon": "shadow",
        "character": "Miguel",
    },
    "john_float": {
        "name": "Sem Gravidade",
        "description": "Use a queda lenta do John Jonh.",
        "icon": "wing",
        "character": "John Jonh",
    },
    "diogo_cookie": {
        "name": "Chef da Quadra",
        "description": "Ative a Bolacha Turbo do Diogo.",
        "icon": "cookie",
        "character": "Diogo",
    },
    "paulo_spin": {
        "name": "Gira Tudo",
        "description": "Use a roleta do Paulo.",
        "icon": "wheel",
        "character": "Paulo",
    },
    "henrique_speedster": {
        "name": "Ladrao Relampago",
        "description": "Venca 3 partidas usando Henrique.",
        "icon": "shoe",
        "character": "Henrique",
    },
    "henrique_finisher": {
        "name": "Dash para a Gloria",
        "description": "Faca 30 pontos usando Henrique.",
        "icon": "trophy",
        "character": "Henrique",
    },
    "natan_escape": {
        "name": "Fuga Invisivel",
        "description": "Jogue 5 partidas usando Natan.",
        "icon": "shadow",
        "character": "Natan",
    },
    "natan_silent_score": {
        "name": "Cesta Silenciosa",
        "description": "Faca 8 cestas usando Natan.",
        "icon": "ball",
        "character": "Natan",
    },
    "press_defender": {
        "name": "Defensor da Rede",
        "description": "Venca 3 partidas usando Presscinotti.",
        "icon": "shield",
        "character": "Presscinotti",
    },
    "press_anchor": {
        "name": "Ancora da Defesa",
        "description": "Jogue 10 partidas usando Presscinotti.",
        "icon": "crown",
        "character": "Presscinotti",
    },
    "rafael_sniper": {
        "name": "Arco Perfeito",
        "description": "Faca 40 pontos usando Rafael.",
        "icon": "target",
        "character": "Rafael",
    },
    "rafael_air": {
        "name": "Forca Aerea",
        "description": "Chegue ao level 4 com Rafael.",
        "icon": "wing",
        "character": "Rafael",
    },
    "miguel_double": {
        "name": "Dois em Um",
        "description": "Jogue 5 partidas usando Miguel.",
        "icon": "shadow",
        "character": "Miguel",
    },
    "miguel_collector": {
        "name": "Sombra Cestinha",
        "description": "Faca 8 cestas usando Miguel.",
        "icon": "ball",
        "character": "Miguel",
    },
    "john_skywalker": {
        "name": "Andando no Ar",
        "description": "Chegue ao level 4 com John Jonh.",
        "icon": "wing",
        "character": "John Jonh",
    },
    "john_winner": {
        "name": "Leveza Vitoriosa",
        "description": "Venca 3 partidas usando John Jonh.",
        "icon": "trophy",
        "character": "John Jonh",
    },
    "diogo_supplier": {
        "name": "Fornecedor Oficial",
        "description": "Jogue 5 partidas usando Diogo.",
        "icon": "cookie",
        "character": "Diogo",
    },
    "diogo_buffed_score": {
        "name": "Bolacha e Cesta",
        "description": "Faca 30 pontos usando Diogo.",
        "icon": "ball",
        "character": "Diogo",
    },
    "paulo_lucky": {
        "name": "Sorte Insistente",
        "description": "Jogue 5 partidas usando Paulo.",
        "icon": "wheel",
        "character": "Paulo",
    },
    "paulo_showman": {
        "name": "Showman da Quadra",
        "description": "Venca 3 partidas usando Paulo.",
        "icon": "star",
        "character": "Paulo",
    },
    "paulo_jackpot": {
        "name": "JACKPOT!",
        "description": "Consiga um JACKPOT usando a roleta do Paulo.",
        "icon": "wheel",
        "character": "Paulo",
    },
    "jackpot_witness": {
        "name": "Eu Vi o Impossivel",
        "description": "Esteja em quadra quando Paulo conseguir um JACKPOT.",
        "icon": "star",
        "characters": ("Henrique", "Natan", "John Jonh", "Presscinotti", "Rafael", "Diogo", "Miguel"),
    },
    "jackpot_ally": {
        "name": "Time da Sorte",
        "description": "Esteja no time do Paulo quando ele conseguir um JACKPOT.",
        "icon": "crown",
        "characters": ("Henrique", "Natan", "John Jonh", "Presscinotti", "Rafael", "Diogo", "Miguel"),
    },
    "jackpot_stopper": {
        "name": "Anti-JACKPOT",
        "description": "Venca uma partida contra um Paulo que conseguiu JACKPOT.",
        "icon": "trophy",
        "characters": ("Henrique", "Natan", "John Jonh", "Presscinotti", "Rafael", "Diogo", "Miguel"),
    },
    "dunk_master": {
        "name": "Cravada Confirmada",
        "description": "Complete um QTE de dunk com este personagem.",
        "icon": "ball",
    },
    "clash_winner": {
        "name": "Entrou no Clash",
        "description": "Entre em um clash de habilidades com este personagem.",
        "icon": "trophy",
        "characters": ("Henrique", "Presscinotti", "Miguel", "John Jonh"),
    },
}

PAIR_ACHIEVEMENT_DEFS = {
    "Henrique+Presscinotti:clash": {
        "name": "Raio Contra Muralha",
        "description": "Entre em um clash entre Henrique e Presscinotti.",
        "icon": "shield",
        "characters": ("Henrique", "Presscinotti"),
    },
    "Henrique+Miguel:clash": {
        "name": "Velocidade Contra Sombra",
        "description": "Entre em um clash entre Henrique e Miguel.",
        "icon": "shadow",
        "characters": ("Henrique", "Miguel"),
    },
    "John Jonh+Rafael:aerial": {
        "name": "Duelo Aereo",
        "description": "Jogue uma partida que tenha Rafael e John Jonh.",
        "icon": "wing",
        "characters": ("Rafael", "John Jonh"),
    },
    "Diogo+Paulo:chaos": {
        "name": "Caos Total",
        "description": "Jogue uma partida que tenha Diogo e Paulo.",
        "icon": "wheel",
        "characters": ("Diogo", "Paulo"),
    },
}


def get_connection():
    os.makedirs(APP_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS player_profile (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                money INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS character_progress (
                character TEXT PRIMARY KEY,
                xp INTEGER NOT NULL DEFAULT 0,
                level INTEGER NOT NULL DEFAULT 1,
                matches INTEGER NOT NULL DEFAULT 0,
                wins INTEGER NOT NULL DEFAULT 0,
                losses INTEGER NOT NULL DEFAULT 0,
                baskets INTEGER NOT NULL DEFAULT 0,
                points INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        for column in ["matches", "wins", "losses", "baskets", "points"]:
            try:
                conn.execute(f"ALTER TABLE character_progress ADD COLUMN {column} INTEGER NOT NULL DEFAULT 0")
            except sqlite3.OperationalError:
                pass

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS global_stats (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                matches INTEGER NOT NULL DEFAULT 0,
                wins INTEGER NOT NULL DEFAULT 0,
                losses INTEGER NOT NULL DEFAULT 0,
                baskets INTEGER NOT NULL DEFAULT 0,
                points INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS achievements (
                achievement_id TEXT PRIMARY KEY,
                character TEXT NOT NULL,
                unlocked_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS owned_skins (
                skin_id TEXT PRIMARY KEY
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS equipped_skins (
                character TEXT PRIMARY KEY,
                skin_id TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS story_progress (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                unlocked_level INTEGER NOT NULL DEFAULT 1
            )
            """
        )
        conn.execute("INSERT OR IGNORE INTO player_profile (id, money) VALUES (1, 0)")
        conn.execute("INSERT OR IGNORE INTO global_stats (id) VALUES (1)")
        conn.execute("INSERT OR IGNORE INTO story_progress (id, unlocked_level) VALUES (1, 1)")
        conn.execute("INSERT OR IGNORE INTO owned_skins (skin_id) VALUES ('default')")

        for char in CHARACTERS:
            conn.execute(
                "INSERT OR IGNORE INTO character_progress (character, xp, level) VALUES (?, 0, 1)",
                (char,),
            )
            conn.execute(
                "INSERT OR IGNORE INTO equipped_skins (character, skin_id) VALUES (?, 'default')",
                (char,),
            )


def xp_for_next_level(level):
    return 100 + (level - 1) * 60


def get_money():
    with get_connection() as conn:
        row = conn.execute("SELECT money FROM player_profile WHERE id = 1").fetchone()
        return int(row["money"]) if row else 0


def add_money(amount):
    with get_connection() as conn:
        conn.execute("UPDATE player_profile SET money = MAX(0, money + ?) WHERE id = 1", (int(amount),))


def get_character_progress(character):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM character_progress WHERE character = ?",
            (character,),
        ).fetchone()

    if not row:
        return {
            "xp": 0,
            "level": 1,
            "matches": 0,
            "wins": 0,
            "losses": 0,
            "baskets": 0,
            "points": 0,
        }

    return {
        "xp": int(row["xp"]) if "xp" in row.keys() else 0,
        "level": int(row["level"]) if "level" in row.keys() else 1,
        "matches": int(row["matches"]) if "matches" in row.keys() else 0,
        "wins": int(row["wins"]) if "wins" in row.keys() else 0,
        "losses": int(row["losses"]) if "losses" in row.keys() else 0,
        "baskets": int(row["baskets"]) if "baskets" in row.keys() else 0,
        "points": int(row["points"]) if "points" in row.keys() else 0,
    }


def add_character_xp(character, amount):
    progress = get_character_progress(character)
    xp = progress["xp"] + int(amount)
    level = progress["level"]

    while xp >= xp_for_next_level(level):
        xp -= xp_for_next_level(level)
        level += 1

    with get_connection() as conn:
        conn.execute(
            "UPDATE character_progress SET xp = ?, level = ? WHERE character = ?",
            (xp, level, character),
        )

    check_character_achievements(character)


def record_match(character, won, baskets, points):
    wins = 1 if won else 0
    losses = 0 if won else 1

    with get_connection() as conn:
        conn.execute(
            """
            UPDATE global_stats
            SET matches = matches + 1,
                wins = wins + ?,
                losses = losses + ?,
                baskets = baskets + ?,
                points = points + ?
            WHERE id = 1
            """,
            (wins, losses, int(baskets), int(points)),
        )
        conn.execute(
            """
            UPDATE character_progress
            SET matches = matches + 1,
                wins = wins + ?,
                losses = losses + ?,
                baskets = baskets + ?,
                points = points + ?
            WHERE character = ?
            """,
            (wins, losses, int(baskets), int(points), character),
        )

    check_character_achievements(character)


def unlock_achievement(achievement_id, character):
    with get_connection() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO achievements (achievement_id, character) VALUES (?, ?)",
            (achievement_id, character),
        )


def check_character_achievements(character):
    progress = get_character_progress(character)

    thresholds = [
        ("rookie", progress["matches"] >= 1),
        ("winner", progress["wins"] >= 1),
        ("scorer_10", progress["baskets"] >= 10),
        ("level_5", progress["level"] >= 5),
        ("main_10", progress["matches"] >= 10),
    ]

    character_thresholds = {
        "Henrique": [
            ("henrique_speedster", progress["wins"] >= 3),
            ("henrique_finisher", progress["points"] >= 30),
        ],
        "Natan": [
            ("natan_escape", progress["matches"] >= 5),
            ("natan_silent_score", progress["baskets"] >= 8),
        ],
        "Presscinotti": [
            ("press_defender", progress["wins"] >= 3),
            ("press_anchor", progress["matches"] >= 10),
        ],
        "Rafael": [
            ("rafael_sniper", progress["points"] >= 40),
            ("rafael_air", progress["level"] >= 4),
        ],
        "Miguel": [
            ("miguel_double", progress["matches"] >= 5),
            ("miguel_collector", progress["baskets"] >= 8),
        ],
        "John Jonh": [
            ("john_skywalker", progress["level"] >= 4),
            ("john_winner", progress["wins"] >= 3),
        ],
        "Diogo": [
            ("diogo_supplier", progress["matches"] >= 5),
            ("diogo_buffed_score", progress["points"] >= 30),
        ],
        "Paulo": [
            ("paulo_lucky", progress["matches"] >= 5),
            ("paulo_showman", progress["wins"] >= 3),
        ],
    }

    thresholds.extend(character_thresholds.get(character, []))

    for suffix, unlocked in thresholds:
        if unlocked:
            unlock_achievement(f"{character}:{suffix}", character)


def unlock_character_achievement(character, suffix):
    definition = ACHIEVEMENT_DEFS.get(suffix)

    if not definition:
        return

    specific_character = definition.get("character")
    valid_characters = definition.get("characters")

    if specific_character and specific_character != character:
        return

    if valid_characters and character not in valid_characters:
        return

    unlock_achievement(f"{character}:{suffix}", character)


def unlock_pair_achievement(char_a, char_b, suffix):
    ordered = sorted([char_a, char_b])
    achievement_id = f"{ordered[0]}+{ordered[1]}:{suffix}"
    unlock_achievement(achievement_id, "+".join(ordered))


def get_global_stats():
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM global_stats WHERE id = 1").fetchone()

    if not row:
        return {"matches": 0, "wins": 0, "losses": 0, "baskets": 0, "points": 0}

    return {
        "matches": int(row["matches"]),
        "wins": int(row["wins"]),
        "losses": int(row["losses"]),
        "baskets": int(row["baskets"]),
        "points": int(row["points"]),
    }


def get_achievements():
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT achievement_id, character, unlocked_at FROM achievements ORDER BY unlocked_at DESC"
        ).fetchall()

    return [dict(row) for row in rows]


def get_all_achievements_status():
    unlocked = {row["achievement_id"]: row for row in get_achievements()}
    result = []

    for character in CHARACTERS:
        for suffix, data in ACHIEVEMENT_DEFS.items():
            specific_character = data.get("character")
            valid_characters = data.get("characters")

            if specific_character and specific_character != character:
                continue

            if valid_characters and character not in valid_characters:
                continue

            achievement_id = f"{character}:{suffix}"
            row = unlocked.get(achievement_id)
            result.append(
                {
                    "achievement_id": achievement_id,
                    "character": character,
                    "suffix": suffix,
                    "name": data["name"],
                    "description": data["description"],
                    "icon": data["icon"],
                    "unlocked": row is not None,
                    "unlocked_at": row["unlocked_at"] if row else None,
                }
            )

    for achievement_id, data in PAIR_ACHIEVEMENT_DEFS.items():
        row = unlocked.get(achievement_id)
        result.append(
            {
                "achievement_id": achievement_id,
                "character": " + ".join(data["characters"]),
                "suffix": achievement_id.split(":", 1)[1],
                "name": data["name"],
                "description": data["description"],
                "icon": data["icon"],
                "unlocked": row is not None,
                "unlocked_at": row["unlocked_at"] if row else None,
            }
        )

    return result


def get_owned_skins():
    with get_connection() as conn:
        rows = conn.execute("SELECT skin_id FROM owned_skins").fetchall()
    return {row["skin_id"] for row in rows}


def owns_skin(skin_id):
    return skin_id in get_owned_skins()


def buy_skin(skin_id):
    if skin_id not in COSMETICS:
        return False, "Skin invalida."

    if owns_skin(skin_id):
        return False, "Voce ja possui essa skin."

    price = int(COSMETICS[skin_id]["price"])

    if get_money() < price:
        return False, "Dinheiro insuficiente."

    with get_connection() as conn:
        conn.execute("UPDATE player_profile SET money = money - ? WHERE id = 1", (price,))
        conn.execute("INSERT INTO owned_skins (skin_id) VALUES (?)", (skin_id,))

    return True, "Skin comprada."


def get_equipped_skin(character):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT skin_id FROM equipped_skins WHERE character = ?",
            (character,),
        ).fetchone()

    if not row or row["skin_id"] not in COSMETICS:
        return "default"

    return row["skin_id"]


def equip_skin(character, skin_id):
    if skin_id not in COSMETICS:
        return False, "Skin invalida."

    if not owns_skin(skin_id):
        return False, "Compre a skin antes de equipar."

    with get_connection() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO equipped_skins (character, skin_id) VALUES (?, ?)",
            (character, skin_id),
        )

    return True, "Skin equipada."


def get_unlocked_story_level():
    with get_connection() as conn:
        row = conn.execute("SELECT unlocked_level FROM story_progress WHERE id = 1").fetchone()

    return int(row["unlocked_level"]) if row else 1


def set_unlocked_story_level(level):
    with get_connection() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO story_progress (id, unlocked_level) VALUES (1, ?)",
            (int(level),),
        )
