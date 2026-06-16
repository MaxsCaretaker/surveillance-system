import board
import busio
import adafruit_ssd1306
from PIL import Image, ImageDraw, ImageFont
import time

# Initialize I2C and display
i2c = busio.I2C(board.SCL, board.SDA)
oled = adafruit_ssd1306.SSD1306_I2C(128, 64, i2c)

def clear():
    oled.fill(0)
    oled.show()

def display_text(line1="", line2="", line3=""):
    image = Image.new("1", (oled.width, oled.height))
    draw = ImageDraw.Draw(image)
    draw.text((0, 0),  line1, fill=255)
    draw.text((0, 20), line2, fill=255)
    draw.text((0, 40), line3, fill=255)
    oled.image(image)
    oled.show()

# Test
print("Testing OLED display...")
clear()
display_text("SURVEILLANCE", "SYSTEM", "ONLINE")
print("Check your OLED screen")
time.sleep(5)
clear()
print("Done")
