# protocol_handlers.py
def handle_ssh_connect(ip, login, passwd, msg_log):
    from protocols.sshCP import SSHConnection
    conn = SSHConnection(host=ip, username=login, password=passwd, msg_log=msg_log)
    port = conn.connect_with_protocol_fallback()
    conn.run_terminal(port)
    msg_log(f"SSH -> {ip} {login}")


def handle_ftp_connect(ip, login, passwd, msg_log):
    from protocols.ftpCP import FTPConnection
    conn = FTPConnection(host=ip, user=login, password=passwd, msg_log=msg_log)
    conn.main()
    msg_log(f"FTP -> {ip} {login}")


def dispatch_protocol(proto_name, ip, login, passwd, msg_log):
    # универсальный диспетчер
    if proto_name.upper() == "SSH":
        handle_ssh_connect(ip, login, passwd, msg_log)
    elif proto_name.upper() == "FTP":
        handle_ftp_connect(ip, login, passwd, msg_log)
    else:
        print("Unknown protocol", proto_name)
