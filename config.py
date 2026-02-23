# ==========================================
# NN LEAGUE - CONFIGURAÇÕES GERAIS
# ==========================================

HOST = 'localhost'
PORT = 5555
BUFFER_SIZE = 2048

WIDTH = 1280
HEIGHT = 720
FPS = 60
GRAVITY = 0.8
MAX_SCORE = 30
MATCH_TIME = 5 * 60

WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GRAY = (50, 50, 50)
TEAM_1_COLOR = (0, 0, 255)
TEAM_2_COLOR = (255, 0, 0)
BALL_COLOR = (255, 140, 0)
COURT_COLOR = (222, 184, 135)

# --- INFORMAÇÕES DOS PERSONAGENS (Para a Tela de Seleção) ---
# O nome do arquivo da foto deve ser exatamente o que está em 'img'
CHARACTERS_INFO = {
    "Henrique": {
        "desc": "Rouba a bola do inimigo mais próximo rapidamente.",
        "img": "henrique.png", "color": (100, 100, 250)
    },
    "Natan": {
        "desc": "Fica invisível para os inimigos por um curto período de tempo.",
        "img": "natan.png", "color": (150, 150, 150)
    },
    "John Jonh": {
        "desc": "Poder de ficar mais leve, correndo mais rápido e pulando alto.",
        "img": "john.png", "color": (50, 200, 50)
    },
    "Presscinotti": {
        "desc": "Expande a orelha para proteger e barrar a passagem de inimigos.",
        "img": "presscinotti.png", "color": (250, 150, 50)
    },
    "Rafael": {
        "desc": "Habilidade de jogar a bola muito mais longe e pular mais alto.",
        "img": "rafael.png", "color": (200, 50, 50)
    },
    "Diogo": {
        "desc": "Concede bolachas amaldiçoadas que dão buffs aleatórios para os aliados.",
        "img": "diogo.png", "color": (200, 200, 50)
    },
    "Miguel": {
        "desc": "Invoca um clone das sombras que copia todos os seus movimentos.",
        "img": "miguel.png", "color": (100, 50, 150)
    },
    "Paulo": {
        "desc": "Gira uma roleta de apostas para ganhar efeitos na arena (Chance de Jackpot Épico!).",
        "img": "paulo.png", "color": (255, 215, 0)
    }
}

# Cria a lista de nomes automaticamente a partir do dicionário
CHARACTERS = list(CHARACTERS_INFO.keys())