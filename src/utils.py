import framebuf
import gc
#import adafruit_framebuf as framebuf

ARROW_BA = bytearray(64*64//8)
ARROW_FB = framebuf.FrameBuffer(memoryview(ARROW_BA), 64, 64, framebuf.MONO_HLSB)

DIGIT_BA = bytearray(48*88//8)
DIGIT_FB = framebuf.FrameBuffer(memoryview(DIGIT_BA), 48, 88, framebuf.MONO_HLSB)

def load_arrow(arrow):
    with open("navarrow_64/{}.bp".format(arrow), "rb") as f:
        f.readinto(ARROW_BA)
        return ARROW_FB
    
def load_digit(digit):
    with open("roboto_72pt/{}.bp".format(digit), "rb") as f:
        w, h = f.read(2) # first two bytes are w and h of glyph
        f.readinto(DIGIT_BA)
        return w, h

def process_dist(dist):
    if dist >= 9950:
        dist /= 1000
        return "{}k".format(int(round(dist, -1)))
    elif dist > 990:
        dist /= 1000
        return "{}km".format(round(dist, 1))
    else:
        return "{}m".format(round(dist, -1))

def assemble_nav(buf: framebuf.FrameBuffer, direction, dist, street, bat_voltage):
    dist_str = process_dist(dist)
    
    buf.blit(load_arrow(direction), 5, 27) 

    dist_offset = 68
    for digit in dist_str:
        if digit == ".":
            digit = "dot"
        d_w, d_h = load_digit(digit)
        buf.blit(DIGIT_FB, dist_offset, 18)
        dist_offset += d_w

    street_offset = 125 - len(street) * 4 # Center minus half string length (8px per char)
    buf.text(street.upper(), street_offset, 100, 0)

    buf.text("BAT:{:.2f}V".format(bat_voltage), 22*8, 8, 0)

def assemble_terminal(buf: framebuf.FrameBuffer, log, offset=(0,0)):
    for idx, line in enumerate(log):
        buf.text(line, offset[0], offset[1]+(idx*10), 0)


class DisplayRenderer():
    def __init__(self, w, h, mode="blank", logger=None):
        self.ba = bytearray(w*(h//8))
        self.buf = framebuf.FrameBuffer(
            memoryview(self.ba),
            w, 
            h, 
            framebuf.MONO_VLSB # For landscape mode
        )
        self.w = w
        self.h = h
        self.mode = mode
        self.nav_data = [None, 30, 0, "No nav data"]
        self.bat_voltage = 0
        self.logger = logger

    def convert_ba_to_epd(self):
        render_ba = bytearray(self.w * (self.h // 8))
        i = 1
        for col in range(self.w):
            for row in range(self.h // 8):
                render_ba[-i] = self.ba[row * 250 + col]
                i += 1

        return memoryview(render_ba)

    def render(self):
        self.buf.fill(0xFF)

        if self.mode == "blank":
            pass
        if self.mode == "term" and self.logger is not None:
            assemble_terminal(self.buf, self.logger.buffer, offset=(0, 8))
        if self.mode == "nav":
            assemble_nav(self.buf, self.nav_data[1], self.nav_data[2], self.nav_data[3], self.bat_voltage)
        gc.collect()
        return self.convert_ba_to_epd()


class Logger():
    """
    Wrapper for printing with a fixed-size buffer.
    """
    def __init__(self, max_len=12, callback=None):
        """
        Wrapper for printing with a fixed-size buffer.

        Parameters:
        ----------
        timeout: int, optional
        max_len: int, optional
            maximum buffer size in lines (default 12).
        callback: callable, optional
            Callback function to be called when something is logged.
            Must accept a single argument containing the logger instance.
        """

        self.buffer = []
        self.max_len = max_len

        if callback is None:
            self.callback = None
        else:
            if callable(callback):
                self.log = callback
            else:
                raise ValueError("callback is not a callable.")

    def log(self, *args, sep=' '):
        """
        Log something to the logger and print to console. If the logger has a callback set, trigger the callback.

        Parameters
        ----------
        *args: str
            objects to log.
        sep: str
            separator str (default ' ')
        """
        
        s = sep.join([str(s) for s in args])
        self.buffer += s.split("\n")
        if len(self.buffer) > self.max_len:
            self.buffer = self.buffer[-self.max_len:]
        
        print(s)

        if self.callback:
            self.callback(self)