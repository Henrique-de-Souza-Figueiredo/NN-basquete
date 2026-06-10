import pygame
import sys
import os
import math
import random
import json
from config import *
import save_db

pygame.init()
save_db.init_db()

screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("NN League - Modo História")
clock = pygame.time.Clock()

font_sm = pygame.font.SysFont("Arial", 20)
font_md = pygame.font.SysFont("Arial", 30)
font_lg = pygame.font.SysFont("Arial", 55, bold=True)
font_xl = pygame.font.SysFont("Arial", 85, bold=True)

IMAGES_DIR = "imagens"
STORY_DIR = os.path.join(IMAGES_DIR, "historia")
SAVE_FILE = "story_save.json"


def image_path(filename):
    return os.path.join(IMAGES_DIR, filename)


def story_image_path(filename):
    return os.path.join(STORY_DIR, filename)


def clamp(value, min_value, max_value):
    return max(min_value, min(value, max_value))


def rects_overlap(a, b):
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return ax < bx + bw and ax + aw > bx and ay < by + bh and ay + ah > by


def make_team_tinted_image(image, team):
    tinted = image.copy().convert_alpha()
    overlay = pygame.Surface(tinted.get_size(), pygame.SRCALPHA)

    if team == 1:
        overlay.fill((40, 80, 255, 95))
    else:
        overlay.fill((255, 40, 40, 95))

    tinted.blit(overlay, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)
    return tinted


def get_player_throw_power(player):
    power = 25

    if player["char"] == "Rafael":
        power = 34

    if player["throw_buff"] > 0:
        power += 8

    if player["jackpot_timer"] > 0:
        power += 10

    return power


def get_score_points_from_origin(ball, scored_team):
    origin_x = ball.get("shot_origin_x")
    origin_y = ball.get("shot_origin_y")

    if ball.get("score_override"):
        return ball["score_override"]

    if origin_x is None or origin_y is None:
        return 2

    hoop_x, hoop_y = get_attack_hoop(scored_team)
    distance = math.hypot(origin_x - hoop_x, origin_y - hoop_y)

    if distance >= THREE_POINT_DISTANCE:
        return 3

    return 2


def predict_ball_path(ball, target_x, target_y, power, steps=180):
    angle = math.atan2(target_y - ball["y"], target_x - ball["x"])
    x = ball["x"]
    y = ball["y"]
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


def is_player_timed_ability_active(player):
    char = player["char"]

    if char == "Henrique":
        return player["dash_timer"] > 0

    if char == "Natan":
        return player["invisible_timer"] > 0

    if char == "Presscinotti":
        return player["ear_timer"] > 0

    if char == "Diogo":
        return player["speed_buff"] > 0 or player["throw_buff"] > 0

    if char == "Miguel":
        return player["clone_timer"] > 0

    if char == "Rafael":
        return player["throw_buff"] > 0

    if char == "John Jonh":
        return player["john_float_timer"] > 0

    if char == "Paulo":
        return (
            player["speed_buff"] > 0
            or player["throw_buff"] > 0
            or player["jackpot_timer"] > 0
            or player["roleta_timer"] > 0
        )

    return False


def get_attack_hoop(team):
    if team == 1:
        return (RIGHT_HOOP_X1 + RIGHT_HOOP_X2) / 2, HOOP_Y

    return (LEFT_HOOP_X1 + LEFT_HOOP_X2) / 2, HOOP_Y


def can_start_dunk(player, ball):
    if ball["holder"] != "player":
        return False

    if player.get("dunk_active", 0) > 0:
        return False

    if player.get("stun_timer", 0) > 0 or player.get("knockback_timer", 0) > 0:
        return False

    if player["y"] >= GROUND_Y - CHAR_H - 4:
        return False

    hoop_x, hoop_y = get_attack_hoop(player["team"])
    player_cx = player["x"] + CHAR_W / 2
    player_cy = player["y"] + CHAR_H / 2

    return (
        abs(player_cx - hoop_x) <= DUNK_RANGE_X
        and abs(player_cy - hoop_y) <= DUNK_RANGE_Y
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


def ball_crossed_hoop(prev_y, ball, x1, x2):
    return (
        ball["vel_y"] > 0
        and prev_y <= HOOP_Y + HOOP_SCORE_MARGIN_Y
        and ball["y"] >= HOOP_Y - HOOP_SCORE_MARGIN_Y
        and x1 + HOOP_SCORE_MARGIN_X <= ball["x"] <= x2 - HOOP_SCORE_MARGIN_X
    )


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


def load_save():
    return {"unlocked_level": save_db.get_unlocked_story_level()}


def save_progress(unlocked_level):
    save_db.set_unlocked_story_level(unlocked_level)


class Button:
    def __init__(self, text, x, y, w, h, color, text_color=WHITE):
        self.rect = pygame.Rect(x, y, w, h)
        self.text = text
        self.color = color
        self.text_color = text_color

    def draw(self, surface):
        pygame.draw.rect(surface, self.color, self.rect, border_radius=12)
        pygame.draw.rect(surface, BLACK, self.rect, 2, border_radius=12)

        txt = font_md.render(self.text, True, self.text_color)
        surface.blit(
            txt,
            (
                self.rect.centerx - txt.get_width() // 2,
                self.rect.centery - txt.get_height() // 2
            )
        )

    def is_clicked(self, pos):
        return self.rect.collidepoint(pos)


STORY_LEVELS = [
    {
        "level": 1,
        "title": "A Origem de Rafael",
        "player_char": "Rafael",
        "enemy_name": "Treinador Bruno",
        "enemy_char": "Henrique",
        "enemy_team": "Treinadores de Rua",
        "difficulty": 1,
        "target_score": 6,
        "cutscene": "cutscene_rafael.png",
        "objective": "Use salto e arremessos fortes para vencer.",
        "story": [
            "Rafael sempre sentiu que podia voar mais alto que todos.",
            "Na quadra, seu salto e sua força chamaram atenção.",
            "Agora ele precisa provar que nasceu para liderar."
        ]
    },
    {
        "level": 2,
        "title": "A Origem de Natan",
        "player_char": "Natan",
        "enemy_name": "Olheiro Invisível",
        "enemy_char": "Rafael",
        "enemy_team": "Marcadores Silenciosos",
        "difficulty": 2,
        "target_score": 6,
        "cutscene": "cutscene_natan.png",
        "objective": "Use invisibilidade para enganar a marcação.",
        "story": [
            "Natan sempre passou despercebido.",
            "Enquanto todos olhavam para a bola, ele observava espaços vazios.",
            "Ninguém consegue marcar aquilo que não consegue ver."
        ]
    },
    {
        "level": 3,
        "title": "A Origem de Presscinotti",
        "player_char": "Presscinotti",
        "enemy_name": "Zé Provocação",
        "enemy_char": "John Jonh",
        "enemy_team": "Atacantes Falastrões",
        "difficulty": 3,
        "target_score": 8,
        "cutscene": "cutscene_prescinotti.png",
        "objective": "Use as orelhas para empurrar e defender.",
        "story": [
            "Todos riam das orelhas de Presscinotti.",
            "Mas na quadra, aquilo virou uma muralha.",
            "Agora ninguém passa sem pedir licença."
        ]
    },
    {
        "level": 4,
        "title": "A Origem de Henrique",
        "player_char": "Henrique",
        "enemy_name": "Driblador Relâmpago",
        "enemy_char": "Miguel",
        "enemy_team": "Dribladores de Rua",
        "difficulty": 4,
        "target_score": 8,
        "cutscene": "cutscene_henrique.png",
        "objective": "Use o dash para roubar a bola.",
        "story": [
            "Henrique descobriu que velocidade decide jogos.",
            "Em um piscar de olhos, ele já estava com a bola.",
            "Contra ele, não existe posse segura."
        ]
    },
    {
        "level": 5,
        "title": "A Origem de Diogo",
        "player_char": "Diogo",
        "enemy_name": "Chefão da Defesa",
        "enemy_char": "Presscinotti",
        "enemy_team": "Defensores Famintos",
        "difficulty": 5,
        "target_score": 10,
        "cutscene": "cutscene_diogo.png",
        "objective": "Use a Bolacha Turbo para ganhar velocidade e força.",
        "story": [
            "Diogo não entrou na quadra com tênis novo.",
            "Ele entrou com bolachas.",
            "E ninguém esperava que uma bolacha mudaria o jogo."
        ]
    },
    {
        "level": 6,
        "title": "A Origem de Paulo",
        "player_char": "Paulo",
        "enemy_name": "Capitão Azar",
        "enemy_char": "Diogo",
        "enemy_team": "Apostadores da Quadra",
        "difficulty": 6,
        "target_score": 10,
        "cutscene": "cutscene_paulo.png",
        "objective": "Use a roleta para buscar buffs ou jackpot.",
        "story": [
            "Paulo nunca jogava uma partida normal.",
            "Com ele, tudo virava sorte, caos e espetáculo.",
            "Quando a roleta gira, até a quadra prende a respiração."
        ]
    },
    {
        "level": 7,
        "title": "A Origem de Miguel",
        "player_char": "Miguel",
        "enemy_name": "Sombra Rival",
        "enemy_char": "Natan",
        "enemy_team": "Defesa Sombria",
        "difficulty": 7,
        "target_score": 12,
        "cutscene": "cutscene_miguel.png",
        "objective": "Use o clone para confundir o inimigo.",
        "story": [
            "Miguel percebeu que sozinho já era perigoso.",
            "Mas com um clone, a defesa nunca saberia quem marcar.",
            "Dois Miguel na quadra. Uma só bola. Muito caos."
        ]
    },
    {
        "level": 8,
        "title": "A Origem de John Jonh",
        "player_char": "John Jonh",
        "enemy_name": "Bloqueador Pesado",
        "enemy_char": "Rafael",
        "enemy_team": "Gigantes da Tabela",
        "difficulty": 8,
        "target_score": 12,
        "cutscene": "cutscene_johnjonh.png",
        "objective": "Use velocidade e leveza para escapar.",
        "story": [
            "John Jonh parecia desafiar a gravidade.",
            "Enquanto os outros corriam, ele flutuava.",
            "Na quadra, leveza também é poder."
        ]
    },
    {
        "level": 9,
        "title": "Primeiro Treino do Time",
        "player_char": "Henrique",
        "enemy_name": "Time de Treino",
        "enemy_char": "Paulo",
        "enemy_team": "Equipe de Teste",
        "difficulty": 9,
        "target_score": 14,
        "cutscene": "cutscene_treino.png",
        "objective": "Mostre que o time está pronto.",
        "story": [
            "Os poderes estavam surgindo.",
            "Mas talento individual não vence campeonato.",
            "Era hora de aprender a jogar como equipe."
        ]
    },
    {
        "level": 10,
        "title": "Havoc Squad - Primeiro Confronto",
        "player_char": "Rafael",
        "enemy_name": "Rex Havoc",
        "enemy_char": "Miguel",
        "enemy_team": "Havoc Squad",
        "difficulty": 10,
        "target_score": 14,
        "cutscene": "cutscene_havoc_inicio.png",
        "objective": "Sobreviva ao início brutal do Havoc Squad.",
        "story": [
            "O primeiro jogo oficial começou.",
            "Do outro lado, o Havoc Squad não queria apenas vencer.",
            "Eles queriam humilhar a NN League."
        ]
    },
    {
        "level": 11,
        "title": "A Reação da NN League",
        "player_char": "Diogo",
        "enemy_name": "Maverick Havoc",
        "enemy_char": "Presscinotti",
        "enemy_team": "Havoc Squad Elite",
        "difficulty": 11,
        "target_score": 16,
        "cutscene": "cutscene_reacao.png",
        "objective": "Use buffs e estratégia para virar o jogo.",
        "story": [
            "A derrota parecia certa.",
            "Mas foi nesse momento que o time entendeu seu verdadeiro poder.",
            "Juntos, eles eram muito mais do que uma soma de habilidades."
        ]
    },
    {
        "level": 12,
        "title": "A Cesta Final",
        "player_char": "John Jonh",
        "enemy_name": "Lorde Havoc",
        "enemy_char": "Rafael",
        "enemy_team": "Havoc Squad Final",
        "difficulty": 12,
        "target_score": 18,
        "cutscene": "cutscene_final.png",
        "objective": "Faça a cesta da virada e vença a final.",
        "story": [
            "Restavam poucos segundos.",
            "A bola subiu, o ginásio ficou em silêncio.",
            "Era a hora da NN League nascer de verdade."
        ]
    }
]


class StoryMode:
    def __init__(self):
        self.running = True
        self.state = "MENU"

        save = load_save()
        self.unlocked_level = clamp(save.get("unlocked_level", 1), 1, len(STORY_LEVELS))

        self.level_index = 0
        self.level = STORY_LEVELS[self.level_index]

        self.char_images = {}
        self.tinted_images = {}
        self.load_images()

        self.btn_start = Button("COMEÇAR HISTÓRIA", WIDTH // 2 - 180, 300, 360, 60, TEAM_1_COLOR)
        self.btn_level_select = Button("SELEÇÃO DE FASES", WIDTH // 2 - 180, 380, 360, 60, (120, 80, 200))
        self.btn_reset_save = Button("RESETAR PROGRESSO", WIDTH // 2 - 180, 460, 360, 60, (160, 90, 40))
        self.btn_quit = Button("SAIR", WIDTH // 2 - 180, 540, 360, 60, (180, 40, 40))

        self.btn_continue = Button("CONTINUAR", WIDTH - 260, HEIGHT - 80, 220, 55, TEAM_1_COLOR)
        self.btn_back = Button("VOLTAR", 40, HEIGHT - 80, 180, 55, (180, 40, 40))
        self.btn_retry = Button("TENTAR NOVAMENTE", WIDTH // 2 - 180, 400, 360, 60, TEAM_1_COLOR)
        self.btn_next = Button("PRÓXIMA FASE", WIDTH // 2 - 180, 400, 360, 60, TEAM_1_COLOR)
        self.btn_menu = Button("MENU", WIDTH // 2 - 180, 480, 360, 60, (180, 40, 40))

        self.level_buttons = []
        self.make_level_buttons()

        self.reset_match()

    def make_level_buttons(self):
        self.level_buttons = []

        cols = 2
        btn_w = 500
        btn_h = 50
        gap_x = 40
        gap_y = 18
        start_x = WIDTH // 2 - btn_w - gap_x // 2
        start_y = 135

        for i, level in enumerate(STORY_LEVELS):
            col = i % cols
            row = i // cols

            x = start_x + col * (btn_w + gap_x)
            y = start_y + row * (btn_h + gap_y)

            btn = Button(
                f"FASE {level['level']} - {level['player_char']}",
                x,
                y,
                btn_w,
                btn_h,
                (70, 70, 100)
            )
            self.level_buttons.append(btn)

    def load_images(self):
        for name, info in CHARACTERS_INFO.items():
            path = image_path(info["img"])

            if os.path.exists(path):
                img = pygame.image.load(path).convert_alpha()
                small = pygame.transform.scale(img, (CHAR_W, CHAR_H))

                self.char_images[name] = small
                self.tinted_images[(name, 1)] = make_team_tinted_image(small, 1)
                self.tinted_images[(name, 2)] = make_team_tinted_image(small, 2)
            else:
                self.char_images[name] = None
                self.tinted_images[(name, 1)] = None
                self.tinted_images[(name, 2)] = None

    def reset_match(self):
        self.level = STORY_LEVELS[self.level_index]

        self.player = {
            "char": self.level["player_char"],
            "team": 1,
            "x": 200,
            "y": GROUND_Y - CHAR_H,
            "vel_y": 0,
            "facing": 1,
            "is_jumping": False,
            "ability_cd": 0,
            "dash_timer": 0,
            "invisible_timer": 0,
            "ear_timer": 0,
            "clone_timer": 0,
            "clone_x": 0,
            "clone_y": 0,
            "speed_buff": 0,
            "throw_buff": 0,
            "john_float_timer": 0,
            "jackpot_timer": 0,
            "roleta_timer": 0,
            "dunk_active": 0,
            "dunk_timer": 0,
            "dunk_anim_timer": 0,
            "dunk_ready_to_score": 0,
            "dunk_sequence": [],
            "dunk_index": 0,
            "dunk_start_x": 200,
            "dunk_start_y": GROUND_Y - CHAR_H,
            "dunk_target_x": 200,
            "dunk_target_y": GROUND_Y - CHAR_H,
            "stun_timer": 0,
            "knockback_timer": 0,
            "knockback_vx": 0
        }

        self.npc = {
            "char": self.level["enemy_char"],
            "team": 2,
            "name": self.level["enemy_name"],
            "x": WIDTH - 250,
            "y": GROUND_Y - CHAR_H,
            "vel_y": 0,
            "facing": -1,
            "is_jumping": False,
            "throw_timer": 0,
            "stun_timer": 0,
            "knockback_timer": 0,
            "knockback_vx": 0
        }

        self.ball = {
            "x": WIDTH // 2,
            "y": HEIGHT // 2 - 100,
            "vel_x": 0,
            "vel_y": 0,
            "holder": None,
            "dunk_no_score_timer": 0,
            "shot_origin_x": None,
            "shot_origin_y": None,
            "score_override": None,
        }

        self.score = [0, 0]
        self.message = self.level["objective"]
        self.message_timer = 180
        self.winner = None

    def start_intro_cutscene(self):
        self.state = "INTRO_CUTSCENE"

    def start_level(self, index):
        self.level_index = index
        self.reset_match()
        self.state = "CUTSCENE"

    def unlock_next_level(self):
        new_unlocked = max(self.unlocked_level, self.level_index + 2)
        self.unlocked_level = clamp(new_unlocked, 1, len(STORY_LEVELS))
        save_progress(self.unlocked_level)

    def reset_progress(self):
        self.unlocked_level = 1
        save_progress(1)
        self.level_index = 0
        self.reset_match()
        self.state = "MENU"

    def draw_text_wrapped(self, lines, x, y, color=WHITE, line_height=34):
        for i, line in enumerate(lines):
            txt = font_md.render(line, True, color)
            screen.blit(txt, (x, y + i * line_height))

    def draw_wrapped_paragraph(self, text, font, x, y, max_width, color=WHITE, line_height=24):
        current = ""

        for word in text.split():
            candidate = word if not current else f"{current} {word}"

            if font.size(candidate)[0] <= max_width:
                current = candidate
                continue

            if current:
                txt = font.render(current, True, color)
                screen.blit(txt, (x, y))
                y += line_height

            current = word

        if current:
            txt = font.render(current, True, color)
            screen.blit(txt, (x, y))
            y += line_height

        return y

    def draw_menu(self):
        screen.fill((20, 20, 35))

        title = font_xl.render("MODO HISTÓRIA", True, (255, 215, 0))
        screen.blit(title, (WIDTH // 2 - title.get_width() // 2, 70))

        subtitle = font_md.render("NN Basketball League - Origens", True, WHITE)
        screen.blit(subtitle, (WIDTH // 2 - subtitle.get_width() // 2, 180))

        progress = font_sm.render(f"Progresso: fase {self.unlocked_level}/{len(STORY_LEVELS)} desbloqueada", True, GRAY)
        screen.blit(progress, (WIDTH // 2 - progress.get_width() // 2, 225))

        self.btn_start.draw(screen)
        self.btn_level_select.draw(screen)
        self.btn_reset_save.draw(screen)
        self.btn_quit.draw(screen)

        tip = font_sm.render("Aperte ESC durante a partida para voltar ao menu.", True, GRAY)
        screen.blit(tip, (WIDTH // 2 - tip.get_width() // 2, 640))

    def draw_level_select(self):
        screen.fill((20, 20, 35))

        title = font_lg.render("SELEÇÃO DE FASES", True, (255, 215, 0))
        screen.blit(title, (WIDTH // 2 - title.get_width() // 2, 55))

        for i, btn in enumerate(self.level_buttons):
            level = STORY_LEVELS[i]
            unlocked = level["level"] <= self.unlocked_level

            if unlocked:
                btn.color = (70, 70, 100)
                btn.draw(screen)
                desc_color = WHITE
                label = f"FASE {level['level']} - {level['title']}"
            else:
                btn.color = (40, 40, 50)
                btn.draw(screen)
                desc_color = GRAY
                label = f"FASE {level['level']} - BLOQUEADA"

            desc = font_sm.render(label, True, desc_color)
            screen.blit(desc, (btn.rect.x + 18, btn.rect.y + 15))

        self.btn_back.draw(screen)

    def draw_image_cutscene(self, filename, title, lines, objective=None, show_hint=False):
        screen.fill(BLACK)

        path = story_image_path(filename)

        if os.path.exists(path):
            img = pygame.image.load(path).convert_alpha()
            img_ratio = img.get_width() / img.get_height()

            target_h = HEIGHT
            target_w = int(target_h * img_ratio)

            if target_w > WIDTH:
                target_w = WIDTH
                target_h = int(target_w / img_ratio)

            img = pygame.transform.scale(img, (target_w, target_h))
            image_x = WIDTH // 2 - target_w // 2
            image_y = HEIGHT // 2 - target_h // 2
            screen.blit(img, (image_x, image_y))

            left_w = image_x
            right_x = image_x + target_w
            right_w = WIDTH - right_x
            margin = 26

            if left_w >= 260 and right_w >= 260:
                pygame.draw.rect(screen, (10, 10, 18), (0, 0, left_w, HEIGHT))
                pygame.draw.rect(screen, (10, 10, 18), (right_x, 0, right_w, HEIGHT))
                pygame.draw.line(screen, (255, 215, 0), (image_x, 0), (image_x, HEIGHT), 3)
                pygame.draw.line(screen, (255, 215, 0), (right_x, 0), (right_x, HEIGHT), 3)

                title_y = 34
                title_txt = font_md.render(title, True, (255, 215, 0))
                screen.blit(title_txt, (margin, title_y))

                story_y = title_y + 58

                for line in lines:
                    story_y = self.draw_wrapped_paragraph(line, font_sm, margin, story_y, left_w - margin * 2, WHITE, 24)
                    story_y += 10

                if objective:
                    obj_title = font_md.render("Objetivo", True, (255, 215, 0))
                    screen.blit(obj_title, (right_x + margin, 42))
                    self.draw_wrapped_paragraph(objective, font_sm, right_x + margin, 92, right_w - margin * 2, (230, 230, 230), 24)

            else:
                panel_h = 140
                panel_y = HEIGHT - panel_h
                pygame.draw.rect(screen, (10, 10, 18), (0, panel_y, WIDTH, panel_h))
                pygame.draw.line(screen, (255, 215, 0), (0, panel_y), (WIDTH, panel_y), 3)

                title_txt = font_md.render(title, True, (255, 215, 0))
                screen.blit(title_txt, (40, panel_y + 12))

                if objective:
                    obj = font_sm.render(objective, True, (230, 230, 230))
                    screen.blit(obj, (40, panel_y + 58))

        else:
            screen.fill((25, 25, 40))

            title_txt = font_lg.render(title, True, (255, 215, 0))
            screen.blit(title_txt, (WIDTH // 2 - title_txt.get_width() // 2, 85))

            self.draw_text_wrapped(lines, 120, 215, WHITE, 42)

            if objective:
                obj_title = font_md.render("Objetivo:", True, (255, 215, 0))
                screen.blit(obj_title, (120, 470))

                obj = font_md.render(objective, True, WHITE)
                screen.blit(obj, (120, 515))

            if show_hint:
                hint = font_sm.render(
                    f"Coloque {filename} em imagens/historia/ para usar o quadrinho como cutscene.",
                    True,
                    GRAY
                )
                screen.blit(hint, (120, 585))

        self.btn_continue.draw(screen)
        self.btn_back.draw(screen)

    def draw_intro_cutscene(self):
        self.draw_image_cutscene(
            "cutscene_incial.png",
            "O COMEÇO DA NN LEAGUE",
            [
                "Antes dos poderes, antes do Havoc Squad, antes da lenda...",
                "existia apenas uma quadra e um grupo improvável de jogadores.",
                "Essa é a origem da NN Basketball League."
            ],
            "Pressione CONTINUAR para começar a história.",
            True
        )

    def draw_cutscene(self):
        level = self.level

        self.draw_image_cutscene(
            level["cutscene"],
            level["title"],
            level["story"],
            level["objective"],
            True
        )

    def draw_court(self):
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

    def draw_character(self, entity):
        char = entity["char"]
        team = entity["team"]
        img = self.tinted_images.get((char, team))

        color = TEAM_1_COLOR if team == 1 else TEAM_2_COLOR

        if img:
            screen.blit(img, (entity["x"], entity["y"]))
            pygame.draw.rect(screen, color, (entity["x"], entity["y"], CHAR_W, CHAR_H), 2)
        else:
            pygame.draw.rect(screen, color, (entity["x"], entity["y"], CHAR_W, CHAR_H))

        if entity is self.player and entity.get("invisible_timer", 0) > 0:
            inv_txt = font_sm.render("INVISÍVEL", True, WHITE)
            screen.blit(inv_txt, (entity["x"] - 20, entity["y"] - 50))

        if entity is self.player and entity.get("ear_timer", 0) > 0:
            pygame.draw.rect(screen, (255, 200, 150), (entity["x"] - 32, entity["y"] + 5, 32, CHAR_H - 10))
            pygame.draw.rect(screen, (255, 200, 150), (entity["x"] + CHAR_W, entity["y"] + 5, 32, CHAR_H - 10))
            pygame.draw.rect(screen, BLACK, (entity["x"] - 32, entity["y"] + 5, 32, CHAR_H - 10), 2)
            pygame.draw.rect(screen, BLACK, (entity["x"] + CHAR_W, entity["y"] + 5, 32, CHAR_H - 10), 2)

        if entity is self.npc and entity.get("stun_timer", 0) > 0:
            stun_txt = font_sm.render("ATORDOADO", True, (255, 255, 0))
            screen.blit(stun_txt, (entity["x"] - 35, entity["y"] - 50))

        name = char if entity is self.player else entity.get("name", char)
        name_txt = font_sm.render(name, True, WHITE)
        screen.blit(name_txt, (entity["x"] + CHAR_W // 2 - name_txt.get_width() // 2, entity["y"] - 25))

    def draw_clone(self):
        if self.player["clone_timer"] <= 0:
            return

        clone_x = self.player["clone_x"]
        clone_y = self.player["clone_y"]

        img = self.tinted_images.get((self.player["char"], 1))

        if img:
            clone_surface = img.copy()
            clone_surface.set_alpha(150)
            screen.blit(clone_surface, (clone_x, clone_y))
        else:
            surf = pygame.Surface((CHAR_W, CHAR_H), pygame.SRCALPHA)
            surf.fill((80, 80, 180, 160))
            screen.blit(surf, (clone_x, clone_y))

        pygame.draw.rect(screen, WHITE, (clone_x, clone_y, CHAR_W, CHAR_H), 2)

        tag = font_sm.render("CLONE", True, WHITE)
        screen.blit(tag, (clone_x + CHAR_W // 2 - tag.get_width() // 2, clone_y - 20))

    def draw_game(self):
        self.draw_court()

        score_txt = font_lg.render(f"{self.score[0]} x {self.score[1]}", True, WHITE)
        pygame.draw.rect(screen, BLACK, (WIDTH // 2 - 100, 10, 200, 70), border_radius=15)
        screen.blit(score_txt, (WIDTH // 2 - score_txt.get_width() // 2, 15))

        level_txt = font_sm.render(
            f"Fase {self.level['level']} - {self.level['title']} | Meta: {self.level['target_score']} pontos",
            True,
            WHITE
        )
        screen.blit(level_txt, (20, 20))

        objective_txt = font_sm.render(self.level["objective"], True, (255, 255, 120))
        screen.blit(objective_txt, (20, 45))

        enemy_txt = font_sm.render(f"Inimigo: {self.npc['name']} - {self.level['enemy_team']}", True, TEAM_2_COLOR)
        screen.blit(enemy_txt, (20, 70))

        self.draw_clone()
        self.draw_character(self.player)
        self.draw_character(self.npc)

        pygame.draw.circle(screen, BALL_COLOR, (int(self.ball["x"]), int(self.ball["y"])), BALL_RAD)
        pygame.draw.circle(screen, BLACK, (int(self.ball["x"]), int(self.ball["y"])), BALL_RAD, 2)

        if self.ball["holder"] == "player":
            mx, my = pygame.mouse.get_pos()

            if self.player["char"] == "Rafael" and self.player["throw_buff"] > 0:
                path = predict_ball_path(self.ball, mx, my, get_player_throw_power(self.player))

                if len(path) > 1:
                    pygame.draw.lines(screen, (255, 220, 40), False, path, 3)

                    for point in path[::12]:
                        pygame.draw.circle(screen, (255, 245, 160), point, 3)
            else:
                pygame.draw.line(screen, WHITE, (self.player["x"] + CHAR_W // 2, self.player["y"] + 15), (mx, my), 2)

            pygame.draw.circle(screen, (255, 0, 0), (mx, my), 5)

            if can_start_dunk(self.player, self.ball):
                dunk_txt = font_md.render("DUNK: aperte F perto da cesta", True, (255, 230, 80))
                screen.blit(dunk_txt, (WIDTH // 2 - dunk_txt.get_width() // 2, HEIGHT - 105))

        if self.player["dunk_active"] > 0:
            sequence = self.player["dunk_sequence"]
            index = self.player["dunk_index"]
            timer = max(0, self.player["dunk_timer"])

            pygame.draw.rect(screen, BLACK, (WIDTH // 2 - 310, 105, 620, 115), border_radius=14)
            title = font_md.render("DUNK QTE", True, (255, 230, 80))
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

        if self.player["ability_cd"] > 0:
            cd_txt = font_md.render(f"Poder: {self.player['ability_cd'] // 60}s", True, (255, 70, 70))
        else:
            cd_txt = font_md.render("Poder: PRONTO (E)", True, (70, 255, 70))

        screen.blit(cd_txt, (20, HEIGHT - 50))

        if self.message_timer > 0:
            msg = font_md.render(self.message, True, WHITE)
            pygame.draw.rect(screen, BLACK, (WIDTH // 2 - 420, 95, 840, 50), border_radius=12)
            screen.blit(msg, (WIDTH // 2 - msg.get_width() // 2, 105))

    def draw_result(self):
        screen.fill((20, 20, 35))

        if self.state == "WIN":
            title = font_xl.render("VITÓRIA!", True, (255, 215, 0))
            msg = f"{self.level['player_char']} venceu o desafio!"

            if self.level_index + 1 < len(STORY_LEVELS):
                self.btn_next.text = "PRÓXIMA FASE"
            else:
                self.btn_next.text = "FINAL DA HISTÓRIA"

            self.btn_next.draw(screen)

        else:
            title = font_xl.render("DERROTA", True, (255, 80, 80))
            msg = "O inimigo venceu. Tente novamente."
            self.btn_retry.draw(screen)

        screen.blit(title, (WIDTH // 2 - title.get_width() // 2, 120))

        msg_txt = font_md.render(msg, True, WHITE)
        screen.blit(msg_txt, (WIDTH // 2 - msg_txt.get_width() // 2, 250))

        score_txt = font_lg.render(f"Placar: {self.score[0]} x {self.score[1]}", True, WHITE)
        screen.blit(score_txt, (WIDTH // 2 - score_txt.get_width() // 2, 310))

        self.btn_menu.draw(screen)

    def draw_ending(self):
        screen.fill((10, 10, 25))

        title = font_xl.render("NN LEAGUE NASCEU!", True, (255, 215, 0))
        screen.blit(title, (WIDTH // 2 - title.get_width() // 2, 90))

        lines = [
            "A cesta final atravessou o aro.",
            "O Havoc Squad caiu.",
            "E a NN Basketball League deixou de ser apenas um time.",
            "Virou uma lenda da quadra.",
            "",
            "Fim da primeira temporada."
        ]

        y = 230
        for line in lines:
            txt = font_md.render(line, True, WHITE)
            screen.blit(txt, (WIDTH // 2 - txt.get_width() // 2, y))
            y += 45

        self.btn_menu.draw(screen)

    def apply_gravity(self, entity):
        gravity = GRAVITY

        if entity is self.player and entity.get("john_float_timer", 0) > 0 and entity["vel_y"] > 0:
            gravity *= 0.22

        entity["vel_y"] += gravity

        if entity is self.player and entity.get("john_float_timer", 0) > 0 and entity["vel_y"] > 0:
            entity["vel_y"] = min(entity["vel_y"], 3.0)

        entity["y"] += entity["vel_y"]

        if entity["y"] >= GROUND_Y - CHAR_H:
            entity["y"] = GROUND_Y - CHAR_H
            entity["vel_y"] = 0
            entity["is_jumping"] = False

    def update_player(self):
        keys = pygame.key.get_pressed()

        speed = 6
        jump_power = -16

        char = self.player["char"]
        ability_paused = is_player_timed_ability_active(self.player)

        if char == "John Jonh":
            speed = 9
            jump_power = -19

        if char == "Rafael":
            jump_power = -21

        if self.player["speed_buff"] > 0:
            speed += 3
            self.player["speed_buff"] -= 1

        if self.player["jackpot_timer"] > 0:
            speed += 5
            jump_power -= 5
            self.player["jackpot_timer"] -= 1

        if self.player["dunk_active"] > 0:
            interrupted = self.player["stun_timer"] > 0 or self.player["knockback_timer"] > 0
            lost_ball = self.ball["holder"] != "player"

            if interrupted or lost_ball:
                if interrupted or self.ball["holder"] is None:
                    self.fail_dunk()
                else:
                    self.cancel_dunk()
            else:
                self.player["dunk_timer"] -= 1
                update_dunk_position(self.player)
                self.player["vel_y"] = 0

                if (
                    self.player["dunk_ready_to_score"] > 0
                    and self.player["dunk_anim_timer"] >= DUNK_ANIM_TIMER
                ):
                    self.finish_dunk()
                    return

                if self.player["dunk_timer"] <= 0:
                    self.fail_dunk()

                return

        if self.player["dash_timer"] > 0:
            self.player["dash_timer"] -= 1
            self.player["x"] += self.player["facing"] * 24

            if self.ball["holder"] == "npc":
                dist = math.hypot(self.player["x"] - self.npc["x"], self.player["y"] - self.npc["y"])

                if dist < 60:
                    self.ball["holder"] = "player"
                    self.npc["stun_timer"] = 80
                    self.message = "Henrique roubou a bola no dash!"
                    self.message_timer = 100
        else:
            if keys[pygame.K_a]:
                self.player["x"] -= speed
                self.player["facing"] = -1

            if keys[pygame.K_d]:
                self.player["x"] += speed
                self.player["facing"] = 1

            if (keys[pygame.K_w] or keys[pygame.K_SPACE]) and not self.player["is_jumping"]:
                self.player["vel_y"] = jump_power
                self.player["is_jumping"] = True

        self.player["x"] = clamp(self.player["x"], 0, WIDTH - CHAR_W)

        if self.player["ability_cd"] > 0 and not ability_paused:
            self.player["ability_cd"] -= 1

        if self.player["invisible_timer"] > 0:
            self.player["invisible_timer"] -= 1

        if self.player["ear_timer"] > 0:
            self.player["ear_timer"] -= 1
            self.apply_ear_power()

        if self.player["clone_timer"] > 0:
            self.player["clone_timer"] -= 1
            self.update_clone()

        if self.player["john_float_timer"] > 0:
            self.player["john_float_timer"] -= 1

        self.apply_gravity(self.player)

    def use_player_ability(self):
        if self.player["ability_cd"] > 0:
            return

        char = self.player["char"]

        if char == "Henrique":
            self.player["dash_timer"] = 12
            self.player["ability_cd"] = 300
            self.message = "Henrique disparou em velocidade!"
            self.message_timer = 120

        elif char == "Natan":
            self.player["invisible_timer"] = 180
            self.player["ability_cd"] = 360
            self.message = "Natan ficou invisível!"
            self.message_timer = 120

        elif char == "Presscinotti":
            self.player["ear_timer"] = 220
            self.player["ability_cd"] = 360
            self.message = "Presscinotti ativou as orelhas gigantes!"
            self.message_timer = 120

        elif char == "Rafael":
            self.player["throw_buff"] = 240
            self.player["ability_cd"] = 360
            self.message = "Rafael concentrou força máxima!"
            self.message_timer = 120

        elif char == "Diogo":
            self.player["speed_buff"] = 300
            self.player["throw_buff"] = 300
            self.player["ability_cd"] = 420
            self.message = "Diogo ativou a Bolacha Turbo!"
            self.message_timer = 120

        elif char == "Paulo":
            self.player["ability_cd"] = 480
            result = random.choice(["BUFF", "JACKPOT", "DEBUFF"])

            if result == "BUFF":
                self.player["speed_buff"] = 300
                self.player["throw_buff"] = 300
                self.message = "Paulo girou a roleta: BUFF!"
            elif result == "JACKPOT":
                self.player["jackpot_timer"] = 500
                self.message = "JACKPOT ÉPICO DO PAULO!"
            else:
                self.player["speed_buff"] = 80
                self.message = "A roleta quase deu ruim, mas Paulo continuou!"

            self.message_timer = 150

        elif char == "Miguel":
            self.player["clone_timer"] = 300
            self.player["ability_cd"] = 360
            self.player["clone_x"] = clamp(self.player["x"] - self.player["facing"] * 75, 0, WIDTH - CHAR_W)
            self.player["clone_y"] = self.player["y"]
            self.message = "Miguel invocou um clone!"
            self.message_timer = 120

        elif char == "John Jonh":
            self.player["john_float_timer"] = 300
            self.player["ability_cd"] = 360
            self.message = "John Jonh ficou leve como o vento!"
            self.message_timer = 120

    def start_dunk(self):
        if not can_start_dunk(self.player, self.ball):
            return

        hoop_x, hoop_y = get_attack_hoop(self.player["team"])
        self.player["dunk_active"] = 1
        self.player["dunk_timer"] = DUNK_TIMER
        self.player["dunk_anim_timer"] = 0
        self.player["dunk_ready_to_score"] = 0
        self.player["dunk_sequence"] = [random.choice(DUNK_KEYS) for _ in range(DUNK_SEQUENCE_LEN)]
        self.player["dunk_index"] = 0
        self.player["dunk_start_x"] = self.player["x"]
        self.player["dunk_start_y"] = self.player["y"]
        self.player["dunk_target_x"] = clamp(hoop_x - CHAR_W / 2, 0, WIDTH - CHAR_W)
        self.player["dunk_target_y"] = clamp(hoop_y - DUNK_HOLD_OFFSET_Y, 0, GROUND_Y - CHAR_H)
        self.player["vel_y"] = 0
        self.ball["holder"] = "player"
        self.message = "Dunk iniciado! Complete o QTE!"
        self.message_timer = 90

    def cancel_dunk(self):
        self.player["dunk_active"] = 0
        self.player["dunk_timer"] = 0
        self.player["dunk_anim_timer"] = 0
        self.player["dunk_ready_to_score"] = 0
        self.player["dunk_sequence"] = []
        self.player["dunk_index"] = 0

    def fail_dunk(self):
        hoop_x, _ = get_attack_hoop(self.player["team"])
        direction = -1 if hoop_x > WIDTH / 2 else 1
        safe_x = clamp(hoop_x + direction * (DUNK_RANGE_X + 70), BALL_RAD, WIDTH - BALL_RAD)
        safe_y = clamp(HOOP_Y + 55, BALL_RAD, GROUND_Y - BALL_RAD)

        self.cancel_dunk()
        self.player["x"] = clamp(safe_x - CHAR_W / 2, 0, WIDTH - CHAR_W)
        self.player["y"] = clamp(safe_y - CHAR_H / 2, 0, GROUND_Y - CHAR_H)

        if self.ball["holder"] == "player":
            self.ball["holder"] = None

        self.ball["x"] = safe_x
        self.ball["y"] = safe_y
        self.ball["vel_x"] = direction * 9
        self.ball["vel_y"] = -7
        self.ball["dunk_no_score_timer"] = DUNK_NO_SCORE_TIMER

        self.message = "Dunk falhou!"
        self.message_timer = 90

    def finish_dunk(self):
        self.cancel_dunk()
        self.ball["score_override"] = 2
        self.score[0] += 2
        self.reset_after_point()
        self.message = "DUNK!"
        self.message_timer = 120

        if self.score[0] >= self.level["target_score"]:
            self.unlock_next_level()
            self.state = "WIN"

    def handle_dunk_qte(self, key):
        if self.player["dunk_active"] <= 0:
            return

        sequence = self.player["dunk_sequence"]
        index = self.player["dunk_index"]

        if index < len(sequence) and key == sequence[index]:
            self.player["dunk_index"] += 1

            if self.player["dunk_index"] >= len(sequence):
                self.player["dunk_ready_to_score"] = 1
        else:
            self.fail_dunk()

    def apply_ear_power(self):
        left_ear = (self.player["x"] - 32, self.player["y"] + 5, 32, CHAR_H - 10)
        right_ear = (self.player["x"] + CHAR_W, self.player["y"] + 5, 32, CHAR_H - 10)
        npc_rect = (self.npc["x"], self.npc["y"], CHAR_W, CHAR_H)

        hit_left = rects_overlap(left_ear, npc_rect)
        hit_right = rects_overlap(right_ear, npc_rect)

        if hit_left or hit_right:
            direction = -1 if hit_left else 1
            self.npc["knockback_timer"] = 18
            self.npc["knockback_vx"] = direction * 15
            self.npc["stun_timer"] = 40

            if self.ball["holder"] == "npc":
                self.ball["holder"] = None
                self.ball["vel_x"] = direction * 12
                self.ball["vel_y"] = -9

    def update_clone(self):
        self.player["clone_x"] = clamp(self.player["x"] - self.player["facing"] * 75, 0, WIDTH - CHAR_W)
        self.player["clone_y"] = self.player["y"]

        clone_rect = (self.player["clone_x"], self.player["clone_y"], CHAR_W, CHAR_H)
        npc_rect = (self.npc["x"], self.npc["y"], CHAR_W, CHAR_H)

        if rects_overlap(clone_rect, npc_rect):
            direction = 1 if self.npc["x"] > self.player["clone_x"] else -1
            self.npc["knockback_timer"] = 12
            self.npc["knockback_vx"] = direction * 10
            self.npc["stun_timer"] = 25

            if self.ball["holder"] == "npc":
                self.ball["holder"] = "player"
                self.message = "O clone do Miguel roubou a bola!"
                self.message_timer = 100

        if self.ball["holder"] is None:
            cx = self.player["clone_x"] + CHAR_W // 2
            cy = self.player["clone_y"] + CHAR_H // 2
            dist = math.hypot(cx - self.ball["x"], cy - self.ball["y"])

            if dist < CATCH_DIST + 10:
                self.ball["vel_x"] *= -0.8
                self.ball["vel_y"] = -12

    def update_npc_ai(self):
        difficulty = self.level["difficulty"]
        npc_speed = 2.4 + difficulty * 0.42
        npc_jump_chance = 0.004 + difficulty * 0.002
        npc_accuracy = min(0.30 + difficulty * 0.055, 0.88)

        if self.npc["stun_timer"] > 0:
            self.npc["stun_timer"] -= 1
            self.apply_gravity(self.npc)
            return

        if self.npc["knockback_timer"] > 0:
            self.npc["knockback_timer"] -= 1
            self.npc["x"] += self.npc["knockback_vx"]
            self.npc["knockback_vx"] *= 0.82
            self.npc["x"] = clamp(self.npc["x"], 0, WIDTH - CHAR_W)
            self.apply_gravity(self.npc)
            return

        if self.ball["holder"] == "player":
            target_x = self.player["x"]

            if self.player["invisible_timer"] > 0:
                target_x = self.ball["x"] + random.randint(-220, 220)

        elif self.ball["holder"] == "npc":
            target_x = 170
        else:
            target_x = self.ball["x"]

        if self.npc["x"] + CHAR_W // 2 < target_x:
            self.npc["x"] += npc_speed
            self.npc["facing"] = 1
        elif self.npc["x"] + CHAR_W // 2 > target_x:
            self.npc["x"] -= npc_speed
            self.npc["facing"] = -1

        self.npc["x"] = clamp(self.npc["x"], 0, WIDTH - CHAR_W)

        if random.random() < npc_jump_chance and not self.npc["is_jumping"]:
            if self.ball["y"] < self.npc["y"] + 15 or self.ball["holder"] == "npc":
                self.npc["vel_y"] = -16
                self.npc["is_jumping"] = True

        if self.ball["holder"] == "npc":
            self.npc["throw_timer"] += 1

            should_throw = self.npc["x"] < WIDTH * 0.45 or self.npc["throw_timer"] > max(85 - difficulty * 5, 25)

            if should_throw:
                self.npc_throw(npc_accuracy)
                self.npc["throw_timer"] = 0

        if self.ball["holder"] == "player":
            dist = math.hypot(self.npc["x"] - self.player["x"], self.npc["y"] - self.player["y"])

            steal_chance = 0.004 + difficulty * 0.0015

            if dist < 42 and random.random() < steal_chance and self.player["invisible_timer"] <= 0:
                self.ball["holder"] = "npc"
                self.message = f"{self.npc['name']} roubou a bola!"
                self.message_timer = 90

        self.apply_gravity(self.npc)

    def update_ball(self):
        prev_ball_y = self.ball["y"]

        if self.ball.get("dunk_no_score_timer", 0) > 0:
            self.ball["dunk_no_score_timer"] -= 1

        if self.ball["holder"] == "player":
            self.ball["x"] = self.player["x"] + CHAR_W // 2
            self.ball["y"] = self.player["y"] + 16
            self.ball["vel_x"] = 0
            self.ball["vel_y"] = 0

        elif self.ball["holder"] == "npc":
            self.ball["x"] = self.npc["x"] + CHAR_W // 2
            self.ball["y"] = self.npc["y"] + 16
            self.ball["vel_x"] = 0
            self.ball["vel_y"] = 0

        else:
            self.ball["vel_y"] += GRAVITY
            self.ball["x"] += self.ball["vel_x"]
            self.ball["y"] += self.ball["vel_y"]

            if self.ball["y"] >= GROUND_Y - BALL_RAD:
                self.ball["y"] = GROUND_Y - BALL_RAD
                self.ball["vel_y"] *= -0.7
                self.ball["vel_x"] *= 0.9

            if self.ball["x"] <= BALL_RAD:
                self.ball["x"] = BALL_RAD
                self.ball["vel_x"] *= -0.8

            if self.ball["x"] >= WIDTH - BALL_RAD:
                self.ball["x"] = WIDTH - BALL_RAD
                self.ball["vel_x"] *= -0.8

            resolve_hoop_collisions(self.ball)
            self.check_catch()

        self.check_score(prev_ball_y)

    def check_catch(self):
        px = self.player["x"] + CHAR_W // 2
        py = self.player["y"] + CHAR_H // 2
        nx = self.npc["x"] + CHAR_W // 2
        ny = self.npc["y"] + CHAR_H // 2

        dist_player = math.hypot(px - self.ball["x"], py - self.ball["y"])
        dist_npc = math.hypot(nx - self.ball["x"], ny - self.ball["y"])

        if dist_player < CATCH_DIST:
            self.ball["holder"] = "player"

        elif dist_npc < CATCH_DIST:
            self.ball["holder"] = "npc"

    def player_throw(self, target_x, target_y):
        if self.ball["holder"] != "player":
            return

        if self.player["dunk_active"] > 0:
            return

        angle = math.atan2(target_y - self.ball["y"], target_x - self.ball["x"])

        power = get_player_throw_power(self.player)

        if self.player["throw_buff"] > 0:
            self.player["throw_buff"] -= 60

        self.ball["vel_x"] = math.cos(angle) * power
        self.ball["vel_y"] = math.sin(angle) * power
        self.ball["holder"] = None
        self.ball["shot_origin_x"] = self.player["x"] + CHAR_W / 2
        self.ball["shot_origin_y"] = self.player["y"] + CHAR_H / 2
        self.ball["score_override"] = None

    def npc_throw(self, accuracy):
        if self.ball["holder"] != "npc":
            return

        target_x = 120
        target_y = HEIGHT - 350

        error_range = int((1.0 - accuracy) * 230)
        error = random.randint(-error_range, error_range)

        angle = math.atan2(
            target_y - self.ball["y"],
            target_x + error - self.ball["x"]
        )

        power = 22 + self.level["difficulty"] * 1.35

        self.ball["vel_x"] = math.cos(angle) * power
        self.ball["vel_y"] = math.sin(angle) * power
        self.ball["holder"] = None
        self.ball["shot_origin_x"] = self.npc["x"] + CHAR_W / 2
        self.ball["shot_origin_y"] = self.npc["y"] + CHAR_H / 2
        self.ball["score_override"] = None

    def check_score(self, prev_ball_y):
        scored = False
        points = 0

        if (
            self.ball.get("dunk_no_score_timer", 0) <= 0
            and ball_crossed_hoop(prev_ball_y, self.ball, LEFT_HOOP_X1, LEFT_HOOP_X2)
        ):
            points = get_score_points_from_origin(self.ball, 2)
            self.score[1] += points
            scored = True

        elif (
            self.ball.get("dunk_no_score_timer", 0) <= 0
            and ball_crossed_hoop(prev_ball_y, self.ball, RIGHT_HOOP_X1, RIGHT_HOOP_X2)
        ):
            points = get_score_points_from_origin(self.ball, 1)
            self.score[0] += points
            scored = True

        if scored:
            self.reset_after_point()
            self.message = f"Cesta de {points} pontos!"
            self.message_timer = 120

            if self.score[0] >= self.level["target_score"]:
                self.unlock_next_level()
                self.state = "WIN"

            elif self.score[1] >= self.level["target_score"]:
                self.state = "LOSE"

    def reset_after_point(self):
        self.player["x"] = 200
        self.player["y"] = GROUND_Y - CHAR_H
        self.player["vel_y"] = 0
        self.player["is_jumping"] = False
        self.player["dash_timer"] = 0
        self.player["dunk_active"] = 0
        self.player["dunk_timer"] = 0
        self.player["dunk_anim_timer"] = 0
        self.player["dunk_ready_to_score"] = 0
        self.player["dunk_sequence"] = []
        self.player["dunk_index"] = 0
        self.player["stun_timer"] = 0
        self.player["knockback_timer"] = 0
        self.player["knockback_vx"] = 0

        self.npc["x"] = WIDTH - 250
        self.npc["y"] = GROUND_Y - CHAR_H
        self.npc["vel_y"] = 0
        self.npc["is_jumping"] = False
        self.npc["stun_timer"] = 0
        self.npc["knockback_timer"] = 0

        self.ball["x"] = WIDTH // 2
        self.ball["y"] = HEIGHT // 2 - 100
        self.ball["vel_x"] = 0
        self.ball["vel_y"] = 0
        self.ball["holder"] = None
        self.ball["dunk_no_score_timer"] = 0
        self.ball["shot_origin_x"] = None
        self.ball["shot_origin_y"] = None
        self.ball["score_override"] = None

        self.message = "Ponto marcado! Bola no centro."
        self.message_timer = 120

    def update_match(self):
        self.update_player()
        self.update_npc_ai()
        self.update_ball()

        if self.message_timer > 0:
            self.message_timer -= 1

    def handle_events(self):
        mouse_pos = pygame.mouse.get_pos()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False

            if self.state == "MENU":
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if self.btn_start.is_clicked(mouse_pos):
                        self.start_intro_cutscene()

                    elif self.btn_level_select.is_clicked(mouse_pos):
                        self.state = "LEVEL_SELECT"

                    elif self.btn_reset_save.is_clicked(mouse_pos):
                        self.reset_progress()

                    elif self.btn_quit.is_clicked(mouse_pos):
                        self.running = False

            elif self.state == "LEVEL_SELECT":
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if self.btn_back.is_clicked(mouse_pos):
                        self.state = "MENU"

                    for i, btn in enumerate(self.level_buttons):
                        if btn.is_clicked(mouse_pos):
                            level = STORY_LEVELS[i]

                            if level["level"] <= self.unlocked_level:
                                self.start_level(i)

            elif self.state == "INTRO_CUTSCENE":
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if self.btn_continue.is_clicked(mouse_pos):
                        self.start_level(0)

                    elif self.btn_back.is_clicked(mouse_pos):
                        self.state = "MENU"

                if event.type == pygame.KEYDOWN:
                    if event.key in [pygame.K_RETURN, pygame.K_SPACE]:
                        self.start_level(0)

            elif self.state == "CUTSCENE":
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if self.btn_continue.is_clicked(mouse_pos):
                        self.reset_match()
                        self.state = "PLAYING"

                    elif self.btn_back.is_clicked(mouse_pos):
                        self.state = "MENU"

                if event.type == pygame.KEYDOWN:
                    if event.key in [pygame.K_RETURN, pygame.K_SPACE]:
                        self.reset_match()
                        self.state = "PLAYING"

            elif self.state == "PLAYING":
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    self.player_throw(mouse_pos[0], mouse_pos[1])

                if event.type == pygame.KEYDOWN:
                    if self.player["dunk_active"] > 0:
                        qte_key = qte_key_from_event(event)

                        if qte_key:
                            self.handle_dunk_qte(qte_key)
                            continue

                    if event.key == pygame.K_f:
                        self.start_dunk()

                    elif event.key == pygame.K_e:
                        self.use_player_ability()

                    elif event.key == pygame.K_ESCAPE:
                        self.state = "MENU"

            elif self.state == "WIN":
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if self.btn_next.is_clicked(mouse_pos):
                        if self.level_index + 1 < len(STORY_LEVELS):
                            self.start_level(self.level_index + 1)
                        else:
                            self.state = "ENDING"

                    elif self.btn_menu.is_clicked(mouse_pos):
                        self.state = "MENU"

            elif self.state == "LOSE":
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if self.btn_retry.is_clicked(mouse_pos):
                        self.start_level(self.level_index)

                    elif self.btn_menu.is_clicked(mouse_pos):
                        self.state = "MENU"

            elif self.state == "ENDING":
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if self.btn_menu.is_clicked(mouse_pos):
                        self.state = "MENU"

    def draw(self):
        if self.state == "MENU":
            self.draw_menu()

        elif self.state == "LEVEL_SELECT":
            self.draw_level_select()

        elif self.state == "INTRO_CUTSCENE":
            self.draw_intro_cutscene()

        elif self.state == "CUTSCENE":
            self.draw_cutscene()

        elif self.state == "PLAYING":
            self.draw_game()

        elif self.state in ["WIN", "LOSE"]:
            self.draw_result()

        elif self.state == "ENDING":
            self.draw_ending()

    def run(self):
        while self.running:
            clock.tick(FPS)

            self.handle_events()

            if self.state == "PLAYING":
                self.update_match()

            self.draw()
            pygame.display.flip()

        pygame.quit()
        sys.exit()


if __name__ == "__main__":
    game = StoryMode()
    game.run()
