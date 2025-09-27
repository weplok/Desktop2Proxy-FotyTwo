# main.py
import sys
import threading
from PyQt5 import QtWidgets, QtCore
from external_scan import start_scan_protocols

# Пример списка "из коробки" поддерживаемых протоколов для UI.
DEFAULT_PROTOCOL_CHOICES = ["SSH", "FTP", "POSTGRESQL"]

class AddDeviceDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Добавить устройство вручную")
        self.layout = QtWidgets.QFormLayout(self)
        self.ip_edit = QtWidgets.QLineEdit(self)
        self.port_edit = QtWidgets.QLineEdit(self)
        self.protocols_edit = QtWidgets.QLineEdit(self)
        self.layout.addRow("IP:", self.ip_edit)
        self.layout.addRow("Порт:", self.port_edit)
        self.layout.addRow("Протоколы (через запятую):", self.protocols_edit)
        btns = QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        self.bb = QtWidgets.QDialogButtonBox(btns, parent=self)
        self.bb.accepted.connect(self.accept)
        self.bb.rejected.connect(self.reject)
        self.layout.addRow(self.bb)

    def get_data(self):
        return {
            "ip": self.ip_edit.text().strip(),
            "hostname": "",
            "protocols": [p.strip() for p in self.protocols_edit.text().split(",") if p.strip()],
            "open_ports": [self.port_edit.text()],
            "os_guess": "",
        }

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Desktop2Proxy менеджер")
        self.resize(900, 500)
        widget = QtWidgets.QWidget()
        self.setCentralWidget(widget)
        v = QtWidgets.QVBoxLayout(widget)

        # Top controls
        h = QtWidgets.QHBoxLayout()
        self.scan_btn = QtWidgets.QPushButton("Сканировать сеть")
        self.scan_btn.clicked.connect(self.on_scan)
        self.stop_btn = QtWidgets.QPushButton("Остановить скан")
        self.stop_btn.clicked.connect(self.on_stop_scan)
        self.stop_btn.setEnabled(False)
        self.add_btn = QtWidgets.QPushButton("Добавить устройство")
        self.add_btn.clicked.connect(self.add_device)
        h.addWidget(self.scan_btn)
        h.addWidget(self.stop_btn)
        h.addWidget(self.add_btn)
        h.addStretch()
        v.addLayout(h)

        # Table with devices
        self.table = QtWidgets.QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["IP", "Host", "OS (угадано)", "Протоколы", "Открытые порты", "Действия"])
        self.table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        v.addWidget(self.table)

        # Log area
        self.log = QtWidgets.QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(140)
        v.addWidget(self.log)

        # internal state
        self.devices = {}  # ip -> device dict
        self._scan_thread = None
        self._stop_event = threading.Event()

    # ========== API для внешней функции сканирования ==========
    # Внешняя функция start_scan_protocols(add_device_callback, stop_event) будет вызвана при старте скана.
    # Она должна в своём потоке вызывать add_device_callback(device_dict) для каждого найденного устройства,
    # и следить за stop_event.is_set() чтобы корректно остановиться.
    def on_scan(self):
        self.log_msg("Запуск сканирования (вызов внешней функции...)")
        self.scan_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self._stop_event.clear()

        # Запускаем внешнюю функцию в отдельном потоке, чтобы не блокировать GUI.
        # Ожидается, что функция start_scan_protocols(add_cb, stop_event) реализована тобою.
        def worker():
            try:
                start_scan_protocols(self.add_device_from_worker, self._stop_event, self.log_msg)
            except Exception as e:
                # можно логировать исключения
                self.log_msg(f"Ошибка в внешнем сканере: {e}")
            finally:
                # по завершении — восстановим кнопки в GUI-потоке
                QtCore.QMetaObject.invokeMethod(self, "scan_finished", QtCore.Qt.QueuedConnection)

        self._scan_thread = threading.Thread(target=worker, daemon=True)
        self._scan_thread.start()

    def on_stop_scan(self):
        self.log_msg("Запрошена остановка сканирования...")
        self._stop_event.set()
        self.stop_btn.setEnabled(False)
        self.scan_btn.setEnabled(True)

    @QtCore.pyqtSlot()
    def scan_finished(self):
        self.log_msg("Сканирование завершено.")
        self.scan_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)

    # Этот метод безопасен для вызова из фонового потока (scan worker).
    # Он использует invokeMethod, чтобы в GUI-потоке добавить строку.
    def add_device_from_worker(self, device):
        QtCore.QMetaObject.invokeMethod(self, "_add_device_row_gui", QtCore.Qt.QueuedConnection, QtCore.Q_ARG(dict, device))

    @QtCore.pyqtSlot(dict)
    def _add_device_row_gui(self, dev):
        """Добавить устройство в таблицу — вызывается в GUI-потоке."""
        ip = dev.get("ip", "")
        if not ip:
            return
        if ip in self.devices:
            self.log_msg(f"Устройство {ip} уже в списке, пропущено.")
            return
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QtWidgets.QTableWidgetItem(ip))
        self.table.setItem(row, 1, QtWidgets.QTableWidgetItem(dev.get("hostname", ip)))
        self.table.setItem(row, 2, QtWidgets.QTableWidgetItem(dev.get("os_guess", "")))
        self.table.setItem(row, 3, QtWidgets.QTableWidgetItem(", ".join(dev.get("protocols", []))))
        self.table.setItem(row, 4, QtWidgets.QTableWidgetItem(", ".join(str(p) for p in dev.get("open_ports", []))))
        btn = QtWidgets.QPushButton("Подключиться")
        btn.clicked.connect(lambda _, ip=ip: self.connect_to(ip))
        self.table.setCellWidget(row, 5, btn)
        self.devices[ip] = dev
        self.log_msg(f"Добавлено устройство: {ip} — {dev.get('protocols')}")

    # Метод, вызываемый вручную из меню — добавляет устройство через диалог.
    def add_device(self):
        d = AddDeviceDialog(self)
        if d.exec_() == QtWidgets.QDialog.Accepted:
            dev = d.get_data()
            self._add_device_row_gui(dev)

    # ========== Подключение к устройству (только UI, вызывает внешние заглушки) ==========
    def connect_to(self, ip):
        dev = self.devices.get(ip)
        if not dev:
            return
        # список протоколов для выбора (если пуст — используем DEFAULT_PROTOCOL_CHOICES)
        proto_list = dev.get("protocols") or DEFAULT_PROTOCOL_CHOICES
        proto, ok = QtWidgets.QInputDialog.getItem(self, "Выберите протокол", "Протокол:", proto_list, 0, False)
        if not ok:
            return
        login, ok1 = QtWidgets.QInputDialog.getText(self, "Логин", "Логин:")
        if not ok1:
            return
        passwd, ok2 = QtWidgets.QInputDialog.getText(self, "Пароль", "Пароль:", QtWidgets.QLineEdit.Password)
        if not ok2:
            return
        self.log_msg(f"Пользователь ввёл учётные данные для {ip} [{proto}] как {login}")

        # Вызов соответствующей функции-обработчика (реализуй их сам в этом файле или внешнем модуле)
        proto_upper = proto.upper()
        try:
            from protocols.protocol_handlers import dispatch_protocol
            threading.Thread(target=dispatch_protocol, args=(proto, ip, login, passwd, self.log_msg), daemon=True).start()
        except Exception:
            QtWidgets.QMessageBox.information(self, "Неподдерживаемый протокол",
                                                f"Протокол {proto} не реализован. Реализуй в protocol_handlers.py")

    # утилита логирования
    def log_msg(self, s):
        QtCore.QMetaObject.invokeMethod(self.log, "appendPlainText", QtCore.Qt.QueuedConnection, QtCore.Q_ARG(str, s))

def main():
    app = QtWidgets.QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
