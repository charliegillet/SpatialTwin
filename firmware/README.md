# SpatialTwin board firmware

`spatialtwin_board/spatialtwin_board.ino` targets Arduino UNO R4 Minima + PCA9685 + 24 NeoPixels (NDJSON v1, 115200 baud). Libraries: Adafruit PWM Servo Driver, Adafruit NeoPixel.

## SET_DISPLAY

Host line (about 110 bytes, budget 128): `{"v":1,"type":"SET_DISPLAY","session_id":"..","command_id":"cmd-N","px":"<24 chars>"}`.
LEDs 0-7 are P1, 8-15 P2, 16-23 P3. One code per pixel (defined in `px_codec.h` and `backend/app/hardware/display.py` `PX_CODE_RGB`; keep both in sync):

| Code | Colour | Used for |
| --- | --- | --- |
| `0` | off | |
| `G` | green | portal carries modeled flow, gate OPEN |
| `R` | red | portal blocked, gate FAULT |
| `A` | amber | gate in TRANSIT |
| `B` | dim blue | portal idle, gate CLOSED |
| `U` | purple | gate state UNKNOWN |
| `g r a u` | flashing green / red / amber / purple | accepted by the device (400 ms blink); the host does not emit them yet |

Replies echo `command_id`: `ACK {status: DISPLAY_UPDATED}`, or `FAULT {fault: BAD_PX}` (wrong length, unknown code, missing key; LEDs unchanged), or `FAULT {fault: DISPLAY_STOPPED}` (after `STOP_OUTPUTS` the LEDs stay dark until the next `ARM`). SET_DISPLAY does not need ARM and never touches the servo.

## Verification

- Host test of the parser: `cc -I spatialtwin_board tests/test_px_codec.c -o /tmp/px && /tmp/px` (also run by `tests/hardware/test_firmware_px_codec.py`).
- The sketch itself is not compiled in CI; compile and flash it with Arduino IDE or `arduino-cli` on the bench, then check the LEDs follow P2 blocked, then P3 open.
