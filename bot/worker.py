"""A single worker thread draining a FIFO queue: receipts are read one at a time (the GPU has 4 GB)."""
import logging
import queue
import threading
from typing import Callable

log = logging.getLogger(__name__)
_STOP = object()


class Worker:
    def __init__(self, process: Callable[[int], object], deliver: Callable[[object], None]):
        self._process, self._deliver = process, deliver
        self._q: queue.Queue = queue.Queue()
        self._thread = threading.Thread(target=self._run, name="ocr-worker", daemon=True)

    def start(self) -> None:
        self._thread.start()

    def submit(self, receipt_id: int) -> None:
        self._q.put(receipt_id)

    def stop(self, timeout: float | None = 5) -> None:
        self._q.put(_STOP)
        self._thread.join(timeout)

    def join(self) -> None:
        """Block until everything submitted so far has been processed."""
        self._q.join()

    def _run(self) -> None:
        while True:
            item = self._q.get()
            try:
                if item is _STOP:
                    return
                self._deliver(self._process(item))
            except Exception:
                log.exception("receipt %s failed in the worker", item)   # one bad receipt must not stop the queue
            finally:
                self._q.task_done()
