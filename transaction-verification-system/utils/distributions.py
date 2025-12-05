import random
import math

def exponential(rate: float) -> float:
    """Генерация времени по экспоненциальному распределению"""
    if rate <= 0:
        return float('inf')
    return -math.log(1.0 - random.random()) / rate