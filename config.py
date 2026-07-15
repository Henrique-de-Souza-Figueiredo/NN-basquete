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

MAP_WIDTH_NORMAL = WIDTH
MAP_WIDTH_6_PLAYERS = 1480
MAP_WIDTH_8_PLAYERS = 1680

MAX_SCORE = 25
# Pontos necessarios para vencer. O host pode escolher ao criar a sala;
# o servidor usa room["win_points"] e cai neste default se nao informado.
DEFAULT_WIN_POINTS = MAX_SCORE
# Opcoes oferecidas ao host no menu de criacao de partida
WIN_POINTS_OPTIONS = [11, 15, 21, 25, 30, 50]
ULTIMATE_MAX = 100

# ==========================================
# MELHORIAS (specs de networking/UX)
# ==========================================
# SPEC-03: fator de interpolacao do cliente (0=sem smoothing, 1=teleporte)
INTERP_FACTOR = 0.3
# SPEC-04: limiares de ping para cor no HUD (ms)
PING_GREEN_MS = 40
PING_YELLOW_MS = 100
ULTIMATE_COSTS = {
    "Henrique": 110,
    "Natan": 105,
    "Presscinotti": 125,
    "Diogo": 135,
    "Miguel": 120,
    "Rafael": 130,
    "John Jonh": 110,
    "Paulo": 150,
    "Treinador": 150,
    "Murilo": 145,
    "Igor": 155,
    "Laiz": 165,
    "Kauã": 170,
    "Caique": 145,
    "João Roberto": 150,
    "Havoc": 185,
    "Bola": 175,
}

# Agora essa imagem deve estar dentro da pasta imagens/
CAGE_IMG = "cage.png"

WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GRAY = (50, 50, 50)

# Paleta moderna de UI
BG_DARK = (15, 18, 25)
BG_MEDIUM = (22, 27, 38)
BG_CARD = (30, 36, 50)
BG_HOVER = (40, 48, 68)
BORDER_SUBTLE = (55, 65, 85)
BORDER_ACCENT = (100, 180, 255)

TEXT_PRIMARY = (240, 245, 255)
TEXT_SECONDARY = (160, 175, 200)
TEXT_MUTED = (100, 115, 140)

ACCENT_BLUE = (70, 150, 255)
ACCENT_GOLD = (255, 210, 60)
ACCENT_GREEN = (80, 220, 130)
ACCENT_RED = (255, 80, 80)
ACCENT_PURPLE = (160, 100, 255)
ACCENT_CYAN = (80, 230, 255)

TEAM_1_COLOR = (50, 130, 255)
TEAM_2_COLOR = (255, 70, 70)

BALL_COLOR = (255, 160, 40)
COURT_COLOR = (222, 184, 135)

BUFF_COLOR = (80, 255, 130)
DEBUFF_COLOR = (255, 70, 70)
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


def map_width_for_player_count(player_count):
    if player_count >= 8:
        return MAP_WIDTH_8_PLAYERS

    if player_count >= 6:
        return MAP_WIDTH_6_PLAYERS

    return MAP_WIDTH_NORMAL


def get_court_geometry(world_width=WIDTH):
    return {
        "left_hoop_x1": LEFT_HOOP_X1,
        "left_hoop_x2": LEFT_HOOP_X2,
        "right_hoop_x1": world_width - 145,
        "right_hoop_x2": world_width - 95,
        "left_backboard_x": LEFT_BACKBOARD_X,
        "right_backboard_x": world_width - 95,
    }

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

# ==========================================
# SCREEN SHAKE (SPEC-FB-01)
# ==========================================
SHAKE_INTENSITY_DEFAULT = 6
SHAKE_DURATION_DEFAULT = 12
SHAKE_INTENSITY_DUNK = 10
SHAKE_DURATION_DUNK = 18
SHAKE_INTENSITY_3PT = 7
SHAKE_DURATION_3PT = 14
SHAKE_INTENSITY_ULTIMATE = 12
SHAKE_DURATION_ULTIMATE = 20

CLASH_KEYS = ["W", "A", "S", "D"]
CLASH_SEQUENCE_LEN = 7
CLASH_TIMER = 135
CLASH_RANGE = 70

CHARACTERS_INFO = {
    "Henrique": {
        "desc": "Rouba a bola do inimigo mais próximo rapidamente.",
        "ultimate_desc": "Dash insano que atravessa a quadra roubando e derrubando quem estiver perto.",
        "img": "henrique.png",
        "color": (100, 100, 250)
    },
    "Natan": {
        "desc": "Fica invisível para os inimigos por um curto período de tempo.",
        "ultimate_desc": "Some por muito tempo, rouba a bola do inimigo ou teleporta para a bola solta.",
        "img": "natan.png",
        "color": (150, 150, 150)
    },
    "John Jonh": {
        "desc": "Ativa leveza no ar, fazendo John Jonh cair muito mais devagar.",
        "ultimate_desc": "Faz o time inteiro flutuar e corta o pulo dos inimigos.",
        "img": "john.png",
        "color": (50, 200, 50)
    },
    "Presscinotti": {
        "desc": "Expande a orelha para proteger e barrar a passagem de inimigos.",
        "ultimate_desc": "Orelhao gigante por mais tempo, empurrando e atordoando inimigos em area grande.",
        "img": "presscinotti.png",
        "color": (250, 150, 50)
    },
    "Rafael": {
        "desc": "Ativa força máxima e mostra a trajetória exata do arremesso.",
        "ultimate_desc": "Modo arremesso perfeito: buff longo e chute automatico forte valendo 3 se estiver com a bola.",
        "img": "rafael.png",
        "color": (200, 50, 50)
    },
    "Diogo": {
        "desc": "Concede bolachas amaldiçoadas que dão buffs aleatórios para os aliados.",
        "ultimate_desc": "Banquete amaldicoado: time recebe varios buffs e inimigos ficam lentos/fracos.",
        "img": "diogo.png",
        "color": (200, 200, 50)
    },
    "Miguel": {
        "desc": "Invoca um clone das sombras que copia todos os seus movimentos.",
        "ultimate_desc": "Clone supremo dura muito, fortalece arremesso e puxa a bola solta para voce.",
        "img": "miguel.png",
        "color": (100, 50, 150)
    },
    "Paulo": {
        "desc": "Gira uma roleta com chance de Buffs, Debuffs ou JACKPOT ÉPICO.",
        "ultimate_desc": "Jackpot garantido com caos aleatorio nos inimigos.",
        "img": "paulo.png",
        "color": (255, 215, 0)
    },
    "Treinador": {
        "desc": "Aperte E e depois 1-8 para copiar uma habilidade dos 8 principais.",
        "ultimate_desc": "Grito tatico: time inteiro recebe quase todos os buffs e cooldowns caem.",
        "img": "treinador.png",
        "color": (80, 170, 220)
    },
    "Murilo": {
        "desc": "Desenha sinais com o botao direito e aperta E para confirmar o comando.",
        "ultimate_desc": "Rabisco Supremo: invoca 3 NPCs desenhados e bagunca inimigos ao redor.",
        "img": "murilo.png",
        "color": (120, 210, 120)
    },
    "Igor": {
        "desc": "Invoca calopsitas que perseguem a bola e atrapalham inimigos.",
        "ultimate_desc": "Enxame Supremo: 10 calopsitas perseguem a jogada e travam inimigos.",
        "img": "igor.png",
        "color": (245, 220, 95)
    },
    "Laiz": {
        "desc": "Causa lag proposital no time inimigo por alguns segundos.",
        "ultimate_desc": "Lag global pesado: inimigos travam, teleportam e ficam bugados por mais tempo.",
        "img": "laiz.png",
        "color": (235, 120, 210)
    },
    "Kauã": {
        "desc": "Mancha a tela do time inimigo e marca os alvos como Goonado.",
        "ultimate_desc": "Cegueira absurda: tela inimiga fica branca por muito tempo com lentidao.",
        "img": "kaua.png",
        "color": (245, 245, 245)
    },
    "Caique": {
        "desc": "Todo debuff gera raiva; cegueira do Kaua gera ainda mais.",
        "ultimate_desc": "Raiva maxima instantanea com gritao brutal em area enorme.",
        "img": "caique.png",
        "color": (190, 45, 35)
    },
    "João Roberto": {
        "desc": "Troca de lugar com quem esta mais perto da bola e rouba se estiver com ela.",
        "ultimate_desc": "Troca caotica: rouba a bola e joga os inimigos perto dela atordoados.",
        "img": "joao_roberto.png",
        "color": (70, 210, 230)
    },
    "Havoc": {
        "desc": "Lider da Havoc: seleciona um inimigo e escolhe uma ordem para controlar a jogada.",
        "ultimate_desc": "Comando total: aplica ordens caoticas em todos os inimigos ao mesmo tempo.",
        "img": "havoc.png",
        "color": (25, 25, 35)
    },
    "Bola": {
        "desc": "Voce vira a bola do jogo: anda livre, mas pode ser carregado e arremessado por outros.",
        "ultimate_desc": "Meteorito: auto-arremesso muito mais forte, valendo 3 e derrubando quem estiver perto.",
        "img": "bola.png",
        "color": BALL_COLOR
    }
}

TRAINER_COPY_CHARACTERS = [
    "Henrique",
    "Natan",
    "John Jonh",
    "Presscinotti",
    "Rafael",
    "Diogo",
    "Miguel",
    "Paulo",
]

CHARACTERS = list(CHARACTERS_INFO.keys())
SECRET_CHARACTERS = ["Treinador", "Murilo", "Igor", "Laiz", "Kauã", "Caique", "João Roberto", "Havoc", "Bola"]
PUBLIC_CHARACTERS = [char for char in CHARACTERS if char not in SECRET_CHARACTERS]

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
