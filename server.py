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


def generate_room_code():
    while True:
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
        if code not in rooms: return code


def room_physics_loop(room_code):
    """Calcula a física da bola e processa os cronômetros de habilidades a 60 FPS"""
    while room_code in rooms and rooms[room_code]['game_started']:
        room = rooms[room_code]
        ball = room['ball']

        # 1. FÍSICA DA BOLA
        if ball['holder'] is None:
            ball['vel_y'] += GRAVITY
            ball['x'] += ball['vel_x']
            ball['y'] += ball['vel_y']

            if ball['y'] >= HEIGHT - 115:
                ball['y'] = HEIGHT - 115
                ball['vel_y'] *= -0.7
                ball['vel_x'] *= 0.9

            if ball['x'] <= 15 or ball['x'] >= WIDTH - 15:
                ball['vel_x'] *= -0.8

            for pid, p in room['players'].items():
                dist = math.hypot((p['x'] + 25) - ball['x'], (p['y'] + 40) - ball['y'])
                # Só pode pegar a bola se NÃO estiver congelado
                if dist < 40 and p.get('stun_timer', 0) <= 0:
                    ball['holder'] = pid
                    break
        else:
            holder_id = ball['holder']
            if holder_id in room['players']:
                p = room['players'][holder_id]
                ball['x'] = p['x'] + 25
                ball['y'] = p['y'] + 20
                ball['vel_x'], ball['vel_y'] = 0, 0

        # 2. PONTUAÇÃO (CESTAS)
        if ball['y'] > HEIGHT - 380 and ball['y'] < HEIGHT - 350:
            if 95 <= ball['x'] <= 145 and ball['vel_y'] > 0:
                room['score'][1] += 2
                ball['x'], ball['y'], ball['holder'] = WIDTH // 2, HEIGHT // 2, None
            elif (WIDTH - 145) <= ball['x'] <= (WIDTH - 95) and ball['vel_y'] > 0:
                room['score'][0] += 2
                ball['x'], ball['y'], ball['holder'] = WIDTH // 2, HEIGHT // 2, None

        # 3. CRONÔMETROS DE PODERES
        for pid, p in room['players'].items():
            if p.get('invisible_timer', 0) > 0: p['invisible_timer'] -= 1
            if p.get('shield_timer', 0) > 0: p['shield_timer'] -= 1
            if p.get('stun_timer', 0) > 0: p['stun_timer'] -= 1

        time.sleep(1 / FPS)


def handle_client(conn, addr):
    player_id, room_code = None, None
    try:
        initial_data = pickle.loads(conn.recv(BUFFER_SIZE))
        if initial_data[0] == "CREATE":
            room_code = generate_room_code()
            rooms[room_code] = {
                'players': {}, 'game_started': False, 'host_id': 1, 'score': [0, 0],
                'ball': {'x': WIDTH // 2, 'y': HEIGHT // 2 - 200, 'vel_x': 0, 'vel_y': 0, 'holder': None}
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
                conn.send(pickle.dumps(("ERROR", "Sala indisponível.")))
                return

        while True:
            client_data = pickle.loads(conn.recv(BUFFER_SIZE))
            if not client_data: break

            room = rooms[room_code]
            player = room['players'][player_id]

            if not room['game_started']:
                if client_data.get('action') == 'UPDATE_LOBBY':
                    player['team'] = client_data.get('team', player['team'])
                    if client_data.get('char'): player['char'] = client_data['char']

                elif client_data.get('action') == 'START_GAME' and player_id == room['host_id']:
                    room['game_started'] = True
                    for pid, p_data in room['players'].items():
                        p_data['x'] = 200 if p_data['team'] == 1 else WIDTH - 250
                        p_data['y'] = HEIGHT - 180
                        p_data['invisible_timer'], p_data['shield_timer'], p_data['stun_timer'] = 0, 0, 0
                    threading.Thread(target=room_physics_loop, args=(room_code,)).start()

            else:
                # Recebe a posição do jogador APENAS se ele não estiver congelado
                if 'x' in client_data and player.get('stun_timer', 0) <= 0:
                    player['x'] = client_data['x']
                    player['y'] = client_data['y']

                action = client_data.get('action')

                # Arremesso
                if action == 'THROW' and room['ball']['holder'] == player_id and player.get('stun_timer', 0) <= 0:
                    tx, ty = client_data['target_x'], client_data['target_y']
                    angle = math.atan2(ty - room['ball']['y'], tx - room['ball']['x'])
                    power = 35 if player['char'] == "Rafael" else 25
                    room['ball']['vel_x'] = math.cos(angle) * power
                    room['ball']['vel_y'] = math.sin(angle) * power
                    room['ball']['holder'] = None
                    room['ball']['y'] -= 20

                    # --- SISTEMA COMPLETO DE PODERES ---
                elif action == 'USE_ABILITY' and player.get('stun_timer', 0) <= 0:
                    char = player['char']

                    # Henrique: Rouba a bola de quem está perto (se o inimigo NÃO tiver escudo)
                    if char == "Henrique" and room['ball']['holder'] is not None and room['ball'][
                        'holder'] != player_id:
                        enemy_p = room['players'][room['ball']['holder']]
                        dist = math.hypot(player['x'] - enemy_p['x'], player['y'] - enemy_p['y'])
                        if dist < 120 and enemy_p.get('shield_timer', 0) <= 0:
                            room['ball']['holder'] = player_id

                    # Natan: Invisível
                    elif char == "Natan":
                        player['invisible_timer'] = 180

                    # Paulo: Roleta
                    elif char == "Paulo":
                        if random.randint(1, 100) > 90:
                            room['score'][player['team'] - 1] += 2
                        else:
                            room['ball']['vel_y'], room['ball']['holder'] = -40, None

                    # Gabriel: Escudo (Imune a roubo e congelamento por 4 segs)
                    elif char == "Gabriel":
                        player['shield_timer'] = 240  # 60 frames * 4 segundos

                    # Lucas: Congelar inimigos próximos (se eles não tiverem escudo)
                    elif char == "Lucas":
                        for pid, enemy_p in room['players'].items():
                            if enemy_p['team'] != player['team']:
                                dist = math.hypot(player['x'] - enemy_p['x'], player['y'] - enemy_p['y'])
                                if dist < 200 and enemy_p.get('shield_timer', 0) <= 0:
                                    enemy_p['stun_timer'] = 120  # Congelado por 2 segundos
                                    # Se o inimigo congelado estava com a bola, ela cai
                                    if room['ball']['holder'] == pid:
                                        room['ball']['holder'] = None

                    # Pedro: Dash / Arrancada pra frente
                    elif char == "Pedro":
                        dash_dist = 150 if player['team'] == 1 else -150
                        player['x'] += dash_dist
                        # Impede de atravessar a parede da arena
                        player['x'] = max(0, min(player['x'], WIDTH - 50))

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