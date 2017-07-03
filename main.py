#!/usr/bin/env pyimport socket, threading, time
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GObject
import threading, time, socket
import utils


## Globals ##
builder = Gtk.Builder()
builder.add_from_file("PortScannerGUI.glade")
port_status = {}
ports_left = []
can_run = threading.Event()
display_mode = "Open"


## GTK Widgets ##
log_buffer = builder.get_object("log_buffer")
log = builder.get_object("tview_log")
start_bt = builder.get_object("bt_start_scan")
stop_bt = builder.get_object("bt_stop_scan")
warn_host_icon = builder.get_object("img_host_warn")
warn_ports_icon = builder.get_object("img_ports_warn")
warn_threads_icon = builder.get_object("img_threads_warn")
in_host = builder.get_object("in_host")
in_p_start = builder.get_object("in_p_start")
in_p_end = builder.get_object("in_p_end")
in_threads = builder.get_object("in_threads")
in_timeout = builder.get_object("sb_timeout")
port_status_list = builder.get_object("lbox_port_status")
status_bar = builder.get_object("status_bar")
status_indicator = builder.get_object("status_spinner")
cb_display = builder.get_object("cb_display")

# List of all warning icons shown when a specific input is invalid. A scan cannot be started until they are all hidden.
warn_icons = [warn_host_icon, warn_ports_icon, warn_threads_icon]
data_fields = [in_host, in_p_start, in_p_end, in_threads]


class Handler():
    def on_main_window_init(self, *args):
        warn_host_icon.set_visible(False)
        warn_ports_icon.set_visible(False)
        warn_threads_icon.set_visible(False)

        start_bt.set_sensitive(False)
        stop_bt.set_sensitive(False)
        cb_display.set_sensitive(False)

        log.set_buffer(log_buffer)  # Assign a buffer to the program log

    def on_port_input(self, entry, event):
        port1, port2 = in_p_start.get_text(), in_p_end.get_text()
        ports_valid = utils.validate_ports(port1, port2)
        if ports_valid[0]:
            warn_ports_icon.set_visible(False)
        else:
            warn_ports_icon.set_visible(True)
            warn_ports_icon.set_tooltip_text(ports_valid[1])

        validate_input_data()

    def on_threads_input(self, entry, *event):
        port1, port2 = in_p_start.get_text(), in_p_end.get_text()
        ports_valid = utils.validate_ports(port1, port2)

        # Need to validate ports in order to check that # of threads is not greater than # of ports being scanned
        if ports_valid[0]:
            t_count_valid = utils.validate_thread_count(entry.get_text(), ports_valid[3]-ports_valid[2])
            if t_count_valid[0]:
                warn_threads_icon.set_visible(False)
            else:
                warn_threads_icon.set_visible(True)
                warn_threads_icon.set_tooltip_text(t_count_valid[1])
        else:
            warn_threads_icon.set_visible(True)
            warn_threads_icon.set_tooltip_text("Please enter valid port range first")

        validate_input_data()

    def on_host_input(self, entry, *args):
        if utils.validate_host(entry.get_text()):
            warn_host_icon.set_visible(False)
        else:
            warn_host_icon.set_visible(True)

        validate_input_data()

    def on_main_window_quit(self, window):
        Gtk.main_quit(main_window)

    def on_start_button_click(self, prog_bar):
        start_scan_setup()

        host, p_start, p_end, t_count, timeout = collect_input()
        socket.setdefaulttimeout(timeout)

        # Scan thread manages scanning process itself, spawning *t_count* worker threads.
        scan_thread = threading.Thread(target=scan,args=(host, p_start, p_end, t_count),name="MainScanThread")
        scan_thread.start()

        # Updates progress bar, terminates when all ports are scanned or the scan is aborted.
        progress_thread = threading.Thread(target=update_prog_bar, args=(prog_bar, (p_end-p_start)+1),name="ProgressThread")
        progress_thread.start()


    def on_stop_button_click(self, *args):
        stop_bt.set_sensitive(False)
        can_run.clear()  # Stop scan threads
        update_status_bar("Scan aborted.", False)

    def on_display_mode_change(self, cb_display):
        global display_mode

        display_mode = cb_display.get_active_text()
        display_results()

def start_scan_setup():
    """(De)activate specific buttons, set event flag and clear some vars on each scan start."""
    global port_status, can_run

    start_bt.set_sensitive(False)
    stop_bt.set_sensitive(True)
    cb_display.set_sensitive(False)
    can_run.set()

    port_status = {}
    log_buffer.set_text("")
    clear_results()


def end_scan_setup(start_time):
    """Process results and deactivate specific buttons on each scan end."""
    process_results(start_time)
    stop_bt.set_sensitive(False)
    cb_display.set_sensitive(True)


def validate_input_data():
    """Deactivate start button until all fields are non-empty and valid."""
    if all(field.get_text() != "" for field in data_fields):
        if all(not icon.get_visible() for icon in warn_icons):
            start_bt.set_sensitive(True)
            return

    start_bt.set_sensitive(False)


def update_prog_bar(prog_bar, n_tasks):
    """Keep updating the progress bar every 0.2 secs until the can_run flag is cleared."""
    # Update the bar with the fraction of ports scanned/total ports to be scanned.
    while len(port_status) != n_tasks and can_run.is_set():
        time.sleep(0.2)
        completed_p = round(len(port_status) / float(n_tasks),2)
        GObject.idle_add(prog_bar.set_fraction, completed_p)
    if not can_run.is_set():
        GObject.idle_add(prog_bar.set_fraction, 1)


def log_print(text):
    """Print to the application log safely (when not called from MainThread)."""
    GObject.idle_add(log_buffer.insert_at_cursor, text)


def collect_input():
    """Collect the entry fields contents."""
    host = in_host.get_text()
    p_start = int(in_p_start.get_text())
    p_end = int(in_p_end.get_text())
    t_count = int(in_threads.get_text())
    timeout = in_timeout.get_value()

    return host, p_start, p_end, t_count, timeout


def scan_port(host, port):
    """Try to establish connection to the host on a given port. If successful, the port is open."""
    try:
        socket.create_connection((host, port))
        return "Open"
    except Exception as e:
        return "Closed: %s" % e


def scan_manager(host):
    """Assign ports to scan to worker threads until there are no ports of the original range left."""
    global port_status, ports_left

    # Scan worker threads pop remaining port numbers and then scan them. List.pop() is a thread-safe operation.
    # Results are stored in the port_status dict as "port number":"Open" (or "Closed: *exception*")
    while ports_left and can_run.is_set():
        try:
            port = ports_left.pop()
        except Exception as e:
            print e
        port_status[port] = scan_port(host, port)


def scan(host, p_start, p_end, t_count):
    """Initialize worker threads, wait until there are only MainThread/ScanThread left running, then end scan."""
    global ports_left

    # This list will have its elements removed by scan worker threads when the corresponding ports have been scanned.
    # Once it is empty, all ports will have been scanned and the scan ends.
    ports_left = range(p_start, p_end+1)

    log_print("Scanning %s on %d-%d..." % (host, p_start, p_end))
    scan_start_time = time.time()  # Keep track of the scan time
    update_status_bar("Scanning...", True)

    for i in range(t_count):
        t = threading.Thread(target=scan_manager, kwargs={"host": host}, name="Scan thread %s" % i)
        t.start()

    # TODO: Come up with a better way to wait until all scan threads are finished
    while threading.active_count() != 2:
        time.sleep(0.2)

    end_scan_setup(scan_start_time)


def process_results(start_time):
    """Print results to the application log, then call the method to display the ports in a ListView."""
    # The application log displays only open ports
    if not ports_left:
        log_print("\n\n#### Port status ####\n")
        open_ports = [p for p, status in port_status.items() if status == "Open"]
        if open_ports:
            for p in open_ports:
                log_print("* Port %d is open.\n" % p)
        else:
            log_print("None of the scanned ports are open\n")

        log_print("\nScan duration: %ss" % (time.time() - start_time))
        GObject.idle_add(display_results)
    else:
        log_print("\n\n#### Scan aborted ###\n")

    GObject.idle_add(start_bt.set_sensitive, True)


def clear_results():
    """Clear all port results shown in ListView"""
    for child in port_status_list.get_children():
        port_status_list.remove(child)


def display_results():
    """Clear results in ListView, display results depending on the display mode selected by user."""
    clear_results()

    if display_mode == "Open": results = [row for row in sorted(port_status.items()) if "Open" in row[1]]
    elif display_mode == "Closed": results = [row for row in sorted(port_status.items()) if "Closed" in row[1]]
    else: results = [row for row in sorted(port_status.items())]

    if len(results) > 100:
        results = results[:100]
        update_status_bar("Scan complete (first 100 results shown).", False)
    else:
        update_status_bar("Scan complete.", False)

    # Create a new box widget with a label and a image for each port, add them to the port results ListView
    for port, status in results[::-1]:
        row = Gtk.Box(0, 0)
        row.set_visible(True)

        port_n = Gtk.Label("Port %s" % port)
        port_n.set_visible(True)
        port_n.set_halign(Gtk.Align(3))

        state_img = Gtk.Image()
        state_img.set_visible(True)
        state_img.set_halign(Gtk.Align(3))

        if "Open" in status:
            state_img.set_from_file("Icons/open.png")
            state_img.set_tooltip_text(status)
        else:
            state_img.set_from_file("Icons/closed.png")
            state_img.set_tooltip_text(status)

        row.pack_start(port_n, 1, 1, 1)
        row.pack_start(state_img, 1, 1, 1)
        port_status_list.insert(row, 0)


def update_status_bar(text, spin_activate):
    """Update status bar with new message and either start/stop spinner."""
    c_id = status_bar.get_context_id("Context") # Dummy context
    GObject.idle_add(status_bar.push, c_id, text)
    if spin_activate:
        GObject.idle_add(status_indicator.start)
    else:
        GObject.idle_add(status_indicator.stop)


if __name__ == "__main__":
    builder.connect_signals(Handler())  # Connect Gtk.Builder with the Handler class to handle widget callbacks
    main_window = builder.get_object("main_window")
    main_window.show_all()

    Gtk.main()



