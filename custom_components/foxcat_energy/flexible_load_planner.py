from __future__ import annotations
from datetime import datetime,timedelta
from dataclasses import dataclass
from .economic_optimizer import PricePoint
from .machines import MachineDefinition,machine_allowed
START_NOW='START_NOW'; WAIT='WAIT'; CONTINUE='CONTINUE'; STOP_WHEN_SAFE='STOP_WHEN_SAFE'; USER_CONTROL='USER_CONTROL'; SAFETY_OVERRIDE='SAFETY_OVERRIDE'
@dataclass(slots=True)
class Reservation: load_id:str; start:datetime; end:datetime; power_w:float
def _price(ps,at):
 for p in reversed(ps):
  if p.at<=at:return float(p.price)
 return float(ps[0].price) if ps else None
def _step(ps):
 d=[int((b.at-a.at).total_seconds()/60) for a,b in zip(ps,ps[1:]) if b.at>a.at]; return max(5,min(d)) if d else 60
def _available(m,now):
 raw=str(getattr(m,'available_from','') or '')
 if not raw:return now
 try:
  h,mi=raw.split(':')[:2]; x=now.replace(hour=int(h),minute=int(mi),second=0,microsecond=0); return x if x>now else now
 except Exception:return now
def _deadline(m,now):
 raw=str(getattr(m,'deadline','') or '')
 if raw:
  try:
   h,mi=raw.split(':')[:2]; x=now.replace(hour=int(h),minute=int(mi),second=0,microsecond=0); return x if x>now else x+timedelta(1)
  except Exception:pass
 return now+timedelta(hours=max(float(getattr(m,'max_delay_hours',24)),1))
def _profile(m,learning):
 x=learning.get(m.machine_id,{}) if isinstance(learning,dict) else {}; dur=float(x.get('average_duration_s_10',0) or 0)/3600 or float(m.cycle_duration_minutes)/60; dur=max(.25,dur); power=float(x.get('average_energy_wh_10',0) or 0)/dur if x.get('average_energy_wh_10') else float(getattr(m,'nominal_power_w',2000)); return dur,power
def _conflict(a,b,p,res,maxp): return sum(r.power_w for r in res if a<r.end and b>r.start)+p>maxp
def build_flexible_load_plan(*,now,snapshot,settings,import_points,export_points,machines,learning,cycles,price_analysis,solar_forecast,boiler_thermal=None,boiler_user_override='AUTO'):
 ps=sorted(import_points,key=lambda x:x.at); step=_step(ps); dyn=bool(price_analysis.get('active')); result={'active':dyn,'ready':bool(ps),'loads':{},'machines':{},'timeline':[],'behavior':settings.get('mode'),'mode':price_analysis.get('mode','REACTIVE')}
 if not dyn:return result|{'reason':'Planner V1.7.1 réservé à Dynamique Day-Ahead'}
 maxp=min(float(settings.get('planner_max_parallel_power_w',5000)),max(float(settings.get('planner_grid_import_limit_w',5000))+max(snapshot.pv_w,0)-max(snapshot.house_w,0),100))
 result['max_parallel_power_w']=maxp; reservations=[]; behavior=settings.get('mode','Éco'); waitpen=float(settings.get('comfort_wait_penalty_eur_h',.03) if behavior=='Confort' else settings.get('eco_wait_penalty_eur_h',0)); minsaving=float(settings.get('comfort_min_saving_eur',.10) if behavior=='Confort' else settings.get('eco_min_saving_eur',.03)); maxwait=float(settings.get('comfort_max_wait_h',6) if behavior=='Confort' else settings.get('eco_max_wait_h',24))
 for m in sorted(machines,key=lambda x:-int(getattr(x,'priority',50))):
  if not settings.get(m.setting_key,m.automatic_default): result['machines'][m.machine_id]={'name':m.name,'decision':USER_CONTROL,'allow_start_now':False,'reason':'Gestion automatique désactivée'}; continue
  if cycles.get(m.machine_id,{}).get('protected'):
   end=datetime.fromisoformat(cycles[m.machine_id]['expected_end_at']) if cycles[m.machine_id].get('expected_end_at') else now+timedelta(hours=float(m.cycle_duration_minutes)/60); result['machines'][m.machine_id]={'name':m.name,'decision':CONTINUE,'allow_start_now':True,'reason':'Cycle protégé par MachineCycleManager','planned_start':now.isoformat(),'planned_end':end.isoformat()}; reservations.append(Reservation(m.machine_id,now,end,float(getattr(m,'nominal_power_w',2000)))); continue
  dur,power=_profile(m,learning); av=_available(m,now); dl=min(_deadline(m,now),now+timedelta(hours=maxwait)); candidates=[]
  starts=[p.at for p in ps if av<=p.at<=dl-timedelta(hours=dur) and machine_allowed(m,p.at)]
  if av<=dl-timedelta(hours=dur) and machine_allowed(m,av): starts.insert(0,av)
  for st in sorted(set(starts)):
   en=st+timedelta(hours=dur)
   if _conflict(st,en,power,reservations,maxp):continue
   c=sum((_price(ps,st+timedelta(minutes=i*step)) or 0)*power/1000*step/60 for i in range(max(1,int(dur*60/step))))
   wait=max((st-now).total_seconds()/3600,0); candidates.append((c+wait*waitpen,st,c))
  if not candidates:result['machines'][m.machine_id]={'name':m.name,'decision':WAIT,'allow_start_now':False,'reason':'Aucun créneau réalisable'};continue
  candidates.sort(); best=candidates[0]; nowc=next((x for x in candidates if x[1]==av or abs((x[1]-now).total_seconds())<=step*30),None); saving=(nowc[2]-best[2]) if nowc else 0
  if behavior=='Manuel':dec,allow,reason=USER_CONTROL,False,'Manuel : recommandation uniquement'
  elif nowc is None:dec,allow,reason=WAIT,False,'WAIT : charge indisponible maintenant'
  elif best[1]<=now+timedelta(minutes=max(step//2,5)) or saving<minsaving:dec,allow,reason=START_NOW,True,'START NOW : report insuffisamment rentable'; best=(nowc[0],nowc[1],nowc[2])
  else:dec,allow,reason=WAIT,False,f'WAIT : report {max((best[1]-now).total_seconds()/3600,0):.2f} h, économie {saving:.3f} €'
  en=best[1]+timedelta(hours=dur); reservations.append(Reservation(m.machine_id,best[1],en,power)); result['machines'][m.machine_id]={'name':m.name,'decision':dec,'allow_start_now':allow,'reason':reason,'planned_start':best[1].isoformat(),'planned_end':en.isoformat(),'estimated_cost_eur':round(best[2],4),'start_now_cost_eur':round(nowc[2],4) if nowc else None,'expected_saving_eur':round(max(saving,0),4),'energy_kwh':power/1000*dur,'estimated_grid_kwh':power/1000*dur,'estimated_solar_kwh':0}
 result['boiler']=_boiler(now,snapshot,settings,ps,price_analysis,boiler_thermal or {},boiler_user_override,step,maxp); result['loads']={**result['machines'],'boiler':result['boiler']}; result['timeline']=[{'load_id':k,'start':v.get('planned_start'),'end':v.get('planned_end'),'decision':v.get('decision')} for k,v in result['loads'].items() if v.get('planned_start')]; return result
def _boiler(now,snap,settings,ps,analysis,thermal,override,step,maxp):
 temp=thermal.get('measured_temp_c'); safety=float(settings.get('boiler_temp_safety_c',68)); need=float(settings.get('boiler_necessity_temp_c',38)); required=float(thermal.get('heating_duration_h',0) or 0); power=float(thermal.get('element_power_w',1800) or 1800)
 if isinstance(temp,(int,float)) and temp>=safety:return {'name':'Boiler','decision':SAFETY_OVERRIDE,'allow_start_now':False,'reason':'Sécurité thermique 68 °C prioritaire','status':'Bloqué par sécurité'}
 if override!='AUTO':return {'name':'Boiler','decision':USER_CONTROL,'allow_start_now':override=='FORCE_ON','reason':f'Commande utilisateur Boiler={override}'}
 if required<=.01:return {'name':'Boiler','decision':STOP_WHEN_SAFE,'allow_start_now':False,'reason':'Besoin thermique satisfait'}
 mandatory=isinstance(temp,(int,float)) and temp<need
 n=max(1,int((required*60+step-1)//step)); chosen=sorted(ps,key=lambda p:p.price)[:n]; energy=power/1000*step/60*len(chosen); cost=sum(p.price*power/1000*step/60 for p in chosen); nowp=_price(ps,now); nowcost=power/1000*required*nowp if nowp is not None else None
 dec=START_NOW if mandatory or any(p.at<=now<p.at+timedelta(minutes=step) for p in chosen) else WAIT; allow=dec==START_NOW or mandatory; reason=f'Nécessité ECS : {temp:.1f} °C < seuil {need:.1f} °C' if mandatory else 'Boiler interruptible : meilleurs créneaux tarifaires'; return {'name':'Boiler','decision':dec,'allow_start_now':allow,'reason':reason,'interruptible':True,'necessity':mandatory,'required_duration_h':required,'energy_kwh':energy,'estimated_grid_kwh':energy,'estimated_solar_kwh':0,'estimated_cost_eur':cost,'start_now_cost_eur':nowcost,'expected_saving_eur':max((nowcost or cost)-cost,0),'segments':[{'start':p.at.isoformat(),'end':(p.at+timedelta(minutes=step)).isoformat()} for p in chosen]}
