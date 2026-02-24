import pygame
import sys
import os
import math
import random
from config import *
from network import Network

pygame.init()
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("NN League - Multiplayer")
clock = pygame.time.Clock()

font_sm = pygame.font.SysFont("Arial", 20)
font_md = pygame.font.SysFont("Arial", 32)
font_lg = pygame.font.SysFont("Arial", 64, bold=True)
font_title = pygame.font.SysFont("Arial", 40, bold=True)
font_xl = pygame.font.SysFont("Arial", 100, bold=True)


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

    def is_clicked(self, pos): return self.rect.collidepoint(pos)


class GameClient:
    def __init__(self):
        self.net = Network()
        self.state = "MENU"
        self.my_id, self.my_team, self.is_host = None, None, False
        self.room_code, self.error_msg, self.server_data = "", "", None
        self.selected_char_idx = 0
        self.player_x, self.player_y = 0, 0
        self.vel_y, self.is_jumping = 0, False
        self.speed, self.jump_power, self.gravity = 6, -16, 0.8

        self.ability_cooldown = 0
        self.facing = 1  # 1 = Direita, -1 = Esquerda (Necessário para o Dash)

        self.btn_create = Button("CRIAR SALA", WIDTH // 2 - 220, 400, 200, 60, TEAM_1_COLOR)
        self.btn_join = Button("ENTRAR", WIDTH // 2 + 20, 400, 200, 60, TEAM_2_COLOR)
        self.btn_start_game = Button("INICIAR", WIDTH - 220, 20, 200, 60, BALL_COLOR)
        self.btn_team_blue = Button("TIME AZUL", 50, 80, 180, 40, TEAM_1_COLOR)
        self.btn_team_red = Button("TIME VERM.", 240, 80, 180, 40, TEAM_2_COLOR)

        self.btn_exit = Button("SAIR", WIDTH // 2 - 100, HEIGHT - 100, 200, 60, (220, 50, 50))

        self.char_images = {}
        self.card_w, self.card_h = 140, 400
        for name, info in CHARACTERS_INFO.items():
            if os.path.exists(info["img"]):
                self.char_images[name] = pygame.transform.scale(pygame.image.load(info["img"]).convert_alpha(),
                                                                (self.card_w, self.card_h))
            else:
                self.char_images[name] = None

        self.jackpot_img = None
        if os.path.exists("paulo_dancando.png"):
            self.jackpot_img = pygame.transform.scale(pygame.image.load("paulo_dancando.png").convert_alpha(),
                                                      (self.card_w, self.card_h))

        self.cage_img = None
        if os.path.exists(CAGE_IMG):
            self.cage_w, self.cage_h = 300, 250
            self.cage_img = pygame.transform.scale(pygame.image.load(CAGE_IMG).convert_alpha(),
                                                   (self.cage_w, self.cage_h))

        self.char_rects = []

    def draw_menu(self):
        screen.fill(COURT_COLOR)
        title = font_lg.render("NN LEAGUE", True, BLACK)
        screen.blit(title, (WIDTH // 2 - title.get_width() // 2, 80))
        pygame.draw.rect(screen, WHITE, (WIDTH // 2 - 100, 280, 200, 50), border_radius=8)
        pygame.draw.rect(screen, BLACK, (WIDTH // 2 - 100, 280, 200, 50), 3, border_radius=8)
        code_text = font_md.render(self.room_code, True, BLACK)
        screen.blit(code_text, (WIDTH // 2 - code_text.get_width() // 2, 290))
        info = font_sm.render("Digite o código da sala para entrar:", True, BLACK)
        screen.blit(info, (WIDTH // 2 - 100, 250))
        self.btn_create.draw(screen)
        self.btn_join.draw(screen)
        if self.error_msg:
            err = font_sm.render(self.error_msg, True, (200, 0, 0))
            screen.blit(err, (WIDTH // 2 - err.get_width() // 2, 500))

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
        if self.my_team == 1:
            pygame.draw.rect(screen, (255, 255, 0), self.btn_team_blue.rect, 4, border_radius=12)
        else:
            pygame.draw.rect(screen, (255, 255, 0), self.btn_team_red.rect, 4, border_radius=12)
        if self.server_data:
            y_pos = 140
            for pid, p_data in self.server_data['players'].items():
                p_team_color = TEAM_1_COLOR if p_data['team'] == 1 else TEAM_2_COLOR
                p_char = p_data['char'] if p_data['char'] else "Escolhendo..."
                p_text = f"P{pid}: {p_char}"
                if pid == self.my_id:
                    p_text += " (Você)"
                    pygame.draw.rect(screen, (255, 255, 0), (45, y_pos, 250, 30), 1)
                txt_surf = font_sm.render(p_text, True, p_team_color)
                screen.blit(txt_surf, (50, y_pos + 5))
                y_pos += 35
        total_width = (self.card_w * 8) + (10 * 7)
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
                for pid, p_data in self.server_data['players'].items():
                    if pid != self.my_id and p_data['char'] == name: is_taken = True
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
                screen.blit(taken_txt, (x + self.card_w // 2 - taken_txt.get_width() // 2, start_y + self.card_h // 2))
            if i == self.selected_char_idx: pygame.draw.rect(screen, (255, 215, 0), rect, 5)
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
            dancer = pygame.transform.flip(paulo_img, True, False) if (
                                                                                  pygame.time.get_ticks() // 150) % 2 == 0 else paulo_img
            screen.blit(dancer, (WIDTH // 2 - self.card_w // 2, HEIGHT // 2 - self.card_h // 2))
        dance_txt = font_md.render("* Dança da Vitória *", True, WHITE)
        screen.blit(dance_txt, (WIDTH // 2 - dance_txt.get_width() // 2, HEIGHT - 100))

    def draw_game_over(self):
        if not self.server_data or not self.server_data.get('game_over'): return

        winner_team = self.server_data['winner_team']
        winner_color = TEAM_1_COLOR if winner_team == 1 else TEAM_2_COLOR
        winner_text = "TIME AZUL VENCEU!" if winner_team == 1 else "TIME VERMELHO VENCEU!"

        screen.fill((20, 25, 35))

        title_surf = font_xl.render(winner_text, True, winner_color)
        screen.blit(title_surf, (WIDTH // 2 - title_surf.get_width() // 2, 50))

        score = self.server_data['score']
        score_surf = font_lg.render(f"Placar Final: {score[0]} x {score[1]}", True, WHITE)
        screen.blit(score_surf, (WIDTH // 2 - score_surf.get_width() // 2, 130))

        winners = []
        losers = []
        for p_data in self.server_data['players'].values():
            if p_data['char']:
                if p_data['team'] == winner_team:
                    winners.append(p_data['char'])
                else:
                    losers.append(p_data['char'])

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

        if self.cage_img:
            cage_x, cage_y = WIDTH - self.cage_w - 50, HEIGHT - self.cage_h - 50
            loser_w, loser_h = CHAR_W, CHAR_H
            start_x_lose = cage_x + 20

            for i, char_name in enumerate(losers):
                x = start_x_lose + i * (loser_w + 10)
                y = cage_y + self.cage_h - loser_h - 20
                big_img = self.char_images.get(char_name)
                char_color = CHARACTERS_INFO[char_name]["color"]

                if big_img:
                    small_img = pygame.transform.scale(big_img, (loser_w, loser_h))
                    screen.blit(small_img, (x, y))
                else:
                    pygame.draw.rect(screen, char_color, (x, y, loser_w, loser_h))

            screen.blit(self.cage_img, (cage_x, cage_y))
            loser_txt = font_md.render("Perdedores...", True, GRAY)
            screen.blit(loser_txt, (cage_x + self.cage_w // 2 - loser_txt.get_width() // 2, cage_y - 30))

        self.btn_exit.draw(screen)

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

        if not self.server_data: return

        my_p_data = self.server_data['players'][self.my_id]
        am_i_jackpot = my_p_data.get('jackpot_timer', 0) > 0
        r_state = my_p_data.get('roleta_state', 'IDLE')

        score = self.server_data['score']
        score_text = font_lg.render(f"{score[0]} x {score[1]}", True, WHITE)
        pygame.draw.rect(screen, BLACK, (WIDTH // 2 - 100, 10, 200, 70), border_radius=15)
        pygame.draw.rect(screen, TEAM_1_COLOR, (WIDTH // 2 - 100, 10, 100, 70), 4, border_radius=15)
        pygame.draw.rect(screen, TEAM_2_COLOR, (WIDTH // 2, 10, 100, 70), 4, border_radius=15)
        screen.blit(score_text, (WIDTH // 2 - score_text.get_width() // 2, 15))

        for p_id, p_data in self.server_data['players'].items():
            if p_data['char'] is None: continue
            is_invisible = p_data.get('invisible_timer', 0) > 0
            if is_invisible and p_data['team'] != self.my_team and not am_i_jackpot: continue
            color = TEAM_1_COLOR if p_data['team'] == 1 else TEAM_2_COLOR

            if p_data.get('clone_timer', 0) > 0:
                clone_offset = -40 if p_data['team'] == 1 else 40
                clone_color = (max(0, color[0] - 100), max(0, color[1] - 100), max(0, color[2] - 100))
                pygame.draw.rect(screen, clone_color, (p_data['x'] + clone_offset, p_data['y'], 30, 50))
                c_tag = font_sm.render("Clone", True, WHITE)
                screen.blit(c_tag, (p_data['x'] + clone_offset - 5, p_data['y'] - 20))

            if p_id == self.my_id:
                pygame.draw.rect(screen, (255, 255, 0), (p_data['x'] - 2, p_data['y'] - 2, 34, 54), 3)

            if p_data.get('jackpot_timer', 0) > 0:
                pulse = (math.sin(pygame.time.get_ticks() * 0.01) + 1) * 5
                pygame.draw.circle(screen, (0, 255, 100), (p_data['x'] + 15, p_data['y'] + 25), 40 + pulse, 5)

            pygame.draw.rect(screen, color, (p_data['x'], p_data['y'], 30, 50))

            if p_data.get('ear_timer', 0) > 0:
                pygame.draw.rect(screen, (255, 200, 150), (p_data['x'] - 15, p_data['y'] + 5, 15, 40))
                pygame.draw.rect(screen, (255, 200, 150), (p_data['x'] + 30, p_data['y'] + 5, 15, 40))

            has_buff = p_data.get('cookie_buff_timer', 0) > 0 or p_data.get('jump_buff_timer', 0) > 0 or p_data.get(
                'throw_buff_timer', 0) > 0
            has_debuff = p_data.get('jump_debuff_timer', 0) > 0 or p_data.get('speed_debuff_timer',
                                                                              0) > 0 or p_data.get('throw_debuff_timer',
                                                                                                   0) > 0

            if has_buff and p_data.get('jackpot_timer', 0) <= 0:
                pygame.draw.circle(screen, (50, 255, 50), (p_data['x'] + 15, p_data['y'] + 60), 20, 3)
                buff_txt = font_sm.render("BUFF!", True, (50, 255, 50))
                screen.blit(buff_txt, (p_data['x'] - 10, p_data['y'] - 45))

            if has_debuff:
                pygame.draw.circle(screen, (255, 50, 50), (p_data['x'] + 15, p_data['y'] + 60), 20, 3)
                debuff_txt = font_sm.render("DEBUFF!", True, (255, 50, 50))
                screen.blit(debuff_txt, (p_data['x'] - 15, p_data['y'] - 45))

            # --- EFEITO VISUAL DE ATORDOADO (DASH DO HENRIQUE) ---
            if p_data.get('stun_timer', 0) > 0:
                pygame.draw.circle(screen, (255, 255, 0), (p_data['x'] + 15, p_data['y'] + 25), 35, 3)
                stun_txt = font_sm.render("PARALISADO!", True, (255, 255, 0))
                screen.blit(stun_txt, (p_data['x'] + 15 - stun_txt.get_width() // 2, p_data['y'] - 65))

            if is_invisible:
                inv = font_sm.render("INVISÍVEL", True, WHITE)
                screen.blit(inv, (p_data['x'] - 20, p_data['y'] - 45))

            name_tag = font_sm.render(p_data['char'], True, WHITE)
            screen.blit(name_tag, (p_data['x'] + 15 - name_tag.get_width() // 2, p_data['y'] - 25))

            # ==========================================
            # NOVO BLOCO DA ROLETA (APARECE PARA TODOS)
            # ==========================================
            p_r_state = p_data.get('roleta_state', 'IDLE')
            if p_r_state == 'SPINNING':
                box_color = (random.randint(100, 255), random.randint(100, 255), 0)
                pygame.draw.rect(screen, box_color, (p_data['x'] - 25, p_data['y'] - 60, 80, 25), border_radius=5)
                spin_txt = font_sm.render("ROLETA", True, BLACK)
                screen.blit(spin_txt, (p_data['x'] + 15 - spin_txt.get_width() // 2, p_data['y'] - 58))

            elif p_r_state == 'FINISHED':
                outcome = p_data.get('roleta_result', '')
                if outcome:
                    if "JACKPOT" in outcome:
                        res_color = (255, 215, 0)
                    elif "BUFF" in outcome:
                        res_color = (50, 255, 50)
                    else:
                        res_color = (255, 50, 50)

                    res_txt = font_sm.render(outcome.replace("_", " "), True, res_color)
                    screen.blit(res_txt, (p_data['x'] + 15 - res_txt.get_width() // 2, p_data['y'] - 60))
            # ==========================================

        ball = self.server_data['ball']
        pygame.draw.circle(screen, BALL_COLOR, (int(ball['x']), int(ball['y'])), 10)
        pygame.draw.circle(screen, BLACK, (int(ball['x']), int(ball['y'])), 10, 2)

        if ball.get('holder') == self.my_id and r_state != 'CUTSCENE':
            mx, my = pygame.mouse.get_pos()
            pygame.draw.line(screen, WHITE, (self.player_x + 15, self.player_y + 15), (mx, my), 2)
            pygame.draw.circle(screen, (255, 0, 0), (mx, my), 5)

        if self.ability_cooldown > 0:
            cd_txt = font_md.render(f"Poder: {self.ability_cooldown // 60}s", True, (255, 50, 50))
            screen.blit(cd_txt, (20, HEIGHT - 50))
        else:
            cd_txt = font_md.render("Poder: PRONTO (Aperte E)", True, (50, 255, 50))
            screen.blit(cd_txt, (20, HEIGHT - 50))

    def handle_connection(self, response):
        if response and response[0] == "SUCCESS":
            self.room_code = response[1]
            self.my_id = response[2]
            self.my_team = response[3]
            self.is_host = (self.my_id == 1)
            self.state = "LOBBY"
            self.error_msg = ""
        else:
            self.error_msg = response[1] if response else "Erro de conexão."

    def run(self):
        running = True
        while running:
            clock.tick(FPS)
            mouse_pos = pygame.mouse.get_pos()
            data_to_send = {}

            # ==========================================
            # GERENCIAMENTO DE EVENTOS (TECLADO/MOUSE)
            # ==========================================
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                    if self.net.connected:
                        self.net.disconnect()

                # --- JOGANDO ---
                if self.state == "PLAYING" and self.server_data:
                    my_p = self.server_data['players'][self.my_id]
                    if my_p.get('roleta_state') == 'CUTSCENE':
                        continue
                    if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                        if self.server_data.get('ball', {}).get('holder') == self.my_id:
                            data_to_send['action'] = 'THROW'
                            data_to_send['target_x'] = mouse_pos[0]
                            data_to_send['target_y'] = mouse_pos[1]

                    if event.type == pygame.KEYDOWN and event.key == pygame.K_e:
                        # Só pode usar a habilidade se não estiver paralisado!
                        if self.ability_cooldown == 0 and my_p.get('stun_timer', 0) <= 0:
                            data_to_send['action'] = 'USE_ABILITY'
                            data_to_send['facing'] = self.facing  # Envia a direção do dash
                            if CHARACTERS[self.selected_char_idx] in ["Diogo", "Paulo"]:
                                self.ability_cooldown = 480
                            else:
                                self.ability_cooldown = 360

                # --- MENU ---
                elif self.state == "MENU":
                    if event.type == pygame.KEYDOWN:
                        if event.key == pygame.K_BACKSPACE:
                            self.room_code = self.room_code[:-1]
                        elif len(self.room_code) < 4 and event.unicode.isalnum():
                            self.room_code += event.unicode.upper()
                    if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                        if self.btn_create.is_clicked(mouse_pos):
                            self.handle_connection(self.net.connect("CREATE"))
                        elif self.btn_join.is_clicked(mouse_pos):
                            if len(self.room_code) == 4:
                                self.handle_connection(self.net.connect("JOIN", self.room_code))
                            else:
                                self.error_msg = "O código deve ter 4 dígitos."

                # --- LOBBY ---
                elif self.state == "LOBBY":
                    if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                        if self.btn_team_blue.is_clicked(mouse_pos):
                            self.my_team = 1
                        elif self.btn_team_red.is_clicked(mouse_pos):
                            self.my_team = 2

                        for i, rect in enumerate(self.char_rects):
                            if rect.collidepoint(mouse_pos):
                                char_name = CHARACTERS[i]
                                is_taken = False
                                if self.server_data:
                                    for pid, p_data in self.server_data['players'].items():
                                        if pid != self.my_id and p_data['char'] == char_name:
                                            is_taken = True
                                if not is_taken:
                                    self.selected_char_idx = i

                        if self.is_host and self.btn_start_game.is_clicked(mouse_pos):
                            self.net.send({'action': 'START_GAME'})

                # --- GAME OVER (TELA DE VITÓRIA/DERROTA) ---
                elif self.state == "GAME_OVER":
                    if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                        if self.btn_exit.is_clicked(mouse_pos):
                            # Desconecta e limpa os dados para voltar pro Menu limpo
                            if self.net.connected:
                                self.net.disconnect()
                            self.server_data = None
                            self.room_code = ""
                            self.my_id = None
                            self.my_team = None
                            self.is_host = False
                            self.state = "MENU"

            # ==========================================
            # LÓGICA DE FÍSICA E ENVIO DE DADOS
            # ==========================================
            if self.state in ["LOBBY", "PLAYING"]:
                if self.state == "LOBBY":
                    data_to_send['action'] = 'UPDATE_LOBBY'
                    data_to_send['char'] = CHARACTERS[self.selected_char_idx]
                    data_to_send['team'] = self.my_team

                elif self.state == "PLAYING" and self.server_data:
                    my_p = self.server_data['players'][self.my_id]
                    if my_p.get('roleta_state') != 'CUTSCENE':
                        char_name = CHARACTERS[self.selected_char_idx]

                        # Status base do personagem
                        if char_name == "John Jonh":
                            self.speed = 9;
                            self.jump_power = -19
                        elif char_name == "Rafael":
                            self.speed = 6;
                            self.jump_power = -21
                        else:
                            self.speed = 6;
                            self.jump_power = -16

                        # Aplica Buffs e Debuffs
                        if my_p.get('jackpot_timer', 0) > 0:
                            self.speed += 5;
                            self.jump_power -= 5
                        else:
                            if my_p.get('cookie_buff_timer', 0) > 0: self.speed += 3
                            if my_p.get('jump_buff_timer', 0) > 0: self.jump_power -= 4
                            if my_p.get('speed_debuff_timer', 0) > 0: self.speed -= 3
                            if my_p.get('jump_debuff_timer', 0) > 0: self.jump_power += 5

                        # --- VERIFICAÇÃO DE DASH E STUN ---
                        is_stunned = my_p.get('stun_timer', 0) > 0
                        is_dashing = my_p.get('dash_timer', 0) > 0

                        # Se o servidor informou que estamos dando dash, forçamos o X pro valor do servidor
                        if is_dashing:
                            self.player_x = my_p['x']

                        keys = pygame.key.get_pressed()

                        # Movimentação apenas se NÃO estiver atordoado nem dando dash
                        if not is_stunned and not is_dashing:
                            if keys[pygame.K_a]:
                                self.player_x -= self.speed
                                self.facing = -1
                            if keys[pygame.K_d]:
                                self.player_x += self.speed
                                self.facing = 1

                            self.player_x = max(0, min(self.player_x, WIDTH - 30))

                            if (keys[pygame.K_w] or keys[pygame.K_SPACE]) and not self.is_jumping:
                                self.vel_y = self.jump_power
                                self.is_jumping = True

                        self.vel_y += self.gravity
                        self.player_y += self.vel_y

                        # Colisão com o chão
                        if self.player_y >= HEIGHT - 110:
                            self.player_y = HEIGHT - 110
                            self.vel_y = 0
                            self.is_jumping = False

                        if self.ability_cooldown > 0:
                            self.ability_cooldown -= 1

                    data_to_send['x'] = self.player_x
                    data_to_send['y'] = self.player_y

                # Comunicação com o Servidor
                self.server_data = self.net.send(data_to_send)

                if not self.server_data:
                    self.state = "MENU"
                    self.error_msg = "Desconectado do servidor."
                else:
                    if self.server_data.get('game_over'):
                        self.state = "GAME_OVER"
                    elif self.state == "LOBBY" and self.server_data['game_started']:
                        self.state = "PLAYING"
                        my_data = self.server_data['players'][self.my_id]
                        self.player_x = my_data['x']
                        self.player_y = my_data['y']

            # ==========================================
            # RENDERIZAÇÃO NA TELA
            # ==========================================
            if self.state == "MENU":
                self.draw_menu()
            elif self.state == "LOBBY":
                self.draw_lobby()
            elif self.state == "PLAYING":
                alguem_em_cutscene = False
                if self.server_data:
                    for p in self.server_data['players'].values():
                        if p.get('roleta_state') == 'CUTSCENE':
                            alguem_em_cutscene = True
                            break

                if alguem_em_cutscene:
                    self.draw_cutscene()
                else:
                    self.draw_game()
            elif self.state == "GAME_OVER":
                self.draw_game_over()

            pygame.display.flip()

        pygame.quit()
        sys.exit()


if __name__ == "__main__":
    game = GameClient()
    game.run()