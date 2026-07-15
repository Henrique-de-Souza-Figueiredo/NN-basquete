# Specs de Melhorias Visuais — NN League

## SPEC-UI-01 — Efeitos Dinâmicos nos Botões (Hover & Press)

**Contexto:** A classe `Button` atual é estática - não há feedback visual quando o mouse passa por cima ou quando o botão é clicado. Isso torna a interface menos polida e reativa.

**Mudança:**
- `client.py`: Atualizar a classe `Button` para:
  - Detectar hover e mudar a cor do fundo (brilho suave)
  - Aplicar deslocamento de 2 pixels para baixo ao clicar (press)
  - Adicionar animação de transição suave entre estados

**Protocolo:** Nenhum (puramente visual, apenas cliente).

**Risco:** Baixo. Apenas alterações visuais na classe Button.
**Esforço:** Baixo (~30 linhas modificadas).

---

## SPEC-UI-02 — Mapeamento de Teclas Personalizável

**Contexto:** Atualmente as teclas são fixas (W/A/S/D para movimento, Espaço para arremesso, etc.). Jogadores querem personalizar seus controles.

**Mudança:**
- `config.py`: Adicionar dicionário `KEY_BINDINGS` com valores padrão
- `save_db.py`: Adicionar funções para salvar/carregar key bindings do banco local
- `client.py`: 
  - Criar tela de configuração de teclas
  - Substituir todas as referências hardcoded por consultas ao `KEY_BINDINGS`

**Protocolo:** Nenhum (salvo localmente no save_db).

**Risco:** Baixo. Mudanças pontuais no tratamento de input.
**Esforço:** Médio (~80 linhas + lógica de UI).

---

## SPEC-UI-03 — Menu de Configurações de Áudio

**Contexto:** Não há como controlar volumes independentemente. O mixer pode estar muito alto ou baixo.

**Mudança:**
- `config.py`: Adicionar configurações de volume padrão
- `save_db.py`: Salvar preferências de áudio
- `client.py`: Criar tela de configurações com sliders de volume (SFX, música)

**Protocolo:** Nenhum (salvo localmente).

**Risco:** Baixo.
**Esforço:** Médio (~60 linhas).

---

## SPEC-FB-01 — Screen Shake para Dunks e Habilidades

**Contexto:** Falta feedback tátil visual em momentos de impacto como dunks, cestas de 3 pontos e ativação de ultimates.

**Mudança:**
- `config.py`: Adicionar constantes `SHAKE_INTENSITY`, `SHAKE_DURATION`
- `client.py`:
  - Adicionar método `trigger_screen_shake(intensity, duration)`
  - Aplicar offset aleatório na câmera durante o shake
  - Ativar em: dunks, cestas de 3pts, ativação de ultimate

**Protocolo:** Nenhum (puramente visual).

**Risco:** Baixo.
**Esforço:** Baixo (~40 linhas).

---

## SPEC-FB-02 — Sistema de Partículas Estéticas

**Contexto:** Falta polimento visual com partículas para impactos, rastros e efeitos.

**Mudança:**
- `client.py`: Criar classe `Particle` e `ParticleSystem`
- Tipos de partículas:
  - Faíscas quando bola bate no aro
  - Poeira nos pés ao pular/correr
  - Fumaça na bola durante dunks
  - Brilho ao ativar habilidades

**Protocolo:** Nenhum (puramente visual).

**Risco:** Baixo.
**Esforço:** Médio (~100 linhas).

---

## SPEC-FB-03 — Indicadores Visuais de Status

**Contexto:** Estados como stun, buffs e debuffs não são visualmente claros para jogadores.

**Mudança:**
- `client.py`:
  - Adicionar estrelas girando acima de jogadores stunned
  - Ícones de buffs/debuffs sobre os personagens
  - Efeitos de aura para habilidades ativas

**Protocolo:** Nenhum (puramente visual).

**Risco:** Baixo.
**Esforço:** Médio (~60 linhas).

---

## SPEC-SOM-01 — Música de Fundo Dinâmica (BGM)

**Contexto:** O jogo não possui música de fundo, tornando a experiência menos imersiva.

**Mudança:**
- `client.py`:
  - Carregar e tocar música de menu em loop
  - Trocar para música de gameplay ao iniciar partida
  - Funcionalidade premium: acelerar música em match point

**Protocolo:** Nenhum (áudio local).

**Risco:** Baixo.
**Esforço:** Médio (~50 linhas + assets de áudio).

---

## SPEC-SOM-02 — Novos Efeitos Sonoros (SFX)

**Contexto:** Falta feedback sonoro para ações comuns como clique de botão, quique da bola e ativação de habilidades.

**Mudança:**
- `client.py`:
  - Som de clique ao pressionar botões
  - Som de quique da bola (volume baseado na velocidade)
  - Sons de habilidades específicas

**Protocolo:** Nenhum (áudio local).

**Risco:** Baixo.
**Esforço:** Baixo (~30 linhas + assets).

---

## Priorização Sugerida

| Spec | Impacto | Risco | Esforço | Recomendação |
|------|---------|-------|---------|--------------|
| UI-01 (botões) | Alto (UX) | Baixo | Baixo | **Fazer primeiro** |
| FB-01 (screen shake) | Alto (game feel) | Baixo | Baixo | Fazer junto |
| FB-02 (partículas) | Alto (polimento) | Baixo | Médio | Depois |
| FB-03 (indicadores) | Médio (legibilidade) | Baixo | Médio | Depois |
| UI-02 (keybinds) | Médio (acessibilidade) | Baixo | Médio | Opcional |
| SOM-01/02 (áudio) | Médio (imersão) | Baixo | Médio | Por último |
| UI-03 (áudio config) | Baixo | Baixo | Médio | Por último |

> Todas sem novas dependências externas. YAGNI mantido.
