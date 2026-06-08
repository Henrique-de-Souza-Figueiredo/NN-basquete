import pygame
import sys
import os
import math
import random
import json
from config import *

pygame.init()

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


def load_save():
    if not os.path.exists(SAVE_FILE):
        return {"unlocked_level": 1}

    try:
        with open(SAVE_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)

        return {
            "unlocked_level": int(data.get("unlocked_level", 1))
        }

    except Exception:
        return {"unlocked_level": 1}


def save_progress(unlocked_level):
    try:
        with open(SAVE_FILE, "w", encoding="utf-8") as file:
            json.dump({"unlocked_level": unlocked_level}, file, indent=4)
    except Exception:
        pass


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
            "jackpot_timer": 0,
            "roleta_timer": 0
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
            "holder": None
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
            screen.blit(img, (WIDTH // 2 - target_w // 2, HEIGHT // 2 - target_h // 2))

            overlay = pygame.Surface((WIDTH, 190), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 200))
            screen.blit(overlay, (0, HEIGHT - 190))

            title_txt = font_lg.render(title, True, (255, 215, 0))
            screen.blit(title_txt, (40, HEIGHT - 175))

            if objective:
                obj = font_md.render(objective, True, WHITE)
                screen.blit(obj, (40, HEIGHT - 105))

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
        pygame.draw.rect(screen, WHITE, (75, HEIGHT - 410, 20, 100))
        pygame.draw.rect(screen, TEAM_1_COLOR, (75, HEIGHT - 410, 20, 100), 3)
        pygame.draw.rect(screen, (255, 69, 0), (95, HEIGHT - 340, 50, 8))

        pygame.draw.line(screen, WHITE, (95, HEIGHT - 332), (110, HEIGHT - 290), 2)
        pygame.draw.line(screen, WHITE, (145, HEIGHT - 332), (130, HEIGHT - 290), 2)
        pygame.draw.line(screen, WHITE, (110, HEIGHT - 332), (130, HEIGHT - 290), 2)
        pygame.draw.line(screen, WHITE, (130, HEIGHT - 332), (110, HEIGHT - 290), 2)

        pygame.draw.rect(screen, GRAY, (WIDTH - 95, HEIGHT - 360, 15, 300))
        pygame.draw.rect(screen, WHITE, (WIDTH - 95, HEIGHT - 410, 20, 100))
        pygame.draw.rect(screen, TEAM_2_COLOR, (WIDTH - 95, HEIGHT - 410, 20, 100), 3)
        pygame.draw.rect(screen, (255, 69, 0), (WIDTH - 145, HEIGHT - 340, 50, 8))

        pygame.draw.line(screen, WHITE, (WIDTH - 145, HEIGHT - 332), (WIDTH - 130, HEIGHT - 290), 2)
        pygame.draw.line(screen, WHITE, (WIDTH - 95, HEIGHT - 332), (WIDTH - 110, HEIGHT - 290), 2)
        pygame.draw.line(screen, WHITE, (WIDTH - 130, HEIGHT - 332), (WIDTH - 110, HEIGHT - 290), 2)
        pygame.draw.line(screen, WHITE, (WIDTH - 110, HEIGHT - 332), (WIDTH - 130, HEIGHT - 290), 2)

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
            pygame.draw.line(screen, WHITE, (self.player["x"] + CHAR_W // 2, self.player["y"] + 15), (mx, my), 2)
            pygame.draw.circle(screen, (255, 0, 0), (mx, my), 5)

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
        entity["vel_y"] += GRAVITY
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

        if self.player["ability_cd"] > 0:
            self.player["ability_cd"] -= 1

        if self.player["invisible_timer"] > 0:
            self.player["invisible_timer"] -= 1

        if self.player["ear_timer"] > 0:
            self.player["ear_timer"] -= 1
            self.apply_ear_power()

        if self.player["clone_timer"] > 0:
            self.player["clone_timer"] -= 1
            self.update_clone()

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
            self.player["speed_buff"] = 300
            self.player["ability_cd"] = 360
            self.message = "John Jonh ficou leve como o vento!"
            self.message_timer = 120

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

            self.check_catch()

        self.check_score()

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

        angle = math.atan2(target_y - self.ball["y"], target_x - self.ball["x"])

        power = 25

        if self.player["char"] == "Rafael":
            power = 34

        if self.player["throw_buff"] > 0:
            power += 8
            self.player["throw_buff"] -= 60

        if self.player["jackpot_timer"] > 0:
            power += 10

        self.ball["vel_x"] = math.cos(angle) * power
        self.ball["vel_y"] = math.sin(angle) * power
        self.ball["holder"] = None

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

    def check_score(self):
        hoop_y_zone = HEIGHT - 340
        scored = False

        if hoop_y_zone - 30 < self.ball["y"] < hoop_y_zone:
            if 95 <= self.ball["x"] <= 145 and self.ball["vel_y"] > 0:
                self.score[1] += 2
                scored = True

            elif (WIDTH - 145) <= self.ball["x"] <= (WIDTH - 95) and self.ball["vel_y"] > 0:
                self.score[0] += 2
                scored = True

        if scored:
            self.reset_after_point()

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
                    if event.key == pygame.K_e:
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