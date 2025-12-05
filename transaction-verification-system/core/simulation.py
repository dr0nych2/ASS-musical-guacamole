import heapq
import random
from typing import Dict, List, Optional, Tuple
from .entities import PaymentSource, Server, Transaction
from .buffer import Buffer
from .dispatchers import DispatcherIn, DispatcherOut
from .statistics import Statistics
from utils.distributions import exponential


class Event:
    def __init__(self, event_type: str, time: float, source_id: Optional[str] = None,
                 transaction_id: Optional[str] = None, server_id: Optional[str] = None,
                 transaction: Optional[Transaction] = None):
        self.event_type = event_type
        self.time = time
        self.source_id = source_id
        self.transaction_id = transaction_id
        self.server_id = server_id
        self.transaction = transaction

    def __lt__(self, other):
        return self.time < other.time


class Simulation:
    def __init__(self, config: Dict, verbose: bool = True):
        self.config = config
        self.current_time = 0.0
        self.event_queue = []
        self.running = False
        self.verbose = verbose

        self.statistics = Statistics()
        self.buffer = Buffer(config['buffer_capacity'])

        self.sources = []
        for source_config in config['sources']:
            source = PaymentSource(
                source_id=source_config['id'],
                priority=source_config['priority'],
                lambda_param=source_config['lambda']
            )
            self.sources.append(source)

        self.servers = []
        for server_config in config['servers']:
            server = Server(
                server_id=server_config['id'],
                min_time=server_config['min_time'],
                max_time=server_config['max_time']
            )
            self.servers.append(server)

        self.dispatcher_in = DispatcherIn(self.buffer, self.servers, self.statistics, verbose)
        self.dispatcher_out = DispatcherOut(self.buffer, self.servers, self.statistics, verbose)

        self._schedule_initial_events()

    def _schedule_initial_events(self):
        for source in self.sources:
            delay = exponential(source.lambda_param)
            event = Event(
                event_type='GENERATE',
                time=self.current_time + delay,
                source_id=source.source_id
            )
            heapq.heappush(self.event_queue, event)

        end_event = Event(
            event_type='END',
            time=self.config['simulation_time'],
            source_id=None
        )
        heapq.heappush(self.event_queue, end_event)

    def run_step(self) -> bool:
        if not self.event_queue or not self.running:
            return False

        event = heapq.heappop(self.event_queue)
        self.current_time = event.time

        if event.event_type == 'GENERATE':
            self._handle_generate(event)
        elif event.event_type == 'PROCESS':
            self._handle_process(event)
        elif event.event_type == 'END':
            self.running = False
            return False

        return True

    def _handle_generate(self, event: Event):
        source = next(s for s in self.sources if s.source_id == event.source_id)
        transaction = source.generate_transaction(self.current_time)

        if self.verbose:
            print(f"[ГЕНЕРАЦИЯ] Транзакция {transaction.id} от источника {source.source_id}")

        status, end_time, server_id = self.dispatcher_in.process_transaction(transaction)

        if end_time and server_id:
            process_event = Event(
                event_type='PROCESS',
                time=end_time,
                source_id=source.source_id,
                transaction_id=transaction.id,
                server_id=server_id,
                transaction=transaction
            )
            heapq.heappush(self.event_queue, process_event)

        next_delay = exponential(source.lambda_param)
        next_event = Event(
            event_type='GENERATE',
            time=self.current_time + next_delay,
            source_id=source.source_id
        )
        heapq.heappush(self.event_queue, next_event)

    def _handle_process(self, event: Event):
        server = next(s for s in self.servers if s.server_id == event.server_id)

        if server.current_transaction:
            if self.verbose:
                print(
                    f"[ЗАВЕРШЕНИЕ] Транзакция {server.current_transaction.id} завершена на сервере {server.server_id}")

            self.statistics.record_service_end(
                server.current_transaction,
                self.current_time
            )

        server.complete_processing()

        results = self.dispatcher_out.on_server_free(server, self.current_time)

        for end_time, server_id in results:
            processing_server = next(s for s in self.servers if s.server_id == server_id)
            if processing_server.current_transaction:
                process_event = Event(
                    event_type='PROCESS',
                    time=end_time,
                    source_id=processing_server.current_transaction.source_id,
                    transaction_id=processing_server.current_transaction.id,
                    server_id=server_id,
                    transaction=processing_server.current_transaction
                )
                heapq.heappush(self.event_queue, process_event)

    def run_automated(self, target_accuracy: float = 0.1, confidence: float = 0.9):
        t_alpha = 1.643

        initial_iterations = 100
        self.running = True

        print(f"[АВТО] Начальный прогон: {initial_iterations} транзакций")

        completed = 0
        while completed < initial_iterations and self.running:
            if not self.run_step():
                break
            completed += 1

        current_p = self.statistics.get_rejection_rate()
        if current_p <= 0:
            current_p = 0.001

        required_iterations = int((t_alpha ** 2 * (1 - current_p)) / (current_p * target_accuracy ** 2))
        required_iterations = max(100, required_iterations)

        print(f"[АВТО] На основе P(отк)={current_p:.3f} требуется {required_iterations} транзакций")

        iteration = 1
        max_iterations = 10
        previous_p = current_p

        while iteration <= max_iterations:
            additional = min(500, max(100, required_iterations - completed))

            print(f"[АВТО] Итерация {iteration}: {additional} дополнительных транзакций")

            for _ in range(additional):
                if not self.run_step():
                    break
                completed += 1

            previous_p = current_p
            current_p = self.statistics.get_rejection_rate()

            if current_p > 0:
                relative_error = abs(current_p - previous_p) / previous_p if previous_p > 0 else 1.0

                if relative_error < target_accuracy:
                    print(
                        f"[АВТО] Достигнута требуемая точность: {relative_error * 100:.1f}% < {target_accuracy * 100:.1f}%")
                    break
                else:
                    print(f"[АВТО] Текущая ошибка: {relative_error * 100:.1f}%, требуется больше транзакций")

            iteration += 1

        print(f"[АВТО] Финальная симуляция: {completed} транзакций, P(отк)={current_p:.3f}")

        while self.event_queue and self.running:
            self.run_step()

    def get_state(self) -> Dict:
        return {
            'time': self.current_time,
            'buffer': list(self.buffer.queue),
            'servers': [
                {
                    'id': s.server_id,
                    'busy': s.is_busy,
                    'current_transaction': s.current_transaction.id if s.current_transaction else None
                }
                for s in self.servers
            ],
            'current_packet': self.dispatcher_out.current_packet,
            'current_packet_source': self.dispatcher_out.current_packet_source,
            'active_packet_processing': self.dispatcher_out.active_packet_processing,
            'statistics': self.statistics.get_summary()
        }

    def get_event_calendar(self, limit: int = 20) -> List[Dict]:
        return self.statistics.get_event_history(limit)

    def get_timeline_data(self) -> List[Dict]:
        timeline = []
        for event in self.statistics.event_history[-50:]:
            timeline.append({
                'time': event['time'],
                'type': event['type'],
                'transaction_id': event.get('transaction_id', ''),
                'source_id': event.get('source_id', ''),
                'server_id': event.get('server_id', ''),
                'info': event.get('info', '')
            })
        return timeline
