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
# CONFIGURAÇÃO
# ============================================================

PORT = int(os.getenv("PORT", "8787"))
AF_KEY = os.getenv("API_FOOTBALL_KEY", "").strip()
ODDS_KEY = os.getenv("ODDS_API_KEY", "").strip()

CACHE_TTL = int(os.getenv("CACHE_TTL", "900"))
CACHE = {}

DATA_FILE = "marques_pro_history.json"

LEAGUES = {
    "Brasil": 71,
    "Inglaterra": 39,
    "Espanha": 140,
    "Itália": 135,
    "Alemanha": 78,
    "França": 61
}

# ESPN - usado como fonte alternativa para jogos atuais
ESPN_LEAGUES = {
    "Brasil": "bra.1",
    "Inglaterra": "eng.1",
    "Espanha": "esp.1",
    "Itália": "ita.1",
    "Alemanha": "ger.1",
    "França": "fra.1"
}

SPORT_KEYS = {
    "Brasil": "soccer_brazil_campeonato",
    "Inglaterra": "soccer_epl",
    "Espanha": "soccer_spain_la_liga",
    "Itália": "soccer_italy_serie_a",
    "Alemanha": "soccer_germany_bundesliga",
    "França": "soccer_france_ligue_one"
}


# ============================================================
# HISTÓRICO
# ============================================================

def load_data():
    try:
        return json.loads(
            Path(DATA_FILE).read_text(encoding="utf-8")
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
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


# ============================================================
# HTTP
# ============================================================

def get(url, key=None, headers=None):
    h = {
        "User-Agent": "Marques-Pro/12.0",
        "Accept": "application/json"
    }

    if headers:
        h.update(headers)

    if key:
        h["x-apisports-key"] = key

    req = urllib.request.Request(url, headers=h)

    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            raw = r.read().decode("utf-8")
            return json.loads(raw)

    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode("utf-8")
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


def cached(url, key=None, headers=None):
    now = time.time()
    hit = CACHE.get(url)

    if hit and now - hit[0] < CACHE_TTL:
        return hit[1]

    data = get(url, key, headers)
    CACHE[url] = (now, data)

    return data


# ============================================================
# API-FOOTBALL
# ============================================================

def af(path, params):
    if not AF_KEY:
        return {
            "error": "API_FOOTBALL_KEY não configurada",
            "response": []
        }

    q = urllib.parse.urlencode(params)

    url = (
        "https://v3.football.api-sports.io/"
        + path
        + "?"
        + q
    )

    return cached(url, AF_KEY)


def api_football_has_data(data):
    if not isinstance(data, dict):
        return False

    if data.get("error"):
        return False

    if data.get("errors"):
        return False

    return bool(data.get("response"))


# ============================================================
# ODDS API
# ============================================================

def odds(sport):
    if not ODDS_KEY:
        return {
            "error": "ODDS_API_KEY não configurada",
            "matches": []
        }

    q = urllib.parse.urlencode({
        "regions": "eu",
        "markets": "h2h,totals",
        "oddsFormat": "decimal",
        "apiKey": ODDS_KEY
    })

    url = (
        "https://api.the-odds-api.com/v4/sports/"
        + sport
        + "/odds?"
        + q
    )

    return cached(url)


# ============================================================
# NORMALIZAÇÃO
# ============================================================

def norm(s):
    s = str(s or "").lower()

    s = re.sub(
        r"[^a-z0-9áàâãéêíóôõúüç ]",
        " ",
        s
    )

    return re.sub(r"\s+", " ", s).strip()


def parse_pct(v):
    try:
        return float(
            str(v)
            .replace("%", "")
            .replace(",", ".")
        ) / 100
    except Exception:
        return 0.0


# ============================================================
# FONTE ALTERNATIVA - ESPN
# ============================================================

def espn_scoreboard(league, date):
    espn_league = ESPN_LEAGUES.get(league)

    if not espn_league:
        return []

    date_str = date.strftime("%Y%m%d")

    url = (
        "https://site.api.espn.com/apis/site/v2/sports/"
        "soccer/"
        + espn_league
        + "/scoreboard?dates="
        + date_str
    )

    data = cached(url)

    if not isinstance(data, dict):
        return []

    events = data.get("events", [])

    if not isinstance(events, list):
        return []

    return events


def espn_to_fixture(event, league):
    try:
        competitions = event.get("competitions", [])

        if not competitions:
            return None

        competition = competitions[0]

        competitors = competition.get("competitors", [])

        if len(competitors) < 2:
            return None

        home = None
        away = None

        for c in competitors:
            if c.get("homeAway") == "home":
                home = c
            elif c.get("homeAway") == "away":
                away = c

        if not home or not away:
            return None

        home_name = (
            home.get("team", {}).get("displayName")
            or home.get("team", {}).get("name")
            or ""
        )

        away_name = (
            away.get("team", {}).get("displayName")
            or away.get("team", {}).get("name")
            or ""
        )

        if not home_name or not away_name:
            return None

        event_id = str(event.get("id", ""))

        date = event.get("date")

        status = (
            event.get("status", {})
            .get("type", {})
            .get("name", "STATUS_SCHEDULED")
        )

        return {
            "fixture": {
                "id": 900000000 + int(
                    re.sub(r"\D", "", event_id)[:8] or "0"
                ),
                "date": date,
                "status": {
                    "short": status
                }
            },
            "teams": {
                "home": {
                    "id": home.get("team", {}).get("id"),
                    "name": home_name,
                    "logo": home.get("team", {}).get("logo")
                },
                "away": {
                    "id": away.get("team", {}).get("id"),
                    "name": away_name,
                    "logo": away.get("team", {}).get("logo")
                }
            },
            "league": {
                "name": league,
                "id": LEAGUES.get(league)
            },
            "_source": "ESPN"
        }

    except Exception:
        return None


def get_current_fixtures(league, days=1):
    today = datetime.date.today()

    # --------------------------------------------------------
    # 1. Tenta API-Football.
    # --------------------------------------------------------

    if AF_KEY:
        result = af(
            "fixtures",
            {
                "league": LEAGUES.get(league, 71),
                "season": today.year,
                "from": str(today),
                "to": str(
                    today + datetime.timedelta(days=days)
                )
            }
        )

        if api_football_has_data(result):
            fixtures = result.get("response", [])

            for f in fixtures:
                f["_source"] = "API-Football"

            return fixtures, "API-Football"

    # --------------------------------------------------------
    # 2. Fallback ESPN.
    # --------------------------------------------------------

    fixtures = []

    for offset in range(days + 1):
        day = today + datetime.timedelta(days=offset)

        events = espn_scoreboard(league, day)

        for event in events:
            f = espn_to_fixture(event, league)

            if f:
                fixtures.append(f)

    # Remove duplicados
    unique = {}

    for f in fixtures:
        key = (
            norm(f["teams"]["home"]["name"])
            + "|"
            + norm(f["teams"]["away"]["name"])
            + "|"
            + str(f["fixture"].get("date"))
        )

        unique[key] = f

    return list(unique.values()), "ESPN"


# ============================================================
# MODELO DE PREVISÃO
# ============================================================

def local_prediction(fixture):
    """
    Modelo básico de fallback.

    Quando o plano do API-Football não permite a temporada atual,
    usamos uma estimativa inicial para que o aplicativo continue
    funcionando.

    Não representa garantia de resultado.
    """

    home = norm(
        fixture.get("teams", {})
        .get("home", {})
        .get("name", "")
    )

    away = norm(
        fixture.get("teams", {})
        .get("away", {})
        .get("name", "")
    )

    # Pontuação inicial neutra
    home_strength = 50.0
    away_strength = 50.0

    # Vantagem do mandante
    home_strength += 8

    # Pequenos ajustes por palavras conhecidas
    # apenas como heurística, sem fingir que são estatísticas reais.
    strong_teams = [
        "real madrid",
        "barcelona",
        "liverpool",
        "manchester city",
        "arsenal",
        "bayern",
        "inter",
        "milan",
        "juventus",
        "psg",
        "flamengo",
        "palmeiras"
    ]

    for team in strong_teams:
        if team in home:
            home_strength += 7

        if team in away:
            away_strength += 7

    total = home_strength + away_strength

    home_raw = home_strength / total
    away_raw = away_strength / total

    # Reserva espaço para empate
    draw = 0.27

    remaining = 1 - draw

    home_p = home_raw * remaining
    away_p = away_raw * remaining

    # Garantir soma = 1
    total_p = home_p + draw + away_p

    home_p /= total_p
    draw_p = draw / total_p
    away_p /= total_p

    return {
        "predictions": {
            "winner": {
                "id": fixture["teams"]["home"].get("id"),
                "name": fixture["teams"]["home"]["name"]
                if home_p >= away_p
                else fixture["teams"]["away"]["name"]
            },
            "percent": {
                "home": f"{home_p * 100:.1f}%",
                "draw": f"{draw_p * 100:.1f}%",
                "away": f"{away_p * 100:.1f}%"
            },
            "advice": {
                "1": f"{home_p * 100:.1f}%",
                "X": f"{draw_p * 100:.1f}%",
                "2": f"{away_p * 100:.1f}%"
            }
        },
        "model": "Marques Pro fallback",
        "source": fixture.get("_source", "fallback")
    }


# ============================================================
# ODDS EXTERNAS
# ============================================================

def match_external(f, events):
    fh = norm(
        f["teams"]["home"]["name"]
    )

    fa = norm(
        f["teams"]["away"]["name"]
    )

    try:
        ft = datetime.datetime.fromisoformat(
            f["fixture"]["date"].replace("Z", "+00:00")
        ).timestamp()
    except Exception:
        ft = time.time()

    best = None
    bestscore = 999999

    for e in events:
        eh = norm(e.get("home_team", ""))
        ea = norm(e.get("away_team", ""))

        if not eh or not ea:
            continue

        names = (
            (eh in fh or fh in eh)
            and
            (ea in fa or fa in ea)
        )

        if not names:
            continue

        try:
            et = datetime.datetime.fromisoformat(
                e["commence_time"].replace("Z", "+00:00")
            ).timestamp()
        except Exception:
            et = ft

        score = abs(ft - et)

        if score < bestscore and score <= 8 * 3600:
            best = e
            bestscore = score

    return best


def external_markets(f, league):
    if not ODDS_KEY:
        return []

    data = odds(
        SPORT_KEYS.get(league, "")
    )

    events = data if isinstance(data, list) else []

    e = match_external(f, events)

    if not e:
        return []

    out = []

    for bm in e.get("bookmakers", []):
        for m in bm.get("markets", []):
            for o in m.get("outcomes", []):
                if m.get("key") in ("h2h", "totals"):
                    try:
                        price = float(o.get("price"))
                    except Exception:
                        continue

                    out.append({
                        "bookmaker": bm.get("title"),
                        "market": m.get("key"),
                        "name": o.get("name"),
                        "price": price
                    })

    return out


# ============================================================
# ANÁLISE
# ============================================================

def analyze_fixture(f, league):
    source = f.get("_source", "")

    # Se veio do API-Football, tenta previsão real
    if source == "API-Football":
        try:
            pred = af(
                "predictions",
                {
                    "fixture": f["fixture"]["id"]
                }
            )

            response = pred.get("response", [])

            if response:
                p = response[0]

                return {
                    "prediction": p,
                    "markets": external_markets(
                        f,
                        league
                    ),
                    "source": "API-Football"
                }

        except Exception:
            pass

    # Fallback
    return {
        "prediction": local_prediction(f),
        "markets": external_markets(f, league),
        "source": "Marques Pro fallback"
    }


# ============================================================
# CUPONS
# ============================================================

def save_coupon(
    league,
    target,
    sel,
    total_odd
):
    data = load_data()

    now = datetime.datetime.now(
        datetime.timezone.utc
    ).isoformat()

    cid = data["next_coupon_id"]

    data["next_coupon_id"] += 1

    avg_prob = (
        sum(x.get("p", 0) for x in sel)
        / len(sel)
        if sel else 0
    )

    avg_edge = (
        sum(x.get("edge", 0) for x in sel)
        / len(sel)
        if sel else 0
    )

    data["coupons"].append([
        cid,
        now,
        league,
        target,
        total_odd,
        len(sel),
        avg_prob,
        avg_edge,
        "pending"
    ])

    for x in sel:
        pid = data["next_prediction_id"]

        data["next_prediction_id"] += 1

        data["predictions"].append([
            pid,
            now,
            x.get("fixture"),
            x.get("home", ""),
            x.get("away", ""),
            league,
            x.get("market", ""),
            x.get("odd", 0),
            x.get("p", 0),
            x.get("edge", 0),
            x.get("score", 0),
            "pending"
        ])

    save_data(data)

    return cid


# ============================================================
# SERVIDOR
# ============================================================

class Handler(SimpleHTTPRequestHandler):

    def j(self, obj, status=200):
        raw = json.dumps(
            obj,
            ensure_ascii=False
        ).encode("utf-8")

        self.send_response(status)

        self.send_header(
            "Content-Type",
            "application/json; charset=utf-8"
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

        self.wfile.write(raw)

    def body(self):
        n = int(
            self.headers.get(
                "Content-Length",
                "0"
            )
        )

        raw = self.rfile.read(n).decode()

        return json.loads(
            raw or "{}"
        )

    def do_OPTIONS(self):
        self.send_response(204)

        self.send_header(
            "Access-Control-Allow-Origin",
            "*"
        )

        self.send_header(
            "Access-Control-Allow-Headers",
            "Content-Type"
        )

        self.end_headers()

    def do_POST(self):
        u = urllib.parse.urlparse(
            self.path
        )

        try:

            if u.path == "/api/coupon/save":

                b = self.body()

                cid = save_coupon(
                    b.get("league", ""),
                    float(b.get("target", 0)),
                    b.get("selections", []),
                    float(b.get("total_odd", 0))
                )

                return self.j({
                    "ok": True,
                    "id": cid
                })

            if u.path == "/api/result":

                b = self.body()

                data = load_data()

                pid = int(b["id"])

                result = b.get(
                    "result",
                    "pending"
                )

                for row in data["predictions"]:

                    if int(row[0]) == pid:

                        row[11] = result

                        break

                save_data(data)

                return self.j({
                    "ok": True
                })

            return self.j({
                "error": "rota não encontrada"
            }, 404)

        except Exception as e:

            return self.j({
                "error": str(e)
            }, 500)

    def do_GET(self):

        u = urllib.parse.urlparse(
            self.path
        )

        q = urllib.parse.parse_qs(
            u.query
        )

        try:

            # ------------------------------------------------
            # HEALTH
            # ------------------------------------------------

            if u.path == "/api/health":

                return self.j({
                    "ok": True,
                    "api_football": bool(AF_KEY),
                    "odds_api": bool(ODDS_KEY),
                    "cache_ttl": CACHE_TTL,
                    "version": "12.0",
                    "fallback": "ESPN"
                })

            # ------------------------------------------------
            # LIGAS
            # ------------------------------------------------

            if u.path == "/api/leagues":

                return self.j(
                    LEAGUES
                )

            # ------------------------------------------------
            # FIXTURES
            # ------------------------------------------------

            if u.path == "/api/fixtures":

                league = q.get(
                    "league",
                    ["Brasil"]
                )[0]

                days = max(
                    0,
                    min(
                        int(
                            q.get(
                                "days",
                                ["1"]
                            )[0]
                        ),
                        7
                    )
                )

                if league not in LEAGUES:

                    return self.j({
                        "error": "Liga inválida",
                        "response": []
                    }, 400)

                fixtures, source = get_current_fixtures(
                    league,
                    days
                )

                return self.j({
                    "league": league,
                    "source": source,
                    "results": len(fixtures),
                    "response": fixtures
                })

            # ------------------------------------------------
            # PREDICTION
            # ------------------------------------------------

            if u.path == "/api/prediction":

                fixture_id = int(
                    q["fixture"][0]
                )

                home = q.get(
                    "home",
                    [""]
                )[0]

                away = q.get(
                    "away",
                    [""]
                )[0]

                league = q.get(
                    "league",
                    ["Brasil"]
                )[0]

                date = q.get(
                    "date",
                    [
                        datetime.datetime.now(
                            datetime.timezone.utc
                        ).isoformat()
                    ]
                )[0]

                f = {
                    "fixture": {
                        "id": fixture_id,
                        "date": date
                    },
                    "teams": {
                        "home": {
                            "name": home
                        },
                        "away": {
                            "name": away
                        }
                    },
                    "league": {
                        "name": league
                    },
                    "_source": "ESPN"
                }

                return self.j(
                    analyze_fixture(
                        f,
                        league
                    )
                )

            # ------------------------------------------------
            # ANALYZE
            # ------------------------------------------------

            if u.path == "/api/analyze":

                league = q.get(
                    "league",
                    ["Brasil"]
                )[0]

                days = max(
                    0,
                    min(
                        int(
                            q.get(
                                "days",
                                ["1"]
                            )[0]
                        ),
                        3
                    )
                )

                if league not in LEAGUES:

                    return self.j({
                        "error": "Liga inválida",
                        "fixtures": []
                    }, 400)

                fixtures, source = get_current_fixtures(
                    league,
                    days
                )

                out = []

                # Máximo 20 para não sobrecarregar
                for f in fixtures[:20]:

                    try:

                        result = analyze_fixture(
                            f,
                            league
                        )

                        out.append({
                            "fixture": f,
                            "data": result
                        })

                    except Exception as e:

                        out.append({
                            "fixture": f,
                            "data": {
                                "error": str(e)
                            }
                        })

                return self.j({
                    "ok": True,
                    "league": league,
                    "source": source,
                    "results": len(out),
                    "fixtures": out
                })

            # ------------------------------------------------
            # ODDS
            # ------------------------------------------------

            if u.path == "/api/odds":

                league = q.get(
                    "league",
                    ["Brasil"]
                )[0]

                data = odds(
                    SPORT_KEYS.get(
                        league,
                        ""
                    )
                )

                if isinstance(data, dict):

                    return self.j({
                        "league": league,
                        **data
                    })

                return self.j({
                    "league": league,
                    "matches": data
                })

            # ------------------------------------------------
            # HISTORY
            # ------------------------------------------------

            if u.path == "/api/history":

                data = load_data()

                return self.j({
                    "rows": list(
                        reversed(
                            data["predictions"][-200:]
                        )
                    ),
                    "coupons": list(
                        reversed(
                            data["coupons"][-50:]
                        )
                    )
                })

            # ------------------------------------------------
            # FRONTEND
            # ------------------------------------------------

            self.path = "index.html"

            return super().do_GET()

        except Exception as e:

            return self.j({
                "ok": False,
                "error": str(e),
                "path": u.path
            }, 500)


# ============================================================
# START
# ============================================================

print(
    "=============================================="
)

print(
    " Marques Pro v12"
)

print(
    " API-Football:",
    "ATIVA" if AF_KEY else "NÃO CONFIGURADA"
)

print(
    " Odds API:",
    "ATIVA" if ODDS_KEY else "NÃO CONFIGURADA"
)

print(
    " Fallback de jogos: ESPN"
)

print(
    " Porta:",
    PORT
)

print(
    "=============================================="
)

ThreadingHTTPServer(
    ("0.0.0.0", PORT),
    Handler
).serve_forever()
