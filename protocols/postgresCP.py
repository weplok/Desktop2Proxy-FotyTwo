import os
import subprocess
import sys
import shutil


class PQSLConnection:
    def __init__(self, host: str, port: int, user: str, password: str, dbname: str = "postgres"):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.dbname = dbname

        print(f"[INFO] Инициализация подключения к PostgreSQL {user}@{host}:{port}/{dbname}")

        # Ищем psql.exe в PATH
        if shutil.which("psql.exe"):
            print("[INFO] Найден psql.exe, запускаю консоль управления...")
            self.run_psql()
        else:
            # Попробуем pgAdmin4
            pgadmin_path = shutil.which("pgadmin4.exe")
            if pgadmin_path:
                print("[INFO] Найден pgAdmin4, запускаю...")
                self.run_pgadmin(pgadmin_path)
            else:
                print("[ERROR] Не найден ни psql.exe, ни pgAdmin4.exe. Установите PostgreSQL client utilities.")

    def run_psql(self):
        """
        Запуск psql на Windows
        """
        env = os.environ.copy()
        env["PGPASSWORD"] = self.password  # psql берёт пароль отсюда

        cmd = [
            "psql.exe",
            "-h", self.host,
            "-p", str(self.port),
            "-U", self.user,
            "-d", self.dbname
        ]

        print(f"[CMD] {' '.join(cmd)}")
        try:
            subprocess.run(cmd, env=env)
        except Exception as e:
            print(f"[ERROR] Ошибка при запуске psql: {e}")
            sys.exit(1)

    def run_pgadmin(self, pgadmin_path):
        """
        Запуск pgAdmin4
        """
        try:
            subprocess.Popen([pgadmin_path])
        except Exception as e:
            print(f"[ERROR] Ошибка при запуске pgAdmin4: {e}")
            sys.exit(1)


if __name__ == "__main__":
    # пример
    conn = PQSLConnection(
        host="127.0.0.1",
        port=5433,
        user="pguser",
        password="285587"
    )
