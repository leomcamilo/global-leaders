# Implementações futuras — Global Leaders

Backlog de evoluções pós-hackathon. Cada item descreve a visão, como encaixa na arquitetura atual
e os pontos de atenção.

---

## 1. Mundo multi-agente simultâneo (todos os agentes de todos os países jogando juntos)

### Visão
Hoje o jogo é centrado no líder do jogador: os agentes (`engine/agents.py` + personas em
`engine/prompts/countries/<país>/<chave>.md`) reagem às decisões dele, mas não **agem** por conta
própria. A evolução é transformar **cada agente nomeado** (de TODOS os países, não só o do jogador)
num **ator autônomo** que persegue seus próprios interesses a cada mês — gerando uma dinâmica viva e
muito mais imprevisível, em que o tabuleiro inteiro se move mesmo quando o jogador não faz nada.

Cada pessoa específica (Le Pen, Musk, Lavrov, He Lifeng, as elites…) tem:
- **interesses próprios** (o vetor de utilidade que já existe no frontmatter do `.md`);
- **características próprias** (a prosa: como fala, linhas vermelhas, agenda oculta);
- **agência**: a cada turno pode propor/empurrar uma jogada (pressionar o líder, barganhar com outro
  agente, vazar pra imprensa, se aproximar de um rival estrangeiro, conspirar).

### Personas que evoluem durante a partida (no nível do `.md`)
O ponto central pedido: **cada arquivo markdown de agente deve ser detalhado E modificado ao longo do
jogo nesse nível**. Ou seja, a persona não é estática — quando o favor/stance muda, quando o agente é
traído, promovido, ou muda de lado, o **conteúdo do `.md` daquele agente é atualizado** para refletir a
nova realidade (novos `true_wants`, nova `relationship_with_leader`, talvez uma linha vermelha cruzada
que virou ruptura). Assim o estado narrativo de cada figura é legível e persistente, não só um número
de favor escondido.

**Atenção de arquitetura (mudança importante vs. hoje):** atualmente decidimos NÃO reescrever os `.md`
em runtime (filesystem efêmero/compartilhado no HuggingFace Space — ver `GAME_RULES.md §7.6`); o drift
mora em `state.cast` (memória da sessão). Para esta feature funcionar como pedido, será preciso:
- **por-sessão**, materializar uma cópia editável das personas (ex.: `runs/<session_id>/<país>/<chave>.md`)
  que o motor (e o Nemotron) pode reescrever a cada evolução — mantendo os `.md` canônicos em
  `engine/prompts/countries/` como *seed* imutável;
- um **papel novo da SLM** (`evolve_persona`) que, dado o que aconteceu no mês, reescreve as seções da
  persona daquele agente; rodar isso só para agentes que tiveram mudança relevante (custo!).

### Asimetria de dificuldade: países da IA caem mais difícil que o jogador
Requisito explícito: para um líder **controlado pela IA** (país que o jogador NÃO escolheu) perder,
tem que haver **muito mais problemas** do que para derrubar o jogador. Justificativa de design: senão o
mapa vira um carrossel de golpes/quedas a cada poucos meses e perde credibilidade; o foco dramático deve
seguir no jogador. Implementação proposta:
- multiplicador de resiliência/limiares para países-IA (ex.: `collapse.*_min` reduzidos e `_resilience`
  reforçada — precisam afundar por mais tempo e mais fundo para cair);
- a maturação de crises (golpes, no-confidence) dos países-IA roda mais devagar e com mais "saves";
- quedas de líderes-IA, quando acontecem, viram **eventos globais** que repercutem no jogo do jogador.

### Como encaixa no que já existe
- `engine/agents.py` (utilidade, stance, `update_agent_stances`) → base para a função de decisão de cada
  ator autônomo.
- `engine/personas.py` + os 61 `.md` → identidade de cada ator; vira a camada que evolui por sessão.
- `engine/game.py` (loop mensal) → ganha uma fase "os agentes agem" antes/depois dos eventos do jogador.
- `engine/seeds.py` (eventos globais) → canal para propagar o que acontece nos outros países ao jogador.

### Pontos de atenção
- **Custo de tokens**: N países × ~10 agentes agindo por mês é uma explosão de chamadas. Provável
  necessidade de orquestração (resolver em lote, só agentes "relevantes" agem, batch por país).
- **Determinismo/replay**: hoje o Dice garante replay; ações de agentes autônomos com modelo de
  temperatura > 0 quebram isso — pensar em seed por agente/turno.
- **UI**: como mostrar um mundo vivo sem poluir a Situation Room do jogador (feed de "world wire"?).
- **Equilíbrio**: validar com playtests Nemotron, como fizemos com os decks (alta variância já observada).

---
