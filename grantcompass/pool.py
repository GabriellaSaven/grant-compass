"""A thread pool that carries the caller's context (which organisation's database and logs) into every worker,
so parallel work (Discover's searches and assessments) always reads and writes the right organisation."""

import contextvars
from concurrent.futures import ThreadPoolExecutor


class ContextPool(ThreadPoolExecutor):
    def submit(self, fn, /, *args, **kwargs):
        return super().submit(contextvars.copy_context().run, fn, *args, **kwargs)
