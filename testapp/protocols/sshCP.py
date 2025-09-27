import paramiko
import socket
import time
import subprocess
import os
import pyautogui, time


class SSHConnection:
    def __init__(self, host, username, password, command="whoami", msg_log=None):
        self.host = host
        self.username = username
        self.password = password
        self.command = command
        self.msg_log = msg_log

    def is_port_open(self, port=22, timeout=3):
        try:
            with socket.create_connection((self.host, port), timeout=timeout):
                return True
        except:
            return False

    def ping_host(self):
        try:
            result = subprocess.run(['ping', '-c', '4', self.host], stdout=subprocess.PIPE, text=True)
            output = result.stdout
            packet_loss = None
            avg_time = None
            for line in output.split('\n'):
                if 'packet loss' in line:
                    packet_loss = line.split(',')[2].strip()
                if 'rtt min/avg/max/mdev' in line:
                    avg_time = line.split('=')[1].split('/')[1].strip()
            return avg_time, packet_loss
        except:
            return None, None

    def ssh_connect(self, port=22):
        try:
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            start_time = time.time()
            client.connect(hostname=self.host,
                           port=port,
                           username=self.username,
                           password=self.password,
                           look_for_keys=False,
                           )
            connect_time = time.time() - start_time

            if self.msg_log:
                self.msg_log(f"Подключено к {self.host} через SSH порт {port}")
                self.msg_log("Протокол подключения: SSHv2 (Paramiko поддерживает только SSHv2)")
            else:
                print(f"Подключено к {self.host} через SSH порт {port}")
                print("Протокол подключения: SSHv2 (Paramiko поддерживает только SSHv2)")

            stdin, stdout, stderr = client.exec_command('uname -a')
            os_info = stdout.read().decode().strip()
            if self.msg_log:
                self.msg_log(f"Операционная система удалённого ПК: {os_info}")
            else:
                print(f"Операционная система удалённого ПК: {os_info}")

            avg_ping, packet_loss = self.ping_host()
            if avg_ping and packet_loss:
                if self.msg_log:
                    self.msg_log(f"Среднее время отклика (ping): {avg_ping} ms")
                    self.msg_log(f"Потеря пакетов: {packet_loss}")
                else:
                    print(f"Среднее время отклика (ping): {avg_ping} ms")
                    print(f"Потеря пакетов: {packet_loss}")
            else:
                if self.msg_log:
                    self.msg_log("Не удалось получить ping-статистику")
                else:
                    print("Не удалось получить ping-статистику")

            start_cmd_time = time.time()
            stdin, stdout, stderr = client.exec_command(self.command)
            output = stdout.read().decode()
            error = stderr.read().decode()
            duration = time.time() - start_cmd_time

            data_size = len(output.encode('utf-8'))
            if output:
                if self.msg_log:
                    self.msg_log(f"Output:\n{output}")
                else:
                    print("Output:\n", output)
            if error:
                if self.msg_log:
                    self.msg_log(f"Error:\n{error}")
                else:
                    print(f"Error:\n{error}")

            if duration > 0:
                speed = data_size / duration
                if self.msg_log:
                    self.msg_log(f"Скорость получения данных: {speed:.2f} байт/сек")
                else:
                    print(f"Скорость получения данных: {speed:.2f} байт/сек")

            client.close()
            return "DONE"
        except Exception as e:
            if self.msg_log:
                self.msg_log(f"Ошибка подключения или выполнения команды: {e}")
            else:
                print(f"Ошибка подключения или выполнения команды: {e}")
            return "LOGERR"

    def connect_with_protocol_fallback(self, is_port=None):
        if is_port is None:
            ports_to_try = [22, 2222] # стандартный SSH и распространенный альтернативный порт
        else:
            ports_to_try = [is_port]
        for port in ports_to_try:
            if self.msg_log:
                self.msg_log(f"Проверка порта {port}...")
            else:
                print(f"Проверка порта {port}...")
            if self.is_port_open(port):
                if self.msg_log:
                    self.msg_log(f"Порт {port} открыт, пробуем подключиться...")
                else:
                    print(f"Порт {port} открыт, пробуем подключиться...")
                res = self.ssh_connect(port)
                if res != "LOGERR":
                    return port
                else:
                    return "LOGERR"
            else:
                if self.msg_log:
                    self.msg_log(f"Порт {port} закрыт или недоступен.")
                else:
                    print(f"Порт {port} закрыт или недоступен.")
        if self.msg_log:
            self.msg_log(
                "Не удалось подключиться по стандартным SSH портам. Перебор других протоколов не реализован из-за устаревания и небезопасности.")
        else:
            print(
                "Не удалось подключиться по стандартным SSH портам. Перебор других протоколов не реализован из-за устаревания и небезопасности.")

    def run_terminal(self, port):
        if port == "LOGERR":
            if self.msg_log:
                self.msg_log(f"Неверный логин или пароль!")
            else:
                print(f"Неверный логин или пароль!")
            return
        os.system(f'start cmd.exe /k "echo Ожидайте передачу пароля (ничего нажимать не нужно). & ssh {self.username}@{self.host} -p {port}"')

        # открыть терминал через subprocess, затем
        time.sleep(7)
        pyautogui.typewrite(f"{self.password}\n")
        time.sleep(1)
        pyautogui.typewrite("clear\n")


if __name__ == "__main__":
    print("SSH-Connection try")
    host = input("Host: ")
    username = input("Login: ")
    password = input("Password: ")
    command = input("Command: ")
    conn = SSHConnection(host, username, password, command)

    port = conn.connect_with_protocol_fallback()
    conn.run_terminal(port)
