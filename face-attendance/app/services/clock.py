from datetime import datetime, timezone, timedelta
from ..models import Setting
from ..extensions import db

class Clock:
    @staticmethod
    def now():
        """Returns the current simulated or real time as a timezone-aware UTC datetime."""
        sim_enabled = Setting.query.get('sim_enabled')
        
        real_now = datetime.now(timezone.utc)
        
        if sim_enabled and sim_enabled.value == 'true':
            anchor_real_str = Setting.query.get('sim_anchor_real').value
            anchor_sim_str = Setting.query.get('sim_anchor_sim').value
            
            if anchor_real_str and anchor_sim_str:
                anchor_real = datetime.fromisoformat(anchor_real_str)
                anchor_sim = datetime.fromisoformat(anchor_sim_str)
                
                delta = real_now - anchor_real
                return anchor_sim + delta
                
        return real_now

    @staticmethod
    def set_simulated_time(target_dt):
        real_now = datetime.now(timezone.utc)
        
        s_en = Setting.query.get('sim_enabled')
        s_ar = Setting.query.get('sim_anchor_real')
        s_as = Setting.query.get('sim_anchor_sim')
        
        s_en.value = 'true'
        s_ar.value = real_now.isoformat()
        s_as.value = target_dt.isoformat()
        
        db.session.commit()
        
    @staticmethod
    def disable_simulation():
        s_en = Setting.query.get('sim_enabled')
        s_en.value = 'false'
        db.session.commit()
