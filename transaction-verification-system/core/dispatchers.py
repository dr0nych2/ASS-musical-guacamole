from typing import List, Optional, Tuple
from .entities import Transaction, Server
from .buffer import Buffer
from .statistics import Statistics


class DispatcherIn:
    def __init__(self, buffer: Buffer, servers: List[Server], statistics: Statistics, verbose: bool = True):
        self.buffer = buffer
        self.servers = servers
        self.statistics = statistics
        self.verbose = verbose

    def process_transaction(self, transaction: Transaction) -> Tuple[str, Optional[float], Optional[str]]:
        self.statistics.record_transaction_generated(transaction.source_id)

        free_server = None
        for server in self.servers:
            if server.is_free():
                free_server = server
                break

        if free_server:
            end_time = free_server.process_transaction(transaction, transaction.timestamp)
            self.statistics.record_service_start(transaction, transaction.timestamp, free_server.server_id)
            self.statistics.record_transaction_served(transaction, free_server.server_id, transaction.timestamp)

            if self.verbose:
                print(f"[НАПРАВЛЕНИЕ] Транзакция {transaction.id} → сервер {free_server.server_id}")

            return 'served', end_time, free_server.server_id
        else:
            if self.buffer.add_transaction(transaction):
                self.statistics.record_buffer_entry(transaction, transaction.timestamp)

                if self.verbose:
                    print(f"[БУФЕР] Транзакция {transaction.id} добавлена в буфер")

                return 'buffered', None, None
            else:
                self.statistics.record_rejection(transaction.source_id)
                self.statistics.record_transaction_rejected(transaction, transaction.timestamp)

                if self.verbose:
                    print(f"[ОТКАЗ] Транзакция {transaction.id} отклонена (буфер полон)")

                return 'rejected', None, None


class DispatcherOut:
    def __init__(self, buffer: Buffer, servers: List[Server], statistics: Statistics, verbose: bool = True):
        self.buffer = buffer
        self.servers = servers
        self.statistics = statistics
        self.verbose = verbose
        self.current_packet_source: Optional[str] = None
        self.current_packet: List[Transaction] = []
        self.active_packet_processing = False

    def on_server_free(self, server: Server, current_time: float) -> List[Tuple[float, str]]:
        end_times = []

        if self.current_packet and self.active_packet_processing:
            if server.is_free():
                transaction = self.current_packet.pop(0)
                end_time = server.process_transaction(transaction, current_time)
                self.statistics.record_service_start(transaction, current_time, server.server_id)
                end_times.append((end_time, server.server_id))

                if self.verbose:
                    print(f"[ПАКЕТ] Транзакция {transaction.id} из пакета → сервер {server.server_id}")

            if not self.current_packet:
                self.current_packet_source = None
                self.active_packet_processing = False

                if self.verbose:
                    print(f"[ПАКЕТ] Пакет от источника {self.current_packet_source} полностью обработан")

            return end_times

        packet = self.select_packet(current_time)
        if not packet:
            return []

        self.current_packet = packet
        self.current_packet_source = packet[0].source_id
        self.active_packet_processing = True

        self.statistics.record_packet_formed(self.current_packet_source, len(packet), current_time)

        if self.verbose:
            print(f"[ПАКЕТ] Сформирован пакет из {len(packet)} транзакций от источника {self.current_packet_source}")

        if server.is_free():
            transaction = self.current_packet.pop(0)
            end_time = server.process_transaction(transaction, current_time)
            self.statistics.record_service_start(transaction, current_time, server.server_id)
            end_times.append((end_time, server.server_id))

            if self.verbose:
                print(f"[ПАКЕТ] Первая транзакция {transaction.id} → сервер {server.server_id}")

        return end_times

    def select_packet(self, current_time: float) -> List[Transaction]:
        if self.buffer.is_empty():
            return []

        sources_in_buffer = self.buffer.get_all_sources()
        if not sources_in_buffer:
            return []

        priority_order = sorted(sources_in_buffer, key=lambda x: (int(x[1:]) if x[1:].isdigit() else 999))

        for source in priority_order:
            if source in sources_in_buffer:
                packet = self.buffer.remove_transactions_by_source(source)
                return packet

        return []
