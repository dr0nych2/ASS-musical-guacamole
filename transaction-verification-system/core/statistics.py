import math
from collections import defaultdict
from typing import Dict, List
from .entities import Transaction


class Statistics:
    def __init__(self):
        self.rejected_transactions = 0
        self.total_transactions = 0
        self.simulation_start_time = 0.0
        self.simulation_end_time = 0.0

        self.source_stats: Dict[str, Dict] = defaultdict(lambda: {
            'generated': 0,
            'rejected': 0,
            'completed': 0,
            'total_system_time': 0.0,
            'total_service_time': 0.0,
            'total_wait_time': 0.0,
            'service_times': [],
            'wait_times': [],
            'system_times': []
        })

        self.server_stats: Dict[str, Dict] = defaultdict(lambda: {
            'busy_time': 0.0,
            'processed': 0,
            'last_start_time': 0.0
        })

        self.service_starts: Dict[str, Dict] = {}
        self.buffer_entries: Dict[str, float] = {}
        self.event_history: List[Dict] = []

    def record_transaction_generated(self, source_id: str):
        self.total_transactions += 1
        self.source_stats[source_id]['generated'] += 1

    def record_rejection(self, source_id: str):
        self.rejected_transactions += 1
        self.source_stats[source_id]['rejected'] += 1

    def record_buffer_entry(self, transaction: Transaction, entry_time: float):
        self.buffer_entries[transaction.id] = entry_time
        self._add_event('BUFFER_ENTRY', entry_time,
                        transaction_id=transaction.id,
                        source_id=transaction.source_id)

    def record_service_start(self, transaction: Transaction, start_time: float, server_id: str):
        self.service_starts[transaction.id] = {
            'start_time': start_time,
            'server_id': server_id,
            'source_id': transaction.source_id
        }

        self.server_stats[server_id]['last_start_time'] = start_time

        wait_time = 0.0
        if transaction.id in self.buffer_entries:
            wait_time = start_time - self.buffer_entries[transaction.id]
            self.source_stats[transaction.source_id]['wait_times'].append(wait_time)
            self.source_stats[transaction.source_id]['total_wait_time'] += wait_time

        self._add_event('SERVICE_START', start_time,
                        transaction_id=transaction.id,
                        source_id=transaction.source_id,
                        server_id=server_id,
                        wait_time=wait_time)

    def record_service_end(self, transaction: Transaction, end_time: float):
        if transaction.id in self.service_starts:
            start_info = self.service_starts[transaction.id]
            service_time = end_time - start_info['start_time']
            server_id = start_info['server_id']
            source_id = start_info['source_id']

            self.server_stats[server_id]['busy_time'] += service_time
            self.server_stats[server_id]['processed'] += 1

            self.source_stats[source_id]['completed'] += 1
            self.source_stats[source_id]['service_times'].append(service_time)
            self.source_stats[source_id]['total_service_time'] += service_time

            system_time = end_time - transaction.timestamp
            self.source_stats[source_id]['system_times'].append(system_time)
            self.source_stats[source_id]['total_system_time'] += system_time

            self._add_event('SERVICE_END', end_time,
                            transaction_id=transaction.id,
                            source_id=source_id,
                            server_id=server_id,
                            service_time=service_time,
                            system_time=system_time)

            del self.service_starts[transaction.id]

    def record_packet_formed(self, source_id: str, packet_size: int, time: float):
        self._add_event('PACKET_FORMED', time,
                        source_id=source_id,
                        packet_size=packet_size)

    def record_transaction_rejected(self, transaction: Transaction, time: float):
        self._add_event('REJECTED', time,
                        transaction_id=transaction.id,
                        source_id=transaction.source_id)

    def record_transaction_served(self, transaction: Transaction, server_id: str, time: float):
        self._add_event('SERVED_DIRECT', time,
                        transaction_id=transaction.id,
                        source_id=transaction.source_id,
                        server_id=server_id)

    def _add_event(self, event_type: str, time: float, **kwargs):
        """Добавляет событие в историю"""
        event = {
            'type': event_type,
            'time': time,
            **kwargs
        }
        self.event_history.append(event)

    def get_rejection_rate(self) -> float:
        if self.total_transactions == 0:
            return 0.0
        return self.rejected_transactions / self.total_transactions

    def get_source_statistics(self, source_id: str) -> Dict:
        stats = self.source_stats[source_id]
        generated = stats['generated']

        if generated == 0:
            return {
                'generated': 0,
                'rejected': 0,
                'completed': 0,
                'rejection_rate': 0.0,
                'avg_system_time': 0.0,
                'avg_wait_time': 0.0,
                'avg_service_time': 0.0,
                'var_wait_time': 0.0,
                'var_service_time': 0.0
            }

        rejection_rate = stats['rejected'] / generated if generated > 0 else 0.0

        avg_system_time = stats['total_system_time'] / stats['completed'] if stats['completed'] > 0 else 0.0
        avg_wait_time = stats['total_wait_time'] / stats['completed'] if stats['completed'] > 0 else 0.0
        avg_service_time = stats['total_service_time'] / stats['completed'] if stats['completed'] > 0 else 0.0

        var_wait_time = self._calculate_variance(stats['wait_times'], avg_wait_time) if stats['wait_times'] else 0.0
        var_service_time = self._calculate_variance(stats['service_times'], avg_service_time) if stats[
            'service_times'] else 0.0

        return {
            'generated': generated,
            'rejected': stats['rejected'],
            'completed': stats['completed'],
            'rejection_rate': rejection_rate,
            'avg_system_time': avg_system_time,
            'avg_wait_time': avg_wait_time,
            'avg_service_time': avg_service_time,
            'var_wait_time': var_wait_time,
            'var_service_time': var_service_time
        }

    def get_server_statistics(self, server_id: str, total_time: float) -> Dict:
        stats = self.server_stats[server_id]
        utilization = stats['busy_time'] / total_time if total_time > 0 else 0.0

        return {
            'processed': stats['processed'],
            'busy_time': stats['busy_time'],
            'utilization': utilization
        }

    def _calculate_variance(self, values: List[float], mean: float) -> float:
        if len(values) <= 1:
            return 0.0
        squared_diff = sum((x - mean) ** 2 for x in values)
        return squared_diff / (len(values) - 1)

    def get_event_history(self, limit: int = None) -> List[Dict]:
        if limit:
            return self.event_history[-limit:]
        return self.event_history

    def get_summary(self) -> Dict:
        return {
            'total_transactions': self.total_transactions,
            'rejected_transactions': self.rejected_transactions,
            'rejection_rate': self.get_rejection_rate()
        }

    def set_simulation_time(self, start_time: float, end_time: float):
        self.simulation_start_time = start_time
        self.simulation_end_time = end_time
