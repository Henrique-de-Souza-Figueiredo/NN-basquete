import pygame
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


def resolve_hoop_collisions(ball):
    for rim_x in (LEFT_HOOP_X1, LEFT_HOOP_X2, RIGHT_HOOP_X1, RIGHT_HOOP_X2):
        resolve_circle_point_collision(ball, rim_x, HOOP_Y, HOOP_RIM_RAD)

    resolve_circle_rect_collision(ball, (LEFT_BACKBOARD_X, BACKBOARD_Y, BACKBOARD_W, BACKBOARD_H))
    resolve_circle_rect_collision(ball, (RIGHT_BACKBOARD_X, BACKBOARD_Y, BACKBOARD_W, BACKBOARD_H))


def get_attack_hoop(team):
    if team == 1:
        return (RIGHT_HOOP_X1 + RIGHT_HOOP_X2) / 2, HOOP_Y

    return (LEFT_HOOP_X1 + LEFT_HOOP_X2) / 2, HOOP_Y


def can_start_dunk_locally(player_data, ball):
    if ball.get("holder") is None:
        return False

    if player_data.get("dunk_active", 0) > 0:
        return False

    if player_data.get("stun_timer", 0) > 0 or player_data.get("knockback_timer", 0) > 0:
        return False

    if player_data["y"] >= GROUND_Y - CHAR_H - 4:
        return False

    hoop_x, hoop_y = get_attack_hoop(player_data["team"])
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


def predict_ball_path(ball, target_x, target_y, power, steps=180):
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

        if x >= WIDTH - BALL_RAD:
            x = WIDTH - BALL_RAD
            vel_x *= -0.8

        temp_ball = {"x": x, "y": y, "vel_x": vel_x, "vel_y": vel_y}
        resolve_hoop_collisions(temp_ball)
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

        self.btn_start_game = Button("INICIAR", WIDTH - 220, 20, 200, 60, BALL_COLOR)
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

        self.char_images = {}
        self.small_char_images = {}
        self.tinted_small_images = {}

        self.card_w = 140
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
        response = self.net.connect("CREATE")
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

        self.btn_create.draw(screen)
        self.btn_join.draw(screen)
        self.btn_story.draw(screen)
        self.btn_shop.draw(screen)
        self.btn_stats.draw(screen)
        self.btn_achievements.draw(screen)
        self.btn_quit_game.draw(screen)

        money_txt = font_md.render(f"Dinheiro: ${save_db.get_money()}", True, BLACK)
        screen.blit(money_txt, (20, 20))

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

    def draw_shop(self):
        screen.fill((18, 28, 34))

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

        for i, name in enumerate(CHARACTERS):
            rect = pygame.Rect(500 + (i % 4) * 155, 95 + (i // 4) * 42, 145, 34)
            self.shop_char_rects.append((rect, i))
            pygame.draw.rect(screen, (65, 80, 95) if i == self.selected_char_idx else (35, 45, 55), rect, border_radius=8)
            pygame.draw.rect(screen, (255, 230, 120) if i == self.selected_char_idx else GRAY, rect, 2, border_radius=8)
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

        for char in CHARACTERS:
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
                p_text = f"P{pid}: {p_char}"

                if pid == self.my_id:
                    p_text += " (Você)"
                    pygame.draw.rect(screen, (255, 255, 0), (45, y_pos, 250, 30), 1)

                txt_surf = font_sm.render(p_text, True, p_team_color)
                screen.blit(txt_surf, (50, y_pos + 5))
                y_pos += 35

        total_width = (self.card_w * len(CHARACTERS)) + (10 * (len(CHARACTERS) - 1))
        start_x = (WIDTH - total_width) // 2
        start_y = 180

        self.char_rects = []
        hovered_char = None

        for i, name in enumerate(CHARACTERS):
            x = start_x + i * (self.card_w + 10)
            rect = pygame.Rect(x, start_y, self.card_w, self.card_h)
            self.char_rects.append(rect)

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

            if i == self.selected_char_idx:
                pygame.draw.rect(screen, (255, 215, 0), rect, 5)

            if rect.collidepoint(mouse_pos):
                hovered_char = name
                pygame.draw.rect(screen, WHITE, rect, 2)

        char_to_show = hovered_char if hovered_char else CHARACTERS[self.selected_char_idx]

        panel_rect = pygame.Rect(0, HEIGHT - 120, WIDTH, 120)
        pygame.draw.rect(screen, (20, 20, 25), panel_rect)
        pygame.draw.rect(screen, (50, 50, 60), panel_rect, 3)

        desc_title = font_title.render(char_to_show.upper(), True, CHARACTERS_INFO[char_to_show]["color"])
        screen.blit(desc_title, (50, HEIGHT - 100))

        desc_text = font_md.render(CHARACTERS_INFO[char_to_show]["desc"], True, WHITE)
        screen.blit(desc_text, (50, HEIGHT - 50))

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
        score_surf = font_lg.render(f"Placar Final: {score[0]} x {score[1]}", True, WHITE)
        screen.blit(score_surf, (WIDTH // 2 - score_surf.get_width() // 2, 130))

        if self.reward_message:
            reward_txt = font_md.render(self.reward_message, True, (255, 230, 120))
            screen.blit(reward_txt, (WIDTH // 2 - reward_txt.get_width() // 2, 185))

        winners = []
        losers = []

        for p_data in self.server_data["players"].values():
            if p_data["char"]:
                if p_data["team"] == winner_team:
                    winners.append(p_data)
                else:
                    losers.append(p_data)

        start_x_win = WIDTH // 2 - (len(winners) * (self.card_w + 20)) // 2
        y_win = HEIGHT // 2 - self.card_h // 2 - 20

        for i, p_data in enumerate(winners):
            char_name = p_data["char"]
            x = start_x_win + i * (self.card_w + 20)
            img = self.char_images.get(char_name)
            char_color = CHARACTERS_INFO[char_name]["color"]

            if img:
                screen.blit(img, (x, y_win))
            else:
                pygame.draw.rect(screen, char_color, (x, y_win, self.card_w, self.card_h))
                name_fallback = font_sm.render(char_name, True, BLACK)
                screen.blit(name_fallback, (x + 10, y_win + self.card_h // 2))

            draw_skin_overlay(screen, x, y_win, self.card_w, self.card_h, p_data.get("skin_id", "default"), self.card_w / CHAR_W)
            pygame.draw.rect(screen, JACKPOT_COLOR, (x - 5, y_win - 5, self.card_w + 10, self.card_h + 10), 5)

            name_txt = font_md.render(char_name, True, winner_color)
            screen.blit(name_txt, (x + self.card_w // 2 - name_txt.get_width() // 2, y_win + self.card_h + 10))

        self.btn_exit.draw(screen)

    def apply_match_rewards_once(self):
        if not self.server_data or not self.server_data.get("game_over") or self.my_id not in self.server_data["players"]:
            return

        replay_id = self.server_data.get("replay_id", 0)

        if self.reward_applied_for_replay_id == replay_id:
            return

        my_data = self.server_data["players"][self.my_id]
        char_name = my_data.get("char")

        if not char_name:
            return

        won = my_data.get("team") == self.server_data.get("winner_team")
        baskets = int(my_data.get("match_baskets", 0))
        points = int(my_data.get("match_points", 0))

        money = 20 + baskets * 8 + points * 2
        xp = 25 + baskets * 12 + points * 4

        if won:
            money += 60
            xp += 70
        else:
            money = max(10, money // 2)
            xp = max(12, xp // 2)

        unlocked_before = self.get_unlocked_achievement_ids()

        save_db.add_money(money)
        save_db.add_character_xp(char_name, xp)
        save_db.record_match(char_name, won, baskets, points)
        self.reward_applied_for_replay_id = replay_id
        self.reward_message = f"+${money}  +{xp} XP para {char_name}"

        chars_in_match = {p.get("char") for p in self.server_data["players"].values() if p.get("char")}

        if {"Rafael", "John Jonh"} <= chars_in_match:
            save_db.unlock_pair_achievement("Rafael", "John Jonh", "aerial")

        if {"Diogo", "Paulo"} <= chars_in_match:
            save_db.unlock_pair_achievement("Diogo", "Paulo", "chaos")

        if won and self.opponent_jackpot_seen:
            save_db.unlock_character_achievement(char_name, "jackpot_stopper")

        self.enqueue_new_achievement_notifications(unlocked_before)

    def update_local_achievement_events(self):
        if not self.server_data or self.my_id not in self.server_data.get("players", {}):
            return

        my_data = self.server_data["players"][self.my_id]
        char_name = my_data.get("char")

        if not char_name:
            return

        unlocked_before = None

        if my_data.get("dunk_ready_to_score", 0) > 0 and self.last_dunk_ready_state <= 0:
            unlocked_before = self.get_unlocked_achievement_ids()
            save_db.unlock_character_achievement(char_name, "dunk_master")

        self.last_dunk_ready_state = my_data.get("dunk_ready_to_score", 0)

        clash_id = my_data.get("clash_id", 0)

        if my_data.get("clash_active", 0) > 0 and clash_id and clash_id != self.last_seen_clash_id:
            if unlocked_before is None:
                unlocked_before = self.get_unlocked_achievement_ids()

            self.last_seen_clash_id = clash_id
            save_db.unlock_character_achievement(char_name, "clash_winner")
            opponent_id = my_data.get("clash_opponent")
            opponent = self.server_data["players"].get(opponent_id)

            if opponent and opponent.get("char"):
                pair = {char_name, opponent["char"]}

                if pair == {"Henrique", "Presscinotti"}:
                    save_db.unlock_pair_achievement("Henrique", "Presscinotti", "clash")

                if pair == {"Henrique", "Miguel"}:
                    save_db.unlock_pair_achievement("Henrique", "Miguel", "clash")

        if unlocked_before is not None:
            self.enqueue_new_achievement_notifications(unlocked_before)

    def update_jackpot_achievement_events(self):
        if not self.server_data or self.my_id not in self.server_data.get("players", {}):
            return

        my_data = self.server_data["players"][self.my_id]
        my_char = my_data.get("char")

        if not my_char:
            return

        for player_id, player in self.server_data["players"].items():
            if player.get("char") != "Paulo":
                continue

            has_jackpot = (
                player.get("jackpot_timer", 0) > 0
                or player.get("roleta_result") == "JACKPOT"
                or player.get("roleta_state") == "CUTSCENE"
            )

            if not has_jackpot or player_id in self.seen_jackpot_players:
                continue

            self.seen_jackpot_players.add(player_id)
            unlocked_before = self.get_unlocked_achievement_ids()

            if player_id == self.my_id:
                save_db.unlock_character_achievement("Paulo", "paulo_jackpot")
            else:
                save_db.unlock_character_achievement(my_char, "jackpot_witness")

                if player.get("team") == my_data.get("team"):
                    save_db.unlock_character_achievement(my_char, "jackpot_ally")
                else:
                    self.opponent_jackpot_seen = True

            self.enqueue_new_achievement_notifications(unlocked_before)

    def get_unlocked_achievement_ids(self):
        return {item["achievement_id"] for item in save_db.get_achievements()}

    def get_achievement_notification_data(self, achievement_id):
        if achievement_id in save_db.PAIR_ACHIEVEMENT_DEFS:
            data = save_db.PAIR_ACHIEVEMENT_DEFS[achievement_id]
            return {
                "name": data["name"],
                "description": data["description"],
                "character": " + ".join(data["characters"]),
            }

        if ":" not in achievement_id:
            return None

        character, suffix = achievement_id.split(":", 1)
        data = save_db.ACHIEVEMENT_DEFS.get(suffix)

        if not data:
            return None

        return {
            "name": data["name"],
            "description": data["description"],
            "character": character,
        }

    def enqueue_new_achievement_notifications(self, unlocked_before):
        unlocked_after = save_db.get_achievements()
        new_items = [item for item in unlocked_after if item["achievement_id"] not in unlocked_before]

        for item in reversed(new_items):
            notification = self.get_achievement_notification_data(item["achievement_id"])

            if notification:
                notification["timer"] = 240
                self.achievement_notifications.append(notification)

    def render_wrapped_text(self, text, font, color, max_width):
        lines = []
        current = ""

        for word in text.split():
            candidate = word if not current else f"{current} {word}"

            if font.size(candidate)[0] <= max_width:
                current = candidate
            else:
                if current:
                    lines.append(current)
                current = word

        if current:
            lines.append(current)

        return [font.render(line, True, color) for line in lines]

    def draw_achievement_notifications(self):
        if not self.current_achievement_notification and self.achievement_notifications:
            self.current_achievement_notification = self.achievement_notifications.pop(0)

        notification = self.current_achievement_notification

        if not notification:
            return

        notification["timer"] -= 1

        if notification["timer"] <= 0:
            self.current_achievement_notification = None
            return

        timer = notification["timer"]
        panel_w = 500
        panel_h = 118
        target_x = WIDTH - panel_w - 24
        slide = min(1.0, (240 - timer) / 18)

        if timer < 28:
            slide = min(slide, timer / 28)

        x = int(WIDTH - (WIDTH - target_x) * slide)
        y = 92
        rect = pygame.Rect(x, y, panel_w, panel_h)

        shadow = rect.move(6, 6)
        pygame.draw.rect(screen, (0, 0, 0), shadow, border_radius=18)
        pygame.draw.rect(screen, (18, 18, 22), rect, border_radius=18)
        pygame.draw.rect(screen, (255, 140, 0), rect, 3, border_radius=18)

        pygame.draw.circle(screen, BALL_COLOR, (x + 52, y + 58), 28)
        pygame.draw.circle(screen, BLACK, (x + 52, y + 58), 28, 3)
        pygame.draw.arc(screen, BLACK, (x + 32, y + 38, 40, 40), -1.2, 1.2, 3)
        pygame.draw.line(screen, BLACK, (x + 52, y + 30), (x + 52, y + 86), 3)
        pygame.draw.line(screen, BLACK, (x + 26, y + 58), (x + 78, y + 58), 3)

        header = font_sm.render("CONQUISTA DESBLOQUEADA", True, (255, 215, 90))
        title = font_md.render(notification["name"], True, WHITE)
        character = font_sm.render(notification["character"], True, (255, 180, 90))
        desc_lines = self.render_wrapped_text(notification["description"], font_sm, (220, 220, 220), panel_w - 125)

        screen.blit(header, (x + 98, y + 14))
        screen.blit(title, (x + 98, y + 36))
        screen.blit(character, (x + panel_w - character.get_width() - 18, y + 18))

        desc_y = y + 72
        for line in desc_lines[:2]:
            screen.blit(line, (x + 98, desc_y))
            desc_y += 22

    def draw_player_image(self, p_data, color):
        char_name = p_data.get("char")
        team = p_data.get("team", 1)
        img = self.tinted_small_images.get((char_name, team))

        if img:
            screen.blit(img, (p_data["x"], p_data["y"]))
            draw_skin_overlay(screen, p_data["x"], p_data["y"], CHAR_W, CHAR_H, p_data.get("skin_id", "default"))
            pygame.draw.rect(screen, color, (p_data["x"], p_data["y"], CHAR_W, CHAR_H), 2)
        else:
            pygame.draw.rect(screen, color, (p_data["x"], p_data["y"], CHAR_W, CHAR_H))
            draw_skin_overlay(screen, p_data["x"], p_data["y"], CHAR_W, CHAR_H, p_data.get("skin_id", "default"))

    def draw_game(self):
        screen.fill((40, 45, 55))

        floor_rect = pygame.Rect(0, HEIGHT - 60, WIDTH, 60)
        pygame.draw.rect(screen, (205, 133, 63), floor_rect)
        pygame.draw.rect(screen, (139, 69, 19), floor_rect, 5)

        pygame.draw.line(screen, WHITE, (WIDTH // 2, HEIGHT - 60), (WIDTH // 2, HEIGHT), 5)

        pygame.draw.rect(screen, GRAY, (80, HEIGHT - 360, 15, 300))
        pygame.draw.rect(screen, WHITE, (LEFT_BACKBOARD_X, BACKBOARD_Y, BACKBOARD_W, BACKBOARD_H))
        pygame.draw.rect(screen, TEAM_1_COLOR, (LEFT_BACKBOARD_X, BACKBOARD_Y, BACKBOARD_W, BACKBOARD_H), 3)
        pygame.draw.rect(screen, (255, 69, 0), (LEFT_HOOP_X1, HOOP_Y, LEFT_HOOP_X2 - LEFT_HOOP_X1, 8))

        pygame.draw.line(screen, WHITE, (LEFT_HOOP_X1, HOOP_Y + 8), (110, HEIGHT - 290), 2)
        pygame.draw.line(screen, WHITE, (LEFT_HOOP_X2, HOOP_Y + 8), (130, HEIGHT - 290), 2)
        pygame.draw.line(screen, WHITE, (110, HOOP_Y + 8), (130, HEIGHT - 290), 2)
        pygame.draw.line(screen, WHITE, (130, HOOP_Y + 8), (110, HEIGHT - 290), 2)

        pygame.draw.rect(screen, GRAY, (WIDTH - 95, HEIGHT - 360, 15, 300))
        pygame.draw.rect(screen, WHITE, (RIGHT_BACKBOARD_X, BACKBOARD_Y, BACKBOARD_W, BACKBOARD_H))
        pygame.draw.rect(screen, TEAM_2_COLOR, (RIGHT_BACKBOARD_X, BACKBOARD_Y, BACKBOARD_W, BACKBOARD_H), 3)
        pygame.draw.rect(screen, (255, 69, 0), (RIGHT_HOOP_X1, HOOP_Y, RIGHT_HOOP_X2 - RIGHT_HOOP_X1, 8))

        pygame.draw.line(screen, WHITE, (RIGHT_HOOP_X1, HOOP_Y + 8), (WIDTH - 130, HEIGHT - 290), 2)
        pygame.draw.line(screen, WHITE, (RIGHT_HOOP_X2, HOOP_Y + 8), (WIDTH - 110, HEIGHT - 290), 2)
        pygame.draw.line(screen, WHITE, (WIDTH - 130, HOOP_Y + 8), (WIDTH - 110, HEIGHT - 290), 2)
        pygame.draw.line(screen, WHITE, (WIDTH - 110, HOOP_Y + 8), (WIDTH - 130, HEIGHT - 290), 2)

        if not self.server_data:
            loading = font_md.render("Entrando na partida...", True, WHITE)
            screen.blit(loading, (WIDTH // 2 - loading.get_width() // 2, HEIGHT // 2))
            return

        if self.my_id not in self.server_data["players"]:
            return

        my_p_data = self.server_data["players"][self.my_id]
        am_i_jackpot = my_p_data.get("jackpot_timer", 0) > 0
        r_state = my_p_data.get("roleta_state", "IDLE")

        score = self.server_data["score"]
        score_text = font_lg.render(f"{score[0]} x {score[1]}", True, WHITE)

        pygame.draw.rect(screen, BLACK, (WIDTH // 2 - 100, 10, 200, 70), border_radius=15)
        pygame.draw.rect(screen, TEAM_1_COLOR, (WIDTH // 2 - 100, 10, 100, 70), 4, border_radius=15)
        pygame.draw.rect(screen, TEAM_2_COLOR, (WIDTH // 2, 10, 100, 70), 4, border_radius=15)
        screen.blit(score_text, (WIDTH // 2 - score_text.get_width() // 2, 15))

        for p_id, p_data in self.server_data["players"].items():
            if p_data["char"] is None:
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

            self.draw_player_image(p_data, color)

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

        ball = self.server_data["ball"]

        pygame.draw.circle(screen, BALL_COLOR, (int(ball["x"]), int(ball["y"])), BALL_RAD)
        pygame.draw.circle(screen, BLACK, (int(ball["x"]), int(ball["y"])), BALL_RAD, 2)

        if ball.get("holder") == self.my_id and r_state != "CUTSCENE":
            mx, my = pygame.mouse.get_pos()

            if (
                my_p_data.get("char") == "Rafael"
                and my_p_data.get("throw_buff_timer", 0) > 0
            ):
                path = predict_ball_path(ball, mx, my, get_throw_power(my_p_data))

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

        server_cd = my_p_data.get("ability_cd", self.ability_cooldown)

        if server_cd > 0:
            cd_txt = font_md.render(f"Poder: {server_cd // 60}s", True, (255, 50, 50))
            screen.blit(cd_txt, (20, HEIGHT - 50))
        else:
            cd_txt = font_md.render("Poder: PRONTO (Aperte E)", True, (50, 255, 50))
            screen.blit(cd_txt, (20, HEIGHT - 50))

        self.btn_leave_match.draw(screen)

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

    def run(self):
        running = True

        while running:
            clock.tick(FPS)
            mouse_pos = pygame.mouse.get_pos()
            data_to_send = {}

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
                        continue

                    if my_p.get("roleta_state") == "CUTSCENE":
                        continue

                    if event.type == pygame.KEYDOWN and my_p.get("clash_active", 0) > 0:
                        qte_key = qte_key_from_event(event)

                        if qte_key:
                            data_to_send["action"] = "CLASH_QTE_KEY"
                            data_to_send["key"] = qte_key
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
                            data_to_send["action"] = "USE_ABILITY"
                            data_to_send["facing"] = self.facing
                            ability_achievement = ABILITY_ACHIEVEMENTS.get(my_p.get("char"))

                            if ability_achievement:
                                unlocked_before = self.get_unlocked_achievement_ids()
                                save_db.unlock_character_achievement(my_p["char"], ability_achievement)
                                self.enqueue_new_achievement_notifications(unlocked_before)

                            if CHARACTERS[self.selected_char_idx] in ["Diogo", "Paulo"]:
                                self.ability_cooldown = 480
                            else:
                                self.ability_cooldown = 360

                elif self.state == "MENU":
                    if event.type == pygame.KEYDOWN:
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

                    if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                        if self.host_ip_rect.collidepoint(mouse_pos):
                            self.active_input = "host"

                        elif self.room_code_rect.collidepoint(mouse_pos):
                            self.active_input = "room"

                        elif self.btn_create.is_clicked(mouse_pos):
                            self.create_local_room()


                        elif self.btn_join.is_clicked(mouse_pos):
                            self.join_remote_room()

                        elif self.btn_story.is_clicked(mouse_pos):
                            start_story_mode_process()

                        elif self.btn_shop.is_clicked(mouse_pos):
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
                    if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                        if self.btn_leave_lobby.is_clicked(mouse_pos):
                            self.leave_match_to_menu()
                            continue

                        if self.btn_team_blue.is_clicked(mouse_pos):
                            self.my_team = 1

                        elif self.btn_team_red.is_clicked(mouse_pos):
                            self.my_team = 2

                        for i, rect in enumerate(self.char_rects):
                            if rect.collidepoint(mouse_pos):
                                char_name = CHARACTERS[i]
                                is_taken = False

                                if self.server_data:
                                    for pid, p_data in self.server_data["players"].items():
                                        if pid != self.my_id and p_data["char"] == char_name:
                                            is_taken = True

                                if not is_taken:
                                    self.selected_char_idx = i

                        if self.is_host and self.btn_start_game.is_clicked(mouse_pos):
                            self.net.send({"action": "START_GAME"})

                elif self.state == "GAME_OVER":
                    if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                        if self.btn_exit.is_clicked(mouse_pos):
                            self.leave_match_to_menu()

            if self.state in ["LOBBY", "PLAYING"]:
                if self.state == "LOBBY":
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

                            if is_dashing or is_knocked or is_stunned or is_dunking or is_clashing:
                                self.player_x = my_p["x"]
                                self.player_y = my_p["y"]

                            keys = pygame.key.get_pressed()

                            if not is_stunned and not is_dashing and not is_knocked and not is_dunking and not is_clashing:
                                if keys[pygame.K_a]:
                                    self.player_x -= self.speed
                                    self.facing = -1

                                if keys[pygame.K_d]:
                                    self.player_x += self.speed
                                    self.facing = 1

                                self.player_x = max(0, min(self.player_x, WIDTH - CHAR_W))

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

                self.server_data = self.net.send(data_to_send)

                if self.server_data:
                    self.check_replay_trigger()
                    self.update_local_achievement_events()
                    self.update_jackpot_achievement_events()

                if not self.server_data:
                    self.state = "MENU"
                    self.error_msg = "Desconectado do servidor."

                else:
                    if self.server_data.get("game_over"):
                        self.apply_match_rewards_once()
                        self.state = "GAME_OVER"

                    elif self.state == "LOBBY" and self.server_data["game_started"]:
                        self.state = "PLAYING"
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

            if self.state == "MENU":
                self.draw_menu()

            elif self.state == "SHOP":
                self.draw_shop()

            elif self.state == "STATS":
                self.draw_stats()

            elif self.state == "ACHIEVEMENTS":
                self.draw_achievements()

            elif self.state == "LOBBY":
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
