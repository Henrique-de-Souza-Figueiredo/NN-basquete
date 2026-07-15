# Documentação Técnica — NN League (NN-basquete)

Jogo de basquete 2D local/online em Python + PyGame, com arquitetura cliente-servidor autoritativa. Esta doc cobre a estrutura, o protocolo de rede, o ciclo de simulação e as configurações.

---

## 1. Visão geral

| Item | Descrição |
|------|-----------|
| Linguagem | Python 3 (tipagem dinâmica) |
| Render | PyGame 2.x (SDL) |
| Rede | Sockets TCP, serialização via `pickle` |
| Modelo | Servidor autoritativo (valida input, roda a física) |
| Jogadores | 2 a 8 (2 times), + bots de treino |
| Resolução | 1280x720 (mundo estende em 6/8 jogadores) |

O servidor é a única fonte de verdade. O cliente envia apenas intenções (posição, ação) e renderiza o estado que o servidor devolve a cada frame.

---

## 2. Arquitetura

```
┌──────────────┐         TCP :5555          ┌──────────────────┐
│  client.py   │  ── pickle(acao) ───────▶  │    server.py     │
│  (PyGame)    │  ◀─ pickle(room_state) ──  │  (sim autorit.)  │
└──────────────┘                            └──────────────────┘
       │                                          │
       │  inicia server local                     │  rooms = {} (dict)
       ▼                                          ▼
 start_local_server_process()             room_physics_loop (thread/room)
```

Arquivos principais:

| Arquivo | Responsabilidade |
|---------|------------------|
| `client.py` | Loop principal, render, input, UI (menu/lobby/jogo) |
| `server.py` | Socket server, salas, física da bola, pontuação, habilidades |
| `network.py` | Wrapper de socket do cliente (`Network`), config de host/porta |
| `config.py` | Constantes de rede, física, personagens, cosméticos |
| `story_mode.py` | Modo história (subprocess separado) |
| `save_db.py` | Persistência local (skins equipadas, moedas, conquistas) |

---

## 3. Protocolo de rede

- **Transporte**: TCP, `HOST="0.0.0.0"`, `PORT=5555`, `BUFFER_SIZE=4096`.
- **Serialização**: `pickle` (objetos Python diretos, sem schema versionado).
- **Padrão request/response**: o cliente envia um dict/payload e o servidor responde com o dict `room` completo (`pickle.loads(conn.recv(...))`).

### 3.1 Conexão inicial

`Network.connect(action, room_code="", win_points=None)` envia uma tupla:

| Ação | Payload enviado | Resposta |
|------|-----------------|----------|
| `CREATE` | `("CREATE", win_points)` | `("SUCCESS", room_code, player_id, host_id)` ou `("ERROR", msg)` |
| `JOIN` | `("JOIN", room_code)` | `("SUCCESS", ...)` ou `("ERROR", "Sala nao encontrada.")` |

> `win_points=None` faz o servidor usar `DEFAULT_WIN_POINTS` (25). Ver seção 6.

### 3.2 Pacotes por frame (`Network.send`)

O cliente monta `data_to_send` e chama `self.server_data = self.net.send(data_to_send)`. Ações possíveis:

| `action` | Quando | Campos |
|----------|--------|--------|
| `UPDATE_LOBBY` | no lobby | `char`, `skin_id`, `team` |
| `ADD_BOT` / `REMOVE_BOT` | host, no lobby | `bot_char` |
| `START_GAME` | host, no lobby | — |
| `REACTION` | durante o jogo | `reaction` (um de 6文本 pré-definidos) |
| `SKIP_REPLAY` | durante replay | — |
| `BOLA_THROW` | char "Bola" | `target_x`, `target_y` |
| `USE_ABILITY` | habilidade | `facing`, `copied_ability` (Treinador) |
| `CLASH_QTE_KEY` / `DUNK_QTE_KEY` | QTE | `key` |
| `ULTIMATE` | ultimate | — |
| `THROW` | arremesso | `target_x`, `target_y` |
| `DUNK_START` | investida | — |
| (sem action) | movimento | `x`, `y`, `facing` |

O servidor valida cada ação no handler da conexão (ex.: `ADD_BOT`/`START_GAME` só o `host_id` pode disparar).

---

## 4. Fluxo de conexão e sala

1. **Host** clica "Criar sala" → `start_local_server_process()` sobe o `server.py` e `Network.connect("CREATE", win_points=...)`.
2. Servidor gera `room_code` (4 caracteres) e registra a sala em `rooms[room_code]`.
3. **Visitante** cola o código → `Network.connect("JOIN", room_code)`.
4. Cada conexão recebe um `player_id` e roda seu próprio loop de handler (`threading`).
5. No lobby, clientes trocam `UPDATE_LOBBY` até o host mandar `START_GAME`.

---

## 5. Estado da sala (`room`)

Dicionário autoritativo. Campos relevantes:

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `players` | dict | `{player_id: {...}}` com `x`, `y`, `team`, `char`, `skin_id`, `facing`, stats de partida |
| `ball` | dict | `x`, `y`, `vel_x`, `vel_y`, `holder`, `holder_source`, `bola_throw_timer` |
| `score` | `[int, int]` | placar time 1 / time 2 |
| `host_id` | int | quem pode iniciar jogo e gerenciar bots |
| `game_started` | bool | partida em andamento |
| `game_over` | bool | vitória decidida |
| `winner_team` | int/None | time vencedor |
| `win_points` | int | **pontos para vencer (nova feature)** — cai em `DEFAULT_WIN_POINTS` se omitido |
| `world_width` | int | largura do mundo (depende da qtde de jogadores) |
| `replay_timer` | int | congela física durante replay de cesta |
| `skip_votes` | set | votos para pular replay |

> O `win_points` é definido no `CREATE` (validado contra `WIN_POINTS_OPTIONS`) e usado na condição de vitória.

---

## 6. Ciclo de simulação (servidor)

`room_physics_loop(room_code)` roda em thread dedicada por sala, a `FPS=60`:

1. Atualiza `world_width` conforme jogadores (`map_width_for_player_count`).
2. Processa **posse da bola**: se há `holder`, a bola segue o dono; se solta, aplica gravidade e colisões (chão, paredes, backboard).
3. **Treino/bots** e habilidades especiais (Murilo, clones, calopsitas) são resolvidos.
4. **Pontuação**: detecta se a bola cruzou o aro (`ball_crossed_hoop`) e chama `award_score(room, scored_team)`.
5. `award_score` soma `get_score_points(room, team)` (2 ou 3 pts conforme distância do arremesso) e, se `score[team-1] >= win_points`, seta `game_over=True`, `winner_team`, e monta `match_awards`.

```python
points = get_score_points(room, scored_team)   # 2 ou 3
room["score"][scored_team - 1] += points
win_points = room.get("win_points", DEFAULT_WIN_POINTS)
if room["score"][0] >= win_points:
    room["game_over"] = True
    room["winner_team"] = 1
    build_match_awards(room)
```

> `david_star` (comando do Murilo) é um "instant win" que zera o time adversário e força `game_over`.

---

## 7. Loop do cliente

`GameClient.run()` (PyGame, `clock.tick(FPS)`):

1. Lê eventos (`pygame.event.get`): mouse, teclado, QUIT.
2. Constrói `data_to_send` conforme o estado (move, arremessa, reage).
3. **Envia e recebe numa tacada**: `self.server_data = self.net.send(data_to_send)`.
4. Renderiza `self.server_data` (HUD, jogadores, bola, efeitos).
5. Aplica jitter de lag no servidor (não no cliente) para simular perda de pacote.

O cliente nunca calcula pontos ou colisões definitivas: só exibe o que o servidor manda.

---

## 8. Personagens e habilidades

- **16 personagens públicos** + 9 secretos (Treinador, Murilo, Igor, Laiz, Kauã, Caique, João Roberto, Havoc, Bola).
- Cada um tem `desc`, `ultimate_desc`, `img`, `color` (em `CHARACTERS_INFO`).
- Mecânicas especiais: **Dunk** (QTE de 6 teclas), **Clash** (QTE de 7), **Ultimate** (custo em `ULTIMATE_COSTS`), **Bola** (vira a própria bola).
- **Cosméticos** (`COSMETICS`): skins de roupa/chapéu/tênis com efeitos visuais e alguns buffs (`speed`, `bounce`, etc).

---

## 9. Constantes principais (`config.py`)

| Constante | Valor | Uso |
|-----------|-------|-----|
| `WIDTH` / `HEIGHT` | 1280 / 720 | resolução base |
| `FPS` | 60 | tick da simulação |
| `GRAVITY` | 0.8 | física da bola |
| `MAX_SCORE` / `DEFAULT_WIN_POINTS` | 25 / 25 | default de pontos para vencer |
| `WIN_POINTS_OPTIONS` | [11,15,21,25,30,50] | opções do host |
| `THREE_POINT_DISTANCE` | 430 | limite para arremesso de 3 |
| `CHAR_W` / `CHAR_H` | 30 / 50 | hitbox do jogador |
| `BALL_RAD` / `CATCH_DIST` | 12 / 30 | bola e captura |
| `DUNK_*` / `CLASH_*` | — | parâmetros de QTE e investida |

---

## 10. Como rodar

```bash
# Servidor (outro terminal ou máquina)
python3 server.py

# Cliente
python3 client.py
```

- Para **mesma máquina**, o cliente sobe o server local automaticamente (`start_local_server_process`).
- Para **LAN/VPN** (Radmin), o visitante informa o IP do host; a config vai em `server_config.json` (`Network.set_server`).

> Requer PyGame instalado (`pip install pygame` num venv, pois o sistema usa PEP 668).

---

## 11. Alterações da branch `visual-improvements`

Esta branch adiciona duas melhorias sem quebrar a lógica de jogo:

### 11.1 Host escolhe pontos para vencer
- `config.py`: `DEFAULT_WIN_POINTS = MAX_SCORE` + `WIN_POINTS_OPTIONS = [11,15,21,25,30,50]`.
- `network.py`: `connect("CREATE", win_points=...)` envia o valor escolhido.
- `server.py`: `rooms[room_code]` recebe `"win_points"` validado; condição de vitória usa `room["win_points"]` em vez de `MAX_SCORE`.
- `client.py`: seletor cíclo (◀ ▶) no menu principal, passado em `create_local_room`.

### 11.2 Melhorias visuais (HUD)
- Placar em fonte maior (`font_xl`).
- Painel do placar com bordas nas cores dos times.
- Barra de progresso até `win_points` (azul vs vermelho).
- Texto "Vitória em N pts".
- Indicador de posse da bola (seta sobre o jogador que segura a bola).

> Nenhuma dependência nova foi adicionada (YAGNI).
