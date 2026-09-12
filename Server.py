import os
import json
import math
import re
import time
import urllib.request
import urllib.parse
import urllib.error

from datetime import datetime, timedelta, timezone
from pathlib import Path
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler


# ============================================================
# MARQUES PRO
# Backend de análise esportiva
# ============================================================

PORT = int(os.getenv("PORT", "8787"))

AF_KEY = os.getenv(
    "API_FOOTBALL_KEY",
    ""
).strip()

ODDS_KEY = os.getenv(
    "ODDS_API_KEY",
    ""
).strip()

CACHE_TTL = int(
    os.getenv("CACHE_TTL", "900")
)

CACHE = {}

DATA_FILE = "marques_pro_history.json"

VERSION = "Marques Pro V17"


# ============================================================
# HORÁRIO DO BRASIL
# ============================================================

BRAZIL_TZ = timezone(
    timedelta(hours=-3)
)


def brazil_now():
    return datetime.now(
        BRAZIL_TZ
    )


def brazil_today():
    return brazil_now().date()


# ============================================================
# LIGAS
# ============================================================

LEAGUES = {

    "Brasil": {
        "id": 71,
        "country": "Brasil",
        "espn": "bra.1",
        "odds": "soccer_brazil_campeonato"
    },

    "Brasil - Série B": {
        "id": 72,
        "country": "Brasil",
        "espn": "bra.2",
        "odds": "soccer_brazil_serie_b"
    },

    "Inglaterra": {
        "id": 39,
        "country": "Inglaterra",
        "espn": "eng.1",
        "odds": "soccer_epl"
    },

    "Inglaterra - Championship": {
        "id": 40,
        "country": "Inglaterra",
        "espn": "eng.2",
        "odds": None
    },

    "Espanha": {
        "id": 140,
        "country": "Espanha",
        "espn": "esp.1",
        "odds": "soccer_spain_la_liga"
    },

    "Espanha - Segunda": {
        "id": 141,
        "country": "Espanha",
        "espn": "esp.2",
        "odds": None
    },

    "Itália": {
        "id": 135,
        "country": "Itália",
        "espn": "ita.1",
        "odds": "soccer_italy_serie_a"
    },

    "Itália - Série B": {
        "id": 136,
        "country": "Itália",
        "espn": "ita.2",
        "odds": None
    },

    "Alemanha": {
        "id": 78,
        "country": "Alemanha",
        "espn": "ger.1",
        "odds": "soccer_germany_bundesliga"
    },

    "Alemanha - 2. Bundesliga": {
        "id": 79,
        "country": "Alemanha",
        "espn": "ger.2",
        "odds": None
    },

    "França": {
        "id": 61,
        "country": "França",
        "espn": "fra.1",
        "odds": "soccer_france_ligue_one"
    },

    "França - Ligue 2": {
        "id": 62,
        "country": "França",
        "espn": "fra.2",
        "odds": None
    },

    "Portugal": {
        "id": 94,
        "country": "Portugal",
        "espn": "por.1",
        "odds": "soccer_portugal_primeira_liga"
    },

    "Holanda": {
        "id": 88,
        "country": "Holanda",
        "espn": "ned.1",
        "odds": "soccer_netherlands_eredivisie"
    },

    "Bélgica": {
        "id": 144,
        "country": "Bélgica",
        "espn": "bel.1",
        "odds": "soccer_belgium_first_div"
    },

    "Turquia": {
        "id": 203,
        "country": "Turquia",
        "espn": "tur.1",
        "odds": "soccer_turkey_super_league"
    },

    "Grécia": {
        "id": 197,
        "country": "Grécia",
        "espn": "gre.1",
        "odds": "soccer_greece_super_league"
    },

    "Áustria": {
        "id": 218,
        "country": "Áustria",
        "espn": "aut.1",
        "odds": "soccer_austria_bundesliga"
    },

    "Suíça": {
        "id": 207,
        "country": "Suíça",
        "espn": "sui.1",
        "odds": "soccer_switzerland_superleague"
    },

    "Estados Unidos - MLS": {
        "id": 253,
        "country": "Estados Unidos",
        "espn": "usa.1",
        "odds": "soccer_usa_mls"
    },

    "México": {
        "id": 262,
        "country": "México",
        "espn": "mex.1",
        "odds": "soccer_mexico_ligamx"
    },

    "Argentina": {
        "id": 128,
        "country": "Argentina",
        "espn": "arg.1",
        "odds": "soccer_argentina_primera_division"
    },

    "Colômbia": {
        "id": 239,
        "country": "Colômbia",
        "espn": "col.1",
        "odds": "soccer_colombia_primera_a"
    },

    "Chile": {
        "id": 265,
        "country": "Chile",
        "espn": "chi.1",
        "odds": "soccer_chile_primera_division"
    },

    "Uruguai": {
        "id": 268,
        "country": "Uruguai",
        "espn": "uru.1",
        "odds": "soccer_uruguay_primera_division"
    },

    "Japão": {
        "id": 98,
        "country": "Japão",
        "espn": "jpn.1",
        "odds": "soccer_japan_j_league"
    },

    "Coreia do Sul": {
        "id": 292,
        "country": "Coreia do Sul",
        "espn": "kor.1",
        "odds": "soccer_korea_kleague1"
    },

    "Arábia Saudita": {
        "id": 307,
        "country": "Arábia Saudita",
        "espn": None,
        "odds": "soccer_saudi_arabia_pro_league"
    },

    "Emirados Árabes": {
        "id": 301,
        "country": "Emirados Árabes",
        "espn": None,
        "odds": "soccer_uae_pro_league"
    },

    "África do Sul": {
        "id": 288,
        "country": "África do Sul",
        "espn": None,
        "odds": "soccer_south_africa_premiership"
    }
}


# ============================================================
# MERCADOS
# ============================================================

MARKETS = [
    "result",
    "double_chance",

    "over_0_5",
    "over_1_5",
    "over_2_5",
    "over_3_5",

    "under_2_5",

    "btts",

    "corners_over_6_5",
    "corners_over_7_5",
    "corners_over_8_5",
    "corners_over_9_5",

    "cards_over_2_5",
    "cards_over_3_5",
    "cards_over_4_5",

    "shots_on_target_over_3_5",
    "shots_on_target_over_5_5",

    "shots_over_18_5",
    "shots_over_21_5",

    "home_shots_on_target_over_2_5",
    "away_shots_on_target_over_2_5"
]


# ============================================================
# HTTP
# ============================================================

def get(url, headers=None, timeout=15):

    request_headers = headers or {
        "User-Agent": "Marques-Pro/1.0"
    }

    req = urllib.request.Request(
        url,
        headers=request_headers
    )

    try:

        with urllib.request.urlopen(
            req,
            timeout=timeout
        ) as response:

            raw = response.read()

            return json.loads(
                raw.decode("utf-8")
            )

    except urllib.error.HTTPError as error:

        try:
            body = error.read().decode(
                "utf-8",
                "ignore"
            )
        except Exception:
            body = ""

        print(
            f"[HTTP ERROR] "
            f"{error.code} "
            f"{url}"
        )

        if body:
            print(
                f"[HTTP BODY] "
                f"{body[:1000]}"
            )

        return None

    except urllib.error.URLError as error:

        print(
            f"[URL ERROR] "
            f"{url} -> {error}"
        )

        return None

    except Exception as error:

        print(
            f"[HTTP ERROR] "
            f"{url} -> {error}"
        )

        return None


def cached(
    key,
    fn,
    ttl=CACHE_TTL
):

    now = time.time()

    item = CACHE.get(key)

    if item:

        timestamp, value = item

        if now - timestamp < ttl:
            return value

    value = fn()

    if value is not None:

        CACHE[key] = (
            now,
            value
        )

    return value


# ============================================================
# API FOOTBALL
# ============================================================

def af(
    endpoint,
    params=None,
    ttl=CACHE_TTL
):

    if not AF_KEY:
        return None

    params = params or {}

    query = urllib.parse.urlencode(
        params
    )

    url = (
        "https://v3.football.api-sports.io/"
        + endpoint
    )

    if query:
        url += "?" + query

    key = "af:" + url

    return cached(
        key,
        lambda: get(
            url,
            {
                "x-apisports-key": AF_KEY,
                "User-Agent": "Marques-Pro/1.0"
            }
        ),
        ttl
    )


# ============================================================
# ODDS API
# ============================================================

def odds(sport):

    if not ODDS_KEY or not sport:
        return []

    params = urllib.parse.urlencode({
        "regions": "eu",
        "markets": "h2h,totals,spreads",
        "oddsFormat": "decimal",
        "apiKey": ODDS_KEY
    })

    url = (
        "https://api.the-odds-api.com/v4/sports/"
        + urllib.parse.quote(sport)
        + "/odds?"
        + params
    )

    data = cached(
        "odds:" + sport,
        lambda: get(url),
        300
    )

    return (
        data
        if isinstance(data, list)
        else []
    )


# ============================================================
# MATEMÁTICA
# ============================================================

def clamp(
    value,
    minimum,
    maximum
):

    return max(
        minimum,
        min(maximum, value)
    )


def poisson_pmf(
    k,
    lam
):

    lam = max(
        0.01,
        float(lam)
    )

    return (
        math.exp(-lam)
        * pow(lam, k)
        / math.factorial(k)
    )


def poisson_over(
    lam,
    line
):

    limit = int(
        math.floor(line)
    )

    return 1 - sum(
        poisson_pmf(
            k,
            lam
        )
        for k in range(
            limit + 1
        )
    )


def poisson_under(
    lam,
    line
):

    limit = int(
        math.floor(line)
    )

    return sum(
        poisson_pmf(
            k,
            lam
        )
        for k in range(
            limit + 1
        )
    )


def poisson_btts(
    home_lam,
    away_lam
):

    home_no = math.exp(
        -home_lam
    )

    away_no = math.exp(
        -away_lam
    )

    return (
        1
        - home_no
        - away_no
        + (
            home_no
            * away_no
        )
    )


def norm(value):

    return re.sub(
        r"[^a-z0-9 ]",
        "",
        str(
            value or ""
        ).lower()
    ).strip()


def parse_num(
    value,
    default=0
):

    try:

        if isinstance(
            value,
            (int, float)
        ):

            return float(
                value
            )

        text = str(
            value
        )

        match = re.search(
            r"-?\d+(?:\.\d+)?",
            text
        )

        if match:

            return float(
                match.group()
            )

    except Exception:
        pass

    return default


# ============================================================
# NORMALIZAÇÃO DE ESTATÍSTICAS
# ============================================================

def stat_key(value):

    text = str(
        value or ""
    )

    text = re.sub(
        r"([a-z])([A-Z])",
        r"\1 \2",
        text
    )

    compact = re.sub(
        r"[^a-z0-9]",
        "",
        text.lower()
    )

    aliases = {

        "totalshots": "shots",
        "shots": "shots",

        "shotsontarget": "sot",
        "shotsongoal": "sot",
        "shotsontargettotal": "sot",

        "cornerkicks": "corners",
        "corners": "corners",

        "yellowcards": "cards",
        "yellowcard": "cards",
        "yellow": "cards",

        "goals": "goals",
        "goalsfor": "gf",
        "goalsagainst": "ga"
    }

    return aliases.get(
        compact,
        compact
    )


# ============================================================
# ESPN
# ============================================================

def espn_scoreboard(
    league,
    date_value
):

    if not league:
        return None

    url = (
        "https://site.api.espn.com/apis/site/v2/"
        "sports/soccer/"
        + urllib.parse.quote(league)
        + "/scoreboard?dates="
        + urllib.parse.quote(date_value)
    )

    return get(url)


def espn_summary(
    league,
    event_id
):

    if not league or not event_id:
        return None

    url = (
        "https://site.api.espn.com/apis/site/v2/"
        "sports/soccer/"
        + urllib.parse.quote(league)
        + "/summary?event="
        + urllib.parse.quote(
            str(event_id)
        )
    )

    return get(url)


def iso_date(value):

    try:

        return datetime.fromisoformat(
            str(value).replace(
                "Z",
                "+00:00"
            )
        )

    except Exception:

        return None


def espn_fixture(
    event,
    league_name
):

    competitions = event.get(
        "competitions",
        []
    )

    if not competitions:
        return None

    competition = competitions[0]

    competitors = competition.get(
        "competitors",
        []
    )

    home = None
    away = None

    for team in competitors:

        if team.get(
            "homeAway"
        ) == "home":

            home = team

        elif team.get(
            "homeAway"
        ) == "away":

            away = team

    if not home or not away:
        return None

    status = (
        event
        .get("status", {})
        .get("type", {})
    )

    parsed_date = iso_date(
        event.get("date")
    )

    return {

        "fixture": {

            "id": event.get(
                "id"
            ),

            "date": event.get(
                "date"
            ),

            "timestamp": int(
                parsed_date.timestamp()
            )
            if parsed_date
            else None,

            "status": {

                "short": status.get(
                    "shortDetail"
                ),

                "long": status.get(
                    "description"
                )
            }
        },

        "league": {

            "name": league_name,

            "country": LEAGUES.get(
                league_name,
                {}
            ).get(
                "country"
            )
        },

        "teams": {

            "home": {

                "id": home.get(
                    "team",
                    {}
                ).get("id"),

                "name": home.get(
                    "team",
                    {}
                ).get(
                    "displayName"
                )
            },

            "away": {

                "id": away.get(
                    "team",
                    {}
                ).get("id"),

                "name": away.get(
                    "team",
                    {}
                ).get(
                    "displayName"
                )
            }
        },

        "goals": {

            "home": parse_num(
                home.get("score"),
                0
            ),

            "away": parse_num(
                away.get("score"),
                0
            )
        },

        "_source": "ESPN"
    }


# ============================================================
# SOFASCORE
# ============================================================

def sofascore_scheduled_events(
    date_value
):

    url = (
        "https://www.sofascore.com/api/v1/"
        "sport/football/scheduled-events/"
        + urllib.parse.quote(
            date_value
        )
    )

    data = cached(
        "sofascore:" + date_value,
        lambda: get(url),
        300
    )

    if not isinstance(
        data,
        dict
    ):

        return []

    events = data.get(
        "events",
        []
    )

    return (
        events
        if isinstance(
            events,
            list
        )
        else []
    )


def sofascore_fixture(
    event,
    league_name
):

    try:

        home_team = (
            event.get(
                "homeTeam"
            )
            or {}
        )

        away_team = (
            event.get(
                "awayTeam"
            )
            or {}
        )

        tournament = (
            event.get(
                "tournament"
            )
            or {}
        )

        home_name = (
            home_team.get("name")
            or home_team.get("shortName")
        )

        away_name = (
            away_team.get("name")
            or away_team.get("shortName")
        )

        if not home_name or not away_name:
            return None

        timestamp = event.get(
            "startTimestamp"
        )

        event_date = None

        if timestamp:

            try:

                event_date = datetime.fromtimestamp(
                    int(timestamp),
                    timezone.utc
                ).isoformat()

            except Exception:

                event_date = None

        status = (
            event.get(
                "status"
            )
            or {}
        )

        status_type = str(
            status.get(
                "type"
            )
            or ""
        )

        home_score = (
            event.get(
                "homeScore"
            )
            or {}
        )

        away_score = (
            event.get(
                "awayScore"
            )
            or {}
        )

        return {

            "fixture": {

                "id": (
                    "sofa_"
                    + str(
                        event.get("id")
                    )
                ),

                "provider_id": event.get(
                    "id"
                ),

                "date": event_date,

                "timestamp": timestamp,

                "status": {

                    "short": status_type,

                    "long": (
                        status.get(
                            "description"
                        )
                        or status.get(
                            "type"
                        )
                        or ""
                    )
                }
            },

            "league": {

                "name": league_name,

                "country": LEAGUES.get(
                    league_name,
                    {}
                ).get(
                    "country"
                ),

                "provider_name": (
                    tournament.get(
                        "name"
                    )
                    or league_name
                )
            },

            "teams": {

                "home": {

                    "id": home_team.get(
                        "id"
                    ),

                    "name": home_name
                },

                "away": {

                    "id": away_team.get(
                        "id"
                    ),

                    "name": away_name
                }
            },

            "goals": {

                "home": parse_num(
                    home_score.get(
                        "current"
                    ),
                    0
                ),

                "away": parse_num(
                    away_score.get(
                        "current"
                    ),
                    0
                )
            },

            "_source": "SofaScore"
        }

    except Exception as error:

        print(
            f"[SOFASCORE] "
            f"Erro normalizando jogo: "
            f"{error}"
        )

        return None


def sofascore_event_belongs_to_league(
    event,
    league_name
):

    tournament = (
        event.get(
            "tournament"
        )
        or {}
    )

    tournament_name = norm(
        tournament.get(
            "name"
        )
    )

    category = (
        tournament.get(
            "category"
        )
        or {}
    )

    category_name = norm(
        category.get(
            "name"
        )
    )

    aliases = {

        "Brasil": [
            "brasileirao serie a",
            "brasileirao",
            "serie a"
        ],

        "Brasil - Série B": [
            "brasileirao serie b",
            "serie b"
        ],

        "Inglaterra": [
            "premier league"
        ],

        "Inglaterra - Championship": [
            "championship"
        ],

        "Espanha": [
            "la liga",
            "laliga"
        ],

        "Espanha - Segunda": [
            "segunda division",
            "laliga hyermotion"
        ],

        "Itália": [
            "serie a"
        ],

        "Itália - Série B": [
            "serie b"
        ],

        "Alemanha": [
            "bundesliga"
        ],

        "Alemanha - 2. Bundesliga": [
            "2 bundesliga"
        ],

        "França": [
            "ligue 1"
        ],

        "França - Ligue 2": [
            "ligue 2"
        ],

        "Portugal": [
            "liga portugal",
            "primeira liga"
        ],

        "Holanda": [
            "eredivisie"
        ],

        "Bélgica": [
            "pro league"
        ],

        "Turquia": [
            "super lig"
        ],

        "Grécia": [
            "super league"
        ],

        "Áustria": [
            "bundesliga"
        ],

        "Suíça": [
            "super league"
        ],

        "Estados Unidos - MLS": [
            "mls"
        ],

        "México": [
            "liga mx"
        ],

        "Argentina": [
            "liga profesional",
            "primera division"
        ],

        "Colômbia": [
            "primera a"
        ],

        "Chile": [
            "primera division"
        ],

        "Uruguai": [
            "primera division"
        ],

        "Japão": [
            "j1 league",
            "j league"
        ],

        "Coreia do Sul": [
            "k league 1"
        ],

        "Arábia Saudita": [
            "saudi pro league",
            "saudi arabian league"
        ],

        "Emirados Árabes": [
            "uae pro league",
            "uae league"
        ],

        "África do Sul": [
            "premiership"
        ]
    }

    for alias in aliases.get(
        league_name,
        []
    ):

        if norm(alias) in tournament_name:

            # Alguns campeonatos compartilham nomes
            # como Serie A / Super League.
            # Quando houver país, usamos também a categoria.

            if (
                alias
                in [
                    "serie a",
                    "serie b",
                    "super league",
                    "bundesliga",
                    "primera division",
                    "premiership"
                ]
            ):

                if category_name:

                    expected_country = norm(
                        LEAGUES.get(
                            league_name,
                            {}
                        ).get(
                            "country"
                        )
                    )

                    if (
                        expected_country
                        and
                        expected_country
                        not in category_name
                    ):
                        continue

            return True

    return False


def sofascore_fixtures(
    league_name,
    days=7
):

    if league_name not in LEAGUES:

        return []

    search_days = int(
        clamp(
            parse_num(
                days,
                7
            ),
            3,
            7
        )
    )

    today = brazil_today()

    result = []

    print(
        f"[SOFASCORE] "
        f"{league_name} | "
        f"{search_days} dias"
    )

    for i in range(
        search_days + 1
    ):

        day = today + timedelta(
            days=i
        )

        date_string = day.strftime(
            "%Y-%m-%d"
        )

        events = sofascore_scheduled_events(
            date_string
        )

        print(
            f"[SOFASCORE] "
            f"{date_string}: "
            f"{len(events)} eventos"
        )

        for event in events:

            if not sofascore_event_belongs_to_league(
                event,
                league_name
            ):
                continue

            fixture = sofascore_fixture(
                event,
                league_name
            )

            if fixture:

                result.append(
                    fixture
                )

    result = deduplicate_fixtures(
        result
    )

    print(
        f"[SOFASCORE] "
        f"{league_name}: "
        f"{len(result)} jogos encontrados"
    )

    return result


# ============================================================
# API FOOTBALL - FIXTURES
# ============================================================

def api_football_fixtures(
    league_name,
    days=7
):

    league = LEAGUES.get(
        league_name
    )

    if not league:

        print(
            f"[FIXTURES] Liga não encontrada: "
            f"{league_name}"
        )

        return []

    if not AF_KEY:

        print(
            "[FIXTURES] API-Football "
            "sem chave"
        )

        return []

    league_id = league["id"]

    search_days = int(
        clamp(
            parse_num(
                days,
                7
            ),
            3,
            7
        )
    )

    today = brazil_today()

    end = today + timedelta(
        days=search_days
    )

    # ========================================================
    # TENTATIVA 1 — POR DATA
    # ========================================================

    params = {

        "league": league_id,

        "season": today.year,

        "from": today.isoformat(),

        "to": end.isoformat()
    }

    print(
        f"[API-FOOTBALL] "
        f"{league_name} | "
        f"league={league_id} | "
        f"season={today.year} | "
        f"{today} até {end}"
    )

    data = af(
        "fixtures",
        params,
        300
    )

    result = []

    if isinstance(
        data,
        dict
    ):

        errors = data.get(
            "errors"
        )

        if errors:

            print(
                f"[API-FOOTBALL] "
                f"ERROS: {errors}"
            )

        response = data.get(
            "response",
            []
        )

        print(
            f"[API-FOOTBALL] "
            f"Busca por período: "
            f"{len(response)} jogos"
        )

        for item in response:

            try:

                fixture = item.get(
                    "fixture",
                    {}
                )

                teams = item.get(
                    "teams",
                    {}
                )

                if not fixture or not teams:
                    continue

                result.append({

                    "fixture": fixture,

                    "league": item.get(
                        "league",
                        {
                            "name": league_name,
                            "country": league.get(
                                "country"
                            )
                        }
                    ),

                    "teams": teams,

                    "goals": item.get(
                        "goals",
                        {}
                    ),

                    "_source": "API-Football"
                })

            except Exception as error:

                print(
                    f"[API-FOOTBALL] "
                    f"Erro normalizando jogo: "
                    f"{error}"
                )

    # ========================================================
    # TENTATIVA 2 — NEXT 20
    #
    # Serve para contornar casos em que a API retorna
    # temporada antiga/consulta de período vazia.
    # ========================================================

    if not result:

        print(
            f"[API-FOOTBALL] "
            f"{league_name}: "
            f"tentando next=20"
        )

        params_next = {

            "league": league_id,

            "season": today.year,

            "next": 20
        }

        data_next = af(
            "fixtures",
            params_next,
            300
        )

        if isinstance(
            data_next,
            dict
        ):

            errors = data_next.get(
                "errors"
            )

            if errors:

                print(
                    f"[API-FOOTBALL] "
                    f"NEXT ERROS: {errors}"
                )

            response = data_next.get(
                "response",
                []
            )

            print(
                f"[API-FOOTBALL] "
                f"NEXT encontrou: "
                f"{len(response)} jogos"
            )

            for item in response:

                try:

                    fixture = item.get(
                        "fixture",
                        {}
                    )

                    teams = item.get(
                        "teams",
                        {}
                    )

                    if not fixture or not teams:
                        continue

                    date_value = fixture.get(
                        "date"
                    )

                    parsed = iso_date(
                        date_value
                    )

                    if not parsed:
                        continue

                    local_date = (
                        parsed.astimezone(
                            BRAZIL_TZ
                        ).date()
                    )

                    if (
                        today
                        <= local_date
                        <= end
                    ):

                        result.append({

                            "fixture": fixture,

                            "league": item.get(
                                "league",
                                {
                                    "name": league_name,
                                    "country": league.get(
                                        "country"
                                    )
                                }
                            ),

                            "teams": teams,

                            "goals": item.get(
                                "goals",
                                {}
                            ),

                            "_source": "API-Football"
                        })

                except Exception as error:

                    print(
                        f"[API-FOOTBALL] "
                        f"Erro NEXT: "
                        f"{error}"
                    )

    return deduplicate_fixtures(
        result
    )


# ============================================================
# ESPN
# ============================================================

def espn_fixtures(
    league_name,
    days=7
):

    league = LEAGUES.get(
        league_name,
        {}
    )

    espn_code = league.get(
        "espn"
    )

    if not espn_code:

        print(
            f"[ESPN] "
            f"{league_name} "
            f"não possui código ESPN"
        )

        return []

    search_days = int(
        clamp(
            parse_num(
                days,
                7
            ),
            3,
            7
        )
    )

    result = []

    today = brazil_today()

    print(
        f"[ESPN] "
        f"{league_name} | "
        f"{espn_code} | "
        f"{search_days} dias"
    )

    for i in range(
        search_days + 1
    ):

        day = today + timedelta(
            days=i
        )

        date_string = day.strftime(
            "%Y%m%d"
        )

        data = espn_scoreboard(
            espn_code,
            date_string
        )

        if not data:

            print(
                f"[ESPN] "
                f"{league_name} "
                f"{date_string}: "
                f"sem resposta"
            )

            continue

        events = data.get(
            "events",
            []
        )

        print(
            f"[ESPN] "
            f"{league_name} "
            f"{date_string}: "
            f"{len(events)} eventos"
        )

        for event in events:

            fixture = espn_fixture(
                event,
                league_name
            )

            if fixture:

                result.append(
                    fixture
                )

    return deduplicate_fixtures(
        result
    )


# ============================================================
# NORMALIZAÇÃO DE NOME DE EQUIPE
# ============================================================

def normalize_team_name(
    name
):

    text = norm(name)

    replacements = {

        "fc": "",

        "afc": "",

        "cf": "",

        "sc": ""
    }

    for old, new in replacements.items():

        text = text.replace(
            old,
            new
        )

    return re.sub(
        r"\s+",
        " ",
        text
    ).strip()


# ============================================================
# DEDUPLICAÇÃO
# ============================================================

def deduplicate_fixtures(
    fixtures
):

    result = []

    seen = set()

    for fixture in fixtures:

        fixture_data = fixture.get(
            "fixture",
            {}
        )

        teams = fixture.get(
            "teams",
            {}
        )

        home = normalize_team_name(
            teams.get(
                "home",
                {}
            ).get(
                "name"
            )
        )

        away = normalize_team_name(
            teams.get(
                "away",
                {}
            ).get(
                "name"
            )
        )

        date_value = fixture_data.get(
            "date"
        )

        # ----------------------------------------------------
        # Normalizar data para agrupar jogos iguais
        # ----------------------------------------------------

        parsed = iso_date(
            date_value
        )

        date_key = ""

        if parsed:

            date_key = parsed.astimezone(
                BRAZIL_TZ
            ).strftime(
                "%Y-%m-%d-%H-%M"
            )

        # ----------------------------------------------------
        # Não usar ID entre provedores como chave principal,
        # pois ESPN/SofaScore/API-Football usam IDs diferentes.
        # ----------------------------------------------------

        key = (
            home,
            away,
            date_key
        )

        if (
            not home
            or not away
        ):

            fixture_id = fixture_data.get(
                "id"
            )

            key = (
                "id",
                str(fixture_id)
            )

        if key in seen:
            continue

        seen.add(
            key
        )

        result.append(
            fixture
        )

    result.sort(
        key=lambda x: (
            x.get(
                "fixture",
                {}
            ).get(
                "date"
            )
            or ""
        )
    )

    return result


# ============================================================
# BUSCA PRINCIPAL MULTIFONTE
# ============================================================

def get_fixtures(
    league_name="Brasil",
    days=7
):

    if league_name not in LEAGUES:

        print(
            f"[FIXTURES] "
            f"Liga inválida: "
            f"{league_name}"
        )

        return []

    search_days = int(
        clamp(
            parse_num(
                days,
                7
            ),
            3,
            7
        )
    )

    print(
        "================================================"
    )

    print(
        "[FIXTURES] BUSCA MULTIFONTE"
    )

    print(
        f"[FIXTURES] Liga: "
        f"{league_name}"
    )

    print(
        f"[FIXTURES] Janela: "
        f"{search_days} dias"
    )

    print(
        f"[FIXTURES] Hoje Brasil: "
        f"{brazil_today()}"
    )

    all_fixtures = []

    # ========================================================
    # 1 — ESPN
    # ========================================================

    try:

        espn_data = espn_fixtures(
            league_name,
            search_days
        )

        print(
            f"[FIXTURES] ESPN: "
            f"{len(espn_data)} jogos"
        )

        all_fixtures.extend(
            espn_data
        )

    except Exception as error:

        print(
            f"[FIXTURES] ESPN falhou: "
            f"{error}"
        )

    # ========================================================
    # 2 — SOFASCORE
    # ========================================================

    try:

        sofa_data = sofascore_fixtures(
            league_name,
            search_days
        )

        print(
            f"[FIXTURES] SofaScore: "
            f"{len(sofa_data)} jogos"
        )

        all_fixtures.extend(
            sofa_data
        )

    except Exception as error:

        print(
            f"[FIXTURES] SofaScore falhou: "
            f"{error}"
        )

    # ========================================================
    # 3 — API-FOOTBALL
    # ========================================================

    try:

        api_data = api_football_fixtures(
            league_name,
            search_days
        )

        print(
            f"[FIXTURES] API-Football: "
            f"{len(api_data)} jogos"
        )

        all_fixtures.extend(
            api_data
        )

    except Exception as error:

        print(
            f"[FIXTURES] API-Football falhou: "
            f"{error}"
        )

    # ========================================================
    # DEDUPLICAR
    # ========================================================

    all_fixtures = deduplicate_fixtures(
        all_fixtures
    )

    # ========================================================
    # FILTRAR JANELA
    # ========================================================

    today = brazil_today()

    end = today + timedelta(
        days=search_days
    )

    filtered = []

    for fixture in all_fixtures:

        date_value = (
            fixture
            .get("fixture", {})
            .get("date")
        )

        if not date_value:
            continue

        parsed = iso_date(
            date_value
        )

        if not parsed:
            continue

        local_date = (
            parsed.astimezone(
                BRAZIL_TZ
            ).date()
        )

        if (
            today
            <= local_date
            <= end
        ):

            filtered.append(
                fixture
            )

    # ========================================================
    # ORDENAR
    # ========================================================

    filtered.sort(
        key=lambda x: (
            x.get(
                "fixture",
                {}
            ).get(
                "date"
            )
            or ""
        )
    )

    # ========================================================
    # FONTES
    # ========================================================

    sources = {}

    for fixture in filtered:

        source = fixture.get(
            "_source",
            "unknown"
        )

        sources[source] = (
            sources.get(
                source,
                0
            )
            + 1
        )

    print(
        "------------------------------------------------"
    )

    print(
        f"[FIXTURES] TOTAL FINAL: "
        f"{len(filtered)} jogos"
    )

    print(
        f"[FIXTURES] Fontes: "
        f"{sources}"
    )

    print(
        "================================================"
    )

    return filtered


# ============================================================
# DEBUG DE FIXTURES
# ============================================================

def debug_fixtures(
    league_name,
    days=7
):

    league = LEAGUES.get(
        league_name
    )

    if not league:

        return {

            "ok": False,

            "error": "Liga não encontrada",

            "league": league_name
        }

    search_days = int(
        clamp(
            parse_num(
                days,
                7
            ),
            3,
            7
        )
    )

    today = brazil_today()

    end = today + timedelta(
        days=search_days
    )

    result = {

        "ok": True,

        "version": VERSION,

        "league": league_name,

        "league_id": league.get(
            "id"
        ),

        "country": league.get(
            "country"
        ),

        "today_brazil": today.isoformat(),

        "from": today.isoformat(),

        "to": end.isoformat(),

        "days": search_days,

        "api_football_key": bool(
            AF_KEY
        ),

        "odds_key": bool(
            ODDS_KEY
        ),

        "sources": {

            "api_football": {
                "attempted": False,
                "count": 0,
                "errors": None
            },

            "espn": {
                "attempted": False,
                "count": 0,
                "code": league.get(
                    "espn"
                )
            },

            "sofascore": {
                "attempted": False,
                "count": 0
            }
        }
    }

    # ========================================================
    # API FOOTBALL
    # ========================================================

    if AF_KEY:

        result[
            "sources"
        ][
            "api_football"
        ][
            "attempted"
        ] = True

        params = {

            "league": league["id"],

            "season": today.year,

            "from": today.isoformat(),

            "to": end.isoformat()
        }

        data = af(
            "fixtures",
            params,
            60
        )

        if isinstance(
            data,
            dict
        ):

            response = data.get(
                "response",
                []
            )

            result[
                "sources"
            ][
                "api_football"
            ][
                "count"
            ] = len(
                response
            )

            result[
                "sources"
            ][
                "api_football"
            ][
                "errors"
            ] = data.get(
                "errors"
            )

    # ========================================================
    # ESPN
    # ========================================================

    espn_code = league.get(
        "espn"
    )

    if espn_code:

        result[
            "sources"
        ][
            "espn"
        ][
            "attempted"
        ] = True

        total = 0

        for i in range(
            search_days + 1
        ):

            day = today + timedelta(
                days=i
            )

            data = espn_scoreboard(
                espn_code,
                day.strftime(
                    "%Y%m%d"
                )
            )

            if data:

                total += len(
                    data.get(
                        "events",
                        []
                    )
                )

        result[
            "sources"
        ][
            "espn"
        ][
            "count"
        ] = total

    # ========================================================
    # SOFASCORE
    # ========================================================

    result[
        "sources"
    ][
        "sofascore"
    ][
        "attempted"
    ] = True

    try:

        sofa_data = sofascore_fixtures(
            league_name,
            search_days
        )

        result[
            "sources"
        ][
            "sofascore"
        ][
            "count"
        ] = len(
            sofa_data
        )

    except Exception as error:

        result[
            "sources"
        ][
            "sofascore"
        ][
            "error"
        ] = str(
            error
        )

    # ========================================================
    # BUSCA FINAL
    # ========================================================

    try:

        fixtures = get_fixtures(
            league_name,
            search_days
        )

        result[
            "final"
        ] = {

            "count": len(
                fixtures
            ),

            "sources": {}
        }

        for fixture in fixtures:

            source = fixture.get(
                "_source",
                "unknown"
            )

            result[
                "final"
            ][
                "sources"
            ][source] = (
                result[
                    "final"
                ][
                    "sources"
                ].get(
                    source,
                    0
                )
                + 1
            )

    except Exception as error:

        result[
            "final_error"
        ] = str(
            error
        )

    return result


# ============================================================
# ÚLTIMOS JOGOS
# ============================================================

def team_recent_events(
    team_id,
    league_name,
    limit=10
):

    league = LEAGUES.get(
        league_name,
        {}
    )

    espn_code = league.get(
        "espn"
    )

    if not espn_code or not team_id:
        return []

    today = brazil_today()

    start = today - timedelta(
        days=150
    )

    events = []

    current = start

    while current <= today:

        data = espn_scoreboard(
            espn_code,
            current.strftime(
                "%Y%m%d"
            )
        )

        if data:

            for event in data.get(
                "events",
                []
            ):

                fixture = espn_fixture(
                    event,
                    league_name
                )

                if not fixture:
                    continue

                home_id = str(
                    fixture[
                        "teams"
                    ][
                        "home"
                    ].get(
                        "id"
                    )
                )

                away_id = str(
                    fixture[
                        "teams"
                    ][
                        "away"
                    ].get(
                        "id"
                    )
                )

                if str(team_id) not in (
                    home_id,
                    away_id
                ):
                    continue

                status = (
                    fixture
                    .get(
                        "fixture",
                        {}
                    )
                    .get(
                        "status",
                        {}
                    )
                    .get(
                        "long",
                        ""
                    )
                )

                status_text = str(
                    status
                ).lower()

                if (
                    "final" not in
                    status_text
                    and
                    "ended" not in
                    status_text
                ):
                    continue

                events.append(
                    fixture
                )

        current += timedelta(
            days=1
        )

    events.sort(
        key=lambda x: x[
            "fixture"
        ].get(
            "date",
            ""
        ),
        reverse=True
    )

    return events[:limit]


# ============================================================
# ESTATÍSTICAS DO JOGO
# ============================================================

def summary_team_stats(
    league_name,
    event_id,
    team_id
):

    league = LEAGUES.get(
        league_name,
        {}
    )

    espn_code = league.get(
        "espn"
    )

    if not espn_code:
        return {}

    data = espn_summary(
        espn_code,
        event_id
    )

    if not data:
        return {}

    result = {}

    for team_block in data.get(
        "boxscore",
        {}
    ).get(
        "teams",
        []
    ):

        team = team_block.get(
            "team",
            {}
        )

        if str(
            team.get("id")
        ) != str(team_id):

            continue

        for stat in team_block.get(
            "statistics",
            []
        ):

            key = stat_key(
                stat.get("name")
            )

            value = stat.get(
                "displayValue"
            )

            result[key] = parse_num(
                value,
                0
            )

    return result


# ============================================================
# PERFIL RECENTE
# ============================================================

def recent_profile(
    team_id,
    league_name
):

    default = {

        "games": 0,

        "gf": 1.35,

        "ga": 1.25,

        "shots": 12.0,

        "sot": 4.2,

        "corners": 5.0,

        "cards": 2.2
    }

    events = team_recent_events(
        team_id,
        league_name,
        8
    )

    if not events:
        return default

    gf = 0
    ga = 0

    shots = []
    sot = []
    corners = []
    cards = []

    valid = 0

    for event in events:

        teams = event.get(
            "teams",
            {}
        )

        home = teams.get(
            "home",
            {}
        )

        away = teams.get(
            "away",
            {}
        )

        home_id = str(
            home.get("id")
        )

        is_home = (
            home_id
            ==
            str(team_id)
        )

        goals = event.get(
            "goals",
            {}
        )

        home_goals = parse_num(
            goals.get("home"),
            0
        )

        away_goals = parse_num(
            goals.get("away"),
            0
        )

        if is_home:

            gf += home_goals
            ga += away_goals

        else:

            gf += away_goals
            ga += home_goals

        event_id = (
            event
            .get("fixture", {})
            .get("id")
        )

        stats = summary_team_stats(
            league_name,
            event_id,
            team_id
        )

        if "shots" in stats:

            shots.append(
                stats["shots"]
            )

        if "sot" in stats:

            sot.append(
                stats["sot"]
            )

        if "corners" in stats:

            corners.append(
                stats["corners"]
            )

        if "cards" in stats:

            cards.append(
                stats["cards"]
            )

        valid += 1

    if valid == 0:
        return default

    return {

        "games": valid,

        "gf": round(
            gf / valid,
            2
        ),

        "ga": round(
            ga / valid,
            2
        ),

        "shots": round(
            sum(shots) / len(shots),
            2
        )
        if shots
        else default["shots"],

        "sot": round(
            sum(sot) / len(sot),
            2
        )
        if sot
        else default["sot"],

        "corners": round(
            sum(corners) / len(corners),
            2
        )
        if corners
        else default["corners"],

        "cards": round(
            sum(cards) / len(cards),
            2
        )
        if cards
        else default["cards"]
    }


# ============================================================
# DESFALQUES
# ============================================================

def get_injuries(
    fixture_id
):

    if not AF_KEY or not fixture_id:
        return []

    # IDs SofaScore não podem ser enviados como IDs
    # da API-Football.

    if str(
        fixture_id
    ).startswith("sofa_"):

        return []

    data = af(
        "injuries",
        {
            "fixture": fixture_id
        },
        300
    )

    if not data:
        return []

    return data.get(
        "response",
        []
    )


# ============================================================
# ESCALAÇÕES
# ============================================================

def get_lineups(
    fixture_id
):

    if not AF_KEY or not fixture_id:
        return []

    if str(
        fixture_id
    ).startswith("sofa_"):

        return []

    data = af(
        "fixtures/lineups",
        {
            "fixture": fixture_id
        },
        300
    )

    if not data:
        return []

    return data.get(
        "response",
        []
    )


# ============================================================
# CONTEXTO DO ELENCO
# ============================================================

def squad_context(
    fixture
):

    fixture_id = (
        fixture
        .get("fixture", {})
        .get("id")
    )

    context = {

        "available": bool(
            AF_KEY
            and fixture_id
            and not str(
                fixture_id
            ).startswith("sofa_")
        ),

        "lineups_available": False,

        "injuries_available": False,

        "teams": {},

        "injuries": [],

        "summary": []
    }

    if not fixture_id:
        return context

    lineups = get_lineups(
        fixture_id
    )

    injuries = get_injuries(
        fixture_id
    )

    if lineups:

        context[
            "lineups_available"
        ] = True

    if injuries:

        context[
            "injuries_available"
        ] = True

    for lineup in lineups:

        team = lineup.get(
            "team",
            {}
        )

        team_id = str(
            team.get("id")
        )

        team_name = team.get(
            "name"
        )

        players = []

        for item in lineup.get(
            "startXI",
            []
        ):

            player = item.get(
                "player",
                {}
            )

            players.append({

                "id": player.get(
                    "id"
                ),

                "name": player.get(
                    "name"
                ),

                "number": player.get(
                    "number"
                ),

                "position": player.get(
                    "pos"
                ),

                "grid": player.get(
                    "grid"
                ),

                "starter": True
            })

        substitutes = []

        for item in lineup.get(
            "substitutes",
            []
        ):

            player = item.get(
                "player",
                {}
            )

            substitutes.append({

                "id": player.get(
                    "id"
                ),

                "name": player.get(
                    "name"
                ),

                "number": player.get(
                    "number"
                ),

                "position": player.get(
                    "pos"
                ),

                "starter": False
            })

        context[
            "teams"
        ][team_id] = {

            "id": team_id,

            "name": team_name,

            "formation": lineup.get(
                "formation"
            ),

            "starting_xi": players,

            "substitutes": substitutes
        }

    for item in injuries:

        player = item.get(
            "player",
            {}
        )

        team = item.get(
            "team",
            {}
        )

        team_id = str(
            team.get("id")
        )

        injury = {

            "player": player.get(
                "name"
            ),

            "player_id": player.get(
                "id"
            ),

            "team": team.get(
                "name"
            ),

            "team_id": team_id,

            "type": player.get(
                "type"
            ),

            "reason": player.get(
                "reason"
            )
        }

        context[
            "injuries"
        ].append(
            injury
        )

    # ========================================================
    # IMPACTO
    # ========================================================

    for team_id, team in context[
        "teams"
    ].items():

        team[
            "injury_count"
        ] = 0

        team[
            "suspension_count"
        ] = 0

        team[
            "impact_score"
        ] = 0

    for injury in context.get(
        "injuries",
        []
    ):

        team_id = str(
            injury.get(
                "team_id"
            )
        )

        if team_id not in context[
            "teams"
        ]:

            context[
                "teams"
            ][team_id] = {

                "id": team_id,

                "name": injury.get(
                    "team"
                ),

                "formation": None,

                "starting_xi": [],

                "substitutes": [],

                "injury_count": 0,

                "suspension_count": 0,

                "impact_score": 0
            }

        team = context[
            "teams"
        ][team_id]

        team[
            "injury_count"
        ] += 1

        reason = str(
            injury.get(
                "reason"
            )
            or ""
        ).lower()

        player_type = str(
            injury.get(
                "type"
            )
            or ""
        ).lower()

        if (
            "susp" in reason
            or
            "susp" in player_type
        ):

            team[
                "suspension_count"
            ] += 1

            team[
                "impact_score"
            ] += 1.5

        else:

            team[
                "impact_score"
            ] += 1.0

    for team in context[
        "teams"
    ].values():

        score = team.get(
            "impact_score",
            0
        )

        if score >= 4:

            level = "alto"

        elif score >= 2:

            level = "moderado"

        elif score > 0:

            level = "baixo"

        else:

            level = "nenhum"

        team[
            "impact_level"
        ] = level

    return context


# ============================================================
# PLACARES EXATOS
# ============================================================

def exact_score_predictions(
    home_lam,
    away_lam,
    max_goals=7,
    top_n=6
):

    scores = []

    for home_goals in range(
        max_goals + 1
    ):

        for away_goals in range(
            max_goals + 1
        ):

            probability = (

                poisson_pmf(
                    home_goals,
                    home_lam
                )

                *

                poisson_pmf(
                    away_goals,
                    away_lam
                )
            )

            scores.append({

                "home_goals": home_goals,

                "away_goals": away_goals,

                "score": (
                    f"{home_goals}x"
                    f"{away_goals}"
                ),

                "probability": round(
                    probability * 100,
                    2
                )
            })

    scores.sort(
        key=lambda x: x[
            "probability"
        ],
        reverse=True
    )

    return scores[:top_n]


# ============================================================
# MODELO
# ============================================================

def build_model(
    fixture,
    home_context=None,
    away_context=None
):

    teams = fixture.get(
        "teams",
        {}
    )

    home = teams.get(
        "home",
        {}
    )

    away = teams.get(
        "away",
        {}
    )

    home_id = home.get(
        "id"
    )

    away_id = away.get(
        "id"
    )

    league_name = (
        fixture
        .get("league", {})
        .get("name")
        or "Brasil"
    )

    home_profile = recent_profile(
        home_id,
        league_name
    )

    away_profile = recent_profile(
        away_id,
        league_name
    )

    home_xg = clamp(

        (
            home_profile["gf"]
            * 0.55
            +
            away_profile["ga"]
            * 0.45
            +
            0.18
        ),

        0.35,
        3.20
    )

    away_xg = clamp(

        (
            away_profile["gf"]
            * 0.55
            +
            home_profile["ga"]
            * 0.45
        ),

        0.25,
        2.80
    )

    # ========================================================
    # DESFALQUES
    # ========================================================

    home_impact = 0
    away_impact = 0

    if home_context:

        for team in home_context.get(
            "teams",
            {}
        ).values():

            if str(
                team.get("id")
            ) == str(home_id):

                home_impact = team.get(
                    "impact_score",
                    0
                )

    if away_context:

        for team in away_context.get(
            "teams",
            {}
        ).values():

            if str(
                team.get("id")
            ) == str(away_id):

                away_impact = team.get(
                    "impact_score",
                    0
                )

    home_adjustment = clamp(
        1 - home_impact * 0.025,
        0.85,
        1
    )

    away_adjustment = clamp(
        1 - away_impact * 0.025,
        0.85,
        1
    )

    home_xg *= home_adjustment

    away_xg *= away_adjustment

    total_xg = (
        home_xg
        +
        away_xg
    )

    # ========================================================
    # RESULTADO
    # ========================================================

    home_win = 0
    draw = 0
    away_win = 0

    for h in range(8):

        for a in range(8):

            p = (

                poisson_pmf(
                    h,
                    home_xg
                )

                *

                poisson_pmf(
                    a,
                    away_xg
                )
            )

            if h > a:

                home_win += p

            elif h == a:

                draw += p

            else:

                away_win += p

    # ========================================================
    # ESTATÍSTICAS
    # ========================================================

    expected_corners = clamp(

        (
            home_profile["corners"]
            +
            away_profile["corners"]
        ),

        4,
        15
    )

    expected_cards = clamp(

        (
            home_profile["cards"]
            +
            away_profile["cards"]
        ),

        1,
        10
    )

    expected_shots = clamp(

        (
            home_profile["shots"]
            +
            away_profile["shots"]
        ),

        10,
        40
    )

    expected_sot = clamp(

        (
            home_profile["sot"]
            +
            away_profile["sot"]
        ),

        2,
        18
    )

    btts = poisson_btts(
        home_xg,
        away_xg
    )

    markets = []

    def add_market(
        key,
        label,
        probability
    ):

        probability = clamp(
            probability,
            0.01,
            0.99
        )

        fair_odds = (
            1
            /
            probability
        )

        markets.append({

            "key": key,

            "label": label,

            "probability": round(
                probability * 100,
                2
            ),

            "fair_odds": round(
                fair_odds,
                2
            )
        })

    add_market(
        "home_win",
        f"{home.get('name')} vencer",
        home_win
    )

    add_market(
        "draw",
        "Empate",
        draw
    )

    add_market(
        "away_win",
        f"{away.get('name')} vencer",
        away_win
    )

    add_market(
        "double_chance_1x",
        "Casa ou empate",
        home_win + draw
    )

    add_market(
        "double_chance_x2",
        "Empate ou visitante",
        draw + away_win
    )

    add_market(
        "over_0_5",
        "Mais de 0.5 gols",
        poisson_over(
            total_xg,
            0.5
        )
    )

    add_market(
        "over_1_5",
        "Mais de 1.5 gols",
        poisson_over(
            total_xg,
            1.5
        )
    )

    add_market(
        "over_2_5",
        "Mais de 2.5 gols",
        poisson_over(
            total_xg,
            2.5
        )
    )

    add_market(
        "over_3_5",
        "Mais de 3.5 gols",
        poisson_over(
            total_xg,
            3.5
        )
    )

    add_market(
        "under_2_5",
        "Menos de 2.5 gols",
        poisson_under(
            total_xg,
            2.5
        )
    )

    add_market(
        "btts",
        "Ambas marcam",
        btts
    )

    add_market(
        "corners_over_6_5",
        "Mais de 6.5 escanteios",
        poisson_over(
            expected_corners,
            6.5
        )
    )

    add_market(
        "corners_over_7_5",
        "Mais de 7.5 escanteios",
        poisson_over(
            expected_corners,
            7.5
        )
    )

    add_market(
        "corners_over_8_5",
        "Mais de 8.5 escanteios",
        poisson_over(
            expected_corners,
            8.5
        )
    )

    add_market(
        "corners_over_9_5",
        "Mais de 9.5 escanteios",
        poisson_over(
            expected_corners,
            9.5
        )
    )

    add_market(
        "cards_over_2_5",
        "Mais de 2.5 cartões",
        poisson_over(
            expected_cards,
            2.5
        )
    )

    add_market(
        "cards_over_3_5",
        "Mais de 3.5 cartões",
        poisson_over(
            expected_cards,
            3.5
        )
    )

    add_market(
        "cards_over_4_5",
        "Mais de 4.5 cartões",
        poisson_over(
            expected_cards,
            4.5
        )
    )

    add_market(
        "shots_over_18_5",
        "Mais de 18.5 chutes",
        poisson_over(
            expected_shots,
            18.5
        )
    )

    add_market(
        "shots_over_21_5",
        "Mais de 21.5 chutes",
        poisson_over(
            expected_shots,
            21.5
        )
    )

    add_market(
        "shots_on_target_over_3_5",
        "Mais de 3.5 chutes no gol",
        poisson_over(
            expected_sot,
            3.5
        )
    )

    add_market(
        "shots_on_target_over_5_5",
        "Mais de 5.5 chutes no gol",
        poisson_over(
            expected_sot,
            5.5
        )
    )

    add_market(
        "home_shots_on_target_over_2_5",
        (
            f"{home.get('name')} "
            f"+2.5 chutes no gol"
        ),
        poisson_over(
            home_profile["sot"],
            2.5
        )
    )

    add_market(
        "away_shots_on_target_over_2_5",
        (
            f"{away.get('name')} "
            f"+2.5 chutes no gol"
        ),
        poisson_over(
            away_profile["sot"],
            2.5
        )
    )

    markets.sort(
        key=lambda x: x[
            "probability"
        ],
        reverse=True
    )

    exact_scores = (
        exact_score_predictions(
            home_xg,
            away_xg
        )
    )

    games_used = min(
        home_profile["games"],
        away_profile["games"]
    )

    confidence = clamp(
        55 + games_used * 4,
        55,
        90
    )

    return {

        "home_xg": round(
            home_xg,
            2
        ),

        "away_xg": round(
            away_xg,
            2
        ),

        "expected_goals": round(
            total_xg,
            2
        ),

        "expected_corners": round(
            expected_corners,
            2
        ),

        "expected_cards": round(
            expected_cards,
            2
        ),

        "expected_shots": round(
            expected_shots,
            2
        ),

        "expected_shots_on_target": round(
            expected_sot,
            2
        ),

        "result_probability": {

            "home": round(
                home_win * 100,
                2
            ),

            "draw": round(
                draw * 100,
                2
            ),

            "away": round(
                away_win * 100,
                2
            )
        },

        "profiles": {

            "home": home_profile,

            "away": away_profile
        },

        "desfalques_impact": {

            "home": round(
                home_impact,
                2
            ),

            "away": round(
                away_impact,
                2
            )
        },

        "exact_scores": exact_scores,

        "most_likely_score": (
            exact_scores[0]
            if exact_scores
            else None
        ),

        "markets": markets,

        "top_markets": markets[:10],

        "confidence": confidence,

        "model": VERSION
    }


# ============================================================
# ODDS REAIS
# ============================================================

def event_matches(
    fixture,
    event
):

    teams = fixture.get(
        "teams",
        {}
    )

    home = normalize_team_name(
        teams.get(
            "home",
            {}
        ).get(
            "name"
        )
    )

    away = normalize_team_name(
        teams.get(
            "away",
            {}
        ).get(
            "name"
        )
    )

    event_home = normalize_team_name(
        event.get(
            "home_team"
        )
    )

    event_away = normalize_team_name(
        event.get(
            "away_team"
        )
    )

    if not home or not away:
        return False

    if (
        home == event_home
        and
        away == event_away
    ):

        return True

    if (
        (
            home in event_home
            or
            event_home in home
        )
        and
        (
            away in event_away
            or
            event_away in away
        )
    ):

        return True

    return False


def external_odds(
    fixture
):

    league_name = (
        fixture
        .get("league", {})
        .get("name")
    )

    league = LEAGUES.get(
        league_name,
        {}
    )

    sport = league.get(
        "odds"
    )

    if not ODDS_KEY or not sport:
        return []

    events = odds(
        sport
    )

    result = []

    for event in events:

        if not event_matches(
            fixture,
            event
        ):
            continue

        for bookmaker in event.get(
            "bookmakers",
            []
        ):

            for market in bookmaker.get(
                "markets",
                []
            ):

                market_key = market.get(
                    "key"
                )

                for outcome in market.get(
                    "outcomes",
                    []
                ):

                    price = parse_num(
                        outcome.get(
                            "price"
                        ),
                        0
                    )

                    if price <= 1:
                        continue

                    probability = (
                        1 / price
                    ) * 100

                    result.append({

                        "source": "The Odds API",

                        "bookmaker": bookmaker.get(
                            "title"
                        ),

                        "market": market_key,

                        "name": outcome.get(
                            "name"
                        ),

                        "point": outcome.get(
                            "point"
                        ),

                        "price": round(
                            price,
                            2
                        ),

                        "implied_probability": round(
                            probability,
                            2
                        )
                    })

        break

    return result


# ============================================================
# VALUE
# ============================================================

def enrich_value(
    model_markets,
    real_odds
):

    result = []

    model_map = {}

    for market in model_markets:

        model_map[
            market["key"]
        ] = market

    for odd in real_odds:

        price = odd.get(
            "price"
        )

        if not price:
            continue

        implied = (
            1 / price
        ) * 100

        label = str(
            odd.get("name")
            or ""
        ).lower()

        model_probability = None

        if odd.get(
            "market"
        ) == "h2h":

            for model in model_map.values():

                if (
                    model[
                        "label"
                    ].lower()
                    ==
                    label
                ):

                    model_probability = (
                        model[
                            "probability"
                        ]
                    )

                    break

        if model_probability is not None:

            odd[
                "model_probability"
            ] = round(
                model_probability,
                2
            )

            odd[
                "edge"
            ] = round(
                model_probability
                -
                implied,
                2
            )

        result.append(
            odd
        )

    result.sort(
        key=lambda x: x.get(
            "edge",
            -999
        ),
        reverse=True
    )

    return result


# ============================================================
# ANÁLISE COMPLETA
# ============================================================

def analyze_fixture(
    fixture
):

    league_name = (
        fixture
        .get("league", {})
        .get("name")
        or "Brasil"
    )

    teams = fixture.get(
        "teams",
        {}
    )

    home = teams.get(
        "home",
        {}
    )

    away = teams.get(
        "away",
        {}
    )

    context = squad_context(
        fixture
    )

    model = build_model(
        fixture,
        context,
        context
    )

    real_odds = external_odds(
        fixture
    )

    real_odds = enrich_value(
        model.get(
            "markets",
            []
        ),
        real_odds
    )

    prediction = None

    fixture_id = (
        fixture
        .get("fixture", {})
        .get("id")
    )

    # SofaScore IDs não servem para API-Football
    if (
        AF_KEY
        and fixture_id
        and not str(
            fixture_id
        ).startswith("sofa_")
    ):

        data = af(
            "predictions",
            {
                "fixture": fixture_id
            },
            300
        )

        if data:

            response = data.get(
                "response",
                []
            )

            if response:

                prediction = response[0]

    return {

        "fixture": fixture,

        "prediction": prediction,

        "model": model,

        "markets": model.get(
            "markets",
            []
        ),

        "real_odds": real_odds,

        "external_markets": real_odds,

        "squad": context,

        "lineups": context.get(
            "teams",
            {}
        ),

        "injuries": context.get(
            "injuries",
            []
        ),

        "source": fixture.get(
            "_source"
        ),

        "home_team": home.get(
            "name"
        ),

        "away_team": away.get(
            "name"
        ),

        "generated_at": brazil_now().isoformat()
    }


# ============================================================
# HISTÓRICO
# ============================================================

def read_history():

    try:

        if not Path(
            DATA_FILE
        ).exists():

            return []

        with open(
            DATA_FILE,
            "r",
            encoding="utf-8"
        ) as file:

            data = json.load(
                file
            )

            return (
                data
                if isinstance(
                    data,
                    list
                )
                else []
            )

    except Exception:

        return []


def write_history(
    data
):

    try:

        with open(
            DATA_FILE,
            "w",
            encoding="utf-8"
        ) as file:

            json.dump(
                data,
                file,
                ensure_ascii=False,
                indent=2
            )

    except Exception as error:

        print(
            f"[HISTORY] "
            f"Erro salvando histórico: "
            f"{error}"
        )


# ============================================================
# CUPOM
# ============================================================

def build_coupon(
    items
):

    selections = []

    combined = 1.0

    for item in items:

        price = parse_num(
            item.get(
                "price"
            ),
            0
        )

        if price <= 1:

            fair = parse_num(
                item.get(
                    "fair_odds"
                ),
                0
            )

            price = fair

        if price <= 1:
            continue

        combined *= price

        selections.append({

            "fixture": item.get(
                "fixture"
            ),

            "market": item.get(
                "market"
            ),

            "label": item.get(
                "label"
            ),

            "price": round(
                price,
                2
            )
        })

    return {

        "selections": selections,

        "combined_odds": round(
            combined,
            2
        ),

        "count": len(
            selections
        )
    }


# ============================================================
# HTTP HANDLER
# ============================================================

class Handler(
    SimpleHTTPRequestHandler
):

    def send_json(
        self,
        data,
        status=200
    ):

        payload = json.dumps(
            data,
            ensure_ascii=False
        ).encode(
            "utf-8"
        )

        self.send_response(
            status
        )

        self.send_header(
            "Content-Type",
            "application/json; charset=utf-8"
        )

        self.send_header(
            "Content-Length",
            str(len(payload))
        )

        self.send_header(
            "Access-Control-Allow-Origin",
            "*"
        )

        self.send_header(
            "Cache-Control",
            "no-store"
        )

        self.end_headers()

        self.wfile.write(
            payload
        )

    def read_body(
        self
    ):

        try:

            length = int(
                self.headers.get(
                    "Content-Length",
                    0
                )
            )

            if length <= 0:
                return {}

            body = self.rfile.read(
                length
            )

            return json.loads(
                body.decode(
                    "utf-8"
                )
            )

        except Exception:

            return {}

    def do_OPTIONS(
        self
    ):

        self.send_response(
            204
        )

        self.send_header(
            "Access-Control-Allow-Origin",
            "*"
        )

        self.send_header(
            "Access-Control-Allow-Methods",
            "GET, POST, OPTIONS"
        )

        self.send_header(
            "Access-Control-Allow-Headers",
            "Content-Type"
        )

        self.end_headers()

    def do_GET(
        self
    ):

        parsed = urllib.parse.urlparse(
            self.path
        )

        path = parsed.path

        params = urllib.parse.parse_qs(
            parsed.query
        )

        # ====================================================
        # HEALTH
        # ====================================================

        if path == "/api/health":

            self.send_json({

                "ok": True,

                "api_football": bool(
                    AF_KEY
                ),

                "odds_api": bool(
                    ODDS_KEY
                ),

                "leagues": len(
                    LEAGUES
                ),

                "cache_ttl": CACHE_TTL,

                "version": VERSION,

                "fixtures_sources": [
                    "ESPN",
                    "SofaScore",
                    "API-Football"
                ],

                "today_brazil": brazil_today().isoformat(),

                "server_time": brazil_now().isoformat()
            })

            return

        # ====================================================
        # LEAGUES
        # ====================================================

        if path == "/api/leagues":

            result = []

            for name, item in LEAGUES.items():

                result.append({

                    "name": name,

                    "country": item.get(
                        "country"
                    ),

                    "id": item.get(
                        "id"
                    ),

                    "odds": bool(
                        item.get(
                            "odds"
                        )
                    )
                })

            self.send_json(
                result
            )

            return

        # ====================================================
        # DEBUG FIXTURES
        # ====================================================

        if path == "/api/debug/fixtures":

            league = (
                params
                .get(
                    "league",
                    ["Brasil"]
                )[0]
            )

            days = parse_num(
                params.get(
                    "days",
                    ["7"]
                )[0],
                7
            )

            result = debug_fixtures(
                league,
                days
            )

            self.send_json(
                result
            )

            return

        # ====================================================
        # FIXTURES
        # ====================================================

        if path == "/api/fixtures":

            league = (
                params
                .get(
                    "league",
                    ["Brasil"]
                )[0]
            )

            days = parse_num(
                params.get(
                    "days",
                    ["7"]
                )[0],
                7
            )

            days = int(
                clamp(
                    days,
                    3,
                    7
                )
            )

            fixtures = get_fixtures(
                league,
                days
            )

            source_counts = {}

            for fixture in fixtures:

                source = fixture.get(
                    "_source",
                    "unknown"
                )

                source_counts[source] = (
                    source_counts.get(
                        source,
                        0
                    )
                    + 1
                )

            self.send_json({

                "ok": True,

                "league": league,

                "days": days,

                "fixtures": fixtures,

                "count": len(
                    fixtures
                ),

                "source": (
                    fixtures[0].get(
                        "_source"
                    )
                    if fixtures
                    else None
                ),

                "sources": source_counts,

                "today_brazil": brazil_today().isoformat()
            })

            return

        # ====================================================
        # ANALYZE
        # ====================================================

        if path == "/api/analyze":

            league = (
                params
                .get(
                    "league",
                    ["Brasil"]
                )[0]
            )

            days = parse_num(
                params.get(
                    "days",
                    ["7"]
                )[0],
                7
            )

            days = int(
                clamp(
                    days,
                    3,
                    7
                )
            )

            fixtures = get_fixtures(
                league,
                days
            )

            games = []

            for fixture in fixtures:

                try:

                    games.append(
                        analyze_fixture(
                            fixture
                        )
                    )

                except Exception as error:

                    print(
                        f"[ANALYZE] "
                        f"Erro no jogo: "
                        f"{error}"
                    )

                    games.append({

                        "fixture": fixture,

                        "error": str(
                            error
                        )
                    })

            self.send_json({

                "ok": True,

                "league": league,

                "days": days,

                "games": games,

                "count": len(
                    games
                ),

                "today_brazil": brazil_today().isoformat()
            })

            return

        # ====================================================
        # PREDICTION
        # ====================================================

        if path == "/api/prediction":

            fixture_id = (
                params
                .get(
                    "fixture",
                    [None]
                )[0]
            )

            if not fixture_id:

                self.send_json({

                    "ok": False,

                    "error": (
                        "fixture obrigatório"
                    )

                }, 400)

                return

            if str(
                fixture_id
            ).startswith("sofa_"):

                self.send_json({

                    "ok": False,

                    "response": [],

                    "error": (
                        "Este jogo foi encontrado "
                        "pelo SofaScore e não possui "
                        "ID da API-Football."
                    )
                })

                return

            data = af(
                "predictions",
                {
                    "fixture": fixture_id
                },
                300
            )

            self.send_json(
                data or {
                    "response": []
                }
            )

            return

        # ====================================================
        # ODDS
        # ====================================================

        if path == "/api/odds":

            sport = (
                params
                .get(
                    "sport",
                    ["soccer_epl"]
                )[0]
            )

            self.send_json(
                odds(sport)
            )

            return

        # ====================================================
        # HISTORY
        # ====================================================

        if path == "/api/history":

            self.send_json(
                read_history()
            )

            return

        # ====================================================
        # FRONTEND
        # ====================================================

        return super().do_GET()

    def do_POST(
        self
    ):

        parsed = urllib.parse.urlparse(
            self.path
        )

        path = parsed.path

        body = self.read_body()

        # ====================================================
        # COUPON BUILD
        # ====================================================

        if path == "/api/coupon/build":

            items = body.get(
                "items",
                []
            )

            result = build_coupon(
                items
            )

            self.send_json(
                result
            )

            return

        # ====================================================
        # COUPON SAVE
        # ====================================================

        if path == "/api/coupon/save":

            history = read_history()

            record = {

                "type": "coupon",

                "created_at": brazil_now().isoformat(),

                "data": body
            }

            history.append(
                record
            )

            history = history[
                -500:
            ]

            write_history(
                history
            )

            self.send_json({

                "ok": True,

                "saved": record
            })

            return

        # ====================================================
        # RESULT
        # ====================================================

        if path == "/api/result":

            history = read_history()

            record = {

                "type": "result",

                "created_at": brazil_now().isoformat(),

                "data": body
            }

            history.append(
                record
            )

            history = history[
                -500:
            ]

            write_history(
                history
            )

            self.send_json({

                "ok": True
            })

            return

        self.send_json({

            "ok": False,

            "error": "rota não encontrada"
        }, 404)


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    server = ThreadingHTTPServer(
        (
            "0.0.0.0",
            PORT
        ),
        Handler
    )

    print(
        "================================================"
    )

    print(
        f"{VERSION} iniciado"
    )

    print(
        f"Porta: {PORT}"
    )

    print(
        "================================================"
    )

    print(
        "API-Football: "
        +
        (
            "ATIVA"
            if AF_KEY
            else "INATIVA"
        )
    )

    print(
        "Odds API: "
        +
        (
            "ATIVA"
            if ODDS_KEY
            else "INATIVA"
        )
    )

    print(
        "Fontes de fixtures: ESPN + SofaScore + API-Football"
    )

    print(
        f"Ligas disponíveis: "
        f"{len(LEAGUES)}"
    )

    print(
        f"Data Brasil: "
        f"{brazil_today()}"
    )

    print(
        "================================================"
    )

    server.serve_forever()
