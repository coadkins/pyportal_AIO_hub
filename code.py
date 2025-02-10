import adafruit_connection_manager
import adafruit_imageload
import adafruit_requests
import board
import busio
import displayio
import neopixel
import os
import terminalio
import time
from adafruit_io.adafruit_io import IO_HTTP
from adafruit_bitmap_font import bitmap_font
from adafruit_display_text import (bitmap_label,
                                   label)
from adafruit_esp32spi import (adafruit_esp32spi,
 adafruit_esp32spi_wifimanager)
from adafruit_pyportal import PyPortal
from adafruit_ticks import ticks_ms, ticks_add, ticks_diff
from digitalio import DigitalInOut
from font_free_sans_bold_30 import FONT as cpfont

# Import Credentials 
secrets = {
    "ssid" : os.getenv("CIRCUITPY_WIFI_SSID"),
    "password" : os.getenv("CIRCUITPY_WIFI_PASSWORD"),
}
aio_username = os.getenv("ADAFRUIT_AIO_USERNAME")
aio_password = os.getenv("ADAFRUIT_AIO_KEY")

# PyPortal ESP32 AirLift Pins
esp32_cs = DigitalInOut(board.ESP_CS)
esp32_ready = DigitalInOut(board.ESP_BUSY)
esp32_reset = DigitalInOut(board.ESP_RESET)

spi = busio.SPI(board.SCK, board.MOSI, board.MISO)
esp = adafruit_esp32spi.ESP_SPIcontrol(spi, esp32_cs, esp32_ready, esp32_reset)
status_light = neopixel.NeoPixel(board.NEOPIXEL, 1, brightness=0.2)
wifi = adafruit_esp32spi_wifimanager.ESPSPI_WiFiManager(esp, secrets, status_light)

# Initialize PyPortal Display
display = board.DISPLAY

WIDTH = board.DISPLAY.width
HEIGHT = board.DISPLAY.height

# Initialize new PyPortal object
pyportal = PyPortal(esp=esp,
                    external_spi=spi)

# Set backlight level
pyportal.set_backlight(0.8)

# set palette
palette0 = displayio.Palette(5)
palette0[0] = 0x00FF00
palette0[1] = 0xFF0000
palette0[2] = 0xDC1B1B
palette0[3] = 0x4F8BE3
palette0[4] = 0x04C60A

# load bitmap icons
group = displayio.Group()
icon_file = "/fonts/cpicons.bdf"
icon_font = bitmap_font.load_font(icon_file)

# configure icon elements
temp_icon = bitmap_label.Label(icon_font, text = chr(0xe1ff),
                               x = 30, y = 50, color = 0xDC1B1B)
humid_icon = bitmap_label.Label(icon_font, text = "\ue798",
                                x = 30, y = 110, color = 0x4F8BE3)
gas_icon = bitmap_label.Label(icon_font, text = "\ue7b0",
                              x = 30, y = 170, color = 0x04C60A)
# configure text elements
temp_text = bitmap_label.Label(font = cpfont, text = "N/A",
                               x=120, y=50, color=0xDC1B1B)
humid_text = bitmap_label.Label(font = cpfont, text = "N/A",
                                x=120, y=110, color=0x4F8BE3)
gas_text = bitmap_label.Label(font = cpfont, text= "N/A", x=120,
                              y=170, color=0x04C60A)
time_text = label.Label(font = terminalio.FONT, text = "No updates",
                        x = 80, y = 220, color = 0xFFFFFF)

# Add graphics elements to displayio root group 
for viz in [temp_text, humid_text, gas_text,
             temp_icon, humid_icon, gas_icon, time_text]:
    group.append(viz)

display.root_group = group

# Connect to WiFi
while not esp.is_connected:
    try:
        wifi.connect()
    except (RuntimeError, ConnectionError) as e:
        print("could not connect to AP, retrying: ",e)
        wifi.reset()
        continue
print("Connected to WiFi!")

pool = adafruit_connection_manager.get_radio_socketpool(esp)
ssl_context = adafruit_connection_manager.get_radio_ssl_context(esp)
requests = adafruit_requests.Session(pool, ssl_context)

# Initialize a new HTTP client for updating the time
io = IO_HTTP(aio_username, aio_password, requests)

# some helper functions to update time and convert to 12-hour clock
def update_time():
    now = io.receive_time()
    return now

def convert_time(the_time):
    h = the_time[3]
    if h >= 12:
        h -= 12
        a = "PM"
    else:
        a = "AM"
    if h == 0:
        h = 12
    return h, a

def update_values():
    temp = round((1.8*float(io.receive_data(temp_feed["key"])["value"]) + 32))
    temp_text.text = f"{temp} F°"
    humidity = round(float(io.receive_data(hum_feed["key"])["value"]))
    humid_text.text = f"{humidity} %"
    gas = round(float(io.receive_data(co2_feed["key"])["value"]))
    gas_text.text = f"{gas} ppm"
    time_text.text = f"Last updated at {hour}:{minute:02} {am_pm}"

# initial reference time
clock_timer = 1 * 1000
clock_clock = ticks_ms()
clock = update_time()
hour, am_pm = convert_time(clock)
tick = clock[5]
minute = clock[4]

# Get initial values
co2_feed = io.get_feed("plant-co2")
hum_feed = io.get_feed("plant-humidity")
temp_feed = io.get_feed("plant-temperature")
update_clock = ticks_ms()
update_values()

# turn off status light
status_light.fill((0, 0, 0))

while True:
    try:
        if ticks_diff(ticks_ms(), update_clock) >= 10*1000:
            update_values()
            update_clock = ticks_add(update_clock, 10*1000)
        display.refresh()
    except (ValueError, RuntimeError, ConnectionError, OSError) as e:
        print("Failed to get data, retrying...\n", e)
        wifi.reset()
        continue
    if ticks_diff(ticks_ms(), clock_clock) >= clock_timer:
        tick += 1
        if tick > 59:
            tick = 0
            minute += 1
            if minute > 59:
                clock = update_time()
                hour, am_pm = convert_time(clock)
                tick = clock[5]
                minute = clock[4]
        clock_clock = ticks_add(clock_clock, clock_timer)