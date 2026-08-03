import asyncio
import logging
from typing import Callable, Dict
_logger = logging.getLogger(__name__)

class EventEmitter:

    def __init__(self):
        self._listeners: Dict[str, list] = {}

    def on(self, event_name: str, handler: Callable | None=None):

        def _add(fn: Callable) -> Callable:
            self._listeners.setdefault(event_name, []).append(fn)
            return fn
        if handler is not None:
            return _add(handler)
        return _add

    def off(self, event_name: str, handler: Callable):
        bucket = self._listeners.get(event_name)
        if bucket and handler in bucket:
            bucket.remove(handler)

    def once(self, event_name: str, handler: Callable | None=None):

        def _wrap(fn: Callable) -> Callable:

            def _one_shot(*args, **kwargs):
                self.off(event_name, _one_shot)
                return fn(*args, **kwargs)

            async def _one_shot_async(*args, **kwargs):
                self.off(event_name, _one_shot_async)
                return await fn(*args, **kwargs)
            wrapped = _one_shot_async if asyncio.iscoroutinefunction(fn) else _one_shot
            self._listeners.setdefault(event_name, []).append(wrapped)
            return fn
        if handler is not None:
            return _wrap(handler)
        return _wrap

    def emit(self, event_name: str, *args, **kwargs):
        for handler in list(self._listeners.get(event_name, [])):
            if asyncio.iscoroutinefunction(handler):
                task = asyncio.create_task(handler(*args, **kwargs))
                task.add_done_callback(_task_error_cb)
            else:
                try:
                    handler(*args, **kwargs)
                except Exception as exc:
                    _logger.error('Handler error on event %r: %s', event_name, exc, exc_info=True)

def _task_error_cb(task: asyncio.Task):
    if not task.cancelled() and (exc := task.exception()) is not None:
        _logger.error('Unhandled exception in async event handler', exc_info=exc)
