import json
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.simulation import Simulation


def display_header():
    print("╔══════════════════════════════════════════════════════════════════════════════════════════════╗")
    print("║                         СИСТЕМА АНТИФРОД-ВЕРИФИКАЦИИ ТРАНЗАКЦИЙ                              ║")
    print("║                                   Вариант №9 - Имитационная модель                           ║")
    print("╠══════════════════════════════════════════════════════════════════════════════════════════════╣")
    print("║ ПАРАМЕТРЫ ВАРИАНТА: ИБ ИЗ1 ПЗ2 Д10З2 Д10О5 Д2П1 Д2Б5 ОР1 ОД3                                 ║")
    print("╠══════════════════════════════════════════════════════════════════════════════════════════════╣")
    print("║ ИБ  - Бесконечные источники         | Д10З2 - FIFO буфер (по порядку)                        ║")
    print("║ ИЗ1 - Пуассоновский поток (λ=0.5)  | Д10О5 - Отказ НОВОЙ заявке при переполнении             ║")
    print("║ ПЗ2 - Равномерное время обработки  | Д2Б5  - Пакетная обработка по приоритету источника      ║")
    print("║ Бизнес-домен: Система верификации транзакций в банке (антифрод)                              ║")
    print("╚══════════════════════════════════════════════════════════════════════════════════════════════╝")


def display_system_state(state, config, step):
    print(f"\n{'═' * 100}")
    print(f"ШАГ {step:3d} │ Время: {state['time']:7.2f} │ Транзакций: {state['statistics']['total_transactions']:3d} │ "
          f"Отказов: {state['statistics']['rejected_transactions']:3d} │ P(отк): {state['statistics']['rejection_rate'] * 100:5.1f}%")
    print('═' * 100)

    # БУФЕР
    print("БУФЕР (Д10З2 - FIFO):")
    buffer_count = len(state['buffer'])
    buffer_capacity = config['buffer_capacity']

    filled = '█' * buffer_count
    empty = '░' * (buffer_capacity - buffer_count)
    print(f"   [{filled}{empty}] {buffer_count}/{buffer_capacity}")

    if state['buffer']:
        print("   Содержимое:")
        for i, trans in enumerate(state['buffer'][:5]):
            wait_time = state['time'] - trans.timestamp if hasattr(trans, 'timestamp') else 0
            print(f"     {i + 1:2d}. {trans.id:8} (от {trans.source_id:2}, ждет: {wait_time:5.2f})")
        if len(state['buffer']) > 5:
            print(f"     ... и ещё {len(state['buffer']) - 5} транзакций")
    else:
        print("   (пусто)")

    # СЕРВЕРЫ
    print(f"\nСЕРВЕРЫ (Д2П1 - приоритет по номеру):")
    for server in state['servers']:
        status = "🟢 Свободен" if not server['busy'] else "🔴 Занят"
        if server['current_transaction']:
            trans_id = server['current_transaction']
            source_id = trans_id.split('_')[0] if '_' in trans_id else '?'
            print(f"   {server['id']:8} - {status:12} → {trans_id:8} (от {source_id:2})")
        else:
            print(f"   {server['id']:8} - {status:12}")

    # ПАКЕТНАЯ ОБРАБОТКА (Д2Б5)
    if state['current_packet_source']:
        print(f"\nАКТИВНЫЙ ПАКЕТ (Д2Б5 - приоритет по источнику):")
        print(f"   Источник: {state['current_packet_source']} (самый приоритетный в буфере)")
        packet_size = len(state['current_packet'])

        if packet_size > 0:
            print(f"   Размер пакета: {packet_size} транзакций")
            print("   Содержимое пакета:")
            for i, trans in enumerate(state['current_packet'][:3]):
                print(f"     {i + 1:2d}. {trans.id}")
            if packet_size > 3:
                print(f"     ... и ещё {packet_size - 3} транзакций")

            active_servers = [s['id'] for s in state['servers']
                              if s['busy'] and s['current_transaction']
                              and any(s['current_transaction'] == t.id for t in state['current_packet'])]
            if active_servers:
                print(f"   Обрабатывают серверы: {', '.join(active_servers)}")
        else:
            print("   Пакет полностью обработан, ожидается формирование нового")
    elif state['buffer'] and not any(s['busy'] for s in state['servers']):
        print(f"\nГОТОВНОСТЬ К ПАКЕТНОЙ ОБРАБОТКЕ:")
        print("   При освобождении сервера будет сформирован пакет от самого приоритетного источника")
        sources_in_buffer = set(t.source_id for t in state['buffer'])
        if sources_in_buffer:
            priority_order = sorted(sources_in_buffer)
            print(f"   Источники в буфере: {', '.join(priority_order)}")
            print(f"   Первый по приоритету: {priority_order[0]}")


def display_event_calendar(events, current_time):
    if not events:
        return

    print(f"\nКАЛЕНДАРЬ СОБЫТИЙ (последние {len(events)}):")
    print('─' * 100)
    print(f"{'Время':<8} {'Событие':<25} {'Транзакция':<12} {'Детали':<30}")
    print('─' * 100)

    for event in events[-10:]:
        time = event.get('time', 0)
        e_type = event.get('type', '')
        trans = event.get('transaction_id', '')

        description = ""
        if e_type == 'GENERATE':
            description = f"Генерация от {event.get('source_id', '')}"
        elif e_type == 'BUFFER_ENTRY':
            description = f"Добавлена в буфер (Д10З2)"
        elif e_type == 'SERVED_DIRECT':
            description = f"Направлена на сервер {event.get('server_id', '')}"
        elif e_type == 'REJECTED':
            description = f"ОТКАЗ (Д10О5) - буфер полон"
        elif e_type == 'SERVICE_START':
            wait = event.get('wait_time', 0)
            description = f"Начало обработки (ожидание: {wait:.2f})"
        elif e_type == 'SERVICE_END':
            service = event.get('service_time', 0)
            system = event.get('system_time', 0)
            description = f"Завершено (обр: {service:.2f}, в системе: {system:.2f})"
        elif e_type == 'PACKET_FORMED':
            source = event.get('source_id', '')
            size = event.get('packet_size', 0)
            description = f"Пакет сформирован (Д2Б5): {source}, {size} шт."

        print(f"{time:<8.2f} {e_type:<25} {trans:<12} {description:<30}")


def display_automated_results(sim, config):
    print("\n" + "═" * 100)
    print("АВТОМАТИЧЕСКИЙ РЕЖИМ (ОР1 - сводная таблица результатов)")
    print("═" * 100)

    print("\n⏱ПАРАМЕТРЫ СИМУЛЯЦИИ:")
    print(f"   • Общее время: {sim.current_time:.2f}")
    print(f"   • Транзакций обработано: {sim.statistics.total_transactions}")
    print(f"   • Отказов: {sim.statistics.rejected_transactions}")
    print(f"   • Вероятность отказа: {sim.statistics.get_rejection_rate() * 100:.1f}%")

    # ТАБЛИЦА 1: Источники
    print("\n" + "─" * 90)
    print("ТАБЛИЦА 1: ХАРАКТЕРИСТИКИ ИСТОЧНИКОВ")
    print("─" * 90)
    print(f"{'Источник':<8} {'Сген.':<6} {'Отк.':<6} {'Pотк,%':<8} {'Tпреб':<8} {'Tож':<8} "
          f"{'Tобс':<8} {'Дож':<8} {'Добс':<8}")
    print("─" * 90)

    total_generated = 0
    total_rejected = 0
    total_system_time = 0
    total_wait_time = 0

    for source_id in sorted(sim.statistics.source_stats.keys()):
        stats = sim.statistics.get_source_statistics(source_id)
        total_generated += stats['generated']
        total_rejected += stats['rejected']
        total_system_time += stats['avg_system_time'] * stats['completed'] if stats['completed'] > 0 else 0
        total_wait_time += stats['avg_wait_time'] * stats['completed'] if stats['completed'] > 0 else 0

        print(f"{source_id:<8} {stats['generated']:<6} {stats['rejected']:<6} "
              f"{stats['rejection_rate'] * 100:<8.1f} {stats['avg_system_time']:<8.2f} "
              f"{stats['avg_wait_time']:<8.2f} {stats['avg_service_time']:<8.2f} "
              f"{stats['var_wait_time']:<8.2f} {stats['var_service_time']:<8.2f}")

    avg_system = total_system_time / (total_generated - total_rejected) if (total_generated - total_rejected) > 0 else 0
    avg_wait = total_wait_time / (total_generated - total_rejected) if (total_generated - total_rejected) > 0 else 0

    print("─" * 90)
    print(f"{'ИТОГО':<8} {total_generated:<6} {total_rejected:<6} "
          f"{(total_rejected / total_generated * 100) if total_generated > 0 else 0:<8.1f} "
          f"{avg_system:<8.2f} {avg_wait:<8.2f}")

    # ТАБЛИЦА 2: Серверы
    print("\n" + "─" * 60)
    print("ТАБЛИЦА 2: ХАРАКТЕРИСТИКИ СЕРВЕРОВ")
    print("─" * 60)
    print(f"{'Сервер':<10} {'Обработано':<12} {'Время работы':<14} {'Кисп,%':<10}")
    print("─" * 60)

    total_processed = 0
    total_busy = 0

    for server in config['servers']:
        server_id = server['id']
        stats = sim.statistics.get_server_statistics(server_id, sim.current_time)
        total_processed += stats['processed']
        total_busy += stats['busy_time']

        utilization = (stats['busy_time'] / sim.current_time * 100) if sim.current_time > 0 else 0
        print(f"{server_id:<10} {stats['processed']:<12} {stats['busy_time']:<14.2f} {utilization:<10.1f}")

    avg_utilization = (total_busy / sim.current_time / len(config['servers']) * 100) if sim.current_time > 0 else 0
    print("─" * 60)
    print(f"{'СРЕДНЕЕ':<10} {total_processed:<12} {total_busy:<14.2f} {avg_utilization:<10.1f}")

    return avg_utilization, sim.statistics.get_rejection_rate()


'''def display_economic_analysis(config, utilization, rejection_rate):
    print("\n" + "═" * 100)
    print("ЭКОНОМИЧЕСКОЕ ОБОСНОВАНИЕ")
    print("═" * 100)

    # Стоимость компонентов (примерные цены)
    server_cost = 50000  # рублей за сервер
    buffer_slot_cost = 10000  # рублей за место в буфере
    transaction_value = 1000  # рублей средняя ценность транзакции

    server_count = len(config['servers'])
    buffer_capacity = config['buffer_capacity']

    total_cost = server_count * server_cost + buffer_capacity * buffer_slot_cost

    estimated_transactions_per_hour = 1000
    lost_transactions_per_hour = estimated_transactions_per_hour * rejection_rate
    lost_revenue_per_hour = lost_transactions_per_hour * transaction_value

    print(f"\nРАСЧЕТ ЭФФЕКТИВНОСТИ КОНФИГУРАЦИИ:")
    print(f"   • Количество серверов: {server_count} x {server_cost:,} ₽ = {server_count * server_cost:,} ₽")
    print(f"   • Буфер: {buffer_capacity} мест x {buffer_slot_cost:,} ₽ = {buffer_capacity * buffer_slot_cost:,} ₽")
    print(f"   • Общая стоимость системы: {total_cost:,} ₽")
    print(f"\n   • Загрузка серверов: {utilization:.1f}%")
    print(f"   • Вероятность отказа: {rejection_rate * 100:.1f}%")
    print(f"   • Потерянные транзакции в час: {lost_transactions_per_hour:.0f}")
    print(f"   • Потерянная выручка в час: {lost_revenue_per_hour:,.0f} ₽")

    print(f"\nРЕКОМЕНДАЦИИ ПО ОПТИМИЗАЦИИ:")

    if rejection_rate > 0.1:
        print("      Вероятность отказа превышает допустимые 10%")
        print("      Варианты улучшения:")
        print(f"      1. Увеличить буфер с {buffer_capacity} до {buffer_capacity + 2} мест")
        print(f"         Стоимость: +{2 * buffer_slot_cost:,} ₽")
        print(f"         Ожидаемое улучшение: P(отк) ≈ {(rejection_rate * 0.7) * 100:.1f}%")

        print(f"      2. Добавить сервер (всего {server_count + 1})")
        print(f"         Стоимость: +{server_cost:,} ₽")
        print(f"         Ожидаемое улучшение: P(отк) ≈ {(rejection_rate * 0.5) * 100:.1f}%")

        print(f"      3. Увеличить буфер и добавить сервер")
        print(f"         Стоимость: +{server_cost + 2 * buffer_slot_cost:,} ₽")
        print(f"         Ожидаемое улучшение: P(отк) ≈ {(rejection_rate * 0.3) * 100:.1f}%")
    else:
        print("   ✅ Текущая конфигурация удовлетворяет требованиям по отказам")

    if utilization < 0.9:
        print(f"\n   ⚠️  Загрузка серверов {utilization * 100:.1f}% ниже оптимальной 90%")
        print("      Рекомендуется уменьшить количество серверов или увеличить нагрузку")
    elif utilization > 0.95:
        print(f"\n   ⚠️  Загрузка серверов {utilization * 100:.1f}% близка к предельной")
        print("      Рекомендуется добавить резервный сервер для пиковых нагрузок")
    else:
        print(f"\n   ✅ Загрузка серверов оптимальна ({utilization * 100:.1f}%)")
'''

def main():
    try:
        with open('config.json', 'r') as f:
            config = json.load(f)
    except FileNotFoundError:
        print("❌ ОШИБКА: Файл config.json не найден!")
        return

    display_header()

    print(f"\n{'─' * 50}")
    print("РЕЖИМ 1: ПОШАГОВЫЙ (ОД3 - временные диаграммы)")
    print("Команды: Enter - следующий шаг, q - выход, a - автоматический режим")
    print(f"{'─' * 50}")

    sim_step = Simulation(config, verbose=False)
    sim_step.running = True
    step_count = 0

    try:
        while True:
            cmd = input(f"\nШаг {step_count:3d} [Enter/q/a] >>> ").strip()

            if cmd.lower() == 'q':
                print("Выход из пошагового режима...")
                break
            elif cmd.lower() == 'a':
                print("Переход к автоматическому режиму...")
                break

            if not sim_step.run_step():
                print("Симуляция завершена (достигнуто максимальное время)")
                break

            state = sim_step.get_state()
            display_system_state(state, config, step_count)

            events = sim_step.statistics.get_event_history(15)
            display_event_calendar(events, state['time'])

            step_count += 1

            # Ограничиваем пошаговый режим 50 шагами
            if step_count >= 50:
                print("\n⚠️  Достигнуто максимальное количество шагов (50)")
                print("   Переход к автоматическому режиму...")
                break

    except KeyboardInterrupt:
        print("\n\nПрервано пользователем")
        return

    # Автоматический режим
    print(f"\n{'─' * 50}")
    print("РЕЖИМ 2: АВТОМАТИЧЕСКИЙ (ОР1 - сводные таблицы)")
    print("Выполняется симуляция с точностью 10% и доверительной вероятностью 90%...")
    print(f"{'─' * 50}")

    sim_auto = Simulation(config, verbose=False)
    sim_auto.running = True
    sim_auto.run_automated(target_accuracy=0.1, confidence=0.9)

    sim_auto.statistics.set_simulation_time(0.0, sim_auto.current_time)

    utilization, rejection_rate = display_automated_results(sim_auto, config)

    '''display_economic_analysis(config, utilization, rejection_rate)'''

    results = {
        'simulation_time': sim_auto.current_time,
        'total_transactions': sim_auto.statistics.total_transactions,
        'rejected_transactions': sim_auto.statistics.rejected_transactions,
        'rejection_rate': sim_auto.statistics.get_rejection_rate(),
        'source_statistics': {
            source_id: sim_auto.statistics.get_source_statistics(source_id)
            for source_id in sim_auto.statistics.source_stats.keys()
        },
        'server_statistics': {
            server['id']: sim_auto.statistics.get_server_statistics(server['id'], sim_auto.current_time)
            for server in config['servers']
        }
    }

    with open('simulation_results.json', 'w') as f:
        json.dump(results, f, indent=2)

    print(f"\nРезультаты сохранены в simulation_results.json")
    print("=" * 100)
    print("Программа успешно завершена!")
    print("=" * 100)


if __name__ == "__main__":
    main()
