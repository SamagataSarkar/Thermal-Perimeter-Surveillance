import unittest

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect

from backend.app.db.session import create_database_engine


class DatabaseMigrationTests(unittest.TestCase):
    def test_initial_migration_creates_all_tables(self):
        database_url = "sqlite:///migration_test.db"
        config = Config("alembic.ini")
        config.set_main_option("sqlalchemy.url", database_url)
        command.upgrade(config, "head")
        engine = create_database_engine(database_url)
        try:
            self.assertEqual(
                set(inspect(engine).get_table_names()) - {"alembic_version"},
                {
                    "video_sources", "monitoring_sessions", "geofences", "events",
                    "snapshots", "system_metrics", "event_audit_logs", "alerts",
                    "application_settings",
                },
            )
        finally:
            engine.dispose()
            import os
            if os.path.exists("migration_test.db"):
                os.remove("migration_test.db")


if __name__ == "__main__":
    unittest.main()
