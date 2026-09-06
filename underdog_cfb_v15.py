from __future__ import annotations

import math,re,time
from typing import Any,Dict,List,Tuple
import requests

UNDERDOG_URLS=[
'https://api.underdogfantasy.com/beta/v6/over_under_lines?sport_id=ncaaf',
'https://api.underdogfantasy.com/beta/v6/over_under_lines?sport_id=NCAAF',
'https://api.underdogfantasy.com/beta/v6/over_under_lines?sport_id=cfb',
'https://api.underdogfantasy.com/beta/v6/over_under_lines?sport_id=CFB',
'https://api.underdogfantasy.com/beta/v6/over_under_lines?sport_id=college-football',
'https://api.underdogfantasy.com/beta/v6/over_under_lines',
'https://api.underdogfantasy.com/beta/v5/over_under_lines',
'https://api.underdogfantasy.com/beta/v4/over_under_lines',
'https://api.underdogfantasy.com/beta/v3/over_under_lines',
'https://api.underdogfantasy.com/beta/v2/over_under_lines',
'https://api.underdogfantasy.com/beta/v1/over_under_lines']

PROP_ALIASES={
'Passing Yards':['passing yards','pass yards','pass yds'],'Pass Attempts':['pass attempts','passing attempts'],'Completions':['completions','passing completions'],
'Passing TDs':['passing tds','passing touchdowns','pass tds'],'Interceptions':['interceptions','passing interceptions','ints'],
'Rushing Yards':['rushing yards','rush yards','rush yds'],'Rush Attempts':['rush attempts','rushing attempts','carries'],
'Receiving Yards':['receiving yards','rec yards','receiving yds','rec yds'],'Receptions':['receptions','catches'],
'Pass + Rush Yards':['pass + rush yards','passing + rushing yards','pass rush yards'],'Rush + Rec Yards':['rush + rec yards','rushing + receiving yards','rush rec yards'],
'Rush + Rec TDs':['rush + rec tds','rushing + receiving tds','rush + rec touchdowns','rushing + receiving touchdowns'],'Total TDs':['total tds','total touchdowns','pass + rush + rec tds'],
'Fantasy Points':['fantasy points','fantasy score'],'Longest Reception':['longest reception','longest catch'],'Longest Rush':['longest rush','longest carry'],'Longest Completion':['longest completion','longest pass completion'],
'Kicking Points':['kicking points','kicker points'],'Field Goals Made':['field goals made','fg made','made field goals']}

def _norm(x):return re.sub(r'[^a-z0-9]','',str(x or '').lower())
def _num(v,d=None):
    try:
        x=float(v);return x if math.isfinite(x) else d
    except:return d

def _blob(x):
    if isinstance(x,dict):return ' '.join(_blob(v) for v in x.values()).lower()
    if isinstance(x,list):return ' '.join(_blob(v) for v in x).lower()
    return str(x or '').lower()
def _canon(label):
    text=re.sub(r'\s+',' ',str(label or '').strip().lower())
    for canon,als in PROP_ALIASES.items():
        if any(a in text for a in als):return canon
    return None
def _cfb_blob(*objs):
    b=' '+ ' '.join(_blob(o) for o in objs)+' '
    if any(x in b for x in [' nfl ','nfl_','national football league','cfl','xfl','usfl']):return False
    return any(x in b for x in ['ncaaf','ncaa football','college football','college-football','cfb','football_fbs',' fbs '])
def _pname(p):
    if not isinstance(p,dict):return ''
    for k in ['display_name','full_name','player_name','name']:
        if isinstance(p.get(k),str) and p[k].strip():return p[k].strip()
    return (str(p.get('first_name') or '')+' '+str(p.get('last_name') or '')).strip()
def _team(*objs):
    for o in objs:
        if not isinstance(o,dict):continue
        for k in ['team_abbr','team','team_code','team_name','school','abbreviation','name']:
            if isinstance(o.get(k),str) and o[k].strip():return o[k].strip()
    return ''
def _game_names(g):
    if not isinstance(g,dict):return '','',''
    away=str(g.get('away_team') or g.get('away_team_name') or g.get('away') or '').strip(); home=str(g.get('home_team') or g.get('home_team_name') or g.get('home') or '').strip()
    full=str(g.get('full_team_names_title') or '').strip()
    title=str(g.get('title') or g.get('abbreviated_title') or g.get('matchup') or g.get('name') or '').strip()
    source=full or title
    if (not away or not home) and source:
        parts=re.split(r'\s+(?:@|at|vs\.?|v\.)\s+',source,maxsplit=1,flags=re.I)
        if len(parts)==2:away=away or parts[0].strip();home=home or parts[1].strip()
    return away,home,f'{away} @ {home}' if away and home else source

def _line_row(name,team,prop,line,source_url,game=None,line_obj=None,event_id=''):
    game=game or {}; line_obj=line_obj or {}; away,home,matchup=_game_names(game)
    return {'player':name,'team':team,'prop':prop,'line':float(line),'side':'AUTO','source':'Underdog','source_url':source_url,'away':away,'home':home,'matchup':matchup,'event_id':str(event_id or game.get('id') or ''),'underdog_id':str(line_obj.get('id') or ''),'line_status':line_obj.get('status') or '','scheduled_at':game.get('scheduled_at') or game.get('starts_at') or game.get('start_time')}

def _native(data,url):
    if not isinstance(data,dict):return []
    lines=data.get('over_under_lines')
    if not isinstance(lines,list):return []
    players={str(x.get('id')):x for x in data.get('players',[]) if isinstance(x,dict) and x.get('id') is not None}; apps={str(x.get('id')):x for x in data.get('appearances',[]) if isinstance(x,dict) and x.get('id') is not None}; games={str(x.get('id')):x for x in data.get('games',[]) if isinstance(x,dict) and x.get('id') is not None}; teams={str(x.get('id')):x for x in data.get('teams',[]) if isinstance(x,dict) and x.get('id') is not None}; out=[]
    for lo in lines:
        if not isinstance(lo,dict):continue
        ou=lo.get('over_under') if isinstance(lo.get('over_under'),dict) else {}; stat=ou.get('appearance_stat') if isinstance(ou.get('appearance_stat'),dict) else {}
        prop=_canon(stat.get('display_stat') or stat.get('stat') or stat.get('name') or ou.get('title') or lo.get('title') or lo.get('stat') or lo.get('stat_name'))
        line=_num(lo.get('stat_value',lo.get('line',lo.get('value'))))
        if not prop or line is None:continue
        aid=stat.get('appearance_id') or ou.get('appearance_id') or lo.get('appearance_id'); app=apps.get(str(aid),{}) if aid is not None else {}
        pid=app.get('player_id') or stat.get('player_id') or ou.get('player_id') or lo.get('player_id'); p=players.get(str(pid),{}) if pid is not None else {}
        name=_pname(p) or str(lo.get('player_name') or lo.get('display_name') or '').strip()
        if not name:
            for o in lo.get('options',[]) if isinstance(lo.get('options'),list) else []:
                if isinstance(o,dict) and o.get('selection_header'):name=str(o['selection_header']).strip();break
        if not name:continue
        mid=app.get('match_id') or stat.get('match_id') or ou.get('match_id') or lo.get('match_id') or lo.get('game_id'); game=games.get(str(mid),{}) if mid is not None else {}
        if not _cfb_blob(lo,ou,stat,app,p,game) and 'sport_id=' not in url:continue
        tid=str(app.get('team_id') or p.get('team_id') or '')
        ga,gh,_gm=_game_names(game)
        if tid and tid==str(game.get('away_team_id') or ''): t=ga
        elif tid and tid==str(game.get('home_team_id') or ''): t=gh
        else: t=_team(app,p,teams.get(tid,{}) if tid else {})
        row=_line_row(name,t,prop,line,url,game,lo,mid)
        row['team_id']=tid
        row['position']=str(p.get('position_name') or p.get('position_display_name') or '')
        row['player_image_url']=str(p.get('image_url') or p.get('light_image_url') or '')
        out.append(row)
    return out

def _jsonapi(data,url):
    if not isinstance(data,dict) or not isinstance(data.get('data'),list):return []
    included=data.get('included') if isinstance(data.get('included'),list) else []
    idx={}
    for x in included:
        if isinstance(x,dict):idx[(str(x.get('type') or ''),str(x.get('id') or ''))]=x
    def rel(obj,name):
        try:
            d=obj.get('relationships',{}).get(name,{}).get('data')
            if isinstance(d,dict):return idx.get((str(d.get('type') or ''),str(d.get('id') or '')),{})
        except:pass
        return {}
    out=[]
    for obj in data['data']:
        if not isinstance(obj,dict):continue
        a=obj.get('attributes') if isinstance(obj.get('attributes'),dict) else {}
        ou=rel(obj,'over_under'); oua=ou.get('attributes',{}) if isinstance(ou,dict) else {}; app=rel(ou,'appearance') or rel(obj,'appearance'); player=rel(app,'player') or rel(ou,'player') or rel(obj,'player'); game=rel(app,'match') or rel(app,'game') or rel(ou,'match') or rel(obj,'match') or rel(obj,'game'); team=rel(app,'team') or rel(player,'team')
        pa=player.get('attributes',{}) if isinstance(player,dict) else {}; aa=app.get('attributes',{}) if isinstance(app,dict) else {}; ga=game.get('attributes',{}) if isinstance(game,dict) else {}; ta=team.get('attributes',{}) if isinstance(team,dict) else {}
        prop=_canon(a.get('display_stat') or a.get('stat') or a.get('stat_name') or oua.get('title') or oua.get('stat') or aa.get('stat')); line=_num(a.get('stat_value',a.get('line',a.get('value',oua.get('stat_value')))))
        name=_pname(pa) or _pname(aa) or str(a.get('player_name') or '').strip()
        if not prop or line is None or not name:continue
        if not _cfb_blob(a,oua,aa,pa,ga,ta) and 'sport_id=' not in url:continue
        out.append(_line_row(name,_team(aa,pa,ta),prop,line,url,ga,a,game.get('id') if isinstance(game,dict) else ''))
    return out

def _recursive(data,url):
    out=[]
    def walk(x,parents=None):
        parents=parents or []
        if isinstance(x,dict):
            prop=_canon(x.get('display_stat') or x.get('stat') or x.get('stat_name') or x.get('market') or x.get('title')); line=_num(x.get('stat_value',x.get('line',x.get('value',x.get('point')))))
            name=str(x.get('player_name') or x.get('display_name') or x.get('athlete_name') or '').strip()
            if prop and line is not None and name and (_cfb_blob(x,*parents) or 'sport_id=' in url):out.append(_line_row(name,_team(x),prop,line,url,{},x,x.get('game_id') or x.get('match_id') or ''))
            for v in x.values():walk(v,(parents+[x])[-2:])
        elif isinstance(x,list):
            for v in x:walk(v,parents)
    walk(data);return out

def _dedupe(rows):
    d={}
    for r in rows:
        if not _norm(r.get('player')) or not r.get('prop') or _num(r.get('line'),0)<=0:continue
        k=(_norm(r.get('player')),r.get('prop'),float(r.get('line')),str(r.get('event_id') or r.get('matchup') or ''))
        d[k]=r
    return list(d.values())

def fetch_underdog_cfb_props(force=False)->Tuple[List[Dict[str,Any]],List[Dict[str,Any]]]:
    headers={'User-Agent':'Mozilla/5.0 (iPhone; CPU iPhone OS 18_7 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.6 Mobile/15E148 Safari/604.1','Accept':'application/json,text/plain,*/*','Referer':'https://underdogfantasy.com/','Origin':'https://underdogfantasy.com','Cache-Control':'no-cache','Pragma':'no-cache'}
    rows=[];debug=[];start=time.time()
    for idx,url in enumerate(UNDERDOG_URLS):
        try:
            r=requests.get(url,headers=headers,timeout=(4,10)); ct=r.headers.get('content-type',''); r.raise_for_status(); j=r.json(); n=_native(j,url); ja=_jsonapi(j,url) if not n else []; rec=_recursive(j,url) if not n and not ja else []; parsed=n or ja or rec; rows.extend(parsed); debug.append({'url':url,'status':r.status_code,'content_type':ct,'native':len(n),'jsonapi':len(ja),'recursive':len(rec),'rows':len(parsed)})
            if parsed and idx<5:break
        except Exception as e:debug.append({'url':url,'status':'ERROR','rows':0,'error':str(e)[:220]})
        if time.time()-start>28:break
    rows=_dedupe(rows); print('UNDERDOG_CFB_DEBUG',debug,'rows',len(rows),flush=True); return rows,debug

def props_for_game(rows,away,home):
    if not rows:return []
    na,nh=_norm(away),_norm(home); exact=[];loose=[]
    for r in rows:
        ra,rh=_norm(r.get('away')),_norm(r.get('home')); blob=_norm(r.get('matchup'))
        if ra==na and rh==nh:exact.append(r)
        elif na and nh and ((na in blob and nh in blob) or (ra and (ra in na or na in ra) and rh and (rh in nh or nh in rh))):loose.append(r)
    return exact or loose
