# tests/test_projects_intro.py
"""Portfolio projects intro column migration."""
from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path


class ProjectsIntroTests(unittest.TestCase):
    def test_migrate_projects_schema_adds_intro_and_backfills(self) -> None:
        from app import _migrate_projects_schema

        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "test.db"
            conn = sqlite3.connect(db)
            conn.execute(
                """
                CREATE TABLE projects (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    category TEXT NOT NULL,
                    image_url TEXT NOT NULL,
                    description TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                INSERT INTO projects (title, category, image_url, description, created_at)
                VALUES ('A', 'Cat', '/img.jpg', 'Short intro text', '2026-01-01')
                """
            )
            conn.commit()
            _migrate_projects_schema(conn)
            conn.commit()
            row = conn.execute("SELECT intro, description FROM projects WHERE id = 1").fetchone()
            self.assertEqual(row[0], "Short intro text")
            self.assertEqual(row[1], "Short intro text")
            conn.close()


if __name__ == "__main__":
    unittest.main()
