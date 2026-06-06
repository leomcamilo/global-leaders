# Global Leaders — Plano de Aprofundamento de Cenários

> Como dar profundidade a cada país: **figuras reais nomeadas** com personas geradas pelo SLM
> (variando levemente a cada partida), **decks de eventos reais de 2025** (domésticos + internacionais)
> e **eventos globais compartilhados** que se manifestam em vários países ao mesmo tempo.
> Complementa [GAME_DESIGN.md](GAME_DESIGN.md) e [GAME_RULES.md](GAME_RULES.md).

---

## 1. As três camadas de profundidade

1. **Elenco real, persona viva** — cada país tem 6–8 figuras reais (gabinete, oposição, militares,
   instituições, mídia, povo). As *keys* e o *vetor de utilidade base* são fixos (mecânica estável);
   o Nemotron gera, no início de cada jogo, os **traços, valores e agenda oculta** de cada figura, e
   pode *ajustar levemente* o vetor de utilidade dentro de limites → comportamento diferente a cada partida.
2. **Eventos reais por país** — deck curado de fatos de 2025 (ex.: EUA → tarifas, guerra do Irã, caso
   Epstein, imigração/ICE, DOGE/Musk…). Anchored (datados) + conditional (disparados pelo state).
3. **Eventos globais compartilhados** — um mesmo fato atinge vários países com *hooks* distintos
   (guerra do Irã → EUA decide intervir; Rússia vê oportunidade; China teme o petróleo; Brasil sente no
   preço dos combustíveis). Opcionalmente, um *world modifier* aplica um efeito de fundo aos países sem hook.

---

## 2. Mudanças no modelo de dados

### 2.1 `Figure` — roster nomeado real (substitui o `AgentDef` genérico em `countries.py`)

```python
@dataclass
class Figure:
    key: str            # ESTÁVEL p/ a mecânica: "sec_state", "opposition_house", ...
    name: str           # "Marco Rubio"
    role: str           # "Secretary of State"
    faction: str        # cabinet | opposition | military | institution | foreign | society
    base_utility: dict[str, float]   # indicadores que valoriza (base mecânica)
    themes: list[str]   # assuntos que lhe importam: ["china", "iran", "immigration"]
    adjustable: bool = True          # se o SLM pode mexer no utility (figuras "institution" = False)
```

`CountryDef.roster: list[Figure]` (6–8 por país). As 5 categorias de agente de hoje viram um roster
nomeado mais rico; a engine continua referenciando `key` (compatível com o resolver/teoria dos jogos).

### 2.2 Persona gerada no setup — **novo papel do SLM: "Cast Designer"** (§7.5)

No `Game.start()`, além dos 8 objetivos, o Nemotron recebe o roster + contexto 2025 e devolve, por figura:

```json
{
  "cast": [
    {"key": "sec_state", "traits": ["hawkish", "disciplined"], "core_value": "American primacy",
     "hidden_agenda": "Wants to be seen as the natural successor.",
     "utility_shift": {"international_power": +0.2, "approval": -0.1}}
  ]
}
```

Guardrails (código):
- `utility_shift` clampado a **±0.3** por indicador e só aplicado a figuras `adjustable=True`.
- Soma das mudanças por figura limitada (não vira outra pessoa).
- A mecânica de stance segue **determinística** sobre `base_utility + shift`; o SLM dá voz/agenda, não controla números.
- Variação por partida via seed/temperatura → cada jogo, personas levemente diferentes.

Persistido em `state.cast[key] = {traits, core_value, hidden_agenda, utility}`. Entra no save (replay).

### 2.3 Eventos: `CountryEvent` (ampliado) + `GlobalEvent` (novo)

`Event` ganha o campo `figures: list[str]` (quais figuras se pronunciam/agem). O Narrador e o Juiz
recebem as personas dessas figuras → reações específicas e coerentes.

```python
@dataclass
class GlobalEvent:
    id: str
    month: int | None              # datado, ou None p/ condicional global
    title: str
    fact: str
    scope: list[str]               # países diretamente atingidos
    hooks: dict[str, dict]         # country_key -> {dilemma, touches, figures, stakeholder_positions}
    world_modifier: dict | None    # efeito de fundo nos países SEM hook (ex.: choque de petróleo)
```

### 2.4 `WorldModifier` — choques globais de fundo (camada opcional)

Choque (preço do petróleo, juros EUA, recessão global) que ajusta indicadores por **perfil do país**:
exportador de petróleo ganha `economy` quando o preço sobe; importador perde; todos sofrem inflação →
pressão em `approval`/`social_cohesion`. Tabela perfil × choque, aplicada por alguns meses.

---

## 3. Loop de turno atualizado

```
1. (setup, 1x) SLM gera objetivos + personas do elenco
2. A cada mês:
   a. Disparar GlobalEvents do mês → injetar a manifestação (hook) no deck do país, se houver
   b. Aplicar world_modifiers ativos (efeito de fundo) aos indicadores
   c. Selecionar 1–3 eventos (globais-hook + country deck), ponderados pela fraqueza (§5.1 das regras)
   d. Para cada evento: narrar (com personas) → opções → decisão → julgar → resolver
   e. Upkeep + checagem de objetivos/game over
```

---

## 4. Exemplo concreto — Estados Unidos (Trump, 2025)

### 4.1 Roster (rascunho — refinar na pesquisa)

| key | Figura | Cargo | faction | valoriza (base_utility) | temas |
|---|---|---|---|---|---|
| `vice_president` | JD Vance | Vice President | cabinet | approval, social_cohesion, international_power | base-MAGA, tech-right, immigration |
| `sec_state` | Marco Rubio | Secretary of State | cabinet | international_power, security | china, iran, venezuela, latam |
| `sec_defense` | Pete Hegseth | Secretary of Defense | military | security, international_power | military, culture-war |
| `sec_health` | Robert F. Kennedy Jr. | HHS Secretary | cabinet | public_services(à-sua-maneira), approval | health (MAHA), pharma, vaccines |
| `attorney_general` | Pam Bondi | Attorney General | cabinet | security, institutional_stability | justiça, Epstein, imigração |
| `sec_treasury` | Scott Bessent | Treasury Secretary | cabinet | economy, fiscal_health | tarifas, mercados, dívida |
| `opposition_house` | Hakeem Jeffries | House Minority Leader | opposition | social_cohesion(+), approval(−) | democracia, saúde, direitos |
| `fed_chair` | Jerome Powell | Fed Chair | institution (fixo) | fiscal_health, economy | juros, inflação |
| `press` | a imprensa nacional | — | society | approval, social_cohesion | escândalos, liberdades |
| `voice` | os eleitores | — | society | economy, public_services, approval | custo de vida, imigração |

(Figura volátil opcional: **Elon Musk / DOGE** — alia-se e depois rompe; ótimo p/ um arco de ruptura.)

### 4.2 Eventos dos EUA (anchored + conditional) — a confirmar/expandir na pesquisa

- **abr** — "Liberation Day": tarifas amplas → `economy`, `international_power`, `fiscal_health` *(GLOBAL)*
- **jun** — Guerra Israel–Irã / ataques às instalações nucleares → `international_power`, `security`, `approval` *(GLOBAL)*
- **(recorrente)** — Caso/arquivos **Epstein**: racha a base, pressiona Bondi → `social_cohesion`, `approval`, `institutional_stability`
- ICE / megaoperações de imigração & protestos → `security`, `social_cohesion`, `approval`
- Negociações Ucrânia–Rússia / Zelensky → `international_power` *(GLOBAL c/ Rússia)*
- DOGE / cortes & rompimento com Musk → `fiscal_health`, `public_services`, `approval`
- Fed, juros e inflação (Powell) → `economy`, `fiscal_health`
- Protestos "No Kings" → `social_cohesion`
- Briga do shutdown orçamentário → `fiscal_health`, `institutional_stability`

---

## 5. Eventos globais (sementes compartilhadas)

| Evento global | Mês | Atinge (hooks) | world_modifier (países sem hook) |
|---|---|---|---|
| Guerra Israel–Irã | jun | EUA, Rússia, China, Brasil | choque do petróleo |
| Choque do preço do petróleo | (derivado) | Rússia(+), Brasil(+/inflação), China(−), EUA(misto) | inflação global leve |
| Guerra comercial / tarifas dos EUA | abr+ | EUA, China, França(UE), Brasil | desaceleração do comércio |
| Trajetória da guerra na Ucrânia | recorrente | Rússia, EUA, França(UE) | preços de energia/grãos |

Cada hook descreve o *mesmo fato* sob a ótica daquele país (dilema, figuras, indicadores tocados),
de modo que jogar a Rússia na guerra do Irã é uma experiência diferente de jogar os EUA.

---

## 6. Briefs de pesquisa por país (entrada para a skill `deep-research`)

Para **cada** país, um relatório com saída já no formato de sementes:
1. **Roster real 2025** — figuras-chave (gabinete, oposição, militares, instituições), cargos e posições/valores.
2. **6–10 fatos domésticos** de 2025 (datados quando possível).
3. **4–8 fatos internacionais** de 2025.
4. **Boatos/escândalos** plausíveis e ruídos políticos do período.
5. Marcar quais fatos são **globais/compartilhados** com outros países.

Saída: `seeds_<país>.json` (eventos) + `roster_<país>.json` (figuras). Um relatório por país.

---

## 7. Faseamento da implementação

- **F1 — Roster real (todos os 6 países):** refatorar `countries.py` para `Figure` + `base_utility` + nomes
  reais. Ajustar `agents.py` p/ aplicar `base_utility + shift` com bounds. (Sem SLM ainda; usa defaults.)
- **F2 — Cast Designer:** novo papel SLM (schema §7.5 + prompt), persona no `state.cast`, guardrails de bounds.
  Narrador/Juiz passam a receber as personas.
- **F3 — Deck EUA via `deep-research`:** primeiro país completo (roster + eventos), validar ponta a ponta.
- **F4 — GlobalEvent + engine de injeção:** estrutura + seleção + 2 eventos globais (Irã, petróleo).
- **F5 — Decks dos outros 5 países** via `deep-research`.
- **F6 — WorldModifier** (opcional): choques de fundo por perfil de país.

## 8. Impacto no código (módulos)

| Módulo | Mudança |
|---|---|
| `countries.py` | `Figure` + `roster` real por país |
| `agents.py` | aplica `utility_shift` com clamp (±0.3), categorias por `faction` |
| `schemas.py` | novo schema "Cast" (§7.5) + `figures` em Event |
| `prompts.py` | prompt do Cast Designer; narrar/julgar recebem personas |
| `events.py` | `GlobalEvent`, injeção de hooks, `WorldModifier` |
| `game.py` | `start()` chama Cast Designer; loop dispara globais + modifiers |
| `state.py` | `cast`, `active_modifiers` (entram no save) |

## 9. Decisões confirmadas

- **Roster rico: 8–10 figuras por país** (gabinete + oposição + militar + instituição + mídia + povo + 1 volátil).
- **Variação mecânica + narrativa, com limites:** o SLM gera traços/agenda E ajusta o utility dentro de
  bounds (**±0.3**, só p/ figuras `adjustable`); a mecânica de stance segue determinística sobre o resultado.
- **Eventos globais com *world modifier*:** países sem hook sofrem efeito de fundo por perfil (ex.: choque
  do petróleo → Rússia +economy, China −economy, todos +inflação→pressão em approval/cohesion).
