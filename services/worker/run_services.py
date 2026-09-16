"""Start the API and both workers with one database/configuration; exit on child failure."""
import argparse
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from dotenv import load_dotenv

from runtime import configure_environment


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-port", type=int, default=8010)
    parser.add_argument("--env-file", type=Path, help="Optional existing local configuration file")
    parser.add_argument("--check", action="store_true", help="Validate configuration without starting services")
    args = parser.parse_args()
    if args.env_file is not None:
        if not args.env_file.is_file():
            raise RuntimeError("指定的配置文件不存在")
        load_dotenv(args.env_file.resolve(), override=False)
    root = configure_environment()
    from app.core.config import get_settings
    from app.main import validate_runtime_settings
    from qwen_analysis import QwenConfig

    settings = get_settings()
    validate_runtime_settings()
    QwenConfig.from_environment()  # Fail clearly before accepting chats that cannot be analyzed.
    os.environ["DATABASE_URL"] = settings.database_url
    if args.check:
        print("API 与两个 Worker 配置校验通过；实际模型连通性需另行验证。")
        return 0
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    from alembic.runtime.migration import MigrationContext
    from app.db.session import engine

    with engine.connect() as connection:
        current = set(MigrationContext.configure(connection).get_current_heads())
    if current != set(ScriptDirectory.from_config(Config("alembic.ini")).get_heads()):
        raise RuntimeError("数据库未迁移到最新版本。请先备份，再执行 alembic upgrade head。")
    commands = [
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(args.api_port)],
        [sys.executable, str(root / "services/worker/analysis_worker.py")],
        [sys.executable, str(root / "services/worker/notification_worker.py")],
    ]
    children: list[subprocess.Popen] = []
    def stop(_signum, _frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, stop)
    try:
        for command in commands:
            children.append(subprocess.Popen(command))
        while True:
            for child in children:
                if child.poll() is not None:
                    print("一个服务已退出，正在停止其他服务。请检查日志后重新启动。", file=sys.stderr)
                    return 1
            time.sleep(1)
    except KeyboardInterrupt:
        return 0
    finally:
        for child in children:
            if child.poll() is None:
                child.terminate()
        for child in children:
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()


if __name__ == "__main__":
    raise SystemExit(main())
