import pygame
import zlib  # SPEC-02: validacao de crc


import sys
import os
import math
import tkinter as tk
import random
import copy
import subprocess
import time
from collections import deque
from config import *
from network import Network, load_server_config, save_server_config
import save_db

pygame.init()
save_db.init_db()


try:
    pygame.mixer.init()
except pygame.error:
    print("[AVISO] Não foi possível iniciar o mixer de áudio.")

screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("NN League - Multiplayer")
clock = pygame.time.Clock()

font_sm = pygame.font.SysFont("Arial", 20)
font_md = pygame.font.SysFont("Arial", 32)
font_lg = pygame.font.SysFont("Arial", 64, bold=True)
font_title = pygame.font.SysFont("Arial", 40, bold=True)
font_xl = pygame.font.SysFont("Arial", 100, bold=True)

IMAGES_DIR = "imagens"
AUDIOS_DIR = "audios"


def get_image_path(filename):
    return os.path.join(IMAGES_DIR, filename)


def normalize_audio_name(char_name):
    name = char_name.lower().replace(" ", "").replace("_", "")

    if name == "johnjonh":
        return "johnjonh"

    return name


def find_goal_audio(char_name):
    if not char_name:
        return None

    base_name = normalize_audio_name(char_name)
    audio_number = random.randint(1, 3)

    possible_extensions = [".mp3", ".wav", ".ogg"]

    for ext in possible_extensions:
        path = os.path.join(AUDIOS_DIR, f"gol{base_name}{audio_number}{ext}")
        if os.path.exists(path):
            return path

    return None


def get_throw_power(player_data):
    power = 25

    if player_data.get("char") == "Rafael":
        power = 35

    if player_data.get("char") == "Caique":
        power += min(10, float(player_data.get("caique_rage", 0)) * 0.10)

    if player_data.get("jackpot_timer", 0) > 0:
        power += 15
    elif player_data.get("throw_buff_timer", 0) > 0:
        power += 10
    elif player_data.get("throw_debuff_timer", 0) > 0:
        power -= 10

    return power


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
    closest_x = max(rx, min(ball["x"], rx + rw))
    closest_y = max(ry, min(ball["y"], ry + rh))
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


def resolve_hoop_collisions(ball, world_width=WIDTH):
    geo = get_court_geometry(world_width)

    for rim_x in (geo["left_hoop_x1"], geo["left_hoop_x2"], geo["right_hoop_x1"], geo["right_hoop_x2"]):
        resolve_circle_point_collision(ball, rim_x, HOOP_Y, HOOP_RIM_RAD)

    resolve_circle_rect_collision(ball, (geo["left_backboard_x"], BACKBOARD_Y, BACKBOARD_W, BACKBOARD_H))
    resolve_circle_rect_collision(ball, (geo["right_backboard_x"], BACKBOARD_Y, BACKBOARD_W, BACKBOARD_H))


def get_attack_hoop(team, world_width=WIDTH):
    geo = get_court_geometry(world_width)

    if team == 1:
        return (geo["right_hoop_x1"] + geo["right_hoop_x2"]) / 2, HOOP_Y

    return (geo["left_hoop_x1"] + geo["left_hoop_x2"]) / 2, HOOP_Y


def can_start_dunk_locally(player_data, ball):
    world_width = int(player_data.get("world_width", ball.get("world_width", WIDTH)))
    if ball.get("holder") is None:
        return False

    if player_data.get("dunk_active", 0) > 0:
        return False

    if player_data.get("stun_timer", 0) > 0 or player_data.get("knockback_timer", 0) > 0:
        return False

    if player_data["y"] >= GROUND_Y - CHAR_H - 4:
        return False

    hoop_x, hoop_y = get_attack_hoop(player_data["team"], world_width)
    player_cx = player_data["x"] + CHAR_W / 2
    player_cy = player_data["y"] + CHAR_H / 2
    range_bonus_x = 45 if player_data.get("dunk_buff_timer", 0) > 0 else 0
    range_bonus_y = 35 if player_data.get("dunk_buff_timer", 0) > 0 else 0

    return (
        abs(player_cx - hoop_x) <= DUNK_RANGE_X + range_bonus_x
        and abs(player_cy - hoop_y) <= DUNK_RANGE_Y + range_bonus_y
    )


def qte_key_from_event(event):
    if event.key == pygame.K_w:
        return "W"

    if event.key == pygame.K_a:
        return "A"

    if event.key == pygame.K_s:
        return "S"

    if event.key == pygame.K_d:
        return "D"

    return None


def trainer_copy_character_from_key(key):
    number_keys = [
        (pygame.K_1, pygame.K_KP1),
        (pygame.K_2, pygame.K_KP2),
        (pygame.K_3, pygame.K_KP3),
        (pygame.K_4, pygame.K_KP4),
        (pygame.K_5, pygame.K_KP5),
        (pygame.K_6, pygame.K_KP6),
        (pygame.K_7, pygame.K_KP7),
        (pygame.K_8, pygame.K_KP8),
    ]

    for i, keys in enumerate(number_keys):
        if key in keys and i < len(TRAINER_COPY_CHARACTERS):
            return TRAINER_COPY_CHARACTERS[i]

    return None


ABILITY_ACHIEVEMENTS = {
    "Henrique": "henrique_dash",
    "Natan": "natan_ghost",
    "Presscinotti": "press_wall",
    "Rafael": "rafael_arc",
    "Miguel": "miguel_shadow",
    "John Jonh": "john_float",
    "Diogo": "diogo_cookie",
    "Paulo": "paulo_spin",
}

SECRET_CHARACTER_CODE = [
    pygame.K_UP,
    pygame.K_UP,
    pygame.K_DOWN,
    pygame.K_DOWN,
    pygame.K_LEFT,
    pygame.K_RIGHT,
    pygame.K_LEFT,
    pygame.K_RIGHT,
    pygame.K_b,
    pygame.K_a,
    pygame.K_RETURN,
]

SECRET_SELECTABLE_CHARACTERS = [char for char in SECRET_CHARACTERS if char != "Bola"]
LOBBY_CHARACTERS = PUBLIC_CHARACTERS

SECRET_CHARACTER_SLOTS = SECRET_SELECTABLE_CHARACTERS
STORY_COMPLETION_UNLOCK_LEVEL = 12

HAVOC_COMMAND_OPTIONS = [
    ("deliver", "ENTREGAR BOLA", "Se estiver com a bola, entrega para o Havoc; senao, a bola cai perto do alvo."),
    ("freeze", "CONGELAR", "Fica parado e perde a bola por alguns segundos."),
    ("retreat", "RECUAR", "Volta para a defesa com lentidao."),
]

REACTION_OPTIONS = ["Boa!", "Kkk", "Passa!", "Foi mal", "Fraco", "Nossa!"]


def draw_skin_overlay(surface, x, y, w, h, skin_id, scale=1.0):
    cosmetic = COSMETICS.get(skin_id)

    if not cosmetic or skin_id == "default":
        return

    color = cosmetic["color"]
    accent = cosmetic["accent"]
    ticks = pygame.time.get_ticks()
    pulse = (math.sin(ticks / 180) + 1) / 2
    center_x = int(x + w / 2)
    center_y = int(y + h / 2)
    torso = pygame.Rect(x + int(w * 0.12), y + int(h * 0.32), int(w * 0.76), int(h * 0.36))
    shorts = pygame.Rect(x + int(w * 0.18), y + int(h * 0.66), int(w * 0.64), int(h * 0.18))

    effect = cosmetic.get("effect")

    if effect == "glow":
        radius = int(max(w, h) * (0.55 + pulse * 0.12))
        pygame.draw.circle(surface, (*accent, 70), (center_x, center_y), radius, max(1, int(4 * scale)))
    elif effect == "shine":
        pygame.draw.circle(surface, accent, (center_x, int(y + h * 0.12)), max(2, int((3 + pulse * 3) * scale)))
        pygame.draw.line(surface, accent, (center_x, int(y - h * 0.08)), (center_x, int(y + h * 0.05)), max(1, int(2 * scale)))
    elif effect == "ember":
        for i in range(3):
            spark_x = int(x + w * (0.2 + i * 0.3))
            spark_y = int(y + h * (0.25 + ((ticks // 90 + i) % 5) * 0.12))
            pygame.draw.circle(surface, accent, (spark_x, spark_y), max(1, int(2 * scale)))
    elif effect == "bounce":
        arc_y = int(y + h + 4 * scale + pulse * 5 * scale)
        pygame.draw.arc(surface, color, (int(x - w * 0.1), arc_y, int(w * 1.2), int(h * 0.25)), 0, math.pi, max(1, int(2 * scale)))
    elif effect == "stars":
        for i in range(4):
            angle = ticks / 400 + i * math.pi / 2
            sx = int(center_x + math.cos(angle) * w * 0.65)
            sy = int(center_y + math.sin(angle) * h * 0.48)
            pygame.draw.circle(surface, accent, (sx, sy), max(1, int(2 * scale)))
    elif effect == "speed":
        for i in range(3):
            yy = int(y + h * (0.25 + i * 0.18))
            offset = int((ticks // 70 + i * 9) % max(1, int(w * 0.35)))
            pygame.draw.line(surface, accent, (int(x - w * 0.2) + offset, yy), (int(x + w * 0.22) + offset, yy), max(1, int(2 * scale)))
    elif effect == "shadow_aura":
        aura = pygame.Rect(int(x - w * 0.12), int(y + h * 0.1), int(w * 1.24), int(h * 0.88))
        pygame.draw.ellipse(surface, (*accent, 80), aura, max(1, int(3 * scale)))
        pygame.draw.circle(surface, accent, (int(x + w * 0.18), int(y + h * (0.2 + pulse * 0.55))), max(1, int(2 * scale)))
    elif effect == "crumbs":
        for i in range(5):
            crumb_x = int(x + w * (0.12 + i * 0.18))
            crumb_y = int(y + h * (0.18 + ((ticks // 120 + i) % 4) * 0.18))
            pygame.draw.circle(surface, accent, (crumb_x, crumb_y), max(1, int((1.5 + (i % 2)) * scale)))
    elif effect == "jackpot":
        pygame.draw.circle(surface, accent, (center_x, center_y), int(max(w, h) * (0.42 + pulse * 0.08)), max(1, int(2 * scale)))
        for i, label in enumerate(["7", "$", "7"]):
            if scale > 2:
                txt = font_sm.render(label, True, accent)
                surface.blit(txt, (int(x + w * (0.25 + i * 0.2)), int(y + h * 0.04)))
    elif effect == "lightning":
        pts = [
            (int(x + w * 0.58), int(y + h * 0.05)),
            (int(x + w * 0.42), int(y + h * 0.42)),
            (int(x + w * 0.56), int(y + h * 0.42)),
            (int(x + w * 0.38), int(y + h * 0.84)),
        ]
        pygame.draw.lines(surface, accent, False, pts, max(1, int(3 * scale)))
    elif effect == "ice":
        for i in range(3):
            spike_x = int(x + w * (0.18 + i * 0.32))
            pygame.draw.polygon(
                surface,
                accent,
                [
                    (spike_x, int(y + h * 0.1)),
                    (spike_x - int(5 * scale), int(y + h * 0.24)),
                    (spike_x + int(5 * scale), int(y + h * 0.24)),
                ],
            )
    elif effect == "toxic":
        for i in range(3):
            bubble_x = int(x + w * (0.22 + i * 0.28))
            bubble_y = int(y + h * (0.7 - pulse * 0.22 + i * 0.04))
            pygame.draw.circle(surface, color, (bubble_x, bubble_y), max(1, int((3 + i) * scale)), max(1, int(1 * scale)))

    if cosmetic.get("outfit", True):
        pygame.draw.rect(surface, color, torso, border_radius=max(2, int(6 * scale)))
        pygame.draw.rect(surface, accent, shorts, border_radius=max(2, int(5 * scale)))
        pygame.draw.line(surface, accent, (torso.left, torso.top), (torso.right, torso.top), max(1, int(3 * scale)))

        if skin_id in ["blue_star", "gold_royal", "jackpot_orange", "galaxy_set"]:
            pygame.draw.circle(surface, accent, torso.center, max(2, int(w * 0.09)))

        if skin_id in ["shadow", "havoc_black"]:
            pygame.draw.line(surface, accent, (torso.left, torso.bottom), (torso.right, torso.top), max(1, int(3 * scale)))

        if skin_id == "midnight_blue":
            pygame.draw.line(surface, accent, (torso.left, torso.centery), (torso.right, torso.centery), max(1, int(2 * scale)))
            pygame.draw.circle(surface, accent, (torso.centerx, torso.top + max(2, int(5 * scale))), max(1, int(w * 0.05)))

        if skin_id == "cookie_cream":
            dot_radius = max(1, int(w * 0.035))
            pygame.draw.circle(surface, accent, (torso.left + int(w * 0.2), torso.centery), dot_radius)
            pygame.draw.circle(surface, accent, (torso.right - int(w * 0.18), torso.top + int(h * 0.1)), dot_radius)
            pygame.draw.circle(surface, accent, (shorts.centerx, shorts.centery), dot_radius)

    hat = cosmetic.get("hat")

    if hat == "crown":
        base_y = int(y + h * 0.08)
        points = [
            (int(x + w * 0.15), base_y + int(10 * scale)),
            (int(x + w * 0.28), base_y - int(7 * scale)),
            (int(x + w * 0.42), base_y + int(7 * scale)),
            (int(x + w * 0.55), base_y - int(9 * scale)),
            (int(x + w * 0.72), base_y + int(8 * scale)),
            (int(x + w * 0.86), base_y - int(6 * scale)),
            (int(x + w * 0.9), base_y + int(11 * scale)),
        ]
        pygame.draw.polygon(surface, color, points)
        pygame.draw.line(surface, accent, points[0], points[-1], max(1, int(2 * scale)))
    elif hat == "propeller":
        cap = pygame.Rect(int(x + w * 0.16), int(y + h * 0.02), int(w * 0.68), int(h * 0.12))
        pygame.draw.rect(surface, color, cap, border_radius=max(2, int(5 * scale)))
        prop_y = cap.top - int(6 * scale)
        pygame.draw.line(surface, accent, (center_x - int(w * 0.35), prop_y), (center_x + int(w * 0.35), prop_y), max(1, int(3 * scale)))
        pygame.draw.line(surface, color, (center_x, prop_y - int(5 * scale)), (center_x, prop_y + int(5 * scale)), max(1, int(2 * scale)))
    elif hat == "halo":
        halo_rect = pygame.Rect(int(x + w * 0.12), int(y - h * 0.05), int(w * 0.76), int(h * 0.16))
        pygame.draw.ellipse(surface, color, halo_rect, max(1, int(3 * scale)))
        pygame.draw.ellipse(surface, accent, halo_rect.inflate(int(5 * scale), int(5 * scale)), max(1, int(1 * scale)))
    elif hat == "cap":
        cap = pygame.Rect(int(x + w * 0.12), int(y + h * 0.04), int(w * 0.68), int(h * 0.12))
        brim = pygame.Rect(int(x + w * 0.58), int(y + h * 0.08), int(w * 0.34), int(h * 0.045))
        pygame.draw.rect(surface, color, cap, border_radius=max(2, int(5 * scale)))
        pygame.draw.rect(surface, accent, brim, border_radius=max(1, int(3 * scale)))

    shoes = cosmetic.get("shoes")

    if shoes:
        left_shoe = pygame.Rect(int(x + w * 0.05), int(y + h * 0.86), int(w * 0.38), int(h * 0.12))
        right_shoe = pygame.Rect(int(x + w * 0.57), int(y + h * 0.86), int(w * 0.38), int(h * 0.12))
        pygame.draw.rect(surface, color, left_shoe, border_radius=max(2, int(5 * scale)))
        pygame.draw.rect(surface, color, right_shoe, border_radius=max(2, int(5 * scale)))
        pygame.draw.line(surface, accent, left_shoe.midleft, left_shoe.midright, max(1, int(2 * scale)))
        pygame.draw.line(surface, accent, right_shoe.midleft, right_shoe.midright, max(1, int(2 * scale)))

        if shoes == "fire":
            pygame.draw.polygon(surface, accent, [(left_shoe.left, left_shoe.top), (left_shoe.left - int(6 * scale), left_shoe.centery), (left_shoe.left, left_shoe.bottom)])
            pygame.draw.polygon(surface, accent, [(right_shoe.right, right_shoe.top), (right_shoe.right + int(6 * scale), right_shoe.centery), (right_shoe.right, right_shoe.bottom)])
        elif shoes == "toole":
            eye_r = max(1, int(2 * scale))
            pygame.draw.circle(surface, WHITE, (left_shoe.centerx, left_shoe.top), eye_r)
            pygame.draw.circle(surface, WHITE, (right_shoe.centerx, right_shoe.top), eye_r)
            if scale > 2:
                label = font_sm.render("TOOLE", True, accent)
                label = pygame.transform.scale(label, (max(18, int(w * 0.48)), max(7, int(h * 0.06))))
                surface.blit(label, (int(x + w * 0.26), int(y + h * 0.99)))
        elif shoes == "star":
            pygame.draw.circle(surface, accent, left_shoe.center, max(1, int(3 * scale)))
            pygame.draw.circle(surface, accent, right_shoe.center, max(1, int(3 * scale)))


def predict_ball_path(ball, target_x, target_y, power, steps=180, world_width=WIDTH):
    angle = math.atan2(target_y - ball["y"], target_x - ball["x"])
    x = ball["x"]
    y = ball["y"] - 10
    vel_x = math.cos(angle) * power
    vel_y = math.sin(angle) * power
    points = [(int(x), int(y))]

    for _ in range(steps):
        vel_y += GRAVITY
        x += vel_x
        y += vel_y

        if y >= GROUND_Y - BALL_RAD:
            y = GROUND_Y - BALL_RAD
            vel_y *= -0.7
            vel_x *= 0.9

        if x <= BALL_RAD:
            x = BALL_RAD
            vel_x *= -0.8

        if x >= world_width - BALL_RAD:
            x = world_width - BALL_RAD
            vel_x *= -0.8

        temp_ball = {"x": x, "y": y, "vel_x": vel_x, "vel_y": vel_y}
        resolve_hoop_collisions(temp_ball, world_width)
        x = temp_ball["x"]
        y = temp_ball["y"]
        vel_x = temp_ball["vel_x"]
        vel_y = temp_ball["vel_y"]

        points.append((int(x), int(y)))

        if abs(vel_x) < 0.35 and abs(vel_y) < 1 and y >= GROUND_Y - BALL_RAD - 1:
            break

    return points


def make_team_tinted_image(image, team):
    tinted = image.copy().convert_alpha()
    overlay = pygame.Surface(tinted.get_size(), pygame.SRCALPHA)

    if team == 1:
        overlay.fill((40, 80, 255, 95))
    else:
        overlay.fill((255, 40, 40, 95))

    tinted.blit(overlay, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)
    return tinted

def get_story_mode_path():
    base_dir = os.path.dirname(os.path.abspath(sys.argv[0]))

    story_exe = os.path.join(base_dir, "story_mode.exe")
    story_py = os.path.join(base_dir, "story_mode.py")

    if os.path.exists(story_exe):
        return story_exe

    return story_py


def start_story_mode_process():
    story_path = get_story_mode_path()

    try:
        if story_path.endswith(".exe"):
            subprocess.Popen(
                [story_path],
                cwd=os.path.dirname(story_path)
            )
        else:
            subprocess.Popen(
                [sys.executable, story_path],
                cwd=os.path.dirname(story_path)
            )

    except Exception as e:
        print(f"[ERRO] Não foi possível abrir o modo história: {e}")

def get_server_script_path():
    base_dir = os.path.dirname(os.path.abspath(sys.argv[0]))

    server_exe = os.path.join(base_dir, "server.exe")
    server_py = os.path.join(base_dir, "server.py")

    if os.path.exists(server_exe):
        return server_exe

    return server_py


def start_local_server_process():
    server_path = get_server_script_path()

    try:
        if server_path.endswith(".exe"):
            return subprocess.Popen(
                [server_path],
                cwd=os.path.dirname(server_path)
            )

        return subprocess.Popen(
            [sys.executable, server_path],
            cwd=os.path.dirname(server_path)
        )

    except Exception as e:
        print(f"[ERRO] Não foi possível iniciar o servidor local: {e}")
        return None


def get_clipboard_text():
    try:
        root = tk.Tk()
        root.withdraw()
        text = root.clipboard_get()
        root.destroy()
        return text.strip()
    except Exception:
        return ""


def set_clipboard_text(text):
    try:
        root = tk.Tk()
        root.withdraw()
        root.clipboard_clear()
        root.clipboard_append(text)
        root.update()
        root.destroy()
    except Exception:
        pass


class Button:
    def __init__(self, text, x, y, w, h, color, text_color=WHITE):
        self.rect = pygame.Rect(x, y, w, h)
        self.text = text
        self.color = color
        self.text_color = text_color
        self.txt_surf = font_md.render(text, True, self.text_color)
        self.txt_rect = self.txt_surf.get_rect(center=self.rect.center)

    def draw(self, surface):
        pygame.draw.rect(surface, self.color, self.rect, border_radius=12)
        pygame.draw.rect(surface, BLACK, self.rect, 2, border_radius=12)
        surface.blit(self.txt_surf, self.txt_rect)

    def is_clicked(self, pos):
        return self.rect.collidepoint(pos)


class GameClient:
    def __init__(self):
        self.net = Network()

        config = load_server_config()

        self.host_ip = config.get("server_host", "127.0.0.1")
        self.active_input = "room"
        self.local_server_process = None
        self.is_local_host = False

        self.state = "MENU"
        self.my_id = None
        self.my_team = None
        self.is_host = False
        self.room_code = ""
        self.error_msg = ""
        self.server_data = None
        # SPEC-03: estado de interpolacao de render
        self._interp = {}
        self._ball_interp = [None, None]
        self._ping_counter = 0  # SPEC-04: frame counter p/ ping periodico
        self._last_frame_id = -1  # SPEC-02: ultimo frame_id valido
        self.conn_token = None  # SPEC-01: token de reconexao da sala atual

        self._desync_count = 0  # SPEC-02: contador de dessincronizacoes


        self.current_window_width = WIDTH

        self.selected_char_idx = 0
        self.player_x = 0
        self.player_y = 0
        self.vel_y = 0
        self.is_jumping = False

        self.speed = 6
        self.jump_power = -16
        self.gravity = 0.8

        self.ability_cooldown = 0
        self.facing = 1

        self.replay_buffer = deque(maxlen=180)
        self.replay_playing = False
        self.replay_frames = []
        self.replay_index = 0
        self.replay_tick = 0
        self.last_replay_id = 0
        self.reward_applied_for_replay_id = None
        self.reward_message = ""
        self.current_goal_sound = None
        self.skip_replay_requested = False
        self.reward_applied_for_replay_id = None
        self.reward_message = ""
        self.shop_selected_skin = "default"
        self.shop_message = ""
        self.shop_scroll = 0
        self.achievements_scroll = 0
        self.achievement_notifications = []
        self.current_achievement_notification = None
        self.secret_character_select_open = False
        self.secret_code_buffer = []
        self.secret_bola_buffer = ""
        self.admin_code_buffer = ""
        self.admin_password_open = False
        self.admin_password = ""
        self.admin_message = ""
        self.admin_message_timer = 0
        self.trainer_ability_selecting = False
        self.murilo_drawing = False
        self.murilo_draw_points = []
        self.murilo_message = ""
        self.murilo_message_timer = 0
        self.murilo_pending_confirmation = False
        self.havoc_selecting_target = False
        self.havoc_selected_target_id = None
        self.havoc_command_rects = []
        self.bola_aiming = False
        self.reaction_wheel_open = False
        self.reaction_rects = []
        self.last_seen_clash_id = None
        self.last_dunk_ready_state = 0
        self.seen_jackpot_players = set()
        self.opponent_jackpot_seen = False

        self.btn_create = Button("CRIAR SALA", WIDTH // 2 - 220, 430, 200, 60, TEAM_1_COLOR)
        self.btn_join = Button("ENTRAR", WIDTH // 2 + 20, 430, 200, 60, TEAM_2_COLOR)
        self.btn_story = Button("MODO HISTÓRIA", WIDTH // 2 - 330, 500, 300, 55, (120, 80, 200))
        self.btn_shop = Button("LOJA", WIDTH // 2 + 30, 500, 300, 55, (60, 150, 120))
        self.btn_stats = Button("ESTATISTICAS", WIDTH // 2 - 330, 560, 300, 50, (80, 110, 180))
        self.btn_achievements = Button("ACHIEVMENTS", WIDTH // 2 + 30, 560, 300, 50, (170, 130, 55))
        self.btn_quit_game = Button("SAIR DO JOGO", WIDTH // 2 - 120, 625, 240, 45, (180, 40, 40))

        self.host_ip_rect = pygame.Rect(WIDTH // 2 - 160, 250, 320, 45)
        self.room_code_rect = pygame.Rect(WIDTH // 2 - 100, 340, 200, 50)

        # Seletor de pontos para vencer (host escolhe ao criar a sala)
        self.win_points_index = WIN_POINTS_OPTIONS.index(DEFAULT_WIN_POINTS) if DEFAULT_WIN_POINTS in WIN_POINTS_OPTIONS else 0
        self.btn_win_left = pygame.Rect(WIDTH // 2 - 235, 188, 40, 40)
        self.btn_win_right = pygame.Rect(WIDTH // 2 + 195, 188, 40, 40)

        self.btn_start_game = Button("INICIAR", WIDTH - 220, 20, 200, 60, BALL_COLOR)
        self.btn_add_bot = Button("+ BOT", WIDTH - 220, 90, 95, 40, (70, 150, 90))
        self.btn_remove_bot = Button("- BOT", WIDTH - 115, 90, 95, 40, (160, 80, 70))
        self.btn_team_blue = Button("TIME AZUL", 50, 80, 180, 40, TEAM_1_COLOR)
        self.btn_team_red = Button("TIME VERM.", 240, 80, 180, 40, TEAM_2_COLOR)

        self.btn_leave_lobby = Button("SAIR DA SALA", WIDTH - 240, HEIGHT - 70, 220, 50, (180, 40, 40))
        self.btn_leave_match = Button("SAIR", WIDTH - 130, 15, 110, 45, (180, 40, 40))
        self.btn_skip_replay = Button("SKIP", WIDTH - 150, HEIGHT - 70, 130, 50, (220, 170, 40), BLACK)

        self.btn_exit = Button("VOLTAR AO MENU", WIDTH // 2 - 130, HEIGHT - 100, 260, 60, (220, 50, 50))
        self.btn_shop_back = Button("VOLTAR", 40, HEIGHT - 75, 180, 55, (180, 40, 40))
        self.btn_shop_buy = Button("COMPRAR", WIDTH - 270, HEIGHT - 150, 220, 55, (70, 170, 90))
        self.btn_shop_equip = Button("EQUIPAR", WIDTH - 270, HEIGHT - 85, 220, 55, TEAM_1_COLOR)
        self.btn_stats_back = Button("VOLTAR", 40, HEIGHT - 75, 180, 55, (180, 40, 40))
        self.btn_achievements_back = Button("VOLTAR", 40, HEIGHT - 75, 180, 55, (180, 40, 40))
        self.btn_secret_back = Button("VOLTAR", 40, HEIGHT - 75, 180, 55, (180, 40, 40))

        self.char_images = {}
        self.small_char_images = {}
        self.tinted_small_images = {}

        self.card_w = 125
        self.card_h = 400

        for name, info in CHARACTERS_INFO.items():
            image_path = get_image_path(info["img"])

            if os.path.exists(image_path):
                original_img = pygame.image.load(image_path).convert_alpha()

                self.char_images[name] = pygame.transform.scale(
                    original_img,
                    (self.card_w, self.card_h)
                )

                self.small_char_images[name] = pygame.transform.scale(
                    original_img,
                    (CHAR_W, CHAR_H)
                )

                self.tinted_small_images[(name, 1)] = make_team_tinted_image(
                    self.small_char_images[name],
                    1
                )

                self.tinted_small_images[(name, 2)] = make_team_tinted_image(
                    self.small_char_images[name],
                    2
                )

            else:
                self.char_images[name] = None
                self.small_char_images[name] = None
                self.tinted_small_images[(name, 1)] = None
                self.tinted_small_images[(name, 2)] = None

        self.jackpot_img = None
        jackpot_path = get_image_path("paulo_dancando.png")

        if os.path.exists(jackpot_path):
            self.jackpot_img = pygame.transform.scale(
                pygame.image.load(jackpot_path).convert_alpha(),
                (self.card_w, self.card_h)
            )

        self.cage_img = None
        cage_path = get_image_path(CAGE_IMG)

        if os.path.exists(cage_path):
            self.cage_w = 300
            self.cage_h = 250
            self.cage_img = pygame.transform.scale(
                pygame.image.load(cage_path).convert_alpha(),
                (self.cage_w, self.cage_h)
            )

        self.char_rects = []

    def stop_local_server(self):
        if self.local_server_process:
            try:
                self.local_server_process.terminate()
            except Exception:
                pass

            self.local_server_process = None
            self.is_local_host = False

    def create_local_room(self):
        if self.local_server_process is None:
            self.local_server_process = start_local_server_process()
            self.is_local_host = True
            time.sleep(0.8)

        self.net = Network(server_host="127.0.0.1")
        win_points = WIN_POINTS_OPTIONS[self.win_points_index]
        response = self.net.connect("CREATE", win_points=win_points)
        self.handle_connection(response)

    def join_remote_room(self):
        host = self.host_ip.strip()
        code = self.room_code.strip().upper()

        if not host:
            self.error_msg = "Digite o IP Radmin do host."
            return

        if len(code) != 4:
            self.error_msg = "O código deve ter 4 dígitos."
            return

        save_server_config(host)
        self.net = Network(server_host=host)
        # SPEC-01: tenta reconectar com token salvo antes de entrar como novo
        token = save_db.load_conn_token(code)
        if token:
            response = self.net.connect("REJOIN", code, token=token)
            if response and response[0] == "SUCCESS":
                self.handle_connection(response)
                return
        response = self.net.connect("JOIN", code)
        self.handle_connection(response)


    def leave_match_to_menu(self):
        if self.net.connected:
            self.net.disconnect()

        self.net = Network()
        self.server_data = None
        self.room_code = ""
        self.my_id = None
        self.my_team = None
        self.is_host = False
        self.ability_cooldown = 0
        self.player_x = 0
        self.player_y = 0
        self.vel_y = 0
        self.is_jumping = False
        self.replay_buffer.clear()
        self.replay_playing = False
        self.replay_frames = []
        self.replay_index = 0
        self.replay_tick = 0
        self.last_replay_id = 0
        self.secret_character_select_open = False
        self.secret_code_buffer = []
        self.trainer_ability_selecting = False
        self.murilo_drawing = False
        self.murilo_draw_points = []
        self.murilo_message = ""
        self.murilo_message_timer = 0
        self.murilo_pending_confirmation = False

        if self.current_goal_sound:
            self.current_goal_sound.stop()
            self.current_goal_sound = None

        if self.is_local_host:
            self.stop_local_server()

        self.state = "MENU"

    def play_goal_audio(self, char_name):
        audio_path = find_goal_audio(char_name)

        if audio_path:
            try:
                if self.current_goal_sound:
                    self.current_goal_sound.stop()

                self.current_goal_sound = pygame.mixer.Sound(audio_path)
                self.current_goal_sound.play()

            except pygame.error:
                print(f"[AVISO] Não foi possível tocar o áudio: {audio_path}")

    def stop_replay_local(self, stop_audio=False):
        self.replay_playing = False
        self.replay_frames = []
        self.replay_index = 0
        self.replay_tick = 0

        if stop_audio and self.current_goal_sound:
            self.current_goal_sound.stop()
            self.current_goal_sound = None

    def record_replay_frame(self):
        if self.state == "PLAYING" and self.server_data and not self.replay_playing:
            if not self.server_data.get("game_over"):
                self.replay_buffer.append(copy.deepcopy(self.server_data))

    def check_replay_trigger(self):
        if not self.server_data:
            return

        replay_id = self.server_data.get("replay_id", 0)
        replay_timer = self.server_data.get("replay_timer", 0)

        if self.replay_playing and replay_timer <= 0:
            self.stop_replay_local(stop_audio=self.skip_replay_requested)
            self.skip_replay_requested = False

            if self.server_data and self.my_id in self.server_data.get("players", {}):
                my_data = self.server_data["players"][self.my_id]
                self.player_x = my_data["x"]
                self.player_y = my_data["y"]
                self.vel_y = 0
                self.is_jumping = False

            return

        if replay_id != self.last_replay_id:
            self.last_replay_id = replay_id

            if replay_id > 0:
                scorer_char = self.server_data.get("last_score_char")
                self.play_goal_audio(scorer_char)

            if replay_id > 0 and len(self.replay_buffer) > 15:
                self.replay_frames = list(self.replay_buffer)[-120:]
                self.replay_playing = True
                self.replay_index = 0
                self.replay_tick = 0

    def draw_replay_frame(self):
        if not self.replay_frames:
            self.replay_playing = False
            return

        if self.replay_index >= len(self.replay_frames):
            self.stop_replay_local()
            return

        current_data = self.server_data

        self.server_data = self.replay_frames[self.replay_index]
        self.draw_game()
        self.server_data = current_data

        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 70))
        screen.blit(overlay, (0, 0))

        pygame.draw.rect(screen, BLACK, (0, 0, WIDTH, 80))
        pygame.draw.rect(screen, BLACK, (0, HEIGHT - 80, WIDTH, 80))

        replay_txt = font_lg.render("REPLAY", True, (255, 215, 0))
        screen.blit(replay_txt, (WIDTH // 2 - replay_txt.get_width() // 2, 12))

        slow_txt = font_md.render("CÂMERA LENTA", True, WHITE)
        screen.blit(slow_txt, (WIDTH // 2 - slow_txt.get_width() // 2, HEIGHT - 65))

        score_team = current_data.get("last_score_team") if current_data else None
        score_char = current_data.get("last_score_char") if current_data else None
        score_points = current_data.get("last_score_points", 2) if current_data else 2

        if score_team == 1:
            cesta_txt = font_md.render(f"CESTA DO TIME AZUL! +{score_points}", True, TEAM_1_COLOR)
        elif score_team == 2:
            cesta_txt = font_md.render(f"CESTA DO TIME VERMELHO! +{score_points}", True, TEAM_2_COLOR)
        else:
            cesta_txt = font_md.render(f"CESTA! +{score_points}", True, WHITE)

        screen.blit(cesta_txt, (WIDTH // 2 - cesta_txt.get_width() // 2, 90))

        if score_char:
            scorer_txt = font_sm.render(f"Último toque: {score_char}", True, WHITE)
            screen.blit(scorer_txt, (WIDTH // 2 - scorer_txt.get_width() // 2, 125))

        skip_votes = current_data.get("skip_votes_display", []) if current_data else []
        total_players = len(current_data.get("players", {})) if current_data else 0

        skip_count_txt = font_sm.render(f"Skip: {len(skip_votes)}/{total_players}", True, WHITE)
        screen.blit(skip_count_txt, (WIDTH - 150, HEIGHT - 100))

        if self.my_id in skip_votes:
            voted_txt = font_sm.render("Seu voto foi enviado", True, (255, 255, 120))
            screen.blit(voted_txt, (WIDTH - 230, HEIGHT - 125))

        self.btn_skip_replay.draw(screen)

        self.replay_tick += 1

        if self.replay_tick >= 3:
            self.replay_tick = 0
            self.replay_index += 1

    def draw_menu(self):
        screen.fill(COURT_COLOR)

        if self.admin_message_timer > 0:
            self.admin_message_timer -= 1
        elif self.admin_message:
            self.admin_message = ""

        title = font_lg.render("NN LEAGUE", True, BLACK)
        screen.blit(title, (WIDTH // 2 - title.get_width() // 2, 70))

        ip_label = font_sm.render("IP Radmin do host:", True, BLACK)
        screen.blit(ip_label, (self.host_ip_rect.x, self.host_ip_rect.y - 25))

        pygame.draw.rect(screen, WHITE, self.host_ip_rect, border_radius=8)

        border_color = (255, 215, 0) if self.active_input == "host" else BLACK
        pygame.draw.rect(screen, border_color, self.host_ip_rect, 3, border_radius=8)

        ip_text = font_md.render(self.host_ip, True, BLACK)
        screen.blit(ip_text, (self.host_ip_rect.x + 10, self.host_ip_rect.y + 6))

        code_label = font_sm.render("Código da sala:", True, BLACK)
        screen.blit(code_label, (self.room_code_rect.x, self.room_code_rect.y - 25))

        pygame.draw.rect(screen, WHITE, self.room_code_rect, border_radius=8)

        border_color = (255, 215, 0) if self.active_input == "room" else BLACK
        pygame.draw.rect(screen, border_color, self.room_code_rect, 3, border_radius=8)

        code_text = font_md.render(self.room_code, True, BLACK)
        screen.blit(
            code_text,
            (
                self.room_code_rect.centerx - code_text.get_width() // 2,
                self.room_code_rect.y + 8
            )
        )

        hint1 = font_sm.render("Criar sala: inicia servidor neste PC automaticamente.", True, BLACK)
        hint2 = font_sm.render("Entrar: use o IP Radmin do host + código da sala.", True, BLACK)
        hint3 = font_sm.render("Dica: Ctrl+V cola o IP ou código no campo selecionado.", True, BLACK)

        screen.blit(hint1, (WIDTH // 2 - hint1.get_width() // 2, 395))
        screen.blit(hint2, (WIDTH // 2 - hint2.get_width() // 2, 615))
        screen.blit(hint3, (WIDTH // 2 - hint3.get_width() // 2, 645))

        # Seletor de pontos para vencer (apenas quem cria a sala)
        wp = WIN_POINTS_OPTIONS[self.win_points_index]
        panel_wp = pygame.Rect(WIDTH // 2 - 235, 185, 470, 46)
        pygame.draw.rect(screen, (18, 22, 28), panel_wp, border_radius=12)
        pygame.draw.rect(screen, (255, 215, 0), panel_wp, 2, border_radius=12)
        label = font_sm.render(f"Pontos p/ vencer: {wp}", True, (255, 230, 120))
        screen.blit(label, (WIDTH // 2 - label.get_width() // 2, 195))
        pygame.draw.polygon(screen, (255, 215, 0), [(WIDTH // 2 - 225, 208), (WIDTH // 2 - 205, 196), (WIDTH // 2 - 205, 220)])
        pygame.draw.polygon(screen, (255, 215, 0), [(WIDTH // 2 + 225, 208), (WIDTH // 2 + 205, 196), (WIDTH // 2 + 205, 220)])

        self.btn_create.draw(screen)
        self.btn_join.draw(screen)
        self.btn_story.draw(screen)
        self.btn_shop.draw(screen)
        self.btn_stats.draw(screen)
        self.btn_achievements.draw(screen)
        self.btn_quit_game.draw(screen)

        money_txt = font_md.render(f"Dinheiro: ${save_db.get_money()}", True, BLACK)
        screen.blit(money_txt, (20, 20))

        if self.admin_message:
            msg = font_sm.render(self.admin_message, True, (20, 120, 20) if "liberado" in self.admin_message.lower() else (180, 30, 30))
            screen.blit(msg, (WIDTH // 2 - msg.get_width() // 2, 35))

        if self.admin_password_open:
            overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 120))
            screen.blit(overlay, (0, 0))

            panel = pygame.Rect(WIDTH // 2 - 260, HEIGHT // 2 - 115, 520, 230)
            pygame.draw.rect(screen, (18, 22, 28), panel, border_radius=18)
            pygame.draw.rect(screen, (255, 215, 0), panel, 3, border_radius=18)

            title = font_md.render("ACESSO ADMIN", True, (255, 215, 0))
            screen.blit(title, (panel.centerx - title.get_width() // 2, panel.y + 24))

            hint = font_sm.render("Digite a senha e aperte ENTER. ESC cancela.", True, WHITE)
            screen.blit(hint, (panel.centerx - hint.get_width() // 2, panel.y + 65))

            input_rect = pygame.Rect(panel.x + 55, panel.y + 108, panel.w - 110, 48)
            pygame.draw.rect(screen, WHITE, input_rect, border_radius=8)
            pygame.draw.rect(screen, (255, 215, 0), input_rect, 2, border_radius=8)

            password_text = "*" * len(self.admin_password)
            pass_txt = font_md.render(password_text, True, BLACK)
            screen.blit(pass_txt, (input_rect.x + 12, input_rect.y + 8))

            action = font_sm.render("Ao confirmar: libera historia, conquistas e dinheiro.", True, (220, 220, 220))
            screen.blit(action, (panel.centerx - action.get_width() // 2, panel.y + 178))

        if self.error_msg:
            err = font_sm.render(self.error_msg, True, (200, 0, 0))
            screen.blit(err, (WIDTH // 2 - err.get_width() // 2, 585))

    def draw_character_preview(self, char_name, skin_id, x, y, w, h):
        img = self.char_images.get(char_name)

        if img:
            screen.blit(pygame.transform.scale(img, (w, h)), (x, y))
        else:
            pygame.draw.rect(screen, CHARACTERS_INFO[char_name]["color"], (x, y, w, h))

        draw_skin_overlay(screen, x, y, w, h, skin_id, w / CHAR_W)
        pygame.draw.rect(screen, WHITE, (x, y, w, h), 2)

    def draw_character_info_panel(self, char_name, title_y=HEIGHT - 112):
        panel_rect = pygame.Rect(0, HEIGHT - 145, WIDTH, 145)
        pygame.draw.rect(screen, (20, 20, 25), panel_rect)
        pygame.draw.rect(screen, (50, 50, 60), panel_rect, 3)

        info = CHARACTERS_INFO[char_name]
        desc_title = font_title.render(char_name.upper(), True, info["color"])
        screen.blit(desc_title, (50, title_y))

        desc_lines = self.render_wrapped_text(info["desc"], font_sm, WHITE, WIDTH - 100)
        y = HEIGHT - 75

        for line in desc_lines[:1]:
            screen.blit(line, (50, y))
            y += 23

        ultimate_cost = ULTIMATE_COSTS.get(char_name, ULTIMATE_MAX)
        ultimate_text = f"Supremo (Q) - Custo {ultimate_cost}: {info.get('ultimate_desc', 'Versao exagerada do poder.')}"
        ultimate_lines = self.render_wrapped_text(ultimate_text, font_sm, (255, 220, 95), WIDTH - 100)

        for line in ultimate_lines[:2]:
            screen.blit(line, (50, y))
            y += 22

    def draw_shop(self):
        screen.fill((18, 28, 34))

        if CHARACTERS[self.selected_char_idx] in SECRET_CHARACTERS:
            self.selected_char_idx = CHARACTERS.index(PUBLIC_CHARACTERS[0])

        title = font_lg.render("LOJA DE COSMETICOS", True, (120, 240, 200))
        screen.blit(title, (WIDTH // 2 - title.get_width() // 2, 35))

        money_txt = font_md.render(f"Dinheiro: ${save_db.get_money()}", True, (255, 230, 120))
        screen.blit(money_txt, (40, 95))

        char_name = CHARACTERS[self.selected_char_idx]
        progress = save_db.get_character_progress(char_name)
        equipped = save_db.get_equipped_skin(char_name)
        owned = save_db.get_owned_skins()

        char_txt = font_md.render(
            f"{char_name} | Level {progress['level']} XP {progress['xp']}/{save_db.xp_for_next_level(progress['level'])}",
            True,
            WHITE,
        )
        screen.blit(char_txt, (40, 135))

        self.shop_char_rects = []

        for i, name in enumerate(PUBLIC_CHARACTERS):
            char_idx = CHARACTERS.index(name)
            rect = pygame.Rect(500 + (i % 4) * 155, 95 + (i // 4) * 42, 145, 34)
            self.shop_char_rects.append((rect, char_idx))
            pygame.draw.rect(screen, (65, 80, 95) if char_idx == self.selected_char_idx else (35, 45, 55), rect, border_radius=8)
            pygame.draw.rect(screen, (255, 230, 120) if char_idx == self.selected_char_idx else GRAY, rect, 2, border_radius=8)
            p = save_db.get_character_progress(name)
            txt = font_sm.render(f"{name} Lv{p['level']}", True, WHITE)
            screen.blit(txt, (rect.x + 8, rect.y + 7))

        self.shop_skin_rects = []
        skin_items = list(COSMETICS.items())
        visible_top = 190
        visible_bottom = HEIGHT - 170
        max_scroll = max(0, len(skin_items) * 72 - (visible_bottom - visible_top))
        self.shop_scroll = max(0, min(self.shop_scroll, max_scroll))

        for i, (skin_id, cosmetic) in enumerate(skin_items):
            rect = pygame.Rect(45, visible_top + i * 72 - self.shop_scroll, 420, 58)

            if rect.bottom < visible_top or rect.top > visible_bottom:
                continue

            self.shop_skin_rects.append((rect, skin_id))
            selected = skin_id == self.shop_selected_skin
            pygame.draw.rect(screen, (55, 90, 85) if selected else (35, 45, 50), rect, border_radius=10)
            pygame.draw.rect(screen, (120, 240, 200) if selected else GRAY, rect, 2, border_radius=10)

            status = "EQUIPADA" if skin_id == equipped else ("COMPRADA" if skin_id in owned else f"${cosmetic['price']}")
            item_type = cosmetic.get("item_type", "Roupa")
            txt = font_sm.render(f"[{item_type}] {cosmetic['name']} - {status}", True, WHITE)
            screen.blit(txt, (rect.x + 15, rect.y + 11))

            if cosmetic.get("effect"):
                effect_txt = font_sm.render("Efeito visual", True, (120, 240, 200))
                screen.blit(effect_txt, (rect.x + 15, rect.y + 33))

        if max_scroll > 0:
            bar_h = max(35, int((visible_bottom - visible_top) * (visible_bottom - visible_top) / (len(skin_items) * 72)))
            bar_y = visible_top + int((visible_bottom - visible_top - bar_h) * (self.shop_scroll / max_scroll))
            pygame.draw.rect(screen, (45, 60, 65), (475, visible_top, 10, visible_bottom - visible_top), border_radius=5)
            pygame.draw.rect(screen, (120, 240, 200), (475, bar_y, 10, bar_h), border_radius=5)

        self.draw_character_preview(char_name, self.shop_selected_skin, WIDTH - 510, 150, self.card_w * 2, self.card_h)

        info_txt = font_md.render(COSMETICS[self.shop_selected_skin]["name"], True, WHITE)
        screen.blit(info_txt, (WIDTH - 530, 150 + self.card_h + 20))

        selected_cosmetic = COSMETICS[self.shop_selected_skin]
        type_txt = font_sm.render(f"Tipo: {selected_cosmetic.get('item_type', 'Roupa')}", True, (180, 220, 220))
        screen.blit(type_txt, (WIDTH - 530, 150 + self.card_h + 58))

        self.btn_shop_buy.draw(screen)
        self.btn_shop_equip.draw(screen)
        self.btn_shop_back.draw(screen)

        if self.shop_message:
            msg = font_md.render(self.shop_message, True, (255, 230, 120))
            screen.blit(msg, (WIDTH // 2 - msg.get_width() // 2, HEIGHT - 45))

    def draw_stats(self):
        screen.fill((22, 24, 34))

        title = font_lg.render("ESTATISTICAS", True, (150, 190, 255))
        screen.blit(title, (WIDTH // 2 - title.get_width() // 2, 30))

        stats = save_db.get_global_stats()
        story_level = save_db.get_unlocked_story_level()
        achievements = save_db.get_achievements()

        summary_lines = [
            f"Partidas: {stats['matches']}   Vitorias: {stats['wins']}   Derrotas: {stats['losses']}",
            f"Cestas totais: {stats['baskets']}   Pontos totais: {stats['points']}",
            f"Modo historia: fase {story_level} desbloqueada",
            f"Achievements desbloqueados: {len(achievements)}",
        ]

        y = 105
        for line in summary_lines:
            txt = font_md.render(line, True, WHITE)
            screen.blit(txt, (45, y))
            y += 34

        headers = ["Personagem", "Lv", "XP", "Part.", "V", "D", "Cestas", "Pts"]
        xs = [45, 245, 305, 410, 500, 555, 610, 720]
        y = 260

        for x, header in zip(xs, headers):
            txt = font_sm.render(header, True, (150, 190, 255))
            screen.blit(txt, (x, y))

        y += 28

        for char in PUBLIC_CHARACTERS:
            p = save_db.get_character_progress(char)
            values = [
                char,
                str(p["level"]),
                f"{p['xp']}/{save_db.xp_for_next_level(p['level'])}",
                str(p["matches"]),
                str(p["wins"]),
                str(p["losses"]),
                str(p["baskets"]),
                str(p["points"]),
            ]

            for x, value in zip(xs, values):
                txt = font_sm.render(value, True, WHITE)
                screen.blit(txt, (x, y))

            y += 26

        ach_title = font_md.render("Achievements recentes", True, (255, 230, 120))
        screen.blit(ach_title, (860, 245))

        ach_y = 290
        recent = achievements[:10]

        if not recent:
            empty = font_sm.render("Nenhum ainda.", True, GRAY)
            screen.blit(empty, (860, ach_y))
        else:
            for ach in recent:
                label = ach["achievement_id"].replace(":", " - ")
                txt = font_sm.render(label, True, WHITE)
                screen.blit(txt, (860, ach_y))
                ach_y += 28

        self.btn_stats_back.draw(screen)

    def draw_achievement_icon(self, rect, icon_type, unlocked):
        center = rect.center
        main = (255, 215, 80) if unlocked else (85, 85, 85)
        accent = (255, 245, 180) if unlocked else (45, 45, 45)

        pygame.draw.rect(screen, (30, 32, 42), rect, border_radius=14)
        pygame.draw.rect(screen, main if unlocked else GRAY, rect, 3, border_radius=14)

        if icon_type == "trophy":
            cup = pygame.Rect(center[0] - 18, center[1] - 18, 36, 30)
            pygame.draw.rect(screen, main, cup, border_radius=8)
            pygame.draw.rect(screen, accent, (center[0] - 7, center[1] + 12, 14, 18), border_radius=4)
            pygame.draw.rect(screen, main, (center[0] - 22, center[1] + 28, 44, 8), border_radius=4)
            pygame.draw.arc(screen, main, (cup.left - 18, cup.top + 2, 28, 24), math.pi / 2, math.pi * 1.5, 3)
            pygame.draw.arc(screen, main, (cup.right - 10, cup.top + 2, 28, 24), -math.pi / 2, math.pi / 2, 3)

        elif icon_type == "ball":
            pygame.draw.circle(screen, main, center, 26)
            pygame.draw.circle(screen, accent, center, 26, 3)
            pygame.draw.line(screen, accent, (center[0] - 24, center[1]), (center[0] + 24, center[1]), 3)
            pygame.draw.arc(screen, accent, (center[0] - 24, center[1] - 26, 22, 52), -1.2, 1.2, 3)
            pygame.draw.arc(screen, accent, (center[0] + 2, center[1] - 26, 22, 52), 1.9, 4.4, 3)

        elif icon_type == "star":
            points = []
            for i in range(10):
                radius = 28 if i % 2 == 0 else 12
                angle = -math.pi / 2 + i * math.pi / 5
                points.append((center[0] + math.cos(angle) * radius, center[1] + math.sin(angle) * radius))
            pygame.draw.polygon(screen, main, points)
            pygame.draw.polygon(screen, accent, points, 2)

        elif icon_type == "crown":
            pts = [
                (center[0] - 30, center[1] + 20),
                (center[0] - 24, center[1] - 15),
                (center[0] - 8, center[1] + 2),
                (center[0], center[1] - 24),
                (center[0] + 8, center[1] + 2),
                (center[0] + 24, center[1] - 15),
                (center[0] + 30, center[1] + 20),
            ]
            pygame.draw.polygon(screen, main, pts)
            pygame.draw.rect(screen, accent, (center[0] - 28, center[1] + 16, 56, 10), border_radius=4)

        else:
            pygame.draw.rect(screen, main, (center[0] - 22, center[1] - 8, 44, 20), border_radius=8)
            pygame.draw.circle(screen, accent, (center[0] - 12, center[1] + 12), 8)
            pygame.draw.circle(screen, accent, (center[0] + 18, center[1] + 10), 7)

        if not unlocked:
            lock = font_md.render("?", True, WHITE)
            screen.blit(lock, (center[0] - lock.get_width() // 2, center[1] - lock.get_height() // 2))

    def draw_achievements(self):
        screen.fill((24, 20, 30))
        mouse_pos = pygame.mouse.get_pos()

        title = font_lg.render("ACHIEVMENTS", True, (255, 215, 90))
        screen.blit(title, (WIDTH // 2 - title.get_width() // 2, 30))

        all_achievements = save_db.get_all_achievements_status()
        unlocked_count = sum(1 for item in all_achievements if item["unlocked"])
        total_count = len(all_achievements)

        count_txt = font_md.render(f"Desbloqueados: {unlocked_count}/{total_count}", True, WHITE)
        screen.blit(count_txt, (50, 95))

        hovered = None
        cols = 8
        size = 82
        gap_x = 62
        gap_y = 36
        start_x = 58
        rows = math.ceil(len(all_achievements) / cols)
        content_height = rows * (size + gap_y)
        max_scroll = max(0, content_height - (HEIGHT - 230))
        self.achievements_scroll = max(0, min(self.achievements_scroll, max_scroll))
        start_y = 150 - self.achievements_scroll

        for i, item in enumerate(all_achievements):
            col = i % cols
            row = i // cols
            x = start_x + col * (size + gap_x)
            y = start_y + row * (size + gap_y)
            rect = pygame.Rect(x, y, size, size)

            if rect.bottom < 135 or rect.top > HEIGHT - 155:
                continue

            self.draw_achievement_icon(rect, item["icon"], item["unlocked"])

            char_label = font_sm.render(item["character"][:8], True, WHITE if item["unlocked"] else GRAY)
            screen.blit(char_label, (rect.centerx - char_label.get_width() // 2, rect.bottom + 4))

            if rect.collidepoint(mouse_pos):
                hovered = item
                pygame.draw.rect(screen, WHITE, rect, 3, border_radius=14)

        if hovered:
            tooltip = pygame.Rect(335, HEIGHT - 145, 610, 95)
            pygame.draw.rect(screen, (12, 12, 18), tooltip, border_radius=12)
            pygame.draw.rect(screen, (255, 215, 90), tooltip, 2, border_radius=12)
            status = "DESBLOQUEADO" if hovered["unlocked"] else "BLOQUEADO"
            title_txt = font_md.render(f"{hovered['character']} - {hovered['name']} ({status})", True, WHITE)
            desc_txt = font_sm.render(hovered["description"], True, (220, 220, 220))
            screen.blit(title_txt, (tooltip.x + 18, tooltip.y + 15))
            screen.blit(desc_txt, (tooltip.x + 18, tooltip.y + 55))

        if max_scroll > 0:
            bar_h = max(45, int((HEIGHT - 250) * ((HEIGHT - 250) / content_height)))
            bar_y = 145 + int((HEIGHT - 250 - bar_h) * (self.achievements_scroll / max_scroll))
            pygame.draw.rect(screen, (50, 50, 60), (WIDTH - 35, 145, 12, HEIGHT - 250), border_radius=6)
            pygame.draw.rect(screen, (255, 215, 90), (WIDTH - 35, bar_y, 12, bar_h), border_radius=6)

        self.btn_achievements_back.draw(screen)

    def draw_lobby(self):
        screen.fill((30, 30, 40))
        mouse_pos = pygame.mouse.get_pos()

        room_txt = font_title.render(f"SALA: {self.room_code}", True, WHITE)
        screen.blit(room_txt, (20, 20))

        if self.is_host:
            self.btn_start_game.draw(screen)
            self.btn_add_bot.draw(screen)
            self.btn_remove_bot.draw(screen)
            bot_hint = font_sm.render(f"+ BOT usa selecionado: {CHARACTERS[self.selected_char_idx]}", True, (180, 230, 180))
            screen.blit(bot_hint, (WIDTH - 220, 135))
        else:
            wait_txt = font_md.render("Aguardando o Host...", True, GRAY)
            screen.blit(wait_txt, (WIDTH - wait_txt.get_width() - 20, 30))

        self.btn_team_blue.draw(screen)
        self.btn_team_red.draw(screen)
        self.btn_leave_lobby.draw(screen)

        if self.my_team == 1:
            pygame.draw.rect(screen, (255, 255, 0), self.btn_team_blue.rect, 4, border_radius=12)
        else:
            pygame.draw.rect(screen, (255, 255, 0), self.btn_team_red.rect, 4, border_radius=12)

        if self.server_data:
            y_pos = 140

            for pid, p_data in self.server_data["players"].items():
                p_team_color = TEAM_1_COLOR if p_data["team"] == 1 else TEAM_2_COLOR
                p_char = p_data["char"] if p_data["char"] else "Escolhendo..."
                prefix = p_data.get("bot_name", f"P{pid}") if p_data.get("is_bot") else f"P{pid}"
                p_text = f"{prefix}: {p_char}"

                if pid == self.my_id:
                    p_text += " (Você)"
                    pygame.draw.rect(screen, (255, 255, 0), (45, y_pos, 250, 30), 1)

                txt_surf = font_sm.render(p_text, True, p_team_color)
                screen.blit(txt_surf, (50, y_pos + 5))
                y_pos += 35

        total_width = (self.card_w * len(LOBBY_CHARACTERS)) + (10 * (len(LOBBY_CHARACTERS) - 1))
        start_x = (WIDTH - total_width) // 2
        start_y = 180

        self.char_rects = []
        hovered_char = None

        for i, name in enumerate(LOBBY_CHARACTERS):
            char_idx = CHARACTERS.index(name)
            x = start_x + i * (self.card_w + 10)
            rect = pygame.Rect(x, start_y, self.card_w, self.card_h)
            self.char_rects.append((rect, char_idx))

            is_taken = False

            if self.server_data:
                for pid, p_data in self.server_data["players"].items():
                    if pid != self.my_id and p_data["char"] == name:
                        is_taken = True

            if self.char_images[name]:
                screen.blit(self.char_images[name], (x, start_y))
            else:
                pygame.draw.rect(screen, CHARACTERS_INFO[name]["color"], rect)
                name_txt = font_sm.render(name, True, BLACK)
                screen.blit(name_txt, (x + 10, start_y + self.card_h // 2))

            draw_skin_overlay(screen, x, start_y, self.card_w, self.card_h, save_db.get_equipped_skin(name), self.card_w / CHAR_W)

            if is_taken:
                dark_surface = pygame.Surface((self.card_w, self.card_h), pygame.SRCALPHA)
                dark_surface.fill((0, 0, 0, 180))
                screen.blit(dark_surface, (x, start_y))

                taken_txt = font_sm.render("EM USO", True, (255, 50, 50))
                screen.blit(
                    taken_txt,
                    (x + self.card_w // 2 - taken_txt.get_width() // 2, start_y + self.card_h // 2)
                )

            if char_idx == self.selected_char_idx:
                pygame.draw.rect(screen, (255, 215, 0), rect, 5)

            if rect.collidepoint(mouse_pos):
                hovered_char = name
                pygame.draw.rect(screen, WHITE, rect, 2)

        char_to_show = hovered_char if hovered_char else CHARACTERS[self.selected_char_idx]
        self.draw_character_info_panel(char_to_show)

    def register_secret_character_code_key(self, event):
        key = pygame.K_RETURN if event.key == pygame.K_KP_ENTER else event.key

        if key not in SECRET_CHARACTER_CODE:
            self.secret_code_buffer = []
            return

        self.secret_code_buffer.append(key)
        self.secret_code_buffer = self.secret_code_buffer[-len(SECRET_CHARACTER_CODE):]

        if self.secret_code_buffer == SECRET_CHARACTER_CODE:
            self.secret_character_select_open = True
            self.secret_code_buffer = []

    def clear_murilo_drawing(self, message=None):
        self.murilo_drawing = False
        self.murilo_draw_points = []

        if message:
            self.murilo_message = message
            self.murilo_message_timer = 150

    def add_murilo_draw_point(self, pos):
        if not self.murilo_draw_points:
            self.murilo_draw_points.append(pos)
            return

        last_x, last_y = self.murilo_draw_points[-1]

        if math.hypot(pos[0] - last_x, pos[1] - last_y) >= 6:
            self.murilo_draw_points.append(pos)
            self.murilo_draw_points = self.murilo_draw_points[-180:]

    def build_murilo_ability_payload(self):
        if len(self.murilo_draw_points) < 8:
            self.clear_murilo_drawing("Desenho muito curto.")
            return None

        payload_points = [(int(x), int(y)) for x, y in self.murilo_draw_points]
        self.clear_murilo_drawing("Confirmando desenho...")
        self.murilo_pending_confirmation = True

        return {
            "action": "USE_ABILITY",
            "facing": self.facing,
            "murilo_points": payload_points,
        }

    def clear_havoc_selection(self):
        self.havoc_selecting_target = False
        self.havoc_selected_target_id = None
        self.havoc_command_rects = []

    def get_havoc_enemy_at_pos(self, mouse_pos, my_p):
        if not self.server_data:
            return None

        for p_id, p_data in self.server_data["players"].items():
            if p_id == self.my_id:
                continue

            if p_data.get("team") == my_p.get("team") or p_data.get("char") is None:
                continue

            rect = pygame.Rect(p_data["x"] - 10, p_data["y"] - 10, CHAR_W + 20, CHAR_H + 20)

            if rect.collidepoint(mouse_pos):
                return p_id

        return None

    def send_havoc_command_payload(self, command):
        if self.havoc_selected_target_id is None:
            return None

        return {
            "action": "USE_ABILITY",
            "facing": self.facing,
            "havoc_target_id": self.havoc_selected_target_id,
            "havoc_command": command,
        }

    def draw_havoc_selection(self, my_p_data):
        if not self.havoc_selecting_target:
            return

        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 55))
        screen.blit(overlay, (0, 0))

        mouse_pos = pygame.mouse.get_pos()
        hovered_target = self.get_havoc_enemy_at_pos(mouse_pos, my_p_data)

        for p_id, p_data in self.server_data["players"].items():
            if p_id == self.my_id or p_data.get("team") == my_p_data.get("team") or p_data.get("char") is None:
                continue

            selected = p_id == self.havoc_selected_target_id
            hovered = p_id == hovered_target
            color = (255, 70, 40) if selected else (255, 170, 80) if hovered else (190, 55, 45)
            rect = pygame.Rect(p_data["x"] - 12, p_data["y"] - 12, CHAR_W + 24, CHAR_H + 24)
            pygame.draw.rect(screen, color, rect, 3, border_radius=8)
            pygame.draw.circle(screen, color, (int(p_data["x"] + CHAR_W / 2), int(p_data["y"] + CHAR_H / 2)), 42, 2)

        panel = pygame.Rect(WIDTH // 2 - 390, 96, 780, 150 if self.havoc_selected_target_id is None else 245)
        pygame.draw.rect(screen, (15, 15, 20), panel, border_radius=18)
        pygame.draw.rect(screen, (255, 70, 40), panel, 3, border_radius=18)

        title = font_md.render("HAVOC: ORDEM DA QUADRA", True, (255, 90, 55))
        screen.blit(title, (panel.centerx - title.get_width() // 2, panel.y + 18))

        if self.havoc_selected_target_id is None:
            hint = font_sm.render("Clique em um inimigo para dominar. ESC cancela.", True, WHITE)
            screen.blit(hint, (panel.centerx - hint.get_width() // 2, panel.y + 62))
            self.havoc_command_rects = []
            return

        target = self.server_data["players"].get(self.havoc_selected_target_id, {})
        target_name = target.get("char", "Alvo")
        hint = font_sm.render(f"Alvo: {target_name}. Escolha uma ordem com 1-3, clique, ou ESC.", True, WHITE)
        screen.blit(hint, (panel.centerx - hint.get_width() // 2, panel.y + 58))

        self.havoc_command_rects = []

        for i, (command, label, desc) in enumerate(HAVOC_COMMAND_OPTIONS):
            rect = pygame.Rect(panel.x + 32 + i * 244, panel.y + 102, 224, 104)
            mouse_over = rect.collidepoint(mouse_pos)
            bg = (55, 28, 24) if mouse_over else (32, 25, 25)
            pygame.draw.rect(screen, bg, rect, border_radius=14)
            pygame.draw.rect(screen, (255, 90, 55), rect, 2, border_radius=14)

            label_txt = font_sm.render(f"{i + 1} - {label}", True, (255, 120, 75))
            screen.blit(label_txt, (rect.x + 14, rect.y + 14))

            words = desc.split()
            line = ""
            y = rect.y + 44

            for word in words:
                candidate = f"{line} {word}".strip()

                if font_sm.size(candidate)[0] > rect.w - 24:
                    desc_txt = font_sm.render(line, True, WHITE)
                    screen.blit(desc_txt, (rect.x + 14, y))
                    y += 22
                    line = word
                else:
                    line = candidate

            if line:
                desc_txt = font_sm.render(line, True, WHITE)
                screen.blit(desc_txt, (rect.x + 14, y))

            self.havoc_command_rects.append((rect, command))

    def draw_reaction_wheel(self):
        if not self.reaction_wheel_open:
            return

        center_x, center_y = WIDTH // 2, HEIGHT // 2
        panel = pygame.Rect(center_x - 220, center_y - 120, 440, 240)
        pygame.draw.rect(screen, (12, 14, 20), panel, border_radius=18)
        pygame.draw.rect(screen, (255, 215, 90), panel, 3, border_radius=18)

        title = font_md.render("REAÇÕES", True, (255, 215, 90))
        screen.blit(title, (panel.centerx - title.get_width() // 2, panel.y + 16))

        self.reaction_rects = []

        for i, reaction in enumerate(REACTION_OPTIONS):
            col = i % 3
            row = i // 3
            rect = pygame.Rect(panel.x + 35 + col * 125, panel.y + 72 + row * 62, 110, 44)
            mouse_over = rect.collidepoint(pygame.mouse.get_pos())
            pygame.draw.rect(screen, (50, 55, 70) if mouse_over else (30, 34, 48), rect, border_radius=12)
            pygame.draw.rect(screen, WHITE if mouse_over else (120, 125, 145), rect, 2, border_radius=12)
            txt = font_sm.render(reaction, True, WHITE)
            screen.blit(txt, (rect.centerx - txt.get_width() // 2, rect.centery - txt.get_height() // 2))
            self.reaction_rects.append((rect, reaction))

    def draw_secret_character_select(self):
        screen.fill((18, 18, 24))
        mouse_pos = pygame.mouse.get_pos()

        title = font_lg.render("SELECAO SECRETA", True, (255, 215, 0))
        screen.blit(title, (WIDTH // 2 - title.get_width() // 2, 28))

        subtitle = font_sm.render("Codigo desbloqueado. Escolha um personagem secreto. Digite BOLA para virar a bola.", True, WHITE)
        screen.blit(subtitle, (WIDTH // 2 - subtitle.get_width() // 2, 92))

        total_width = (self.card_w * len(SECRET_CHARACTER_SLOTS)) + (10 * (len(SECRET_CHARACTER_SLOTS) - 1))
        start_x = (WIDTH - total_width) // 2
        start_y = 180
        story_completed = save_db.get_unlocked_story_level() >= STORY_COMPLETION_UNLOCK_LEVEL

        self.secret_char_rects = []
        hovered_char = None

        for i, slot_name in enumerate(SECRET_CHARACTER_SLOTS):
            x = start_x + i * (self.card_w + 10)
            rect = pygame.Rect(x, start_y, self.card_w, self.card_h)
            is_character_slot = slot_name in CHARACTERS_INFO

            if is_character_slot:
                char_idx = CHARACTERS.index(slot_name)
                is_story_locked = slot_name == "Treinador" and not story_completed

                if not is_story_locked:
                    self.secret_char_rects.append((rect, char_idx))

                is_taken = False

                if self.server_data:
                    for pid, p_data in self.server_data["players"].items():
                        if pid != self.my_id and p_data["char"] == slot_name:
                            is_taken = True

                if self.char_images[slot_name]:
                    screen.blit(self.char_images[slot_name], (x, start_y))
                else:
                    pygame.draw.rect(screen, CHARACTERS_INFO[slot_name]["color"], rect)
                    name_txt = font_sm.render(slot_name, True, BLACK)
                    screen.blit(name_txt, (x + 10, start_y + self.card_h // 2))

                if is_taken:
                    dark_surface = pygame.Surface((self.card_w, self.card_h), pygame.SRCALPHA)
                    dark_surface.fill((0, 0, 0, 180))
                    screen.blit(dark_surface, (x, start_y))

                    taken_txt = font_sm.render("EM USO", True, (255, 50, 50))
                    screen.blit(
                        taken_txt,
                        (x + self.card_w // 2 - taken_txt.get_width() // 2, start_y + self.card_h // 2)
                    )

                if is_story_locked:
                    dark_surface = pygame.Surface((self.card_w, self.card_h), pygame.SRCALPHA)
                    dark_surface.fill((0, 0, 0, 195))
                    screen.blit(dark_surface, (x, start_y))

                    lock_txt = font_sm.render("BLOQUEADO", True, (255, 215, 0))
                    screen.blit(lock_txt, (x + self.card_w // 2 - lock_txt.get_width() // 2, start_y + self.card_h // 2 - 20))

                    story_txt = font_sm.render("TERMINE A HISTORIA", True, WHITE)
                    screen.blit(story_txt, (x + self.card_w // 2 - story_txt.get_width() // 2, start_y + self.card_h // 2 + 12))

                if char_idx == self.selected_char_idx:
                    pygame.draw.rect(screen, (255, 215, 0), rect, 5)

                if rect.collidepoint(mouse_pos):
                    hovered_char = slot_name
                    pygame.draw.rect(screen, WHITE, rect, 2)
            else:
                pygame.draw.rect(screen, (25, 25, 32), rect)
                pygame.draw.rect(screen, (255, 215, 0), rect, 2)

                slot_txt = font_lg.render("???", True, (255, 215, 0))
                screen.blit(slot_txt, (x + self.card_w // 2 - slot_txt.get_width() // 2, start_y + self.card_h // 2 - 45))

                label = font_sm.render("BLOQUEADO", True, GRAY)
                screen.blit(label, (x + self.card_w // 2 - label.get_width() // 2, start_y + self.card_h // 2 + 20))

        char_to_show = hovered_char

        if not char_to_show and CHARACTERS[self.selected_char_idx] in SECRET_CHARACTERS:
            char_to_show = CHARACTERS[self.selected_char_idx]

        if char_to_show:
            if char_to_show == "Treinador" and not story_completed:
                panel_rect = pygame.Rect(0, HEIGHT - 145, WIDTH, 145)
                pygame.draw.rect(screen, (20, 20, 25), panel_rect)
                pygame.draw.rect(screen, (50, 50, 60), panel_rect, 3)
                desc_title = font_title.render(char_to_show.upper(), True, CHARACTERS_INFO[char_to_show]["color"])
                screen.blit(desc_title, (50, HEIGHT - 112))
                desc = "Bloqueado: termine o modo historia para liberar o Treinador."
                desc_text = font_md.render(desc, True, WHITE)
                screen.blit(desc_text, (50, HEIGHT - 58))
            else:
                self.draw_character_info_panel(char_to_show)
        else:
            panel_rect = pygame.Rect(0, HEIGHT - 145, WIDTH, 145)
            pygame.draw.rect(screen, (20, 20, 25), panel_rect)
            pygame.draw.rect(screen, (50, 50, 60), panel_rect, 3)
            desc_title = font_title.render("PERSONAGENS SECRETOS", True, (255, 215, 0))
            screen.blit(desc_title, (50, HEIGHT - 112))

            desc_text = font_md.render("Passe o mouse em um card para ver a habilidade.", True, WHITE)
            screen.blit(desc_text, (50, HEIGHT - 58))

        self.btn_secret_back.draw(screen)

    def draw_cutscene(self):
        screen.fill(BLACK)

        pygame.draw.circle(screen, (255, 255, 200), (WIDTH // 2, HEIGHT // 2), 200)

        if pygame.time.get_ticks() % 500 < 250:
            jack_txt = font_xl.render("JACKPOT ÉPICO!", True, (255, 215, 0))
            screen.blit(jack_txt, (WIDTH // 2 - jack_txt.get_width() // 2, 100))

        paulo_img = self.jackpot_img if self.jackpot_img else self.char_images.get("Paulo")

        if paulo_img:
            if (pygame.time.get_ticks() // 150) % 2 == 0:
                dancer = pygame.transform.flip(paulo_img, True, False)
            else:
                dancer = paulo_img

            screen.blit(dancer, (WIDTH // 2 - self.card_w // 2, HEIGHT // 2 - self.card_h // 2))

        dance_txt = font_md.render("* Dança da Vitória *", True, WHITE)
        screen.blit(dance_txt, (WIDTH // 2 - dance_txt.get_width() // 2, HEIGHT - 100))

    def draw_game_over(self):
        if not self.server_data or not self.server_data.get("game_over"):
            return

        winner_team = self.server_data["winner_team"]
        winner_color = TEAM_1_COLOR if winner_team == 1 else TEAM_2_COLOR
        winner_text = "TIME AZUL VENCEU!" if winner_team == 1 else "TIME VERMELHO VENCEU!"

        screen.fill((20, 25, 35))

        title_surf = font_xl.render(winner_text, True, winner_color)
        screen.blit(title_surf, (WIDTH // 2 - title_surf.get_width() // 2, 50))

        score = self.server_data["score"]
        win_points = int(self.server_data.get("win_points", DEFAULT_WIN_POINTS))
        score_text = font_xl.render(f"{score[0]} x {score[1]}", True, WHITE)

        # Painel do placar (HUD melhorado)
        pygame.draw.rect(screen, BLACK, (world_width // 2 - 130, 8, 260, 84), border_radius=18)
        pygame.draw.rect(screen, TEAM_1_COLOR, (world_width // 2 - 130, 8, 130, 84), 4, border_radius=18)
        pygame.draw.rect(screen, TEAM_2_COLOR, (world_width // 2, 8, 130, 84), 4, border_radius=18)
        screen.blit(score_text, (world_width // 2 - score_text.get_width() // 2, 12))

        # Barra de progresso ate os pontos para vencer
        bar_x = world_width // 2 - 120
        bar_y = 78
        bar_w = 240
        bar_h = 10
        pygame.draw.rect(screen, (40, 40, 48), (bar_x, bar_y, bar_w, bar_h), border_radius=5)
        p1 = min(1.0, score[0] / win_points) if win_points else 0
        p2 = min(1.0, score[1] / win_points) if win_points else 0
        pygame.draw.rect(screen, TEAM_1_COLOR, (bar_x, bar_y, int(bar_w * p1), bar_h), border_radius=5)
        pygame.draw.rect(screen, TEAM_2_COLOR, (bar_x + int(bar_w * p2), bar_y, int(bar_w * (1 - p2)), bar_h), border_radius=5)
        goal_txt = font_sm.render(f"Vitoria em {win_points} pts", True, (220, 220, 220))
        screen.blit(goal_txt, (world_width // 2 - goal_txt.get_width() // 2, 92))

        # SPEC-04: indicador de latencia no HUD
        rtt = self.net.last_rtt
        if rtt is not None:
            ping_color = (80, 255, 120) if rtt <= PING_GREEN_MS else ((255, 220, 80) if rtt <= PING_YELLOW_MS else (255, 80, 80))
            ping_txt = font_sm.render(f"Ping: {rtt:.0f}ms", True, ping_color)
            screen.blit(ping_txt, (world_width // 2 - ping_txt.get_width() // 2, 108))



        for p_id, p_data in self.server_data["players"].items():
            if p_data["char"] is None:
                continue

            # SPEC-03: suaviza movimento em rede via lerp
            target_x = p_data["x"]
            target_y = p_data["y"]
            prev = self._interp.get(p_id, [target_x, target_y])
            prev[0] += (target_x - prev[0]) * INTERP_FACTOR
            prev[1] += (target_y - prev[1]) * INTERP_FACTOR
            self._interp[p_id] = prev
            p_data["x"] = prev[0]
            p_data["y"] = prev[1]


            if p_data["char"] == "Bola":
                continue

            is_invisible = p_data.get("invisible_timer", 0) > 0

            if is_invisible and p_data["team"] != self.my_team and not am_i_jackpot:
                continue

            color = TEAM_1_COLOR if p_data["team"] == 1 else TEAM_2_COLOR

            if p_data.get("clone_timer", 0) > 0:
                clone_x = p_data.get("clone_x", p_data["x"] - p_data.get("facing", 1) * 75)
                clone_y = p_data.get("clone_y", p_data["y"])

                clone_img = self.tinted_small_images.get((p_data["char"], p_data["team"]))

                if clone_img:
                    clone_surface = clone_img.copy()
                    clone_surface.set_alpha(150)
                    screen.blit(clone_surface, (clone_x, clone_y))
                else:
                    clone_color = (
                        max(0, color[0] - 120),
                        max(0, color[1] - 120),
                        max(0, color[2] - 120)
                    )
                    clone_surface = pygame.Surface((CHAR_W, CHAR_H), pygame.SRCALPHA)
                    clone_surface.fill((*clone_color, 170))
                    screen.blit(clone_surface, (clone_x, clone_y))

                pygame.draw.rect(screen, WHITE, (clone_x, clone_y, CHAR_W, CHAR_H), 2)
                pygame.draw.circle(
                    screen,
                    (80, 80, 120),
                    (int(clone_x + CHAR_W // 2), int(clone_y + CHAR_H // 2)),
                    35,
                    2
                )

                c_tag = font_sm.render("CLONE", True, WHITE)
                screen.blit(c_tag, (clone_x + CHAR_W // 2 - c_tag.get_width() // 2, clone_y - 20))

            if p_id == self.my_id:
                pygame.draw.rect(
                    screen,
                    (255, 255, 0),
                    (p_data["x"] - 2, p_data["y"] - 2, CHAR_W + 4, CHAR_H + 4),
                    3
                )

            if p_data.get("jackpot_timer", 0) > 0:
                pulse = (math.sin(pygame.time.get_ticks() * 0.01) + 1) * 5
                pygame.draw.circle(screen, (0, 255, 100), (p_data["x"] + 15, p_data["y"] + 25), 40 + pulse, 5)

            if p_data.get("havoc_timer", 0) > 0:
                progress = 1 - p_data.get("havoc_timer", 0) / 60
                radius = int(45 + progress * 230)
                pulse = (math.sin(pygame.time.get_ticks() * 0.035) + 1) / 2
                center = (int(p_data["x"] + CHAR_W / 2), int(p_data["y"] + CHAR_H / 2))
                pygame.draw.circle(screen, (255, 70, 40), center, radius, 4)
                pygame.draw.circle(screen, (20, 20, 25), center, int(30 + pulse * 12), 3)
                havoc_txt = font_sm.render("ORDEM HAVOC", True, (255, 90, 50))
                screen.blit(havoc_txt, (p_data["x"] + 15 - havoc_txt.get_width() // 2, p_data["y"] - 110))

            if p_data.get("havoc_mark_timer", 0) > 0:
                mark_pulse = (math.sin(pygame.time.get_ticks() * 0.04) + 1) / 2
                mark_color = (255, int(60 + mark_pulse * 80), 45)
                mark_center = (int(p_data["x"] + CHAR_W / 2), int(p_data["y"] + CHAR_H / 2))
                pygame.draw.circle(screen, mark_color, mark_center, int(38 + mark_pulse * 8), 3)
                mark_txt = font_sm.render("COMANDADO", True, mark_color)
                screen.blit(mark_txt, (p_data["x"] + 15 - mark_txt.get_width() // 2, p_data["y"] - 108))

            if p_data.get("ultimate_flash_timer", 0) > 0:
                pulse = (math.sin(pygame.time.get_ticks() * 0.045) + 1) / 2
                radius = int(42 + pulse * 16)
                center = (int(p_data["x"] + CHAR_W / 2), int(p_data["y"] + CHAR_H / 2))
                pygame.draw.circle(screen, (255, 205, 45), center, radius, 5)
                pygame.draw.circle(screen, (255, 255, 180), center, int(radius * 0.58), 2)
                ult_txt = font_sm.render("SUPREMO!", True, (255, 230, 80))
                screen.blit(ult_txt, (p_data["x"] + 15 - ult_txt.get_width() // 2, p_data["y"] - 125))

            self.draw_player_image(p_data, color)

            # Indicador de posse da bola
            if self.server_data.get("ball", {}).get("holder") == p_id:
                bx = int(p_data["x"] + CHAR_W / 2)
                by = int(p_data["y"] - 18)
                pygame.draw.polygon(screen, JACKPOT_COLOR, [(bx, by - 12), (bx - 8, by), (bx + 8, by)])

            if p_data.get("char") == "Caique":
                rage = min(100, float(p_data.get("caique_rage", 0)))
                rage_factor = rage / 100

                if rage > 0:
                    rage_surface = pygame.Surface((CHAR_W + 10, CHAR_H + 10), pygame.SRCALPHA)
                    rage_surface.fill((255, 30, 20, int(35 + rage_factor * 115)))
                    screen.blit(rage_surface, (p_data["x"] - 5, p_data["y"] - 5))
                    pygame.draw.circle(screen, (255, 60, 35), (p_data["x"] + 15, p_data["y"] + 25), int(24 + rage_factor * 22), 2)

                if rage >= 20:
                    smoke_count = 1 + int(rage_factor * 5)
                    ticks = pygame.time.get_ticks()

                    for s in range(smoke_count):
                        smoke_x = int(p_data["x"] + 15 + math.sin(ticks / 180 + s) * (5 + s * 2))
                        smoke_y = int(p_data["y"] - 8 - s * 8 - (ticks // 90 + s * 7) % 10)
                        smoke_radius = max(3, int(4 + rage_factor * 6 - s * 0.4))
                        pygame.draw.circle(screen, (80, 80, 80), (smoke_x, smoke_y), smoke_radius)

                if p_data.get("caique_shout_timer", 0) > 0:
                    shout_progress = 1 - p_data.get("caique_shout_timer", 0) / 45
                    radius = int(45 + shout_progress * 330)
                    pygame.draw.circle(screen, (255, 70, 35), (int(p_data["x"] + 15), int(p_data["y"] + 25)), radius, 5)

            if p_data.get("ear_timer", 0) > 0:
                pygame.draw.rect(screen, (255, 200, 150), (p_data["x"] - 32, p_data["y"] + 5, 32, CHAR_H - 10))
                pygame.draw.rect(screen, (255, 200, 150), (p_data["x"] + CHAR_W, p_data["y"] + 5, 32, CHAR_H - 10))

                pygame.draw.rect(screen, BLACK, (p_data["x"] - 32, p_data["y"] + 5, 32, CHAR_H - 10), 2)
                pygame.draw.rect(screen, BLACK, (p_data["x"] + CHAR_W, p_data["y"] + 5, 32, CHAR_H - 10), 2)

            has_buff = (
                p_data.get("cookie_buff_timer", 0) > 0
                or p_data.get("jump_buff_timer", 0) > 0
                or p_data.get("throw_buff_timer", 0) > 0
                or p_data.get("dunk_buff_timer", 0) > 0
            )

            has_debuff = (
                p_data.get("jump_debuff_timer", 0) > 0
                or p_data.get("speed_debuff_timer", 0) > 0
                or p_data.get("throw_debuff_timer", 0) > 0
                or p_data.get("lag_timer", 0) > 0
            )

            if has_buff and p_data.get("jackpot_timer", 0) <= 0:
                pygame.draw.circle(screen, (50, 255, 50), (p_data["x"] + 15, p_data["y"] + 60), 20, 3)
                buff_txt = font_sm.render("BUFF!", True, (50, 255, 50))
                screen.blit(buff_txt, (p_data["x"] - 10, p_data["y"] - 45))

            if has_debuff:
                pygame.draw.circle(screen, (255, 50, 50), (p_data["x"] + 15, p_data["y"] + 60), 20, 3)
                debuff_txt = font_sm.render("DEBUFF!", True, (255, 50, 50))
                screen.blit(debuff_txt, (p_data["x"] - 15, p_data["y"] - 45))

            if p_data.get("stun_timer", 0) > 0:
                pygame.draw.circle(screen, (255, 255, 0), (p_data["x"] + 15, p_data["y"] + 25), 35, 3)
                stun_txt = font_sm.render("PARALISADO!", True, (255, 255, 0))
                screen.blit(stun_txt, (p_data["x"] + 15 - stun_txt.get_width() // 2, p_data["y"] - 65))

            if p_data.get("knockback_timer", 0) > 0:
                knock_txt = font_sm.render("EMPURRADO!", True, (255, 180, 0))
                screen.blit(knock_txt, (p_data["x"] + 15 - knock_txt.get_width() // 2, p_data["y"] - 85))

            if p_data.get("lag_timer", 0) > 0:
                lag_offset = random.randint(-3, 3)
                lag_txt = font_sm.render("LAG!", True, (255, 80, 220))
                screen.blit(lag_txt, (p_data["x"] + 15 - lag_txt.get_width() // 2 + lag_offset, p_data["y"] - 105))
                pygame.draw.rect(screen, (255, 80, 220), (p_data["x"] - 5 + lag_offset, p_data["y"] - 5, CHAR_W + 10, CHAR_H + 10), 1)

            if p_data.get("goon_timer", 0) > 0:
                goon_txt = font_md.render("Goonado", True, WHITE)
                goon_shadow = font_md.render("Goonado", True, BLACK)
                goon_x = p_data["x"] + 15 - goon_txt.get_width() // 2
                goon_y = p_data["y"] - 128
                screen.blit(goon_shadow, (goon_x + 2, goon_y + 2))
                screen.blit(goon_txt, (goon_x, goon_y))

            if p_data.get("reaction_timer", 0) > 0 and p_data.get("reaction_text"):
                reaction_txt = font_sm.render(p_data["reaction_text"], True, BLACK)
                bubble = pygame.Rect(
                    int(p_data["x"] + CHAR_W / 2 - reaction_txt.get_width() / 2 - 10),
                    int(p_data["y"] - 142),
                    reaction_txt.get_width() + 20,
                    30,
                )
                pygame.draw.rect(screen, WHITE, bubble, border_radius=10)
                pygame.draw.rect(screen, BLACK, bubble, 2, border_radius=10)
                screen.blit(reaction_txt, (bubble.x + 10, bubble.y + 5))

            if is_invisible:
                inv = font_sm.render("INVISÍVEL", True, WHITE)
                screen.blit(inv, (p_data["x"] - 20, p_data["y"] - 45))

            name_tag = font_sm.render(p_data["char"], True, WHITE)
            screen.blit(name_tag, (p_data["x"] + 15 - name_tag.get_width() // 2, p_data["y"] - 25))

            p_r_state = p_data.get("roleta_state", "IDLE")

            if p_r_state == "SPINNING":
                box_color = (random.randint(100, 255), random.randint(100, 255), 0)
                pygame.draw.rect(screen, box_color, (p_data["x"] - 25, p_data["y"] - 60, 80, 25), border_radius=5)

                spin_txt = font_sm.render("ROLETA", True, BLACK)
                screen.blit(spin_txt, (p_data["x"] + 15 - spin_txt.get_width() // 2, p_data["y"] - 58))

            elif p_r_state == "FINISHED":
                outcome = p_data.get("roleta_result", "")

                if outcome:
                    if "JACKPOT" in outcome:
                        res_color = (255, 215, 0)
                    elif "BUFF" in outcome:
                        res_color = (50, 255, 50)
                    else:
                        res_color = (255, 50, 50)

                    res_txt = font_sm.render(outcome.replace("_", " "), True, res_color)
                    screen.blit(res_txt, (p_data["x"] + 15 - res_txt.get_width() // 2, p_data["y"] - 60))

        for npc in self.server_data.get("murilo_npcs", []):
            npc_x = int(npc.get("x", 0))
            npc_y = int(npc.get("y", 0))
            npc_team = npc.get("team", 1)
            npc_color = TEAM_1_COLOR if npc_team == 1 else TEAM_2_COLOR

            pygame.draw.circle(screen, (235, 235, 235), (npc_x + 15, npc_y + 14), 12)
            pygame.draw.line(screen, npc_color, (npc_x + 15, npc_y + 27), (npc_x + 15, npc_y + 48), 4)
            pygame.draw.line(screen, npc_color, (npc_x + 15, npc_y + 34), (npc_x - 4, npc_y + 24), 3)
            pygame.draw.line(screen, npc_color, (npc_x + 15, npc_y + 34), (npc_x + 34, npc_y + 24), 3)
            pygame.draw.line(screen, npc_color, (npc_x + 15, npc_y + 48), (npc_x + 3, npc_y + 64), 3)
            pygame.draw.line(screen, npc_color, (npc_x + 15, npc_y + 48), (npc_x + 27, npc_y + 64), 3)
            pygame.draw.circle(screen, BLACK, (npc_x + 11, npc_y + 12), 2)
            pygame.draw.circle(screen, BLACK, (npc_x + 19, npc_y + 12), 2)
            pygame.draw.arc(screen, BLACK, (npc_x + 9, npc_y + 12, 12, 8), 0.2, 2.9, 2)

            npc_txt = font_sm.render(npc.get("name", "Rabisco"), True, WHITE)
            screen.blit(npc_txt, (npc_x + 15 - npc_txt.get_width() // 2, npc_y - 24))

            npc_seconds = max(0, int(npc.get("timer", 0) / FPS))
            timer_txt = font_sm.render(f"{npc_seconds}s", True, (255, 230, 120))
            screen.blit(timer_txt, (npc_x + 15 - timer_txt.get_width() // 2, npc_y - 46))

        for bird in self.server_data.get("igor_birds", []):
            bird_x = int(bird.get("x", 0))
            bird_y = int(bird.get("y", 0))
            wing = int(math.sin(pygame.time.get_ticks() / 90 + bird.get("phase", 0)) * 6)

            pygame.draw.ellipse(screen, (245, 225, 105), (bird_x - 12, bird_y - 8, 24, 16))
            pygame.draw.circle(screen, (245, 225, 105), (bird_x + 10, bird_y - 4), 8)
            pygame.draw.polygon(screen, (255, 150, 60), [(bird_x + 18, bird_y - 4), (bird_x + 27, bird_y), (bird_x + 18, bird_y + 4)])
            pygame.draw.circle(screen, BLACK, (bird_x + 12, bird_y - 6), 2)
            pygame.draw.polygon(screen, (245, 245, 170), [(bird_x - 2, bird_y - 5), (bird_x - 22, bird_y - 18 - wing), (bird_x - 10, bird_y + 2)])
            pygame.draw.polygon(screen, (245, 245, 170), [(bird_x - 2, bird_y + 5), (bird_x - 22, bird_y + 18 + wing), (bird_x - 10, bird_y - 2)])

        ball = self.server_data["ball"]

        pygame.draw.circle(screen, BALL_COLOR, (int(ball["x"]), int(ball["y"])), BALL_RAD)

        # SPEC-03: suaviza a bola em rede
        btx, bty = ball["x"], ball["y"]
        if self._ball_interp[0] is None:
            self._ball_interp = [btx, bty]
        self._ball_interp[0] += (btx - self._ball_interp[0]) * INTERP_FACTOR
        self._ball_interp[1] += (bty - self._ball_interp[1]) * INTERP_FACTOR
        ball["x"] = self._ball_interp[0]
        ball["y"] = self._ball_interp[1]

        pygame.draw.circle(screen, BLACK, (int(ball["x"]), int(ball["y"])), BALL_RAD, 2)

        if ball.get("holder") == self.my_id and r_state != "CUTSCENE":
            mx, my = pygame.mouse.get_pos()

            if my_p_data.get("throw_buff_timer", 0) > 0:
                path = predict_ball_path(ball, mx, my, get_throw_power(my_p_data), world_width=world_width)

                if len(path) > 1:
                    pygame.draw.lines(screen, (255, 220, 40), False, path, 3)

                    for point in path[::12]:
                        pygame.draw.circle(screen, (255, 245, 160), point, 3)
            else:
                pygame.draw.line(screen, WHITE, (self.player_x + 15, self.player_y + 15), (mx, my), 2)

            pygame.draw.circle(screen, (255, 0, 0), (mx, my), 5)

            if can_start_dunk_locally(my_p_data, ball):
                dunk_label = "DUNK FACIL: aperte F" if my_p_data.get("dunk_buff_timer", 0) > 0 else "DUNK: aperte F perto da cesta"
                dunk_txt = font_md.render(dunk_label, True, (255, 230, 80))
                screen.blit(dunk_txt, (WIDTH // 2 - dunk_txt.get_width() // 2, HEIGHT - 105))

        if my_p_data.get("dunk_active", 0) > 0:
            sequence = my_p_data.get("dunk_sequence", [])
            index = my_p_data.get("dunk_index", 0)
            timer = max(0, my_p_data.get("dunk_timer", 0))

            pygame.draw.rect(screen, BLACK, (WIDTH // 2 - 310, 105, 620, 115), border_radius=14)
            qte_title = "DUNK QTE - BUFF FACIL" if my_p_data.get("dunk_buff_timer", 0) > 0 else "DUNK QTE"
            title = font_md.render(qte_title, True, (255, 230, 80))
            screen.blit(title, (WIDTH // 2 - title.get_width() // 2, 115))

            x = WIDTH // 2 - len(sequence) * 32

            for i, key in enumerate(sequence):
                color = (70, 255, 120) if i < index else WHITE
                box_color = (40, 90, 50) if i < index else (70, 70, 70)
                rect = pygame.Rect(x + i * 64, 160, 48, 42)
                pygame.draw.rect(screen, box_color, rect, border_radius=8)
                pygame.draw.rect(screen, color, rect, 2, border_radius=8)
                key_txt = font_md.render(key, True, color)
                screen.blit(key_txt, (rect.centerx - key_txt.get_width() // 2, rect.centery - key_txt.get_height() // 2))

            time_txt = font_sm.render(f"Tempo: {timer / FPS:.1f}s", True, WHITE)
            screen.blit(time_txt, (WIDTH // 2 - time_txt.get_width() // 2, 205))

        if my_p_data.get("clash_active", 0) > 0:
            sequence = my_p_data.get("clash_sequence", [])
            index = my_p_data.get("clash_index", 0)
            timer = max(0, my_p_data.get("clash_timer", 0))

            pygame.draw.rect(screen, BLACK, (WIDTH // 2 - 340, 235, 680, 120), border_radius=14)
            title = font_md.render("CLASH DE HABILIDADES", True, (120, 220, 255))
            screen.blit(title, (WIDTH // 2 - title.get_width() // 2, 245))

            x = WIDTH // 2 - len(sequence) * 32

            for i, key in enumerate(sequence):
                color = (80, 220, 255) if i < index else WHITE
                box_color = (30, 70, 90) if i < index else (70, 70, 70)
                rect = pygame.Rect(x + i * 64, 290, 48, 42)
                pygame.draw.rect(screen, box_color, rect, border_radius=8)
                pygame.draw.rect(screen, color, rect, 2, border_radius=8)
                key_txt = font_md.render(key, True, color)
                screen.blit(key_txt, (rect.centerx - key_txt.get_width() // 2, rect.centery - key_txt.get_height() // 2))

            time_txt = font_sm.render(f"Tempo: {timer / FPS:.1f}s", True, WHITE)
            screen.blit(time_txt, (WIDTH // 2 - time_txt.get_width() // 2, 335))

        if self.trainer_ability_selecting and my_p_data.get("char") == "Treinador":
            panel = pygame.Rect(WIDTH // 2 - 360, HEIGHT // 2 - 150, 720, 300)
            pygame.draw.rect(screen, (10, 16, 26), panel, border_radius=18)
            pygame.draw.rect(screen, (80, 170, 220), panel, 3, border_radius=18)

            title = font_md.render("TREINADOR: COPIAR HABILIDADE", True, (120, 220, 255))
            screen.blit(title, (panel.centerx - title.get_width() // 2, panel.y + 22))

            hint = font_sm.render("Aperte 1-8 para escolher, ou ESC para cancelar.", True, WHITE)
            screen.blit(hint, (panel.centerx - hint.get_width() // 2, panel.y + 62))

            for i, copied_char in enumerate(TRAINER_COPY_CHARACTERS):
                col = i % 2
                row = i // 2
                x = panel.x + 70 + col * 320
                y = panel.y + 110 + row * 42
                color = CHARACTERS_INFO[copied_char]["color"]
                option = font_sm.render(f"{i + 1} - {copied_char}", True, color)
                screen.blit(option, (x, y))

        if my_p_data.get("char") == "Havoc":
            self.draw_havoc_selection(my_p_data)

            if my_p_data.get("ability_cd", self.ability_cooldown) <= 0 and not self.havoc_selecting_target:
                hint = font_sm.render("Havoc: E abre a ordem. Escolha inimigo e comando.", True, (255, 120, 75))
                screen.blit(hint, (20, HEIGHT - 82))

        if my_p_data.get("char") == "Bola":
            if self.bola_aiming and self.server_data.get("ball", {}).get("holder") is None:
                mx, my = pygame.mouse.get_pos()
                ball = self.server_data["ball"]
                pygame.draw.line(screen, WHITE, (int(ball["x"]), int(ball["y"])), (mx, my), 2)
                pygame.draw.circle(screen, (255, 60, 40), (mx, my), 6)
                hint = font_sm.render("Bola: clique para se auto arremessar. ESC cancela.", True, (255, 180, 80))
            else:
                hint = font_sm.render("Bola: aperte E para mirar o auto arremesso.", True, (255, 180, 80))

            screen.blit(hint, (20, HEIGHT - 82))

        if my_p_data.get("char") == "Murilo":
            if len(self.murilo_draw_points) > 1:
                pygame.draw.lines(screen, (120, 255, 150), False, self.murilo_draw_points, 6)

                for point in self.murilo_draw_points[::10]:
                    pygame.draw.circle(screen, (230, 255, 230), point, 4)

            if my_p_data.get("ability_cd", self.ability_cooldown) <= 0:
                hint = font_sm.render(
                    "Murilo: segure BOTAO DIREITO para desenhar. E confirma. C limpa.",
                    True,
                    (180, 255, 190)
                )
                screen.blit(hint, (20, HEIGHT - 82))

                commands_1 = font_sm.render(
                    "Desenhos: linha = forca, cima = pulo, baixo = puxar bola, V = dunk, circulo = atordoar.",
                    True,
                    (180, 220, 180)
                )
                screen.blit(commands_1, (20, HEIGHT - 58))

                commands_2 = font_sm.render(
                    "Quadrado = invoca NPC, raio = turbo, sorriso = limpa debuffs, rabisco = bagunca inimigos.",
                    True,
                    (180, 220, 180)
                )
                screen.blit(commands_2, (20, HEIGHT - 34))

            if self.murilo_message_timer > 0:
                msg = font_sm.render(self.murilo_message, True, (255, 230, 120))
                screen.blit(msg, (20, HEIGHT - 112))

        if my_p_data.get("char") == "Caique":
            rage = min(100, float(my_p_data.get("caique_rage", 0)))
            rage_txt = font_sm.render(f"Raiva: {int(rage)}% | E: gritao com 10%+", True, (255, 120, 90))
            screen.blit(rage_txt, (20, HEIGHT - 82))

        if my_p_data.get("lag_timer", 0) > 0:
            glitch = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            glitch.fill((80, 0, 80, 28))

            for _ in range(12):
                y = random.randint(0, HEIGHT - 8)
                h = random.randint(2, 10)
                x_shift = random.randint(-35, 35)
                color = random.choice([(255, 0, 180, 70), (0, 220, 255, 65), (255, 255, 255, 35)])
                pygame.draw.rect(glitch, color, (max(0, x_shift), y, WIDTH, h))

            for _ in range(5):
                y = random.randint(0, HEIGHT - 45)
                h = random.randint(16, 42)
                slice_surface = screen.subsurface((0, y, WIDTH, h)).copy()
                screen.blit(slice_surface, (random.randint(-22, 22), y))

            screen.blit(glitch, (0, 0))
            lag_warning = font_lg.render("LAG", True, (255, 80, 220))
            screen.blit(lag_warning, (WIDTH // 2 - lag_warning.get_width() // 2 + random.randint(-8, 8), 95 + random.randint(-5, 5)))

        if my_p_data.get("goon_timer", 0) > 0:
            stain = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            ticks = pygame.time.get_ticks()
            center_x = WIDTH // 2 + int(math.sin(ticks / 220) * 18)
            center_y = HEIGHT // 2 + int(math.cos(ticks / 260) * 12)

            pygame.draw.ellipse(stain, (255, 255, 255, 255), (center_x - 500, center_y - 310, 1000, 620))
            pygame.draw.ellipse(stain, (255, 255, 255, 255), (center_x - 680, center_y - 220, 520, 390))
            pygame.draw.ellipse(stain, (255, 255, 255, 255), (center_x + 110, center_y - 200, 500, 380))
            pygame.draw.circle(stain, (255, 255, 255, 255), (center_x - 285, center_y + 210), 190)
            pygame.draw.circle(stain, (255, 255, 255, 255), (center_x + 315, center_y + 195), 175)
            pygame.draw.circle(stain, (255, 255, 255, 255), (center_x, center_y - 270), 205)
            pygame.draw.ellipse(stain, (255, 255, 255, 255), (center_x - 630, center_y + 90, 1260, 430))
            pygame.draw.circle(stain, (255, 255, 255, 255), (center_x, center_y + 285), 260)

            clear_hole = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            pygame.draw.circle(clear_hole, (0, 0, 0, 120), (center_x - 35, center_y - 10), 38)
            stain.blit(clear_hole, (0, 0), special_flags=pygame.BLEND_RGBA_SUB)
            screen.blit(stain, (0, 0))

        server_cd = my_p_data.get("ability_cd", self.ability_cooldown)

        if server_cd > 0:
            cd_txt = font_md.render(f"Poder: {server_cd // 60}s", True, (255, 50, 50))
            screen.blit(cd_txt, (20, HEIGHT - 50))
        else:
            cd_txt = font_md.render("Poder: PRONTO (Aperte E)", True, (50, 255, 50))
            screen.blit(cd_txt, (20, HEIGHT - 50))

        ultimate_cost = ULTIMATE_COSTS.get(my_p_data.get("char"), ULTIMATE_MAX)
        ult_charge = min(ultimate_cost, float(my_p_data.get("ultimate_charge", 0)))
        ult_x = world_width - 290
        ult_y = HEIGHT - 52
        ult_w = 250
        ult_h = 18
        pygame.draw.rect(screen, (22, 22, 28), (ult_x, ult_y, ult_w, ult_h), border_radius=8)
        pygame.draw.rect(
            screen,
            (255, 190, 45),
            (ult_x, ult_y, int(ult_w * (ult_charge / ultimate_cost)), ult_h),
            border_radius=8
        )
        pygame.draw.rect(screen, (255, 235, 135), (ult_x, ult_y, ult_w, ult_h), 2, border_radius=8)

        if ult_charge >= ultimate_cost:
            ult_label = "SUPREMO PRONTO (Q)"
            ult_color = (255, 235, 120)
        else:
            ult_label = f"Supremo: {int(ult_charge)}/{ultimate_cost}"
            ult_color = (230, 210, 160)

        ult_txt = font_sm.render(ult_label, True, ult_color)
        screen.blit(ult_txt, (ult_x + ult_w // 2 - ult_txt.get_width() // 2, ult_y - 23))

        # SPEC-05: placar persistente - ultimas partidas registradas localmente
        recent = save_db.get_recent_matches(5)
        if recent:
            hy = HEIGHT - 150
            panel = pygame.Rect(20, hy, 360, 130)
            pygame.draw.rect(screen, (18, 22, 32), panel, border_radius=10)
            pygame.draw.rect(screen, (90, 90, 120), panel, 2, border_radius=10)
            hdr = font_sm.render("ULTIMAS PARTIDAS", True, (200, 200, 230))
            screen.blit(hdr, (panel.x + 12, hy + 8))
            for idx, m in enumerate(recent):
                wt = m.get("winner_team")
                wname = "AZUL" if wt == 1 else ("VERM" if wt == 2 else "-?")
                line = font_sm.render(
                    f'{idx+1}. {wname} {m["score_team1"]}x{m["score_team2"]}',
                    True, (220, 220, 220),
                )
                screen.blit(line, (panel.x + 12, hy + 32 + idx * 19))

        self.btn_leave_match.draw(screen)
        self.draw_reaction_wheel()

    def handle_connection(self, response):
        if response and response[0] == "SUCCESS":
            self.room_code = response[1]
            self.my_id = response[2]
            self.my_team = response[3]
            self.is_host = self.my_id == 1
            self.error_msg = ""

            joined_started_match = False
            forced_char = None

            if len(response) >= 5:
                joined_started_match = response[4]

            if len(response) >= 6:
                forced_char = response[5]

            # SPEC-01: salva token de reconexao para rejoin posterior
            if len(response) >= 7 and response[6]:
                self.conn_token = response[6]
                save_db.save_conn_token(self.room_code, response[6])


            if forced_char in CHARACTERS:
                self.selected_char_idx = CHARACTERS.index(forced_char)

            if joined_started_match:
                self.state = "PLAYING"
                self.player_x = 200 if self.my_team == 1 else WIDTH - 250
                self.player_y = GROUND_Y - CHAR_H
                self.vel_y = 0
                self.is_jumping = False
            else:
                self.state = "LOBBY"

        else:
            self.error_msg = response[1] if response else "Erro de conexão."

    def _validate_room(self, room):
        """SPEC-02: valida frame_id (ordem) e crc32 (integridade) do estado.
        Em caso de pacote antigo ou corrompido, mantem o estado anterior."""
        if not isinstance(room, dict):
            return None
        fid = room.get("frame_id", 0)
        if fid < self._last_frame_id:
            return self.server_data
        crc = room.get("crc")
        if crc is not None:
            payload = dict(room)
            payload.pop("crc", None)
            calc = zlib.crc32(pickle.dumps(payload, protocol=pickle.HIGHEST_PROTOCOL)) & 0xffffffff
            if calc != crc:
                self._desync_count += 1
                print(f"[DESSINC] crc invalido recv={crc} calc={calc}")
                return self.server_data
        self._last_frame_id = fid
        return room

    def run(self):
        running = True

        while running:
            clock.tick(FPS)
            if self.state != "PLAYING":
                self.ensure_window_width(WIDTH)

            mouse_pos = pygame.mouse.get_pos()
            data_to_send = {}

            # SPEC-04: mede ping periodicamente (nao bloqueia o jogo)
            self._ping_counter = (self._ping_counter + 1) % 30
            if self._ping_counter == 0 and self.net.connected:
                self.net.ping()


            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False

                    if self.net.connected:
                        self.net.disconnect()

                    self.stop_local_server()

                if self.state == "PLAYING" and self.server_data:
                    if self.my_id not in self.server_data["players"]:
                        continue

                    my_p = self.server_data["players"][self.my_id]

                    if my_p.get("char") != "Havoc" and self.havoc_selecting_target:
                        self.clear_havoc_selection()

                    if my_p.get("char") != "Bola" and self.bola_aiming:
                        self.bola_aiming = False

                    if self.reaction_wheel_open:
                        if event.type == pygame.KEYDOWN and event.key in (pygame.K_ESCAPE, pygame.K_r):
                            self.reaction_wheel_open = False
                            continue

                        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                            for rect, reaction in self.reaction_rects:
                                if rect.collidepoint(mouse_pos):
                                    data_to_send["action"] = "REACTION"
                                    data_to_send["reaction"] = reaction
                                    self.reaction_wheel_open = False
                                    break
                            else:
                                self.reaction_wheel_open = False

                            continue

                        if event.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN):
                            continue

                    if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                        if self.btn_leave_match.is_clicked(mouse_pos):
                            self.leave_match_to_menu()
                            continue

                        if self.replay_playing and self.btn_skip_replay.is_clicked(mouse_pos):
                            self.skip_replay_requested = True
                            if self.current_goal_sound:
                                self.current_goal_sound.stop()
                                self.current_goal_sound = None
                            data_to_send["action"] = "SKIP_REPLAY"
                            continue

                    if self.replay_playing:
                        self.trainer_ability_selecting = False
                        self.clear_havoc_selection()
                        self.bola_aiming = False
                        self.clear_murilo_drawing()
                        continue

                    if my_p.get("roleta_state") == "CUTSCENE":
                        self.trainer_ability_selecting = False
                        self.clear_havoc_selection()
                        self.bola_aiming = False
                        self.clear_murilo_drawing()
                        continue

                    if self.bola_aiming and my_p.get("char") == "Bola":
                        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                            self.bola_aiming = False
                            continue

                        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                            data_to_send["action"] = "BOLA_THROW"
                            data_to_send["target_x"] = mouse_pos[0]
                            data_to_send["target_y"] = mouse_pos[1]
                            self.bola_aiming = False
                            self.ability_cooldown = 240
                            continue

                        if event.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN):
                            continue

                    if self.havoc_selecting_target and my_p.get("char") == "Havoc":
                        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                            self.clear_havoc_selection()
                            continue

                        if event.type == pygame.KEYDOWN and self.havoc_selected_target_id is not None:
                            key_to_command = {
                                pygame.K_1: "deliver",
                                pygame.K_KP1: "deliver",
                                pygame.K_2: "freeze",
                                pygame.K_KP2: "freeze",
                                pygame.K_3: "retreat",
                                pygame.K_KP3: "retreat",
                            }
                            command = key_to_command.get(event.key)

                            if command:
                                payload = self.send_havoc_command_payload(command)

                                if payload:
                                    data_to_send.update(payload)
                                    self.ability_cooldown = 540

                                self.clear_havoc_selection()
                                continue

                        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                            if self.havoc_selected_target_id is not None:
                                for rect, command in self.havoc_command_rects:
                                    if rect.collidepoint(mouse_pos):
                                        payload = self.send_havoc_command_payload(command)

                                        if payload:
                                            data_to_send.update(payload)
                                            self.ability_cooldown = 540

                                        self.clear_havoc_selection()
                                        break
                                else:
                                    clicked_target = self.get_havoc_enemy_at_pos(mouse_pos, my_p)

                                    if clicked_target is not None:
                                        self.havoc_selected_target_id = clicked_target

                                continue

                            clicked_target = self.get_havoc_enemy_at_pos(mouse_pos, my_p)

                            if clicked_target is not None:
                                self.havoc_selected_target_id = clicked_target

                            continue

                        if event.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN):
                            continue

                    if my_p.get("char") == "Murilo":
                        server_cd = my_p.get("ability_cd", self.ability_cooldown)
                        can_draw = (
                            server_cd <= 0
                            and my_p.get("stun_timer", 0) <= 0
                            and my_p.get("clash_active", 0) <= 0
                            and my_p.get("dunk_active", 0) <= 0
                        )

                        if can_draw and event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
                            self.murilo_drawing = True
                            self.add_murilo_draw_point(mouse_pos)
                            continue

                        if event.type == pygame.MOUSEMOTION and self.murilo_drawing:
                            self.add_murilo_draw_point(mouse_pos)
                            continue

                        if event.type == pygame.MOUSEBUTTONUP and event.button == 3 and self.murilo_drawing:
                            self.add_murilo_draw_point(mouse_pos)
                            self.murilo_drawing = False
                            continue

                        if event.type == pygame.KEYDOWN and event.key == pygame.K_c:
                            self.clear_murilo_drawing("Desenho limpo.")
                            continue

                    if self.trainer_ability_selecting and event.type == pygame.KEYDOWN:
                        copied_char = trainer_copy_character_from_key(event.key)

                        if event.key == pygame.K_ESCAPE:
                            self.trainer_ability_selecting = False
                            continue

                        if copied_char:
                            data_to_send["action"] = "USE_ABILITY"
                            data_to_send["facing"] = self.facing
                            data_to_send["copied_ability"] = copied_char
                            self.trainer_ability_selecting = False

                            if copied_char in ["Diogo", "Paulo"]:
                                self.ability_cooldown = 480
                            else:
                                self.ability_cooldown = 360

                            continue

                    if event.type == pygame.KEYDOWN and my_p.get("clash_active", 0) > 0:
                        qte_key = qte_key_from_event(event)

                        if qte_key:
                            data_to_send["action"] = "CLASH_QTE_KEY"
                            data_to_send["key"] = qte_key
                            continue

                    if event.type == pygame.KEYDOWN and event.key == pygame.K_q:
                        ultimate_cost = ULTIMATE_COSTS.get(my_p.get("char"), ULTIMATE_MAX)
                        if (
                            float(my_p.get("ultimate_charge", 0)) >= ultimate_cost
                            and my_p.get("stun_timer", 0) <= 0
                            and my_p.get("clash_active", 0) <= 0
                            and my_p.get("dunk_active", 0) <= 0
                        ):
                            data_to_send["action"] = "ULTIMATE"
                            self.trainer_ability_selecting = False
                            self.clear_havoc_selection()
                            self.bola_aiming = False
                            self.clear_murilo_drawing()
                            continue

                    if event.type == pygame.KEYDOWN and event.key == pygame.K_r:
                        self.reaction_wheel_open = True
                        continue

                    if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                        if (
                            self.server_data.get("ball", {}).get("holder") == self.my_id
                            and my_p.get("dunk_active", 0) <= 0
                            and my_p.get("clash_active", 0) <= 0
                        ):
                            data_to_send["action"] = "THROW"
                            data_to_send["target_x"] = mouse_pos[0]
                            data_to_send["target_y"] = mouse_pos[1]

                    if event.type == pygame.KEYDOWN and my_p.get("dunk_active", 0) > 0:
                        qte_key = qte_key_from_event(event)

                        if qte_key:
                            data_to_send["action"] = "DUNK_QTE_KEY"
                            data_to_send["key"] = qte_key
                            continue

                    if event.type == pygame.KEYDOWN and event.key == pygame.K_f:
                        ball = self.server_data.get("ball", {})

                        if (
                            ball.get("holder") == self.my_id
                            and my_p.get("clash_active", 0) <= 0
                            and can_start_dunk_locally(my_p, ball)
                        ):
                            data_to_send["action"] = "DUNK_START"
                            continue

                    if event.type == pygame.KEYDOWN and event.key == pygame.K_e:
                        server_cd = my_p.get("ability_cd", self.ability_cooldown)

                        if server_cd <= 0 and my_p.get("stun_timer", 0) <= 0 and my_p.get("clash_active", 0) <= 0:
                            if my_p.get("char") == "Murilo":
                                payload = self.build_murilo_ability_payload()

                                if payload:
                                    data_to_send.update(payload)

                                continue

                            if my_p.get("char") == "Treinador":
                                self.trainer_ability_selecting = True
                                continue

                            if my_p.get("char") == "Havoc":
                                self.havoc_selecting_target = True
                                self.havoc_selected_target_id = None
                                self.havoc_command_rects = []
                                continue

                            if my_p.get("char") == "Bola":
                                ball = self.server_data.get("ball", {})

                                if ball.get("holder") is None and ball.get("bola_throw_timer", 0) <= 0:
                                    self.bola_aiming = True

                                continue

                            data_to_send["action"] = "USE_ABILITY"
                            data_to_send["facing"] = self.facing
                            ability_achievement = ABILITY_ACHIEVEMENTS.get(my_p.get("char"))

                            if ability_achievement:
                                unlocked_before = self.get_unlocked_achievement_ids()
                                save_db.unlock_character_achievement(my_p["char"], ability_achievement)
                                self.enqueue_new_achievement_notifications(unlocked_before)

                            if CHARACTERS[self.selected_char_idx] in ["Diogo", "Paulo"]:
                                self.ability_cooldown = 480
                            elif CHARACTERS[self.selected_char_idx] == "Igor":
                                self.ability_cooldown = 420
                            elif CHARACTERS[self.selected_char_idx] == "Laiz":
                                self.ability_cooldown = 480
                            elif CHARACTERS[self.selected_char_idx] == "Kauã":
                                self.ability_cooldown = 480
                            elif CHARACTERS[self.selected_char_idx] == "Caique":
                                if float(my_p.get("caique_rage", 0)) >= 10:
                                    self.ability_cooldown = 360
                                else:
                                    self.ability_cooldown = 0
                            elif CHARACTERS[self.selected_char_idx] == "João Roberto":
                                self.ability_cooldown = 420
                            else:
                                self.ability_cooldown = 360

                elif self.state == "MENU":
                    if event.type == pygame.KEYDOWN:
                        if self.admin_password_open:
                            if event.key == pygame.K_ESCAPE:
                                self.admin_password_open = False
                                self.admin_password = ""
                                continue

                            if event.key == pygame.K_RETURN or event.key == pygame.K_KP_ENTER:
                                if self.admin_password == "Rafael@1":
                                    save_db.admin_unlock_everything()
                                    self.admin_message = "Admin liberado: historia, conquistas e dinheiro desbloqueados."
                                    self.admin_message_timer = 240
                                else:
                                    self.admin_message = "Senha admin incorreta."
                                    self.admin_message_timer = 180

                                self.admin_password_open = False
                                self.admin_password = ""
                                continue

                            if event.key == pygame.K_BACKSPACE:
                                self.admin_password = self.admin_password[:-1]
                                continue

                            if event.unicode and event.unicode.isprintable() and len(self.admin_password) < 32:
                                self.admin_password += event.unicode

                            continue

                        ctrl_pressed = pygame.key.get_mods() & pygame.KMOD_CTRL

                        if ctrl_pressed and event.key == pygame.K_v:
                            pasted_text = get_clipboard_text()

                            if self.active_input == "host":
                                allowed_chars = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ.-:"
                                clean_text = "".join(ch for ch in pasted_text if ch in allowed_chars)
                                self.host_ip = clean_text[:40]

                            elif self.active_input == "room":
                                clean_text = "".join(ch for ch in pasted_text.upper() if ch.isalnum())
                                self.room_code = clean_text[:4]

                        elif ctrl_pressed and event.key == pygame.K_c:
                            if self.active_input == "host":
                                set_clipboard_text(self.host_ip)

                            elif self.active_input == "room":
                                set_clipboard_text(self.room_code)

                        elif ctrl_pressed and event.key == pygame.K_a:
                            if self.active_input == "host":
                                self.host_ip = ""

                            elif self.active_input == "room":
                                self.room_code = ""

                        else:
                            if self.active_input == "room":
                                if event.key == pygame.K_BACKSPACE:
                                    self.room_code = self.room_code[:-1]

                                elif len(self.room_code) < 4 and event.unicode.isalnum():
                                    self.room_code += event.unicode.upper()

                            elif self.active_input == "host":
                                if event.key == pygame.K_BACKSPACE:
                                    self.host_ip = self.host_ip[:-1]

                                elif len(self.host_ip) < 40:
                                    allowed_chars = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ.-:"
                                    if event.unicode in allowed_chars:
                                        self.host_ip += event.unicode

                            if event.key == pygame.K_TAB:
                                self.active_input = "host" if self.active_input == "room" else "room"

                        if event.unicode and event.unicode.isalpha():
                            self.admin_code_buffer = (self.admin_code_buffer + event.unicode.lower())[-5:]

                            if self.admin_code_buffer == "admin":
                                self.admin_password_open = True
                                self.admin_password = ""
                                self.admin_code_buffer = ""
                                if self.active_input == "room":
                                    self.room_code = ""
                                elif self.active_input == "host" and self.host_ip.lower().endswith("admin"):
                                    self.host_ip = self.host_ip[:-5]
                                self.error_msg = ""
                        elif event.key not in (pygame.K_LSHIFT, pygame.K_RSHIFT, pygame.K_TAB):
                            self.admin_code_buffer = ""

                    if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                        if self.host_ip_rect.collidepoint(mouse_pos):
                            self.active_input = "host"

                        elif self.room_code_rect.collidepoint(mouse_pos):
                            self.active_input = "room"

                        elif self.btn_create.is_clicked(mouse_pos):
                            self.create_local_room()

                        elif self.btn_win_left.collidepoint(mouse_pos):
                            self.win_points_index = (self.win_points_index - 1) % len(WIN_POINTS_OPTIONS)

                        elif self.btn_win_right.collidepoint(mouse_pos):
                            self.win_points_index = (self.win_points_index + 1) % len(WIN_POINTS_OPTIONS)

                        elif self.btn_join.is_clicked(mouse_pos):
                            self.join_remote_room()

                        elif self.btn_story.is_clicked(mouse_pos):
                            start_story_mode_process()

                        elif self.btn_shop.is_clicked(mouse_pos):
                            if CHARACTERS[self.selected_char_idx] in SECRET_CHARACTERS:
                                self.selected_char_idx = CHARACTERS.index(PUBLIC_CHARACTERS[0])
                                self.shop_selected_skin = save_db.get_equipped_skin(CHARACTERS[self.selected_char_idx])

                            self.state = "SHOP"

                        elif self.btn_stats.is_clicked(mouse_pos):
                            self.state = "STATS"

                        elif self.btn_achievements.is_clicked(mouse_pos):
                            self.state = "ACHIEVEMENTS"

                        elif self.btn_quit_game.is_clicked(mouse_pos):
                            running = False

                            self.stop_local_server()
                elif self.state == "SHOP":
                    if event.type == pygame.MOUSEWHEEL:
                        self.shop_scroll -= event.y * 45

                    if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                        if self.btn_shop_back.is_clicked(mouse_pos):
                            self.state = "MENU"

                        elif self.btn_shop_buy.is_clicked(mouse_pos):
                            ok, msg = save_db.buy_skin(self.shop_selected_skin)
                            self.shop_message = msg

                        elif self.btn_shop_equip.is_clicked(mouse_pos):
                            char_name = CHARACTERS[self.selected_char_idx]
                            ok, msg = save_db.equip_skin(char_name, self.shop_selected_skin)
                            self.shop_message = msg

                        else:
                            for rect, char_idx in getattr(self, "shop_char_rects", []):
                                if rect.collidepoint(mouse_pos):
                                    self.selected_char_idx = char_idx
                                    self.shop_selected_skin = save_db.get_equipped_skin(CHARACTERS[self.selected_char_idx])
                                    self.shop_message = ""
                                    break

                            for rect, skin_id in getattr(self, "shop_skin_rects", []):
                                if rect.collidepoint(mouse_pos):
                                    self.shop_selected_skin = skin_id
                                    self.shop_message = ""

                elif self.state == "STATS":
                    if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                        if self.btn_stats_back.is_clicked(mouse_pos):
                            self.state = "MENU"

                elif self.state == "ACHIEVEMENTS":
                    if event.type == pygame.MOUSEWHEEL:
                        self.achievements_scroll -= event.y * 45

                    if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                        if self.btn_achievements_back.is_clicked(mouse_pos):
                            self.state = "MENU"

                elif self.state == "LOBBY":
                    if self.secret_character_select_open:
                        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                            self.secret_character_select_open = False
                            self.secret_bola_buffer = ""

                        elif event.type == pygame.KEYDOWN:
                            if event.unicode and event.unicode.isalpha():
                                self.secret_bola_buffer = (self.secret_bola_buffer + event.unicode.lower())[-4:]

                                if self.secret_bola_buffer == "bola":
                                    is_taken = False

                                    if self.server_data:
                                        for pid, p_data in self.server_data["players"].items():
                                            if pid != self.my_id and p_data["char"] == "Bola":
                                                is_taken = True

                                    if not is_taken:
                                        self.selected_char_idx = CHARACTERS.index("Bola")
                                        self.secret_character_select_open = False

                                    self.secret_bola_buffer = ""
                            else:
                                self.secret_bola_buffer = ""

                        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                            if self.btn_secret_back.is_clicked(mouse_pos):
                                self.secret_character_select_open = False
                                self.secret_bola_buffer = ""
                            else:
                                for rect, char_idx in getattr(self, "secret_char_rects", []):
                                    if rect.collidepoint(mouse_pos):
                                        char_name = CHARACTERS[char_idx]
                                        is_taken = False

                                        if self.server_data:
                                            for pid, p_data in self.server_data["players"].items():
                                                if pid != self.my_id and p_data["char"] == char_name:
                                                    is_taken = True

                                        if not is_taken:
                                            self.selected_char_idx = char_idx
                                            self.secret_character_select_open = False
                                        break

                        continue

                    if event.type == pygame.KEYDOWN:
                        self.register_secret_character_code_key(event)

                    if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                        if self.btn_leave_lobby.is_clicked(mouse_pos):
                            self.leave_match_to_menu()
                            continue

                        if self.btn_team_blue.is_clicked(mouse_pos):
                            self.my_team = 1

                        elif self.btn_team_red.is_clicked(mouse_pos):
                            self.my_team = 2

                        elif self.is_host and self.btn_add_bot.is_clicked(mouse_pos):
                            self.net.send({"action": "ADD_BOT", "bot_char": CHARACTERS[self.selected_char_idx]})
                            continue

                        elif self.is_host and self.btn_remove_bot.is_clicked(mouse_pos):
                            self.net.send({"action": "REMOVE_BOT"})
                            continue

                        for rect, char_idx in self.char_rects:
                            if rect.collidepoint(mouse_pos):
                                char_name = CHARACTERS[char_idx]
                                is_taken = False

                                if self.server_data:
                                    for pid, p_data in self.server_data["players"].items():
                                        if pid != self.my_id and p_data["char"] == char_name:
                                            is_taken = True

                                if not is_taken:
                                    self.selected_char_idx = char_idx

                        if self.is_host and self.btn_start_game.is_clicked(mouse_pos):
                            self.net.send({"action": "START_GAME"})

                elif self.state == "GAME_OVER":
                    if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                        if self.btn_exit.is_clicked(mouse_pos):
                            self.leave_match_to_menu()

            if self.state in ["LOBBY", "PLAYING"]:
                if self.state == "LOBBY":
                    if (
                        CHARACTERS[self.selected_char_idx] == "Treinador"
                        and save_db.get_unlocked_story_level() < STORY_COMPLETION_UNLOCK_LEVEL
                    ):
                        for fallback_secret in SECRET_SELECTABLE_CHARACTERS:
                            if fallback_secret != "Treinador":
                                self.selected_char_idx = CHARACTERS.index(fallback_secret)
                                break

                    data_to_send["action"] = "UPDATE_LOBBY"
                    data_to_send["char"] = CHARACTERS[self.selected_char_idx]
                    data_to_send["skin_id"] = save_db.get_equipped_skin(CHARACTERS[self.selected_char_idx])
                    data_to_send["team"] = self.my_team

                elif self.state == "PLAYING":
                    if self.server_data and self.my_id in self.server_data["players"]:
                        my_p = self.server_data["players"][self.my_id]

                        if not self.replay_playing and my_p.get("roleta_state") != "CUTSCENE":
                            char_name = CHARACTERS[self.selected_char_idx]

                            if char_name == "John Jonh":
                                self.speed = 9
                                self.jump_power = -19

                            elif char_name == "Rafael":
                                self.speed = 6
                                self.jump_power = -21

                            else:
                                self.speed = 6
                                self.jump_power = -16

                            if char_name == "Caique":
                                rage_factor = min(1.0, float(my_p.get("caique_rage", 0)) / 100)
                                self.speed += rage_factor * 5
                                self.jump_power -= rage_factor * 3

                            if my_p.get("jackpot_timer", 0) > 0:
                                self.speed += 5
                                self.jump_power -= 5

                            else:
                                if my_p.get("cookie_buff_timer", 0) > 0:
                                    self.speed += 3

                                if my_p.get("jump_buff_timer", 0) > 0:
                                    self.jump_power -= 4

                                if my_p.get("speed_debuff_timer", 0) > 0:
                                    self.speed -= 3

                                if my_p.get("jump_debuff_timer", 0) > 0:
                                    self.jump_power += 5

                            is_stunned = my_p.get("stun_timer", 0) > 0
                            is_dashing = my_p.get("dash_timer", 0) > 0
                            is_knocked = my_p.get("knockback_timer", 0) > 0
                            is_dunking = my_p.get("dunk_active", 0) > 0
                            is_clashing = my_p.get("clash_active", 0) > 0
                            ball_state = self.server_data.get("ball", {})
                            is_bola_control_locked = (
                                char_name == "Bola"
                                and (
                                    ball_state.get("holder") is not None
                                    or ball_state.get("bola_throw_timer", 0) > 0
                                )
                            )

                            if char_name == "Bola":
                                self.player_x = my_p["x"]
                                self.player_y = my_p["y"]

                            if is_dashing or is_knocked or is_stunned or is_dunking or is_clashing or is_bola_control_locked:
                                self.player_x = my_p["x"]
                                self.player_y = my_p["y"]

                            keys = pygame.key.get_pressed()

                            if not is_stunned and not is_dashing and not is_knocked and not is_dunking and not is_clashing and not is_bola_control_locked:
                                if keys[pygame.K_a]:
                                    self.player_x -= self.speed
                                    self.facing = -1

                                if keys[pygame.K_d]:
                                    self.player_x += self.speed
                                    self.facing = 1

                                world_width = int(my_p.get("world_width", self.get_world_width()))
                                self.player_x = max(0, min(self.player_x, world_width - CHAR_W))

                                if (keys[pygame.K_w] or keys[pygame.K_SPACE]) and not self.is_jumping:
                                    self.vel_y = self.jump_power
                                    self.is_jumping = True

                            if is_dunking or is_clashing:
                                self.vel_y = 0
                            else:
                                gravity = self.gravity

                                if my_p.get("john_float_timer", 0) > 0 and self.vel_y > 0:
                                    gravity *= 0.22

                                self.vel_y += gravity

                                if my_p.get("john_float_timer", 0) > 0 and self.vel_y > 0:
                                    self.vel_y = min(self.vel_y, 3.0)

                                self.player_y += self.vel_y

                                if self.player_y >= GROUND_Y - CHAR_H:
                                    self.player_y = GROUND_Y - CHAR_H
                                    self.vel_y = 0
                                    self.is_jumping = False

                            if self.ability_cooldown > 0:
                                self.ability_cooldown -= 1

                    data_to_send["x"] = self.player_x
                    data_to_send["y"] = self.player_y
                    data_to_send["facing"] = self.facing

                raw = self.net.send(data_to_send)
                if raw is not None:
                    validated = self._validate_room(raw)
                    if validated is not None:
                        self.server_data = validated


                if self.server_data:
                    self.check_replay_trigger()
                    self.update_local_achievement_events()
                    self.update_jackpot_achievement_events()

                    if self.murilo_pending_confirmation and self.my_id in self.server_data.get("players", {}):
                        murilo_data = self.server_data["players"][self.my_id]

                        if murilo_data.get("ability_cd", 0) > 0:
                            self.murilo_message = "Comando reconhecido."
                        else:
                            self.murilo_message = "Desenho invalido. Cooldown preservado."

                        self.murilo_message_timer = 150
                        self.murilo_pending_confirmation = False

                if not self.server_data:
                    self.state = "MENU"
                    self.error_msg = "Desconectado do servidor."

                else:
                    if self.server_data.get("game_over"):
                        self.apply_match_rewards_once()
                        self.state = "GAME_OVER"

                    elif self.state == "LOBBY" and self.server_data["game_started"]:
                        self.state = "PLAYING"
                        self.secret_character_select_open = False
                        self.secret_code_buffer = []
                        self.trainer_ability_selecting = False
                        self.clear_murilo_drawing()
                        self.murilo_pending_confirmation = False
                        self.seen_jackpot_players.clear()
                        self.opponent_jackpot_seen = False
                        self.last_seen_clash_id = None
                        self.last_dunk_ready_state = 0

                        my_data = self.server_data["players"][self.my_id]
                        self.player_x = my_data["x"]
                        self.player_y = my_data["y"]

                    elif self.state == "PLAYING" and self.server_data and self.my_id in self.server_data["players"]:
                        my_data = self.server_data["players"][self.my_id]

                        is_replay_active = self.server_data.get("replay_timer", 0) > 0
                        is_dashing = my_data.get("dash_timer", 0) > 0
                        is_knocked = my_data.get("knockback_timer", 0) > 0
                        is_stunned = my_data.get("stun_timer", 0) > 0
                        is_dunking = my_data.get("dunk_active", 0) > 0
                        is_clashing = my_data.get("clash_active", 0) > 0
                        has_ball = self.server_data["ball"].get("holder") == self.my_id

                        if is_replay_active or is_dashing or is_knocked or is_stunned or is_dunking or is_clashing or has_ball:
                            self.player_x = my_data["x"]
                            self.player_y = my_data["y"]

            self.record_replay_frame()

            if self.murilo_message_timer > 0:
                self.murilo_message_timer -= 1

            if self.state == "MENU":
                self.draw_menu()

            elif self.state == "SHOP":
                self.draw_shop()

            elif self.state == "STATS":
                self.draw_stats()

            elif self.state == "ACHIEVEMENTS":
                self.draw_achievements()

            elif self.state == "LOBBY":
                if self.secret_character_select_open:
                    self.draw_secret_character_select()
                else:
                    self.draw_lobby()

            elif self.state == "PLAYING":
                if self.replay_playing:
                    self.draw_replay_frame()

                else:
                    alguem_em_cutscene = False

                    if self.server_data:
                        for p in self.server_data["players"].values():
                            if p.get("roleta_state") == "CUTSCENE":
                                alguem_em_cutscene = True
                                break

                    if alguem_em_cutscene:
                        self.draw_cutscene()
                    else:
                        self.draw_game()

            elif self.state == "GAME_OVER":
                self.draw_game_over()

            self.draw_achievement_notifications()
            pygame.display.flip()

        if self.net.connected:
            self.net.disconnect()

        self.stop_local_server()

        pygame.quit()
        sys.exit()


if __name__ == "__main__":
    game = GameClient()
    game.run()
