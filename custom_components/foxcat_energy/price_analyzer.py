from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime,timedelta
from statistics import median
from .economic_optimizer import PricePoint
REACTIVE='REACTIVE'; PREDICTIVE='PREDICTIVE'; BEFORE_FAVORABLE_WINDOW='BEFORE_FAVORABLE_WINDOW'; IN_FAVORABLE_WINDOW='IN_FAVORABLE_WINDOW'; AFTER_FAVORABLE_WINDOW='AFTER_FAVORABLE_WINDOW'
def _uniq(ps): return sorted({p.at:p for p in ps}.values(),key=lambda p:p.at)
def _gran(ps):
 d=[(b.at-a.at).total_seconds()/60 for a,b in zip(ps,ps[1:]) if 1<=(b.at-a.at).total_seconds()/60<=360]; return int(round(median(d))) if d else 60
def _pos(v,lo,hi): return 50.0 if hi<=lo else max(0,min(100,(v-lo)/(hi-lo)*100))
def analyze_price_curve(*,now,import_points,export_points=(),settings,tomorrow_available=False,current_buy=None):
 ps=_uniq(import_points); ex=_uniq(export_points); g=_gran(ps); td=now.date(); tm=td+timedelta(1); yd=td-timedelta(1)
 day=[p for p in ps if p.at.date()==td]; nxt=[p for p in ps if p.at.date()==tm]; prev=[p for p in ps if p.at.date()==yd]
 cur=float(current_buy) if isinstance(current_buy,(int,float)) else next((p.price for p in reversed(ps) if p.at<=now),None)
 future=[p for p in ps if p.at>=now-timedelta(minutes=g)]; vals=[p.price for p in future] or ([cur] if cur is not None else [])
 lo=min(vals) if vals else None; hi=max(vals) if vals else None; pos=_pos(cur,lo,hi) if cur is not None and lo is not None else None
 rank=1+sum(v<cur for v in vals) if cur is not None else None
 threshold=float(settings.get('dynamic_favorable_position_pct',30)); maxh=float(settings.get('dynamic_favorable_max_hours',4)); high=float(settings.get('dynamic_high_position_pct',70))
 selected=[p for p in day if _pos(p.price,min(x.price for x in day),max(x.price for x in day))<=threshold] if day else []
 selected=sorted(selected,key=lambda p:(p.price,p.at))[:max(1,int(maxh*60/g))]
 windows=[]; block=[]
 for p in sorted(selected,key=lambda x:x.at):
  if block and p.at-block[-1].at>timedelta(minutes=g*1.5): windows.append((block[0].at,block[-1].at+timedelta(minutes=g))); block=[]
  block.append(p)
 if block: windows.append((block[0].at,block[-1].at+timedelta(minutes=g)))
 current_window=next((w for w in windows if w[0]<=now<w[1]),None); future_windows=[w for w in windows if w[0]>now]
 state=IN_FAVORABLE_WINDOW if current_window else BEFORE_FAVORABLE_WINDOW if future_windows else AFTER_FAVORABLE_WINDOW
 maxgap=max([(b.at-a.at).total_seconds()/60 for a,b in zip(future,future[1:])] or [0]); continuity=maxgap<=g*2.5; predictive=bool(tomorrow_available and nxt and continuity)
 ysame=next((p for p in prev if abs((p.at-(now-timedelta(1))).total_seconds())<=g*30),None)
 stats=lambda a:{'available':bool(a),'minimum':min([p.price for p in a],default=None),'maximum':max([p.price for p in a],default=None),'average':sum(p.price for p in a)/len(a) if a else None,'points':len(a)}
 def wd(w): return {'start':w[0].isoformat(),'end':w[1].isoformat(),'duration_h':(w[1]-w[0]).total_seconds()/3600} if w else None
 saving=(cur-min((p.price for p in future if p.at>=now),default=cur)) if cur is not None else None
 return {'active':True,'last_update':now.isoformat(),'mode':PREDICTIVE if predictive else REACTIVE,'state':state,'valid':bool(ps and continuity),'granularity_minutes':g,'current_price_eur_kwh':cur,'current_position_pct':pos,'current_rank':rank,'today':stats(day),'tomorrow':stats(nxt),'yesterday':stats(prev),'threshold_pct':threshold,'high_threshold_pct':high,'favorable_max_hours':maxh,'favorable_selected_hours_today':len(selected)*g/60,'favorable_used_hours_today':len([p for p in selected if p.at+timedelta(minutes=g)<=now])*g/60,'favorable_remaining_hours_today':len([p for p in selected if p.at+timedelta(minutes=g)>now])*g/60,'current_window_remaining_h':max((current_window[1]-now).total_seconds()/3600,0) if current_window else 0,'next_favorable_window':wd(current_window or (future_windows[0] if future_windows else None)),'next_peak':None,'best_remaining_today':None,'best_tomorrow':None,'potential_saving_eur_kwh':max(saving or 0,0),'yesterday_same_time_eur_kwh':ysame.price if ysame else None,'delta_vs_yesterday_same_time_pct':((cur-ysame.price)/abs(ysame.price)*100) if cur is not None and ysame and ysame.price else None,'delta_vs_yesterday_average_eur_kwh':cur-stats(prev)['average'] if cur is not None and stats(prev)['average'] is not None else None,'freshness':{'continuity_ok':continuity,'maximum_gap_minutes':maxgap},'series':[{'at':p.at.isoformat(),'import_eur_kwh':p.price,'export_eur_kwh':next((e.price for e in ex if e.at==p.at),None),'favorable':p in selected,'peak':False} for p in ps]}
