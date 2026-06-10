# ==========================================
# NN LEAGUE - CONFIGURAÇÕES DE REDE
# ==========================================

# Para o servidor aceitar conexões pelo Radmin VPN.
HOST = "0.0.0.0"
PORT = 5555
BUFFER_SIZE = 4096

# ==========================================
# NN LEAGUE - CONFIGURAÇÕES GERAIS
# ==========================================

WIDTH = 1280
HEIGHT = 720
FPS = 60
GRAVITY = 0.8

MAX_SCORE = 25

# Agora essa imagem deve estar dentro da pasta imagens/
CAGE_IMG = "cage.png"

WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GRAY = (50, 50, 50)

TEAM_1_COLOR = (0, 0, 255)
TEAM_2_COLOR = (255, 0, 0)

BALL_COLOR = (255, 140, 0)
COURT_COLOR = (222, 184, 135)

BUFF_COLOR = (50, 255, 50)
DEBUFF_COLOR = (255, 50, 50)
JACKPOT_COLOR = (255, 215, 0)
JACKPOT_AURA_COLOR = (0, 255, 100)

CHAR_W = 30
CHAR_H = 50
FLOOR_H = 60
BALL_RAD = 12
CATCH_DIST = 30

GROUND_Y = HEIGHT - FLOOR_H

HOOP_Y = HEIGHT - 340
LEFT_HOOP_X1 = 95
LEFT_HOOP_X2 = 145
RIGHT_HOOP_X1 = WIDTH - 145
RIGHT_HOOP_X2 = WIDTH - 95
HOOP_SCORE_MARGIN_X = 6
HOOP_SCORE_MARGIN_Y = 18
HOOP_RIM_RAD = 5
BACKBOARD_Y = HEIGHT - 410
BACKBOARD_W = 20
BACKBOARD_H = 100
LEFT_BACKBOARD_X = 75
RIGHT_BACKBOARD_X = WIDTH - 95

DUNK_KEYS = ["W", "A", "S", "D"]
DUNK_SEQUENCE_LEN = 6
DUNK_TIMER = 105
DUNK_ANIM_TIMER = 55
DUNK_RANGE_X = 90
DUNK_RANGE_Y = 115
DUNK_HOLD_OFFSET_Y = 42
DUNK_JUMP_ARC = 70
DUNK_NO_SCORE_TIMER = 35

THREE_POINT_DISTANCE = 430

CLASH_KEYS = ["W", "A", "S", "D"]
CLASH_SEQUENCE_LEN = 7
CLASH_TIMER = 135
CLASH_RANGE = 70

CHARACTERS_INFO = {
    "Henrique": {
        "desc": "Rouba a bola do inimigo mais próximo rapidamente.",
        "img": "henrique.png",
        "color": (100, 100, 250)
    },
    "Natan": {
        "desc": "Fica invisível para os inimigos por um curto período de tempo.",
        "img": "natan.png",
        "color": (150, 150, 150)
    },
    "John Jonh": {
        "desc": "Ativa leveza no ar, fazendo John Jonh cair muito mais devagar.",
        "img": "john.png",
        "color": (50, 200, 50)
    },
    "Presscinotti": {
        "desc": "Expande a orelha para proteger e barrar a passagem de inimigos.",
        "img": "presscinotti.png",
        "color": (250, 150, 50)
    },
    "Rafael": {
        "desc": "Ativa força máxima e mostra a trajetória exata do arremesso.",
        "img": "rafael.png",
        "color": (200, 50, 50)
    },
    "Diogo": {
        "desc": "Concede bolachas amaldiçoadas que dão buffs aleatórios para os aliados.",
        "img": "diogo.png",
        "color": (200, 200, 50)
    },
    "Miguel": {
        "desc": "Invoca um clone das sombras que copia todos os seus movimentos.",
        "img": "miguel.png",
        "color": (100, 50, 150)
    },
    "Paulo": {
        "desc": "Gira uma roleta com chance de Buffs, Debuffs ou JACKPOT ÉPICO.",
        "img": "paulo.png",
        "color": (255, 215, 0)
    }
}

CHARACTERS = list(CHARACTERS_INFO.keys())

COSMETICS = {
    "default": {
        "name": "Uniforme Padrao",
        "price": 0,
        "color": (255, 255, 255),
        "accent": (30, 30, 30),
    },
    "street_red": {
        "name": "Jaqueta Rua Vermelha",
        "price": 120,
        "color": (210, 45, 45),
        "accent": (255, 220, 80),
        "effect": "speed",
    },
    "blue_star": {
        "name": "Regata Estrela Azul",
        "price": 160,
        "color": (45, 110, 230),
        "accent": (245, 245, 255),
        "effect": "stars",
    },
    "gold_royal": {
        "name": "Dourado Real",
        "price": 300,
        "color": (235, 190, 45),
        "accent": (90, 45, 10),
        "effect": "shine",
        "hat": "crown",
    },
    "shadow": {
        "name": "Sombra Neon",
        "price": 260,
        "color": (35, 35, 45),
        "accent": (80, 255, 180),
        "effect": "shadow_aura",
    },
    "jackpot_orange": {
        "name": "Jackpot Laranja",
        "price": 380,
        "color": (255, 115, 20),
        "accent": (255, 235, 80),
        "effect": "jackpot",
    },
    "midnight_blue": {
        "name": "Azul Meia-Noite",
        "price": 340,
        "color": (18, 32, 78),
        "accent": (90, 190, 255),
        "effect": "glow",
    },
    "cookie_cream": {
        "name": "Creme Bolacha",
        "price": 220,
        "color": (226, 184, 122),
        "accent": (110, 65, 35),
        "effect": "crumbs",
    },
    "havoc_black": {
        "name": "Havoc Preto",
        "price": 520,
        "color": (12, 12, 16),
        "accent": (255, 70, 40),
        "effect": "ember",
    },
    "crown_hat": {
        "name": "Chapeu Coroa",
        "price": 450,
        "color": (255, 210, 45),
        "accent": (255, 255, 220),
        "item_type": "Chapeu",
        "hat": "crown",
        "outfit": False,
        "effect": "shine",
    },
    "propeller_hat": {
        "name": "Bone Propulsor",
        "price": 280,
        "color": (45, 170, 255),
        "accent": (255, 80, 80),
        "item_type": "Chapeu",
        "hat": "propeller",
        "outfit": False,
    },
    "halo_hat": {
        "name": "Aureola de Craque",
        "price": 360,
        "color": (255, 245, 150),
        "accent": (120, 220, 255),
        "item_type": "Chapeu",
        "hat": "halo",
        "outfit": False,
        "effect": "glow",
    },
    "fire_sneakers": {
        "name": "Tenis Turbo Fogo",
        "price": 330,
        "color": (255, 70, 25),
        "accent": (255, 220, 60),
        "item_type": "Tenis",
        "shoes": "fire",
        "outfit": False,
        "effect": "ember",
    },
    "toole_meme_sneakers": {
        "name": "Tenis Toole Meme",
        "price": 420,
        "color": (90, 255, 80),
        "accent": (20, 20, 20),
        "item_type": "Tenis",
        "shoes": "toole",
        "outfit": False,
        "effect": "bounce",
    },
    "galaxy_set": {
        "name": "Set Galaxia",
        "price": 650,
        "color": (35, 20, 85),
        "accent": (120, 245, 255),
        "item_type": "Roupa + Efeito",
        "hat": "halo",
        "shoes": "star",
        "effect": "stars",
    },
    "thunder_set": {
        "name": "Set Trovao",
        "price": 700,
        "color": (30, 35, 55),
        "accent": (255, 235, 70),
        "item_type": "Roupa + Efeito",
        "shoes": "star",
        "effect": "lightning",
    },
    "ice_drip": {
        "name": "Drip Congelante",
        "price": 560,
        "color": (160, 230, 255),
        "accent": (35, 90, 180),
        "item_type": "Roupa + Efeito",
        "hat": "halo",
        "effect": "ice",
    },
    "toxic_green": {
        "name": "Verde Toxico",
        "price": 480,
        "color": (80, 210, 55),
        "accent": (20, 35, 20),
        "item_type": "Roupa + Efeito",
        "effect": "toxic",
    },
    "referee_drip": {
        "name": "Juiz Dripado",
        "price": 390,
        "color": (245, 245, 245),
        "accent": (15, 15, 15),
        "item_type": "Roupa",
        "hat": "cap",
        "shoes": "star",
        "effect": "shine",
    },
}
