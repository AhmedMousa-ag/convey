import logging
import os

_perf_logger = logging.getLogger("convey.performance")
_perf_logger.setLevel(logging.INFO)

_log_path = os.path.join(os.path.dirname(__file__), "..", "..", "performance.log")
_handler = logging.FileHandler(_log_path)
_handler.setFormatter(logging.Formatter("%(asctime)s | %(message)s"))
_perf_logger.addHandler(_handler)
_perf_logger.propagate = False


def perf_log(msg: str):
    _perf_logger.info(msg)
