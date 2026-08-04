import logging
import threading
import traceback
from collections import defaultdict
from typing import Callable

from app.events import BusMessage, ModuleId, SignalType


logger = logging.getLogger('rvc_client')


class AppScheduler:
    _instance = None
    _instance_lock = threading.Lock()

    def __init__(self):
        self._lock = threading.RLock()
        self._running = False
        self._threads = {}
        self._shutdown_hooks = []
        self._subscribers = defaultdict(list)

    @classmethod
    def instance(cls):
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    @classmethod
    def reset_for_test(cls):
        with cls._instance_lock:
            if cls._instance is not None and cls._instance._running:
                cls._instance.shutdown()
            cls._instance = None

    @property
    def running(self):
        return self._running

    def start(self):
        with self._lock:
            if self._running:
                return self
            self._running = True
            self.publish(BusMessage(SignalType.STATUS, ModuleId.SCHEDULER, {'state': 'started'}))
            logger.info('scheduler started')
            return self

    def shutdown(self):
        with self._lock:
            if not self._running:
                return self
            self.publish(BusMessage(SignalType.SHUTDOWN, ModuleId.SCHEDULER, {'state': 'stopping'}))
            for hook in reversed(self._shutdown_hooks):
                try:
                    hook()
                except Exception:
                    logger.error('shutdown hook failed:\n%s', traceback.format_exc())
            self._threads.clear()
            self._running = False
            logger.info('scheduler stopped')
            return self

    def subscribe(self, signal: SignalType, callback: Callable[[BusMessage], None]):
        with self._lock:
            self._subscribers[signal].append(callback)
            return callback

    def unsubscribe(self, signal: SignalType, callback: Callable[[BusMessage], None]):
        with self._lock:
            items = self._subscribers.get(signal, [])
            if callback in items:
                items.remove(callback)

    def publish(self, message: BusMessage):
        with self._lock:
            callbacks = list(self._subscribers.get(message.signal, []))
            callbacks.extend(self._subscribers.get(SignalType.LOG, []))
        for callback in callbacks:
            try:
                callback(message)
            except Exception:
                logger.error('bus callback failed signal=%s:\n%s', message.signal, traceback.format_exc())
        return message

    def register_thread(self, name: str, thread: threading.Thread):
        with self._lock:
            self._threads[name] = thread
            logger.debug('thread registered: %s', name)
            return thread

    def unregister_thread(self, name: str):
        with self._lock:
            self._threads.pop(name, None)

    def add_shutdown_hook(self, hook: Callable[[], None]):
        with self._lock:
            self._shutdown_hooks.append(hook)
            return hook

    def thread_names(self):
        with self._lock:
            return list(self._threads.keys())
