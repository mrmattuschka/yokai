import framebuf
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

def assemble_nav(buf: framebuf.FrameBuffer, direction, dist, street):
    dist_str = process_dist(dist)
    
    buf.blit(load_arrow(direction), 5, 27) 

    dist_offset = 68
    for digit in dist_str:
        d_w, d_h = load_digit(digit)
        buf.blit(DIGIT_FB, dist_offset, 18)
        dist_offset += d_w

    buf.text(street.upper(), 64, 100, 0)
