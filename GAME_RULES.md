# Global Leaders — Regras Detalhadas & Schemas

> Complemento de [GAME_DESIGN.md](GAME_DESIGN.md). Aqui ficam os números, fórmulas e contratos JSON.
> **Princípio-mestre:** o SLM *propõe*; o código *valida, clampa e aplica*. O `World State` é a verdade.
> Todos os valores numéricos abaixo são *tuning inicial* — ajustáveis após playtest.

---

## 0. Fundamentos de design: Método do Caso + Teoria dos Jogos

Duas lentes orientam *como* os eventos são escritos e *como* o Juiz avalia — para o jogo premiar
raciocínio defensável, e não "adivinhar a resposta certa".

### 0.1 Método do Caso (estilo Harvard)

Um "caso" é uma situação real e ambígua, contada do ponto de vista de um **protagonista** que enfrenta
uma decisão, com **informação incompleta por design** e **sem resposta única certa**. Cada evento do
jogo é um caso:

- **Protagonista** = o jogador-líder.
- **Dilema** = a tensão central; toda escolha tem custo.
- **Informação incompleta** = parte do contexto fica oculta → é justamente o que o *dado de incerteza*
  (§2.1) representa: consequências que você não tinha como prever no momento da decisão.
- **Stakeholders em conflito** = os agentes (ver GAME_DESIGN §5), cada um defendendo sua posição.
- **Sem gabarito** = várias decisões são defensáveis. O Juiz (§7.4) **não marca certo/errado**; avalia
  **coerência interna**, **alinhamento com seus objetivos** e **como você lida com os trade-offs**.

→ Cada semente/evento ganha campos de caso: `dilemma`, `hidden_info`, `stakeholder_positions` (§9).

### 0.2 Teoria dos Jogos

Os stakeholders são **jogadores com payoffs próprios**: reagem por incentivo, não por roteiro.

- **Vetor de utilidade por agente** = os indicadores que ele valoriza (ex: Finance Minister →
  `fiscal_health`+`economy`; Opposition → ganha quando sua `approval` cai). O código computa a reação
  esperada de cada agente a uma decisão (quanto ela move os indicadores que ele valoriza) → atualiza o
  `stance` de forma principled; o SLM apenas **narra** essa reação.
- **Diplomacia = jogo repetido** (dilema do prisioneiro / tit-for-tat): com o Key Foreign Leader você
  coopera ou trai, e ele responde com base no histórico da relação — dá memória e peso à geopolítica.
- **Coalizão**: cooptar a oposição (`hostile → allied`) custa capital político (formação de aliança).
- **Metagame** (Howard): cada crise é enquadrada como um jogo em que cada stakeholder persegue seus
  objetivos com as opções disponíveis → o Option Generator (§7.3) gera opções que favorecem payoffs
  de stakeholders diferentes.

---

## 1. Indicadores

8 indicadores, inteiros `0–100`. Chaves usadas no código/JSON:

`economy` · `approval` · `security` · `social_cohesion` · `public_services` ·
`fiscal_health` · `international_power` · `institutional_stability`

---

## 2. Sistema de deltas (como uma decisão move o state)

O SLM **não** cospe números livres. Ele classifica a ação em **magnitude** e lista os indicadores
afetados; o **código** mapeia magnitude → range permitido e clampa.

| Magnitude | Range por indicador | Significado |
|---|---|---|
| `minor` | ±1 a ±3 | gesto, declaração, ajuste pequeno |
| `moderate` | ±3 a ±6 | política setorial, decreto |
| `major` | ±6 a ±10 | reforma, mudança de rumo |
| `radical` | ±10 a ±15 | medida extrema (pode disparar follow-ups) |

> **Calibração (pós-playtest com Nemotron).** Ranges suavizados (acima); no máximo **3** indicadores por
> decisão; no máximo **2 eventos por mês** (evita pile-ups brutais). Ver §3 para a resiliência.

**Regras de game design (validadas em código):**

1. **Sem almoço grátis.** Ações `major`/`radical` exigem ≥1 indicador com efeito **negativo** (trade-off).
   Se o SLM não fornecer, o código injeta um custo padrão no indicador "natural" da ação
   (ex: gasto social → `-fiscal_health`).
2. **Clamp de magnitude.** Se o SLM propõe `+50`, o código clampa ao teto da magnitude (ex: `+20`).
3. **Limite de indicadores tocados.** No máximo 4 indicadores por decisão (evita "tudo melhora").
4. **Tetos/pisos.** Após aplicar, `clamp(0, 100)`.

### 2.1 Dado de incerteza

Cada delta proposto `Δ` (já clampado) passa por uma rolagem antes de virar `Δ_final`:

```
roll      = clamp(normal(mean=1.0, sd=0.25), 0.4, 1.6)
Δ_final   = round(Δ * roll)

# eventos de cauda (drama), checados 1x por decisão:
p_backfire = 0.07   -> a decisão "saiu pela culatra": inverte o sinal dos efeitos e aplica 0.5x
p_windfall = 0.07   -> "deu surpreendentemente certo": aplica 1.5x
```

`backfire`/`windfall` são marcados num flag que o **Narrador do próximo turno** usa para explicar o twist.
A rolagem usa um **RNG com seed por partida** (`seed + turno + índice`) → replays reproduzíveis e justos.

---

## 3. Condição de game over (por país)

Cada país tem uma `collapse_rule`. Dois arquétipos + uma regra universal:

- **Democracias** (USA, Brasil, França, Argentina) — impeachment / moção de censura / renúncia:
  `approval < A_min  AND  institutional_stability < I_min`
- **Autocracias** (Rússia, China) — golpe palaciano / colapso:
  `institutional_stability < I_min  AND  (economy < E_min  OR  social_cohesion < S_min)`
- **Universal** (qualquer país) — crise terminal:
  qualquer indicador-chave `< 15` por **2 meses consecutivos**.

Quando dispara, o jogo encerra antes de dezembro com uma cena de queda narrada pelo SLM.

**Resiliência (anti-espiral, calibração).** No upkeep mensal, indicadores em extremos baixos recuperam um
pouco (`< 25 → +2`, `< 35 → +1`) e muito altos regridem (`> 88 → −1`). Evita que um país apanhado entre em
espiral da morte por acúmulo de eventos negativos, sem apagar a dificuldade (`engine/resolver._resilience`).

### 3.1 Medidores de facção (variáveis ocultas específicas de país)

Além dos 8 indicadores universais, cada país pode ter 1–2 **medidores de facção** (`0–100`, semi-ocultos —
o jogador percebe por dicas narrativas, não por número exato) que certos eventos movem e que disparam
**finais especiais**. No MVP, detalhados para a **China**; extensível depois (Rússia → siloviki/oligarcas;
EUA → lealdade do partido no Congresso; etc.).

**China — duas facções, dois caminhos de queda** (além do colapso econômico universal):

- **`party_loyalty`** — lealdade do Partido / Politburo. Cai com economia/coesão ruins e fracasso
  prolongado. Se `< 25` → **Party ouster**: você é afastado numa plenária e um sucessor assume
  (queda "elegante", nos bastidores).
- **`pla_loyalty`** — lealdade do Exército de Libertação Popular (ELP). **Sobe** ao investir no exército
  *e* desarticular cliques; **cai** ao cortar/humilhar o ELP ou **tolerar cliques**. Tolerar a clique faz
  amadurecer um contador oculto `coup_plot_progress`.

**O plano do ELP — contrafactual de 2025.** Na realidade, Xi expurgou a cúpula militar em 2025
(He Weidong — o nº 2 e vice da Comissão Militar Central —, Miao Hua e outros, sob a bandeira de
"anticorrupção"/desmonte de cliques; a CMC ficou com mais vagas que em qualquer momento desde Mao). No
jogo isso vira um **caso âncora**: você descobre uma clique no alto comando do ELP e precisa decidir.
Se você **não souber controlá-la** — ignorar os sinais, deixar `coup_plot_progress` chegar a 100, ou
`pla_loyalty < 20` —, o plano que estava sendo investigado **dá certo** → **golpe militar do ELP**,
fim de jogo dramático, independente dos demais indicadores.

Tensão dupla única da China: agradar o Partido **e** manter o Exército na rédea — duas facções com
payoffs diferentes (teoria dos jogos, §0.2) que você equilibra o ano inteiro. Purgar cedo demais sem
provas custa `social_cohesion`/`institutional_stability`; tarde demais, o golpe amadurece.

**Avisos (calibração "meio-termo").** A maturação começa quando `pla_loyalty < 50` e é relativamente
rápida, MAS quando `coup_plot_progress` cruza **40** e **70** o jogo dispara um **aviso narrativo**
(`state.pending_alert`, lido pelo Narrador do mês seguinte: "rumores de deslealdade no ELP"). O jogador é
avisado e tem 1–2 meses para reagir — desarmar a clique exige uma decisão decisiva pró-controle
(`pla_loyalty` aplicado `≥ +6`), não basta tolerar.

---

## 4. Valores iniciais por país (jan/2025) — tuning inicial

> Reflete o arquétipo e o contexto real de início de 2025. Sujeito a curadoria/playtest.
> Ordem: `eco / apr / sec / coh / serv / fisc / intl / inst`  ·  `gov` = tipo de regime.

| País | eco | apr | sec | coh | serv | fisc | intl | inst | gov | game over (limiares) |
|---|---|---|---|---|---|---|---|---|---|---|
| **USA** (Trump) | 62 | 47 | 55 | 35 | 50 | 38 | 85 | 65 | dem | apr<25 ∧ inst<35 |
| **Brasil** (Lula) | 50 | 45 | 40 | 38 | 48 | 35 | 55 | 58 | dem | apr<22 ∧ inst<35 |
| **Rússia** (Putin) | 42 | 70 | 50 | 55 | 45 | 40 | 60 | 72 | auto | inst<30 ∧ (eco<20 ∨ coh<25) |
| **China** (Xi) | 58 | 65 | 60 | 58 | 55 | 50 | 78 | 75 | auto | inst<30 ∧ (eco<25 ∨ coh<25); **+ facções §3.1** |
| **Argentina** (Milei) | 30 | 50 | 45 | 35 | 35 | 25 | 35 | 45 | dem | apr<22 ∧ inst<35 (ou eco<15) |
| **França** (Macron) | 52 | 30 | 48 | 40 | 55 | 35 | 62 | 55 | dem | apr<25 ∧ inst<35 |

Arquétipos de objetivo embutidos: USA → `international_power`; Argentina → `economy`/`fiscal_health`;
França → `approval`/`social_cohesion`; Rússia → manter `institutional_stability`; etc. (o SLM personaliza).

**Medidores de facção iniciais (§3.1).** China: `party_loyalty 70`, `pla_loyalty 55` (clique latente no
ELP), `coup_plot_progress 0`. Demais países: sem medidores de facção no MVP.

---

## 5. Seleção de eventos por mês

A cada mês o engine escolhe **N eventos** (`N = 2` base, faixa 1–3). Três tipos no pool do país:

- **`anchored`** — fato real datado de 2025 (eleição, tarifas, cúpula, guerra). Dispara no seu mês-âncora
  independentemente do state. ~1 slot/mês.
- **`conditional`** — disparado pelo state (ex: `security < 35` → "onda de crime"). Preenche os outros slots.
- **`branching`** — follow-up fictício gerado pelo SLM a partir de uma decisão `radical`/`major` anterior.

### 5.1 Ponderação (pressão dramática onde o jogador está fraco)

Para um evento `e` que toca o indicador `i`:

```
weight(e) = base_weight(e) * Π_i ( 1 + ((50 - state[i]) / 50) * sensitivity )   # sensitivity ≈ 0.6
```

Indicador baixo → peso maior → crises convergem para a fraqueza do jogador. `anchored` ignora peso
(é determinístico). Sem repetição: evento consumido sai do pool (salvo no save).

---

## 6. Memória dentro do orçamento de contexto (SLM pequeno)

Nunca passamos histórico bruto. O prompt de cada chamada recebe um pacote enxuto:

```
[ state atual (8 ints) ]
[ objetivos + progresso ]
[ history_digest  (≤120 tokens) ]
[ stances dos agentes (5x: hostile|neutral|allied + 1 frase) ]
[ evento atual ]
```

- **`history_digest`**: resumo rolante mantido pelo **código**. Últimos 3 meses em 1 linha cada
  (`M04: subiu juros → eco -, apr -`) + 1 linha de sumário comprimido do resto.
- **`stances`**: cada agente guarda `stance` + última fala. Atualizados pelo Juiz a cada turno.

Isso mantém o prompt curto o suficiente para 4–12B e barato de rodar local (Off the Grid).

---

## 7. Schemas JSON dos papéis do SLM

Quatro chamadas, todas com **saída JSON validada + retry**. Campos em inglês (idioma do jogo).

### 7.1 Setup — Objective Generator (1x no início)

**Input:** país, indicadores iniciais, contexto/arquétipo.
```json
{
  "objectives": [
    {
      "id": "obj_1",
      "title": "Tame inflation",
      "description": "Bring the cost-of-living crisis under control by year end.",
      "category": "economy",
      "metric": { "indicator": "economy", "op": ">=", "target": 55, "by_month": 12 },
      "difficulty": "hard"
    }
  ]
}
```
- Exatamente **8** objetivos. `metric` deve ser **checável por código** (`indicator`, `op` ∈ `>= <= >`,
  `target` 0–100, `by_month` 1–12). Alguns podem ser "manter acima de X até dezembro".

### 7.2 Narrator — Event Presenter

**Input:** evento, state, agentes relevantes, flag de twist do turno anterior.
```json
{
  "headline": "Markets reel as new tariffs hit",
  "narrative": "2–4 sentences, dramatic with light humor.",
  "agent_reactions": [
    { "agent": "finance_minister", "stance": "hostile", "quote": "Mr. President, this is madness." }
  ],
  "stakes": "One line: what's at risk if you get this wrong."
}
```

### 7.3 Option Generator

```json
{
  "options": [
    { "id": "A", "label": "Double down", "summary": "...", "tone": "bold" },
    { "id": "B", "label": "Negotiate exemptions", "summary": "...", "tone": "cautious" }
  ]
}
```
- 2–4 opções. `tone` ∈ `bold|cautious|populist|technocratic|defiant|conciliatory`.

### 7.4 Judge — Resolver (o core)

**Input:** evento + ação do jogador (texto livre OU id de opção) + state + agentes.
**Princípio (Método do Caso, §0.1):** não existe "resposta certa". O Juiz avalia coerência, alinhamento
com os objetivos e tratamento dos trade-offs — nunca pune por divergir da história real.
```json
{
  "interpretation": "Restate what the player chose to do.",
  "magnitude": "major",
  "plausibility": "ok",
  "effects": [
    { "indicator": "economy", "direction": "+", "proposed_delta": 7, "reason": "..." },
    { "indicator": "fiscal_health", "direction": "-", "proposed_delta": 6, "reason": "trade-off" }
  ],
  "agent_reactions": [
    { "agent": "opposition_leader", "stance": "hostile", "quote": "...", "stance_changed": true }
  ],
  "consequence_narrative": "What happens as a result, 2–4 sentences.",
  "spawns_followup": false
}
```

**Pós-processamento em código (não confiar no LLM):**
1. `plausibility`:
   - `ok` → aplica efeitos normalmente.
   - `absurd` (possível mas extremo, ex: "declaro guerra a todos") → aplica efeitos catastróficos roteados.
   - `impossible` (ex: "transformo todos em ouro") → **zero efeito**; Narrador recusa com humor.
2. Valida `magnitude` → clampa cada `proposed_delta` ao range da tabela §2.
3. Aplica regra "sem almoço grátis" (§2, regra 1).
4. Aplica dado de incerteza (§2.1).
5. `clamp(0,100)`, atualiza `stances`, atualiza `history_digest`, checa objetivos e game over.

### 7.5 Cast Designer (1x no início)

Para cada figura do roster, gera persona (`traits`, `core_value`, `hidden_agenda`) e pode aplicar um
`utility_shift` por indicador (±0.3, clampado) que ajusta o vetor base — variação entre partidas sem
mudar a mecânica. Instituições (ex.: bancos centrais) não recebem shift. Guardado em `state.cast`.

### 7.6 Lunch — conversa privada com uma figura

A "verdade-base" de cada figura mora em **`engine/prompts/countries/<país>/<chave>.md`** (frontmatter
determinístico com o vetor de utilidade + prosa autoral via glm-5.1: quem é, o que realmente quer, linhas
vermelhas, como fala, quão franco fica num almoço fora dos autos). São legíveis/editáveis por humanos e
pelo modelo. Carregados por `engine/personas.py`.

No "The Room" o jogador clica numa figura (🟢/🟡/🔴) e a leva a um **almoço off-the-record**: faz perguntas
e ela responde **em personagem**, mais franca que em público, segundo seus interesses (teoria dos jogos) e
seu `stance` atual. É **puramente informativo** — não move indicadores nem favor (sem exploit). O transcript
fica em `game.conversations[chave]` (memória da sessão); o modelo recebe o histórico para manter coerência.
```json
{ "reply": "o que a figura diz à mesa (2-4 frases, 1ª pessoa, na voz dela)" }
```
Mudança rara de interesse durante a partida é gravada na sessão (`state.cast`), nunca reescrevendo o `.md`
compartilhado (no Space o filesystem é efêmero). Edição direta do `.md` é fluxo de autoria offline.

---

## 8. Save / Replay

Save = JSON com: `country`, `month`, `state`, `objectives` (+progresso), `history_digest`,
`agent_stances`, `rng_seed`, `consumed_events`. Mesma seed → mesmas rolagens (replay justo).
Para o hackathon, persistir no `gr.State` da sessão Gradio basta; arquivo é nice-to-have.

---

## 9. Próxima execução (ordem definida)

1. [ ] **Protótipo da engine headless** — World State + Resolver + dado de incerteza + medidores de
       facção, em Python puro, testável sem UI nem modelo (com um *fake LLM* stub). Prova o loop e os guardrails.
2. [ ] **Desenhar a fundo o cenário de cada país** (perfil, agentes nomeados, facções, dilemas centrais de 2025).
3. [ ] **Curar o deck de sementes reais de 2025** por país (anchored: ~5–8/país; conditional: ~4–6/país) —
       notícias *e* boatos. Candidato ideal para a skill `deep-research`.
4. [ ] **Benchmark de modelos** NVIDIA Nemotron vs. Gemma 3 12B / Qwen3 nos 6 prompts-padrão.

Estrutura de cada semente:
      ```json
      {
        "id": "usa_2025_04_tariffs", "type": "anchored", "month": 4,
        "title_seed": "Sweeping import tariffs ('Liberation Day')",
        "fact": "In April 2025 the US announced broad tariffs on imports...",
        "touches": ["economy", "international_power", "fiscal_health"],
        "dilemma": "Protect domestic industry and project strength, or avoid a market crash and trade war?",
        "hidden_info": "How hard trading partners will retaliate and how markets price it in.",
        "stakeholder_positions": {
          "finance_minister": "Warns of inflation and market panic.",
          "voice_of_people": "Cheers 'America First', until prices rise.",
          "key_foreign_leader": "Threatens reciprocal tariffs."
        },
        "preconditions": {}, "branchable": true
      }
      ```
