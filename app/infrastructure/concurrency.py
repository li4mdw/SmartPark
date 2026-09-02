from collections.abc import Callable
from functools import partial
from typing import Any, TypeVar

import anyio


ResultT = TypeVar("ResultT")


class InferenceExecutor:
    """Run blocking inference in worker threads with a process-wide limit."""

    def __init__(self, max_concurrency: int) -> None:
        if max_concurrency < 1:
            raise ValueError("INFERENCE_CONCURRENCY must be at least 1")
        self.max_concurrency = max_concurrency
        self._semaphore = anyio.Semaphore(max_concurrency)

    async def run(
        self,
        function: Callable[..., ResultT],
        *args: Any,
        **kwargs: Any,
    ) -> ResultT:
        call = partial(function, *args, **kwargs)
        async with self._semaphore:
            return await anyio.to_thread.run_sync(call)
