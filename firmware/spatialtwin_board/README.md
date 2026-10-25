# SpatialTwin Tabletop Firmware

Target: **Arduino UNO R4 Minima** with **Adafruit PCA9685 16-Channel PWM breakout (#815)** and **24 WS2812B RGB NeoPixels**.

## Pin Connections

| UNO R4 Pin | Connected To | Notes |
|------------|--------------|-------|
| USB-C | Laptop USB Port | 115200 baud, line-delimited JSON (NDJSON) |
| +5V | PCA9685 VCC | Logic power only |
| GND | Common Star Ground | Common ground with 5V 4A power supply |
| A4 | PCA9685 SDA | I2C Data |
| A5 | PCA9685 SCL | I2C Clock |
| D2 | OPEN Microswitch (NO) | `INPUT_PULLUP`, COM to GND |
| D3 | CLOSED Microswitch (NO) | `INPUT_PULLUP`, COM to GND |
| D6 | NeoPixel Data IN | 470Ω series resistor to Stick A DIN |
| D7 | PCA9685 OE | Active LOW, 2.2kΩ pull-up to +5V |

## Power Isolation
- **Regulated 5V 4A External Supply**: Powers NeoPixels +5V and PCA9685 V+ (servo load power) through 3.15A M fuse.
- **Laptop USB**: Powers UNO R4 and PCA9685 logic VCC only.
- **Never connect external +5V load to UNO +5V or USB.**

## Libraries Required
1. `Adafruit PWM Servo Driver Library`
2. `Adafruit NeoPixel`
3. `Wire` (built-in)

## Upload Instructions
1. Open `spatialtwin_board.ino` in Arduino IDE 2.x or use `arduino-cli`.
2. Select Board: **Arduino UNO R4 Minima**.
3. Select Port: `/dev/cu.usbmodem...`
4. Click **Upload**.
