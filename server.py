import os, json, urllib.request, urllib.parse, datetime, sqlite3, time, re
from pathlib import Path
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler

PORT=int(os.getenv('PORT','8787'))
AF_KEY=os.getenv('API_FOOTBALL_KEY','').strip()
ODDS_KEY=os.getenv('ODDS_API_KEY','').strip()
DB='marques_pro.db'
CACHE_TTL=int(os.getenv('CACHE_TTL','900'))
CACHE={}

LEAGUES={'Brasil':71,'Inglaterra':39,'Espanha':140,'Itália':135,'Alemanha':78,'França':61}
SPORT_KEYS={'Brasil':'soccer_brazil_campeonato','Inglaterra':'soccer_epl','Espanha':'soccer_spain_la_liga','Itália':'soccer_italy_serie_a','Alemanha':'soccer_germany_bundesliga','França':'soccer_france_ligue_one'}


DATA_FILE='marques_pro_history.json'

def load_data():
    try:
        return json.loads(Path(DATA_FILE).read_text(encoding='utf-8'))
    except Exception:
        return {'predictions': [], 'coupons': [], 'next_prediction_id': 1, 'next_coupon_id': 1}

def save_data(data):
    Path(DATA_FILE).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def get(url,key=None):
    h={'x-apisports-key':key} if key else {}
    req=urllib.request.Request(url,headers=h)
    with urllib.request.urlopen(req,timeout=20) as r: return json.loads(r.read().decode())


def cached(url,key=None):
    now=time.time(); hit=CACHE.get(url)
    if hit and now-hit[0]<CACHE_TTL: return hit[1]
    data=get(url,key); CACHE[url]=(now,data); return data


def af(path,params):
    if not AF_KEY: return {'error':'API_FOOTBALL_KEY não configurada','response':[]}
    q=urllib.parse.urlencode(params); return cached('https://v3.football.api-sports.io/'+path+'?'+q,AF_KEY)


def odds(sport):
    if not ODDS_KEY: return {'error':'ODDS_API_KEY não configurada','matches':[]}
    q=urllib.parse.urlencode({'regions':'eu','markets':'h2h,totals','oddsFormat':'decimal','apiKey':ODDS_KEY})
    return cached('https://api.the-odds-api.com/v4/sports/'+sport+'/odds?'+q)


def norm(s):
    s=s.lower()
    s=re.sub(r'[^a-z0-9áàâãéêíóôõúüç ]',' ',s)
    return re.sub(r'\s+',' ',s).strip()


def parse_pct(v):
    try: return float(str(v).replace('%','').replace(',','.'))/100
    except: return 0.0


def match_external(f, events):
    fh=norm(f['teams']['home']['name']); fa=norm(f['teams']['away']['name'])
    ft=datetime.datetime.fromisoformat(f['fixture']['date'].replace('Z','+00:00')).timestamp()
    best=None; bestscore=999999
    for e in events:
        eh=norm(e.get('home_team','')); ea=norm(e.get('away_team',''))
        if not eh or not ea: continue
        names=(eh in fh or fh in eh) and (ea in fa or fa in ea)
        if not names: continue
        try: et=datetime.datetime.fromisoformat(e['commence_time'].replace('Z','+00:00')).timestamp()
        except: et=ft
        score=abs(ft-et)
        if score<bestscore and score<=8*3600: best=e; bestscore=score
    return best


def external_markets(f, league):
    if not ODDS_KEY: return []
    data=odds(SPORT_KEYS.get(league,'')); events=data if isinstance(data,list) else []
    e=match_external(f,events)
    if not e: return []
    out=[]
    for bm in e.get('bookmakers',[]):
        for m in bm.get('markets',[]):
            for o in m.get('outcomes',[]):
                if m.get('key') in ('h2h','totals'):
                    out.append({'bookmaker':bm.get('title'), 'market':m.get('key'), 'name':o.get('name'), 'price':float(o.get('price'))})
    return out


def analyze_fixture(f, league):
    pred=af('predictions',{'fixture':f['fixture']['id']})
    p=(pred.get('response') or [{}])[0]
    return {'prediction':p,'markets':external_markets(f,league)}


def save_coupon(league,target,sel,total_odd):
    data=load_data(); now=datetime.datetime.now(datetime.timezone.utc).isoformat()
    cid=data['next_coupon_id']; data['next_coupon_id']+=1
    avg_prob=sum(x['p'] for x in sel)/len(sel) if sel else 0
    avg_edge=sum(x['edge'] for x in sel)/len(sel) if sel else 0
    data['coupons'].append([cid,now,league,target,total_odd,len(sel),avg_prob,avg_edge,'pending'])
    for x in sel:
        pid=data['next_prediction_id']; data['next_prediction_id']+=1
        data['predictions'].append([pid,now,x.get('fixture'),x.get('home',''),x.get('away',''),league,x.get('market',''),x.get('odd',0),x.get('p',0),x.get('edge',0),x.get('score',0),'pending'])
    save_data(data); return cid


class Handler(SimpleHTTPRequestHandler):
    def j(self,obj,status=200):
        raw=json.dumps(obj,ensure_ascii=False).encode(); self.send_response(status)
        self.send_header('Content-Type','application/json; charset=utf-8'); self.send_header('Access-Control-Allow-Origin','*'); self.send_header('Cache-Control','no-store'); self.end_headers(); self.wfile.write(raw)
    def body(self):
        n=int(self.headers.get('Content-Length','0')); return json.loads(self.rfile.read(n).decode() or '{}')
    def do_OPTIONS(self): self.send_response(204); self.send_header('Access-Control-Allow-Origin','*'); self.send_header('Access-Control-Allow-Headers','Content-Type'); self.end_headers()
    def do_POST(self):
        u=urllib.parse.urlparse(self.path)
        try:
            if u.path=='/api/coupon/save':
                b=self.body(); cid=save_coupon(b.get('league',''),float(b.get('target',0)),b.get('selections',[]),float(b.get('total_odd',0))); return self.j({'ok':True,'id':cid})
            if u.path=='/api/result':
                b=self.body(); data=load_data(); pid=int(b['id']); result=b.get('result','pending');
                for row in data['predictions']:
                    if int(row[0])==pid: row[11]=result; break
                save_data(data); return self.j({'ok':True})
            self.j({'error':'rota não encontrada'},404)
        except Exception as e: self.j({'error':str(e)},500)
    def do_GET(self):
        u=urllib.parse.urlparse(self.path); q=urllib.parse.parse_qs(u.query)
        if u.path=='/api/health': return self.j({'ok':True,'api_football':bool(AF_KEY),'odds_api':bool(ODDS_KEY),'cache_ttl':CACHE_TTL})
        if u.path=='/api/leagues': return self.j(LEAGUES)
        if u.path=='/api/fixtures':
            league=q.get('league',['Brasil'])[0]; days=max(0,min(int(q.get('days',['1'])[0]),7)); today=datetime.date.today(); lid=LEAGUES.get(league)
            if not lid: return self.j({'error':'Liga inválida','response':[]},400)
            return self.j(af('fixtures',{'league':lid,'season':today.year,'from':str(today),'to':str(today+datetime.timedelta(days=days))}))
        if u.path=='/api/prediction': return self.j(analyze_fixture({'fixture':{'id':int(q['fixture'][0]),'date':q.get('date',[datetime.datetime.now(datetime.timezone.utc).isoformat()])[0],'teams':{'home':{'name':q.get('home',[''])[0]},'away':{'name':q.get('away',[''])[0]}}},'league':{'name':q.get('league',[''])[0]}},q.get('league',['Brasil'])[0]))
        if u.path=='/api/analyze':
            league=q.get('league',['Brasil'])[0]; days=max(0,min(int(q.get('days',['1'])[0]),3)); fx=af('fixtures',{'league':LEAGUES.get(league,71),'season':datetime.date.today().year,'from':str(datetime.date.today()),'to':str(datetime.date.today()+datetime.timedelta(days=days))}).get('response',[])
            out=[]
            for f in fx[:30]:
                try: out.append({'fixture':f,'data':analyze_fixture(f,league)})
                except Exception as e: out.append({'fixture':f,'data':{'error':str(e)}})
            return self.j({'league':league,'fixtures':out})
        if u.path=='/api/odds':
            league=q.get('league',['Brasil'])[0]; return self.j({'league':league,**odds(SPORT_KEYS.get(league,''))} if isinstance(odds(SPORT_KEYS.get(league,'')),dict) else {'league':league,'matches':odds(SPORT_KEYS.get(league,''))})
        if u.path=='/api/history':
            data=load_data(); return self.j({'rows':list(reversed(data['predictions'][-200:])), 'coupons':list(reversed(data['coupons'][-50:]))})
        self.path='index.html'; return super().do_GET()

print('Marques Pro v11: http://127.0.0.1:'+str(PORT))
print('Configure API_FOOTBALL_KEY para jogos reais. Odds de bookmaker não são necessárias.')
ThreadingHTTPServer(('0.0.0.0',PORT),Handler).serve_forever()
