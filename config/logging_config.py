# config/logging_config.py
import logging
import os


def setup_logging(log_file: str = "logs/audit.log"):
    """Configure le logging applicatif + le journal d'audit."""
    os.makedirs(os.path.dirname(log_file), exist_ok=True)

    # Logger applicatif (console)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    # Logger d'audit (fichier)
    audit = logging.getLogger("audit")
    audit.setLevel(logging.INFO)
    handler = logging.FileHandler(log_file)
    handler.setFormatter(logging.Formatter("%(asctime)s - %(message)s"))
    audit.addHandler(handler)
    audit.propagate = False

    return audit
