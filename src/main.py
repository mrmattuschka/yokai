__version__ = "0.1.2"
__yokai_model__ = "1"

import sync_ubt
import struct
import time
import epd2in13_V2
from utils import Logger, DisplayRenderer
from machine import Pin, ADC, deepsleep
import os

class KomootError(Exception):
    pass

komoot_svc_rev = b'lC\xb3\x1d\x17\x0f\xb2\xa2\xa8O/\xd9(\xe1\xc1q' # Stuff to locate komoot dev in adv mode
komoot_svc_uuid = "71C1E128-D92F-4FA8-A2B2-0F171DB3436C"
komoot_chr_uuid = "503DD605-9BCB-4F6E-B235-270A57483026"

global komoot_dev
komoot_addr = None
komoot_dev = None
nav_interval = 2

global last_nav
last_nav = None

# failure counter
global failures
failures = 0


log = Logger(max_len=12)
mp_v = os.uname().release
log.log("YOKAI model {m} firmware v{v}\nmicropython {mp_v}".format(m = __yokai_model__, v = __version__, mp_v = mp_v))

# Display properties
w = 250
h = 128

DPR = DisplayRenderer(w, h, mode="blank", logger=log)

# Initialize E-paper display
log.log("Initializing EPD...")
EPD = epd2in13_V2.EPD()
EPD.init(EPD.FULL_UPDATE)

# Set conditional EPD update as logger callback
def logger_display_callback(Logger):
    if DPR.mode == "term":
        render = DPR.render()
        EPD.display_cycle(render, cycle=False)
        del render

DPR.mode = "term"
render = DPR.render()
EPD.display_cycle(render, cycle=True) # Cycle once
del render

log.callback = logger_display_callback

# get SyncBLE interface
log.log("Initializing BLE interface...")
sbt = sync_ubt.SyncBLE(debug_logger=log.log)

# Voltage monitor
bat_monitor = ADC(Pin(34))
bat_monitor.atten(ADC.ATTN_11DB)

def get_bat_voltage():
    U = (bat_monitor.read()/4095)*3.6*2
    return U

def setup_komoot_dev(timeout=10, interval_ms=1000):
    """
    Detect and connect to a nearby BLE peripheral running Komoot.

    Parameters
    ----------
    timeout: int, optional
        time to wait in seconds for successful connection before failing (default 10).
    interval_ms: int, optional
        scanning interval in milliseconds (default 1000)

    Returns
    ----------
    a sync_ubt.Peripheral instance referring to the connected device
    """

    start = time.time()
    while time.time() < (start + timeout):
        devs = sbt.scan(interval_ms)

        for dev in devs.values():
            # Identify whether device is running Komoot
            adv_data = sync_ubt.decode_adv_data(dev["adv_data"])
            if adv_data.get("07", None) != komoot_svc_rev:
                continue

            log.log("Found device running Komoot:", dev["addr_decoded"])
            komoot_dev = sbt.connect(dev["addr_type"], dev["addr_decoded"])

            if komoot_dev is None:
                raise KomootError("Unable to connect to Komoot device")
            else:
                # Get device name from generic access SVC
                devname = "Unknown device"

                generic_acc = komoot_dev.get_service(0x1800)
                if generic_acc:
                    devname_chr = generic_acc[0].get_characteristic(0x2A00)
                    if devname_chr:
                        devname = devname_chr[0].read().decode()
                        komoot_dev.name = devname

                log.log("Connected to device: '{}'".format(devname))

                # Find Komoot SVC & CHR, register notify
                komoot_svc = komoot_dev.get_service(komoot_svc_uuid)

                if not komoot_svc:
                    raise KomootError("No Komoot SVC found")
                else:
                    log.log("Found Komoot SVC, locating CHR...")
                    komoot_chr = komoot_svc[0].get_characteristic(komoot_chr_uuid)

                    if not komoot_chr:
                        raise KomootError("No Komoot CHR found")
                    else:
                        log.log("Found Komoot CHR, registering...")
                        komoot_chr[0].register_notify()
                        komoot_dev.komoot_chr = komoot_chr[0]
                        log.log("Setup complete. Happy hiking!")
                        return komoot_dev

    else:
        raise KomootError("No device running Komoot found")

def decode_nav_data(data):
    """
    Decode navigation instructions retrieved from the Komoot app.
    Documentation on navigation instructions can be found here: https://docs.google.com/document/d/1iYgV4lDKG8LdCuYwzTXpt3FLO_kaoJGGWzai8yehv6g
    """
    if data is None:
        return None, None, None, None
    else:
        try:
            nav_id, nav_dir, dist = struct.unpack("<IbI", data[0:9])
            street = data[9:].decode()
            return nav_id, nav_dir, dist, street
        except ValueError:
            return None, None, None, None

def nav_routine():
    global komoot_dev
    global last_nav
    global failures

    if komoot_dev is None:
        log.log("Searching for Komoot device...")
        DPR.mode = "blank"
        komoot_dev = setup_komoot_dev()
        DPR.mode = "term"
        log.callback(None)

    if not komoot_dev.connected: # Returns zero on failure/no connection
        log.log("Komoot device is not connected, reconnecting...")
        komoot_dev = None
        komoot_dev = setup_komoot_dev()

    if komoot_dev.connected:
        DPR.mode = "nav"

        bat_voltage = get_bat_voltage()
        DPR.bat_voltage = bat_voltage
        
        nav_data = komoot_dev.komoot_chr.read()
        nav_id, nav_dir, dist, street = decode_nav_data(nav_data)
        
        if nav_id is not None:
            log.log(nav_id, nav_dir, dist, street)
            DPR.nav_data = [nav_id, nav_dir, dist, street]
            render = DPR.render()

            if ((dist > 200) & (street != last_nav)): 
                # only do full refresh if we have more than 200m and new street
                log.log("Cycling display...")
                EPD.display_cycle(render, cycle=True)
                #time.sleep(5)
            else:
                EPD.display_cycle(render, cycle=False)
            if (dist > 200):
                time.sleep(5)
            del render
            last_nav = street

        else:
            log.log("No nav data available.")
            DPR.nav_data = [None, 30, 0, "No nav data"]
            render = DPR.render()
            EPD.display_cycle(render, cycle=True)
            del render
            time.sleep(5)
    else:
        raise KomootError("Komoot device not connected")


while failures < 10:
    try:
        nav_routine()
    except Exception as e:
        DPR.mode = "term"
        log.log(e.__class__.__name__ + ':', str(e))
        failures += 1
        time.sleep(5)
    else:
        # If nav_routine succeeds, reset failure counter.
        failures = 0
else:
    DPR.mode = "term"
    log.log(">10 failures, going into deep sleep.\nCycle device to try again.")
    deepsleep()
