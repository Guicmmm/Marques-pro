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
from concurrent.futures import ThreadPoolExecutor, as_completed

# ============================================================
# MARQUES PRO AI V20
# Backend focado EXCLUSIVAMENTE em previsões para apostas.
#
# FONTES DE JOGOS:
#   1. SofaScore
#   2. ESPN
#   3. API-Football (opcional)
#   4. Flashscore via API compatível configurada (opcional)
#
# DADOS PARA O MODELO:
#   - últimos jogos
#   - gols feitos/sofridos
#   - forma
#   - casa/fora
#   - BTTS
#   - over/under
#   - escanteios
#   - cartões
#   - chutes
#   - chutes no gol
#
# NÃO USA:
#   - escalações
#   - lesões
#   - notícias
#
# index.html: não precisa ser alterado.
# ============================================================

PORT = int(os.getenv("PORT", "8787"))
AF_KEY = os.getenv("API_FOOTBALL_KEY", "").strip()
ODDS_KEY = os.getenv("ODDS_API_KEY", "").strip()
FLASHSCORE_API_URL = os.getenv("FLASHSCORE_API_URL", "").strip()

CACHE_TTL = int(os.getenv("CACHE_TTL", "900"))
DATA_FILE = "marques_pro_history.json"
VERSION = "Marques Pro AI V20"

BRAZIL_TZ = timezone(timedelta(hours=-3))
CACHE = {}

# ============================================================
# LIGAS PRINCIPAIS
# ============================================================

LEAGUES = {
    "Brasil": {"id": 71, "country": "Brasil", "espn": "bra.1", "odds": "soccer_brazil_campeonato", "sofa_id": 325},
    "Inglaterra": {"id": 39, "country": "Inglaterra", "espn": "eng.1", "odds": "soccer_epl", "sofa_id": 17},
    "Espanha": {"id": 140, "country": "Espanha", "espn": "esp.1", "odds": "soccer_spain_la_liga", "sofa_id": 8},
    "Itália": {"id": 135, "country": "Itália", "espn": "ita.1", "odds": "soccer_italy_serie_a", "sofa_id": 23},
    "Alemanha": {"id": 78, "country": "Alemanha", "espn": "ger.1", "odds": "soccer_germany_bundesliga", "sofa_id": 35},
    "França": {"id": 61, "country": "França", "espn": "fra.1", "odds": "soccer_france_ligue_one", "sofa_id": 34},
    "Portugal": {"id": 94, "country": "Portugal", "espn": "por.1", "odds": "soccer_portugal_primeira_liga", "sofa_id": 238},
    "Holanda": {"id": 88, "country": "Holanda", "espn": "ned.1", "odds": "soccer_netherlands_eredivisie", "sofa_id": 37},
    "Bélgica": {"id": 144, "country": "Bélgica", "espn": "bel.1", "odds": "soccer_belgium_first_div", "sofa_id": 38},
    "Turquia": {"id": 203, "country": "Turquia", "espn": "tur.1", "odds": "soccer_turkey_super_league", "sofa_id": 52},
    "Argentina": {"id": 128, "country": "Argentina", "espn": "arg.1", "odds": "soccer_argentina_primera_division", "sofa_id": 155},
    "México": {"id": 262, "country": "México", "espn": "mex.1", "odds": "soccer_mexico_ligamx", "sofa_id": 116},
    "Estados Unidos - MLS": {"id": 253, "country": "Estados Unidos", "espn": "usa.1", "odds": "soccer_usa_mls", "sofa_id": 169},
    "Arábia Saudita": {"id": 307, "country": "Arábia Saudita", "espn": None, "odds": "soccer_saudi_arabia_pro_league", "sofa_id": 300},
    "Japão": {"id": 98, "country": "Japão", "espn": "jpn.1", "odds": "soccer_japan_j_league", "sofa_id": 196},
    "Coreia do Sul": {"id": 292, "country": "Coreia do Sul", "espn": "kor.1", "odds": "soccer_korea_kleague1", "sofa_id": 292},
    "Colômbia": {"id": 239, "country": "Colômbia", "espn": "col.1", "odds": "soccer_colombia_primera_a", "sofa_id": 115},
    "Chile": {"id": 265, "country": "Chile", "espn": "chi.1", "odds": "soccer_chile_primera_division", "sofa_id": 21},
    "Uruguai": {"id": 268, "country": "Uruguai", "espn": "uru.1", "odds": "soccer_uruguay_primera_division", "sofa_id": 278},
}

INTERNATIONAL = {
    "Champions League": {"id": 2, "country": "Europa", "espn": "uefa.champions", "odds": "soccer_uefa_champs_league", "sofa_id": 7},
    "Europa League": {"id": 3, "country": "Europa", "espn": "uefa.europa", "odds": "soccer_uefa_europa_league", "sofa_id": 679},
    "Conference League": {"id": 848, "country": "Europa", "espn": "uefa.europa.conf", "odds": "soccer_uefa_europa_conference_league", "sofa_id": 17015},
    "Libertadores": {"id": 13, "country": "América do Sul", "espn": "conmebol.libertadores", "odds": "soccer_conmebol_libertadores", "sofa_id": 384},
    "Sul-Americana": {"id": 11, "country": "América do Sul", "espn": "conmebol.sudamericana", "odds": "soccer_conmebol_sudamericana", "sofa_id": 480},
}
LEAGUES.update(INTERNATIONAL)

# ============================================================
# UTILITÁRIOS
# ============================================================

def brazil_now():
    return datetime.now(BRAZIL_TZ)

def brazil_today():
    return brazil_now().date()

def clamp(v, lo, hi):
    return max(lo, min(hi, v))

def parse_num(v, default=0):
    try:
        if isinstance(v, (int, float)):
            return float(v)
        m = re.search(r"-?\d+(?:\.\d+)?", str(v))
        return float(m.group()) if m else default
    except Exception:
        return default

def norm(v):
    return re.sub(r"[^a-z0-9 ]", "", str(v or "").lower()).strip()

def normalize_team_name(name):
    x = norm(name)
    x = re.sub(r"\b(fc|afc|cf|sc|club|football club)\b", "", x)
    return re.sub(r"\s+", " ", x).strip()

def iso_date(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None

def local_date_from_timestamp(ts):
    try:
        return datetime.fromtimestamp(int(ts), timezone.utc).astimezone(BRAZIL_TZ).date()
    except Exception:
        return None

def cached(key, fn, ttl=CACHE_TTL):
    now = time.time()
    item = CACHE.get(key)
    if item and now - item[0] < ttl:
        return item[1]
    value = fn()
    if value is not None:
        CACHE[key] = (now, value)
    return value

def get(url, headers=None, timeout=8):
    h = headers or {
        "User-Agent": "Mozilla/5.0 (compatible; MarquesProAI/20.0)",
        "Accept": "application/json,text/plain,*/*"
    }
    try:
        req = urllib.request.Request(url, headers=h)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as e:
        print(f"[HTTP] {url} -> {e}")
        return None

def poisson_pmf(k, lam):
    lam = max(.01, float(lam))
    return math.exp(-lam) * lam**k / math.factorial(k)

def poisson_over(lam, line):
    # Para linhas .5: P(X > linha) = 1 - P(X <= floor(linha))
    n = int(math.floor(line))
    return 1 - sum(poisson_pmf(k, lam) for k in range(n + 1))

def poisson_under(lam, line):
    n = int(math.floor(line))
    return sum(poisson_pmf(k, lam) for k in range(n + 1))

def poisson_btts(h, a):
    return 1 - math.exp(-h) - math.exp(-a) + math.exp(-(h + a))

# ============================================================
# API FOOTBALL / ODDS
# ============================================================

def af(endpoint, params=None, ttl=900):
    if not AF_KEY:
        return None
    params = params or {}
    q = urllib.parse.urlencode(params)
    url = "https://v3.football.api-sports.io/" + endpoint + (("?" + q) if q else "")
    return cached("af:" + url, lambda: get(url, {
        "x-apisports-key": AF_KEY,
        "User-Agent": "MarquesProAI/20"
    }), ttl)

def odds_api(sport):
    if not ODDS_KEY or not sport:
        return []
    q = urllib.parse.urlencode({
        "regions": "eu",
        "markets": "h2h,totals,spreads",
        "oddsFormat": "decimal",
        "apiKey": ODDS_KEY
    })
    url = f"https://api.the-odds-api.com/v4/sports/{urllib.parse.quote(sport)}/odds?{q}"
    data = cached("odds:" + sport, lambda: get(url), 300)
    return data if isinstance(data, list) else []

# ============================================================
# ESPN - JOGOS
# ============================================================

def espn_scoreboard(code, date_value):
    if not code:
        return None
    url = (
        "https://site.api.espn.com/apis/site/v2/sports/soccer/"
        + urllib.parse.quote(code)
        + "/scoreboard?dates="
        + date_value
    )
    return cached("espn:" + code + ":" + date_value, lambda: get(url), 180)

def espn_summary(code, event_id):
    if not code or not event_id:
        return None
    url = (
        "https://site.api.espn.com/apis/site/v2/sports/soccer/"
        + urllib.parse.quote(code)
        + "/summary?event="
        + urllib.parse.quote(str(event_id))
    )
    return cached("espn-summary:" + code + ":" + str(event_id), lambda: get(url), 900)

def espn_fixture(event, league_name):
    comps = event.get("competitions", [])
    if not comps:
        return None
    comp = comps[0]
    home = next((x for x in comp.get("competitors", []) if x.get("homeAway") == "home"), None)
    away = next((x for x in comp.get("competitors", []) if x.get("homeAway") == "away"), None)
    if not home or not away:
        return None
    parsed = iso_date(event.get("date"))
    st = event.get("status", {}).get("type", {})
    return {
        "fixture": {
            "id": event.get("id"),
            "provider_id": event.get("id"),
            "date": event.get("date"),
            "timestamp": int(parsed.timestamp()) if parsed else None,
            "status": {"short": st.get("shortDetail"), "long": st.get("description")}
        },
        "league": {
            "name": league_name,
            "country": LEAGUES.get(league_name, {}).get("country")
        },
        "teams": {
            "home": {"id": home.get("team", {}).get("id"), "name": home.get("team", {}).get("displayName")},
            "away": {"id": away.get("team", {}).get("id"), "name": away.get("team", {}).get("displayName")}
        },
        "goals": {"home": parse_num(home.get("score"), 0), "away": parse_num(away.get("score"), 0)},
        "_source": "ESPN"
    }

def espn_fixtures(league_name, days=7):
    code = LEAGUES.get(league_name, {}).get("espn")
    if not code:
        return []
    days = int(clamp(parse_num(days, 7), 1, 14))
    today = brazil_today()
    out = []
    for i in range(days + 1):
        d = (today + timedelta(days=i)).strftime("%Y%m%d")
        data = espn_scoreboard(code, d)
        for event in (data or {}).get("events", []):
            f = espn_fixture(event, league_name)
            if f:
                out.append(f)
    return deduplicate_fixtures(out)

# ============================================================
# SOFASCORE - JOGOS
# ============================================================

SOFA = "https://www.sofascore.com/api/v1"

def sofa_json(path, ttl=180):
    return cached("sofa:" + path, lambda: get(SOFA + path), ttl)

def sofascore_tournament_events(sofa_id, direction="next", pages=5):
    out = []
    for page in range(pages):
        data = sofa_json(f"/unique-tournament/{sofa_id}/events/{direction}/{page}", 180)
        if not isinstance(data, dict):
            continue
        out.extend(data.get("events", []) or [])
        if data.get("hasNextPage") is False:
            break
    return out

def sofascore_scheduled_events(date_value):
    data = sofa_json("/sport/football/scheduled-events/" + date_value, 180)
    return data.get("events", []) if isinstance(data, dict) else []

def sofascore_fixture(event, league_name):
    try:
        ht = event.get("homeTeam") or {}
        at = event.get("awayTeam") or {}
        if not ht.get("name") or not at.get("name"):
            return None
        ts = event.get("startTimestamp")
        dt = datetime.fromtimestamp(int(ts), timezone.utc).isoformat() if ts else None
        status = event.get("status") or {}
        hs = event.get("homeScore") or {}
        aws = event.get("awayScore") or {}
        tournament = event.get("tournament") or {}
        return {
            "fixture": {
                "id": "sofa_" + str(event.get("id")),
                "provider_id": event.get("id"),
                "date": dt,
                "timestamp": ts,
                "status": {"short": status.get("type"), "long": status.get("description") or status.get("type", "")}
            },
            "league": {
                "name": league_name,
                "country": LEAGUES.get(league_name, {}).get("country"),
                "provider_name": tournament.get("name") or league_name,
                "sofa_id": LEAGUES.get(league_name, {}).get("sofa_id")
            },
            "teams": {
                "home": {"id": ht.get("id"), "name": ht.get("name")},
                "away": {"id": at.get("id"), "name": at.get("name")}
            },
            "goals": {
                "home": parse_num(hs.get("current"), 0),
                "away": parse_num(aws.get("current"), 0)
            },
            "_source": "SofaScore"
        }
    except Exception:
        return None

def sofascore_fixtures(league_name, days=7):
    sofa_id = LEAGUES.get(league_name, {}).get("sofa_id")
    if not sofa_id:
        return []
    days = int(clamp(parse_num(days, 7), 1, 14))
    today = brazil_today()
    end = today + timedelta(days=days)
    events = []
    for e in sofascore_tournament_events(sofa_id, "next", 6):
        if sofa_event_date_in_window(e, today, end):
            events.append(e)
    # Fallback diário somente se o torneio não retornou nada.
    if not events:
        for i in range(days + 1):
            for e in sofascore_scheduled_events((today + timedelta(days=i)).isoformat()):
                tid = ((e.get("tournament") or {}).get("uniqueTournament") or {}).get("id")
                if str(tid) == str(sofa_id):
                    events.append(e)
    result = []
    seen = set()
    for e in events:
        if e.get("id") in seen:
            continue
        seen.add(e.get("id"))
        f = sofascore_fixture(e, league_name)
        if f:
            result.append(f)
    return deduplicate_fixtures(result)

def sofa_event_date_in_window(event, start, end):
    d = local_date_from_timestamp(event.get("startTimestamp"))
    return bool(d and start <= d <= end)

# ============================================================
# API FOOTBALL - JOGOS
# ============================================================

def api_football_fixtures(league_name, days=7):
    if not AF_KEY:
        return []
    league = LEAGUES.get(league_name, {})
    lid = league.get("id")
    today = brazil_today()
    end = today + timedelta(days=int(clamp(parse_num(days, 7), 1, 14)))
    data = af("fixtures", {
        "league": lid,
        "season": today.year,
        "from": today.isoformat(),
        "to": end.isoformat()
    }, 300)
    out = []
    for item in (data or {}).get("response", []):
        out.append({
            "fixture": item.get("fixture", {}),
            "league": item.get("league", {}),
            "teams": item.get("teams", {}),
            "goals": item.get("goals", {}),
            "_source": "API-Football"
        })
    return deduplicate_fixtures(out)

# ============================================================
# FLASHCORE COMPLEMENTAR
# ============================================================

def flashscore_fixtures(league_name, days=7):
    if not FLASHSCORE_API_URL:
        return []
    try:
        sep = "&" if "?" in FLASHSCORE_API_URL else "?"
        url = FLASHSCORE_API_URL + sep + urllib.parse.urlencode({
            "league": league_name,
            "country": LEAGUES.get(league_name, {}).get("country"),
            "days": days
        })
        data = get(url, timeout=12)
        raw = data.get("fixtures", []) if isinstance(data, dict) else []
        return [x for x in (normalize_generic_fixture(i, league_name, "Flashscore") for i in raw) if x]
    except Exception as e:
        print("[FLASHSCORE]", e)
        return []

def normalize_generic_fixture(item, league_name, source):
    home = item.get("home") or item.get("homeTeam") or {}
    away = item.get("away") or item.get("awayTeam") or {}
    if isinstance(home, str):
        home = {"name": home}
    if isinstance(away, str):
        away = {"name": away}
    if not home.get("name") or not away.get("name"):
        return None
    date_value = item.get("date") or item.get("startTime")
    parsed = iso_date(date_value)
    return {
        "fixture": {
            "id": f"{source.lower()}_{item.get('id') or item.get('fixture_id') or ''}",
            "provider_id": item.get("id") or item.get("fixture_id"),
            "date": date_value,
            "timestamp": int(parsed.timestamp()) if parsed else None,
            "status": {"short": item.get("status"), "long": item.get("status")}
        },
        "league": {"name": league_name, "country": LEAGUES.get(league_name, {}).get("country")},
        "teams": {
            "home": {"id": home.get("id"), "name": home.get("name") or item.get("home_name")},
            "away": {"id": away.get("id"), "name": away.get("name") or item.get("away_name")}
        },
        "goals": {"home": parse_num(item.get("home_goals"), 0), "away": parse_num(item.get("away_goals"), 0)},
        "_source": source
    }

# ============================================================
# DEDUPLICAÇÃO
# ============================================================

def fixture_identity(f):
    t = f.get("teams", {})
    h = normalize_team_name((t.get("home") or {}).get("name"))
    a = normalize_team_name((t.get("away") or {}).get("name"))
    dt = iso_date((f.get("fixture") or {}).get("date"))
    d = dt.astimezone(BRAZIL_TZ).strftime("%Y-%m-%d") if dt else ""
    return h, a, d

def source_priority(s):
    return {"API-Football": 1, "SofaScore": 2, "ESPN": 3, "Flashscore": 4}.get(s, 99)

def deduplicate_fixtures(fixtures):
    grouped = {}
    for f in fixtures:
        key = fixture_identity(f)
        if not key[0] or not key[1]:
            key = ("id", str((f.get("fixture") or {}).get("id")))
        old = grouped.get(key)
        if old is None or source_priority(f.get("_source")) < source_priority(old.get("_source")):
            grouped[key] = f
    return sorted(grouped.values(), key=lambda x: (x.get("fixture") or {}).get("date") or "")

def get_fixtures(league_name="Brasil", days=7):
    if league_name not in LEAGUES:
        return []
    days = int(clamp(parse_num(days, 7), 1, 14))
    all_f = []
    sources = [
        ("SofaScore", lambda: sofascore_fixtures(league_name, days)),
        ("ESPN", lambda: espn_fixtures(league_name, days)),
        ("API-Football", lambda: api_football_fixtures(league_name, days)),
        ("Flashscore", lambda: flashscore_fixtures(league_name, days)),
    ]
    for name, fn in sources:
        try:
            data = fn()
            print(f"[FIXTURES] {name}: {len(data)}")
            all_f.extend(data)
        except Exception as e:
            print(f"[FIXTURES] {name} erro: {e}")
    today = brazil_today()
    end = today + timedelta(days=days)
    out = []
    for f in deduplicate_fixtures(all_f):
        d = iso_date((f.get("fixture") or {}).get("date"))
        if d:
            local = d.astimezone(BRAZIL_TZ).date()
            if today <= local <= end:
                out.append(f)
    print(f"[FIXTURES] {league_name}: {len(out)} jogos finais")
    return out

# ============================================================
# HISTÓRICO REAL SOFASCORE
# ============================================================

def sofa_team_recent_events(team_id, limit=10):
    if not team_id:
        return []
    # endpoint oficial/estável da camada pública do SofaScore.
    all_events = []
    for page in range(3):
        data = sofa_json(f"/team/{team_id}/events/last/{page}", 900)
        if not isinstance(data, dict):
            continue
        all_events.extend(data.get("events", []) or [])
        if data.get("hasNextPage") is False:
            break
    all_events.sort(key=lambda e: e.get("startTimestamp", 0), reverse=True)
    result = []
    for e in all_events:
        status = str((e.get("status") or {}).get("type") or "").lower()
        # Apenas partidas já encerradas.
        if status not in ("finished", "afterpenalties", "afterextra") and not (e.get("homeScore") and e.get("awayScore")):
            continue
        result.append(e)
        if len(result) >= limit:
            break
    return result

def sofa_event_statistics(event_id):
    if not event_id:
        return {}
    data = sofa_json(f"/event/{event_id}/statistics", 900)
    return data if isinstance(data, dict) else {}

def extract_stat_number(value):
    if isinstance(value, dict):
        for k in ("value", "displayValue", "current"):
            if k in value:
                return parse_num(value[k], None)
    return parse_num(value, None)

def sofa_stats_for_team(event_id, team_id):
    data = sofa_event_statistics(event_id)
    if not data:
        return {}
    # SofaScore normalmente organiza por períodos (ALL, 1ST, 2ND).
    groups = []
    for period in data.get("statistics", []) or []:
        if str(period.get("period", "")).upper() == "ALL":
            groups.append(period)
    if not groups:
        groups = data.get("statistics", []) or []
    wanted = {
        "totalshots": "shots",
        "shots": "shots",
        "shotsontarget": "sot",
        "shotsongoal": "sot",
        "cornerkicks": "corners",
        "corners": "corners",
        "yellowcards": "cards",
        "yellowcard": "cards",
        "possession": "possession",
    }
    result = {}
    for group in groups:
        for item in group.get("groups", []) or []:
            for stat in item.get("statisticsItems", []) or []:
                name = re.sub(r"[^a-z0-9]", "", str(stat.get("name", "")).lower())
                key = wanted.get(name)
                if not key:
                    continue
                # Pode vir como home/away.
                home_val = extract_stat_number(stat.get("home"))
                away_val = extract_stat_number(stat.get("away"))
                # Descobrimos o lado pelo item.
                event = sofa_json(f"/event/{event_id}", 900) or {}
                ev = event.get("event", event)
                home_id = str((ev.get("homeTeam") or {}).get("id"))
                if str(team_id) == home_id:
                    value = home_val
                else:
                    value = away_val
                if value is not None:
                    result[key] = value
    return result

# ============================================================
# PERFIL RECENTE DATA-DRIVEN
# ============================================================

def default_profile():
    return {
        "games": 0,
        "gf": 1.35,
        "ga": 1.25,
        "shots": 12.0,
        "sot": 4.2,
        "corners": 5.0,
        "cards": 2.2,
        "btts_rate": 0.50,
        "over15_rate": 0.75,
        "over25_rate": 0.50,
        "over35_rate": 0.25,
        "wins": 0.33,
        "draws": 0.34,
        "losses": 0.33,
        "clean_sheets": 0.20,
        "scored_rate": 0.70
    }

def recent_profile(team_id, league_name):
    p = default_profile()
    events = sofa_team_recent_events(team_id, 10)
    if not events:
        # fallback ESPN quando o SofaScore não entregar histórico
        events = team_recent_events_espn(team_id, league_name, 8)
        return profile_from_fixtures(events, team_id, p)

    return profile_from_sofa_events(events, team_id, p)

def profile_from_sofa_events(events, team_id, base):
    if not events:
        return base
    gf = ga = 0.0
    shots = []
    sot = []
    corners = []
    cards = []
    wins = draws = losses = 0
    btts = o15 = o25 = o35 = scored = clean = 0
    valid = 0

    for e in events:
        ht = e.get("homeTeam") or {}
        at = e.get("awayTeam") or {}
        hs = e.get("homeScore") or {}
        aws = e.get("awayScore") or {}
        hg = parse_num(hs.get("current"), None)
        ag = parse_num(aws.get("current"), None)
        if hg is None or ag is None:
            continue
        home_side = str(ht.get("id")) == str(team_id)
        mygf, myga = (hg, ag) if home_side else (ag, hg)
        gf += mygf
        ga += myga
        total = mygf + myga
        btts += int(mygf > 0 and myga > 0)
        o15 += int(total >= 2)
        o25 += int(total >= 3)
        o35 += int(total >= 4)
        scored += int(mygf > 0)
        clean += int(myga == 0)
        if mygf > myga: wins += 1
        elif mygf == myga: draws += 1
        else: losses += 1
        valid += 1

        # Estatísticas são consultadas com cache e somente para jogos recentes.
        try:
            st = sofa_stats_for_team(e.get("id"), team_id)
            if st.get("shots") is not None: shots.append(st["shots"])
            if st.get("sot") is not None: sot.append(st["sot"])
            if st.get("corners") is not None: corners.append(st["corners"])
            if st.get("cards") is not None: cards.append(st["cards"])
        except Exception:
            pass

    if not valid:
        return base

    def avg(values, fallback):
        return round(sum(values) / len(values), 2) if values else fallback

    return {
        "games": valid,
        "gf": round(gf / valid, 2),
        "ga": round(ga / valid, 2),
        "shots": avg(shots, base["shots"]),
        "sot": avg(sot, base["sot"]),
        "corners": avg(corners, base["corners"]),
        "cards": avg(cards, base["cards"]),
        "btts_rate": round(btts / valid, 3),
        "over15_rate": round(o15 / valid, 3),
        "over25_rate": round(o25 / valid, 3),
        "over35_rate": round(o35 / valid, 3),
        "wins": round(wins / valid, 3),
        "draws": round(draws / valid, 3),
        "losses": round(losses / valid, 3),
        "clean_sheets": round(clean / valid, 3),
        "scored_rate": round(scored / valid, 3),
    }

def profile_from_fixtures(events, team_id, base):
    if not events:
        return base
    gf = ga = 0
    valid = 0
    wins = draws = losses = btts = o15 = o25 = o35 = scored = clean = 0
    for e in events:
        teams = e.get("teams", {})
        h = teams.get("home", {})
        a = teams.get("away", {})
        g = e.get("goals", {})
        hg = parse_num(g.get("home"), None)
        ag = parse_num(g.get("away"), None)
        if hg is None or ag is None:
            continue
        home_side = str(h.get("id")) == str(team_id)
        mygf, myga = (hg, ag) if home_side else (ag, hg)
        gf += mygf; ga += myga; valid += 1
        btts += int(mygf > 0 and myga > 0)
        total = mygf + myga
        o15 += int(total >= 2); o25 += int(total >= 3); o35 += int(total >= 4)
        scored += int(mygf > 0); clean += int(myga == 0)
        if mygf > myga: wins += 1
        elif mygf == myga: draws += 1
        else: losses += 1
    if not valid:
        return base
    result = dict(base)
    result.update({
        "games": valid,
        "gf": round(gf / valid, 2),
        "ga": round(ga / valid, 2),
        "btts_rate": round(btts / valid, 3),
        "over15_rate": round(o15 / valid, 3),
        "over25_rate": round(o25 / valid, 3),
        "over35_rate": round(o35 / valid, 3),
        "wins": round(wins / valid, 3),
        "draws": round(draws / valid, 3),
        "losses": round(losses / valid, 3),
        "clean_sheets": round(clean / valid, 3),
        "scored_rate": round(scored / valid, 3)
    })
    return result

# ============================================================
# FALLBACK ESPN HISTÓRICO
# ============================================================

def team_recent_events_espn(team_id, league_name, limit=8):
    code = LEAGUES.get(league_name, {}).get("espn")
    if not code or not team_id:
        return []
    today = brazil_today()
    start = today - timedelta(days=120)
    events = []
    # reduz chamadas: percorre apenas os últimos 120 dias e para cedo
    for i in range((today - start).days + 1):
        d = start + timedelta(days=i)
        data = espn_scoreboard(code, d.strftime("%Y%m%d"))
        for event in (data or {}).get("events", []):
            f = espn_fixture(event, league_name)
            if not f:
                continue
            ids = {
                str((f["teams"]["home"] or {}).get("id")),
                str((f["teams"]["away"] or {}).get("id"))
            }
            if str(team_id) in ids:
                status = str(f["fixture"]["status"].get("long", "")).lower()
                if "final" in status or "ended" in status:
                    events.append(f)
    events.sort(key=lambda x: x["fixture"].get("date", ""), reverse=True)
    return events[:limit]

# ============================================================
# MODELO DE PREVISÃO
# ============================================================

LEAGUE_PRIORS = {
    "Brasil": (1.25, 1.02, 9.8, 5.0, 2.7, 23.0, 7.0),
    "Inglaterra": (1.48, 1.22, 10.3, 4.9, 2.4, 25.0, 8.0),
    "Espanha": (1.42, 1.10, 9.6, 5.0, 2.8, 24.0, 8.0),
    "Itália": (1.38, 1.05, 9.4, 4.9, 2.8, 23.0, 7.5),
    "Alemanha": (1.60, 1.28, 10.5, 5.0, 2.6, 25.0, 8.2),
    "França": (1.42, 1.10, 9.7, 4.9, 2.8, 24.0, 7.8),
    "Portugal": (1.40, 1.05, 9.3, 4.8, 2.9, 23.0, 7.5),
}
DEFAULT_PRIOR = (1.35, 1.12, 9.8, 4.9, 2.7, 24.0, 7.5)

def weighted_blend(real_value, prior, weight):
    return real_value * weight + prior * (1 - weight)

def exact_score_predictions(h_lam, a_lam, top_n=6):
    rows = []
    for h in range(8):
        for a in range(8):
            p = poisson_pmf(h, h_lam) * poisson_pmf(a, a_lam)
            rows.append({
                "home_goals": h,
                "away_goals": a,
                "score": f"{h}x{a}",
                "probability": round(p * 100, 2)
            })
    return sorted(rows, key=lambda x: x["probability"], reverse=True)[:top_n]

def build_model(fixture):
    """Modelo data-driven.

    Importante: o mando de campo é apenas um ajuste pequeno. A previsão
    nasce principalmente dos dados recentes das duas equipes e da média
    da competição. Assim, um visitante forte pode ser favorito e jogos
    equilibrados podem apontar para empate.
    """
    teams = fixture.get("teams", {})
    home = teams.get("home", {})
    away = teams.get("away", {})
    league_name = fixture.get("league", {}).get("name", "Brasil")

    hp = recent_profile(home.get("id"), league_name)
    ap = recent_profile(away.get("id"), league_name)

    prior = LEAGUE_PRIORS.get(league_name, DEFAULT_PRIOR)
    lgf, lga, lc, lshots, lcards, ltotalshots, lsot = prior

    sample = min(hp["games"], ap["games"])
    data_weight = clamp(0.42 + sample * 0.045, 0.42, 0.82)

    # -----------------------------------------------------------------
    # FORÇA RELATIVA
    # -----------------------------------------------------------------
    # Em vez de somar um bônus fixo ao mandante, calculamos quanto cada
    # equipe produz/sofre em relação ao padrão da própria competição.
    h_attack_g = weighted_blend(hp["gf"] / max(lgf, .01), 1.0, data_weight)
    a_attack_g = weighted_blend(ap["gf"] / max(lga, .01), 1.0, data_weight)

    # Defesa > 1 significa que sofre mais gols que a média (logo,
    # aumenta o xG do adversário).
    h_def_weak = weighted_blend(hp["ga"] / max(lga, .01), 1.0, data_weight)
    a_def_weak = weighted_blend(ap["ga"] / max(lgf, .01), 1.0, data_weight)

    # Chutes e chutes no alvo entram como confirmação da força ofensiva,
    # mas têm peso menor que gols para não superajustar amostras pequenas.
    h_shot_strength = weighted_blend(hp["shots"] / max(ltotalshots * 0.50, 1.0), 1.0, data_weight)
    a_shot_strength = weighted_blend(ap["shots"] / max(ltotalshots * 0.50, 1.0), 1.0, data_weight)
    h_sot_strength = weighted_blend(hp["sot"] / max(lsot * 0.50, 1.0), 1.0, data_weight)
    a_sot_strength = weighted_blend(ap["sot"] / max(lsot * 0.50, 1.0), 1.0, data_weight)

    h_attack = clamp(
        0.62 * h_attack_g + 0.23 * h_shot_strength + 0.15 * h_sot_strength,
        0.45, 1.75
    )
    a_attack = clamp(
        0.62 * a_attack_g + 0.23 * a_shot_strength + 0.15 * a_sot_strength,
        0.45, 1.75
    )

    # -----------------------------------------------------------------
    # FORMA RECENTE
    # -----------------------------------------------------------------
    # Pontos por jogo e saldo de gols. O efeito é limitado para impedir
    # que 2 ou 3 resultados distorçam completamente a previsão.
    h_ppg = 3 * hp["wins"] + hp["draws"]
    a_ppg = 3 * ap["wins"] + ap["draws"]
    form_delta = clamp(h_ppg - a_ppg, -2.0, 2.0)

    h_form = clamp(1.0 + form_delta * 0.035, 0.93, 1.07)
    a_form = clamp(1.0 - form_delta * 0.035, 0.93, 1.07)

    # -----------------------------------------------------------------
    # EXPECTED GOALS
    # -----------------------------------------------------------------
    # Baseline de gols da competição + ataque próprio + fragilidade
    # defensiva adversária. O mando acrescenta somente ~4% ao xG da casa.
    h_xg = lgf * h_attack * a_def_weak * h_form * 1.04
    a_xg = lga * a_attack * h_def_weak * a_form * 0.99

    h_xg = clamp(h_xg, 0.20, 3.50)
    a_xg = clamp(a_xg, 0.18, 3.20)
    total_xg = h_xg + a_xg

    # -----------------------------------------------------------------
    # RESULTADO POR POISSON
    # -----------------------------------------------------------------
    hw = dr = aw = 0.0
    for h in range(10):
        for a in range(10):
            p = poisson_pmf(h, h_xg) * poisson_pmf(a, a_xg)
            if h > a:
                hw += p
            elif h == a:
                dr += p
            else:
                aw += p

    # Normalização para compensar a pequena massa acima de 9 gols.
    total_result = hw + dr + aw
    if total_result > 0:
        hw /= total_result
        dr /= total_result
        aw /= total_result

    # -----------------------------------------------------------------
    # ESTATÍSTICAS DE JOGO
    # -----------------------------------------------------------------
    corners = clamp(
        weighted_blend(hp["corners"] + ap["corners"], lc * 2, data_weight),
        5.0, 15.5
    )
    cards = clamp(
        weighted_blend(hp["cards"] + ap["cards"], lcards * 2, data_weight),
        1.0, 10.0
    )
    shots = clamp(
        weighted_blend(hp["shots"] + ap["shots"], ltotalshots, data_weight),
        12.0, 40.0
    )
    sot = clamp(
        weighted_blend(hp["sot"] + ap["sot"], lsot, data_weight),
        2.0, 16.0
    )

    # BTTS combina a probabilidade matemática com o comportamento real.
    btts_model = poisson_btts(h_xg, a_xg)
    btts_history = (hp["btts_rate"] + ap["btts_rate"]) / 2
    btts = clamp(
        0.62 * btts_model + 0.38 * btts_history,
        0.03, 0.97
    )

    markets = []

    def add(key, label, probability):
        probability = clamp(probability, 0.01, 0.99)
        markets.append({
            "key": key,
            "label": label,
            "probability": round(probability * 100, 2),
            "fair_odds": round(1 / probability, 2)
        })

    add("home_win", f"{home.get('name')} vencer", hw)
    add("draw", "Empate", dr)
    add("away_win", f"{away.get('name')} vencer", aw)
    add("double_chance_1x", "Casa ou empate", hw + dr)
    add("double_chance_x2", "Empate ou visitante", dr + aw)
    add("double_chance_12", "Casa ou visitante", hw + aw)

    add("over_0_5", "Mais de 0.5 gols", poisson_over(total_xg, .5))
    add("over_1_5", "Mais de 1.5 gols", poisson_over(total_xg, 1.5))
    add("over_2_5", "Mais de 2.5 gols", poisson_over(total_xg, 2.5))
    add("over_3_5", "Mais de 3.5 gols", poisson_over(total_xg, 3.5))
    add("under_2_5", "Menos de 2.5 gols", poisson_under(total_xg, 2.5))
    add("btts", "Ambas marcam", btts)

    for line in (6.5, 7.5, 8.5, 9.5):
        add(f"corners_over_{str(line).replace('.', '_')}", f"Mais de {line} escanteios", poisson_over(corners, line))
    for line in (2.5, 3.5, 4.5):
        add(f"cards_over_{str(line).replace('.', '_')}", f"Mais de {line} cartões", poisson_over(cards, line))
    for line in (18.5, 21.5):
        add(f"shots_over_{str(line).replace('.', '_')}", f"Mais de {line} chutes", poisson_over(shots, line))
    for line in (3.5, 5.5):
        add(f"shots_on_target_over_{str(line).replace('.', '_')}", f"Mais de {line} chutes no gol", poisson_over(sot, line))

    # Distribuição aproximada de SOT por equipe conforme o xG relativo.
    home_share = h_xg / max(total_xg, .01)
    away_share = a_xg / max(total_xg, .01)
    home_sot = clamp(hp["sot"] * 0.65 + sot * 0.35 * home_share * 2, 1.0, 8.0)
    away_sot = clamp(ap["sot"] * 0.65 + sot * 0.35 * away_share * 2, 1.0, 8.0)
    add("home_shots_on_target_over_2_5", f"{home.get('name')} +2.5 chutes no gol", poisson_over(home_sot, 2.5))
    add("away_shots_on_target_over_2_5", f"{away.get('name')} +2.5 chutes no gol", poisson_over(away_sot, 2.5))

    scores = exact_score_predictions(h_xg, a_xg)

    # -----------------------------------------------------------------
    # CONFIANÇA
    # -----------------------------------------------------------------
    # Confiança mede qualidade/consistência da amostra, não "chance de green".
    evidence = clamp(42 + sample * 4 + data_weight * 18, 46, 84)
    separation = abs(hw - aw)
    top_prob = max(hw, dr, aw, btts, poisson_over(total_xg, 1.5))
    confidence = round(
        clamp(evidence * 0.62 + top_prob * 100 * 0.25 + separation * 100 * 0.13, 48, 90),
        1
    )

    markets.sort(key=lambda x: x["probability"], reverse=True)

    probabilities = {
        "home": round(hw * 100, 2),
        "draw": round(dr * 100, 2),
        "away": round(aw * 100, 2)
    }

    props = {
        "over_1_5": round(poisson_over(total_xg, 1.5) * 100, 2),
        "over_2_5": round(poisson_over(total_xg, 2.5) * 100, 2),
        "btts": round(btts * 100, 2),
        "corners_over_8_5": round(poisson_over(corners, 8.5) * 100, 2),
        "cards_over_3_5": round(poisson_over(cards, 3.5) * 100, 2),
        "shots_on_target_over_3_5": round(poisson_over(sot, 3.5) * 100, 2)
    }

    # Só recomendamos mercados com boa probabilidade e que tenham alguma
    # robustez estatística. Não tratamos 1X2 como obrigatório.
    best = []
    for m in markets:
        p = m["probability"]
        if p >= 72:
            best.append({
                **m,
                "rating": "forte" if p >= 80 else "boa"
            })
    best = best[:8]

    favorite_key = max(
        (("home", hw), ("draw", dr), ("away", aw)),
        key=lambda x: x[1]
    )[0]
    favorite_name = {
        "home": home.get("name"),
        "draw": "Empate",
        "away": away.get("name")
    }[favorite_key]

    return {
        "home_xg": round(h_xg, 2),
        "away_xg": round(a_xg, 2),
        "expected_goals": round(total_xg, 2),
        "expected_corners": round(corners, 2),
        "expected_cards": round(cards, 2),
        "expected_shots": round(shots, 2),
        "expected_shots_on_target": round(sot, 2),
        "result_probability": probabilities,
        "probabilities": probabilities,
        "profiles": {"home": hp, "away": ap},
        "exact_scores": scores,
        "most_likely_score": scores[0] if scores else None,
        "favorite": {"key": favorite_key, "name": favorite_name, "probability": round(max(hw, dr, aw) * 100, 2)},
        "markets": markets,
        "top_markets": markets[:10],
        "props": props,
        "metrics": {
            "sample_games": sample,
            "data_weight": round(data_weight, 3),
            "home_advantage_factor": 1.04,
            "model_type": "dados recentes + força relativa + gols/chutes + Poisson + média da liga"
        },
        "best_bets": best,
        "confidence": confidence,
        "model": VERSION
    }

# ============================================================
# ODDS REAIS E VALOR
# ============================================================

def event_matches(fixture, event):
    t = fixture.get("teams", {})
    h = normalize_team_name((t.get("home") or {}).get("name"))
    a = normalize_team_name((t.get("away") or {}).get("name"))
    eh = normalize_team_name(event.get("home_team"))
    ea = normalize_team_name(event.get("away_team"))
    return bool(h and a and ((h == eh and a == ea) or ((h in eh or eh in h) and (a in ea or ea in a))))

def external_odds(fixture):
    league_name = fixture.get("league", {}).get("name")
    sport = LEAGUES.get(league_name, {}).get("odds")
    if not ODDS_KEY or not sport:
        return []
    result = []
    for event in odds_api(sport):
        if not event_matches(fixture, event):
            continue
        for bookmaker in event.get("bookmakers", []):
            for market in bookmaker.get("markets", []):
                for outcome in market.get("outcomes", []):
                    price = parse_num(outcome.get("price"), 0)
                    if price > 1:
                        result.append({
                            "source": "The Odds API",
                            "bookmaker": bookmaker.get("title"),
                            "market": market.get("key"),
                            "name": outcome.get("name"),
                            "point": outcome.get("point"),
                            "price": round(price, 2),
                            "implied_probability": round(100 / price, 2)
                        })
        break
    return result

def enrich_value(model_markets, real_odds):
    out = []
    for odd in real_odds:
        p = odd.get("price")
        if not p:
            continue
        implied = 100 / p
        name = str(odd.get("name") or "").lower()
        matches = [m for m in model_markets if m["label"].lower() == name]
        if matches:
            odd["model_probability"] = matches[0]["probability"]
            odd["edge"] = round(matches[0]["probability"] - implied, 2)
        out.append(odd)
    return sorted(out, key=lambda x: x.get("edge", -999), reverse=True)

# ============================================================
# ANÁLISE
# ============================================================

def analyze_fixture(fixture):
    model = build_model(fixture)
    real_odds = enrich_value(model["markets"], external_odds(fixture))
    teams = fixture.get("teams", {})
    result = {
        "fixture": fixture,
        "prediction": None,
        "model": model,
        "markets": model["markets"],
        "real_odds": real_odds,
        "external_markets": real_odds,
        "source": fixture.get("_source"),
        "home_team": (teams.get("home") or {}).get("name"),
        "away_team": (teams.get("away") or {}).get("name"),
        "generated_at": brazil_now().isoformat()
    }
    # Opcional: previsão externa da API-Football, sem depender dela.
    fid = (fixture.get("fixture") or {}).get("id")
    if AF_KEY and fid and not str(fid).startswith("sofa_"):
        try:
            data = af("predictions", {"fixture": fid}, 300)
            response = (data or {}).get("response", [])
            result["prediction"] = response[0] if response else None
        except Exception:
            pass
    return result

# ============================================================
# DEBUG / HISTÓRICO / CUPOM
# ============================================================

def debug_fixtures(league_name, days=7):
    fixtures = get_fixtures(league_name, days)
    counts = {}
    for f in fixtures:
        s = f.get("_source", "unknown")
        counts[s] = counts.get(s, 0) + 1
    return {
        "ok": True,
        "version": VERSION,
        "league": league_name,
        "today_brazil": brazil_today().isoformat(),
        "days": int(days),
        "api_football_key": bool(AF_KEY),
        "odds_key": bool(ODDS_KEY),
        "flashscore_configured": bool(FLASHSCORE_API_URL),
        "final": {"count": len(fixtures), "sources": counts}
    }

def read_history():
    try:
        if not Path(DATA_FILE).exists():
            return []
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []

def write_history(data):
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("[HISTORY]", e)

def build_coupon(items):
    selections = []
    combined = 1.0
    for item in items:
        price = parse_num(item.get("price"), 0)
        if price <= 1:
            price = parse_num(item.get("fair_odds"), 0)
        if price <= 1:
            continue
        combined *= price
        selections.append({
            "fixture": item.get("fixture"),
            "market": item.get("market"),
            "label": item.get("label"),
            "price": round(price, 2)
        })
    return {"selections": selections, "combined_odds": round(combined, 2), "count": len(selections)}

# ============================================================
# HTTP
# ============================================================

class Handler(SimpleHTTPRequestHandler):
    def send_json(self, data, status=200):
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def read_body(self):
        try:
            n = int(self.headers.get("Content-Length", 0))
            return json.loads(self.rfile.read(n).decode("utf-8")) if n else {}
        except Exception:
            return {}

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        params = urllib.parse.parse_qs(parsed.query)

        if path == "/api/health":
            return self.send_json({
                "ok": True,
                "api_football": bool(AF_KEY),
                "odds_api": bool(ODDS_KEY),
                "flashscore": bool(FLASHSCORE_API_URL),
                "leagues": len(LEAGUES),
                "cache_ttl": CACHE_TTL,
                "version": VERSION,
                "fixtures_sources": ["SofaScore", "ESPN", "API-Football", "Flashscore"],
                "prediction_sources": ["SofaScore historical data", "ESPN fallback", "API-Football optional"],
                "today_brazil": brazil_today().isoformat(),
                "server_time": brazil_now().isoformat()
            })

        if path == "/api/leagues":
            return self.send_json([
                {
                    "name": n,
                    "country": x.get("country"),
                    "id": x.get("id"),
                    "sofa_id": x.get("sofa_id"),
                    "odds": bool(x.get("odds"))
                } for n, x in LEAGUES.items()
            ])

        if path in ("/api/debug/fixtures", "/api/fixtures"):
            league = params.get("league", ["Brasil"])[0]
            days = int(clamp(parse_num(params.get("days", ["7"])[0], 7), 1, 14))
            fixtures = get_fixtures(league, days)
            counts = {}
            for f in fixtures:
                s = f.get("_source", "unknown")
                counts[s] = counts.get(s, 0) + 1
            if path == "/api/debug/fixtures":
                return self.send_json({
                    "ok": True,
                    "version": VERSION,
                    "league": league,
                    "days": days,
                    "today_brazil": brazil_today().isoformat(),
                    "final": {"count": len(fixtures), "sources": counts}
                })
            return self.send_json({
                "ok": True,
                "version": VERSION,
                "league": league,
                "days": days,
                "fixtures": fixtures,
                "count": len(fixtures),
                "source": fixtures[0].get("_source") if fixtures else None,
                "sources": counts,
                "today_brazil": brazil_today().isoformat()
            })

        if path == "/api/analyze":
            league = params.get("league", ["Brasil"])[0]
            days = int(clamp(parse_num(params.get("days", ["7"])[0], 7), 1, 14))
            fixtures = get_fixtures(league, days)
            games = []
            # Paralelismo evita que vários jogos façam o navegador ficar esperando um por um.
            with ThreadPoolExecutor(max_workers=5) as pool:
                futures = {pool.submit(analyze_fixture, f): f for f in fixtures}
                for future in as_completed(futures):
                    f = futures[future]
                    try:
                        games.append(future.result())
                    except Exception as e:
                        games.append({"fixture": f, "error": str(e)})
            games.sort(key=lambda x: (x.get("fixture", {}).get("fixture", {}).get("date") or ""))
            return self.send_json({
                "ok": True,
                "version": VERSION,
                "league": league,
                "days": days,
                "games": games,
                "fixtures": fixtures,
                "count": len(games),
                "today_brazil": brazil_today().isoformat()
            })

        if path == "/api/prediction":
            fid = params.get("fixture", [None])[0]
            if not fid:
                return self.send_json({"ok": False, "error": "fixture obrigatório"}, 400)
            if str(fid).startswith("sofa_"):
                return self.send_json({"ok": False, "response": [], "error": "Jogo encontrado pelo SofaScore; previsão própria está em /api/analyze."})
            data = af("predictions", {"fixture": fid}, 300)
            return self.send_json(data or {"response": []})

        if path == "/api/odds":
            sport = params.get("sport", ["soccer_epl"])[0]
            return self.send_json(odds_api(sport))

        if path == "/api/history":
            return self.send_json(read_history())

        return super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        body = self.read_body()

        if path == "/api/coupon/build":
            return self.send_json(build_coupon(body.get("items", [])))

        if path in ("/api/coupon/save", "/api/result"):
            history = read_history()
            record = {
                "type": "coupon" if path.endswith("build") is False and path.endswith("save") else "result",
                "created_at": brazil_now().isoformat(),
                "data": body
            }
            if path == "/api/result":
                record["type"] = "result"
            history.append(record)
            write_history(history[-500:])
            return self.send_json({"ok": True, "saved": record})

        return self.send_json({"ok": False, "error": "rota não encontrada"}, 404)

# ============================================================
# START
# ============================================================

if __name__ == "__main__":
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print("=" * 60)
    print(f"{VERSION} iniciado | porta={PORT} | Brasil={brazil_today()}")
    print("Fixtures: SofaScore + ESPN + API-Football + Flashscore opcional")
    print("Modelo: histórico real + forma + Poisson + baseline da liga")
    print("Escalações/lesões/notícias: DESATIVADOS")
    print(f"Ligas principais: {len(LEAGUES)}")
    print("=" * 60)
    server.serve_forever()
