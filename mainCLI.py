#!/usr/bin/env python
import socket, threading, time

timeout = 0.1
port_status = {}

def scan_ports(host, start, end):
    global port_status

    for port in range(start, end+1):
        try:
            socket.create_connection((host, port), timeout)
            port_status[port] = "Open"
        except Exception as e:
            port_status[port] = "Closed: %s" % e
    return

def get_host():
    while True:
        try:
            host = raw_input("Enter the target host (DNS name/IPv4/IPv6): ")
            host = socket.gethostbyname(host)
            break
        except:
            print "Invalid host, please enter a valid host."
    return host

def main():
    host = get_host()
    p_start = int(raw_input("Enter the start port: ")) - 1
    p_end = int(raw_input("Enter the end port: "))
    t_count = int(raw_input("Enter the number of used threads (must be <= number of ports): "))

    step = (p_end - p_start) / t_count  # Number of ports scanned per thread
    rem = (p_end - p_start) % t_count # Remaining ports after equal division

    for i in range(t_count):
        rng_start = p_start + i*step + 1
        rng_end = p_start + (i+1)*step
        # print (rng_start, rng_end)
        t = threading.Thread(target=scan_ports, args=(host, rng_start, rng_end),
                             name="%s-%s scanner" % (rng_start, rng_end))
        t.start()
    if rem != 0:
        rem_t = threading.Thread(target=scan_ports, args=(host, (p_end - rem) + 1, p_end), name="Remaining ports scanner")
        rem_t.start()
        # print (p_end - rem, p_end)

    print "Scanning..."
    scan_start_time = time.time()

    while len(threading.enumerate()) != 1:  # Wait until all port scan threads are completed
        time.sleep(0.1)

    print "\nPort status:"
    open_ports = [p for p, status in port_status.items() if status == "Open"]
    if open_ports:
        for p in open_ports:
            print "* Port %d is open." % p
    else:
        print "None of the scanned ports are open"
    print "Scan duration: %ss" % (time.time() - scan_start_time)

if __name__ == "__main__":
    main()

