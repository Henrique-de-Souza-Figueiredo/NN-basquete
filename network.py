import socket
import pickle
import json
import os
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

    def set_server(self, server_host, server_port=None):
        self.server = server_host
        self.port = server_port if server_port else PORT
        self.addr = (self.server, self.port)
        save_server_config(self.server, self.port)

    def connect(self, action, room_code=""):
        try:
            self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client.connect(self.addr)

            if action == "CREATE":
                initial_data = ("CREATE",)

            elif action == "JOIN":
                initial_data = ("JOIN", room_code)

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

    def disconnect(self):
        try:
            self.client.close()
        except socket.error:
            pass

        self.connected = False