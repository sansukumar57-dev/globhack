PRESET_BENCHMARKS = [
    {
        "id": "rate_limiter",
        "title": "Sliding Window Rate Limiter Bug",
        "description": "Fix an off-by-one window calculation bug where requests at the exact boundary are falsely rejected.",
        "target_function": "is_allowed",
        "prompt": "Fix is_allowed in RateLimiter so that timestamps equal to (current_time - window_seconds) are properly evicted and not counted.",
        "original_code": '''import time
from typing import Dict, List

class SystemMetrics:
    """Tracks global gateway health metrics."""
    def __init__(self):
        self.total_requests = 0
        self.rejected_requests = 0

    def record_accept(self):
        self.total_requests += 1

    def record_reject(self):
        self.rejected_requests += 1

    def get_summary(self) -> Dict[str, int]:
        return {
            "total": self.total_requests,
            "rejected": self.rejected_requests
        }


class RateLimiter:
    """In-memory sliding window rate limiter for API Gateways."""

    def __init__(self, limit: int, window_seconds: float):
        self.limit = limit
        self.window_seconds = window_seconds
        self.user_history: Dict[str, List[float]] = {}
        self.metrics = SystemMetrics()

    def get_user_count(self, user_id: str) -> int:
        return len(self.user_history.get(user_id, []))

    def reset(self, user_id: str):
        if user_id in self.user_history:
            del self.user_history[user_id]

    def is_allowed(self, user_id: str, current_time: float) -> bool:
        if user_id not in self.user_history:
            self.user_history[user_id] = []

        history = self.user_history[user_id]
        cutoff = current_time - self.window_seconds

        # BUG: Uses > cutoff instead of >= cutoff, keeping old boundary timestamps!
        # Should filter: keep only timestamps that are strictly greater than cutoff: t > cutoff
        valid_requests = [t for t in history if t >= cutoff]
        self.user_history[user_id] = valid_requests

        if len(valid_requests) >= self.limit:
            self.metrics.record_reject()
            return False

        valid_requests.append(current_time)
        self.metrics.record_accept()
        return True
''',
        "test_code": '''def run_test(module_dict):
    RateLimiter = module_dict["RateLimiter"]
    limiter = RateLimiter(limit=2, window_seconds=10.0)
    
    # Send request at t=0 and t=5
    assert limiter.is_allowed("alice", 0.0) == True
    assert limiter.is_allowed("alice", 5.0) == True
    # At t=6, limit reached
    assert limiter.is_allowed("alice", 6.0) == False
    
    # At t=10.0, the t=0 request (10.0 - 10.0 = 0.0) should be evicted
    # so alice should now be allowed!
    allowed = limiter.is_allowed("alice", 10.0)
    assert allowed == True, f"Expected allowed=True at t=10.0, got {allowed}"
    return "All tests passed! Rate limiter edge case correctly resolved."
'''
    },
    {
        "id": "e_commerce_discount",
        "title": "E-Commerce Cart Price & Discount Edge Cases",
        "description": "Fix calculate_total to handle None discount, clamp negative discounts to 0, and compute correct 2-decimal rounded tax.",
        "target_function": "calculate_total",
        "prompt": "Fix calculate_total to safely handle discount=None (treat as 0), ensure discount never exceeds subtotal or drops below 0, and round final tax to 2 decimal places.",
        "original_code": '''from dataclasses import dataclass
from typing import List, Optional

@dataclass
class CartItem:
    item_id: str
    name: str
    unit_price: float
    quantity: int

class OrderReceipt:
    def __init__(self, order_id: str):
        self.order_id = order_id
        self.is_printed = False

    def print_receipt(self):
        self.is_printed = True


class CheckoutService:
    """Calculates checkout totals and handles coupon deductions."""

    def __init__(self, tax_rate: float = 0.08):
        self.tax_rate = tax_rate

    def validate_cart(self, items: List[CartItem]) -> bool:
        if not items:
            return False
        return all(i.quantity > 0 and i.unit_price >= 0 for i in items)

    def calculate_subtotal(self, items: List[CartItem]) -> float:
        return sum(item.unit_price * item.quantity for item in items)

    def calculate_total(self, items: List[CartItem], discount: Optional[float] = None) -> float:
        subtotal = self.calculate_subtotal(items)
        
        # BUG: Crashes if discount is None, or allows negative discount
        discounted_subtotal = subtotal - discount
        
        tax = discounted_subtotal * self.tax_rate
        return round(discounted_subtotal + tax, 2)
''',
        "test_code": '''def run_test(module_dict):
    CheckoutService = module_dict["CheckoutService"]
    CartItem = module_dict["CartItem"]
    svc = CheckoutService(tax_rate=0.10)
    items = [CartItem("1", "Widget", 100.0, 1)]
    
    # Test 1: None discount
    t1 = svc.calculate_total(items, None)
    assert t1 == 110.0, f"Expected 110.0, got {t1}"
    
    # Test 2: Valid discount 20.0 -> subtotal 80.0 + 8.0 tax = 88.0
    t2 = svc.calculate_total(items, 20.0)
    assert t2 == 88.0, f"Expected 88.0, got {t2}"
    
    # Test 3: Excessive discount 150.0 -> capped at subtotal -> total 0.0
    t3 = svc.calculate_total(items, 150.0)
    assert t3 == 0.0, f"Expected 0.0, got {t3}"
    return "All tests passed! Cart calculation robust against null and extreme discount values."
'''
    },
    {
        "id": "lru_ttl_cache",
        "title": "LRU Cache TTL Expiration Bug",
        "description": "Fix get() method to evict expired keys on access and return None instead of returning stale data.",
        "target_function": "get",
        "prompt": "Fix the get method in TTLCache so that if current_time exceeds the item's expire_at timestamp, the item is deleted and None is returned.",
        "original_code": '''import time
from typing import Any, Optional, Dict

class CacheMetrics:
    def __init__(self):
        self.hits = 0
        self.misses = 0

    def record_hit(self):
        self.hits += 1

    def record_miss(self):
        self.misses += 1


class TTLCache:
    """Key-value cache with per-item time-to-live."""

    def __init__(self, default_ttl_seconds: float = 60.0):
        self.default_ttl = default_ttl_seconds
        self.store: Dict[str, Dict[str, Any]] = {}
        self.metrics = CacheMetrics()

    def set(self, key: str, value: Any, ttl: Optional[float] = None, current_time: Optional[float] = None):
        t = current_time if current_time is not None else time.time()
        expire = t + (ttl if ttl is not None else self.default_ttl)
        self.store[key] = {"val": value, "expire_at": expire}

    def clear(self):
        self.store.clear()

    def get(self, key: str, current_time: Optional[float] = None) -> Optional[Any]:
        t = current_time if current_time is not None else time.time()
        if key not in self.store:
            self.metrics.record_miss()
            return None

        entry = self.store[key]
        # BUG: Returns entry value without checking expiration against t!
        self.metrics.record_hit()
        return entry["val"]
''',
        "test_code": '''def run_test(module_dict):
    TTLCache = module_dict["TTLCache"]
    cache = TTLCache(default_ttl_seconds=5.0)
    
    # Store key at t=100.0, expires at t=105.0
    cache.set("session_123", "user_active", ttl=5.0, current_time=100.0)
    
    # Access at t=102.0 (valid)
    assert cache.get("session_123", current_time=102.0) == "user_active"
    
    # Access at t=106.0 (expired)
    val = cache.get("session_123", current_time=106.0)
    assert val is None, f"Expected None for expired item, got {val}"
    assert "session_123" not in cache.store, "Expired key was not purged from cache store!"
    return "All tests passed! TTL cache eviction operates properly on expiration."
'''
    }
]
