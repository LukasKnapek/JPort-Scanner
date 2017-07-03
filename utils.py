import socket

def validate_host(host):
    try:
        socket.gethostbyname(host)
        return True
    except Exception as e:
        return False

def validate_ports(start_port, end_port):
    try:
        port1 = int(start_port)
        port2 = int(end_port)
    except ValueError:
        return False, "Invalid port, not an integer."

    if port1 not in range(1, 65535 + 1) or port2 not in range(1, 65535 + 1):
        msg = "Invalid port number, port has to be in range 1-65535."
    elif port1 > port2:
        msg = "Start port is greater than the end port."
    else:
        return True, None, port1, port2

    return False, msg, port1, port2

def validate_thread_count(t_count, p_range):
    try:
        t_num = int(t_count)
    except ValueError:
        return False, "Invalid thread count, not an integer."

    if t_num > (p_range + 1):
        msg = "Too many threads, the number of threads cannot exceed the number of scanned ports."
    elif t_num == 0:
        msg = "At least one thread must be used."
    elif t_num > 1000:
        msg = "Too many threads, please use fewer than 1000 threads."
    else:
        return True, None

    return False, msg