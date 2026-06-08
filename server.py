import socket
import threading
import pickle
import random
import string
import math
import time
from config import *

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.bind((HOST, PORT))
server.listen()
print(f"[SERVIDOR LIGADO] Aguardando em {HOST}:{PORT}...")

rooms = {}

ROLETA_OUTCOMES = [
    "BUFF_BOLACHA",
    "BUFF_PULO",
    "BUFF_FORCA",
    "DEBUFF_PULO",
    "DEBUFF_VELOCIDADE",
    "DEBUFF_FORCA",
    "JACKPOT"
]

ROLETA_WEIGHTS = [18, 18, 14, 14, 14, 14, 8]

ABILITY_COOLDOWNS = {
    "Diogo": 480,
    "Paulo": 480,
    "Henrique": 360,
    "Natan": 360,
    "Presscinotti": 360,
    "Miguel": 360,
    "Rafael": 360,
    "John Jonh": 360,
}


def clamp(value, min_value, max_value):
    return max(min_value, min(value, max_value))


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
    facing = p.get("facing", 1)
    clone_x = clamp(p["x"] - facing * 75, 0, WIDTH - CHAR_W)
    clone_y = p["y"]

    p["clone_x"] = clone_x
    p["clone_y"] = clone_y

    return (clone_x, clone_y, CHAR_W, CHAR_H)


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

    for char in CHARACTERS:
        if char not in used_chars:
            return char

    return None


def reset_player_status(p_data):
    keys_to_reset = [
        "invisible_timer",
        "ear_timer",
        "clone_timer",
        "cookie_buff_timer",
        "jackpot_timer",
        "jump_buff_timer",
        "throw_buff_timer",
        "jump_debuff_timer",
        "speed_debuff_timer",
        "throw_debuff_timer",
        "stun_timer",
        "dash_timer",
        "roleta_timer",
        "ability_cd",
        "knockback_timer",
        "knockback_vx",
        "clone_hit_cd",
        "clone_block_cd",
    ]

    for k in keys_to_reset:
        p_data[k] = 0

    p_data["roleta_state"] = "IDLE"
    p_data["roleta_result"] = None
    p_data["dash_dir"] = 1
    p_data["facing"] = 1
    p_data["clone_x"] = p_data["x"]
    p_data["clone_y"] = p_data["y"]


def spawn_player_for_match(p_data):
    p_data["x"] = 200 if p_data["team"] == 1 else WIDTH - 250
    p_data["y"] = GROUND_Y - CHAR_H
    reset_player_status(p_data)


def reset_all_players_after_score(room):
    for p_data in room["players"].values():
        spawn_player_for_match(p_data)


def set_last_touch(room, player_id):
    if player_id in room["players"]:
        player = room["players"][player_id]
        room["ball"]["last_touch_player"] = player_id
        room["ball"]["last_touch_char"] = player.get("char")


def get_skip_votes_display(room):
    return list(room.get("skip_votes", set()))


def room_physics_loop(room_code):
    while room_code in rooms and rooms[room_code]["game_started"]:
        room = rooms[room_code]
        ball = room["ball"]

        # Durante o replay, congela a partida.
        if room.get("replay_timer", 0) > 0:
            room["replay_timer"] -= 1
            time.sleep(1 / FPS)
            continue

        # =====================================================
        # FÍSICA DA BOLA
        # =====================================================
        if ball["holder"] is None:
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

            if ball["x"] >= WIDTH - BALL_RAD:
                ball["x"] = WIDTH - BALL_RAD
                ball["vel_x"] *= -0.8

            for pid, p in list(room["players"].items()):
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
            else:
                ball["holder"] = None
                ball["holder_source"] = None

        # =====================================================
        # PONTUAÇÃO
        # =====================================================
        hoop_y_zone = HEIGHT - 340
        score_changed = False
        scored_team = None

        if hoop_y_zone - 30 < ball["y"] < hoop_y_zone:
            if 95 <= ball["x"] <= 145 and ball["vel_y"] > 0:
                room["score"][1] += 2
                score_changed = True
                scored_team = 2

            elif (WIDTH - 145) <= ball["x"] <= (WIDTH - 95) and ball["vel_y"] > 0:
                room["score"][0] += 2
                score_changed = True
                scored_team = 1

        if score_changed:
            room["replay_id"] = room.get("replay_id", 0) + 1
            room["replay_timer"] = 360

            room["skip_votes"] = set()
            room["skip_votes_display"] = []

            room["last_score_team"] = scored_team
            room["last_score_char"] = ball.get("last_touch_char")
            room["last_score_player"] = ball.get("last_touch_player")

            ball["x"] = WIDTH // 2
            ball["y"] = HEIGHT // 2 - 100
            ball["vel_x"] = 0
            ball["vel_y"] = 0
            ball["holder"] = None
            ball["holder_source"] = None
            ball["last_touch_player"] = None
            ball["last_touch_char"] = None

            reset_all_players_after_score(room)

            if room["score"][0] >= MAX_SCORE:
                room["game_started"] = False
                room["game_over"] = True
                room["winner_team"] = 1

            elif room["score"][1] >= MAX_SCORE:
                room["game_started"] = False
                room["game_over"] = True
                room["winner_team"] = 2

        if room.get("game_over"):
            break

        # =====================================================
        # TIMERS, PODERES E ESTADOS
        # =====================================================
        for pid, p in list(room["players"].items()):
            if p.get("invisible_timer", 0) > 0:
                p["invisible_timer"] -= 1

            if p.get("ear_timer", 0) > 0:
                p["ear_timer"] -= 1

            if p.get("clone_timer", 0) > 0:
                p["clone_timer"] -= 1

            if p.get("cookie_buff_timer", 0) > 0:
                p["cookie_buff_timer"] -= 1

            if p.get("stun_timer", 0) > 0:
                p["stun_timer"] -= 1

            if p.get("ability_cd", 0) > 0:
                p["ability_cd"] -= 1

            if p.get("clone_hit_cd", 0) > 0:
                p["clone_hit_cd"] -= 1

            if p.get("clone_block_cd", 0) > 0:
                p["clone_block_cd"] -= 1

            if p.get("knockback_timer", 0) > 0:
                p["knockback_timer"] -= 1
                p["x"] += p.get("knockback_vx", 0)
                p["x"] = clamp(p["x"], 0, WIDTH - CHAR_W)
                p["knockback_vx"] *= 0.82

            if p.get("dash_timer", 0) > 0:
                p["dash_timer"] -= 1
                p["x"] += p.get("dash_dir", 1) * 22
                p["x"] = clamp(p["x"], 0, WIDTH - CHAR_W)

                holder_id = room["ball"]["holder"]

                if holder_id and holder_id != pid and holder_id in room["players"]:
                    enemy = room["players"][holder_id]
                    dist = math.hypot(p["x"] - enemy["x"], p["y"] - enemy["y"])

                    if dist < 50 and enemy.get("jackpot_timer", 0) <= 0:
                        room["ball"]["holder"] = pid
                        room["ball"]["holder_source"] = "player"
                        set_last_touch(room, pid)
                        enemy["stun_timer"] = 120
                        p["dash_timer"] = 0

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

            if p.get("jump_debuff_timer", 0) > 0:
                p["jump_debuff_timer"] -= 1

            if p.get("speed_debuff_timer", 0) > 0:
                p["speed_debuff_timer"] -= 1

            if p.get("throw_debuff_timer", 0) > 0:
                p["throw_debuff_timer"] -= 1

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
                        direction = 1 if enemy["x"] + CHAR_W / 2 > clone_center_x else -1

                        enemy["knockback_timer"] = max(enemy.get("knockback_timer", 0), 12)
                        enemy["knockback_vx"] = direction * 12
                        enemy["stun_timer"] = max(enemy.get("stun_timer", 0), 12)

                        if room["ball"].get("holder") == enemy_id and p.get("clone_hit_cd", 0) <= 0:
                            room["ball"]["holder"] = pid
                            room["ball"]["holder_source"] = "clone"
                            set_last_touch(room, pid)
                            p["clone_hit_cd"] = 35

        time.sleep(1 / FPS)


def handle_client(conn, addr):
    player_id = None
    room_code = None

    try:
        initial_data = pickle.loads(conn.recv(BUFFER_SIZE))

        if initial_data[0] == "CREATE":
            room_code = generate_room_code()

            rooms[room_code] = {
                "players": {},
                "game_started": False,
                "game_over": False,
                "winner_team": None,
                "host_id": 1,
                "score": [0, 0],

                "replay_id": 0,
                "replay_timer": 0,
                "last_score_team": None,
                "last_score_char": None,
                "last_score_player": None,

                "skip_votes": set(),
                "skip_votes_display": [],

                "ball": {
                    "x": WIDTH // 2,
                    "y": HEIGHT // 2 - 100,
                    "vel_x": 0,
                    "vel_y": 0,
                    "holder": None,
                    "holder_source": None,
                    "last_touch_player": None,
                    "last_touch_char": None,
                }
            }

            player_id = 1
            team = 1

            rooms[room_code]["players"][player_id] = {
                "char": None,
                "team": team,
                "x": 0,
                "y": 0,
            }

            conn.send(pickle.dumps(("SUCCESS", room_code, player_id, team, False, None)))

        elif initial_data[0] == "JOIN":
            room_code = initial_data[1]

            if room_code not in rooms:
                conn.send(pickle.dumps(("ERROR", "Sala não encontrada.")))
                return

            room = rooms[room_code]

            if room.get("game_over"):
                conn.send(pickle.dumps(("ERROR", "Essa partida já acabou.")))
                return

            player_id = get_next_player_id(room)
            team = choose_balanced_team(room)

            if room["game_started"]:
                chosen_char = choose_available_character(room)

                if chosen_char is None:
                    conn.send(pickle.dumps(("ERROR", "Todos os personagens já estão em uso.")))
                    return

                room["players"][player_id] = {
                    "char": chosen_char,
                    "team": team,
                    "x": 0,
                    "y": 0,
                }

                spawn_player_for_match(room["players"][player_id])

                conn.send(pickle.dumps(("SUCCESS", room_code, player_id, team, True, chosen_char)))

            else:
                room["players"][player_id] = {
                    "char": None,
                    "team": team,
                    "x": 0,
                    "y": 0,
                }

                conn.send(pickle.dumps(("SUCCESS", room_code, player_id, team, False, None)))

        while True:
            client_data = pickle.loads(conn.recv(BUFFER_SIZE))

            if not client_data:
                break

            if room_code not in rooms:
                break

            room = rooms[room_code]

            if player_id not in room["players"]:
                break

            player = room["players"][player_id]

            if room.get("game_over"):
                conn.send(pickle.dumps(room))
                continue

            if not room["game_started"]:
                if client_data.get("action") == "UPDATE_LOBBY":
                    player["team"] = client_data.get("team", player["team"])

                    if client_data.get("char"):
                        player["char"] = client_data["char"]

                elif client_data.get("action") == "START_GAME" and player_id == room["host_id"]:
                    room["game_started"] = True

                    for p_data in room["players"].values():
                        if p_data.get("char") is None:
                            p_data["char"] = choose_available_character(room) or CHARACTERS[0]

                        spawn_player_for_match(p_data)

                    threading.Thread(target=room_physics_loop, args=(room_code,), daemon=True).start()

            else:
                action = client_data.get("action")

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

                    conn.send(pickle.dumps(room))
                    continue

                if "x" in client_data and player.get("roleta_state") != "CUTSCENE":
                    player["facing"] = client_data.get("facing", player.get("facing", 1))

                    if (
                        player.get("dash_timer", 0) <= 0
                        and player.get("knockback_timer", 0) <= 0
                        and player.get("stun_timer", 0) <= 0
                    ):
                        player["x"] = clamp(client_data["x"], 0, WIDTH - CHAR_W)

                    player["y"] = clamp(client_data["y"], 0, GROUND_Y - CHAR_H)

                if (
                    action == "THROW"
                    and room["ball"]["holder"] == player_id
                    and player.get("roleta_state") != "CUTSCENE"
                ):
                    tx = client_data["target_x"]
                    ty = client_data["target_y"]

                    angle = math.atan2(ty - room["ball"]["y"], tx - room["ball"]["x"])
                    power = 25

                    if player["char"] == "Rafael":
                        power = 35

                    if player.get("jackpot_timer", 0) > 0:
                        power += 15

                    elif player.get("throw_buff_timer", 0) > 0:
                        power += 10

                    elif player.get("throw_debuff_timer", 0) > 0:
                        power -= 10

                    set_last_touch(room, player_id)

                    room["ball"]["vel_x"] = math.cos(angle) * power
                    room["ball"]["vel_y"] = math.sin(angle) * power
                    room["ball"]["holder"] = None
                    room["ball"]["holder_source"] = None
                    room["ball"]["y"] -= 10

                elif action == "USE_ABILITY" and player.get("roleta_state") != "CUTSCENE":
                    char = player["char"]

                    if player.get("ability_cd", 0) <= 0:
                        if char == "Henrique":
                            player["dash_timer"] = 12
                            player["dash_dir"] = client_data.get("facing", 1)
                            player["ability_cd"] = ABILITY_COOLDOWNS.get(char, 360)

                        elif char == "Natan":
                            player["invisible_timer"] = 180
                            player["ability_cd"] = ABILITY_COOLDOWNS.get(char, 360)

                        elif char == "Presscinotti":
                            player["ear_timer"] = 240
                            player["ability_cd"] = ABILITY_COOLDOWNS.get(char, 360)

                        elif char == "Diogo":
                            for p in room["players"].values():
                                if p["team"] == player["team"]:
                                    p["cookie_buff_timer"] = 300

                            player["ability_cd"] = ABILITY_COOLDOWNS.get(char, 480)

                        elif char == "Miguel":
                            player["clone_timer"] = 300
                            player["clone_hit_cd"] = 0
                            player["clone_block_cd"] = 0
                            player["ability_cd"] = ABILITY_COOLDOWNS.get(char, 360)

                        elif (
                            char == "Paulo"
                            and player.get("roleta_state") == "IDLE"
                            and player.get("jackpot_timer", 0) <= 0
                        ):
                            player["roleta_state"] = "SPINNING"
                            player["roleta_timer"] = 120
                            player["ability_cd"] = ABILITY_COOLDOWNS.get(char, 480)

            conn.send(pickle.dumps(room))

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