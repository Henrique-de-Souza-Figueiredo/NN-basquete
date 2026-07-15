import socket
import pickle
import json
import os
import time  # SPEC-04: medicoes de RTT
from config import PORT, BUFFER_SIZE


CONFIG_FILE = "server_config.json"


def load_server_config():
    default_config = {
        "server_host": "127.0.0.1",
        "server_port": PORT
    }

    if not os.path.exists(CONFIG_FILE):
        save_server_config(default_config["server_host"], default_config["server_port"])
        return default_config

    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)

        return {
            "server_host": data.get("server_host", "127.0.0.1"),
            "server_port": int(data.get("server_port", PORT))
        }

    except Exception:
        return default_config


def save_server_config(server_host, server_port=PORT):
    data = {
        "server_host": server_host,
        "server_port": server_port
    }

    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as file:
            json.dump(data, file, indent=4)
    except Exception as e:
        print(f"[ERRO CONFIG] Não foi possível salvar server_config.json: {e}")


class Network:
    def __init__(self, server_host=None, server_port=None):
        config = load_server_config()

        self.server = server_host if server_host else config["server_host"]
        self.port = server_port if server_port else config["server_port"]
        self.addr = (self.server, self.port)

        self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.connected = False
        self.last_rtt = None  # SPEC-04: RTT em ms da ultima medicao de ping

    def set_server(self, server_host, server_port=None):
        self.server = server_host
        self.port = server_port if server_port else PORT
        self.addr = (self.server, self.port)
        save_server_config(self.server, self.port)

    def connect(self, action, room_code="", win_points=None, token=None):
        try:
            self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client.connect(self.addr)

            if action == "CREATE":
                # Host escolhe os pontos para vencer; None -> default do server
                initial_data = ("CREATE", win_points)

            elif action == "JOIN":
                initial_data = ("JOIN", room_code)

            elif action == "REJOIN":
                # SPEC-01: reconexao usando o token recebido no CREATE/JOIN
                initial_data = ("REJOIN", room_code, token)

            else:
                return ("ERROR", "Ação inválida.")

            self.client.send(pickle.dumps(initial_data))
            response = pickle.loads(self.client.recv(BUFFER_SIZE))

            if response[0] == "SUCCESS":
                self.connected = True
                return response

            print(f"[ERRO DE CONEXÃO] {response[1]}")
            return response

        except socket.error as e:
            print(f"[FALHA AO CONECTAR] Servidor offline ou IP incorreto: {e}")
            self.connected = False
            return ("ERROR", "Não foi possível conectar ao servidor.")

        except Exception as e:
            print(f"[ERRO NETWORK] {e}")
            self.connected = False
            return ("ERROR", "Erro inesperado na conexão.")

    def send(self, data):
        try:
            self.client.send(pickle.dumps(data))
            return pickle.loads(self.client.recv(BUFFER_SIZE))

        except socket.error as e:
            print(f"[DESCONECTADO] Erro na rede: {e}")
            self.connected = False
            return None

        except Exception as e:
            print(f"[ERRO SEND] {e}")
            self.connected = False
            return None

    def ping(self):
        """SPEC-04: mede o RTT (ms) enviando PING e aguardando PONG.
        Nao afeta o jogo; usa o socket ja aberto."""
        if not self.connected:
            return None
        try:
            t0 = time.perf_counter()
            self.client.send(pickle.dumps(("PING",)))
            resp = pickle.loads(self.client.recv(BUFFER_SIZE))
            if isinstance(resp, tuple) and resp and resp[0] == "PONG":
                self.last_rtt = round((time.perf_counter() - t0) * 1000, 1)
                return self.last_rtt
        except Exception:
            self.connected = False
        return None

    def disconnect(self):
        try:
            self.client.close()
        except socket.error:
            pass

        self.connected = False