"""Disposable browser-test database; never migrates the developer's database."""
import os
from pathlib import Path
import signal
import subprocess
import sys
from tempfile import TemporaryDirectory

root = Path(__file__).resolve().parents[1]
with TemporaryDirectory(prefix="tanaspace-browser-") as directory:
    env = {**os.environ, "POSTGRES_HOST": "", "DJANGO_DEBUG": "true",
           "DJANGO_DB_PATH": str(Path(directory) / "browser.sqlite3"),
           "DJANGO_ALLOWED_HOSTS": "localhost,127.0.0.1"}
    subprocess.run([sys.executable, "manage.py", "migrate", "--noinput"], cwd=root, env=env, check=True)
    process = subprocess.Popen([sys.executable, "manage.py", "runserver", "127.0.0.1:5174", "--noreload"], cwd=root, env=env)
    def stop(*_):
        process.terminate()
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        process.wait()
    finally:
        process.terminate()
        process.wait()
