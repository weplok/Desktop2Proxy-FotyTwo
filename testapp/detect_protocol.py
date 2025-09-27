# detect_service.py
# Python 3.8+
# Пример: python detect_service.py 192.168.56.1 21

import socket
import ssl
import sys


class DetectConnection:
    def __init__(self, ip: str, port: int):
        self.ip = ip
        self.port = port
        self.SOCKET_TIMEOUT = 3.0

    def recv_some(self, s, max_bytes=1024):
        try:
            return s.recv(max_bytes)
        except Exception:
            return b''

    def try_banner(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(self.SOCKET_TIMEOUT)
        try:
            s.connect((self.ip, self.port))
        except Exception as e:
            return None, f"connect_failed: {e}"
        try:
            data = self.recv_some(s, 2048)
            if data:
                return data.decode(errors='ignore'), None
            return '', None
        finally:
            s.close()

    def try_http_head(self):
        try:
            s = socket.create_connection((self.ip, self.port), timeout=self.SOCKET_TIMEOUT)
        except Exception as e:
            return None, f"connect_failed: {e}"
        try:
            req = "HEAD / HTTP/1.0\r\nHost: {}\r\n\r\n".format(self.ip)
            s.send(req.encode())
            resp = b''
            while True:
                part = s.recv(1024)
                if not part:
                    break
                resp += part
                if b'\r\n\r\n' in resp:
                    break
            return resp.decode(errors='ignore'), None
        except Exception as e:
            return None, f"http_failed: {e}"
        finally:
            s.close()

    def try_ssl(self):
        context = ssl.create_default_context()
        # do not verify for detection; we only want cert details
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        try:
            raw = socket.create_connection((self.ip, self.port), timeout=self.SOCKET_TIMEOUT)
            ssl_sock = context.wrap_socket(raw, server_hostname=self.ip)
            # trigger handshake
            cert = ssl_sock.getpeercert()
            ssl_sock.close()
            return cert, None
        except ssl.SSLError as e:
            return None, f"ssl_error: {e}"
        except Exception as e:
            return None, f"ssl_connect_failed: {e}"

    def detect(self):
        out = {}
        banner, err = self.try_banner()
        out['banner'] = banner
        out['banner_error'] = err

        if banner:
            b = banner.strip()
            if b.startswith('SSH-'):
                out['likely_protocol'] = 'ssh'
                return out
            if b.startswith('220') and 'ftp' in b.lower() or 'ftp' in b.lower():
                out['likely_protocol'] = 'ftp'
                return out
            if b.startswith('+OK'):
                out['likely_protocol'] = 'pop3'
                return out
            if b.startswith('* OK') or 'imap' in b.lower():
                out['likely_protocol'] = 'imap'
                return out
            if b.startswith('220') and 'smtp' in b.lower():
                out['likely_protocol'] = 'smtp'
                return out

        # ------------------------------------------------

        # fallback: if banner exists but not recognized, return banner
        if banner:
            out['likely_protocol'] = 'unknown_banner'
            return out

        out['likely_protocol'] = 'unknown_or_filtered'
        return out

    def check(self):
        res = self.detect()
        return res


if __name__ == '__main__':
    if len(sys.argv) != 3:
        print("Usage: python detect_service.py <ip> <port>")
        sys.exit(1)
    ip = sys.argv[1]
    port = int(sys.argv[2])
    conn = DetectConnection(ip, port)
    res = conn.check()
    print(res)
