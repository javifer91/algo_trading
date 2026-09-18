from core.config import settings
from core.logger import get_logger
from core.exceptions import SafeModeActiveError, EmergencyStopActiveError

logger = get_logger(__name__)

class SafetyMonitor:
    def __init__(self):
        self.safe_mode = settings.safe_mode_enabled
        self.emergency_stop = settings.emergency_stop
        
    def trigger_safe_mode(self, reason: str):
        if not self.safe_mode:
            logger.critical(f"SAFE MODE TRIGGERED: {reason}")
            self.safe_mode = True
            
    def trigger_emergency_stop(self, reason: str):
        if not self.emergency_stop:
            logger.critical(f"EMERGENCY STOP TRIGGERED: {reason}")
            self.emergency_stop = True
            
    def check_trading_allowed(self):
        if self.emergency_stop:
            raise EmergencyStopActiveError("Emergency stop is active. No new trades allowed.")
        if self.safe_mode:
            raise SafeModeActiveError("Safe mode is active. System is restricted.")
