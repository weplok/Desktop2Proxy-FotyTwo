#!/usr/bin/env python3
"""
arp_nmap_timeout.py

Простой поток:
 - arp -a -> получить IP
 - для каждого IP: запуск nmap (XML в stdout) с таймаутом 15s
 - парсинг открытых портов -> collect ip:port
 - сохранение списка и вызов detect(ip, port)
"""

from pathlib import Path
from datetime import datetime
import subprocess
import re
import xml.etree.ElementTree as ET
import sys
import time

OUTPUT_DIR = Path("scan_results")
OUTPUT_DIR.mkdir(exist_ok=True)
ARP_FILE = OUTPUT_DIR / f"arp_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
PAIRS_FILE = OUTPUT_DIR / f"ip_port_pairs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"

NMAP_TIMEOUT = 15  # seconds per IP
NMAP_CMD = r"C:\Program Files (x86)\Nmap\nmap.exe"  # если nmap установлен не в PATH — замените на полный путь
msg_log = None


# ---------------- utilities ----------------
def timestamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def mlog(msg):
    if msg_log:
        msg_log(msg)
    else:
        print(msg)


def run_arp() -> list[str]:
    """Запускает arp -a, сохраняет вывод и возвращает список IPv4."""
    try:
        proc = subprocess.run(["arp", "-a"], capture_output=True, text=True, check=False)
        out = proc.stdout or proc.stderr or ""
    except FileNotFoundError:
        out = ""
    ARP_FILE.write_text(out, encoding="utf-8")
    ips = set(re.findall(r"\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b", out))
    # Фильтрация нечего лишнего
    valid = [ip for ip in sorted(ips) if ip != "255.255.255.255"]
    if "127.0.0.1" not in valid:
        valid.insert(0, "127.0.0.1")
    return valid[:2]


def run_nmap_for_ip(ip: str, timeout: int) -> str | None:
    """
    Запускает nmap для одного IP и возвращает XML-строку (stdout).
    При превышении timeout возвращает None.
    """
    # Используем -Pn (не пингует), -sT (TCP connect если нет прав), -T4 и вывод в XML на stdout (-oX -)
    cmd = [NMAP_CMD, "-Pn", "-sT", "-T4", "-oX", "-", ip]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
        # даже если returncode != 0, nmap всё равно может вернуть XML в stdout
        xml_out = proc.stdout.strip()
        if not xml_out:
            # возможно nmap писал в stderr; попытаемся вернуть stderr — но parse, скорее всего, не получится
            xml_out = proc.stderr.strip() or None
        return xml_out
    except subprocess.TimeoutExpired:
        mlog(f"[!] nmap timeout for {ip} (>{timeout}s). Пропускаем.")
        return None
    except FileNotFoundError:
        mlog("[ERROR] nmap не найден. Установите nmap или пропишите полный путь в NMAP_CMD.")
        sys.exit(1)


def parse_nmap_xml_string(xml_text: str) -> list[tuple[str, int]]:
    """Парсит nmap XML (строку) и возвращает список (ip, port) для открытых портов."""
    pairs = []
    if not xml_text:
        return pairs
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return pairs
    for host in root.findall("host"):
        addr = None
        for a in host.findall("address"):
            addr = a.get("addr")
            if addr:
                break
        if not addr:
            continue
        ports_elem = host.find("ports")
        if ports_elem is None:
            continue
        for port in ports_elem.findall("port"):
            portid = port.get("portid")
            try:
                port_int = int(portid)
            except (TypeError, ValueError):
                continue
            state = port.find("state")
            if state is None:
                continue
            st = state.get("state", "")
            if st in ("open", "open|filtered"):
                pairs.append((addr, port_int))
    return pairs


def save_pairs(pairs: list[tuple[str, int]]):
    if not pairs:
        PAIRS_FILE.write_text("", encoding="utf-8")
        return
    PAIRS_FILE.write_text("\n".join(f"{ip}:{port}" for ip, port in pairs), encoding="utf-8")


# ---------------- заглушка detect ----------------
def detect(ip: str, port: int, add_device_callback, stop_event):
    from detect_protocol import DetectConnection
    conn = DetectConnection(ip, port)
    res = conn.check()
    if res["likely_protocol"] != "unknown_or_filtered":
        add_device_callback({
            "ip": ip,
            "protocols": [res["likely_protocol"]],
            "open_ports": [port],
        })
        time.sleep(0.2)
    if stop_event.is_set():
        return "STOP"


# ---------------- main ----------------
def start_scan_protocols(add_device_callback, stop_event, msglog):
    global msg_log
    msg_log = msglog
    mlog("[*] Запуск arp -a...")
    hosts = run_arp()
    mlog(f"    Найдено IP: {hosts}")
    if not hosts:
        mlog("[!] IP не найдены — выход.")
        return

    all_pairs = []
    for ip in hosts:
        mlog(f"[*] Сканирование {ip} (таймаут {NMAP_TIMEOUT}s)...")
        xml = run_nmap_for_ip(ip, NMAP_TIMEOUT)
        if xml is None:
            continue
        # для удобства сохраняем xml на диск (файл в OUTPUT_DIR)
        xml_path = OUTPUT_DIR / f"nmap_{ip.replace('.', '_')}_{timestamp()}.xml"
        try:
            xml_path.write_text(xml, encoding="utf-8")
        except Exception:
            pass
        pairs = parse_nmap_xml_string(xml)
        if pairs:
            mlog(f"    Найдено: {pairs}")
            all_pairs.extend(pairs)
        else:
            mlog("    Открытых портов не найдено.")
        if stop_event.is_set():
            return

    # удалим дубликаты и отсортируем
    unique = sorted(set(all_pairs), key=lambda x: (x[0], x[1]))
    save_pairs(unique)
    mlog(f"[*] Сохранено пар: {len(unique)} -> {PAIRS_FILE}")

    mlog("[*] Вызов detect() для каждой пары:")
    for ip, port in unique:
        try:
            rtrn = detect(ip, port, add_device_callback, stop_event)
            if rtrn == "STOP":
                return
        except Exception as e:
            mlog(f"    Ошибка при detect({ip},{port}): {e}")

    mlog("[*] Готово.")
