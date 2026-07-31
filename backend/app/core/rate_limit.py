"""Rate limiting via slowapi (in-memory storage for local dev/single-instance;
swap the storage_uri to a Redis URL in production for multi-instance
correctness — see docs/06-deployment-security.md §6.3).
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
