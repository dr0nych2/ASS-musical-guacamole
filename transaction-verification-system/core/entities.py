import random
from dataclasses import dataclass
from typing import Optional


@dataclass
class Transaction:
    id: str
    source_id: str
    timestamp: float
    amount: float = 100.0


class PaymentSource:
    def __init__(self, source_id: str, priority: int, lambda_param: float):
        self.source_id = source_id
        self.priority = priority
        self.lambda_param = lambda_param
        self.generated_count = 0

    def generate_transaction(self, current_time: float) -> Transaction:
        self.generated_count += 1
        return Transaction(
            id=f"{self.source_id}_{self.generated_count}",
            source_id=self.source_id,
            timestamp=current_time
        )


class Server:
    def __init__(self, server_id: str, min_time: float, max_time: float):
        self.server_id = server_id
        self.min_process_time = min_time
        self.max_process_time = max_time
        self.is_busy = False
        self.current_transaction: Optional[Transaction] = None

    def is_free(self) -> bool:
        return not self.is_busy

    def process_transaction(self, transaction: Transaction, current_time: float) -> float:
        self.is_busy = True
        self.current_transaction = transaction
        process_time = random.uniform(self.min_process_time, self.max_process_time)
        return current_time + process_time

    def complete_processing(self):
        self.is_busy = False
        self.current_transaction = None
