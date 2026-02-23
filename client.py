import pygame
import sys
import os
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
        self.state = "MENU"
        self.my_id = None
        self.my_team = None
        self.is_host = False
        self.room_code = ""
        self.selected_char_idx = 0
        self.player_x, self.player_y = 0, 0
        self.error_msg = ""
        self.server_data = None

        # --- NOVAS VARIÁVEIS DE FÍSICA E PODERES ---
        self.vel_y = 0
        self.is_jumping = False
        self.speed = 6
        self.jump_power = -16
        self.gravity = 0.8
        self.ability_cooldown = 0

        # Botões Menu Principal
        self.btn_create = Button("CRIAR SALA", WIDTH // 2 - 220, 400, 200, 60, TEAM_1_COLOR)
        self.btn_join = Button("ENTRAR", WIDTH // 2 + 20, 400, 200, 60, TEAM_2_COLOR)

        # Botões do Lobby
        self.btn_start_game = Button("INICIAR", WIDTH - 220, 20, 200, 60, BALL_COLOR)
        self.btn_team_blue = Button("TIME AZUL", 50, 80, 180, 40, TEAM_1_COLOR)
        self.btn_team_red = Button("TIME VERM.", 240, 80, 180, 40, TEAM_2_COLOR)

        self.char_images = {}
        self.card_w = 140
        self.card_h = 400

        for name, info in CHARACTERS_INFO.items():
            img_path = info["img"]
            if os.path.exists(img_path):
                img = pygame.image.load(img_path).convert_alpha()
                self.char_images[name] = pygame.transform.scale(img, (self.card_w, self.card_h))
            else:
                self.char_images[name] = None

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
                    if pid != self.my_id and p_data['char'] == name:
                        is_taken = True

            if self.char_images[name]:
                screen.blit(self.char_images[name], (x, start_y))
            else:
                color = CHARACTERS_INFO[name]["color"]
                pygame.draw.rect(screen, color, rect)
                name_txt = font_sm.render(name, True, BLACK)
                screen.blit(name_txt, (x + 10, start_y + self.card_h // 2))

            if is_taken:
                dark_surface = pygame.Surface((self.card_w, self.card_h), pygame.SRCALPHA)
                dark_surface.fill((0, 0, 0, 180))
                screen.blit(dark_surface, (x, start_y))
                taken_txt = font_sm.render("EM USO", True, (255, 50, 50))
                screen.blit(taken_txt, (x + self.card_w // 2 - taken_txt.get_width() // 2, start_y + self.card_h // 2))

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

    def draw_game(self):
        screen.fill((40, 45, 55))

        floor_rect = pygame.Rect(0, HEIGHT - 100, WIDTH, 100)
        pygame.draw.rect(screen, (205, 133, 63), floor_rect)
        pygame.draw.rect(screen, (139, 69, 19), floor_rect, 5)

        pygame.draw.line(screen, WHITE, (WIDTH // 2, HEIGHT - 100), (WIDTH // 2, HEIGHT), 5)

        pygame.draw.rect(screen, GRAY, (80, HEIGHT - 400, 15, 300))
        pygame.draw.rect(screen, WHITE, (75, HEIGHT - 450, 20, 100))
        pygame.draw.rect(screen, TEAM_1_COLOR, (75, HEIGHT - 450, 20, 100), 3)
        pygame.draw.rect(screen, (255, 69, 0), (95, HEIGHT - 380, 50, 8))
        pygame.draw.line(screen, WHITE, (95, HEIGHT - 372), (110, HEIGHT - 330), 2)
        pygame.draw.line(screen, WHITE, (145, HEIGHT - 372), (130, HEIGHT - 330), 2)
        pygame.draw.line(screen, WHITE, (110, HEIGHT - 372), (130, HEIGHT - 330), 2)
        pygame.draw.line(screen, WHITE, (130, HEIGHT - 372), (110, HEIGHT - 330), 2)

        pygame.draw.rect(screen, GRAY, (WIDTH - 95, HEIGHT - 400, 15, 300))
        pygame.draw.rect(screen, WHITE, (WIDTH - 95, HEIGHT - 450, 20, 100))
        pygame.draw.rect(screen, TEAM_2_COLOR, (WIDTH - 95, HEIGHT - 450, 20, 100), 3)
        pygame.draw.rect(screen, (255, 69, 0), (WIDTH - 145, HEIGHT - 380, 50, 8))
        pygame.draw.line(screen, WHITE, (WIDTH - 145, HEIGHT - 372), (WIDTH - 130, HEIGHT - 330), 2)
        pygame.draw.line(screen, WHITE, (WIDTH - 95, HEIGHT - 372), (WIDTH - 110, HEIGHT - 330), 2)
        pygame.draw.line(screen, WHITE, (WIDTH - 130, HEIGHT - 372), (WIDTH - 110, HEIGHT - 330), 2)
        pygame.draw.line(screen, WHITE, (WIDTH - 110, HEIGHT - 372), (WIDTH - 130, HEIGHT - 330), 2)

        if not self.server_data: return

        score = self.server_data['score']
        score_text = font_lg.render(f"{score[0]} x {score[1]}", True, WHITE)
        pygame.draw.rect(screen, BLACK, (WIDTH // 2 - 100, 10, 200, 70), border_radius=15)
        pygame.draw.rect(screen, TEAM_1_COLOR, (WIDTH // 2 - 100, 10, 100, 70), 4, border_radius=15)
        pygame.draw.rect(screen, TEAM_2_COLOR, (WIDTH // 2, 10, 100, 70), 4, border_radius=15)
        screen.blit(score_text, (WIDTH // 2 - score_text.get_width() // 2, 15))

        for p_id, p_data in self.server_data['players'].items():
            if p_data['char'] is None: continue

            # Não desenha inimigo invisível (Natan)
            if p_data.get('invisible_timer', 0) > 0 and p_data['team'] != self.my_team:
                continue

            color = TEAM_1_COLOR if p_data['team'] == 1 else TEAM_2_COLOR
            if p_id == self.my_id:
                pygame.draw.rect(screen, (255, 255, 0), (p_data['x'] - 3, p_data['y'] - 3, 56, 86), 3)

            # Efeito visual de Escudo (Gabriel)
            if p_data.get('shield_timer', 0) > 0:
                pygame.draw.circle(screen, (0, 255, 255), (p_data['x'] + 25, p_data['y'] + 40), 60, 4)

            pygame.draw.rect(screen, color, (p_data['x'], p_data['y'], 50, 80))

            # Avisos de status
            if p_data.get('invisible_timer', 0) > 0:
                inv = font_sm.render("INVISÍVEL", True, WHITE)
                screen.blit(inv, (p_data['x'], p_data['y'] - 65))

            # Efeito visual de Congelado (Lucas usou em você)
            if p_data.get('stun_timer', 0) > 0:
                stun_txt = font_sm.render("CONGELADO!", True, (100, 200, 255))
                screen.blit(stun_txt, (p_data['x'] - 15, p_data['y'] + 30))

            name_tag = font_sm.render(p_data['char'], True, WHITE)
            screen.blit(name_tag, (p_data['x'] + 25 - name_tag.get_width() // 2, p_data['y'] - 25))

        ball = self.server_data['ball']
        pygame.draw.circle(screen, BALL_COLOR, (int(ball['x']), int(ball['y'])), 15)
        pygame.draw.circle(screen, BLACK, (int(ball['x']), int(ball['y'])), 15, 2)

        if ball.get('holder') == self.my_id and self.server_data['players'][self.my_id].get('stun_timer', 0) <= 0:
            mx, my = pygame.mouse.get_pos()
            pygame.draw.line(screen, WHITE, (self.player_x + 25, self.player_y + 20), (mx, my), 2)
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

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                    if self.net.connected: self.net.disconnect()

                if self.state == "PLAYING" and self.server_data:
                    am_i_stunned = self.server_data['players'][self.my_id].get('stun_timer', 0) > 0

                    if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and not am_i_stunned:
                        if self.server_data.get('ball', {}).get('holder') == self.my_id:
                            data_to_send['action'] = 'THROW'
                            data_to_send['target_x'] = mouse_pos[0]
                            data_to_send['target_y'] = mouse_pos[1]

                    if event.type == pygame.KEYDOWN and event.key == pygame.K_e and not am_i_stunned:
                        if self.ability_cooldown == 0:
                            data_to_send['action'] = 'USE_ABILITY'
                            self.ability_cooldown = 300  # 5 segundos

                if self.state == "MENU":
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
                                        if pid != self.my_id and p_data['char'] == char_name: is_taken = True
                                if not is_taken: self.selected_char_idx = i

                        if self.is_host and self.btn_start_game.is_clicked(mouse_pos):
                            self.net.send({'action': 'START_GAME'})

            if self.state in ["LOBBY", "PLAYING"]:
                if self.state == "LOBBY":
                    data_to_send['action'] = 'UPDATE_LOBBY'
                    data_to_send['char'] = CHARACTERS[self.selected_char_idx]
                    data_to_send['team'] = self.my_team

                elif self.state == "PLAYING" and self.server_data:
                    am_i_stunned = self.server_data['players'][self.my_id].get('stun_timer', 0) > 0

                    # Se NÃO estiver atordoado, pode andar e pular
                    if not am_i_stunned:
                        char_name = CHARACTERS[self.selected_char_idx]
                        if char_name == "John Jonh":
                            self.speed = 9; self.jump_power = -20
                        elif char_name == "Rafael":
                            self.speed = 6; self.jump_power = -22
                        else:
                            self.speed = 6; self.jump_power = -16

                        keys = pygame.key.get_pressed()
                        if keys[pygame.K_a]: self.player_x -= self.speed
                        if keys[pygame.K_d]: self.player_x += self.speed
                        self.player_x = max(0, min(self.player_x, WIDTH - 50))

                        if (keys[pygame.K_w] or keys[pygame.K_SPACE]) and not self.is_jumping:
                            self.vel_y = self.jump_power
                            self.is_jumping = True

                    # Gravidade sempre age (mesmo congelado)
                    self.vel_y += self.gravity
                    self.player_y += self.vel_y

                    if self.player_y >= HEIGHT - 180:
                        self.player_y = HEIGHT - 180
                        self.vel_y = 0
                        self.is_jumping = False

                    if self.ability_cooldown > 0:
                        self.ability_cooldown -= 1

                    data_to_send['x'] = self.player_x
                    data_to_send['y'] = self.player_y

                self.server_data = self.net.send(data_to_send)

                if not self.server_data:
                    self.state = "MENU"
                    self.error_msg = "Desconectado do servidor."
                else:
                    if self.state == "LOBBY" and self.server_data['game_started']:
                        self.state = "PLAYING"
                        my_data = self.server_data['players'][self.my_id]
                        self.player_x = my_data['x']
                        self.player_y = my_data['y']

            if self.state == "MENU":
                self.draw_menu()
            elif self.state == "LOBBY":
                self.draw_lobby()
            elif self.state == "PLAYING":
                self.draw_game()

            pygame.display.flip()

        pygame.quit()
        sys.exit()


if __name__ == "__main__":
    game = GameClient()
    game.run()