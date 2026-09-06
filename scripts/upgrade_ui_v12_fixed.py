from pathlib import Path

p = Path('app.py')
s = p.read_text()

s = s.replace('APP_VERSION = "CFB Prop Engine v1.0"', 'APP_VERSION = "CFB Prop Engine v1.2 — ELITE PLAYER CARDS + CFB DATA STACK"')
s = s.replace('st.set_page_config(page_title="CFB Prop Engine", page_icon="🏈", layout="wide")', 'st.set_page_config(page_title="CFB Prop Engine", page_icon="🏈", layout="wide", initial_sidebar_state="collapsed")')

if '.cfb-player-card{' not in s:
    css_block = '''
st.markdown("""
<style>
.block-container{max-width:1750px!important;padding-left:1rem!important;padding-right:1rem!important}
.cfb-player-card{--team:#2f81f7;position:relative;overflow:hidden;background:radial-gradient(circle at 0% 0%,color-mix(in srgb,var(--team) 28%,transparent),transparent 32%),linear-gradient(145deg,#09131e 0%,#050a11 100%);border:1px solid color-mix(in srgb,var(--team) 58%,#24384c);border-left:4px solid var(--team);border-radius:20px;padding:14px 15px;margin:10px 0;box-shadow:0 12px 35px rgba(0,0,0,.22)}
.cfb-card-top{display:grid;grid-template-columns:62px minmax(0,1fr) auto;gap:11px;align-items:center}.cfb-team-logo{width:58px;height:58px;object-fit:contain;filter:drop-shadow(0 0 8px color-mix(in srgb,var(--team) 55%,transparent))}
.cfb-player-name{font-size:20px;font-weight:950;line-height:1.05;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.cfb-player-sub{font-size:10px;color:#9fb1c3;text-transform:uppercase;font-weight:850;letter-spacing:.07em;margin-top:4px}
.cfb-status{font-size:10px;font-weight:950;padding:6px 9px;border-radius:999px;border:1px solid #2b4156;background:#0b1722}.cfb-status.playable{color:#66f594;border-color:#2a7044}.cfb-status.lean{color:#ffd166;border-color:#79672d}.cfb-status.track{color:#9eb1c4}
.cfb-prop-title{margin-top:10px;font-size:11px;color:#8da1b5;text-transform:uppercase;font-weight:900;letter-spacing:.08em}.cfb-proj-row{display:grid;grid-template-columns:1.1fr .8fr .8fr .8fr;gap:7px;margin-top:6px}
.cfb-box{background:rgba(3,9,15,.72);border:1px solid #1c3043;border-radius:11px;padding:8px;text-align:center}.cfb-box .lab{font-size:7px;color:#7890a8;text-transform:uppercase;font-weight:900;letter-spacing:.08em}.cfb-box .val{font-size:17px;font-weight:950;margin-top:2px}.cfb-box.main .val{font-size:23px}.cfb-prob{color:#65f28a}.cfb-edge.good{color:#65f28a}.cfb-edge.bad{color:#ff7385}
.cfb-match-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:6px;margin-top:8px}.cfb-mini{background:#07111a;border:1px solid #172b3e;border-radius:9px;padding:7px;text-align:center}.cfb-mini .lab{font-size:7px;color:#778da4;text-transform:uppercase;font-weight:900}.cfb-mini .val{font-size:12px;font-weight:900;margin-top:2px}
.cfb-why{border-top:1px solid #182b3d;margin-top:9px;padding-top:8px;font-size:9px;color:#a6b7c8;line-height:1.45}.cfb-game-strip{font-size:9px;color:#91a6bb;margin-top:6px}
@media(max-width:900px){.cfb-player-card{border-radius:16px;padding:12px}.cfb-player-name{font-size:18px}}
@media(max-width:560px){.block-container{padding-left:.55rem!important;padding-right:.55rem!important}.cfb-card-top{grid-template-columns:48px minmax(0,1fr) auto}.cfb-team-logo{width:46px;height:46px}.cfb-proj-row{grid-template-columns:1.1fr .8fr}.cfb-match-grid{grid-template-columns:repeat(2,1fr)}.cfb-box .val{font-size:15px}.cfb-box.main .val{font-size:20px}}
</style>
""", unsafe_allow_html=True)
'''
    anchor = '\n\ndef secret(name: str, default: str = "") -> str:'
    s = s.replace(anchor, css_block + anchor, 1)

if 'bundle.get("teams",[])' not in s:
    s = s.replace('''    for r in bundle.get("talent",[]):''', '''    for r in bundle.get("teams",[]):
        t=r.get("school")
        if t:
            logos=r.get("logos") or []
            teams.setdefault(t,{}).update({"logo":logos[0] if logos else "","color":("#"+str(r.get("color","")).lstrip("#")) if r.get("color") else "#2f81f7","conference":r.get("conference") or ""})
    for r in bundle.get("talent",[]):''', 1)

if '"teams":("/teams/fbs"' not in s:
    s = s.replace('''        "rankings":("/rankings",{"year":year,"week":week},21600),''', '''        "teams":("/teams/fbs",{"year":year},86400),
        "rankings":("/rankings",{"year":year,"week":week},21600),''', 1)

if 'def render_player_card(' not in s:
    card_func = '''
def render_player_card(r:dict, ctx:dict, game:dict):
    team=str(r.get("team") or ""); opp=str(r.get("opp") or "")
    tc=get_team(ctx,team); oc=get_team(ctx,opp)
    logo=tc.get("logo") or ""; color=tc.get("color") or "#2f81f7"
    status=str(r.get("status") or "TRACK"); status_cls="playable" if status=="PLAYABLE" else "lean" if status=="LEAN" else "track"
    prob=sf(r.get("probability"))*100; proj=sf(r.get("projection")); line=sf(r.get("line")); edge=sf(r.get("edge")); side=str(r.get("side") or "Over")
    notes=str(r.get("notes") or "No extra flags"); ap=oc.get("ap_rank") or "—"; modelrk=oc.get("model_rank") or "—"
    passd=oc.get("def_passing"); rushd=oc.get("def_rushing"); expld=oc.get("def_expl"); blow=sf(game.get("blowout_prob"))*100
    logo_html=f"<img class='cfb-team-logo' src='{logo}'/>" if logo else "<div class='cfb-team-logo'></div>"
    edge_cls="good" if edge>=0 else "bad"
    st.markdown(f"""
    <div class='cfb-player-card' style='--team:{color}'>
      <div class='cfb-card-top'>{logo_html}<div><div class='cfb-player-name'>{r.get('player','')}</div><div class='cfb-player-sub'>{team} · vs {opp} · AP #{ap} / Model #{modelrk}</div></div><div class='cfb-status {status_cls}'>{status}</div></div>
      <div class='cfb-prop-title'>{side} {line:g} · {r.get('prop','')}</div>
      <div class='cfb-proj-row'><div class='cfb-box main'><div class='lab'>Projection</div><div class='val'>{proj:.1f}</div></div><div class='cfb-box'><div class='lab'>{side} Prob</div><div class='val cfb-prob'>{prob:.1f}%</div></div><div class='cfb-box'><div class='lab'>Edge</div><div class='val cfb-edge {edge_cls}'>{edge:+.1f}</div></div><div class='cfb-box'><div class='lab'>Model SD</div><div class='val'>{sf(r.get('sd')):.1f}</div></div></div>
      <div class='cfb-match-grid'><div class='cfb-mini'><div class='lab'>Opp Pass D</div><div class='val'>{'—' if passd is None else f'{sf(passd):.1f}'}</div></div><div class='cfb-mini'><div class='lab'>Opp Rush D</div><div class='val'>{'—' if rushd is None else f'{sf(rushd):.1f}'}</div></div><div class='cfb-mini'><div class='lab'>Explosive D</div><div class='val'>{'—' if expld is None else f'{sf(expld):.1f}'}</div></div><div class='cfb-mini'><div class='lab'>Blowout Risk</div><div class='val'>{blow:.0f}%</div></div></div>
      <div class='cfb-game-strip'>Game model: {game.get('away')} {sf(game.get('away_points')):.1f} — {sf(game.get('home_points')):.1f} {game.get('home')} · Total {sf(game.get('model_total')):.1f}</div>
      <div class='cfb-why'>WHY: {notes}</div>
    </div>""", unsafe_allow_html=True)

'''
    s = s.replace('\n\n# --------------------------- APP ---------------------------', '\n\n' + card_func + '# --------------------------- APP ---------------------------', 1)

old = '''        if not pdf.empty:
            pdf["probability"]=(pdf["probability"]*100).round(1)
            for c in ["line","projection","edge"]: pdf[c]=pd.to_numeric(pdf[c],errors="coerce").round(2)
            st.dataframe(pdf[show].sort_values("probability",ascending=False),use_container_width=True,hide_index=True)
            if st.button("Save this projected board"):'''
new = '''        if not pdf.empty:
            ranked=sorted(projected,key=lambda x:sf(x.get("probability")),reverse=True)
            cols=st.columns(2)
            for i,rr in enumerate(ranked):
                with cols[i%2]: render_player_card(rr,ctx,selected_game)
            with st.expander("📋 Compact projection table",expanded=False):
                pdf["probability"]=(pdf["probability"]*100).round(1)
                for c in ["line","projection","edge"]: pdf[c]=pd.to_numeric(pdf[c],errors="coerce").round(2)
                st.dataframe(pdf[show].sort_values("probability",ascending=False),use_container_width=True,hide_index=True)
            if st.button("Save this projected board"):'''
if old in s:
    s = s.replace(old, new, 1)

s = s.replace('for k in ["games","sp","core","srs","elo","rankings","talent","player_stats","advanced"]:', 'for k in ["games","teams","sp","core","srs","elo","rankings","talent","player_stats","advanced"]:')
s = s.replace('"games":"schedule/results/game counts","sp":', '"games":"schedule/results/game counts","teams":"FBS identity/logos/colors/conference","sp":')

p.write_text(s)
