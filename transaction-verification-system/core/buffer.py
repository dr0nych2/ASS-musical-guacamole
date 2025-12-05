from collections import deque
from typing import List
from .entities import Transaction


class Buffer:
    def __init__(self, capacity: int):
        self.capacity = capacity
        self.queue = deque()

    def add_transaction(self, transaction: Transaction) -> bool:
        if len(self.queue) < self.capacity:
            self.queue.append(transaction)
            return True
        return False

    def get_transactions_by_source(self, source_id: str) -> List[Transaction]:
        return [t for t in self.queue if t.source_id == source_id]

    def remove_transactions_by_source(self, source_id: str) -> List[Transaction]:
        removed = []
        remaining = []
        for t in self.queue:
            if t.source_id == source_id:
                removed.append(t)
            else:
                remaining.append(t)
        self.queue = deque(remaining)
        return removed

    def get_all_sources(self) -> List[str]:
        sources = set()
        for t in self.queue:
            sources.add(t.source_id)
        return list(sources)

    def is_full(self) -> bool:
        return len(self.queue) >= self.capacity

    def is_empty(self) -> bool:
        return len(self.queue) == 0
