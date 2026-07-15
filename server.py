import socket
import threading
import pickle
import zlib  # SPEC-02: checksum anti-dessincronizacao
import random
import string
import math
import time
import uuid  # SPEC-01: token de reconexao
from config import *
import save_db  # SPEC-05: placar persistente local

# NOTA DE SEGURANCA: o jogo usa pickle para o protocolo de rede desde a origem.
# E' um jogo local/LAN (Radmin VPN) entre jogadores confiaveis; trocar por JSON/
# msgspec exigiria reescrever cliente e servidor. Mantido por compatibilidade.

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.bind((HOST, PORT))
server.listen()
print(f"[SERVIDOR LIGADO] Aguardando em {HOST}:{PORT}...")

rooms = {}


def send_room(conn, room):
    """SPEC-02: envia o room com frame_id e crc32 para o cliente detectar
    pacotes fora de ordem ou corrompidos (anti-dessincronizacao)."""
    room["frame_id"] = room.get("frame_counter", 0)
    payload = dict(room)
    payload.pop("crc", None)
    room["crc"] = zlib.crc32(pickle.dumps(payload, protocol=pickle.HIGHEST_PROTOCOL)) & 0xffffffff
    conn.send(pickle.dumps(room, protocol=pickle.HIGHEST_PROTOCOL))


ROLETA_OUTCOMES = [
    "BUFF_BOLACHA",
    "BUFF_PULO",
    "BUFF_FORCA",
    "BUFF_DUNK",
    "DEBUFF_PULO",
    "DEBUFF_VELOCIDADE",
    "DEBUFF_FORCA",
    "JACKPOT"
]

ROLETA_WEIGHTS = [22, 22, 18, 14, 6, 6, 6, 6]

ABILITY_COOLDOWNS = {
    "Diogo": 480,
    "Paulo": 480,
    "Henrique": 360,
    "Natan": 360,
    "Presscinotti": 360,
    "Miguel": 360,
    "Rafael": 360,
    "John Jonh": 360,
    "Treinador": 360,
    "Murilo": 360,
    "Igor": 420,
    "Laiz": 480,
    "Kauã": 480,
    "Caique": 360,
    "João Roberto": 420,
    "Havoc": 540,
    "Bola": 240,
}


def clamp(value, min_value, max_value):
    return max(min_value, min(value, max_value))


def get_room_width(room):
    return int(room.get("world_width", WIDTH))


def update_room_world_width(room):
    width = map_width_for_player_count(len(room.get("players", {})))
    old_width = get_room_width(room)
    room["world_width"] = width

    if width == old_width:
        return

    for p in room.get("players", {}).values():
        p["world_width"] = width
        p["x"] = clamp(p.get("x", 0), 0, width - CHAR_W)

    ball = room.get("ball")

    if ball:
        ball["x"] = clamp(ball.get("x", width / 2), BALL_RAD, width - BALL_RAD)


def get_room_geometry(room):
    return get_court_geometry(get_room_width(room))


def get_bola_player_id(room):
    for pid, player in room.get("players", {}).items():
        if player.get("char") == "Bola":
            return pid

    return None


def sync_bola_player_to_ball(room):
    bola_id = get_bola_player_id(room)

    if bola_id not in room.get("players", {}):
        return

    bola = room["players"][bola_id]
    ball = room["ball"]
    world_width = get_room_width(room)
    bola["x"] = clamp(ball["x"] - CHAR_W / 2, 0, world_width - CHAR_W)
    bola["y"] = clamp(ball["y"] - CHAR_H / 2, 0, GROUND_Y - CHAR_H)


def rects_overlap(a, b):
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return ax < bx + bw and ax + aw > bx and ay < by + bh and ay + ah > by


def player_rect(p):
    return (p["x"], p["y"], CHAR_W, CHAR_H)


def center_of_rect(rect):
    x, y, w, h = rect
    return x + w / 2, y + h / 2


def get_clone_rect(p):
    world_width = int(p.get("world_width", WIDTH))
    facing = p.get("facing", 1)
    clone_x = clamp(p["x"] - facing * 75, 0, world_width - CHAR_W)
    clone_y = p["y"]

    p["clone_x"] = clone_x
    p["clone_y"] = clone_y

    return (clone_x, clone_y, CHAR_W, CHAR_H)


def is_timed_ability_active(p):
    char = p.get("char")

    if char == "Treinador":
        return (
            p.get("dash_timer", 0) > 0
            or p.get("invisible_timer", 0) > 0
            or p.get("ear_timer", 0) > 0
            or p.get("cookie_buff_timer", 0) > 0
            or p.get("clone_timer", 0) > 0
            or p.get("throw_buff_timer", 0) > 0
            or p.get("john_float_timer", 0) > 0
            or p.get("roleta_state", "IDLE") != "IDLE"
            or p.get("jackpot_timer", 0) > 0
            or p.get("jump_buff_timer", 0) > 0
            or p.get("dunk_buff_timer", 0) > 0
            or p.get("jump_debuff_timer", 0) > 0
            or p.get("speed_debuff_timer", 0) > 0
            or p.get("throw_debuff_timer", 0) > 0
        )

    if char == "Henrique":
        return p.get("dash_timer", 0) > 0

    if char == "Natan":
        return p.get("invisible_timer", 0) > 0

    if char == "Presscinotti":
        return p.get("ear_timer", 0) > 0

    if char == "Diogo":
        return p.get("cookie_buff_timer", 0) > 0

    if char == "Miguel":
        return p.get("clone_timer", 0) > 0

    if char == "Rafael":
        return p.get("throw_buff_timer", 0) > 0

    if char == "John Jonh":
        return p.get("john_float_timer", 0) > 0

    if char == "Paulo":
        return (
            p.get("roleta_state", "IDLE") != "IDLE"
            or p.get("jackpot_timer", 0) > 0
            or p.get("cookie_buff_timer", 0) > 0
            or p.get("jump_buff_timer", 0) > 0
            or p.get("throw_buff_timer", 0) > 0
            or p.get("dunk_buff_timer", 0) > 0
            or p.get("jump_debuff_timer", 0) > 0
            or p.get("speed_debuff_timer", 0) > 0
            or p.get("throw_debuff_timer", 0) > 0
        )

    if char == "Havoc":
        return p.get("havoc_timer", 0) > 0

    return False


def ball_crossed_hoop(prev_y, ball, x1, x2):
    return (
        ball["vel_y"] > 0
        and prev_y <= HOOP_Y + HOOP_SCORE_MARGIN_Y
        and ball["y"] >= HOOP_Y - HOOP_SCORE_MARGIN_Y
        and x1 + HOOP_SCORE_MARGIN_X <= ball["x"] <= x2 - HOOP_SCORE_MARGIN_X
    )


def get_hoop_center_for_team(team, room=None):
    geo = get_room_geometry(room) if room else get_court_geometry(WIDTH)

    if team == 1:
        return (geo["right_hoop_x1"] + geo["right_hoop_x2"]) / 2, HOOP_Y

    return (geo["left_hoop_x1"] + geo["left_hoop_x2"]) / 2, HOOP_Y


def get_score_points(room, scored_team):
    ball = room["ball"]

    if ball.get("score_override"):
        return ball["score_override"]

    origin_x = ball.get("shot_origin_x")
    origin_y = ball.get("shot_origin_y")

    if origin_x is None or origin_y is None:
        return 2

    hoop_x, hoop_y = get_hoop_center_for_team(scored_team, room)
    distance = math.hypot(origin_x - hoop_x, origin_y - hoop_y)

    if distance >= THREE_POINT_DISTANCE:
        return 3

    return 2


def resolve_circle_point_collision(ball, point_x, point_y, radius, bounce=0.78):
    dx = ball["x"] - point_x
    dy = ball["y"] - point_y
    dist = math.hypot(dx, dy)
    min_dist = BALL_RAD + radius

    if dist <= 0 or dist >= min_dist:
        return

    nx = dx / dist
    ny = dy / dist
    dot = ball["vel_x"] * nx + ball["vel_y"] * ny

    ball["x"] = point_x + nx * min_dist
    ball["y"] = point_y + ny * min_dist

    if dot < 0:
        ball["vel_x"] -= (1 + bounce) * dot * nx
        ball["vel_y"] -= (1 + bounce) * dot * ny


def resolve_circle_rect_collision(ball, rect, bounce=0.75):
    rx, ry, rw, rh = rect
    closest_x = clamp(ball["x"], rx, rx + rw)
    closest_y = clamp(ball["y"], ry, ry + rh)
    dx = ball["x"] - closest_x
    dy = ball["y"] - closest_y
    dist = math.hypot(dx, dy)

    if dist <= 0 or dist >= BALL_RAD:
        return

    nx = dx / dist
    ny = dy / dist
    dot = ball["vel_x"] * nx + ball["vel_y"] * ny

    ball["x"] = closest_x + nx * BALL_RAD
    ball["y"] = closest_y + ny * BALL_RAD

    if dot < 0:
        ball["vel_x"] -= (1 + bounce) * dot * nx
        ball["vel_y"] -= (1 + bounce) * dot * ny


def resolve_hoop_collisions(ball, room=None):
    geo = get_room_geometry(room) if room else get_court_geometry(WIDTH)

    for rim_x in (geo["left_hoop_x1"], geo["left_hoop_x2"], geo["right_hoop_x1"], geo["right_hoop_x2"]):
        resolve_circle_point_collision(ball, rim_x, HOOP_Y, HOOP_RIM_RAD)

    resolve_circle_rect_collision(ball, (geo["left_backboard_x"], BACKBOARD_Y, BACKBOARD_W, BACKBOARD_H))
    resolve_circle_rect_collision(ball, (geo["right_backboard_x"], BACKBOARD_Y, BACKBOARD_W, BACKBOARD_H))


def generate_room_code():
    while True:
        code = "".join(random.choices(string.ascii_uppercase + string.digits, k=4))
        if code not in rooms:
            return code


def get_next_player_id(room):
    pid = 1
    while pid in room["players"]:
        pid += 1
    return pid


def count_team_players(room, team):
    total = 0

    for p in room["players"].values():
        if p.get("team") == team:
            total += 1

    return total


def choose_balanced_team(room):
    team_1_count = count_team_players(room, 1)
    team_2_count = count_team_players(room, 2)

    if team_1_count <= team_2_count:
        return 1

    return 2


def choose_available_character(room):
    used_chars = []

    for p in room["players"].values():
        if p.get("char"):
            used_chars.append(p["char"])

    for char in PUBLIC_CHARACTERS:
        if char not in used_chars:
            return char

    return None


def choose_available_bot_character(room):
    used_chars = [p.get("char") for p in room["players"].values() if p.get("char")]

    for char in CHARACTERS:
        if char not in used_chars:
            return char

    return random.choice(CHARACTERS)


def add_training_bot(room, requested_char=None):
    if room.get("game_started"):
        return False

    bot_count = sum(1 for p in room["players"].values() if p.get("is_bot"))

    if len(room["players"]) >= 8:
        return False

    bot_id = -room.get("next_bot_id", 1)
    room["next_bot_id"] = room.get("next_bot_id", 1) + 1
    team = choose_balanced_team(room)
    bot_char = requested_char if requested_char in CHARACTERS else choose_available_bot_character(room)
    bot = {
        "char": bot_char,
        "skin_id": "default",
        "team": team,
        "x": 0,
        "y": 0,
        "world_width": get_room_width(room),
        "is_bot": True,
        "bot_name": f"BOT {bot_count + 1}",
        "bot_jump_cd": 0,
    }
    room["players"][bot_id] = bot
    reset_player_status(bot)
    reset_player_match_stats(bot)
    update_room_world_width(room)
    return True


def remove_training_bot(room):
    bot_ids = [pid for pid, p in room["players"].items() if p.get("is_bot")]

    if not bot_ids or room.get("game_started"):
        return False

    del room["players"][bot_ids[-1]]
    update_room_world_width(room)
    return True


def reset_player_status(p_data):
    keys_to_reset = [
        "invisible_timer",
        "ear_timer",
        "clone_timer",
        "cookie_buff_timer",
        "jackpot_timer",
        "jump_buff_timer",
        "throw_buff_timer",
        "dunk_buff_timer",
        "jump_debuff_timer",
        "speed_debuff_timer",
        "throw_debuff_timer",
        "lag_timer",
        "lag_tick",
        "goon_timer",
        "caique_rage",
        "caique_shout_timer",
        "havoc_timer",
        "havoc_mark_timer",
        "john_float_timer",
        "stun_timer",
        "dash_timer",
        "ultimate_flash_timer",
        "roleta_timer",
        "ability_cd",
        "knockback_timer",
        "knockback_vx",
        "clone_hit_cd",
        "clone_block_cd",
        "dunk_active",
        "dunk_timer",
        "dunk_anim_timer",
        "dunk_ready_to_score",
        "dunk_index",
        "pending_dunk_score_team",
        "dunk_no_score_timer",
        "clash_active",
        "clash_id",
        "clash_timer",
        "clash_index",
    ]

    for k in keys_to_reset:
        p_data[k] = 0

    p_data["roleta_state"] = "IDLE"
    p_data["roleta_result"] = None
    p_data["dash_dir"] = 1
    p_data["facing"] = 1
    p_data["clone_x"] = p_data["x"]
    p_data["clone_y"] = p_data["y"]
    p_data["dunk_sequence"] = []
    p_data["dunk_score_team"] = None
    p_data["dunk_start_x"] = p_data["x"]
    p_data["dunk_start_y"] = p_data["y"]
    p_data["dunk_target_x"] = p_data["x"]
    p_data["dunk_target_y"] = p_data["y"]
    p_data["clash_sequence"] = []
    p_data["clash_opponent"] = None


def reset_player_match_stats(p_data):
    p_data["match_points"] = 0
    p_data["match_baskets"] = 0
    p_data["match_steals"] = 0
    p_data["match_possession_ticks"] = 0
    p_data["match_humiliated"] = 0
    p_data["ultimate_charge"] = 0


def sanitize_murilo_points(raw_points):
    points = []

    for item in raw_points[:180]:
        if not isinstance(item, (list, tuple)) or len(item) < 2:
            continue

        try:
            x = float(item[0])
            y = float(item[1])
        except (TypeError, ValueError):
            continue

        points.append((clamp(x, 0, WIDTH), clamp(y, 0, HEIGHT)))

    return points


def murilo_path_length(points):
    total = 0

    for i in range(1, len(points)):
        total += math.hypot(points[i][0] - points[i - 1][0], points[i][1] - points[i - 1][1])

    return total


def resample_murilo_points(points, target_count=24):
    if len(points) <= target_count:
        return points[:]

    total_len = murilo_path_length(points)

    if total_len <= 0:
        return points[:target_count]

    interval = total_len / (target_count - 1)
    sampled = [points[0]]
    accumulated = 0
    cursor = points[0]
    i = 1

    while i < len(points) and len(sampled) < target_count - 1:
        current = points[i]
        segment_len = math.hypot(current[0] - cursor[0], current[1] - cursor[1])

        if accumulated + segment_len >= interval and segment_len > 0:
            ratio = (interval - accumulated) / segment_len
            cursor = (
                cursor[0] + (current[0] - cursor[0]) * ratio,
                cursor[1] + (current[1] - cursor[1]) * ratio,
            )
            sampled.append(cursor)
            accumulated = 0
        else:
            accumulated += segment_len
            cursor = current
            i += 1

    sampled.append(points[-1])
    return sampled


def count_direction_changes(values, min_delta=18):
    changes = 0
    last_dir = 0

    for i in range(1, len(values)):
        delta = values[i] - values[i - 1]

        if abs(delta) < min_delta:
            continue

        current_dir = 1 if delta > 0 else -1

        if last_dir and current_dir != last_dir:
            changes += 1

        last_dir = current_dir

    return changes


def bounding_edge_ratio(points, min_x, max_x, min_y, max_y, tolerance=18):
    if not points:
        return 0

    edge_hits = 0

    for x, y in points:
        if (
            abs(x - min_x) <= tolerance
            or abs(x - max_x) <= tolerance
            or abs(y - min_y) <= tolerance
            or abs(y - max_y) <= tolerance
        ):
            edge_hits += 1

    return edge_hits / len(points)


def count_corner_zones(points, min_x, max_x, min_y, max_y, tolerance):
    corners = set()

    for x, y in points:
        near_left = abs(x - min_x) <= tolerance
        near_right = abs(x - max_x) <= tolerance
        near_top = abs(y - min_y) <= tolerance
        near_bottom = abs(y - max_y) <= tolerance

        if near_left and near_top:
            corners.add("lt")
        if near_right and near_top:
            corners.add("rt")
        if near_left and near_bottom:
            corners.add("lb")
        if near_right and near_bottom:
            corners.add("rb")

    return len(corners)


def is_murilo_secret_star(points, width, height, diagonal, path_len, start_end_dist, x_changes, y_changes):
    if width < 85 or height < 85:
        return False

    aspect = width / max(1, height)

    if not 0.55 <= aspect <= 1.85:
        return False

    # A estrela judaica normalmente cria dois triangulos sobrepostos: muitos
    # cruzamentos/dobras e caminho bem mais longo que uma forma simples.
    return (
        path_len >= diagonal * 3.0
        and x_changes + y_changes >= 7
        and start_end_dist <= diagonal * 1.35
    )


def recognize_murilo_drawing(points):
    if len(points) < 8:
        return None

    points = resample_murilo_points(points)
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    width = max_x - min_x
    height = max_y - min_y

    if width < 25 and height < 25:
        return None

    start = points[0]
    end = points[-1]
    path_len = murilo_path_length(points)
    diagonal = max(1, math.hypot(width, height))
    start_end_dist = math.hypot(end[0] - start[0], end[1] - start[1])
    x_changes = count_direction_changes(xs, max(10, width * 0.12))
    y_changes = count_direction_changes(ys, max(10, height * 0.12))
    aspect = width / max(1, height)
    closed = start_end_dist <= diagonal * 0.55
    mostly_horizontal = width >= 65 and width >= height * 1.45
    mostly_vertical = height >= 65 and height >= width * 1.25
    net_dx = end[0] - start[0]
    net_dy = end[1] - start[1]
    edge_tolerance = max(18, diagonal * 0.12)

    if is_murilo_secret_star(points, width, height, diagonal, path_len, start_end_dist, x_changes, y_changes):
        return "david_star"

    if (
        width >= 55
        and height >= 55
        and closed
        and x_changes + y_changes >= 2
        and bounding_edge_ratio(points, min_x, max_x, min_y, max_y, edge_tolerance) >= 0.42
        and count_corner_zones(points, min_x, max_x, min_y, max_y, edge_tolerance * 1.25) >= 3
    ):
        return "square"

    if (
        width >= 55
        and height >= 55
        and 0.38 <= aspect <= 2.4
        and start_end_dist <= diagonal * 0.7
        and path_len >= diagonal * 1.55
        and x_changes + y_changes >= 2
    ):
        return "circle"

    start_top = start[1] <= min_y + height * 0.38
    end_top = end[1] <= min_y + height * 0.38
    lowest_i = max(range(len(points)), key=lambda i: points[i][1])
    lowest = points[lowest_i]
    smile_mid = 0.2 * len(points) <= lowest_i <= 0.8 * len(points)

    if width >= 75 and height >= 28 and height <= width * 0.95 and start_top and end_top and smile_mid:
        return "smile"

    lowest_i = max(range(len(points)), key=lambda i: points[i][1])
    lowest = points[lowest_i]
    v_has_sides = 0.12 * len(points) <= lowest_i <= 0.88 * len(points)
    v_has_depth = lowest[1] - start[1] >= height * 0.32 and lowest[1] - end[1] >= height * 0.32
    v_has_width = abs(end[0] - start[0]) >= width * 0.32

    if width >= 50 and height >= 50 and v_has_sides and v_has_depth and v_has_width:
        return "v"

    if height >= 70 and width >= 25 and x_changes >= 1 and net_dy <= -height * 0.25:
        return "lightning"

    if width >= 75 and height >= 25 and x_changes >= 2 and path_len >= diagonal * 1.15:
        return "zigzag"

    if x_changes + y_changes >= 5 and width >= 35 and height >= 35 and path_len >= diagonal * 1.55:
        return "scribble"

    if mostly_horizontal and abs(net_dy) <= max(55, height * 1.1):
        return "horizontal"

    if mostly_vertical and net_dy <= -height * 0.35:
        return "up"

    if mostly_vertical and net_dy >= height * 0.35:
        return "down"

    return None


def apply_murilo_drawing(room, player_id, player, raw_points):
    points = sanitize_murilo_points(raw_points)
    command = recognize_murilo_drawing(points)

    if not command:
        return False

    if command == "horizontal":
        player["throw_buff_timer"] = 300

    elif command == "david_star":
        room["score"][player["team"] - 1] = MAX_SCORE
        room["game_started"] = False
        room["game_over"] = True
        room["winner_team"] = player["team"]

    elif command == "up":
        player["jump_buff_timer"] = 300

    elif command == "v":
        player["dunk_buff_timer"] = 420

    elif command == "zigzag":
        for p in room["players"].values():
            if p["team"] == player["team"]:
                p["cookie_buff_timer"] = 300

    elif command == "circle":
        center_x = player["x"] + CHAR_W / 2
        center_y = player["y"] + CHAR_H / 2

        for enemy_id, enemy in room["players"].items():
            if enemy_id == player_id or enemy.get("team") == player.get("team"):
                continue

            enemy_center_x = enemy["x"] + CHAR_W / 2
            enemy_center_y = enemy["y"] + CHAR_H / 2

            if math.hypot(enemy_center_x - center_x, enemy_center_y - center_y) <= 220:
                enemy["stun_timer"] = max(enemy.get("stun_timer", 0), 90)

                if room["ball"].get("holder") == enemy_id:
                    room["ball"]["holder"] = player_id
                    room["ball"]["holder_source"] = "player"
                    set_last_touch(room, player_id)

    elif command == "square":
        room.setdefault("murilo_npcs", [])
        room["murilo_npcs"] = [
            npc for npc in room["murilo_npcs"]
            if npc.get("owner_id") != player_id or npc.get("timer", 0) > 120
        ][-2:]
        room["next_murilo_npc_id"] = room.get("next_murilo_npc_id", 0) + 1
        room["murilo_npcs"].append({
            "id": f"murilo_npc_{room['next_murilo_npc_id']}",
            "owner_id": player_id,
            "team": player["team"],
            "x": player["x"],
            "y": player["y"],
            "vel_y": 0,
            "facing": player.get("facing", 1),
            "shoot_cd": 35,
            "jump_cd": 0,
            "catch_cd": 0,
            "timer": 720,
            "duration": 720,
            "name": "Rabisco",
        })

    elif command == "lightning":
        player["cookie_buff_timer"] = max(player.get("cookie_buff_timer", 0), 360)
        player["jump_buff_timer"] = max(player.get("jump_buff_timer", 0), 240)

    elif command == "smile":
        for p in room["players"].values():
            if p["team"] == player["team"]:
                p["jump_debuff_timer"] = 0
                p["speed_debuff_timer"] = 0
                p["throw_debuff_timer"] = 0
                p["stun_timer"] = 0

    elif command == "scribble":
        center_x = player["x"] + CHAR_W / 2
        center_y = player["y"] + CHAR_H / 2

        for enemy_id, enemy in room["players"].items():
            if enemy_id == player_id or enemy.get("team") == player.get("team"):
                continue

            enemy_center_x = enemy["x"] + CHAR_W / 2
            enemy_center_y = enemy["y"] + CHAR_H / 2

            if math.hypot(enemy_center_x - center_x, enemy_center_y - center_y) <= 260:
                direction = 1 if enemy_center_x >= center_x else -1
                enemy["stun_timer"] = max(enemy.get("stun_timer", 0), 55)
                enemy["knockback_timer"] = max(enemy.get("knockback_timer", 0), 24)
                enemy["knockback_vx"] = direction * 14

    elif command == "down":
        ball = room["ball"]
        ball["holder"] = player_id
        ball["holder_source"] = "player"
        ball["vel_x"] = 0
        ball["vel_y"] = 0
        set_last_touch(room, player_id)

    player["ability_cd"] = ABILITY_COOLDOWNS.get("Murilo", 360)
    player["murilo_last_command"] = command
    return True


def apply_character_ability(room, player, ability_char, facing):
    if ability_char == "Henrique":
        player["dash_timer"] = 12
        player["dash_dir"] = facing
        player["ability_cd"] = ABILITY_COOLDOWNS.get(ability_char, 360)
        return True

    if ability_char == "Natan":
        player["invisible_timer"] = 180
        player["ability_cd"] = ABILITY_COOLDOWNS.get(ability_char, 360)
        return True

    if ability_char == "Presscinotti":
        player["ear_timer"] = 240
        player["ability_cd"] = ABILITY_COOLDOWNS.get(ability_char, 360)
        return True

    if ability_char == "Diogo":
        for p in room["players"].values():
            if p["team"] == player["team"]:
                p["cookie_buff_timer"] = 300

        player["ability_cd"] = ABILITY_COOLDOWNS.get(ability_char, 480)
        return True

    if ability_char == "Miguel":
        player["clone_timer"] = 300
        player["clone_hit_cd"] = 0
        player["clone_block_cd"] = 0
        player["ability_cd"] = ABILITY_COOLDOWNS.get(ability_char, 360)
        return True

    if ability_char == "Rafael":
        player["throw_buff_timer"] = 240
        player["ability_cd"] = ABILITY_COOLDOWNS.get(ability_char, 360)
        return True

    if ability_char == "John Jonh":
        player["john_float_timer"] = 300
        player["ability_cd"] = ABILITY_COOLDOWNS.get(ability_char, 360)
        return True

    if (
        ability_char == "Paulo"
        and player.get("roleta_state") == "IDLE"
        and player.get("jackpot_timer", 0) <= 0
    ):
        player["roleta_state"] = "SPINNING"
        player["roleta_timer"] = 120
        player["ability_cd"] = ABILITY_COOLDOWNS.get(ability_char, 480)
        return True

    return False


def get_attack_hoop(team, room=None):
    geo = get_room_geometry(room) if room else get_court_geometry(WIDTH)

    if team == 1:
        return (geo["right_hoop_x1"] + geo["right_hoop_x2"]) / 2, HOOP_Y

    return (geo["left_hoop_x1"] + geo["left_hoop_x2"]) / 2, HOOP_Y


def can_start_dunk(player, ball, player_id, room=None):
    if ball.get("holder") != player_id:
        return False

    if player.get("dunk_active", 0) > 0:
        return False

    if player.get("stun_timer", 0) > 0 or player.get("knockback_timer", 0) > 0:
        return False

    if player.get("roleta_state") == "CUTSCENE":
        return False

    if player["y"] >= GROUND_Y - CHAR_H - 4:
        return False

    hoop_x, hoop_y = get_attack_hoop(player["team"], room)
    player_cx = player["x"] + CHAR_W / 2
    player_cy = player["y"] + CHAR_H / 2
    range_bonus_x = 45 if player.get("dunk_buff_timer", 0) > 0 else 0
    range_bonus_y = 35 if player.get("dunk_buff_timer", 0) > 0 else 0

    return (
        abs(player_cx - hoop_x) <= DUNK_RANGE_X + range_bonus_x
        and abs(player_cy - hoop_y) <= DUNK_RANGE_Y + range_bonus_y
    )


def start_dunk(player, room=None):
    world_width = get_room_width(room) if room else WIDTH
    hoop_x, hoop_y = get_attack_hoop(player["team"], room)
    easy_dunk = player.get("dunk_buff_timer", 0) > 0
    player["dunk_active"] = 1
    player["dunk_timer"] = DUNK_TIMER + (45 if easy_dunk else 0)
    player["dunk_anim_timer"] = 0
    player["dunk_ready_to_score"] = 0
    sequence_len = max(3, DUNK_SEQUENCE_LEN - 2) if easy_dunk else DUNK_SEQUENCE_LEN
    player["dunk_sequence"] = [random.choice(DUNK_KEYS) for _ in range(sequence_len)]
    player["dunk_index"] = 0
    player["dunk_score_team"] = player["team"]
    player["dunk_start_x"] = player["x"]
    player["dunk_start_y"] = player["y"]
    player["dunk_target_x"] = clamp(hoop_x - CHAR_W / 2, 0, world_width - CHAR_W)
    player["dunk_target_y"] = clamp(hoop_y - DUNK_HOLD_OFFSET_Y, 0, GROUND_Y - CHAR_H)


def cancel_dunk(player):
    player["dunk_active"] = 0
    player["dunk_timer"] = 0
    player["dunk_anim_timer"] = 0
    player["dunk_ready_to_score"] = 0
    player["dunk_index"] = 0
    player["dunk_score_team"] = None
    player["dunk_sequence"] = []


def update_dunk_position(player, room=None):
    world_width = get_room_width(room) if room else WIDTH
    player["dunk_anim_timer"] = min(player.get("dunk_anim_timer", 0) + 1, DUNK_ANIM_TIMER)
    t = player["dunk_anim_timer"] / DUNK_ANIM_TIMER
    eased = 1 - (1 - t) * (1 - t)
    arc = math.sin(math.pi * t) * DUNK_JUMP_ARC

    start_x = player.get("dunk_start_x", player["x"])
    start_y = player.get("dunk_start_y", player["y"])
    target_x = player.get("dunk_target_x", player["x"])
    target_y = player.get("dunk_target_y", player["y"])

    player["x"] = clamp(start_x + (target_x - start_x) * eased, 0, world_width - CHAR_W)
    player["y"] = clamp(start_y + (target_y - start_y) * eased - arc, 0, GROUND_Y - CHAR_H)


def release_failed_dunk(room, player_id, player):
    world_width = get_room_width(room)
    ball = room["ball"]
    hoop_x, _ = get_attack_hoop(player["team"], room)
    direction = -1 if hoop_x > world_width / 2 else 1

    safe_x = clamp(hoop_x + direction * (DUNK_RANGE_X + 70), BALL_RAD, world_width - BALL_RAD)
    safe_y = clamp(HOOP_Y + 55, BALL_RAD, GROUND_Y - BALL_RAD)

    player["x"] = clamp(safe_x - CHAR_W / 2, 0, world_width - CHAR_W)
    player["y"] = clamp(safe_y - CHAR_H / 2, 0, GROUND_Y - CHAR_H)

    if ball.get("holder") == player_id:
        ball["holder"] = None
        ball["holder_source"] = None

    ball["x"] = safe_x
    ball["y"] = safe_y
    ball["vel_x"] = direction * 9
    ball["vel_y"] = -7
    ball["dunk_no_score_timer"] = DUNK_NO_SCORE_TIMER


def resolve_dunk_score_team(room):
    for p in room["players"].values():
        scored_team = p.get("pending_dunk_score_team")

        if scored_team:
            p["pending_dunk_score_team"] = None
            return scored_team

    return None


def player_has_clash_ability(p):
    return (
        p.get("dash_timer", 0) > 0
        or p.get("ear_timer", 0) > 0
        or p.get("clone_timer", 0) > 0
        or p.get("john_float_timer", 0) > 0
    )


def can_start_clash(room, p1_id, p2_id):
    if p1_id == p2_id:
        return False

    p1 = room["players"].get(p1_id)
    p2 = room["players"].get(p2_id)

    if not p1 or not p2:
        return False

    if p1.get("team") == p2.get("team"):
        return False

    if p1.get("clash_active", 0) > 0 or p2.get("clash_active", 0) > 0:
        return False

    return player_has_clash_ability(p1) and player_has_clash_ability(p2)


def start_clash(room, p1_id, p2_id):
    if not can_start_clash(room, p1_id, p2_id):
        return False

    room["next_clash_id"] = room.get("next_clash_id", 0) + 1
    clash_id = room["next_clash_id"]
    sequence = [random.choice(CLASH_KEYS) for _ in range(CLASH_SEQUENCE_LEN)]

    for pid, opponent_id in ((p1_id, p2_id), (p2_id, p1_id)):
        p = room["players"][pid]
        p["clash_active"] = 1
        p["clash_id"] = clash_id
        p["clash_timer"] = CLASH_TIMER
        p["clash_sequence"] = sequence[:]
        p["clash_index"] = 0
        p["clash_opponent"] = opponent_id
        p["dash_timer"] = 0
        p["ear_timer"] = 0
        p["clone_timer"] = 0
        p["john_float_timer"] = 0

    return True


def clear_clash_player(p):
    p["clash_active"] = 0
    p["clash_id"] = 0
    p["clash_timer"] = 0
    p["clash_index"] = 0
    p["clash_sequence"] = []
    p["clash_opponent"] = None


def resolve_clash(room, p1_id, p2_id):
    p1 = room["players"].get(p1_id)
    p2 = room["players"].get(p2_id)

    if not p1 or not p2:
        return

    score1 = p1.get("clash_index", 0)
    score2 = p2.get("clash_index", 0)

    if score1 > score2:
        winner, loser = p1, p2
    elif score2 > score1:
        winner, loser = p2, p1
    else:
        winner = None
        loser = None

    if winner and loser:
        direction = 1 if loser["x"] > winner["x"] else -1
        loser["knockback_timer"] = max(loser.get("knockback_timer", 0), 22)
        loser["knockback_vx"] = direction * 18
        loser["stun_timer"] = max(loser.get("stun_timer", 0), 55)

        if room["ball"].get("holder") in (p1_id, p2_id):
            holder_id = room["ball"]["holder"]

            if room["players"].get(holder_id) is loser:
                winner_id = p1_id if winner is p1 else p2_id
                room["ball"]["holder"] = winner_id
                room["ball"]["holder_source"] = "player"
                set_last_touch(room, winner_id)
    else:
        for p in (p1, p2):
            direction = -1 if p is p1 else 1
            p["knockback_timer"] = max(p.get("knockback_timer", 0), 14)
            p["knockback_vx"] = direction * 12
            p["stun_timer"] = max(p.get("stun_timer", 0), 20)

    clear_clash_player(p1)
    clear_clash_player(p2)


def spawn_player_for_match(p_data):
    world_width = int(p_data.get("world_width", WIDTH))
    p_data["x"] = 200 if p_data["team"] == 1 else world_width - 250
    p_data["y"] = GROUND_Y - CHAR_H
    reset_player_status(p_data)


def reset_all_players_after_score(room):
    world_width = get_room_width(room)

    for p_data in room["players"].values():
        p_data["world_width"] = world_width
        spawn_player_for_match(p_data)

    sync_bola_player_to_ball(room)


def set_last_touch(room, player_id):
    if player_id in room["players"]:
        player = room["players"][player_id]
        room["ball"]["last_touch_player"] = player_id
        room["ball"]["last_touch_char"] = player.get("char")


def get_murilo_npc(room, npc_id):
    for npc in room.get("murilo_npcs", []):
        if npc.get("id") == npc_id:
            return npc

    return None


def set_last_touch_from_npc(room, npc):
    owner_id = npc.get("owner_id")

    if owner_id in room["players"]:
        owner = room["players"][owner_id]
        room["ball"]["last_touch_player"] = owner_id
        room["ball"]["last_touch_char"] = owner.get("char")


def give_ball_to_murilo_npc(room, npc):
    ball = room["ball"]
    ball["holder"] = npc["id"]
    ball["holder_source"] = "murilo_npc"
    ball["vel_x"] = 0
    ball["vel_y"] = 0
    set_last_touch_from_npc(room, npc)


def get_caique_rage_gain(player):
    gain = 0

    negative_effect_weights = {
        "stun_timer": 0.55,
        "knockback_timer": 0.35,
        "jump_debuff_timer": 0.25,
        "speed_debuff_timer": 0.25,
        "throw_debuff_timer": 0.25,
        "lag_timer": 0.45,
        "goon_timer": 1.15,
        "dunk_no_score_timer": 0.20,
        "clash_active": 0.20,
    }

    for timer_name, weight in negative_effect_weights.items():
        if player.get(timer_name, 0) > 0:
            gain += weight

    return gain


def release_caique_rage(room, player_id, player):
    rage = float(player.get("caique_rage", 0))

    if rage < 10:
        return False

    rage_factor = min(1.0, rage / 100)
    shout_range = 190 + rage_factor * 260
    push_power = 12 + rage_factor * 18
    enemy_stun = int(45 + rage_factor * 105)
    center_x = player["x"] + CHAR_W / 2
    center_y = player["y"] + CHAR_H / 2

    for target_id, target in room["players"].items():
        if target_id == player_id:
            continue

        target_cx = target["x"] + CHAR_W / 2
        target_cy = target["y"] + CHAR_H / 2
        dx = target_cx - center_x
        dy = target_cy - center_y
        dist = max(1, math.hypot(dx, dy))

        if dist > shout_range:
            continue

        direction = 1 if dx >= 0 else -1
        strength = push_power * (1 - dist / shout_range * 0.35)
        target["knockback_timer"] = max(target.get("knockback_timer", 0), int(18 + rage_factor * 18))
        target["knockback_vx"] = direction * strength

        if target.get("team") != player.get("team"):
            target["stun_timer"] = max(target.get("stun_timer", 0), enemy_stun)

            if room["ball"].get("holder") == target_id:
                room["ball"]["holder"] = None
                room["ball"]["holder_source"] = None
                room["ball"]["vel_x"] = direction * 10
                room["ball"]["vel_y"] = -9
                set_last_touch(room, player_id)

    player["caique_rage"] = 0
    player["caique_shout_timer"] = 45
    player["ability_cd"] = ABILITY_COOLDOWNS.get("Caique", 360)
    return True


def joao_roberto_swap(room, player_id, player):
    ball = room["ball"]
    closest_id = None
    closest_dist = None

    for target_id, target in room["players"].items():
        if target_id == player_id:
            continue

        if target.get("char") is None:
            continue

        target_cx = target["x"] + CHAR_W / 2
        target_cy = target["y"] + CHAR_H / 2
        dist = math.hypot(target_cx - ball["x"], target_cy - ball["y"])

        if closest_dist is None or dist < closest_dist:
            closest_id = target_id
            closest_dist = dist

    if closest_id is None:
        return False

    target = room["players"][closest_id]
    player_x, player_y = player["x"], player["y"]
    player["x"], player["y"] = target["x"], target["y"]
    target["x"], target["y"] = player_x, player_y
    player["vel_y"] = 0
    target["vel_y"] = 0

    if ball.get("holder") == closest_id:
        ball["holder"] = player_id
        ball["holder_source"] = "player"
        ball["vel_x"] = 0
        ball["vel_y"] = 0
        set_last_touch(room, player_id)
    elif ball.get("holder") is None:
        ball["x"] = player["x"] + CHAR_W / 2
        ball["y"] = player["y"] + CHAR_H / 3

    player["ability_cd"] = ABILITY_COOLDOWNS.get("João Roberto", 420)
    return True


def havoc_command(room, player_id, player, target_id, command):
    world_width = get_room_width(room)
    if target_id not in room["players"]:
        try:
            target_id = int(target_id)
        except (TypeError, ValueError):
            return False

    if target_id not in room["players"]:
        return False

    target = room["players"][target_id]

    if target_id == player_id or target.get("team") == player.get("team") or target.get("char") is None:
        return False

    if target.get("jackpot_timer", 0) > 0:
        return False

    ball = room["ball"]
    center_x = player["x"] + CHAR_W / 2
    center_y = player["y"] + CHAR_H / 2
    target_cx = target["x"] + CHAR_W / 2
    direction = 1 if target_cx >= center_x else -1

    if command == "deliver":
        if ball.get("holder") == target_id:
            ball["holder"] = player_id
            ball["holder_source"] = "player"
            ball["vel_x"] = 0
            ball["vel_y"] = 0
            ball["x"] = center_x
            ball["y"] = player["y"] + CHAR_H / 3
            set_last_touch(room, player_id)
        else:
            ball["holder"] = None
            ball["holder_source"] = None
            ball["x"] = target["x"] + CHAR_W / 2
            ball["y"] = target["y"] + CHAR_H / 3
            ball["vel_x"] = -direction * 8
            ball["vel_y"] = -8

        target["stun_timer"] = max(target.get("stun_timer", 0), 45)

    elif command == "freeze":
        target["stun_timer"] = max(target.get("stun_timer", 0), 135)
        target["knockback_timer"] = 0
        target["knockback_vx"] = 0

        if ball.get("holder") == target_id:
            ball["holder"] = None
            ball["holder_source"] = None
            ball["vel_x"] = direction * 5
            ball["vel_y"] = -6

    elif command == "retreat":
        retreat_x = 120 if target.get("team") == 1 else world_width - 120 - CHAR_W
        target["x"] = clamp(retreat_x, 0, world_width - CHAR_W)
        target["y"] = clamp(target["y"], 0, GROUND_Y - CHAR_H)
        target["speed_debuff_timer"] = max(target.get("speed_debuff_timer", 0), 240)
        target["knockback_timer"] = max(target.get("knockback_timer", 0), 20)
        target["knockback_vx"] = -10 if target.get("team") == 1 else 10

        if ball.get("holder") == target_id:
            ball["holder"] = None
            ball["holder_source"] = None
            ball["x"] = target["x"] + CHAR_W / 2
            ball["y"] = target["y"] + CHAR_H / 3
            ball["vel_x"] = -target["knockback_vx"] * 0.8
            ball["vel_y"] = -7

    else:
        return False

    player["havoc_timer"] = 60
    target["havoc_mark_timer"] = 120
    player["ability_cd"] = ABILITY_COOLDOWNS.get("Havoc", 540)
    return True


def bola_self_throw(room, player_id, player, target_x, target_y):
    ball = room["ball"]

    if player.get("char") != "Bola":
        return False

    if ball.get("holder") is not None or ball.get("bola_throw_timer", 0) > 0:
        return False

    try:
        tx = float(target_x)
        ty = float(target_y)
    except (TypeError, ValueError):
        return False

    ball["x"] = player["x"] + CHAR_W / 2
    ball["y"] = player["y"] + CHAR_H / 2
    angle = math.atan2(ty - ball["y"], tx - ball["x"])
    power = 29
    ball["vel_x"] = math.cos(angle) * power
    ball["vel_y"] = math.sin(angle) * power
    ball["holder"] = None
    ball["holder_source"] = None
    ball["bola_throw_timer"] = 90
    ball["shot_origin_x"] = ball["x"]
    ball["shot_origin_y"] = ball["y"]
    ball["score_override"] = None
    set_last_touch(room, player_id)
    player["ability_cd"] = ABILITY_COOLDOWNS.get("Bola", 240)
    return True


def summon_igor_birds(room, player_id, player):
    room.setdefault("igor_birds", [])
    room["igor_birds"] = [bird for bird in room["igor_birds"] if bird.get("owner_id") != player_id][-6:]
    room["next_igor_bird_id"] = room.get("next_igor_bird_id", 0)

    for i in range(3):
        room["next_igor_bird_id"] += 1
        room["igor_birds"].append({
            "id": f"igor_bird_{room['next_igor_bird_id']}",
            "owner_id": player_id,
            "team": player["team"],
            "x": player["x"] + CHAR_W / 2 + (i - 1) * 28,
            "y": player["y"] - 28 - i * 10,
            "timer": 540,
            "hit_cd": 0,
            "phase": i * 30,
        })

    player["ability_cd"] = ABILITY_COOLDOWNS.get("Igor", 420)


def add_ultimate_charge(player, amount):
    if not player.get("char") or amount <= 0:
        return

    ultimate_cost = ULTIMATE_COSTS.get(player.get("char"), ULTIMATE_MAX)
    current = float(player.get("ultimate_charge", 0))
    if current >= ultimate_cost:
        return

    player["ultimate_charge"] = min(ultimate_cost, current + amount)


def knock_enemy_from_player(room, player_id, player, target, stun=90, power=15):
    center_x = player["x"] + CHAR_W / 2
    target_cx = target["x"] + CHAR_W / 2
    direction = 1 if target_cx >= center_x else -1
    target["stun_timer"] = max(target.get("stun_timer", 0), stun)
    target["knockback_timer"] = max(target.get("knockback_timer", 0), 28)
    target["knockback_vx"] = direction * power

    if room["ball"].get("holder") in room["players"] and room["ball"].get("holder") != player_id:
        holder = room["players"][room["ball"]["holder"]]
        if holder is target:
            room["ball"]["holder"] = None
            room["ball"]["holder_source"] = None
            room["ball"]["vel_x"] = direction * 10
            room["ball"]["vel_y"] = -9
            set_last_touch(room, player_id)


def spawn_ultimate_igor_birds(room, player_id, player, count=10):
    room.setdefault("igor_birds", [])
    room["igor_birds"] = [bird for bird in room["igor_birds"] if bird.get("owner_id") != player_id][-6:]
    room["next_igor_bird_id"] = room.get("next_igor_bird_id", 0)

    for i in range(count):
        room["next_igor_bird_id"] += 1
        room["igor_birds"].append({
            "id": f"igor_bird_{room['next_igor_bird_id']}",
            "owner_id": player_id,
            "team": player["team"],
            "x": player["x"] + CHAR_W / 2 + (i - 2.5) * 26,
            "y": player["y"] - 36 - (i % 3) * 14,
            "timer": 780,
            "hit_cd": 0,
            "phase": i * 22,
        })


def spawn_ultimate_murilo_npcs(room, player_id, player, count=3):
    room.setdefault("murilo_npcs", [])
    room["murilo_npcs"] = [npc for npc in room["murilo_npcs"] if npc.get("owner_id") != player_id][-3:]
    room["next_murilo_npc_id"] = room.get("next_murilo_npc_id", 0)

    for i in range(count):
        room["next_murilo_npc_id"] += 1
        room["murilo_npcs"].append({
            "id": f"murilo_npc_{room['next_murilo_npc_id']}",
            "owner_id": player_id,
            "team": player["team"],
            "x": clamp(player["x"] + (i - 1) * 46, 0, get_room_width(room) - CHAR_W),
            "y": player["y"],
            "vel_y": -8 if i == 1 else 0,
            "facing": player.get("facing", 1),
            "shoot_cd": 15 + i * 8,
            "jump_cd": 0,
            "catch_cd": 0,
            "timer": 900,
            "duration": 900,
            "name": "Rabisco Supremo",
        })


def activate_ultimate(room, player_id, player):
    if not player.get("char"):
        return False

    ultimate_cost = ULTIMATE_COSTS.get(player.get("char"), ULTIMATE_MAX)
    if float(player.get("ultimate_charge", 0)) < ultimate_cost:
        return False

    if player.get("stun_timer", 0) > 0 or player.get("clash_active", 0) > 0 or player.get("roleta_state") == "CUTSCENE":
        return False

    char = player.get("char")
    player["ultimate_charge"] = 0
    player["ultimate_flash_timer"] = 150
    player["reaction_text"] = "SUPREMO!"
    player["reaction_timer"] = 140
    ball = room["ball"]
    world_width = get_room_width(room)

    enemies = [
        (target_id, target)
        for target_id, target in room["players"].items()
        if target_id != player_id and target.get("team") != player.get("team") and target.get("char")
    ]
    teammates = [p for p in room["players"].values() if p.get("team") == player.get("team") and p.get("char")]

    if char == "Henrique":
        player["dash_timer"] = max(player.get("dash_timer", 0), 58)
        player["dash_dir"] = player.get("facing", 1)
        player["ability_cd"] = 0
        for _, enemy in enemies:
            if math.hypot(enemy["x"] - player["x"], enemy["y"] - player["y"]) <= 210:
                knock_enemy_from_player(room, player_id, player, enemy, 85, 20)

    elif char == "Natan":
        player["invisible_timer"] = max(player.get("invisible_timer", 0), 780)
        player["speed_debuff_timer"] = 0
        if ball.get("holder") in room["players"] and room["players"][ball["holder"]].get("team") != player.get("team"):
            victim_id = ball["holder"]
            victim = room["players"][victim_id]
            ball["holder"] = player_id
            ball["holder_source"] = "player"
            victim["stun_timer"] = max(victim.get("stun_timer", 0), 75)
            set_last_touch(room, player_id)
        elif ball.get("holder") is None:
            player["x"] = clamp(ball["x"] - CHAR_W / 2, 0, world_width - CHAR_W)
            player["y"] = clamp(ball["y"] - CHAR_H / 2, 0, GROUND_Y - CHAR_H)

    elif char == "Presscinotti":
        player["ear_timer"] = max(player.get("ear_timer", 0), 820)
        for _, enemy in enemies:
            if math.hypot(enemy["x"] - player["x"], enemy["y"] - player["y"]) <= 460:
                knock_enemy_from_player(room, player_id, player, enemy, 145, 24)

    elif char == "Diogo":
        for teammate in teammates:
            teammate["cookie_buff_timer"] = max(teammate.get("cookie_buff_timer", 0), 960)
            teammate["jump_buff_timer"] = max(teammate.get("jump_buff_timer", 0), 640)
            teammate["throw_buff_timer"] = max(teammate.get("throw_buff_timer", 0), 640)
            teammate["dunk_buff_timer"] = max(teammate.get("dunk_buff_timer", 0), 420)
        for _, enemy in enemies:
            enemy["speed_debuff_timer"] = max(enemy.get("speed_debuff_timer", 0), 360)
            enemy["throw_debuff_timer"] = max(enemy.get("throw_debuff_timer", 0), 360)

    elif char == "Miguel":
        player["clone_timer"] = max(player.get("clone_timer", 0), 980)
        player["clone_hit_cd"] = 0
        player["clone_block_cd"] = 0
        player["throw_buff_timer"] = max(player.get("throw_buff_timer", 0), 420)
        if ball.get("holder") is None:
            ball["holder"] = player_id
            ball["holder_source"] = "player"
            set_last_touch(room, player_id)

    elif char == "Rafael":
        player["throw_buff_timer"] = max(player.get("throw_buff_timer", 0), 980)
        player["dunk_buff_timer"] = max(player.get("dunk_buff_timer", 0), 620)
        if ball.get("holder") == player_id:
            hoop_x, hoop_y = get_attack_hoop(player["team"], room)
            vx, vy = get_npc_shot_velocity(ball["x"], ball["y"], hoop_x, hoop_y)
            ball["vel_x"] = vx * 1.35
            ball["vel_y"] = vy * 1.15
            ball["holder"] = None
            ball["holder_source"] = None
            ball["score_override"] = 3
            set_last_touch(room, player_id)

    elif char == "John Jonh":
        for teammate in teammates:
            teammate["john_float_timer"] = max(teammate.get("john_float_timer", 0), 820)
            teammate["jump_buff_timer"] = max(teammate.get("jump_buff_timer", 0), 560)
        for _, enemy in enemies:
            enemy["jump_debuff_timer"] = max(enemy.get("jump_debuff_timer", 0), 480)

    elif char == "Paulo":
        player["jackpot_timer"] = max(player.get("jackpot_timer", 0), 900)
        player["roleta_state"] = "IDLE"
        player["roleta_timer"] = 0
        for teammate in teammates:
            teammate["throw_buff_timer"] = max(teammate.get("throw_buff_timer", 0), 360)
        for _, enemy in enemies:
            if random.random() < 0.7:
                enemy["stun_timer"] = max(enemy.get("stun_timer", 0), 80)
            else:
                enemy["speed_debuff_timer"] = max(enemy.get("speed_debuff_timer", 0), 420)

    elif char == "Treinador":
        for teammate in teammates:
            teammate["cookie_buff_timer"] = max(teammate.get("cookie_buff_timer", 0), 560)
            teammate["jump_buff_timer"] = max(teammate.get("jump_buff_timer", 0), 560)
            teammate["throw_buff_timer"] = max(teammate.get("throw_buff_timer", 0), 560)
            teammate["dunk_buff_timer"] = max(teammate.get("dunk_buff_timer", 0), 500)
            teammate["ability_cd"] = min(teammate.get("ability_cd", 0), 60)

    elif char == "Murilo":
        player["throw_buff_timer"] = max(player.get("throw_buff_timer", 0), 680)
        player["jump_buff_timer"] = max(player.get("jump_buff_timer", 0), 680)
        player["dunk_buff_timer"] = max(player.get("dunk_buff_timer", 0), 560)
        spawn_ultimate_murilo_npcs(room, player_id, player, 3)
        for _, enemy in enemies:
            if math.hypot(enemy["x"] - player["x"], enemy["y"] - player["y"]) <= 380:
                knock_enemy_from_player(room, player_id, player, enemy, 125, 20)

    elif char == "Igor":
        spawn_ultimate_igor_birds(room, player_id, player)
        for _, enemy in enemies:
            enemy["stun_timer"] = max(enemy.get("stun_timer", 0), 35)

    elif char == "Laiz":
        for _, enemy in enemies:
            enemy["lag_timer"] = max(enemy.get("lag_timer", 0), 900)
            enemy["lag_tick"] = 0
            enemy["stun_timer"] = max(enemy.get("stun_timer", 0), 55)
            enemy["x"] = clamp(enemy["x"] + random.choice([-95, -65, 65, 95]), 0, world_width - CHAR_W)

    elif char == "Kau\u00e3":
        for _, enemy in enemies:
            enemy["goon_timer"] = max(enemy.get("goon_timer", 0), 900)
            enemy["speed_debuff_timer"] = max(enemy.get("speed_debuff_timer", 0), 480)
            enemy["stun_timer"] = max(enemy.get("stun_timer", 0), 35)

    elif char == "Caique":
        player["caique_rage"] = 100
        release_caique_rage(room, player_id, player)
        for _, enemy in enemies:
            if math.hypot(enemy["x"] - player["x"], enemy["y"] - player["y"]) <= 520:
                knock_enemy_from_player(room, player_id, player, enemy, 145, 28)

    elif char == "Jo\u00e3o Roberto":
        joao_roberto_swap(room, player_id, player)
        ball["holder"] = player_id
        ball["holder_source"] = "player"
        set_last_touch(room, player_id)
        for i, (_, enemy) in enumerate(enemies):
            enemy["x"] = clamp(ball["x"] + (i - len(enemies) / 2) * 42, 0, world_width - CHAR_W)
            enemy["y"] = clamp(ball["y"] - CHAR_H / 2, 0, GROUND_Y - CHAR_H)
            enemy["stun_timer"] = max(enemy.get("stun_timer", 0), 105)

    elif char == "Havoc":
        for target_id, enemy in enemies:
            havoc_command(room, player_id, player, target_id, random.choice(["deliver", "freeze", "retreat"]))
            enemy["lag_timer"] = max(enemy.get("lag_timer", 0), 220)
            enemy["goon_timer"] = max(enemy.get("goon_timer", 0), 220)
        player["ability_cd"] = 0

    elif char == "Bola":
        hoop_x, hoop_y = get_attack_hoop(player["team"], room)
        if bola_self_throw(room, player_id, player, hoop_x, hoop_y):
            ball["vel_x"] *= 1.75
            ball["vel_y"] *= 1.35
            ball["score_override"] = 3
            player["ability_cd"] = 0
            for _, enemy in enemies:
                if math.hypot(enemy["x"] - player["x"], enemy["y"] - player["y"]) <= 260:
                    knock_enemy_from_player(room, player_id, player, enemy, 80, 18)

    else:
        player["throw_buff_timer"] = max(player.get("throw_buff_timer", 0), 560)

    return True

def update_igor_birds(room):
    world_width = get_room_width(room)
    birds = room.get("igor_birds", [])

    if not birds:
        return

    updated = []
    ball = room["ball"]

    for bird in birds:
        owner_id = bird.get("owner_id")
        owner = room["players"].get(owner_id)

        if not owner:
            continue

        bird["timer"] = bird.get("timer", 0) - 1

        if bird["timer"] <= 0:
            continue

        if bird.get("hit_cd", 0) > 0:
            bird["hit_cd"] -= 1

        target_x = ball.get("x", bird["x"])
        target_y = ball.get("y", bird["y"])
        holder_id = ball.get("holder")
        owner_has_ball = holder_id == owner_id

        if owner_has_ball:
            bird["disabled_until_ground"] = True

        if bird.get("disabled_until_ground"):
            if ball.get("holder") is None and ball.get("y", 0) >= GROUND_Y - BALL_RAD - 4:
                bird["disabled_until_ground"] = False
            else:
                formation_offset = (int(str(bird.get("id", "0")).split("_")[-1]) % 3 - 1) * 70
                target_x = clamp(owner["x"] + CHAR_W / 2 + formation_offset, 50, world_width - 50)
                target_y = 55 + (int(str(bird.get("id", "0")).split("_")[-1]) % 2) * 18

        if not bird.get("disabled_until_ground") and holder_id in room["players"] and room["players"][holder_id].get("team") != bird.get("team"):
            holder = room["players"][holder_id]
            target_x = holder["x"] + CHAR_W / 2
            target_y = holder["y"] + CHAR_H / 2
        elif not bird.get("disabled_until_ground") and holder_id:
            target_x = owner["x"] + CHAR_W / 2
            target_y = owner["y"] - 45

        bird["phase"] = bird.get("phase", 0) + 1
        target_y += math.sin(bird["phase"] / 8) * 18
        dx = target_x - bird["x"]
        dy = target_y - bird["y"]
        dist = max(1, math.hypot(dx, dy))
        speed = 8.5
        bird["x"] = clamp(bird["x"] + dx / dist * speed, 0, world_width)
        bird["y"] = clamp(bird["y"] + dy / dist * speed, 20, GROUND_Y - 15)

        if not bird.get("disabled_until_ground") and holder_id in room["players"] and room["players"][holder_id].get("team") != bird.get("team"):
            holder = room["players"][holder_id]
            holder_cx = holder["x"] + CHAR_W / 2
            holder_cy = holder["y"] + CHAR_H / 2

            if bird.get("hit_cd", 0) <= 0 and math.hypot(holder_cx - bird["x"], holder_cy - bird["y"]) <= 42:
                holder["stun_timer"] = max(holder.get("stun_timer", 0), 24)
                holder["knockback_timer"] = max(holder.get("knockback_timer", 0), 10)
                holder["knockback_vx"] = 8 if holder_cx >= bird["x"] else -8
                ball["holder"] = owner_id
                ball["holder_source"] = "player"
                set_last_touch(room, owner_id)
                bird["hit_cd"] = 45

        elif (
            not bird.get("disabled_until_ground")
            and ball.get("holder") is None
            and math.hypot(ball["x"] - bird["x"], ball["y"] - bird["y"]) <= CATCH_DIST + 16
        ):
            ball["holder"] = owner_id
            ball["holder_source"] = "player"
            set_last_touch(room, owner_id)
            bird["hit_cd"] = 35

        updated.append(bird)

    room["igor_birds"] = updated


def get_npc_shot_velocity(start_x, start_y, hoop_x, hoop_y):
    direction = 1 if hoop_x >= start_x else -1
    best = None
    common_throw_power = 27.5

    for angle_deg in range(18, 78, 3):
        angle = math.radians(angle_deg)
        vx = math.cos(angle) * common_throw_power * direction
        vy = -math.sin(angle) * common_throw_power

        if abs(vx) < 0.1:
            continue

        ticks_to_hoop = (hoop_x - start_x) / vx

        if ticks_to_hoop <= 0:
            continue

        predicted_y = start_y + vy * ticks_to_hoop + 0.5 * GRAVITY * ticks_to_hoop * ticks_to_hoop
        error = abs(predicted_y - hoop_y)

        if best is None or error < best[0]:
            best = (error, vx, vy)

    if best:
        return best[1], best[2]

    fallback_angle = math.atan2(hoop_y - start_y, hoop_x - start_x)
    return math.cos(fallback_angle) * common_throw_power, math.sin(fallback_angle) * common_throw_power


def get_skip_votes_display(room):
    return list(room.get("skip_votes", set()))


def apply_bot_skip_votes(room):
    if room.get("replay_timer", 0) <= 0:
        return

    room.setdefault("skip_votes", set())

    for pid, player in room["players"].items():
        if player.get("is_bot"):
            room["skip_votes"].add(pid)

    room["skip_votes_display"] = get_skip_votes_display(room)

    connected_players = set(room["players"].keys())

    if connected_players and room["skip_votes"] >= connected_players:
        room["replay_timer"] = 0
        room["skip_votes"] = set()
        room["skip_votes_display"] = []


def player_label(player_id, player):
    name = player.get("bot_name") if player.get("is_bot") else f"P{player_id}"
    return f"{name} - {player.get('char', '???')}"


def build_match_awards(room):
    players = [(pid, p) for pid, p in room["players"].items() if p.get("char")]

    if not players:
        room["match_awards"] = []
        room["match_highlights"] = []
        return

    def best_by(key):
        pid, player = max(players, key=lambda item: item[1].get(key, 0))
        return player_label(pid, player), int(player.get(key, 0))

    scorer_name, scorer_points = best_by("match_points")
    steal_name, steals = best_by("match_steals")
    possession_name, possession_ticks = best_by("match_possession_ticks")
    humiliated_name, humiliated_count = best_by("match_humiliated")

    mvp_pid, mvp_player = max(
        players,
        key=lambda item: (
            item[1].get("match_points", 0) * 3
            + item[1].get("match_steals", 0) * 5
            + item[1].get("match_baskets", 0) * 4
            + item[1].get("match_possession_ticks", 0) / 60
            - item[1].get("match_humiliated", 0) * 2
        ),
    )

    room["match_awards"] = [
        {"title": "MVP", "value": player_label(mvp_pid, mvp_player), "detail": f"{mvp_player.get('match_points', 0)} pts"},
        {"title": "Cestinha", "value": scorer_name, "detail": f"{scorer_points} pontos"},
        {"title": "Ladrao", "value": steal_name, "detail": f"{steals} roubos"},
        {"title": "Dono da Bola", "value": possession_name, "detail": f"{possession_ticks // FPS}s com a bola"},
        {"title": "Mais Humilhado", "value": humiliated_name, "detail": f"{humiliated_count} travadas/empurroes"},
    ]

    last_scorer = room.get("last_score_char") or "ninguem"
    room["match_highlights"] = [
        f"Maior cesta: {scorer_name} carregou o placar com {scorer_points} pontos.",
        f"Maior tombo: {humiliated_name} sofreu {humiliated_count} humilhacoes.",
        f"Jogada caotica: ultimo ponto saiu com {last_scorer} valendo {room.get('last_score_points', 2)}.",
    ]


def award_score(room, scored_team):
    world_width = get_room_width(room)
    ball = room["ball"]
    points = get_score_points(room, scored_team)
    room["score"][scored_team - 1] += points

    scorer_id = ball.get("last_touch_player")

    if scorer_id in room["players"]:
        scorer = room["players"][scorer_id]
        scorer["match_points"] = scorer.get("match_points", 0) + points
        scorer["match_baskets"] = scorer.get("match_baskets", 0) + 1
        add_ultimate_charge(scorer, 24 + points * 3)
    room["replay_id"] = room.get("replay_id", 0) + 1
    room["replay_timer"] = 360

    room["skip_votes"] = set()
    room["skip_votes_display"] = []

    room["last_score_team"] = scored_team
    room["last_score_points"] = points
    room["last_score_char"] = ball.get("last_touch_char")
    room["last_score_player"] = ball.get("last_touch_player")

    ball["x"] = world_width // 2
    ball["y"] = HEIGHT // 2 - 100
    ball["vel_x"] = 0
    ball["vel_y"] = 0
    ball["holder"] = None
    ball["holder_source"] = None
    ball["last_touch_player"] = None
    ball["last_touch_char"] = None
    ball["shot_origin_x"] = None
    ball["shot_origin_y"] = None
    ball["score_override"] = None
    ball["bola_throw_timer"] = 0
    room["murilo_npcs"] = []
    room["igor_birds"] = []

    reset_all_players_after_score(room)

    win_points = room.get("win_points", DEFAULT_WIN_POINTS)

    if room["score"][0] >= win_points:
        room["game_started"] = False
        room["game_over"] = True
        room["winner_team"] = 1
        build_match_awards(room)
        _persist_match_history(room)  # SPEC-05

    elif room["score"][1] >= win_points:
        room["game_started"] = False
        room["game_over"] = True
        room["winner_team"] = 2
        build_match_awards(room)
        _persist_match_history(room)  # SPEC-05


def _persist_match_history(room):
    """SPEC-05: grava o resultado da partida no placar persistente local."""
    try:
        save_db.record_match_history(
            room_code=room.get("room_code"),
            winner_team=room.get("winner_team"),
            score=room.get("score", [0, 0]),
            duration_ticks=room.get("frame_counter", 0),
        )
    except Exception as e:
        print(f"[SPEC-05] falha ao registrar historico: {e}")


def update_murilo_npcs(room):
    npcs = room.get("murilo_npcs", [])

    if not npcs:
        return

    updated_npcs = []
    ball = room["ball"]

    for npc in npcs:
        owner_id = npc.get("owner_id")
        owner = room["players"].get(owner_id)

        if not owner:
            continue

        npc["timer"] = npc.get("timer", 0) - 1

        if npc["timer"] <= 0:
            if ball.get("holder") == npc.get("id"):
                ball["holder"] = None
                ball["holder_source"] = None
            continue

        npc.setdefault("vel_y", 0)
        npc.setdefault("facing", 1)
        npc.setdefault("shoot_cd", 0)
        npc.setdefault("jump_cd", 0)
        npc.setdefault("catch_cd", 0)

        if npc["shoot_cd"] > 0:
            npc["shoot_cd"] -= 1

        if npc["jump_cd"] > 0:
            npc["jump_cd"] -= 1

        if npc["catch_cd"] > 0:
            npc["catch_cd"] -= 1

        holder_id = ball.get("holder")
        has_ball = holder_id == npc.get("id")
        world_width = get_room_width(room)
        hoop_x, hoop_y = get_attack_hoop(npc["team"], room)
        defend_x, _ = get_attack_hoop(2 if npc["team"] == 1 else 1, room)
        target_x = ball.get("x", npc["x"])
        target_y = ball.get("y", npc["y"])

        if has_ball:
            attack_spot = clamp(hoop_x + (-185 if npc["team"] == 1 else 185), 80, world_width - 80)
            target_x = attack_spot
            target_y = GROUND_Y - CHAR_H
            distance_to_hoop = math.hypot((npc["x"] + CHAR_W / 2) - hoop_x, (npc["y"] + CHAR_H / 2) - hoop_y)

            if distance_to_hoop <= 390 and npc["shoot_cd"] <= 0:
                shot_vx, shot_vy = get_npc_shot_velocity(ball["x"], ball["y"], hoop_x, hoop_y)
                ball["vel_x"] = shot_vx
                ball["vel_y"] = shot_vy
                ball["holder"] = None
                ball["holder_source"] = None
                ball["shot_origin_x"] = npc["x"] + CHAR_W / 2
                ball["shot_origin_y"] = npc["y"] + CHAR_H / 2
                ball["score_override"] = None
                set_last_touch_from_npc(room, npc)
                npc["shoot_cd"] = 90
                npc["catch_cd"] = 20

        elif holder_id in room["players"]:
            holder = room["players"][holder_id]

            if holder.get("team") != npc.get("team"):
                target_x = holder["x"] + CHAR_W / 2
                target_y = holder["y"] + CHAR_H / 2
            else:
                target_x = clamp(holder["x"] + (-80 if npc["team"] == 1 else 80), 0, world_width - CHAR_W)
                target_y = GROUND_Y - CHAR_H
        elif holder_id:
            target_x = defend_x
            target_y = GROUND_Y - CHAR_H

        dx = target_x - (npc["x"] + CHAR_W / 2)
        speed = 7.2

        if abs(dx) > 8:
            npc["x"] = clamp(npc["x"] + (speed if dx > 0 else -speed), 0, world_width - CHAR_W)
            npc["facing"] = 1 if dx > 0 else -1

        if holder_id in room["players"] and room["players"][holder_id].get("team") != npc.get("team"):
            holder = room["players"][holder_id]

            if math.hypot((holder["x"] + CHAR_W / 2) - npc["x"], (holder["y"] + CHAR_H / 2) - npc["y"]) <= 42:
                give_ball_to_murilo_npc(room, npc)
                holder["stun_timer"] = max(holder.get("stun_timer", 0), 45)

        if (
            ball.get("holder") is None
            and npc.get("catch_cd", 0) <= 0
            and math.hypot(ball["x"] - (npc["x"] + CHAR_W / 2), ball["y"] - (npc["y"] + CHAR_H / 2)) <= CATCH_DIST + 18
        ):
            give_ball_to_murilo_npc(room, npc)

        if ball.get("holder") == npc.get("id"):
            ball["x"] = npc["x"] + CHAR_W / 2
            ball["y"] = npc["y"] + CHAR_H / 3
            ball["vel_x"] = 0
            ball["vel_y"] = 0
            set_last_touch_from_npc(room, npc)

        should_jump = (
            npc["jump_cd"] <= 0
            and npc["y"] >= GROUND_Y - CHAR_H - 2
            and (
                (ball.get("holder") is None and abs(ball["x"] - npc["x"]) <= 90 and ball["y"] < npc["y"] - 20)
                or (ball.get("holder") == npc.get("id") and abs((npc["x"] + CHAR_W / 2) - hoop_x) <= 270)
            )
        )

        if should_jump:
            npc["vel_y"] = -15
            npc["jump_cd"] = 45

        npc["vel_y"] += GRAVITY
        npc["y"] += npc["vel_y"]

        if npc["y"] >= GROUND_Y - CHAR_H:
            npc["y"] = GROUND_Y - CHAR_H
            npc["vel_y"] = 0

        npc["x"] = clamp(npc["x"], 0, world_width - CHAR_W)
        npc["y"] = clamp(npc["y"], 0, GROUND_Y - CHAR_H)

        updated_npcs.append(npc)

    room["murilo_npcs"] = updated_npcs


def update_training_bots(room):
    ball = room["ball"]
    world_width = get_room_width(room)

    for pid, bot in list(room["players"].items()):
        if not bot.get("is_bot") or not bot.get("char"):
            continue

        if bot.get("stun_timer", 0) > 0 or bot.get("knockback_timer", 0) > 0 or bot.get("dunk_active", 0) > 0:
            continue

        bot["bot_jump_cd"] = max(0, bot.get("bot_jump_cd", 0) - 1)
        if bot.get("ultimate_charge", 0) >= ULTIMATE_COSTS.get(bot.get("char"), ULTIMATE_MAX) and random.random() < 0.025:
            activate_ultimate(room, pid, bot)

        has_ball = ball.get("holder") == pid
        nearest_enemy = None
        nearest_enemy_id = None
        nearest_enemy_dist = None

        for other_id, other in room["players"].items():
            if other_id == pid or other.get("team") == bot.get("team") or not other.get("char"):
                continue

            dist = math.hypot((other["x"] + CHAR_W / 2) - (bot["x"] + CHAR_W / 2), (other["y"] + CHAR_H / 2) - (bot["y"] + CHAR_H / 2))

            if nearest_enemy_dist is None or dist < nearest_enemy_dist:
                nearest_enemy = other
                nearest_enemy_id = other_id
                nearest_enemy_dist = dist

        if bot.get("ability_cd", 0) <= 0 and bot.get("clash_active", 0) <= 0:
            char = bot.get("char")
            used_ability = False

            if char == "Henrique" and ball.get("holder") in room["players"] and room["players"][ball["holder"]].get("team") != bot.get("team"):
                bot["facing"] = 1 if room["players"][ball["holder"]]["x"] > bot["x"] else -1
                used_ability = apply_character_ability(room, bot, "Henrique", bot.get("facing", 1))
            elif char == "Natan" and nearest_enemy_dist is not None and nearest_enemy_dist < 220:
                used_ability = apply_character_ability(room, bot, "Natan", bot.get("facing", 1))
            elif char == "Presscinotti" and nearest_enemy_dist is not None and nearest_enemy_dist < 120:
                used_ability = apply_character_ability(room, bot, "Presscinotti", bot.get("facing", 1))
            elif char == "Diogo" and random.random() < 0.015:
                used_ability = apply_character_ability(room, bot, "Diogo", bot.get("facing", 1))
            elif char == "Miguel" and (has_ball or (nearest_enemy_dist is not None and nearest_enemy_dist < 180)):
                used_ability = apply_character_ability(room, bot, "Miguel", bot.get("facing", 1))
            elif char == "Rafael" and has_ball:
                used_ability = apply_character_ability(room, bot, "Rafael", bot.get("facing", 1))
            elif char == "John Jonh" and bot["y"] < GROUND_Y - CHAR_H - 20:
                used_ability = apply_character_ability(room, bot, "John Jonh", bot.get("facing", 1))
            elif char == "Paulo" and random.random() < 0.012:
                used_ability = apply_character_ability(room, bot, "Paulo", bot.get("facing", 1))
            elif char == "Igor" and random.random() < 0.015:
                summon_igor_birds(room, pid, bot)
                used_ability = True
            elif char == "Laiz" and nearest_enemy is not None and random.random() < 0.015:
                for p in room["players"].values():
                    if p.get("team") != bot.get("team"):
                        p["lag_timer"] = max(p.get("lag_timer", 0), 300)
                        p["lag_tick"] = 0
                bot["ability_cd"] = ABILITY_COOLDOWNS.get("Laiz", 480)
                used_ability = True
            elif char == "Kauã" and nearest_enemy is not None and random.random() < 0.015:
                for p in room["players"].values():
                    if p.get("team") != bot.get("team"):
                        p["goon_timer"] = max(p.get("goon_timer", 0), 300)
                bot["ability_cd"] = ABILITY_COOLDOWNS.get("Kauã", 480)
                used_ability = True
            elif char == "Caique" and float(bot.get("caique_rage", 0)) >= 10:
                used_ability = release_caique_rage(room, pid, bot)
            elif char == "João Roberto" and random.random() < 0.018:
                used_ability = joao_roberto_swap(room, pid, bot)
            elif char == "Havoc" and nearest_enemy is not None and random.random() < 0.016:
                used_ability = havoc_command(room, pid, bot, nearest_enemy_id, random.choice(["deliver", "freeze", "retreat"]))
            elif char == "Bola" and ball.get("holder") is None and random.random() < 0.02:
                hoop_x, hoop_y = get_attack_hoop(bot["team"], room)
                used_ability = bola_self_throw(room, pid, bot, hoop_x, hoop_y)

            if used_ability:
                bot["reaction_text"] = "Poder!"
                bot["reaction_timer"] = 80

        if has_ball:
            hoop_x, hoop_y = get_attack_hoop(bot["team"], room)
            dist_to_hoop = abs((bot["x"] + CHAR_W / 2) - hoop_x)

            if dist_to_hoop <= 420:
                vx, vy = get_npc_shot_velocity(ball["x"], ball["y"], hoop_x, hoop_y)
                ball["vel_x"] = vx
                ball["vel_y"] = vy
                ball["holder"] = None
                ball["holder_source"] = None
                ball["shot_origin_x"] = bot["x"] + CHAR_W / 2
                ball["shot_origin_y"] = bot["y"] + CHAR_H / 2
                ball["score_override"] = None
                set_last_touch(room, pid)
            else:
                target_x = hoop_x + (-220 if bot["team"] == 1 else 220)
                bot["x"] += 4.8 if target_x > bot["x"] else -4.8
        else:
            target_x = ball["x"]

            if ball.get("holder") in room["players"]:
                holder = room["players"][ball["holder"]]

                if holder.get("team") == bot.get("team"):
                    hoop_x, _ = get_attack_hoop(bot["team"], room)
                    target_x = hoop_x + (-260 if bot["team"] == 1 else 260)
                else:
                    target_x = holder["x"]

            if abs(target_x - bot["x"]) > 8:
                bot["x"] += 5.2 if target_x > bot["x"] else -5.2
                bot["facing"] = 1 if target_x > bot["x"] else -1

        if bot["bot_jump_cd"] <= 0 and bot["y"] >= GROUND_Y - CHAR_H - 2 and ball["y"] < bot["y"] - 35 and abs(ball["x"] - bot["x"]) < 110:
            bot["vel_y"] = -15
            bot["bot_jump_cd"] = 45

        bot["vel_y"] = bot.get("vel_y", 0) + GRAVITY
        bot["y"] += bot["vel_y"]

        if bot["y"] >= GROUND_Y - CHAR_H:
            bot["y"] = GROUND_Y - CHAR_H
            bot["vel_y"] = 0

        bot["x"] = clamp(bot["x"], 0, world_width - CHAR_W)
        bot["y"] = clamp(bot["y"], 0, GROUND_Y - CHAR_H)


def room_physics_loop(room_code):
    while room_code in rooms and rooms[room_code]["game_started"]:
        room = rooms[room_code]
        room["frame_counter"] = room.get("frame_counter", 0) + 1  # SPEC-02
        update_room_world_width(room)
        world_width = get_room_width(room)
        geo = get_room_geometry(room)

        for p in room["players"].values():
            p["world_width"] = world_width

        ball = room["ball"]
        room["ball"]["world_width"] = world_width

        holder_id = ball.get("holder")

        if holder_id in room["players"]:
            room["players"][holder_id]["match_possession_ticks"] = room["players"][holder_id].get("match_possession_ticks", 0) + 1
            add_ultimate_charge(room["players"][holder_id], 0.04)

            previous_holder = room.get("last_holder_for_steal")

            if (
                previous_holder in room["players"]
                and previous_holder != holder_id
                and room["players"][previous_holder].get("team") != room["players"][holder_id].get("team")
            ):
                room["players"][holder_id]["match_steals"] = room["players"][holder_id].get("match_steals", 0) + 1

            room["last_holder_for_steal"] = holder_id
        elif holder_id is None:
            room["last_holder_for_steal"] = None

        for p in room["players"].values():
            if p.get("char"):
                add_ultimate_charge(p, 0.015)

        # Durante o replay, congela a partida.
        if room.get("replay_timer", 0) > 0:
            apply_bot_skip_votes(room)
            room["replay_timer"] -= 1
            time.sleep(1 / FPS)
            continue

        prev_ball_y = ball["y"]

        if ball.get("dunk_no_score_timer", 0) > 0:
            ball["dunk_no_score_timer"] -= 1

        # =====================================================
        # FÍSICA DA BOLA
        # =====================================================
        update_training_bots(room)

        if ball.get("bola_throw_timer", 0) > 0:
            ball["bola_throw_timer"] -= 1

        bola_player_id = get_bola_player_id(room)
        bola_controls_ball = (
            bola_player_id in room["players"]
            and ball.get("holder") is None
            and ball.get("bola_throw_timer", 0) <= 0
        )

        if bola_controls_ball:
            bola_player = room["players"][bola_player_id]
            ball["x"] = clamp(bola_player["x"] + CHAR_W / 2, BALL_RAD, world_width - BALL_RAD)
            ball["y"] = clamp(bola_player["y"] + CHAR_H / 2, BALL_RAD, GROUND_Y - BALL_RAD)
            ball["vel_x"] = 0
            ball["vel_y"] = 0

            for pid, p in list(room["players"].items()):
                if pid == bola_player_id or p.get("roleta_state") == "CUTSCENE":
                    continue

                char_center_x = p["x"] + CHAR_W // 2
                char_center_y = p["y"] + CHAR_H // 2
                dist = math.hypot(char_center_x - ball["x"], char_center_y - ball["y"])

                if dist < CATCH_DIST:
                    ball["holder"] = pid
                    ball["holder_source"] = "player"
                    set_last_touch(room, pid)
                    break

        elif ball["holder"] is None:
            ball["vel_y"] += GRAVITY
            ball["x"] += ball["vel_x"]
            ball["y"] += ball["vel_y"]

            ball_floor_hit = GROUND_Y - BALL_RAD

            if ball["y"] >= ball_floor_hit:
                ball["y"] = ball_floor_hit
                ball["vel_y"] *= -0.7
                ball["vel_x"] *= 0.9

            if ball["x"] <= BALL_RAD:
                ball["x"] = BALL_RAD
                ball["vel_x"] *= -0.8

            if ball["x"] >= world_width - BALL_RAD:
                ball["x"] = world_width - BALL_RAD
                ball["vel_x"] *= -0.8

            resolve_hoop_collisions(ball, room)

            for pid, p in list(room["players"].items()):
                if pid == bola_player_id:
                    continue

                if p.get("roleta_state") == "CUTSCENE":
                    continue

                char_center_x = p["x"] + CHAR_W // 2
                char_center_y = p["y"] + CHAR_H // 2
                dist = math.hypot(char_center_x - ball["x"], char_center_y - ball["y"])

                if dist < CATCH_DIST:
                    ball["holder"] = pid
                    ball["holder_source"] = "player"
                    set_last_touch(room, pid)
                    break

                if p.get("clone_timer", 0) > 0:
                    clone_rect = get_clone_rect(p)
                    clone_center_x, clone_center_y = center_of_rect(clone_rect)
                    clone_dist = math.hypot(clone_center_x - ball["x"], clone_center_y - ball["y"])

                    if clone_dist < CATCH_DIST + 10:
                        ball["holder"] = pid
                        ball["holder_source"] = "clone"
                        set_last_touch(room, pid)
                        break

                    if clone_dist < CATCH_DIST + 25 and p.get("clone_block_cd", 0) <= 0:
                        direction = 1 if ball["x"] > clone_center_x else -1
                        ball["vel_x"] = direction * 16
                        ball["vel_y"] = -12
                        p["clone_block_cd"] = 25
                        set_last_touch(room, pid)

        else:
            holder_id = ball["holder"]

            if holder_id in room["players"]:
                p = room["players"][holder_id]

                if p.get("roleta_state") == "CUTSCENE":
                    ball["holder"] = None
                    ball["holder_source"] = None
                else:
                    set_last_touch(room, holder_id)

                    if ball.get("holder_source") == "clone" and p.get("clone_timer", 0) > 0:
                        clone_rect = get_clone_rect(p)
                        clone_center_x, clone_center_y = center_of_rect(clone_rect)
                        ball["x"] = clone_center_x
                        ball["y"] = clone_center_y - 10
                    else:
                        ball["x"] = p["x"] + CHAR_W // 2
                        ball["y"] = p["y"] + CHAR_H // 3

                    ball["vel_x"] = 0
                    ball["vel_y"] = 0
            elif ball.get("holder_source") == "murilo_npc":
                npc = get_murilo_npc(room, holder_id)

                if npc:
                    ball["x"] = npc["x"] + CHAR_W // 2
                    ball["y"] = npc["y"] + CHAR_H // 3
                    ball["vel_x"] = 0
                    ball["vel_y"] = 0
                    set_last_touch_from_npc(room, npc)
                else:
                    ball["holder"] = None
                    ball["holder_source"] = None
            else:
                ball["holder"] = None
                ball["holder_source"] = None

        if not bola_controls_ball:
            sync_bola_player_to_ball(room)

        # =====================================================
        # PONTUAÇÃO
        # =====================================================
        scored_team = resolve_dunk_score_team(room)

        if (
            scored_team is None
            and ball.get("dunk_no_score_timer", 0) <= 0
            and ball_crossed_hoop(prev_ball_y, ball, geo["left_hoop_x1"], geo["left_hoop_x2"])
        ):
            scored_team = 2

        elif (
            scored_team is None
            and ball.get("dunk_no_score_timer", 0) <= 0
            and ball_crossed_hoop(prev_ball_y, ball, geo["right_hoop_x1"], geo["right_hoop_x2"])
        ):
            scored_team = 1

        if scored_team is not None:
            award_score(room, scored_team)

        if room.get("game_over"):
            break

        # =====================================================
        # TIMERS, PODERES E ESTADOS
        # =====================================================
        for pid, p in list(room["players"].items()):
            ability_paused = is_timed_ability_active(p)

            if p.get("char") == "Murilo":
                ability_paused = ability_paused or any(
                    npc.get("owner_id") == pid and npc.get("timer", 0) > 0
                    for npc in room.get("murilo_npcs", [])
                )

            if p.get("char") == "Igor":
                ability_paused = ability_paused or any(
                    bird.get("owner_id") == pid and bird.get("timer", 0) > 0
                    for bird in room.get("igor_birds", [])
                )

            if p.get("clash_active", 0) > 0:
                p["clash_timer"] -= 1
                opponent_id = p.get("clash_opponent")

                if p["clash_timer"] <= 0 and opponent_id in room["players"]:
                    resolve_clash(room, pid, opponent_id)

                continue

            if p.get("dunk_active", 0) > 0:
                interrupted = p.get("stun_timer", 0) > 0 or p.get("knockback_timer", 0) > 0
                lost_ball = room["ball"].get("holder") != pid

                if interrupted or lost_ball:
                    if interrupted or room["ball"].get("holder") is None:
                        release_failed_dunk(room, pid, p)

                    cancel_dunk(p)
                else:
                    p["dunk_timer"] -= 1
                    update_dunk_position(p, room)

                    if room["ball"].get("holder") == pid:
                        room["ball"]["holder_source"] = "player"

                    if p.get("dunk_ready_to_score", 0) > 0 and p.get("dunk_anim_timer", 0) >= DUNK_ANIM_TIMER:
                        room["ball"]["score_override"] = 2
                        p["pending_dunk_score_team"] = p.get("dunk_score_team")
                        cancel_dunk(p)

                    if p["dunk_timer"] <= 0:
                        release_failed_dunk(room, pid, p)
                        cancel_dunk(p)

            if p.get("invisible_timer", 0) > 0:
                p["invisible_timer"] -= 1

            if p.get("ear_timer", 0) > 0:
                p["ear_timer"] -= 1

            if p.get("clone_timer", 0) > 0:
                p["clone_timer"] -= 1

            if p.get("cookie_buff_timer", 0) > 0:
                p["cookie_buff_timer"] -= 1

            if p.get("char") == "Caique":
                rage_gain = get_caique_rage_gain(p)

                if rage_gain > 0:
                    p["caique_rage"] = min(100, float(p.get("caique_rage", 0)) + rage_gain)

                if p.get("caique_shout_timer", 0) > 0:
                    p["caique_shout_timer"] -= 1

            if p.get("stun_timer", 0) > 0:
                p["stun_timer"] -= 1
                p["match_humiliated"] = p.get("match_humiliated", 0) + 1

            if p.get("lag_timer", 0) > 0:
                p["lag_timer"] -= 1

            if p.get("goon_timer", 0) > 0:
                p["goon_timer"] -= 1

            if p.get("havoc_timer", 0) > 0:
                p["havoc_timer"] -= 1

            if p.get("havoc_mark_timer", 0) > 0:
                p["havoc_mark_timer"] -= 1

            if p.get("ultimate_flash_timer", 0) > 0:
                p["ultimate_flash_timer"] -= 1

            if p.get("ability_cd", 0) > 0 and not ability_paused:
                p["ability_cd"] -= 1

            if p.get("clone_hit_cd", 0) > 0:
                p["clone_hit_cd"] -= 1

            if p.get("clone_block_cd", 0) > 0:
                p["clone_block_cd"] -= 1

            if p.get("knockback_timer", 0) > 0:
                p["knockback_timer"] -= 1
                p["match_humiliated"] = p.get("match_humiliated", 0) + 1
                p["x"] += p.get("knockback_vx", 0)
                p["x"] = clamp(p["x"], 0, world_width - CHAR_W)
                p["knockback_vx"] *= 0.82

            if p.get("reaction_timer", 0) > 0:
                p["reaction_timer"] -= 1

            if p.get("dash_timer", 0) > 0:
                p["dash_timer"] -= 1
                p["x"] += p.get("dash_dir", 1) * 22
                p["x"] = clamp(p["x"], 0, world_width - CHAR_W)

                holder_id = room["ball"]["holder"]

                if holder_id and holder_id != pid and holder_id in room["players"]:
                    enemy = room["players"][holder_id]
                    dist = math.hypot(p["x"] - enemy["x"], p["y"] - enemy["y"])

                    if dist < CLASH_RANGE and can_start_clash(room, pid, holder_id):
                        start_clash(room, pid, holder_id)
                        continue

                    if dist < 50 and enemy.get("jackpot_timer", 0) <= 0:
                        room["ball"]["holder"] = pid
                        room["ball"]["holder_source"] = "player"
                        set_last_touch(room, pid)
                        enemy["stun_timer"] = 120
                        p["dash_timer"] = 0

                for enemy_id, enemy in list(room["players"].items()):
                    if enemy_id == pid or enemy.get("team") == p.get("team"):
                        continue

                    if not player_has_clash_ability(enemy):
                        continue

                    if math.hypot(p["x"] - enemy["x"], p["y"] - enemy["y"]) < CLASH_RANGE:
                        if start_clash(room, pid, enemy_id):
                            break

            r_state = p.get("roleta_state", "IDLE")

            if r_state == "SPINNING":
                p["roleta_timer"] -= 1

                if p["roleta_timer"] <= 0:
                    outcome = random.choices(ROLETA_OUTCOMES, weights=ROLETA_WEIGHTS, k=1)[0]
                    p["roleta_result"] = outcome

                    if outcome == "JACKPOT":
                        p["roleta_state"] = "CUTSCENE"
                        p["roleta_timer"] = 180
                    else:
                        p["roleta_state"] = "FINISHED"
                        p["roleta_timer"] = 120

                        if outcome == "BUFF_BOLACHA":
                            p["cookie_buff_timer"] = 300
                        elif outcome == "BUFF_PULO":
                            p["jump_buff_timer"] = 300
                        elif outcome == "BUFF_FORCA":
                            p["throw_buff_timer"] = 300
                        elif outcome == "BUFF_DUNK":
                            p["dunk_buff_timer"] = 420
                        elif outcome == "DEBUFF_PULO":
                            p["jump_debuff_timer"] = 300
                        elif outcome == "DEBUFF_VELOCIDADE":
                            p["speed_debuff_timer"] = 300
                        elif outcome == "DEBUFF_FORCA":
                            p["throw_debuff_timer"] = 300

            elif r_state == "CUTSCENE":
                p["roleta_timer"] -= 1

                if p["roleta_timer"] <= 0:
                    p["roleta_state"] = "FINISHED"
                    p["roleta_timer"] = 120
                    p["jackpot_timer"] = 900

            elif r_state == "FINISHED":
                p["roleta_timer"] -= 1

                if p["roleta_timer"] <= 0:
                    p["roleta_state"] = "IDLE"

            if p.get("jackpot_timer", 0) > 0:
                p["jackpot_timer"] -= 1

            if p.get("jump_buff_timer", 0) > 0:
                p["jump_buff_timer"] -= 1

            if p.get("throw_buff_timer", 0) > 0:
                p["throw_buff_timer"] -= 1

            if p.get("dunk_buff_timer", 0) > 0:
                p["dunk_buff_timer"] -= 1

            if p.get("jump_debuff_timer", 0) > 0:
                p["jump_debuff_timer"] -= 1

            if p.get("speed_debuff_timer", 0) > 0:
                p["speed_debuff_timer"] -= 1

            if p.get("throw_debuff_timer", 0) > 0:
                p["throw_debuff_timer"] -= 1

            if p.get("john_float_timer", 0) > 0:
                p["john_float_timer"] -= 1

            if p.get("ear_timer", 0) > 0:
                left_ear = (p["x"] - 32, p["y"] + 5, 32, CHAR_H - 10)
                right_ear = (p["x"] + CHAR_W, p["y"] + 5, 32, CHAR_H - 10)

                for enemy_id, enemy in list(room["players"].items()):
                    if enemy_id == pid:
                        continue

                    if enemy["team"] == p["team"]:
                        continue

                    if enemy.get("jackpot_timer", 0) > 0:
                        continue

                    e_rect = player_rect(enemy)
                    hit_left = rects_overlap(left_ear, e_rect)
                    hit_right = rects_overlap(right_ear, e_rect)

                    if hit_left or hit_right:
                        if can_start_clash(room, pid, enemy_id):
                            start_clash(room, pid, enemy_id)
                            continue

                        direction = -1 if hit_left else 1

                        enemy["knockback_timer"] = max(enemy.get("knockback_timer", 0), 16)
                        enemy["knockback_vx"] = direction * 15
                        enemy["stun_timer"] = max(enemy.get("stun_timer", 0), 18)

                        if room["ball"].get("holder") == enemy_id:
                            room["ball"]["holder"] = None
                            room["ball"]["holder_source"] = None
                            room["ball"]["vel_x"] = direction * 10
                            room["ball"]["vel_y"] = -8
                            set_last_touch(room, pid)

            if p.get("clone_timer", 0) > 0:
                clone_rect = get_clone_rect(p)
                clone_center_x, clone_center_y = center_of_rect(clone_rect)

                for enemy_id, enemy in list(room["players"].items()):
                    if enemy_id == pid:
                        continue

                    if enemy["team"] == p["team"]:
                        continue

                    if enemy.get("jackpot_timer", 0) > 0:
                        continue

                    if rects_overlap(clone_rect, player_rect(enemy)):
                        if can_start_clash(room, pid, enemy_id):
                            start_clash(room, pid, enemy_id)
                            continue

                        direction = 1 if enemy["x"] + CHAR_W / 2 > clone_center_x else -1

                        enemy["knockback_timer"] = max(enemy.get("knockback_timer", 0), 12)
                        enemy["knockback_vx"] = direction * 12
                        enemy["stun_timer"] = max(enemy.get("stun_timer", 0), 12)

                        if room["ball"].get("holder") == enemy_id and p.get("clone_hit_cd", 0) <= 0:
                            room["ball"]["holder"] = pid
                            room["ball"]["holder_source"] = "clone"
                            set_last_touch(room, pid)
                            p["clone_hit_cd"] = 35

        update_murilo_npcs(room)
        update_igor_birds(room)

        time.sleep(1 / FPS)


def handle_client(conn, addr):
    player_id = None
    room_code = None

    try:
        initial_data = pickle.loads(conn.recv(BUFFER_SIZE))

        if initial_data[0] == "CREATE":
            room_code = generate_room_code()

            # Host pode escolher os pontos para vencer (initial_data[1]);
            # valida contra as opcoes e cai no default se invalido/ausente.
            raw_win = initial_data[1] if len(initial_data) > 1 else None
            try:
                chosen = int(raw_win)
            except (TypeError, ValueError):
                chosen = DEFAULT_WIN_POINTS
            if chosen not in WIN_POINTS_OPTIONS:
                chosen = DEFAULT_WIN_POINTS

            rooms[room_code] = {
                "players": {},
                "room_code": room_code,  # SPEC-05: código da sala para histórico
                "game_started": False,
                "game_over": False,
                "winner_team": None,
                "host_id": 1,
                "score": [0, 0],
                "world_width": WIDTH,
                # Pontos para vencer: definido pelo host no CREATE (validado acima)
                "win_points": chosen,
                "frame_counter": 0,  # SPEC-02: incrementado a cada tick da simulacao

                "replay_id": 0,
                "replay_timer": 0,
                "last_score_team": None,
                "last_score_char": None,
                "last_score_player": None,
                "last_score_points": 2,
                "next_clash_id": 0,
                "next_murilo_npc_id": 0,
                "next_igor_bird_id": 0,
                "next_bot_id": 1,
                "last_holder_for_steal": None,
                "match_awards": [],
                "match_highlights": [],

                "skip_votes": set(),
                "skip_votes_display": [],
                "murilo_npcs": [],
                "igor_birds": [],

                "ball": {
                    "x": WIDTH // 2,
                    "y": HEIGHT // 2 - 100,
                    "vel_x": 0,
                    "vel_y": 0,
                    "holder": None,
                    "holder_source": None,
                    "last_touch_player": None,
                    "last_touch_char": None,
                    "shot_origin_x": None,
                    "shot_origin_y": None,
                    "score_override": None,
                    "bola_throw_timer": 0,
                }
            }

            player_id = 1
            team = 1

            rooms[room_code]["players"][player_id] = {
                "char": None,
                "skin_id": "default",
                "team": team,
                "x": 0,
                "y": 0,
                "world_width": WIDTH,
                "conn_token": str(uuid.uuid4()),  # SPEC-01: token de reconexao
            }

            update_room_world_width(rooms[room_code])

            conn.send(pickle.dumps(("SUCCESS", room_code, player_id, team, False, None,
                                    rooms[room_code]["players"][player_id]["conn_token"])))

        elif initial_data[0] == "JOIN":
            room_code = initial_data[1]

            if room_code not in rooms:
                conn.send(pickle.dumps(("ERROR", "Sala não encontrada.")))
                return

            room = rooms[room_code]

            if room.get("game_over"):
                conn.send(pickle.dumps(("ERROR", "Essa partida já acabou.")))
                return

            conn_token = str(uuid.uuid4())  # SPEC-01: token de reconexao

            player_id = get_next_player_id(room)
            team = choose_balanced_team(room)

            if room["game_started"]:
                chosen_char = choose_available_character(room)

                if chosen_char is None:
                    conn.send(pickle.dumps(("ERROR", "Todos os personagens já estão em uso.")))
                    return

                room["players"][player_id] = {
                    "char": chosen_char,
                    "skin_id": "default",
                    "team": team,
                    "x": 0,
                    "y": 0,
                    "conn_token": conn_token,
                }

                update_room_world_width(room)
                room["players"][player_id]["world_width"] = get_room_width(room)
                spawn_player_for_match(room["players"][player_id])
                reset_player_match_stats(room["players"][player_id])

                conn.send(pickle.dumps(("SUCCESS", room_code, player_id, team, True, chosen_char, conn_token)))

            else:
                room["players"][player_id] = {
                    "char": None,
                    "skin_id": "default",
                    "team": team,
                    "x": 0,
                    "y": 0,
                    "world_width": get_room_width(room),
                    "conn_token": conn_token,
                }

                update_room_world_width(room)

                conn.send(pickle.dumps(("SUCCESS", room_code, player_id, team, False, None, conn_token)))

        elif initial_data[0] == "REJOIN":  # SPEC-01: reconexao por token
            room_code = initial_data[1]
            token = initial_data[2] if len(initial_data) > 2 else None

            if room_code not in rooms:
                conn.send(pickle.dumps(("ERROR", "Sala nao encontrada.")))
                return

            room = rooms[room_code]

            if room.get("game_over"):
                conn.send(pickle.dumps(("ERROR", "Essa partida ja acabou.")))
                return

            found = None
            for pid, p in room["players"].items():
                if p.get("conn_token") == token:
                    found = pid
                    break

            if found is None:
                conn.send(pickle.dumps(("ERROR", "Token invalido ou voce nao esta nesta sala.")))
                return

            player_id = found
            team = room["players"][player_id]["team"]
            in_game = room["game_started"]
            char = room["players"][player_id].get("char")
            conn.send(pickle.dumps(("SUCCESS", room_code, player_id, team, in_game, char, token)))

        while True:
            client_data = pickle.loads(conn.recv(BUFFER_SIZE))

            # SPEC-04: PING/PONG nao toca no estado do jogo
            if isinstance(client_data, tuple) and client_data and client_data[0] == "PING":
                try:
                    conn.send(pickle.dumps(("PONG",)))
                except socket.error:
                    pass
                continue

            if not client_data:
                break

            if room_code not in rooms:
                break

            room = rooms[room_code]
            update_room_world_width(room)
            world_width = get_room_width(room)

            if player_id not in room["players"]:
                break

            player = room["players"][player_id]

            if room.get("game_over"):
                send_room(conn, room)
                continue

            if not room["game_started"]:
                if client_data.get("action") == "UPDATE_LOBBY":
                    player["team"] = client_data.get("team", player["team"])

                    if client_data.get("char"):
                        player["char"] = client_data["char"]

                    if client_data.get("skin_id") in COSMETICS:
                        player["skin_id"] = client_data["skin_id"]

                elif client_data.get("action") == "ADD_BOT" and player_id == room["host_id"]:
                    add_training_bot(room, client_data.get("bot_char"))

                elif client_data.get("action") == "REMOVE_BOT" and player_id == room["host_id"]:
                    remove_training_bot(room)

                elif client_data.get("action") == "START_GAME" and player_id == room["host_id"]:
                    room["game_started"] = True

                    for p_data in room["players"].values():
                        if p_data.get("char") is None:
                            p_data["char"] = choose_available_character(room) or CHARACTERS[0]

                        spawn_player_for_match(p_data)
                        reset_player_match_stats(p_data)

                    sync_bola_player_to_ball(room)
                    threading.Thread(target=room_physics_loop, args=(room_code,), daemon=True).start()

            else:
                action = client_data.get("action")

                if action == "REACTION":
                    reaction = str(client_data.get("reaction", ""))[:18]

                    if reaction in ["Boa!", "Kkk", "Passa!", "Foi mal", "Fraco", "Nossa!"]:
                        player["reaction_text"] = reaction
                        player["reaction_timer"] = 150

                if room.get("replay_timer", 0) > 0:
                    if action == "SKIP_REPLAY":
                        room.setdefault("skip_votes", set())
                        room["skip_votes"].add(player_id)

                        connected_players = set(room["players"].keys())
                        room["skip_votes_display"] = get_skip_votes_display(room)

                        if connected_players and room["skip_votes"] >= connected_players:
                            room["replay_timer"] = 0
                            room["skip_votes"] = set()
                            room["skip_votes_display"] = []

                    send_room(conn, room)
                    continue

                if "x" in client_data and player.get("roleta_state") != "CUTSCENE":
                    player["facing"] = client_data.get("facing", player.get("facing", 1))
                    lagged = player.get("lag_timer", 0) > 0
                    accept_lagged_input = True

                    if lagged:
                        player["lag_tick"] = player.get("lag_tick", 0) + 1
                        accept_lagged_input = player["lag_tick"] % 4 == 0

                    if (
                        player.get("dash_timer", 0) <= 0
                        and player.get("knockback_timer", 0) <= 0
                        and player.get("stun_timer", 0) <= 0
                        and player.get("dunk_active", 0) <= 0
                        and player.get("clash_active", 0) <= 0
                        and accept_lagged_input
                        and not (
                            player.get("char") == "Bola"
                            and (
                                room["ball"].get("holder") is not None
                                or room["ball"].get("bola_throw_timer", 0) > 0
                            )
                        )
                    ):
                        jitter = random.choice([-10, -5, 0, 5, 10]) if lagged else 0
                        player["x"] = clamp(client_data["x"] + jitter, 0, world_width - CHAR_W)

                    if (
                        player.get("dunk_active", 0) <= 0
                        and player.get("clash_active", 0) <= 0
                        and accept_lagged_input
                        and not (
                            player.get("char") == "Bola"
                            and (
                                room["ball"].get("holder") is not None
                                or room["ball"].get("bola_throw_timer", 0) > 0
                            )
                        )
                    ):
                        y_jitter = random.choice([-6, 0, 6]) if lagged else 0
                        player["y"] = clamp(client_data["y"] + y_jitter, 0, GROUND_Y - CHAR_H)

                if (
                    action == "THROW"
                    and room["ball"]["holder"] == player_id
                    and player.get("roleta_state") != "CUTSCENE"
                    and player.get("dunk_active", 0) <= 0
                    and player.get("clash_active", 0) <= 0
                ):
                    tx = client_data["target_x"]
                    ty = client_data["target_y"]

                    angle = math.atan2(ty - room["ball"]["y"], tx - room["ball"]["x"])
                    power = 25

                    if player["char"] == "Rafael":
                        power = 35

                    if player["char"] == "Caique":
                        power += min(10, float(player.get("caique_rage", 0)) * 0.10)

                    if player.get("jackpot_timer", 0) > 0:
                        power += 15

                    elif player.get("throw_buff_timer", 0) > 0:
                        power += 10

                    elif player.get("throw_debuff_timer", 0) > 0:
                        power -= 10

                    set_last_touch(room, player_id)

                    if player.get("char") == "Igor":
                        for bird in room.get("igor_birds", []):
                            if bird.get("owner_id") == player_id:
                                bird["disabled_until_ground"] = True

                    room["ball"]["vel_x"] = math.cos(angle) * power
                    room["ball"]["vel_y"] = math.sin(angle) * power
                    room["ball"]["holder"] = None
                    room["ball"]["holder_source"] = None
                    if get_bola_player_id(room) is not None:
                        room["ball"]["bola_throw_timer"] = 90
                    room["ball"]["y"] -= 10
                    room["ball"]["shot_origin_x"] = player["x"] + CHAR_W / 2
                    room["ball"]["shot_origin_y"] = player["y"] + CHAR_H / 2
                    room["ball"]["score_override"] = None

                elif action == "DUNK_START" and player.get("roleta_state") != "CUTSCENE":
                    if can_start_dunk(player, room["ball"], player_id, room):
                        start_dunk(player, room)
                        set_last_touch(room, player_id)

                elif action == "DUNK_QTE_KEY" and player.get("dunk_active", 0) > 0:
                    key = str(client_data.get("key", "")).upper()
                    sequence = player.get("dunk_sequence", [])
                    index = player.get("dunk_index", 0)

                    if index < len(sequence) and key == sequence[index]:
                        player["dunk_index"] = index + 1

                        if player["dunk_index"] >= len(sequence):
                            player["dunk_ready_to_score"] = 1
                            set_last_touch(room, player_id)
                    else:
                        release_failed_dunk(room, player_id, player)
                        cancel_dunk(player)

                elif action == "CLASH_QTE_KEY" and player.get("clash_active", 0) > 0:
                    key = str(client_data.get("key", "")).upper()
                    sequence = player.get("clash_sequence", [])
                    index = player.get("clash_index", 0)

                    if index < len(sequence) and key == sequence[index]:
                        player["clash_index"] = index + 1

                        if player["clash_index"] >= len(sequence):
                            opponent_id = player.get("clash_opponent")

                            if opponent_id in room["players"]:
                                resolve_clash(room, player_id, opponent_id)

                elif action == "BOLA_THROW" and player.get("roleta_state") != "CUTSCENE":
                    if player.get("ability_cd", 0) <= 0 and player.get("clash_active", 0) <= 0:
                        bola_self_throw(
                            room,
                            player_id,
                            player,
                            client_data.get("target_x"),
                            client_data.get("target_y"),
                        )

                elif action == "ULTIMATE" and player.get("roleta_state") != "CUTSCENE":
                    activate_ultimate(room, player_id, player)

                elif action == "USE_ABILITY" and player.get("roleta_state") != "CUTSCENE":
                    char = player["char"]

                    if player.get("ability_cd", 0) <= 0 and player.get("clash_active", 0) <= 0:
                        ability_char = char

                        if char == "Treinador":
                            copied_ability = client_data.get("copied_ability")

                            if copied_ability in TRAINER_COPY_CHARACTERS:
                                ability_char = copied_ability
                            else:
                                ability_char = None

                        elif char == "Murilo":
                            apply_murilo_drawing(room, player_id, player, client_data.get("murilo_points", []))
                            ability_char = None

                        elif char == "Igor":
                            summon_igor_birds(room, player_id, player)
                            ability_char = None

                        elif char == "Laiz":
                            for p in room["players"].values():
                                if p.get("team") != player.get("team"):
                                    p["lag_timer"] = max(p.get("lag_timer", 0), 300)
                                    p["lag_tick"] = 0

                            player["ability_cd"] = ABILITY_COOLDOWNS.get("Laiz", 480)
                            ability_char = None

                        elif char == "Kauã":
                            for p in room["players"].values():
                                if p.get("team") != player.get("team"):
                                    p["goon_timer"] = max(p.get("goon_timer", 0), 300)

                            player["ability_cd"] = ABILITY_COOLDOWNS.get("Kauã", 480)
                            ability_char = None

                        elif char == "Caique":
                            release_caique_rage(room, player_id, player)
                            ability_char = None

                        elif char == "João Roberto":
                            joao_roberto_swap(room, player_id, player)
                            ability_char = None

                        elif char == "Havoc":
                            havoc_command(
                                room,
                                player_id,
                                player,
                                client_data.get("havoc_target_id"),
                                client_data.get("havoc_command"),
                            )
                            ability_char = None

                        if ability_char:
                            apply_character_ability(room, player, ability_char, client_data.get("facing", 1))

            send_room(conn, room)

    except Exception:
        import traceback
        print(f"[ERRO CLIENTE {addr}]")
        traceback.print_exc()

    finally:
        if room_code and room_code in rooms and player_id in rooms[room_code]["players"]:
            room = rooms[room_code]

            if room.get("ball", {}).get("holder") == player_id:
                room["ball"]["holder"] = None
                room["ball"]["holder_source"] = None
                room["ball"]["vel_x"] = 0
                room["ball"]["vel_y"] = -8

            del room["players"][player_id]
            update_room_world_width(room)

            if "skip_votes" in room:
                room["skip_votes"].discard(player_id)
                room["skip_votes_display"] = get_skip_votes_display(room)

                connected_players = set(room["players"].keys())

                if (
                    room.get("replay_timer", 0) > 0
                    and connected_players
                    and room["skip_votes"] >= connected_players
                ):
                    room["replay_timer"] = 0
                    room["skip_votes"] = set()
                    room["skip_votes_display"] = []

            if len(room["players"]) == 0:
                del rooms[room_code]

            elif room.get("host_id") == player_id:
                room["host_id"] = min(room["players"].keys())

        conn.close()


while True:
    conn, addr = server.accept()
    threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()
