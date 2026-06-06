# Global Leaders — Game Design Doc

> Jogo para o HuggingFace Build Small Hackathon 2026 (Track 2 — "An Adventure in Thousand Token Wood").
> Você assume um líder global no início de 2025 e tenta cumprir 8 objetivos até dezembro, reagindo a
> eventos baseados em fatos reais daquele ano. SLM ≤32B rodando local.

---

## 1. Pitch (uma frase)

Você vira presidente/primeiro-ministro de um país real em janeiro de 2025 e governa 12 meses tomando decisões diante de crises tiradas das manchetes reais daquele ano — uma IA narra o mundo, dá voz aos seus ministros e à oposição, julga suas decisões em texto livre e move os indicadores do país. Falhe e você pode cair antes de dezembro (golpe / renúncia / impeachment).

## 2. Decisões de design travadas

| Dimensão | Decisão |
|---|---|
| **Fonte dos eventos** | Híbrido: sementes reais de 2025 (fatos ancorados por país/mês) + ramificação fictícia gerada pelo SLM conforme as decisões divergem da história |
| **Core loop (decisão)** | Híbrido: texto livre interpretado pelo SLM + 2-4 opções sugeridas como atalho |
| **Métricas / fim de jogo** | Indicadores vivos + 8 objetivos; **game over antecipado** possível (aprovação/estabilidade no chão → golpe/renúncia/impeachment) |
| **Escopo MVP** | 5-6 países profundos: **EUA, Brasil, Rússia, China, Argentina, França** |
| **Agentes** | Elenco fixo por país, persistente, com memória e agenda própria |
| **Tempo** | 12 turnos mensais (jan→dez 2025), 1-3 eventos por turno |
| **Tom** | Dramático com humor leve |
| **Impacto das decisões** | SLM julga e propõe deltas + dado de incerteza (aleatoriedade) por cima |
| **Idioma** | Inglês (interface + saídas do SLM) |
| **Líderes** | Reais, nomeados (Trump, Lula, Putin, Xi, Milei, Macron) — tom cuidadoso |
| **Modelo** | **Preferência: NVIDIA (Nemotron Nano) como candidato primário** — NVIDIA é patrocinador parceiro. Decisão final por benchmark. Comparar com Gemma 3 12B / Qwen3. Manter MiniCPM4.1-8B na lista (habilita prêmio OpenBMB) |

## 3. Indicadores (World State) — proposta

Cada país tem 8 indicadores 0-100 (fonte da verdade = código, NÃO o texto do LLM):

1. **Economy** — crescimento, emprego, inflação
2. **Approval** — popularidade do líder
3. **Security** — ordem interna, crime, terrorismo
4. **Social cohesion** — polarização, protestos, unidade
5. **Public services** — educação + saúde
6. **Fiscal health** — contas públicas, dívida
7. **International power** — influência/diplomacia/poder militar
8. **Institutional stability** — risco de golpe/impeachment/ruptura

→ **Game over** se `Approval` E `Institutional stability` caírem abaixo de um limiar simultaneamente
(ou um evento-gatilho dispara com esses dois baixos).

## 4. Os 8 objetivos

No início, o SLM recebe o **perfil inicial do país em 2025** (status dos indicadores + contexto real) e
gera **8 objetivos personalizados e mensuráveis** contra os indicadores. Validados por código para serem
checáveis (ex: "Approval ≥ 60 em dezembro", "International power +15", "evitar recessão = Economy não cai
abaixo de 40 por 3 meses"). O perfil reflete o arquétipo do país (imperialista → poder; emergente →
economia+serviços; etc.).

## 5. Agentes (elenco fixo por país)

Personas persistentes, cada uma com voz, agenda e memória das suas decisões:

- **Finance Minister** — pressiona por responsabilidade fiscal vs. gasto popular
- **Opposition Leader** — ataca, explora suas falhas, sobe se a aprovação cai
- **Media / Press** — enquadra suas decisões, amplifica acertos e crises
- **Key Foreign Leader** — varia por país (ex: EUA↔China/Rússia; Argentina↔FMI/Brasil)
- **Voice of the People** — humor popular, protestos, redes sociais

O SLM dá voz a esses agentes nas narrações e reações. Memória = histórico resumido das decisões + estado
de relação (ex: oposição "hostil/neutra/cooptada").

## 6. Loop de turno (mensal)

```
1. Engine seleciona 1-3 eventos do mês (sementes reais do país + condicionados ao state atual)
2. SLM (Narrador) apresenta cada evento + falas dos agentes relevantes        [structured out]
3. SLM (Options) sugere 2-4 ações plausíveis                                   [structured out]
4. Jogador responde em texto livre (ou escolhe uma sugestão)
5. SLM (Juiz) classifica a ação, propõe deltas + justificativa + reação dos agentes  [structured out]
6. Engine valida/clampa deltas, aplica dado de incerteza, atualiza World State
7. Checa objetivos + condição de game over
8. Avança o mês
```

## 7. Arquitetura: engine determinística + SLM como narrador/juiz com I/O estruturado

**O state é a fonte da verdade. O SLM preenche os espaços, não controla a máquina.**

- **World State (código/JSON)**: indicadores, objetivos, mês, histórico/memória
- **Event Engine (código)**: deck de eventos por país-mês (sementes reais 2025), pré-condições por state
- **SLM (3 papéis, sempre JSON validado)**: Narrador · Juiz/Interpretador de texto livre · Gerador de opções
- **Guardrails (código)**: schema validation + retry · clamp de deltas (ex: ±15/decisão) · dado de
  incerteza · roteamento de ações absurdas para consequências (não quebra o jogo) · filtro de tom
- **Setup (SLM)**: gera os 8 objetivos a partir do perfil inicial

## 8. Hackathon — alvos

- **Track 2** (delight + IA load-bearing): o jogo não existe sem a IA julgando/narrando ✔
- **Bonus quests naturais**: 🔌 Off the Grid (modelo 100% local no Space) · 🎨 Off-Brand (UI de jogo custom, não cara de Gradio) · 📓 Field Notes (blog do processo) · 🎯 Well-Tuned (se houver LoRA) · 🦙 Llama Champion (se usar llama.cpp)
- **Prêmios extras**: MiniCPM → OpenBMB ($10k) · Nemotron → NVIDIA (parceiro)
- **Entregáveis**: Space funcionando · demo video · social post

## 9. Regras detalhadas

→ Ver **[GAME_RULES.md](GAME_RULES.md)**: sistema de deltas, dado de incerteza, limiares de game over
e valores iniciais por país, seleção de eventos, memória dos agentes, e os schemas JSON dos papéis do SLM.

Ainda pendente de execução (não de decisão):
- **Curadoria das sementes reais de 2025** por país (candidato ideal para a skill `deep-research`)
- Tuning fino dos números após playtests
