import logging, sys
from logging.handlers import QueueHandler, QueueListener
from queue import Queue
from pathlib import Path

def setup_logging(save_dir: Path, level=logging.DEBUG):
    save_dir = Path(save_dir)
    save_dir.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("biomass")
    logger.setLevel(level)

    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%H:%M:%S"
    )

    fh = logging.FileHandler(save_dir / "training.log", mode="a")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)

    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(fmt)

    queue = Queue(-1)
    qh = QueueHandler(queue)
    logger.addHandler(qh)

    listener = QueueListener(queue, fh, ch, respect_handler_level=True)
    listener.start()

    return logger, listener
