# Specs de Melhoria — NN League

Cinco propostas de evolução do jogo, no formato Spec (contexto, mudança, protocolo, risco, esforço). Ordem por impacto/risco. Nenhuma quebra a arquitetura cliente-servidor autoritativa atual.

---

## SPEC-01 — Reconexão de jogador (rejoin)

**Contexto:** Hoje cada conexão recebe um `player_id` efêmero. Se o cliente cair (QUIT, crash, lag de VPN), a thread do servidor dá `break` e o jogador some da sala. Em LAN com Radmin VPN, queda é comum.

**Mudança:**
- `server.py`: `rooms[code]["players"][pid]` ganha `conn_token` (uuid gerado no CREATE/JOIN).
- `network.py`: `connect("REJOIN", room_code, conn_token)` → servidor reanexa a `player_id` existente se `conn_token` bater e o jogador não estiver ativo.
- `client.py`: persiste `conn_token` em `save_db` (local); ao reconectar, tenta REJOIN antes de JOIN.
- Se não houver token ou já estiver ativo, fallback para JOIN normal (novo personagem).

**Protocolo:**
```
("REJOIN", room_code, conn_token) -> ("SUCCESS", room_code, player_id, host_id) | ("ERROR", "Token invalido")
```

**Risco:** Baixo. `player_id` continua estável; física não muda.
**Esforço:** Médio (~80 linhas: token gen, handler REJOIN, persistência no client).

---

## SPEC-02 — CRC/versionamento do estado (anti-dessincronização)

**Contexto:** O servidor manda o `room` completo via pickle a cada frame. Se um pacote corromper (pickle quebrado) ou o cliente aplicar fora de ordem, o jogo dessincroniza silenciosamente. Não há `frame_id` nem checksum.

**Mudança:**
- `server.py`: todo `room` enviado recebe `"frame_id": room["frame_counter"]` (incrementa por tick) e `"crc": zlib.crc32(pickle(room)) & 0xffffffff`.
- `client.py`: ignora pacotes com `frame_id <= last_frame_id` (duplicados/out-of-order) e detecta CRC inválido (loga `[DESSINC]` e pede snapshot).
- Adicionar ação `REQUEST_SNAPSHOT` para o cliente pedir o estado completo atual após perda.

**Protocolo:**
```
send({"action": "REQUEST_SNAPSHOT"}) -> server responde com room atual (frame_id atual)
```

**Risco:** Baixo/médio (pickle é frágil a corrupção; crc barato). Sem dependências novas (`zlib` é stdlib).
**Esforço:** Médio (~60 linhas).

---

## SPEC-03 — Reconciliação de input no cliente (interpolação)

**Contexto:** O cliente renderiza `server_data` cru. Com jitter de rede (servidor já aplica ±10px de lag), os jogadores "teleportam" visivelmente entre frames, pior em 8 jogadores / LAN lenta.

**Mudança:**
- `client.py`: manter `render_x/render_y` por `player_id`; a cada frame, interpolar em direção a `server_data["players"][pid]["x"]` com fator `lerp` (ex.: 0.3).
- Bola também: `render_ball_x/y` interpolado.
- `config.py`: `INTERP_FACTOR = 0.3` (tunável).

**Protocolo:** Nenhum (só cliente). Servidor não precisa saber.
**Risco:** Baixo. Puramente visual; não afeta autoridade.
**Esforço:** Baixo (~40 linhas no draw loop).

---

## SPEC-04 — Ping/latência no HUD

**Contexto:** Não há medição de latência. Em VPN, o jogador não sabe se o lag é da rede ou do jogo.

**Mudança:**
- `network.py`: `send()` mede `rtt = time.perf_counter() - t0` e expõe `self.last_rtt`.
- `client.py`: HUD mostra `Ping: Xms` (cor: verde <40, amarelo <100, vermelho >=100).
- Opcional: `server.py` responde a `("PING",)` com `("PONG",)` para medir RTT sem afetar gameplay.

**Protocolo:**
```
("PING",) -> ("PONG",)   # mantido pelo servidor no handler, não toca room
```

**Risco:** Baixo.
**Esforço:** Baixo (~25 linhas).

---

## SPEC-05 — Reconciliação de placar + placar persistente (save_db)

**Contexto:** `score` vive só em memória (`rooms`). Ao reiniciar o server ou fechar, histórico de partidas some. Não há "career stats".

**Mudança:**
- `server.py`: ao `game_over`, chamar `save_db.record_match(room_code, winner_team, score, duration_ticks)` (função nova no `save_db.py`).
- `save_db.py`: nova tabela `matches` (JSON ou sqlite local) com `timestamp, winner, score_final, duracao`.
- `client.py`: tela de vitória mostra "Últimas 5 partidas" lidas do `save_db`.

**Protocolo:** Nenhum em rede (server→local DB).
**Risco:** Baixo.
**Esforço:** Médio (~70 linhas + schema save_db).

---

## Priorização sugerida

| Spec | Impacto | Risco | Esforço | Recomendação |
|------|---------|-------|---------|--------------|
| SPEC-03 (interpolação) | Alto (feel) | Baixo | Baixo | **Fazer primeiro** |
| SPEC-04 (ping) | Médio | Baixo | Baixo | Fazer junto |
| SPEC-02 (CRC/frame) | Alto (estabilidade) | Médio | Médio | Depois |
| SPEC-01 (rejoin) | Alto (retenção) | Baixo | Médio | Depois |
| SPEC-05 (placar DB) | Médio (meta) | Baixo | Médio | Por último |

> Todas sem novas dependências (Python stdlib + PyGame já presentes). YAGNI mantido.
