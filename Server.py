import os
import json
import urllib.request
import urllib.parse
import urllib.error
import datetime
import time
import re
import math
from pathlib import Path
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler


# ============================================================
# MARQUES PRO V15
# Football Intelligence & Betting Analysis
# ============================================================

PORT = int(os.getenv("PORT", "8787"))

AF_KEY = os.getenv("API_FOOTBALL_KEY", "").strip()
ODDS_KEY = os.getenv("ODDS_API_KEY", "").strip()

CACHE_TTL = int(os.getenv("CACHE_TTL", "900"))

CACHE = {}

DATA_FILE = "marques_pro_history.json"


# ============================================================
# LIGAS
# ============================================================

LEAGUES = {

    # BRASIL
    "Brasil": 71,
    "Brasil Série B": 72,
    "Brasil Série C": 75,
    "Brasil Série D": 76,
    "Copa do Brasil": 73,

    # EUROPA
    "Inglaterra": 39,
    "Inglaterra Championship": 40,

    "Espanha": 140,
    "Espanha Segunda": 141,

    "Itália": 135,
    "Itália Serie B": 136,

    "Alemanha": 78,
    "Alemanha 2": 79,

    "França": 61,
    "França Ligue 2": 62,

    "Portugal": 94,
    "Holanda": 88,
    "Bélgica": 144,
    "Turquia": 203,
    "Grécia": 197,
    "Escócia": 179,
    "Áustria": 218,
    "Suíça": 207,
    "Dinamarca": 119,
    "Suécia": 113,
    "Noruega": 103,

    # AMÉRICAS
    "Argentina": 128,
    "Colômbia": 239,
    "Chile": 265,
    "Uruguai": 268,
    "Equador": 242,
    "México": 262,
    "MLS": 253,

    # ÁSIA
    "Arábia Saudita": 307,
    "Japão": 98,
    "Coreia do Sul": 292,

    # CONTINENTAIS
    "Libertadores": 13,
    "Sul-Americana": 11,
    "Champions League": 2,
    "Europa League": 3,
    "Conference League": 848
}


# ============================================================
# ESPN
# ============================================================

ESPN_LEAGUES = {

    "Brasil": "bra.1",
    "Brasil Série B": "bra.2",
    "Brasil Série C": "bra.3",
    "Copa do Brasil": "bra.copa_do_brasil",

    "Inglaterra": "eng.1",
    "Inglaterra Championship": "eng.2",

    "Espanha": "esp.1",
    "Espanha Segunda": "esp.2",

    "Itália": "ita.1",
    "Itália Serie B": "ita.2",

    "Alemanha": "ger.1",
    "Alemanha 2": "ger.2",

    "França": "fra.1",
    "França Ligue 2": "fra.2",

    "Portugal": "por.1",
    "Holanda": "ned.1",
    "Bélgica": "bel.1",
    "Turquia": "tur.1",
    "Escócia": "sco.1",
    "Áustria": "aut.1",
    "Suíça": "sui.1",
    "Dinamarca": "den.1",
    "Suécia": "swe.1",
    "Noruega": "nor.1",

    "Argentina": "arg.1",
    "Colômbia": "col.1",
    "Chile": "chi.1",
    "Uruguai": "uru.1",
    "Equador": "ecu.1",
    "México": "mex.1",
    "MLS": "usa.1",

    "Arábia Saudita": "ksa.1",
    "Japão": "jpn.1",
    "Coreia do Sul": "kor.1"
}


# ============================================================
# ODDS API
# ============================================================

SPORT_KEYS = {

    "Brasil": "soccer_brazil_campeonato",
    "Inglaterra": "soccer_epl",
    "Espanha": "soccer_spain_la_liga",
    "Itália": "soccer_italy_serie_a",
    "Alemanha": "soccer_germany_bundesliga",
    "França": "soccer_france_ligue_one",
    "Portugal": "soccer_portugal_primeira_liga",
    "Holanda": "soccer_netherlands_eredivisie",
    "Bélgica": "soccer_belgium_first_div",
    "Turquia": "soccer_turkey_super_league",
    "Escócia": "soccer_spl",
    "Argentina": "soccer_argentina_primera_division",
    "Colômbia": "soccer_colombia_primera_a",
    "Chile": "soccer_chile_primera_division",
    "MLS": "soccer_usa_mls",
    "Japão": "soccer_japan_j_league",
    "Coreia do Sul": "soccer_south_korea_k_league_1",
    "Arábia Saudita": "soccer_saudi_arabia_pro_league",
    "Champions League": "soccer_uefa_champs_league",
    "Europa League": "soccer_uefa_europa_league"
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
    "under_3_5",

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

    "shots_over_15_5",
    "shots_over_18_5",
    "shots_over_21_5",

    "home_shots_on_target_over_2_5",
    "away_shots_on_target_over_2_5"
]


# ============================================================
# BANCO
# ============================================================

def load_data():

    try:

        return json.loads(
            Path(DATA_FILE).read_text(
                encoding="utf-8"
            )
        )

    except Exception:

        return {
            "predictions": [],
            "coupons": [],
            "next_prediction_id": 1,
            "next_coupon_id": 1
        }


def save_data(data):

    Path(DATA_FILE).write_text(
        json.dumps(
            data,
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )


# ============================================================
# HTTP
# ============================================================

def get(url, key=None, headers=None):

    h = {
        "User-Agent": "Marques-Pro/15.0",
        "Accept": "application/json"
    }

    if headers:
        h.update(headers)

    if key:
        h["x-apisports-key"] = key

    req = urllib.request.Request(
        url,
        headers=h
    )

    try:

        with urllib.request.urlopen(
            req,
            timeout=20
        ) as response:

            raw = response.read().decode(
                "utf-8"
            )

            return json.loads(raw)

    except urllib.error.HTTPError as e:

        try:

            body = e.read().decode(
                "utf-8"
            )

            data = json.loads(body)

        except Exception:

            data = {}

        return {
            "error": f"HTTP {e.code}",
            "http_status": e.code,
            "details": data
        }

    except Exception as e:

        return {
            "error": str(e)
        }


def cached(
    url,
    key=None,
    headers=None,
    ttl=None
):

    now = time.time()

    lifetime = (
        CACHE_TTL
        if ttl is None
        else ttl
    )

    hit = CACHE.get(url)

    if hit and now - hit[0] < lifetime:

        return hit[1]

    data = get(
        url,
        key,
        headers
    )

    CACHE[url] = (
        now,
        data
    )

    return data


# ============================================================
# API FOOTBALL
# ============================================================

def af(path, params):

    if not AF_KEY:

        return {
            "error": "API_FOOTBALL_KEY não configurada",
            "response": []
        }

    query = urllib.parse.urlencode(
        params
    )

    url = (
        "https://v3.football.api-sports.io/"
        + path
        + "?"
        + query
    )

    return cached(
        url,
        AF_KEY
    )


def api_football_has_data(data):

    return (
        isinstance(data, dict)
        and not data.get("error")
        and not data.get("errors")
        and bool(data.get("response"))
    )


# ============================================================
# ODDS API
# ============================================================

def odds(sport):

    if not ODDS_KEY or not sport:

        return {
            "error": "ODDS_API_KEY não configurada",
            "matches": []
        }

    query = urllib.parse.urlencode({

        "regions": "eu",

        "markets": "h2h,totals,spreads",

        "oddsFormat": "decimal",

        "apiKey": ODDS_KEY

    })

    url = (
        "https://api.the-odds-api.com/v4/sports/"
        + sport
        + "/odds?"
        + query
    )

    return cached(
        url,
        ttl=300
    )


# ============================================================
# NORMALIZAÇÃO
# ============================================================

def norm(s):

    s = str(
        s or ""
    )

    # camelCase -> palavras
    s = re.sub(
        r"([a-z])([A-Z])",
        r"\1 \2",
        s
    )

    s = s.lower()

    s = re.sub(
        r"[^a-z0-9áàâãéêíóôõúüç ]",
        " ",
        s
    )

    return re.sub(
        r"\s+",
        " ",
        s
    ).strip()


def stat_key(value):

    value = norm(value)

    compact = re.sub(
        r"[^a-z0-9]",
        "",
        value
    )

    aliases = {

        "totalshots":
        "total shots",

        "shots":
        "total shots",

        "shotsontarget":
        "shots on target",

        "shotsongoal":
        "shots on target",

        "cornerkicks":
        "corner kicks",

        "corners":
        "corner kicks",

        "yellowcards":
        "yellow cards",

        "yellow":
        "yellow cards"

    }

    return aliases.get(
        compact,
        value
    )


def clamp(
    value,
    minimum=0.01,
    maximum=0.99
):

    try:

        value = float(value)

    except Exception:

        value = minimum

    return max(
        minimum,
        min(
            maximum,
            value
        )
    )


def parse_num(value):

    try:

        return float(
            str(value)
            .replace(",", ".")
            .replace("%", "")
            .strip()
        )

    except Exception:

        return None


# ============================================================
# POISSON
# ============================================================

def poisson_pmf(
    k,
    lam
):

    try:

        return (
            math.exp(-lam)
            * (lam ** k)
            / math.factorial(k)
        )

    except Exception:

        return 0.0


def poisson_over(
    lam,
    line
):

    threshold = int(
        math.floor(line)
    )

    return 1 - sum(
        poisson_pmf(
            k,
            lam
        )
        for k in range(
            threshold + 1
        )
    )


def poisson_under(
    lam,
    line
):

    threshold = int(
        math.floor(line)
    )

    return sum(
        poisson_pmf(
            k,
            lam
        )
        for k in range(
            threshold + 1
        )
    )


def poisson_btts(
    home_lam,
    away_lam
):

    return (
        1 - math.exp(
            -home_lam
        )
    ) * (
        1 - math.exp(
            -away_lam
        )
    )


# ============================================================
# PLACARES EXATOS
# ============================================================

def exact_score_predictions(
    home_xg,
    away_xg,
    max_goals=7
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
                    home_xg
                )
                *
                poisson_pmf(
                    away_goals,
                    away_xg
                )
            )

            scores.append({

                "home_goals":
                home_goals,

                "away_goals":
                away_goals,

                "score":
                f"{home_goals} x {away_goals}",

                "probability":
                round(
                    probability * 100,
                    2
                )

            })

    scores.sort(
        key=lambda item:
        item["probability"],
        reverse=True
    )

    return scores[:5]


# ============================================================
# ID
# ============================================================

def event_id_unique(
    event_id,
    home,
    away,
    date
):

    raw = (
        f"{event_id}|"
        f"{home}|"
        f"{away}|"
        f"{date}"
    )

    value = 0

    for char in raw:

        value = (
            value * 131
            + ord(char)
        ) % 800000000

    return 100000000 + value


# ============================================================
# ESPN
# ============================================================

def espn_scoreboard(
    league,
    date
):

    slug = ESPN_LEAGUES.get(
        league
    )

    if not slug:

        return []

    date_str = date.strftime(
        "%Y%m%d"
    )

    url = (
        "https://site.api.espn.com/apis/site/v2/"
        "sports/soccer/"
        f"{slug}/scoreboard?dates={date_str}"
    )

    data = cached(url)

    if not isinstance(
        data,
        dict
    ):

        return []

    return data.get(
        "events",
        []
    )


def espn_summary(
    league,
    event_id
):

    slug = ESPN_LEAGUES.get(
        league
    )

    if not slug:

        return {}

    url = (
        "https://site.api.espn.com/apis/site/v2/"
        "sports/soccer/"
        f"{slug}/summary?"
        f"event={urllib.parse.quote(str(event_id))}"
    )

    data = cached(
        url,
        ttl=1800
    )

    if isinstance(
        data,
        dict
    ):

        return data

    return {}


# ============================================================
# ESPN -> FIXTURE
# ============================================================

def espn_to_fixture(
    event,
    league
):

    try:

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

        home = next(
            (
                c
                for c in competitors
                if c.get("homeAway") == "home"
            ),
            None
        )

        away = next(
            (
                c
                for c in competitors
                if c.get("homeAway") == "away"
            ),
            None
        )

        if not home or not away:

            return None

        home_team = home.get(
            "team",
            {}
        )

        away_team = away.get(
            "team",
            {}
        )

        home_name = (
            home_team.get("displayName")
            or home_team.get("name")
            or ""
        )

        away_name = (
            away_team.get("displayName")
            or away_team.get("name")
            or ""
        )

        if not home_name or not away_name:

            return None

        event_id = str(
            event.get(
                "id",
                ""
            )
        )

        date = event.get(
            "date"
        )

        fixture_id = event_id_unique(
            event_id,
            home_name,
            away_name,
            date
        )

        return {

            "fixture": {

                "id":
                fixture_id,

                "external_id":
                event_id,

                "date":
                date,

                "status": {

                    "short":
                    event.get(
                        "status",
                        {}
                    ).get(
                        "type",
                        {}
                    ).get(
                        "name",
                        "STATUS_SCHEDULED"
                    )

                }

            },

            "teams": {

                "home": {

                    "id":
                    home_team.get("id"),

                    "name":
                    home_name,

                    "logo":
                    home_team.get("logo")

                },

                "away": {

                    "id":
                    away_team.get("id"),

                    "name":
                    away_name,

                    "logo":
                    away_team.get("logo")

                }

            },

            "league": {

                "name":
                league,

                "id":
                LEAGUES.get(league)

            },

            "_source":
            "ESPN"

        }

    except Exception:

        return None


# ============================================================
# JOGOS ATUAIS
# ============================================================

def get_current_fixtures(
    league,
    days=1
):

    today = datetime.date.today()

    league_id = LEAGUES.get(
        league
    )

    # --------------------------------------------------------
    # API FOOTBALL
    # --------------------------------------------------------

    if AF_KEY and league_id:

        result = af(
            "fixtures",
            {

                "league":
                league_id,

                "season":
                today.year,

                "from":
                str(today),

                "to":
                str(
                    today
                    + datetime.timedelta(
                        days=days
                    )
                )

            }
        )

        if api_football_has_data(
            result
        ):

            fixtures = result.get(
                "response",
                []
            )

            for fixture in fixtures:

                fixture[
                    "_source"
                ] = "API-Football"

            return (
                fixtures,
                "API-Football"
            )

    # --------------------------------------------------------
    # ESPN
    # --------------------------------------------------------

    fixtures = []

    for offset in range(
        days + 1
    ):

        day = (
            today
            + datetime.timedelta(
                days=offset
            )
        )

        events = espn_scoreboard(
            league,
            day
        )

        for event in events:

            fixture = espn_to_fixture(
                event,
                league
            )

            if fixture:

                fixtures.append(
                    fixture
                )

    unique = {}

    for fixture in fixtures:

        unique[
            str(
                fixture[
                    "fixture"
                ][
                    "external_id"
                ]
            )
        ] = fixture

    return (
        list(
            unique.values()
        ),
        "ESPN"
    )


# ============================================================
# EVENTO FINALIZADO
# ============================================================

def completed_event(
    event
):

    try:

        return bool(
            event.get(
                "status",
                {}
            ).get(
                "type",
                {}
            ).get(
                "completed"
            )
        )

    except Exception:

        return False


# ============================================================
# JOGOS RECENTES
# ============================================================

def team_recent_events(
    league,
    team_id,
    days_back=120,
    max_events=8
):

    slug = ESPN_LEAGUES.get(
        league
    )

    if not slug or not team_id:

        return []

    end = datetime.date.today()

    start = (
        end
        - datetime.timedelta(
            days=days_back
        )
    )

    url = (
        "https://site.api.espn.com/apis/site/v2/"
        "sports/soccer/"
        f"{slug}/scoreboard?"
        f"dates={start.strftime('%Y%m%d')}-"
        f"{end.strftime('%Y%m%d')}"
    )

    data = cached(
        url,
        ttl=1800
    )

    events = (
        data.get(
            "events",
            []
        )
        if isinstance(
            data,
            dict
        )
        else []
    )

    found = []

    for event in events:

        competitions = event.get(
            "competitions",
            []
        )

        if not competitions:

            continue

        competitors = competitions[0].get(
            "competitors",
            []
        )

        for competitor in competitors:

            competitor_team = competitor.get(
                "team",
                {}
            )

            if str(
                competitor_team.get("id")
            ) == str(team_id):

                if completed_event(
                    event
                ):

                    found.append(
                        event
                    )

                break

    found.sort(
        key=lambda item:
        item.get(
            "date",
            ""
        ),
        reverse=True
    )

    return found[:max_events]


# ============================================================
# ESTATÍSTICAS
# ============================================================

def summary_team_stats(
    league,
    event_id,
    team_id
):

    data = espn_summary(
        league,
        event_id
    )

    if not isinstance(
        data,
        dict
    ):

        return {}

    boxscore = data.get(
        "boxscore",
        {}
    )

    teams = boxscore.get(
        "teams",
        []
    )

    for item in teams:

        team = item.get(
            "team",
            {}
        )

        if str(
            team.get("id")
        ) != str(team_id):

            continue

        result = {}

        for stat in item.get(
            "statistics",
            []
        ):

            name = stat_key(
                stat.get("name")
            )

            value = parse_num(
                stat.get(
                    "displayValue",
                    stat.get("value")
                )
            )

            if value is not None:

                result[name] = value

        return result

    return {}


# ============================================================
# PERFIL RECENTE
# ============================================================

def recent_profile(
    league,
    team_id
):

    events = team_recent_events(
        league,
        team_id
    )

    if not events:

        return {

            "games": 0,

            "gf": 1.35,
            "ga": 1.25,

            "shots": 12.0,
            "sot": 4.2,

            "corners": 5.0,
            "cards": 2.2

        }

    gf = 0.0
    ga = 0.0

    shots = 0.0
    sot = 0.0
    corners = 0.0
    cards = 0.0

    stat_games = 0

    for event in events:

        competitions = event.get(
            "competitions",
            []
        )

        if not competitions:

            continue

        competitors = competitions[0].get(
            "competitors",
            []
        )

        me = next(
            (
                c
                for c in competitors
                if str(
                    c.get(
                        "team",
                        {}
                    ).get("id")
                ) == str(team_id)
            ),
            None
        )

        if not me:

            continue

        opponent = next(
            (
                c
                for c in competitors
                if c is not me
            ),
            None
        )

        try:

            gf += float(
                me.get(
                    "score",
                    0
                ) or 0
            )

            if opponent:

                ga += float(
                    opponent.get(
                        "score",
                        0
                    ) or 0
                )

        except Exception:

            pass

        stats = summary_team_stats(
            league,
            event.get("id"),
            team_id
        )

        current_shots = stats.get(
            "total shots",
            0
        )

        current_sot = stats.get(
            "shots on target",
            0
        )

        current_corners = stats.get(
            "corner kicks",
            0
        )

        current_cards = stats.get(
            "yellow cards",
            0
        )

        if stats:

            shots += current_shots
            sot += current_sot
            corners += current_corners
            cards += current_cards

            stat_games += 1

    games = len(events)

    return {

        "games":
        games,

        "gf":
        round(
            gf / games
            if games
            else 1.35,
            2
        ),

        "ga":
        round(
            ga / games
            if games
            else 1.25,
            2
        ),

        "shots":
        round(
            shots / stat_games
            if stat_games
            else 12.0,
            2
        ),

        "sot":
        round(
            sot / stat_games
            if stat_games
            else 4.2,
            2
        ),

        "corners":
        round(
            corners / stat_games
            if stat_games
            else 5.0,
            2
        ),

        "cards":
        round(
            cards / stat_games
            if stat_games
            else 2.2,
            2
        )

    }


# ============================================================
# MODELO
# ============================================================

def build_model(
    fixture,
    league
):

    home = fixture["teams"]["home"]
    away = fixture["teams"]["away"]

    home_profile = recent_profile(
        league,
        home.get("id")
    )

    away_profile = recent_profile(
        league,
        away.get("id")
    )

    # --------------------------------------------------------
    # XG
    # --------------------------------------------------------

    home_xg = clamp(
        (
            home_profile["gf"] * 0.55
            +
            away_profile["ga"] * 0.45
        )
        + 0.18,
        0.35,
        3.20
    )

    away_xg = clamp(
        (
            away_profile["gf"] * 0.55
            +
            home_profile["ga"] * 0.45
        ),
        0.25,
        2.80
    )

    total_xg = (
        home_xg
        + away_xg
    )

    # --------------------------------------------------------
    # RESULTADOS
    # --------------------------------------------------------

    home_win = 0.0
    draw = 0.0
    away_win = 0.0

    for h in range(10):

        for a in range(10):

            probability = (
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

                home_win += probability

            elif h == a:

                draw += probability

            else:

                away_win += probability

    # --------------------------------------------------------
    # MÉDIAS
    # --------------------------------------------------------

    corners_mean = clamp(
        (
            home_profile["corners"]
            +
            away_profile["corners"]
        ) * 0.96,
        4.5,
        16.0
    )

    cards_mean = clamp(
        (
            home_profile["cards"]
            +
            away_profile["cards"]
        ) * 0.98,
        1.5,
        8.5
    )

    sot_mean = clamp(
        (
            home_profile["sot"]
            +
            away_profile["sot"]
        ) * 0.98,
        2.5,
        14.0
    )

    shots_mean = clamp(
        (
            home_profile["shots"]
            +
            away_profile["shots"]
        ) * 0.98,
        10.0,
        35.0
    )

    btts = poisson_btts(
        home_xg,
        away_xg
    )

    # --------------------------------------------------------
    # PLACARES
    # --------------------------------------------------------

    exact_scores = exact_score_predictions(
        home_xg,
        away_xg,
        7
    )

    # --------------------------------------------------------
    # MERCADOS
    # --------------------------------------------------------

    markets = [

        (
            "Casa vence",
            "result",
            home_win
        ),

        (
            "Empate",
            "result",
            draw
        ),

        (
            "Fora vence",
            "result",
            away_win
        ),

        (
            "Casa ou empate (1X)",
            "double_chance",
            home_win + draw
        ),

        (
            "Empate ou fora (X2)",
            "double_chance",
            draw + away_win
        ),

        (
            "Mais de 0.5 gols",
            "goals",
            poisson_over(
                total_xg,
                0.5
            )
        ),

        (
            "Mais de 1.5 gols",
            "goals",
            poisson_over(
                total_xg,
                1.5
            )
        ),

        (
            "Mais de 2.5 gols",
            "goals",
            poisson_over(
                total_xg,
                2.5
            )
        ),

        (
            "Mais de 3.5 gols",
            "goals",
            poisson_over(
                total_xg,
                3.5
            )
        ),

        (
            "Menos de 2.5 gols",
            "goals",
            poisson_under(
                total_xg,
                2.5
            )
        ),

        (
            "Menos de 3.5 gols",
            "goals",
            poisson_under(
                total_xg,
                3.5
            )
        ),

        (
            "Ambas marcam",
            "btts",
            btts
        ),

        (
            "Mais de 6.5 escanteios",
            "corners",
            poisson_over(
                corners_mean,
                6.5
            )
        ),

        (
            "Mais de 7.5 escanteios",
            "corners",
            poisson_over(
                corners_mean,
                7.5
            )
        ),

        (
            "Mais de 8.5 escanteios",
            "corners",
            poisson_over(
                corners_mean,
                8.5
            )
        ),

        (
            "Mais de 9.5 escanteios",
            "corners",
            poisson_over(
                corners_mean,
                9.5
            )
        ),

        (
            "Mais de 2.5 cartões",
            "cards",
            poisson_over(
                cards_mean,
                2.5
            )
        ),

        (
            "Mais de 3.5 cartões",
            "cards",
            poisson_over(
                cards_mean,
                3.5
            )
        ),

        (
            "Mais de 4.5 cartões",
            "cards",
            poisson_over(
                cards_mean,
                4.5
            )
        ),

        (
            "Mais de 3.5 chutes no gol",
            "shots_on_target",
            poisson_over(
                sot_mean,
                3.5
            )
        ),

        (
            "Mais de 5.5 chutes no gol",
            "shots_on_target",
            poisson_over(
                sot_mean,
                5.5
            )
        ),

        (
            "Mais de 15.5 finalizações",
            "shots",
            poisson_over(
                shots_mean,
                15.5
            )
        ),

        (
            "Mais de 18.5 finalizações",
            "shots",
            poisson_over(
                shots_mean,
                18.5
            )
        ),

        (
            "Mais de 21.5 finalizações",
            "shots",
            poisson_over(
                shots_mean,
                21.5
            )
        ),

        (
            "Casa: mais de 2.5 chutes no gol",
            "shots_on_target",
            poisson_over(
                home_profile["sot"],
                2.5
            )
        ),

        (
            "Fora: mais de 2.5 chutes no gol",
            "shots_on_target",
            poisson_over(
                away_profile["sot"],
                2.5
            )
        )

    ]

    # --------------------------------------------------------
    # CONFIANÇA
    # --------------------------------------------------------

    games_home = home_profile["games"]
    games_away = away_profile["games"]

    confidence = int(
        round(
            min(
                94,
                max(
                    52,
                    50
                    +
                    min(
                        12,
                        games_home * 1.2
                    )
                    +
                    min(
                        12,
                        games_away * 1.2
                    )
                )
            )
        )
    )

    # --------------------------------------------------------
    # RESULTADOS
    # --------------------------------------------------------

    result_markets = []

    for name, category, probability in markets:

        probability = clamp(
            probability
        )

        fair_odd = round(
            1 / probability,
            2
        )

        if probability >= 0.72:

            risk = "baixo"

        elif probability >= 0.58:

            risk = "médio"

        elif probability >= 0.45:

            risk = "alto"

        else:

            risk = "muito alto"

        score = int(
            round(
                probability * 75
                +
                confidence * 0.25
            )
        )

        result_markets.append({

            "market":
            name,

            "category":
            category,

            "probability":
            round(
                probability * 100,
                1
            ),

            "fair_odd":
            fair_odd,

            "risk":
            risk,

            "score":
            score

        })

    result_markets.sort(
        key=lambda item:
        item["score"],
        reverse=True
    )

    # --------------------------------------------------------
    # RETORNO
    # --------------------------------------------------------

    return {

        "expected_goals":
        round(
            total_xg,
            2
        ),

        "home_xg":
        round(
            home_xg,
            2
        ),

        "away_xg":
        round(
            away_xg,
            2
        ),

        "expected_corners":
        round(
            corners_mean,
            1
        ),

        "expected_cards":
        round(
            cards_mean,
            1
        ),

        "expected_shots":
        round(
            shots_mean,
            1
        ),

        "expected_shots_on_target":
        round(
            sot_mean,
            1
        ),

        "confidence":
        confidence,

        "exact_scores":
        exact_scores,

        "most_likely_score":
        exact_scores[0]
        if exact_scores
        else None,

        "home_profile":
        home_profile,

        "away_profile":
        away_profile,

        "markets":
        result_markets,

        "top_markets":
        result_markets[:8],

        "model":
        "Marques Pro V15"

    }


# ============================================================
# MATCH ODDS
# ============================================================

def match_external(
    fixture,
    events
):

    home_name = norm(
        fixture[
            "teams"
        ][
            "home"
        ][
            "name"
        ]
    )

    away_name = norm(
        fixture[
            "teams"
        ][
            "away"
        ][
            "name"
        ]
    )

    try:

        fixture_time = (
            datetime.datetime
            .fromisoformat(
                fixture[
                    "fixture"
                ][
                    "date"
                ].replace(
                    "Z",
                    "+00:00"
                )
            )
            .timestamp()
        )

    except Exception:

        fixture_time = time.time()

    best = None
    best_score = 999999999

    for event in events:

        event_home = norm(
            event.get(
                "home_team",
                ""
            )
        )

        event_away = norm(
            event.get(
                "away_team",
                ""
            )
        )

        if not event_home or not event_away:

            continue

        names_match = (

            (
                event_home in home_name
                or home_name in event_home
            )

            and

            (
                event_away in away_name
                or away_name in event_away
            )

        )

        if not names_match:

            continue

        try:

            event_time = (
                datetime.datetime
                .fromisoformat(
                    event[
                        "commence_time"
                    ].replace(
                        "Z",
                        "+00:00"
                    )
                )
                .timestamp()
            )

        except Exception:

            event_time = fixture_time

        difference = abs(
            fixture_time
            -
            event_time
        )

        if (
            difference < best_score
            and difference <= 8 * 3600
        ):

            best = event
            best_score = difference

    return best


# ============================================================
# ODDS REAIS
# ============================================================

def external_markets(
    fixture,
    league
):

    if not ODDS_KEY:

        return []

    sport = SPORT_KEYS.get(
        league,
        ""
    )

    if not sport:

        return []

    data = odds(
        sport
    )

    events = (
        data
        if isinstance(
            data,
            list
        )
        else []
    )

    event = match_external(
        fixture,
        events
    )

    if not event:

        return []

    output = []

    for bookmaker in event.get(
        "bookmakers",
        []
    ):

        bookmaker_name = bookmaker.get(
            "title"
        )

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

                try:

                    price = float(
                        outcome.get(
                            "price"
                        )
                    )

                except Exception:

                    continue

                output.append({

                    "bookmaker":
                    bookmaker_name,

                    "market":
                    market_key,

                    "name":
                    outcome.get(
                        "name"
                    ),

                    "point":
                    outcome.get(
                        "point"
                    ),

                    "price":
                    price

                })

    return output


# ============================================================
# MELHORES ODDS
# ============================================================

def best_real_odds(
    model_markets,
    real_odds,
    fixture
):

    if not real_odds:

        return []

    home_name = fixture[
        "teams"
    ][
        "home"
    ][
        "name"
    ]

    away_name = fixture[
        "teams"
    ][
        "away"
    ][
        "name"
    ]

    results = []

    for model_market in model_markets:

        market_name = model_market[
            "market"
        ]

        probability = (
            model_market[
                "probability"
            ] / 100
        )

        candidates = []

        for odd in real_odds:

            odd_market = odd.get(
                "market"
            )

            outcome = norm(
                odd.get(
                    "name"
                )
            )

            point = odd.get(
                "point"
            )

            try:

                point = float(point)

            except Exception:

                point = None

            match = False

            # ------------------------------------------------
            # RESULTADO
            # ------------------------------------------------

            if (
                market_name == "Casa vence"
                and odd_market == "h2h"
                and (
                    outcome == norm(home_name)
                    or norm(home_name) in outcome
                    or outcome in norm(home_name)
                )
            ):

                match = True

            elif (
                market_name == "Fora vence"
                and odd_market == "h2h"
                and (
                    outcome == norm(away_name)
                    or norm(away_name) in outcome
                    or outcome in norm(away_name)
                )
            ):

                match = True

            elif (
                market_name == "Empate"
                and odd_market == "h2h"
                and outcome == "draw"
            ):

                match = True

            # ------------------------------------------------
            # TOTAIS
            # ------------------------------------------------

            elif (
                odd_market == "totals"
                and outcome == "over"
                and point is not None
            ):

                expected_line = {

                    "Mais de 0.5 gols": 0.5,
                    "Mais de 1.5 gols": 1.5,
                    "Mais de 2.5 gols": 2.5,
                    "Mais de 3.5 gols": 3.5

                }.get(
                    market_name
                )

                if (
                    expected_line is not None
                    and abs(
                        point
                        -
                        expected_line
                    ) < 0.01
                ):

                    match = True

            elif (
                odd_market == "totals"
                and outcome == "under"
                and point is not None
            ):

                expected_line = {

                    "Menos de 2.5 gols": 2.5,
                    "Menos de 3.5 gols": 3.5

                }.get(
                    market_name
                )

                if (
                    expected_line is not None
                    and abs(
                        point
                        -
                        expected_line
                    ) < 0.01
                ):

                    match = True

            if match:

                candidates.append(
                    odd
                )

        if not candidates:

            continue

        candidates.sort(
            key=lambda item:
            item["price"],
            reverse=True
        )

        best = candidates[0]

        real_price = best[
            "price"
        ]

        implied_probability = (
            1 / real_price
        )

        value = (
            probability
            * real_price
            - 1
        ) * 100

        results.append({

            "market":
            market_name,

            "category":
            model_market[
                "category"
            ],

            "model_probability":
            model_market[
                "probability"
            ],

            "fair_odd":
            model_market[
                "fair_odd"
            ],

            "bookmaker":
            best[
                "bookmaker"
            ],

            "real_odd":
            real_price,

            "implied_probability":
            round(
                implied_probability * 100,
                1
            ),

            "value_percent":
            round(
                value,
                2
            ),

            "score":
            model_market[
                "score"
            ]

        })

    results.sort(
        key=lambda item:
        item["value_percent"],
        reverse=True
    )

    return results


# ============================================================
# ANALISAR JOGO
# ============================================================

def analyze_fixture(
    fixture,
    league
):

    api_prediction = None

    if fixture.get(
        "_source"
    ) == "API-Football":

        try:

            prediction = af(
                "predictions",
                {

                    "fixture":
                    fixture[
                        "fixture"
                    ][
                        "id"
                    ]

                }
            )

            response = prediction.get(
                "response",
                []
            )

            if response:

                api_prediction = response[0]

        except Exception:

            api_prediction = None

    model = build_model(
        fixture,
        league
    )

    real_odds = external_markets(
        fixture,
        league
    )

    value_bets = best_real_odds(
        model.get(
            "markets",
            []
        ),
        real_odds,
        fixture
    )

    return {

        "prediction":
        api_prediction,

        "model":
        model,

        "markets":
        real_odds,

        "real_odds":
        real_odds,

        "value_bets":
        value_bets[:10],

        "best_value":
        value_bets[0]
        if value_bets
        else None,

        "source":
        fixture.get(
            "_source",
            "fallback"
        )

    }


# ============================================================
# CUPONS
# ============================================================

def risk_limit(
    risk
):

    risk = str(
        risk or "equilibrado"
    ).lower()

    if risk in (
        "conservador",
        "baixo"
    ):

        return 0.68

    if risk in (
        "agressivo",
        "alto"
    ):

        return 0.48

    return 0.58


def build_coupon(
    analyzed,
    target_odd=50,
    risk="equilibrado"
):

    try:

        target_odd = float(
            target_odd
        )

    except Exception:

        target_odd = 50.0

    target_odd = max(
        2.0,
        min(
            target_odd,
            100000.0
        )
    )

    minimum_probability = risk_limit(
        risk
    )

    candidates = []

    for item in analyzed:

        fixture = item.get(
            "fixture",
            {}
        )

        analysis = item.get(
            "analysis",
            {}
        )

        model = analysis.get(
            "model",
            {}
        )

        markets = model.get(
            "markets",
            []
        )

        for market in markets:

            probability = (
                float(
                    market.get(
                        "probability",
                        0
                    )
                )
                / 100
            )

            if probability < minimum_probability:

                continue

            fair_odd = float(
                market.get(
                    "fair_odd",
                    0
                ) or 0
            )

            if fair_odd <= 1:

                continue

            teams = fixture.get(
                "teams",
                {}
            )

            home = teams.get(
                "home",
                {}
            ).get(
                "name",
                "Casa"
            )

            away = teams.get(
                "away",
                {}
            ).get(
                "name",
                "Fora"
            )

            candidates.append({

                "fixture_id":
                fixture.get(
                    "fixture",
                    {}
                ).get("id"),

                "home":
                home,

                "away":
                away,

                "market":
                market.get("market"),

                "category":
                market.get("category"),

                "probability":
                round(
                    probability * 100,
                    1
                ),

                "fair_odd":
                fair_odd,

                "risk":
                market.get(
                    "risk",
                    "médio"
                ),

                "score":
                market.get(
                    "score",
                    0
                )

            })

    candidates.sort(
        key=lambda item: (
            item["score"],
            item["probability"]
        ),
        reverse=True
    )

    selected = []

    used_fixtures = set()
    category_count = {}

    for candidate in candidates:

        fixture_id = str(
            candidate["fixture_id"]
        )

        category = candidate[
            "category"
        ]

        if fixture_id in used_fixtures:

            continue

        if category_count.get(
            category,
            0
        ) >= 2:

            continue

        selected.append(
            candidate
        )

        used_fixtures.add(
            fixture_id
        )

        category_count[
            category
        ] = (
            category_count.get(
                category,
                0
            )
            + 1
        )

        current_odd = 1.0

        for selection in selected:

            current_odd *= selection[
                "fair_odd"
            ]

        if current_odd >= target_odd:

            break

    if not selected:

        return {

            "ok":
            False,

            "message":
            "Nenhum mercado adequado foi encontrado.",

            "selections":
            [],

            "estimated_odd":
            1.0

        }

    estimated_odd = 1.0

    for selection in selected:

        estimated_odd *= selection[
            "fair_odd"
        ]

    combined_probability = 1.0

    for selection in selected:

        combined_probability *= (
            selection[
                "probability"
            ] / 100
        )

    return {

        "ok":
        True,

        "target_odd":
        target_odd,

        "risk":
        risk,

        "estimated_odd":
        round(
            estimated_odd,
            2
        ),

        "combined_probability":
        round(
            combined_probability * 100,
            3
        ),

        "selections":
        selected,

        "count":
        len(selected),

        "warning":
        "A odd justa é estimada pelo modelo. A odd real deve ser conferida na casa."

    }


# ============================================================
# JSON
# ============================================================

def json_response(
    handler,
    payload,
    status=200
):

    body = json.dumps(
        payload,
        ensure_ascii=False
    ).encode(
        "utf-8"
    )

    handler.send_response(
        status
    )

    handler.send_header(
        "Content-Type",
        "application/json; charset=utf-8"
    )

    handler.send_header(
        "Content-Length",
        str(len(body))
    )

    handler.end_headers()

    handler.wfile.write(
        body
    )


# ============================================================
# SERVIDOR
# ============================================================

class MarquesHandler(
    SimpleHTTPRequestHandler
):

    def log_message(
        self,
        format,
        *args
    ):

        print(
            "%s - %s"
            % (
                self.address_string(),
                format % args
            )
        )

    # ========================================================
    # GET
    # ========================================================

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

        try:

            # ------------------------------------------------
            # HEALTH
            # ------------------------------------------------

            if path == "/api/health":

                return json_response(
                    self,
                    {

                        "ok":
                        True,

                        "api_football":
                        bool(AF_KEY),

                        "odds_api":
                        bool(ODDS_KEY),

                        "cache_ttl":
                        CACHE_TTL,

                        "leagues":
                        len(LEAGUES),

                        "model":
                        "Marques Pro V15"

                    }
                )

            # ------------------------------------------------
            # LIGAS
            # ------------------------------------------------

            if path == "/api/leagues":

                return json_response(
                    self,
                    {

                        "ok":
                        True,

                        "count":
                        len(LEAGUES),

                        "leagues":
                        list(
                            LEAGUES.keys()
                        )

                    }
                )

            # ------------------------------------------------
            # JOGOS
            # ------------------------------------------------

            if path == "/api/fixtures":

                league = params.get(
                    "league",
                    ["Brasil"]
                )[0]

                try:

                    days = int(
                        params.get(
                            "days",
                            ["1"]
                        )[0]
                    )

                except Exception:

                    days = 1

                days = max(
                    0,
                    min(days, 7)
                )

                fixtures, source = (
                    get_current_fixtures(
                        league,
                        days
                    )
                )

                return json_response(
                    self,
                    {

                        "ok":
                        True,

                        "league":
                        league,

                        "days":
                        days,

                        "source":
                        source,

                        "count":
                        len(fixtures),

                        "fixtures":
                        fixtures

                    }
                )

            # ------------------------------------------------
            # ANALISAR
            # ------------------------------------------------

            if path == "/api/analyze":

                league = params.get(
                    "league",
                    ["Brasil"]
                )[0]

                try:

                    days = int(
                        params.get(
                            "days",
                            ["1"]
                        )[0]
                    )

                except Exception:

                    days = 1

                days = max(
                    0,
                    min(days, 3)
                )

                fixtures, source = (
                    get_current_fixtures(
                        league,
                        days
                    )
                )

                analyzed = []

                for fixture in fixtures:

                    try:

                        analysis = analyze_fixture(
                            fixture,
                            league
                        )

                        analyzed.append({

                            "fixture":
                            fixture,

                            "analysis":
                            analysis

                        })

                    except Exception as e:

                        print(
                            "ANALYSIS ERROR:",
                            repr(e)
                        )

                        analyzed.append({

                            "fixture":
                            fixture,

                            "analysis": {

                                "error":
                                str(e)

                            }

                        })

                return json_response(
                    self,
                    {

                        "ok":
                        True,

                        "league":
                        league,

                        "days":
                        days,

                        "source":
                        source,

                        "count":
                        len(analyzed),

                        "games":
                        analyzed

                    }
                )

            # ------------------------------------------------
            # PREDICTION
            # ------------------------------------------------

            if path == "/api/prediction":

                fixture_id = params.get(
                    "fixture",
                    [""]
                )[0]

                league = params.get(
                    "league",
                    ["Brasil"]
                )[0]

                fixtures, _ = (
                    get_current_fixtures(
                        league,
                        3
                    )
                )

                fixture = next(
                    (
                        f
                        for f in fixtures
                        if str(
                            f.get(
                                "fixture",
                                {}
                            ).get("id")
                        )
                        ==
                        str(fixture_id)
                    ),
                    None
                )

                if not fixture:

                    return json_response(
                        self,
                        {

                            "ok":
                            False,

                            "error":
                            "Jogo não encontrado."

                        },
                        404
                    )

                analysis = analyze_fixture(
                    fixture,
                    league
                )

                return json_response(
                    self,
                    {

                        "ok":
                        True,

                        "fixture":
                        fixture,

                        "analysis":
                        analysis

                    }
                )

            # ------------------------------------------------
            # MERCADOS
            # ------------------------------------------------

            if path == "/api/markets":

                return json_response(
                    self,
                    {

                        "ok":
                        True,

                        "markets":
                        MARKETS

                    }
                )

            # ------------------------------------------------
            # ODDS
            # ------------------------------------------------

            if path == "/api/odds":

                league = params.get(
                    "league",
                    ["Brasil"]
                )[0]

                result = odds(
                    SPORT_KEYS.get(
                        league,
                        ""
                    )
                )

                return json_response(
                    self,
                    {

                        "ok":
                        not bool(
                            result.get("error")
                        ),

                        "league":
                        league,

                        "bookmakers":
                        len(
                            result[0].get(
                                "bookmakers",
                                []
                            )
                        )
                        if isinstance(
                            result,
                            list
                        ) and result
                        else 0,

                        "data":
                        result

                    }
                )

            # ------------------------------------------------
            # HISTÓRICO
            # ------------------------------------------------

            if path == "/api/history":

                data = load_data()

                return json_response(
                    self,
                    {

                        "ok":
                        True,

                        "predictions":
                        data.get(
                            "predictions",
                            []
                        ),

                        "coupons":
                        data.get(
                            "coupons",
                            []
                        )

                    }
                )

            return super().do_GET()

        except Exception as e:

            print(
                "API ERROR:",
                repr(e)
            )

            return json_response(
                self,
                {

                    "ok":
                    False,

                    "error":
                    str(e)

                },
                500
            )

    # ========================================================
    # POST
    # ========================================================

    def do_POST(
        self
    ):

        parsed = urllib.parse.urlparse(
            self.path
        )

        path = parsed.path

        try:

            length = int(
                self.headers.get(
                    "Content-Length",
                    "0"
                )
            )

            raw = self.rfile.read(
                length
            )

            payload = (
                json.loads(
                    raw.decode("utf-8")
                )
                if raw
                else {}
            )

        except Exception:

            payload = {}

        try:

            # ------------------------------------------------
            # CUPOM
            # ------------------------------------------------

            if path == "/api/coupon/build":

                league = payload.get(
                    "league",
                    "Brasil"
                )

                try:

                    days = int(
                        payload.get(
                            "days",
                            1
                        )
                    )

                except Exception:

                    days = 1

                try:

                    target_odd = float(
                        payload.get(
                            "target_odd",
                            50
                        )
                    )

                except Exception:

                    target_odd = 50

                risk = payload.get(
                    "risk",
                    "equilibrado"
                )

                fixtures, source = (
                    get_current_fixtures(
                        league,
                        days
                    )
                )

                analyzed = []

                for fixture in fixtures:

                    try:

                        analysis = analyze_fixture(
                            fixture,
                            league
                        )

                        analyzed.append({

                            "fixture":
                            fixture,

                            "analysis":
                            analysis

                        })

                    except Exception as e:

                        print(
                            "ANALYSIS ERROR:",
                            repr(e)
                        )

                coupon = build_coupon(
                    analyzed,
                    target_odd,
                    risk
                )

                coupon["league"] = league
                coupon["source"] = source

                return json_response(
                    self,
                    coupon
                )

            # ------------------------------------------------
            # SALVAR CUPOM
            # ------------------------------------------------

            if path == "/api/coupon/save":

                data = load_data()

                coupon_id = data.get(
                    "next_coupon_id",
                    1
                )

                payload["id"] = coupon_id

                payload["created_at"] = (
                    datetime.datetime.utcnow()
                    .isoformat()
                    + "Z"
                )

                data.setdefault(
                    "coupons",
                    []
                ).append(
                    payload
                )

                data[
                    "next_coupon_id"
                ] = coupon_id + 1

                save_data(
                    data
                )

                return json_response(
                    self,
                    {

                        "ok":
                        True,

                        "coupon":
                        payload

                    }
                )

            # ------------------------------------------------
            # RESULTADO
            # ------------------------------------------------

            if path == "/api/result":

                data = load_data()

                prediction_id = payload.get(
                    "prediction_id"
                )

                result = payload.get(
                    "result"
                )

                for item in data.get(
                    "predictions",
                    []
                ):

                    if str(
                        item.get("id")
                    ) == str(
                        prediction_id
                    ):

                        item[
                            "result"
                        ] = result

                save_data(
                    data
                )

                return json_response(
                    self,
                    {

                        "ok":
                        True

                    }
                )

            return json_response(
                self,
                {

                    "ok":
                    False,

                    "error":
                    "Rota não encontrada."

                },
                404
            )

        except Exception as e:

            print(
                "POST ERROR:",
                repr(e)
            )

            return json_response(
                self,
                {

                    "ok":
                    False,

                    "error":
                    str(e)

                },
                500
            )


# ============================================================
# INICIAR
# ============================================================

def run_server():

    server = ThreadingHTTPServer(
        (
            "0.0.0.0",
            PORT
        ),
        MarquesHandler
    )

    print("")
    print("==========================================")
    print(
        f"Marques Pro V15 rodando na porta {PORT}"
    )
    print("==========================================")

    print(
        "API-Football:",
        "CONFIGURADA"
        if AF_KEY
        else "NÃO CONFIGURADA"
    )

    print(
        "Odds API:",
        "CONFIGURADA"
        if ODDS_KEY
        else "NÃO CONFIGURADA"
    )

    print(
        "Ligas:",
        len(LEAGUES)
    )

    print("==========================================")

    server.serve_forever()


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    run_server()
