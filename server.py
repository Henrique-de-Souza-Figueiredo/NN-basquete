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


def is_timed_ability_active(p):
    char = p.get("char")

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

    return False


def ball_crossed_hoop(prev_y, ball, x1, x2):
    return (
        ball["vel_y"] > 0
        and prev_y <= HOOP_Y + HOOP_SCORE_MARGIN_Y
        and ball["y"] >= HOOP_Y - HOOP_SCORE_MARGIN_Y
        and x1 + HOOP_SCORE_MARGIN_X <= ball["x"] <= x2 - HOOP_SCORE_MARGIN_X
    )


def get_hoop_center_for_team(team):
    if team == 1:
        return (RIGHT_HOOP_X1 + RIGHT_HOOP_X2) / 2, HOOP_Y

    return (LEFT_HOOP_X1 + LEFT_HOOP_X2) / 2, HOOP_Y


def get_score_points(room, scored_team):
    ball = room["ball"]

    if ball.get("score_override"):
        return ball["score_override"]

    origin_x = ball.get("shot_origin_x")
    origin_y = ball.get("shot_origin_y")

    if origin_x is None or origin_y is None:
        return 2

    hoop_x, hoop_y = get_hoop_center_for_team(scored_team)
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


def resolve_hoop_collisions(ball):
    for rim_x in (LEFT_HOOP_X1, LEFT_HOOP_X2, RIGHT_HOOP_X1, RIGHT_HOOP_X2):
        resolve_circle_point_collision(ball, rim_x, HOOP_Y, HOOP_RIM_RAD)

    resolve_circle_rect_collision(ball, (LEFT_BACKBOARD_X, BACKBOARD_Y, BACKBOARD_W, BACKBOARD_H))
    resolve_circle_rect_collision(ball, (RIGHT_BACKBOARD_X, BACKBOARD_Y, BACKBOARD_W, BACKBOARD_H))


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
        "dunk_buff_timer",
        "jump_debuff_timer",
        "speed_debuff_timer",
        "throw_debuff_timer",
        "john_float_timer",
        "stun_timer",
        "dash_timer",
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


def get_attack_hoop(team):
    if team == 1:
        return (RIGHT_HOOP_X1 + RIGHT_HOOP_X2) / 2, HOOP_Y

    return (LEFT_HOOP_X1 + LEFT_HOOP_X2) / 2, HOOP_Y


def can_start_dunk(player, ball, player_id):
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

    hoop_x, hoop_y = get_attack_hoop(player["team"])
    player_cx = player["x"] + CHAR_W / 2
    player_cy = player["y"] + CHAR_H / 2
    range_bonus_x = 45 if player.get("dunk_buff_timer", 0) > 0 else 0
    range_bonus_y = 35 if player.get("dunk_buff_timer", 0) > 0 else 0

    return (
        abs(player_cx - hoop_x) <= DUNK_RANGE_X + range_bonus_x
        and abs(player_cy - hoop_y) <= DUNK_RANGE_Y + range_bonus_y
    )


def start_dunk(player):
    hoop_x, hoop_y = get_attack_hoop(player["team"])
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
    player["dunk_target_x"] = clamp(hoop_x - CHAR_W / 2, 0, WIDTH - CHAR_W)
    player["dunk_target_y"] = clamp(hoop_y - DUNK_HOLD_OFFSET_Y, 0, GROUND_Y - CHAR_H)


def cancel_dunk(player):
    player["dunk_active"] = 0
    player["dunk_timer"] = 0
    player["dunk_anim_timer"] = 0
    player["dunk_ready_to_score"] = 0
    player["dunk_index"] = 0
    player["dunk_score_team"] = None
    player["dunk_sequence"] = []


def update_dunk_position(player):
    player["dunk_anim_timer"] = min(player.get("dunk_anim_timer", 0) + 1, DUNK_ANIM_TIMER)
    t = player["dunk_anim_timer"] / DUNK_ANIM_TIMER
    eased = 1 - (1 - t) * (1 - t)
    arc = math.sin(math.pi * t) * DUNK_JUMP_ARC

    start_x = player.get("dunk_start_x", player["x"])
    start_y = player.get("dunk_start_y", player["y"])
    target_x = player.get("dunk_target_x", player["x"])
    target_y = player.get("dunk_target_y", player["y"])

    player["x"] = clamp(start_x + (target_x - start_x) * eased, 0, WIDTH - CHAR_W)
    player["y"] = clamp(start_y + (target_y - start_y) * eased - arc, 0, GROUND_Y - CHAR_H)


def release_failed_dunk(room, player_id, player):
    ball = room["ball"]
    hoop_x, _ = get_attack_hoop(player["team"])
    direction = -1 if hoop_x > WIDTH / 2 else 1

    safe_x = clamp(hoop_x + direction * (DUNK_RANGE_X + 70), BALL_RAD, WIDTH - BALL_RAD)
    safe_y = clamp(HOOP_Y + 55, BALL_RAD, GROUND_Y - BALL_RAD)

    player["x"] = clamp(safe_x - CHAR_W / 2, 0, WIDTH - CHAR_W)
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


def award_score(room, scored_team):
    ball = room["ball"]
    points = get_score_points(room, scored_team)
    room["score"][scored_team - 1] += points

    scorer_id = ball.get("last_touch_player")

    if scorer_id in room["players"]:
        scorer = room["players"][scorer_id]
        scorer["match_points"] = scorer.get("match_points", 0) + points
        scorer["match_baskets"] = scorer.get("match_baskets", 0) + 1
    room["replay_id"] = room.get("replay_id", 0) + 1
    room["replay_timer"] = 360

    room["skip_votes"] = set()
    room["skip_votes_display"] = []

    room["last_score_team"] = scored_team
    room["last_score_points"] = points
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
    ball["shot_origin_x"] = None
    ball["shot_origin_y"] = None
    ball["score_override"] = None

    reset_all_players_after_score(room)

    if room["score"][0] >= MAX_SCORE:
        room["game_started"] = False
        room["game_over"] = True
        room["winner_team"] = 1

    elif room["score"][1] >= MAX_SCORE:
        room["game_started"] = False
        room["game_over"] = True
        room["winner_team"] = 2


def room_physics_loop(room_code):
    while room_code in rooms and rooms[room_code]["game_started"]:
        room = rooms[room_code]
        ball = room["ball"]

        # Durante o replay, congela a partida.
        if room.get("replay_timer", 0) > 0:
            room["replay_timer"] -= 1
            time.sleep(1 / FPS)
            continue

        prev_ball_y = ball["y"]

        if ball.get("dunk_no_score_timer", 0) > 0:
            ball["dunk_no_score_timer"] -= 1

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

            resolve_hoop_collisions(ball)

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
        scored_team = resolve_dunk_score_team(room)

        if (
            scored_team is None
            and ball.get("dunk_no_score_timer", 0) <= 0
            and ball_crossed_hoop(prev_ball_y, ball, LEFT_HOOP_X1, LEFT_HOOP_X2)
        ):
            scored_team = 2

        elif (
            scored_team is None
            and ball.get("dunk_no_score_timer", 0) <= 0
            and ball_crossed_hoop(prev_ball_y, ball, RIGHT_HOOP_X1, RIGHT_HOOP_X2)
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
                    update_dunk_position(p)

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

            if p.get("stun_timer", 0) > 0:
                p["stun_timer"] -= 1

            if p.get("ability_cd", 0) > 0 and not ability_paused:
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
                "last_score_points": 2,
                "next_clash_id": 0,

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
                    "shot_origin_x": None,
                    "shot_origin_y": None,
                    "score_override": None,
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
                    "skin_id": "default",
                    "team": team,
                    "x": 0,
                    "y": 0,
                }

                spawn_player_for_match(room["players"][player_id])
                reset_player_match_stats(room["players"][player_id])

                conn.send(pickle.dumps(("SUCCESS", room_code, player_id, team, True, chosen_char)))

            else:
                room["players"][player_id] = {
                    "char": None,
                    "skin_id": "default",
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

                    if client_data.get("skin_id") in COSMETICS:
                        player["skin_id"] = client_data["skin_id"]

                elif client_data.get("action") == "START_GAME" and player_id == room["host_id"]:
                    room["game_started"] = True

                    for p_data in room["players"].values():
                        if p_data.get("char") is None:
                            p_data["char"] = choose_available_character(room) or CHARACTERS[0]

                        spawn_player_for_match(p_data)
                        reset_player_match_stats(p_data)

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
                        and player.get("dunk_active", 0) <= 0
                        and player.get("clash_active", 0) <= 0
                    ):
                        player["x"] = clamp(client_data["x"], 0, WIDTH - CHAR_W)

                    if player.get("dunk_active", 0) <= 0 and player.get("clash_active", 0) <= 0:
                        player["y"] = clamp(client_data["y"], 0, GROUND_Y - CHAR_H)

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
                    room["ball"]["shot_origin_x"] = player["x"] + CHAR_W / 2
                    room["ball"]["shot_origin_y"] = player["y"] + CHAR_H / 2
                    room["ball"]["score_override"] = None

                elif action == "DUNK_START" and player.get("roleta_state") != "CUTSCENE":
                    if can_start_dunk(player, room["ball"], player_id):
                        start_dunk(player)
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

                elif action == "USE_ABILITY" and player.get("roleta_state") != "CUTSCENE":
                    char = player["char"]

                    if player.get("ability_cd", 0) <= 0 and player.get("clash_active", 0) <= 0:
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

                        elif char == "Rafael":
                            player["throw_buff_timer"] = 240
                            player["ability_cd"] = ABILITY_COOLDOWNS.get(char, 360)

                        elif char == "John Jonh":
                            player["john_float_timer"] = 300
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
