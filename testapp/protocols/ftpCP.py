# open_ftp_shortcut.py
import os
import sys
import time
import tempfile
import pathlib
from urllib.parse import quote
import subprocess


class FTPConnection:
    def __init__(self, host, user, password, path="", msg_log=None):
        self.host = host
        self.path = path
        self.username = user
        self.password = password
        self.wait = 0.8
        self.msg_log = msg_log

    def mlog(self, msg):
        if self.msg_log:
            self.msg_log(msg)
        else:
            print(msg)

    def build_ftp_url(self) -> str:
        self.mlog("Генерирую FTP-ссылку...")
        if self.path and not self.path.startswith("/"):
            self.path = "/" + self.path
        if self.username is None:
            creds = ""
        else:
            if self.password is None:
                creds = quote(self.username, safe="")
            else:
                creds = f"{quote(self.username, safe='')}:{quote(self.password, safe='')}"
        netloc = f"{creds + '@' if creds else ''}{self.host}"
        self.mlog("Ссылка сгенерирована!")
        return f"ftp://{netloc}{self.path}"


    def create_lnk(self, shortcut_path: str, target: str, workdir: str = None, icon: str = None) -> bool:
        """
        Попытка создать .lnk через pywin32. Возвращает True при успехе, False если pywin32 не доступен.
        """
        self.mlog("Попытка создать .lnk ярлык...")
        try:
            import pythoncom  # type: ignore
            from win32com.shell import shell, shellcon  # type: ignore
            from win32com.client import Dispatch  # type: ignore
        except Exception:
            self.mlog("Ярлык .lnk не удалось создать.")
            return False

        shell_link = Dispatch('WScript.Shell').CreateShortcut(shortcut_path)
        # У .lnk target обычно executable; мы указываем explorer.exe и аргумент — ftp-URL,
        # чтобы гарантированно открыть в Проводнике:
        shell_link.Targetpath = "explorer.exe"
        shell_link.Arguments = f'"{target}"'
        if workdir:
            shell_link.WorkingDirectory = workdir
        if icon:
            shell_link.IconLocation = icon
        shell_link.save()
        self.mlog("Ярлык .lnk успешно создан!")
        return True


    def create_url(self, shortcut_path: str, url: str) -> None:
        """
        Создаёт .url (Internet Shortcut) файл с содержимым:
        [InternetShortcut]
        URL=ftp://...
        """
        self.mlog("Создание .url ярлыка...")
        with open(shortcut_path, "w", encoding="utf-8") as f:
            f.write("[InternetShortcut]\n")
            f.write(f"URL={url}\n")
        self.mlog("Ярлык .url успешно создан!")


    def open_and_cleanup(self, shortcut_path) -> None:
        """
        Открывает файл (os.startfile) и удаляет его через небольшую паузу.
        wait_seconds можно увеличить, если загрузка проводника медленная.
        """
        self.mlog("Открытие ярлыка FTP-сервера...")
        try:
            self.mlog("Запускаю ярлык...")
            if sys.platform.startswith("win"):
                os.startfile(shortcut_path)
                self.mlog("FTP-сервер запущен (Ожидайте!)")
            else:
                self.mlog("Не удалось запустить ярлык")
                self.mlog("Запускаю ярлык №2...")
                # fallback: открыть в браузере на других ОС
                import webbrowser
                webbrowser.open(shortcut_path)
                self.mlog("FTP-сервер запущен (Ожидайте!)")
        except Exception:
            self.mlog("Не удалось запустить ярлык №2")
            # альтернативный вызов explorer
            if sys.platform.startswith("win"):
                try:
                    self.mlog("Запускаю ярлык №3...")
                    subprocess.Popen(["explorer", shortcut_path])
                    self.mlog("FTP-сервер запущен (Ожидайте!)")
                except Exception:
                    self.mlog("Не удалось запустить ярлык FTP-сервера.")
                    pass
            else:
                self.mlog("Не удалось запустить ярлык FTP-сервера, рекомендуется запускать на Windows.")
                pass

        # Небольшая пауза, чтобы ОС успела использовать файл
        time.sleep(self.wait)
        try:
            self.mlog("Удаляю временный файл ярлыка FTP-сервера...")
            os.remove(shortcut_path)
            self.mlog("Временный ярлык удалён")
        except Exception:
            self.mlog("Не удалось удалить ярлык")
            # если удалить не получилось — бессрочно игнорируем
            pass

    def main(self):
        url = self.build_ftp_url()
        tmpdir = tempfile.gettempdir()
        # имя файла в temp с случайным суффиксом
        base = pathlib.Path(tmpdir) / f"ftp_shortcut_{int(time.time() * 1000)}"
        lnk_path = str(base) + ".lnk"
        url_path = str(base) + ".url"

        created = False
        # сначала попробуем .lnk (требует pywin32); если не получилось — создаём .url
        if sys.platform.startswith("win"):
            try:
                created = self.create_lnk(lnk_path, url)
                if created:
                    shortcut_path = lnk_path
                else:
                    # fallback на .url
                    self.create_url(url_path, url)
                    shortcut_path = url_path
            except Exception:
                self.create_url(url_path, url)
                shortcut_path = url_path
        else:
            # не windows — просто откроем URL
            self.create_url(url_path, url)
            shortcut_path = url_path

        self.mlog(f"Открываю: {url}")
        self.open_and_cleanup(shortcut_path)
        self.mlog("Готово.")


if __name__ == "__main__":
    host = input("Host: ")
    user = input("User: ")
    pwrd = input("Password: ")
    conn = FTPConnection(host, user, pwrd)
    conn.main()
