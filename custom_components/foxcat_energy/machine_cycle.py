from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

IDLE="IDLE"
START_DETECTED="START_DETECTED"
PROTECTED_CYCLE="PROTECTED_CYCLE"
END_CONFIRMATION="END_CONFIRMATION"
FINISHED="FINISHED"

@dataclass(slots=True)
class MachineCycleState:
    machine_id: str
    state: str = IDLE
    started_at: datetime | None = None
    candidate_at: datetime | None = None
    low_since: datetime | None = None
    expected_end_at: datetime | None = None
    timeout_at: datetime | None = None
    last_power_w: float = 0.0
    origin: str = "NONE"
    @property
    def protected(self)->bool:
        return self.state in {PROTECTED_CYCLE,END_CONFIRMATION}

class MachineCycleManager:
    """Cycle logique persistant : une pause à 0 W ne termine jamais un cycle prématurément."""
    def __init__(self)->None:
        self._states: dict[str,MachineCycleState]={}
    def state_for(self,machine_id:str)->MachineCycleState:
        return self._states.setdefault(machine_id,MachineCycleState(machine_id))
    def is_protected(self,machine_id:str)->bool:
        return self.state_for(machine_id).protected
    def update(self,machine_id:str,power_w:float,now:datetime,*,start_w:float,start_confirm_s:float,duration_minutes:float,margin_minutes:float,end_w:float,end_confirm_minutes:float,external_cycle_on:bool=False)->MachineCycleState:
        st=self.state_for(machine_id); power=max(float(power_w),0.0); st.last_power_w=power
        if external_cycle_on and not st.protected:
            self._start(st,now,duration_minutes,margin_minutes,"EXTERNAL_USER"); return st
        if st.state in {IDLE,FINISHED}:
            if power>=start_w:
                st.state=START_DETECTED; st.candidate_at=st.candidate_at or now
                if (now-st.candidate_at).total_seconds()>=start_confirm_s:
                    self._start(st,st.candidate_at,duration_minutes,margin_minutes,"POWER_DETECTED")
            else:
                st.state=IDLE; st.candidate_at=None
            return st
        if st.state==START_DETECTED:
            if power<start_w: st.state=IDLE; st.candidate_at=None
            elif st.candidate_at and (now-st.candidate_at).total_seconds()>=start_confirm_s:
                self._start(st,st.candidate_at,duration_minutes,margin_minutes,"POWER_DETECTED")
            return st
        if st.state==PROTECTED_CYCLE:
            if st.expected_end_at and now>=st.expected_end_at:
                st.state=END_CONFIRMATION; st.low_since=now if power<=end_w else None
            return st
        if st.state==END_CONFIRMATION:
            if st.timeout_at and now>=st.timeout_at:
                self._finish(st); return st
            if power<=end_w:
                st.low_since=st.low_since or now
                if now-st.low_since>=timedelta(minutes=end_confirm_minutes): self._finish(st)
            else: st.low_since=None
        return st
    def force_start(self, machine_id: str, now: datetime, *, duration_minutes: float, margin_minutes: float, origin: str = "USER_BUTTON") -> MachineCycleState:
        """Démarre immédiatement un cycle protégé demandé par l'utilisateur."""
        st = self.state_for(machine_id)
        self._start(st, now, duration_minutes, margin_minutes, origin)
        return st

    def force_finish(self, machine_id: str) -> MachineCycleState:
        """Termine explicitement un cycle à la demande de l'utilisateur."""
        st = self.state_for(machine_id)
        self._finish(st)
        return st

    def snapshot(self,now:datetime)->dict[str,dict[str,Any]]:
        return {mid:{"state":st.state,"protected":st.protected,"origin":st.origin,"power_w":st.last_power_w,"started_at":st.started_at,"expected_end_at":st.expected_end_at,"timeout_at":st.timeout_at,"remaining_s":max((st.expected_end_at-now).total_seconds(),0) if st.expected_end_at and st.protected else None} for mid,st in self._states.items()}
    @staticmethod
    def _start(st,started,duration,margin,origin):
        st.state=PROTECTED_CYCLE; st.started_at=started; st.candidate_at=None; st.low_since=None; st.origin=origin; st.expected_end_at=started+timedelta(minutes=max(duration,1)); st.timeout_at=st.expected_end_at+timedelta(minutes=max(margin,1))
    @staticmethod
    def _finish(st):
        st.state=FINISHED; st.started_at=None; st.candidate_at=None; st.low_since=None; st.expected_end_at=None; st.timeout_at=None; st.origin="NONE"
