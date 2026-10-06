from __future__ import annotations
from pathlib import Path
import hashlib,json,shutil
from datetime import datetime,timezone
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from .const import VERSION
from .registry import render_dashboard_template,resolve_registry
DASHBOARD_FOLDER='foxcat_energy'; DASHBOARD_FILENAME='dashboard.yaml'; RECOMMENDED='1.7.1'; ORIGINAL='1.6.160'
def _dir(): return Path(__file__).parent/'dashboard'/'versions'
def _target(h): return Path(h.config.path(DASHBOARD_FOLDER,DASHBOARD_FILENAME))
def _state(h): return Path(h.config.path(DASHBOARD_FOLDER,'dashboard_state.json'))
def _read(p):
 try:return json.loads(p.read_text()) if p.exists() else {}
 except Exception:return {}
def _write(p,x): p.parent.mkdir(parents=True,exist_ok=True); t=p.with_suffix('.tmp'); t.write_text(json.dumps(x,ensure_ascii=False,indent=2)); t.replace(p)
def _src(ver): return _dir()/f'dashboard_v{ver}.yaml'
def dashboard_select_options(h=None): return ['Actuelle recommandée','Dashboard V1.6.160 original']
def dashboard_status(h):
 st=_read(_state(h)); return {'engine_version':VERSION,'active_version':st.get('active_version'),'previous_version':st.get('previous_version'),'available':['1.7.1','1.6.160'],'sha256':hashlib.sha256(_target(h).read_bytes()).hexdigest() if _target(h).exists() else None,'customized':False}
def _render(h,e,c,ver):
 text=_src(ver).read_text(); return render_dashboard_template(text,resolve_registry(h,e,c))[0]
def _apply(h,e,c,ver):
 target=_target(h); old=target.read_bytes() if target.exists() else None; st=_read(_state(h)); backup=None
 if old:
  backup=target.with_suffix('.yaml.bak'); shutil.copy2(target,backup)
 try:
  target.parent.mkdir(parents=True,exist_ok=True); target.write_text(_render(h,e,c,ver)); _write(_state(h),{'active_version':ver,'previous_version':st.get('active_version'),'backup':str(backup) if backup else None,'last_change':datetime.now(timezone.utc).isoformat(),'sha256':hashlib.sha256(target.read_bytes()).hexdigest()}); return dashboard_status(h)
 except Exception:
  if old is not None: target.write_bytes(old)
  raise
async def async_switch_dashboard(h,e,c,selection):
 ver='1.7.1' if selection=='Actuelle recommandée' else '1.6.160'; return await h.async_add_executor_job(_apply,h,e,c,ver)
async def async_ensure_dashboard(h,e,c):
 if _target(h).exists(): return False,str(_target(h))
 await async_switch_dashboard(h,e,c,'Actuelle recommandée'); return True,str(_target(h))
async def async_regenerate_dashboard(h,e,c):
 st=dashboard_status(h); ver='1.6.160' if st.get('active_version')=='1.6.160' else '1.7.1'; await h.async_add_executor_job(_apply,h,e,c,ver); return str(_target(h))
async def async_restore_previous_dashboard(h,e,c):
 st=_read(_state(h)); prev=st.get('previous_version'); return await async_switch_dashboard(h,e,c,'Dashboard V1.6.160 original' if prev=='1.6.160' else 'Actuelle recommandée')
