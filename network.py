import socket
import pickle
from config import HOST, PORT, BUFFER_SIZE


class Network:
    def __init__(self):
        self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server = HOST
        self.port = PORT
        self.addr = (self.server, self.port)
        self.connected = False

    # Mudamos aqui: agora room_code é opcional (vazio por padrão) e tiramos o character
    def connect(self, action, room_code=""):
        """
        Faz a conexão inicial com o servidor para CRIAR ou ENTRAR numa sala.
        action: "CREATE" ou "JOIN"
        """
        try:
            self.client.connect(self.addr)

            # Prepara o pacote inicial de dados (sem o personagem agora!)
            if action == "CREATE":
                initial_data = ("CREATE",)
            elif action == "JOIN":
                initial_data = ("JOIN", room_code)

            # Envia o pedido para o servidor
            self.client.send(pickle.dumps(initial_data))

            # Recebe a resposta do servidor
            response = pickle.loads(self.client.recv(BUFFER_SIZE))

            if response[0] == "SUCCESS":
                self.connected = True
                return response
            else:
                print(f"[ERRO DE CONEXÃO] {response[1]}")
                return response

        except socket.error as e:
            print(f"[FALHA AO CONECTAR] Servidor offline ou IP incorreto: {e}")
            return ("ERROR", "Não foi possível conectar ao servidor.")

    def send(self, data):
        """
        Envia as ações do jogador e recebe o estado da arena.
        """
        try:
            self.client.send(pickle.dumps(data))
            return pickle.loads(self.client.recv(BUFFER_SIZE))
        except socket.error as e:
            print(f"[DESCONECTADO] Erro na rede: {e}")
            self.connected = False
            return None

    def disconnect(self):
        """Fecha a conexão limpa com o servidor."""
        self.client.close()
        self.connected = False