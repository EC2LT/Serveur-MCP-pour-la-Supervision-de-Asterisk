# asterisk/cdr_client.py
import logging
from config import settings

logger = logging.getLogger(__name__)


class CDRClient:
    """Client pour interroger la base CDR d'Asterisk (MySQL/MariaDB)."""

    def __init__(self):
        self.host = settings.CDR_DB_HOST
        self.user = settings.CDR_DB_USER
        self.password = settings.CDR_DB_PASSWORD
        self.database = settings.CDR_DB_NAME

    def query(self, sql: str, params: tuple = None) -> list[dict]:
        """Exécute une requête SQL et retourne une liste de dictionnaires."""
        try:
            import mysql.connector
            conn = mysql.connector.connect(
                host=self.host, user=self.user,
                password=self.password, database=self.database,
                connection_timeout=5,
            )
            cursor = conn.cursor(dictionary=True)
            cursor.execute(sql, params or ())
            rows = cursor.fetchall()
            cursor.close()
            conn.close()
            return rows
        except Exception as e:
            logger.error(f"Erreur CDR : {e}")
            return []


cdr = CDRClient()
