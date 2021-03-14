__version__ = "0.1.0"

import sync_ubt
import struct
import time
import DisplayRenderer
import framebuf
import epd2in13_V2


# get SyncBLE interface
sbt = sync_ubt.SyncBLE()

komoot_svc_rev = b'lC\xb3\x1d\x17\x0f\xb2\xa2\xa8O/\xd9(\xe1\xc1q' # Stuff to locate komoot dev in adv mode
komoot_svc_uuid = "71C1E128-D92F-4FA8-A2B2-0F171DB3436C"
komoot_chr_uuid = "503DD605-9BCB-4F6E-B235-270A57483026"

global komoot_dev
komoot_addr = None
komoot_dev = None
nav_interval = 2

# Display properties
w = 250
h = 128

# Initialize E-paper display
EPD = epd2in13_V2.EPD()
EPD.init(EPD.FULL_UPDATE)
EPD.Clear(0xFF)

# Create framebuffer to render the display
DISPLAY_BA = bytearray(w*(h//8))
DISPLAY_FB = framebuf.FrameBuffer(
    memoryview(DISPLAY_BA),
    w, 
    h, 
    framebuf.MONO_VLSB # For landscape mode
)


class KomootError(Exception):
    pass


def setup_komoot_dev(timeout=10, interval_ms=1000):
    start = time.time()
    while time.time() < (start + timeout):
        devs = sbt.scan(interval_ms)

        for dev in devs.values():
            # Identify whether device is running Komoot
            adv_data = sync_ubt.decode_adv_data(dev["adv_data"])
            if adv_data.get("07", None) != komoot_svc_rev:
                continue

            print("Found device running Komoot:", dev["addr_decoded"])
            kom_dev = sbt.connect(dev["addr_type"], dev["addr_decoded"])

            if kom_dev is None:
                raise KomootError("Unable to connect to Komoot device")
            else:
                # Get device name from generic access SVC
                devname = "Unknown device"

                generic_acc = kom_dev.get_service(0x1800)
                if generic_acc:
                    devname_chr = generic_acc[0].get_characteristic(0x2A00)
                    if devname_chr:
                        devname = devname_chr[0].read().decode()
                        kom_dev.name = devname

                print("Connected to device: '{}'".format(devname))

                # Find Komoot SVC & CHR, register notify
                komoot_svc = kom_dev.get_service(komoot_svc_uuid)

                if not komoot_svc:
                    raise KomootError("No Komoot SVC found")
                else:
                    print("Found Komoot SVC, locating CHR...")
                    komoot_chr = komoot_svc[0].get_characteristic(komoot_chr_uuid)

                    if not komoot_chr:
                        raise KomootError("No Komoot CHR found")
                    else:
                        print("Found Komoot CHR, registering...")
                        komoot_chr[0].register_notify()
                        kom_dev.komoot_chr = komoot_chr[0]
                        print("Setup Complete.")
                        return kom_dev

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
   
    # TODO: handle failure
    try:
        if komoot_dev is None:
            komoot_dev = setup_komoot_dev()

        if komoot_dev.connected == False:
            if komoot_dev.connect() != 0: # Returns zero on failure
                komoot_dev = None
                komoot_dev = setup_komoot_dev()
    except (sync_ubt.TimeoutError, KomootError) as err:
        print(err, str(err))
        time.sleep(10)
    else:
        try:
            nav_data = komoot_dev.komoot_chr.read()
            nav_id, nav_dir, dist, street = decode_nav_data(nav_data)
            if nav_id is not None:
                print(nav_dir, dist, street)
                DISPLAY_FB.fill(0xFF)
                DisplayRenderer.assemble_nav(DISPLAY_FB, nav_dir, dist, street)

                render = [DISPLAY_BA[row * 250 + col] for col in range(w) for row in range(h//8)] # OPTIMIZE ME!
                render = bytearray(reversed(render))

                EPD.display(render)

            else:
                print("No nav data available.")
                DISPLAY_FB.fill(0xFF)
                DisplayRenderer.assemble_nav(DISPLAY_FB, 30, 0, "No nav data")

                render = [DISPLAY_BA[row * 250 + col] for col in range(w) for row in range(h//8)] # OPTIMIZE ME!
                render = bytearray(reversed(render))

                EPD.display(render)
                
        except sync_ubt.TimeoutError:
            print("BLE response timeout.")
            time.sleep(10)
        else:
            time.sleep(5)
        

while True:
    try:
        nav_routine()
    except:
        time.sleep(10)