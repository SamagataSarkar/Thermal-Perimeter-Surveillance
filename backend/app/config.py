import os


DATABASE_URL = os.getenv("THERMAL_DATABASE_URL", "sqlite:///./backend-data/thermal.db")
SNAPSHOT_DIRECTORY = os.getenv("THERMAL_SNAPSHOT_DIRECTORY", "snapshots")
