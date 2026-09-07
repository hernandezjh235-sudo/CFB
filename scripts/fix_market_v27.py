from pathlib import Path
p=Path('free_data_v16.py')
s=p.read_text()
old='''    market={}
    if betting is not None and not betting.empty:
        away=base._text(betting,'away_team','away_display_name')
        home=base._text(betting,'home_team','home_display_name')
        spread=base._series(betting,'spread','home_spread','spread_line',default=np.nan)
        total=base._series(betting,'over_under','total','total_line',default=np.nan)
        bw=base._series(betting,'week',default=resolved_week)
        for i in betting.index:
            if int(base._num(bw.loc[i],resolved_week))!=int(resolved_week):continue
            if not away.loc[i] or not home.loc[i]:continue
            market[(base._norm(away.loc[i]),base._norm(home.loc[i]))]={
                'away':away.loc[i],'home':home.loc[i],
                'market_home_spread':None if pd.isna(spread.loc[i]) else float(spread.loc[i]),
                'market_total':None if pd.isna(total.loc[i]) else float(total.loc[i])}
'''
new='''    market={}
    if betting is not None and not betting.empty:
        # v2.7 market cleanup: cfbfastR betting rows are keyed by game_id and do not
        # carry team names. Join them to the schedule instead of silently producing
        # an empty market map. These lines are used only as game-level validation /
        # environment context; player prop lines never manufacture projections.
        bgid=base._col(betting,'game_id','id','event_id')
        bw=base._series(betting,'week',default=resolved_week)
        spread=base._series(betting,'home_team_spread','home_spread','spread','game_spread',default=np.nan)
        total=base._series(betting,'over_under','total','total_line',default=np.nan)
        sgid=base._col(schedule,'game_id','id','event_id') if schedule is not None else None
        saway=base._col(schedule,'away_team','away_display_name') if schedule is not None else None
        shome=base._col(schedule,'home_team','home_display_name') if schedule is not None else None
        sched_lookup={}
        if sgid and saway and shome:
            for _,sr in schedule.iterrows():
                sched_lookup[str(sr.get(sgid))]=(str(sr.get(saway) or ''),str(sr.get(shome) or ''))
        for i in betting.index:
            if int(base._num(bw.loc[i],resolved_week))!=int(resolved_week):continue
            gid=str(betting.loc[i,bgid]) if bgid else ''
            away,home=sched_lookup.get(gid,('',''))
            if not away or not home:continue
            market[(base._norm(away),base._norm(home))]={
                'away':away,'home':home,'game_id':gid,
                'market_home_spread':None if pd.isna(spread.loc[i]) else float(spread.loc[i]),
                'market_total':None if pd.isna(total.loc[i]) else float(total.loc[i])}
'''
if old not in s: raise SystemExit('market block not found')
s=s.replace(old,new)
p.write_text(s)
print('v2.7 market game_id join applied')
