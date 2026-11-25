"""Disposable browser-test database; never migrates the developer's database."""
import os
from pathlib import Path
import signal
import subprocess
import sys
from tempfile import TemporaryDirectory

root = Path(__file__).resolve().parents[1]
port = int(os.environ.get("BROWSER_TEST_PORT", "5174"))
with TemporaryDirectory(prefix="tanaspace-browser-") as directory:
    env = {**os.environ, "POSTGRES_HOST": "", "DJANGO_DEBUG": "true",
           "DJANGO_DB_PATH": str(Path(directory) / "browser.sqlite3"),
           "DJANGO_ALLOWED_HOSTS": "localhost,127.0.0.1",
           "DEV_DEMO_ENABLED": os.environ.get("BROWSER_TEST_DEV_DEMO", "false")}
    subprocess.run([sys.executable, "manage.py", "migrate", "--noinput"], cwd=root, env=env, check=True)
    process = subprocess.Popen([sys.executable, "manage.py", "runserver", f"127.0.0.1:{port}", "--noreload"], cwd=root, env=env)
    def stop(*_):
        process.terminate()
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        process.wait()
    finally:
        process.terminate()
        process.wait()
