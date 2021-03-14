# /*****************************************************************************
# * | File        :	  epdconfig.py
# * | Author      :   Waveshare team
# * | Function    :   Hardware underlying interface
# * | Info        :
# *----------------
# * | This version:   V1.0
# * | Date        :   2019-06-21
# * | Info        :   
# ******************************************************************************
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documnetation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to  whom the Software is
# furished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS OR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#

# import logging <- not present on ESP
import time
import sys
from machine import SPI, Pin
from micropython import const

RST_PIN = const(16)
DC_PIN = const(17)
CS_PIN = const(5)
BUSY_PIN = const(4)


class ESP32:

    def __init__(self):
        self.SPI = SPI(2, baudrate=1000000, sck=Pin(18), mosi=Pin(23))
        # Stating this seems to be important! make sure SPI gets initialized
        #SPI(2, baudrate=1000000)
        self.rst = Pin(RST_PIN)
        self.dc = Pin(DC_PIN)
        self.cs = Pin(CS_PIN)
        self.busy = Pin(BUSY_PIN)

        self.GPIO = {
            RST_PIN : self.rst,
            DC_PIN : self.dc,
            CS_PIN : self.cs,
            BUSY_PIN : self.busy
        }


    def digital_write(self, pin, value):
        self.GPIO[pin].value(value)

    def digital_read(self, pin):
        return self.GPIO[pin].value()

    def delay_ms(self, delaytime):
        time.sleep_ms(delaytime)

    def spi_writebyte(self, data):
        self.SPI.write(bytearray(data))

    def module_init(self):
        self.cs.init(self.cs.OUT, value=1)
        self.dc.init(self.dc.OUT, value=0)
        self.rst.init(self.rst.OUT, value=0)
        self.busy.init(self.busy.IN)
        return 0

    def module_exit(self):
        # logging.debug("spi end")
        self.SPI.deinit()

        # logging.debug("close 5V, Module enters 0 power consumption ...")
        self.rst.value(0)
        self.dc.value(0)


implementation = ESP32()

for func in [x for x in dir(implementation) if not x.startswith('_')]:
    setattr(sys.modules[__name__], func, getattr(implementation, func))


### END OF FILE ###
