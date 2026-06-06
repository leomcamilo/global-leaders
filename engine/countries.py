"""Country definitions — initial 2025 state, regime, real-named roster, collapse rules
(GAME_RULES.md §3, §3.1, §4; COUNTRY_SCENARIOS.md §2, §4).

Rosters are 8–10 real figures per country. The keys are stable (mechanics); the SLM Cast
Designer fleshes out personas at game start. Non-USA rosters are a solid first draft to be
refined by the deep-research curation pass.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from engine.agents import Figure, fig


@dataclass
class CollapseRule:
    """Early game-over thresholds (GAME_RULES.md §3)."""

    gov: str  # "dem" | "auto"
    approval_min: int = 25
    inst_min: int = 35
    eco_min: int = 25
    coh_min: int = 25
    universal_floor: int = 12


@dataclass
class CountryDef:
    key: str
    name: str
    leader: str
    archetype: str
    indicators: dict[str, int]
    collapse: CollapseRule
    roster: list[Figure] = field(default_factory=list)
    factions: dict[str, int] = field(default_factory=dict)
    # "approachable" | "challenging" | "brutal" — surfaced at country select so a player knows
    # what they're picking (validated by Nemotron playtests: USA/Brazil survive easily; France,
    # Argentina and China are high-variance / can collapse early).
    difficulty: str = "challenging"

    @property
    def agents(self) -> dict[str, Figure]:
        """Roster as a key->Figure dict (what the engine references)."""
        return {f.key: f for f in self.roster}


# ---------------------------------------------------------------------------------
# Rosters. Order of indicators in comments: eco apr sec coh serv fisc intl inst.
# ---------------------------------------------------------------------------------

USA_ROSTER = [
    fig("vice_president", "JD Vance", "Vice President", "cabinet", "loyalist",
        ["maga-base", "tech-right", "immigration"]),
    fig("sec_state", "Marco Rubio", "Secretary of State", "cabinet", "hawk",
        ["china", "iran", "venezuela", "latam"]),
    fig("sec_defense", "Pete Hegseth", "Secretary of Defense", "military", "military",
        ["military", "culture-war"]),
    fig("sec_health", "Robert F. Kennedy Jr.", "HHS Secretary", "cabinet", "health",
        ["maha", "pharma", "vaccines"]),
    fig("attorney_general", "Pam Bondi", "Attorney General", "cabinet", "justice",
        ["epstein", "immigration-enforcement", "loyalty"]),
    fig("sec_treasury", "Scott Bessent", "Treasury Secretary", "cabinet", "treasury",
        ["tariffs", "markets", "debt"]),
    fig("doge", "Elon Musk", "DOGE / volatile ally", "cabinet", "loyalist",
        ["spending-cuts", "tech"], approval=0.3, fiscal_health=0.6, social_cohesion=-0.2),
    fig("opposition_house", "Hakeem Jeffries", "House Minority Leader", "opposition", "opposition",
        ["democracy", "healthcare", "rights"]),
    fig("fed_chair", "Jerome Powell", "Federal Reserve Chair", "institution", "institution",
        ["interest-rates", "inflation"]),
    fig("elites", "Wall Street & Big Tech", "Big Tech & corporate lobbies", "elite", "elite",
        ["markets", "big-tech", "ai", "chips", "deregulation", "tax-cuts"], influence=0.8),
    fig("press", "the national press", "Press / Media", "society", "media",
        ["scandals", "civil-liberties"]),
    fig("voice", "American voters", "Voice of the People", "society", "society",
        ["cost-of-living", "immigration"]),
]

BRAZIL_ROSTER = [
    fig("vice_president", "Geraldo Alckmin", "Vice President", "cabinet", "loyalist", ["industry", "moderation"]),
    fig("sec_finance", "Fernando Haddad", "Finance Minister", "cabinet", "treasury", ["fiscal-rule", "taxes"]),
    fig("sec_justice", "Ricardo Lewandowski", "Justice Minister", "cabinet", "justice", ["security", "police"]),
    fig("supreme_court", "Alexandre de Moraes", "Supreme Court (STF)", "institution", "institution",
        ["rule-of-law", "disinformation"]),
    fig("opposition", "Jair Bolsonaro / PL", "Opposition leader", "opposition", "opposition",
        ["amnesty", "trial", "evangelicals"]),
    fig("defense", "José Múcio", "Defense Minister", "military", "military", ["armed-forces"]),
    fig("foreign", "Mauro Vieira", "Foreign Minister", "cabinet", "diplomat", ["brics", "mercosur", "us-tariffs"]),
    fig("press", "Brazilian press", "Press / Media", "society", "media", ["corruption", "scandals"]),
    fig("elites", "Faria Lima, agronegócio & Globo/Record", "Financial, agribusiness & media elite",
        "elite", "elite", ["fiscal-rule", "agribusiness", "markets", "media-narrative"], influence=0.9,
        social_cohesion=0.2),
    fig("voice", "the Brazilian street", "Voice of the People", "society", "society",
        ["food-prices", "jobs", "crime"]),
]

RUSSIA_ROSTER = [
    fig("premier", "Mikhail Mishustin", "Prime Minister", "cabinet", "treasury", ["economy", "sanctions"]),
    fig("foreign", "Sergei Lavrov", "Foreign Minister", "cabinet", "diplomat", ["ukraine", "us", "china"]),
    fig("defense", "Andrei Belousov", "Defense Minister", "military", "military", ["war", "procurement"]),
    fig("army_chief", "Valery Gerasimov", "Chief of the General Staff", "military", "military", ["front", "mobilisation"]),
    fig("security_council", "Dmitry Medvedev", "Security Council Deputy Chair", "cabinet", "hawk",
        ["escalation", "nuclear-rhetoric"]),
    fig("opposition", "the exiled opposition", "Opposition (exiled)", "opposition", "opposition",
        ["repression", "elections"]),
    fig("foreign_leader", "Volodymyr Zelensky", "Ukraine's President", "foreign", "foreign", ["war", "peace-talks"]),
    fig("press", "state media", "State Media", "society", "media", ["propaganda", "morale"]),
    fig("elites", "the oligarchs & siloviki", "Oligarchs & security barons", "elite", "elite",
        ["assets", "regime-protection", "war-economy"], influence=0.7,
        institutional_stability=0.5, security=0.3),
    fig("voice", "the Russian public", "Voice of the People", "society", "society", ["wages", "war-fatigue"]),
]

CHINA_ROSTER = [
    fig("premier", "Li Qiang", "Premier", "cabinet", "treasury", ["growth", "property", "stimulus"]),
    fig("econ_czar", "He Lifeng", "Economic Czar", "cabinet", "treasury", ["trade-war", "industry"]),
    fig("foreign", "Wang Yi", "Foreign Minister", "cabinet", "diplomat", ["us", "taiwan", "global-south"]),
    fig("military_chief", "Zhang Youxia", "CMC Vice-Chair (loyal)", "military", "pla", ["pla", "taiwan", "loyalty"]),
    fig("security", "Chen Wenqing", "Security Chief", "cabinet", "security", ["dissent", "surveillance"]),
    fig("opposition", "reformist Politburo faction", "Reformist faction", "opposition", "opposition",
        ["openness", "succession"]),
    fig("foreign_leader", "the US President", "Strategic rival", "foreign", "foreign", ["tariffs", "tech-curbs"]),
    fig("press", "People's Daily", "Party Media", "society", "media", ["narrative", "unity"]),
    fig("elites", "state-linked tycoons", "Tycoons (subordinate to the Party)", "elite", "elite",
        ["markets", "private-capital", "ai-chips"], influence=0.3),
    fig("voice", "the urban middle class", "Voice of the People", "society", "society",
        ["youth-unemployment", "housing"]),
]

ARGENTINA_ROSTER = [
    fig("vice_president", "Victoria Villarruel", "Vice President", "cabinet", "loyalist", ["security", "right"]),
    fig("sec_economy", "Luis Caputo", "Economy Minister", "cabinet", "treasury", ["inflation", "imf", "austerity"]),
    fig("chief_advisor", "Karina Milei", "General Secretary (sister)", "cabinet", "loyalist", ["loyalty", "strategy"]),
    fig("sec_security", "Patricia Bullrich", "Security Minister", "cabinet", "security", ["protests", "order"]),
    fig("opposition", "Cristina Kirchner / Peronism", "Opposition leader", "opposition", "opposition",
        ["pensions", "social-spending"]),
    fig("imf", "the IMF", "Lender of last resort", "institution", "institution", ["targets", "reserves"]),
    fig("press", "Argentine press", "Press / Media", "society", "media", ["austerity-costs", "scandals"]),
    fig("elites", "agro-export & financial elite", "Campo & financial markets", "elite", "elite",
        ["dollar", "exports", "markets", "deregulation"], influence=0.7),
    fig("voice", "workers & retirees", "Voice of the People", "society", "society", ["pensions", "wages", "prices"]),
]

FRANCE_ROSTER = [
    fig("prime_minister", "François Bayrou", "Prime Minister", "cabinet", "loyalist", ["budget", "survival"]),
    fig("sec_economy", "the Economy Minister", "Economy Minister", "cabinet", "treasury", ["deficit", "eu-rules"]),
    fig("opposition_rn", "Marine Le Pen / Jordan Bardella", "RN opposition", "opposition", "opposition",
        ["immigration", "no-confidence"]),
    fig("opposition_left", "Jean-Luc Mélenchon", "Left opposition", "opposition", "opposition",
        ["pensions", "purchasing-power"]),
    fig("interior", "the Interior Minister", "Interior Minister", "cabinet", "security", ["protests", "banlieues"]),
    fig("eu", "the EU Commission", "Brussels", "institution", "institution", ["deficit-procedure", "rules"]),
    fig("foreign_leader", "Ukraine & NATO", "European security", "foreign", "foreign", ["ukraine", "defense"]),
    fig("press", "French press", "Press / Media", "society", "media", ["strikes", "scandals"]),
    fig("elites", "business & media elite (CAC 40, Bolloré)", "Corporate & media elite", "elite", "elite",
        ["markets", "deficit", "media-narrative"], influence=0.6, social_cohesion=0.2),
    fig("voice", "French citizens", "Voice of the People", "society", "society", ["cost-of-living", "pensions"]),
]


COUNTRIES: dict[str, CountryDef] = {
    "usa": CountryDef(
        key="usa", name="United States", leader="Donald Trump", archetype="international_power",
        indicators=dict(economy=62, approval=47, security=55, social_cohesion=35,
                        public_services=50, fiscal_health=38, international_power=85,
                        institutional_stability=65),
        collapse=CollapseRule("dem", approval_min=25, inst_min=35),
        roster=USA_ROSTER, difficulty="approachable",
    ),
    "brazil": CountryDef(
        key="brazil", name="Brazil", leader="Luiz Inácio Lula da Silva", archetype="public_services",
        indicators=dict(economy=50, approval=45, security=40, social_cohesion=38,
                        public_services=48, fiscal_health=35, international_power=55,
                        institutional_stability=58),
        collapse=CollapseRule("dem", approval_min=22, inst_min=35),
        roster=BRAZIL_ROSTER, difficulty="approachable",
    ),
    "russia": CountryDef(
        key="russia", name="Russia", leader="Vladimir Putin", archetype="institutional_stability",
        indicators=dict(economy=42, approval=70, security=50, social_cohesion=55,
                        public_services=45, fiscal_health=40, international_power=60,
                        institutional_stability=72),
        collapse=CollapseRule("auto", inst_min=30, eco_min=20, coh_min=25),
        roster=RUSSIA_ROSTER, difficulty="challenging",
    ),
    "china": CountryDef(
        key="china", name="China", leader="Xi Jinping", archetype="international_power",
        indicators=dict(economy=58, approval=65, security=60, social_cohesion=58,
                        public_services=55, fiscal_health=50, international_power=78,
                        institutional_stability=75),
        collapse=CollapseRule("auto", inst_min=30, eco_min=25, coh_min=25),
        factions=dict(party_loyalty=70, pla_loyalty=55, coup_plot_progress=0),
        roster=CHINA_ROSTER, difficulty="brutal",
    ),
    "argentina": CountryDef(
        key="argentina", name="Argentina", leader="Javier Milei", archetype="economy",
        indicators=dict(economy=30, approval=50, security=45, social_cohesion=35,
                        public_services=35, fiscal_health=25, international_power=35,
                        institutional_stability=45),
        collapse=CollapseRule("dem", approval_min=22, inst_min=35, eco_min=15),
        roster=ARGENTINA_ROSTER, difficulty="brutal",
    ),
    "france": CountryDef(
        key="france", name="France", leader="Emmanuel Macron", archetype="social_cohesion",
        indicators=dict(economy=52, approval=30, security=48, social_cohesion=40,
                        public_services=55, fiscal_health=35, international_power=62,
                        institutional_stability=55),
        collapse=CollapseRule("dem", approval_min=25, inst_min=35),
        roster=FRANCE_ROSTER, difficulty="brutal",
    ),
}


def get_country(key: str) -> CountryDef:
    try:
        return COUNTRIES[key]
    except KeyError:
        raise KeyError(f"unknown country {key!r}; choose from {sorted(COUNTRIES)}")
