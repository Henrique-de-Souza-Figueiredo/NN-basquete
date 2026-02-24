# ==========================================
# NN LEAGUE - CONFIGURAÇÕES GERAIS
# ==========================================

HOST = 'localhost'
PORT = 5555
BUFFER_SIZE = 4096

# ==========================================
# NN LEAGUE - CONFIGURAÇÕES GERAIS
# ==========================================

# ... (outras configurações de HOST, PORT, WIDTH, HEIGHT...)

WIDTH = 1280
HEIGHT = 720
FPS = 60
GRAVITY = 0.8

# PONTUAÇÃO MÁXIMA PARA ACABAR O JOGO
MAX_SCORE = 2  # Mude para 30 ou mais quando for jogar pra valer!

# ... (Cores...)

# Imagem da Jaula (Deve estar na mesma pasta)
CAGE_IMG = "cage.png"

# --- NOVAS DEFINIÇÕES DE TAMANHO (Arena Grande / Personagens Pequenos) ---
CHAR_W = 30
CHAR_H = 50
# ... (resto do arquivo igual)

WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GRAY = (50, 50, 50)
TEAM_1_COLOR = (0, 0, 255)
TEAM_2_COLOR = (255, 0, 0)
BALL_COLOR = (255, 140, 0)
COURT_COLOR = (222, 184, 135)

# Cores da Roleta
BUFF_COLOR = (50, 255, 50)
DEBUFF_COLOR = (255, 50, 50)
JACKPOT_COLOR = (255, 215, 0)
JACKPOT_AURA_COLOR = (0, 255, 100)

# --- NOVAS DEFINIÇÕES DE TAMANHO (Arena Grande / Personagens Pequenos) ---
CHAR_W = 30      # Largura do personagem (antes era 50)
CHAR_H = 50      # Altura do personagem (antes era 80)
FLOOR_H = 60     # Altura do chão a partir da base (antes era 100, agora tem mais ar)
BALL_RAD = 12    # Raio da bola um pouco menor (antes era 15)
CATCH_DIST = 30  # Distância para pegar a bola (antes era 40)

# Onde o pé do personagem toca o chão
GROUND_Y = HEIGHT - FLOOR_H

# --- INFORMAÇÕES DOS PERSONAGENS ---
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
        "desc": "Gira uma roleta com chance de Buffs, Debuffs ou JACKPOT ÉPICO (Cutscene e Poder Total)!",
        "img": "paulo.png", "color": (255, 215, 0)
    }
}

CHARACTERS = list(CHARACTERS_INFO.keys())