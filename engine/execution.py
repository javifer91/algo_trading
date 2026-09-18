from broker.base import BrokerInterface, OrderStatus
from core.logger import get_logger
from core.exceptions import OrderExecutionError
import time

logger = get_logger(__name__)

class ExecutionEngine:
    """
    Manages order execution and verifies order states with the broker.
    """
    def __init__(self, broker: BrokerInterface):
        self.broker = broker

    def await_execution(self, order_id: str, timeout_seconds: int = 10) -> bool:
        """
        Polls the broker until the order is filled, cancelled, or rejected.
        Returns True if FILLED, False otherwise.
        """
        start_time = time.time()
        while time.time() - start_time < timeout_seconds:
            status = self.broker.get_order_status(order_id)
            if status == OrderStatus.FILLED:
                logger.info(f"Order {order_id} executed successfully.")
                return True
            elif status in [OrderStatus.CANCELLED, OrderStatus.REJECTED, OrderStatus.EXPIRED]:
                logger.error(f"Order {order_id} failed with status: {status.name}")
                return False
                
            time.sleep(0.5)
            
        logger.warning(f"Order {order_id} execution timeout.")
        return False
