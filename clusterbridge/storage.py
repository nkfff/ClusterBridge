import sqlite3
from pathlib import Path

from .models import ConnectionProfile


class ProfileStore:
    def __init__(self, database_path: Path | None = None) -> None:
        self.database_path = database_path or (
            Path.home() / ".clusterbridge" / "clusterbridge.sqlite3"
        )
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(self.database_path)
        self._connection.row_factory = sqlite3.Row
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS connections (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                host TEXT NOT NULL,
                username TEXT NOT NULL,
                port INTEGER NOT NULL,
                default_path TEXT NOT NULL
            )
            """
        )
        self._connection.commit()

    def list_profiles(self) -> list[ConnectionProfile]:
        rows = self._connection.execute(
            "SELECT id, name, host, username, port, default_path "
            "FROM connections ORDER BY name"
        ).fetchall()
        return [ConnectionProfile(**dict(row)) for row in rows]

    def save_profile(self, profile: ConnectionProfile) -> None:
        self._connection.execute(
            """
            INSERT INTO connections (id, name, host, username, port, default_path)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name=excluded.name, host=excluded.host,
                username=excluded.username, port=excluded.port,
                default_path=excluded.default_path
            """,
            (profile.id, profile.name, profile.host, profile.username,
             profile.port, profile.default_path),
        )
        self._connection.commit()

    def delete_profile(self, profile_id: str) -> None:
        self._connection.execute(
            "DELETE FROM connections WHERE id = ?", (profile_id,)
        )
        self._connection.commit()

    def close(self) -> None:
        self._connection.close()
