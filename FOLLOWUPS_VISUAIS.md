# Documentação de Follow-ups Visuais — NN League

## 📋 Resumo do Implementado

### ✅ Especificações Criadas (SPECS_MELHORIAS_VISUAIS.md)
- SPEC-UI-01: Efeitos dinâmicos nos botões (hover/press)
- SPEC-UI-02: Mapeamento de teclas personalizável
- SPEC-UI-03: Menu de configurações de áudio
- SPEC-FB-01: Screen shake para dunks e habilidades
- SPEC-FB-02: Sistema de partículas estéticas
- SPEC-FB-03: Indicadores visuais de status
- SPEC-SOM-01: Música de fundo dinâmica (BGM)
- SPEC-SOM-02: Novos efeitos sonoros (SFX)

### ✅ Código Implementado
1. **Classe Button aprimorada** (`client.py`)
   - Efeito de hover com brilho dourado
   - Efeito de press com deslocamento de 2px
   - Sombra cacheada para performance
   - Métodos `_brighten()` e `_darken()` para ajuste de cores

2. **Sistema de Screen Shake** (`client.py` + `config.py`)
   - Constantes configuráveis no `config.py`
   - Intensidades diferentes por tipo de evento
   - Decaimento suave ao longo do tempo
   - Tratamento correto de offsets negativos

3. **Integração no Loop Principal**
   - Atualização de todos os botões a cada frame
   - Screen shake integrado no pipeline de rendering

---

## 🎯 Follow-ups Prioritários

### Prioridade 1: Integração de Eventos (Alto Impacto, Médio Esforço)

#### 1.1 Screen Shake em Eventos do Jogo
**Descrição:** Conectar o `trigger_screen_shake()` aos eventos reais do jogo.

**Onde integrar:**
- `server.py`: Quando detectar dunk, cesta de 3pts ou ativação de ultimate
- `client.py`: Ao receber notificação de evento do servidor

**Protocolo sugerido:**
```python
# No servidor, ao detectar evento:
send_to_all({"event": "SHAKE", "type": "dunk", "intensity": 10, "duration": 18})
send_to_all({"event": "SHAKE", "type": "three_point", "intensity": 7, "duration": 14})
send_to_all({"event": "SHAKE", "type": "ultimate", "intensity": 12, "duration": 20})

# No cliente, ao receber:
if event_type == "SHAKE":
    self.trigger_screen_shake(data["intensity"], data["duration"])
```

**Arquivos afetados:** `server.py`, `client.py`
**Esforço:** ~40 linhas

---

#### 1.2 Sistema de Partículas Básico
**Descrição:** Criar sistema leve de partículas para feedback visual.

**Tipos de partículas a implementar:**
1. **Faíscas no aro** - Quando bola bate no aro com força
2. **Poeira ao pular** - Partículas nos pés ao saltar
3. **Brilho na bola** - Durante dunks vitoriosos
4. **Impacto no chão** - Quando bola quica no chão

**Implementação sugerida:**
```python
class Particle:
    def __init__(self, x, y, vx, vy, color, lifetime):
        self.x, self.y = x, y
        self.vx, self.vy = vx, vy
        self.color = color
        self.lifetime = lifetime
        self.alpha = 255
    
    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.vy += 0.1  # gravidade leve
        self.lifetime -= 1
        self.alpha = max(0, int(255 * self.lifetime / 60))
    
    def draw(self, surface):
        if self.alpha > 0:
            s = pygame.Surface((4, 4), pygame.SRCALPHA)
            pygame.draw.circle(s, (*self.color, self.alpha), (2, 2), 2)
            surface.blit(s, (int(self.x), int(self.y)))

class ParticleSystem:
    def __init__(self):
        self.particles = []
    
    def emit(self, x, y, count, color, spread=3):
        for _ in range(count):
            vx = random.uniform(-spread, spread)
            vy = random.uniform(-spread, 0)
            self.particles.append(Particle(x, y, vx, vy, color, 60))
    
    def update(self):
        self.particles = [p for p in self.particles if p.lifetime > 0]
        for p in self.particles:
            p.update()
    
    def draw(self, surface):
        for p in self.particles:
            p.draw(surface)
```

**Arquivos afetados:** `client.py`
**Esforço:** ~80 linhas

---

### Prioridade 2: Feedback Visual (Alto Impacto, Baixo Esforço)

#### 2.1 Indicadores Visuais de Status
**Descrição:** Mostrar estados de jogadores de forma visual clara.

**Efeitos a implementar:**
1. **Stun (Atordoamento)** - Estrelas girando acima da cabeça
2. **Buff de força** - Aura vermelha ao redor do personagem
3. **Buff de velocidade** - Linhas de velocidade atrás
4. **Debuff de lentidão** - Nuvem de poeira lenta
5. **Invencibilidade** - Brilho dourado pulsante

**Implementação:**
```python
def draw_status_effects(surface, player_data, x, y, ticks):
    # Stun: estrelas girando
    if player_data.get("stun_timer", 0) > 0:
        for i in range(3):
            angle = ticks / 200 + i * (2 * math.pi / 3)
            sx = int(x + CHAR_W / 2 + math.cos(angle) * 20)
            sy = int(y - 10 + math.sin(angle) * 5)
            pygame.draw.circle(surface, (255, 255, 100), (sx, sy), 4)
    
    # Buff de força: aura vermelha
    if player_data.get("throw_buff_timer", 0) > 0:
        aura_rect = pygame.Rect(x - 5, y - 5, CHAR_W + 10, CHAR_H + 10)
        pygame.draw.ellipse(surface, (255, 100, 100, 60), aura_rect, 2)
    
    # Buff de velocidade: linhas
    if player_data.get("speed_buff_timer", 0) > 0:
        for i in range(3):
            ly = y + 10 + i * 15
            pygame.draw.line(surface, (100, 200, 255), 
                           (x - 15, ly), (x - 5, ly), 2)
```

**Arquivos afetados:** `client.py`
**Esforço:** ~50 linhas

---

#### 2.2 Trail de Bola
**Descrição:** Adicionar rastro visual à bola quando se move rápido.

**Implementação:**
```python
class BallTrail:
    def __init__(self, max_length=10):
        self.points = deque(maxlen=max_length)
    
    def update(self, x, y, vel_x, vel_y):
        speed = math.hypot(vel_x, vel_y)
        if speed > 5:
            self.points.append((int(x), int(y)))
        elif len(self.points) > 0:
            self.points.popleft()
    
    def draw(self, surface):
        if len(self.points) > 1:
            for i, (x, y) in enumerate(self.points):
                alpha = int(255 * (i + 1) / len(self.points))
                radius = int(3 + 3 * (i + 1) / len(self.points))
                s = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
                pygame.draw.circle(s, (255, 140, 0, alpha), (radius, radius), radius)
                surface.blit(s, (x - radius, y - radius))
```

**Arquivos afetados:** `client.py`
**Esforço:** ~40 linhas

---

### Prioridade 3: UI/UX (Médio Impacto, Médio Esforço)

#### 3.1 Menu de Configurações de Áudio
**Descrição:** Adicionar sliders de volume independentes.

**Elementos da UI:**
- Slider de volume de música (BGM)
- Slider de volume de efeitos (SFX)
- Toggle de mudo
- Salvar preferências no `save_db`

**Arquivos afetados:** `client.py`, `config.py`, `save_db.py`
**Esforço:** ~80 linhas

---

#### 3.2 Mapeamento de Teclas Personalizável
**Descrição:** Permitir ao jogadores redefinirem teclas.

**Funcionalidades:**
- Tela de configuração de controles
- Salvar bindings no banco local
- Fallback para teclas padrão
- Validação de conflitos

**Arquivos afetados:** `client.py`, `config.py`, `save_db.py`
**Esforço:** ~100 linhas

---

#### 3.3 Tela de Estatísticas Aprimorada
**Descrição:** Melhorar a visualização das estatísticas.

**Melhorias:**
- Gráficos de desempenho por personagem
- Histórico de partidas com timeline
- Comparativo com outros jogadores
- Badges e conquistas visuais

**Arquivos afetados:** `client.py`, `save_db.py`
**Esforço:** ~120 linhas

---

### Prioridade 4: Áudio (Médio Impacto, Médio Esforço)

#### 4.1 Música de Fundo Dinâmica (BGM)
**Descrição:** Adicionar trilhas sonoras que reagem ao jogo.

**Funcionalidades:**
- Música de menu diferente da de gameplay
- Aceleração em match point
- Fade suave entre estados
- Volume configurável

**Arquivos afetados:** `client.py`, `config.py`
**Esforço:** ~50 linhas + assets de áudio

---

#### 4.2 Novos Efeitos Sonoros (SFX)
**Descrição:** Adicionar sons para ações comuns.

**Sons a implementar:**
- Clique de botão no menu
- Quique da bola (volume baseado na velocidade)
- Ativação de habilidades
- Coleta de item
- Notificação de achievements

**Arquivos afetados:** `client.py`
**Esforço:** ~30 linhas + assets de áudio

---

### Prioridade 5: Quick Wins (Alto Impacto, Baixo Esforço - <30 min cada)

#### 5.1 Integração Imediata do Screen Shake
**Descrição:** Conectar o `trigger_screen_shake()` já implementado aos eventos do servidor.
**Arquivos:** `server.py`, `client.py`
**Esforço:** ~20 linhas

#### 5.2 Sons de Botão
**Descrição:** Adicionar clique sonoro ao pressionar qualquer botão.
**Arquivos:** `client.py`
**Esforço:** ~15 linhas + 1 arquivo de áudio

#### 5.3 Melhoria no Clipboard
**Descrição:** Substituir tkinter por `pyperclip` ou fallback nativo para evitar micro-travamentos.
**Arquivos:** `client.py`
**Esforço:** ~25 linhas

---

### Prioridade 6: Polimento Avançado (Baixo Impacto, Alto Esforço)

#### 5.1 Sombras Dinâmicas
**Descrição:** Adicionar sombras projetadas no chão.

**Implementação:**
- Projeção simples baseada na posição da "luz"
- Sombras elípticas sob os personagens
- Opacidade baseada na altura

**Arquivos afetados:** `client.py`
**Esforço:** ~60 linhas

---

#### 5.2 Efeitos de Transição entre Telas
**Descrição:** Animações suaves ao mudar de estado.

**Tipos:**
- Fade in/out
- Slide horizontal
- Zoom suave
- Dissolve

**Arquivos afetados:** `client.py`
**Esforço:** ~80 linhas

---

#### 5.3 Melhorias no HUD
**Descrição:** Tornar o HUD mais informativo e polido.

**Elementos:**
- Barras de habilidade animadas
- Combo counter para sequências
- Indicador de ultimate pronto
- Minimapa com posição dos jogadores

**Arquivos afetados:** `client.py`
**Esforço:** ~100 linhas

---

## 🗂️ Ordem de Implementação Sugerida

| # | Tarefa | Prioridade | Esforço | Impacto |
|---|--------|------------|---------|---------|
| 1 | Screen shake em eventos | Alta | Médio | Alto |
| 2 | Sistema de partículas | Alta | Médio | Alto |
| 3 | Indicadores de status | Alta | Baixo | Alto |
| 4 | Trail de bola | Média | Baixo | Médio |
| 5 | Menu de áudio | Média | Médio | Médio |
| 6 | Mapeamento de teclas | Média | Médio | Médio |
| 7 | BGM dinâmica | Baixa | Médio | Médio |
| 8 | Novos SFX | Baixa | Baixo | Médio |
| 9 | Sombras dinâmicas | Baixa | Alto | Baixo |
| 10 | Transições de tela | Baixa | Alto | Baixo |
| 11 | Melhorias no HUD | Baixa | Alto | Médio |

---

## 📝 Notas de Implementação

### Dependências
- Nenhuma dependência externa necessária
- Todas as melhorias usam PyGame nativo
- Assets de áudio podem ser adicionados na pasta `audios/`

### Performance
- Partículas: Limitar a 100 ativas por vez
- Screen shake: Usar `screen.copy()` apenas quando necessário
- Shadows: Usar superfícies SRCALPHA com baixa resolução

### Compatibilidade
- Manter compatibilidade com PyGame 2.x
- Testar em Windows e Linux
- Verificar performance em máquinas mais lentas

### Testes
- Verificar syntax com `python3 -m py_compile`
- Testar cada feature individualmente
- Verificar não-regressão nas features existentes

---

## 🔗 Arquivos Relacionados

- `SPECS_MELHORIAS_VISUAIS.md` - Specs detalhadas
- `SPECS_MELHORIAS.md` - Specs originais de networking
- `DOCUMENTACAO_TECNICA.md` - Documentação técnica existente
- `config.py` - Constantes e configurações
- `client.py` - Código do cliente (implementações visuais)
- `server.py` - Código do servidor (eventos)
- `save_db.py` - Persistência de dados

---

*Documentação criada em: 15/07/2026*
*Última atualização: 15/07/2026*
