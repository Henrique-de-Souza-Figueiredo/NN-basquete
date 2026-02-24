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

ROLETA_OUTCOMES = ["BUFF_BOLACHA", "BUFF_PULO", "BUFF_FORCA", "DEBUFF_PULO", "DEBUFF_VELOCIDADE", "DEBUFF_FORCA",
                   "JACKPOT"]
ROLETA_WEIGHTS = [0, 0, 5, 5, 5, 0, 50]


def generate_room_code():
    while True:
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
        if code not in rooms: return code


def room_physics_loop(room_code):
    while room_code in rooms and rooms[room_code]['game_started']:
        room = rooms[room_code]
        ball = room['ball']

        # 1. FÍSICA DA BOLA
        if ball['holder'] is None:
            ball['vel_y'] += GRAVITY
            ball['x'] += ball['vel_x']
            ball['y'] += ball['vel_y']

            ball_floor_hit = GROUND_Y - BALL_RAD
            if ball['y'] >= ball_floor_hit:
                ball['y'] = ball_floor_hit;
                ball['vel_y'] *= -0.7;
                ball['vel_x'] *= 0.9
            if ball['x'] <= BALL_RAD or ball['x'] >= WIDTH - BALL_RAD: ball['vel_x'] *= -0.8

            for pid, p in room['players'].items():
                if p.get('roleta_state') == 'CUTSCENE': continue
                char_center_x = p['x'] + CHAR_W // 2
                char_center_y = p['y'] + CHAR_H // 2
                dist = math.hypot(char_center_x - ball['x'], char_center_y - ball['y'])
                if dist < CATCH_DIST: ball['holder'] = pid; break

                if p.get('clone_timer', 0) > 0:
                    clone_offset = -(CHAR_W + 10) if p['team'] == 1 else (CHAR_W + 10)
                    clone_dist = math.hypot((char_center_x + clone_offset) - ball['x'], char_center_y - ball['y'])
                    if clone_dist < CATCH_DIST: ball['holder'] = pid; break
        else:
            holder_id = ball['holder']
            if holder_id in room['players']:
                p = room['players'][holder_id]
                if p.get('roleta_state') == 'CUTSCENE':
                    ball['holder'] = None
                else:
                    ball['x'], ball['y'] = p['x'] + CHAR_W // 2, p['y'] + CHAR_H // 3
                    ball['vel_x'], ball['vel_y'] = 0, 0

        # 2. PONTUAÇÃO E FIM DE JOGO
        hoop_y_zone = HEIGHT - 340
        score_changed = False
        if ball['y'] > hoop_y_zone - 30 and ball['y'] < hoop_y_zone:
            if 95 <= ball['x'] <= 145 and ball['vel_y'] > 0:
                room['score'][1] += 2;
                score_changed = True
            elif (WIDTH - 145) <= ball['x'] <= (WIDTH - 95) and ball['vel_y'] > 0:
                room['score'][0] += 2;
                score_changed = True

        if score_changed:
            ball['x'], ball['y'], ball['holder'] = WIDTH // 2, HEIGHT // 2 - 100, None
            if room['score'][0] >= MAX_SCORE:
                room['game_started'], room['game_over'], room['winner_team'] = False, True, 1
            elif room['score'][1] >= MAX_SCORE:
                room['game_started'], room['game_over'], room['winner_team'] = False, True, 2

        if room.get('game_over'): break

        # 3. GERENCIAMENTO DE ESTADOS E TIMERS
        for pid, p in room['players'].items():
            if p.get('invisible_timer', 0) > 0: p['invisible_timer'] -= 1
            if p.get('ear_timer', 0) > 0: p['ear_timer'] -= 1
            if p.get('clone_timer', 0) > 0: p['clone_timer'] -= 1
            if p.get('cookie_buff_timer', 0) > 0: p['cookie_buff_timer'] -= 1
            if p.get('stun_timer', 0) > 0: p['stun_timer'] -= 1

            # --- LÓGICA DO DASH DO HENRIQUE ---
            if p.get('dash_timer', 0) > 0:
                p['dash_timer'] -= 1
                p['x'] += p.get('dash_dir', 1) * 22  # Velocidade do Dash
                p['x'] = max(0, min(p['x'], WIDTH - 30))  # Não deixa sair da tela

                # Verifica colisão com quem está com a bola durante o dash
                holder_id = room['ball']['holder']
                if holder_id and holder_id != pid and holder_id in room['players']:
                    enemy = room['players'][holder_id]
                    dist = math.hypot(p['x'] - enemy['x'], p['y'] - enemy['y'])
                    if dist < 50 and enemy.get('jackpot_timer', 0) <= 0:
                        room['ball']['holder'] = pid  # Rouba a bola
                        enemy['stun_timer'] = 120  # Paralisado por 2 segundos
                        p['dash_timer'] = 0  # Finaliza o dash na hora do impacto
            # -----------------------------------

            r_state = p.get('roleta_state', 'IDLE')
            if r_state == 'SPINNING':
                p['roleta_timer'] -= 1
                if p['roleta_timer'] <= 0:
                    outcome = random.choices(ROLETA_OUTCOMES, weights=ROLETA_WEIGHTS, k=1)[0]
                    p['roleta_result'] = outcome
                    if outcome == "JACKPOT":
                        p['roleta_state'] = 'CUTSCENE'; p['roleta_timer'] = 180
                    else:
                        p['roleta_state'] = 'FINISHED';
                        p['roleta_timer'] = 120
                        if outcome == "BUFF_BOLACHA":
                            p['cookie_buff_timer'] = 300
                        elif outcome == "BUFF_PULO":
                            p['jump_buff_timer'] = 300
                        elif outcome == "BUFF_FORCA":
                            p['throw_buff_timer'] = 300
                        elif outcome == "DEBUFF_PULO":
                            p['jump_debuff_timer'] = 300
                        elif outcome == "DEBUFF_VELOCIDADE":
                            p['speed_debuff_timer'] = 300
                        elif outcome == "DEBUFF_FORCA":
                            p['throw_debuff_timer'] = 300
            elif r_state == 'CUTSCENE':
                p['roleta_timer'] -= 1
                if p['roleta_timer'] <= 0: p['roleta_state'] = 'FINISHED'; p['roleta_timer'] = 120; p[
                    'jackpot_timer'] = 900
            elif r_state == 'FINISHED':
                p['roleta_timer'] -= 1
                if p['roleta_timer'] <= 0: p['roleta_state'] = 'IDLE'

            if p.get('jackpot_timer', 0) > 0: p['jackpot_timer'] -= 1
            if p.get('jump_buff_timer', 0) > 0: p['jump_buff_timer'] -= 1
            if p.get('throw_buff_timer', 0) > 0: p['throw_buff_timer'] -= 1
            if p.get('jump_debuff_timer', 0) > 0: p['jump_debuff_timer'] -= 1
            if p.get('speed_debuff_timer', 0) > 0: p['speed_debuff_timer'] -= 1
            if p.get('throw_debuff_timer', 0) > 0: p['throw_debuff_timer'] -= 1

            if p.get('ear_timer', 0) > 0:
                for enemy_id, enemy in room['players'].items():
                    if enemy['team'] != p['team'] and enemy.get('jackpot_timer', 0) <= 0:
                        dist = math.hypot(p['x'] - enemy['x'], p['y'] - enemy['y'])
                        if dist < 60:
                            if enemy['x'] < p['x']:
                                enemy['x'] -= 10
                            else:
                                enemy['x'] += 10
        time.sleep(1 / FPS)


def handle_client(conn, addr):
    player_id, room_code = None, None
    try:
        initial_data = pickle.loads(conn.recv(BUFFER_SIZE))
        if initial_data[0] == "CREATE":
            room_code = generate_room_code()
            rooms[room_code] = {
                'players': {}, 'game_started': False, 'game_over': False, 'winner_team': None, 'host_id': 1,
                'score': [0, 0],
                'ball': {'x': WIDTH // 2, 'y': HEIGHT // 2 - 100, 'vel_x': 0, 'vel_y': 0, 'holder': None}
            }
            player_id, team = 1, 1
            rooms[room_code]['players'][player_id] = {'char': None, 'team': team, 'x': 0, 'y': 0}
            conn.send(pickle.dumps(("SUCCESS", room_code, player_id, team)))

        elif initial_data[0] == "JOIN":
            room_code = initial_data[1]
            if room_code in rooms and not rooms[room_code]['game_started']:
                player_id = len(rooms[room_code]['players']) + 1
                team = 1 if player_id % 2 != 0 else 2
                rooms[room_code]['players'][player_id] = {'char': None, 'team': team, 'x': 0, 'y': 0}
                conn.send(pickle.dumps(("SUCCESS", room_code, player_id, team)))
            else:
                conn.send(pickle.dumps(("ERROR", "Sala indisponível."))); return

        while True:
            client_data = pickle.loads(conn.recv(BUFFER_SIZE))
            if not client_data: break
            room = rooms[room_code]
            player = room['players'][player_id]

            if room.get('game_over'):
                conn.send(pickle.dumps(room))
                continue

            if not room['game_started']:
                if client_data.get('action') == 'UPDATE_LOBBY':
                    player['team'] = client_data.get('team', player['team'])
                    if client_data.get('char'): player['char'] = client_data['char']
                elif client_data.get('action') == 'START_GAME' and player_id == room['host_id']:
                    room['game_started'] = True
                    for p_data in room['players'].values():
                        p_data['x'] = 200 if p_data['team'] == 1 else WIDTH - 250
                        p_data['y'] = GROUND_Y - CHAR_H
                        # Adicionado stun_timer e dash_timer ao zerar
                        keys_to_reset = ['invisible_timer', 'ear_timer', 'clone_timer', 'cookie_buff_timer',
                                         'jackpot_timer', 'jump_buff_timer', 'throw_buff_timer',
                                         'jump_debuff_timer', 'speed_debuff_timer', 'throw_debuff_timer',
                                         'stun_timer', 'dash_timer']
                        for k in keys_to_reset: p_data[k] = 0
                        p_data['roleta_state'] = 'IDLE';
                        p_data['roleta_result'] = None;
                        p_data['roleta_timer'] = 0
                    threading.Thread(target=room_physics_loop, args=(room_code,)).start()
            else:
                if 'x' in client_data and player.get('roleta_state') != 'CUTSCENE':
                    # O servidor ignora o X do cliente se ele estiver dando dash, para não bugar a investida
                    if player.get('dash_timer', 0) <= 0:
                        player['x'] = client_data['x']
                    # Aceitamos sempre o Y para que a gravidade local (pulo) funcione fluidamente
                    player['y'] = client_data['y']

                action = client_data.get('action')
                if action == 'THROW' and room['ball']['holder'] == player_id and player.get(
                        'roleta_state') != 'CUTSCENE':
                    tx, ty = client_data['target_x'], client_data['target_y']
                    angle = math.atan2(ty - room['ball']['y'], tx - room['ball']['x'])
                    power = 25
                    if player['char'] == "Rafael": power = 35
                    if player.get('jackpot_timer', 0) > 0:
                        power += 15
                    elif player.get('throw_buff_timer', 0) > 0:
                        power += 10
                    elif player.get('throw_debuff_timer', 0) > 0:
                        power -= 10
                    room['ball']['vel_x'] = math.cos(angle) * power
                    room['ball']['vel_y'] = math.sin(angle) * power
                    room['ball']['holder'] = None
                    room['ball']['y'] -= 10

                elif action == 'USE_ABILITY' and player.get('roleta_state') != 'CUTSCENE':
                    char = player['char']
                    # --- NOVO PODER DO HENRIQUE: Aplica o Dash no servidor ---
                    if char == "Henrique":
                        player['dash_timer'] = 12  # Dura 12 frames (rapidíssimo)
                        player['dash_dir'] = client_data.get('facing', 1)

                    elif char == "Natan":
                        player['invisible_timer'] = 180
                    elif char == "Presscinotti":
                        player['ear_timer'] = 240
                    elif char == "Diogo":
                        for p in room['players'].values():
                            if p['team'] == player['team']: p['cookie_buff_timer'] = 300
                    elif char == "Miguel":
                        player['clone_timer'] = 300
                    elif char == "Paulo" and player.get('roleta_state') == 'IDLE' and player.get('jackpot_timer',
                                                                                                 0) <= 0:
                        player['roleta_state'] = 'SPINNING';
                        player['roleta_timer'] = 120

            conn.send(pickle.dumps(room))
    except Exception as e:
        pass
    finally:
        if room_code and room_code in rooms and player_id in rooms[room_code]['players']:
            del rooms[room_code]['players'][player_id]
        conn.close()


while True:
    conn, addr = server.accept()
    threading.Thread(target=handle_client, args=(conn, addr)).start()