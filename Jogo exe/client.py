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

pygame.init()


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
        return "johnjohn"

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


def make_team_tinted_image(image, team):
    tinted = image.copy().convert_alpha()
    overlay = pygame.Surface(tinted.get_size(), pygame.SRCALPHA)

    if team == 1:
        overlay.fill((40, 80, 255, 95))
    else:
        overlay.fill((255, 40, 40, 95))

    tinted.blit(overlay, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)
    return tinted


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
        self.current_goal_sound = None

        self.btn_create = Button("CRIAR SALA", WIDTH // 2 - 220, 430, 200, 60, TEAM_1_COLOR)
        self.btn_join = Button("ENTRAR", WIDTH // 2 + 20, 430, 200, 60, TEAM_2_COLOR)
        self.btn_quit_game = Button("SAIR DO JOGO", WIDTH // 2 - 120, 520, 240, 55, (180, 40, 40))

        self.host_ip_rect = pygame.Rect(WIDTH // 2 - 160, 250, 320, 45)
        self.room_code_rect = pygame.Rect(WIDTH // 2 - 100, 340, 200, 50)

        self.btn_start_game = Button("INICIAR", WIDTH - 220, 20, 200, 60, BALL_COLOR)
        self.btn_team_blue = Button("TIME AZUL", 50, 80, 180, 40, TEAM_1_COLOR)
        self.btn_team_red = Button("TIME VERM.", 240, 80, 180, 40, TEAM_2_COLOR)

        self.btn_leave_lobby = Button("SAIR DA SALA", WIDTH - 240, HEIGHT - 70, 220, 50, (180, 40, 40))
        self.btn_leave_match = Button("SAIR", WIDTH - 130, 15, 110, 45, (180, 40, 40))
        self.btn_skip_replay = Button("SKIP", WIDTH - 150, HEIGHT - 70, 130, 50, (220, 170, 40), BLACK)

        self.btn_exit = Button("VOLTAR AO MENU", WIDTH // 2 - 130, HEIGHT - 100, 260, 60, (220, 50, 50))

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

    def stop_replay_local(self):
        self.replay_playing = False
        self.replay_frames = []
        self.replay_index = 0
        self.replay_tick = 0

        if self.current_goal_sound:
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
            self.stop_replay_local()

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

        if score_team == 1:
            cesta_txt = font_md.render("CESTA DO TIME AZUL!", True, TEAM_1_COLOR)
        elif score_team == 2:
            cesta_txt = font_md.render("CESTA DO TIME VERMELHO!", True, TEAM_2_COLOR)
        else:
            cesta_txt = font_md.render("CESTA!", True, WHITE)

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
        self.btn_quit_game.draw(screen)

        if self.error_msg:
            err = font_sm.render(self.error_msg, True, (200, 0, 0))
            screen.blit(err, (WIDTH // 2 - err.get_width() // 2, 585))

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

        winners = []
        losers = []

        for p_data in self.server_data["players"].values():
            if p_data["char"]:
                if p_data["team"] == winner_team:
                    winners.append(p_data["char"])
                else:
                    losers.append(p_data["char"])

        start_x_win = WIDTH // 2 - (len(winners) * (self.card_w + 20)) // 2
        y_win = HEIGHT // 2 - self.card_h // 2 - 20

        for i, char_name in enumerate(winners):
            x = start_x_win + i * (self.card_w + 20)
            img = self.char_images.get(char_name)
            char_color = CHARACTERS_INFO[char_name]["color"]

            if img:
                screen.blit(img, (x, y_win))
            else:
                pygame.draw.rect(screen, char_color, (x, y_win, self.card_w, self.card_h))
                name_fallback = font_sm.render(char_name, True, BLACK)
                screen.blit(name_fallback, (x + 10, y_win + self.card_h // 2))

            pygame.draw.rect(screen, JACKPOT_COLOR, (x - 5, y_win - 5, self.card_w + 10, self.card_h + 10), 5)

            name_txt = font_md.render(char_name, True, winner_color)
            screen.blit(name_txt, (x + self.card_w // 2 - name_txt.get_width() // 2, y_win + self.card_h + 10))

        self.btn_exit.draw(screen)

    def draw_player_image(self, p_data, color):
        char_name = p_data.get("char")
        team = p_data.get("team", 1)
        img = self.tinted_small_images.get((char_name, team))

        if img:
            screen.blit(img, (p_data["x"], p_data["y"]))
            pygame.draw.rect(screen, color, (p_data["x"], p_data["y"], CHAR_W, CHAR_H), 2)
        else:
            pygame.draw.rect(screen, color, (p_data["x"], p_data["y"], CHAR_W, CHAR_H))

    def draw_game(self):
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

            pygame.draw.line(screen, WHITE, (self.player_x + 15, self.player_y + 15), (mx, my), 2)
            pygame.draw.circle(screen, (255, 0, 0), (mx, my), 5)

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
                            data_to_send["action"] = "SKIP_REPLAY"
                            continue

                    if self.replay_playing:
                        continue

                    if my_p.get("roleta_state") == "CUTSCENE":
                        continue

                    if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                        if self.server_data.get("ball", {}).get("holder") == self.my_id:
                            data_to_send["action"] = "THROW"
                            data_to_send["target_x"] = mouse_pos[0]
                            data_to_send["target_y"] = mouse_pos[1]

                    if event.type == pygame.KEYDOWN and event.key == pygame.K_e:
                        server_cd = my_p.get("ability_cd", self.ability_cooldown)

                        if server_cd <= 0 and my_p.get("stun_timer", 0) <= 0:
                            data_to_send["action"] = "USE_ABILITY"
                            data_to_send["facing"] = self.facing

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

                        elif self.btn_quit_game.is_clicked(mouse_pos):
                            running = False
                            self.stop_local_server()

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

                            if is_dashing or is_knocked or is_stunned:
                                self.player_x = my_p["x"]

                            keys = pygame.key.get_pressed()

                            if not is_stunned and not is_dashing and not is_knocked:
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

                            self.vel_y += self.gravity
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

                if not self.server_data:
                    self.state = "MENU"
                    self.error_msg = "Desconectado do servidor."

                else:
                    if self.server_data.get("game_over"):
                        self.state = "GAME_OVER"

                    elif self.state == "LOBBY" and self.server_data["game_started"]:
                        self.state = "PLAYING"

                        my_data = self.server_data["players"][self.my_id]
                        self.player_x = my_data["x"]
                        self.player_y = my_data["y"]

                    elif self.state == "PLAYING" and self.server_data and self.my_id in self.server_data["players"]:
                        my_data = self.server_data["players"][self.my_id]

                        is_replay_active = self.server_data.get("replay_timer", 0) > 0
                        is_dashing = my_data.get("dash_timer", 0) > 0
                        is_knocked = my_data.get("knockback_timer", 0) > 0
                        is_stunned = my_data.get("stun_timer", 0) > 0
                        has_ball = self.server_data["ball"].get("holder") == self.my_id

                        if is_replay_active or is_dashing or is_knocked or is_stunned or has_ball:
                            self.player_x = my_data["x"]
                            self.player_y = my_data["y"]

            self.record_replay_frame()

            if self.state == "MENU":
                self.draw_menu()

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

            pygame.display.flip()

        if self.net.connected:
            self.net.disconnect()

        self.stop_local_server()

        pygame.quit()
        sys.exit()


if __name__ == "__main__":
    game = GameClient()
    game.run()