# SpatialTwin physical demo: verified wiring and firmware design

Companion to the [physical build plan and budget](PHYSICAL_DEMO_BUILD_PLAN.md). Match the [shopping list](PHYSICAL_DEMO_BOM.csv), exact board revision and actual measured mechanism before assembly.

Research checked 23 October 2026. This is a construction plan, not a bench-tested circuit or firmware release. Primary manufacturer docs/source were fetched with Firecrawl; the Adafruit Eagle schematic was inspected with authenticated GitHub CLI because the guessed GitHub scrape path was absent.

## Recommended fixed hardware architecture

Use **Arduino UNO R4 Minima, USB-C data cable to laptop, Adafruit PCA9685 breakout #815, one positional microservo, and three 8-pixel RGB NeoPixel sticks (24 pixels total)**. Power the UNO only by laptop USB. Independently power the 24 pixels and servo from the regulated 5 V 4 A Adafruit #1466 supply. Add a common ground, but keep the two positive power rails separate.

**Do not include Servo.h.** The PCA9685 generates the servo waveform independently over I2C. This small additional board is justified: current Adafruit NeoPixel code has a Renesas/UNO R4 branch, but `show()` still disables interrupts; the current Arduino Renesas Servo implementation generates edges from FspTimer interrupt callbacks. These are separately supported libraries, not evidence that their combination produces stable servo pulses. At 800 kbit/s, a 24-RGB-pixel frame occupies approximately 24 × 24 / 800000 = 0.72 ms (32 pixels: 0.96 ms), material compared with a typical 1–2 ms servo pulse. External PWM avoids that timing dependency.

Sources: [UNO R4 hardware](https://docs.arduino.cc/hardware/uno-r4-minima/), [current NeoPixel source](https://github.com/adafruit/Adafruit_NeoPixel/blob/master/Adafruit_NeoPixel.cpp), [current Renesas Servo source](https://github.com/arduino-libraries/Servo/blob/master/src/renesas/Servo.cpp), [Adafruit explanation of NeoPixel/servo conflicts](https://learn.adafruit.com/neopixels-and-servos/the-issue).

## Exact signal pin map

| UNO R4 Minima pin | Connect to | Notes |
|---|---|---|
| USB-C | Laptop USB data port | Power and serial only; no VIN/barrel power |
| +5V | PCA9685 **VCC** | Logic power only, also powers PCA I2C pullups |
| GND | Negative star distribution; PCA GND | Required common signal reference |
| A4/SDA | PCA SDA | A4 and dedicated SDA are the same signal; choose one header location |
| A5/SCL | PCA SCL | A5 and dedicated SCL are the same signal |
| D6 | 470 ohm resistor, then first stick DIN | Resistor physically close to first DIN; no separate logic level shifter with this 5 V MCU |
| D7 | PCA **OE** | LOW enables outputs, HIGH disables; add 2.2 kohm pullup described below |
| D2 | OPEN microswitch NO | INPUT_PULLUP; switch COM to common GND; NC unconnected |
| D3 | CLOSED microswitch NO | INPUT_PULLUP; switch COM to common GND; NC unconnected |
| D4, optional | Capture/confirm pushbutton NO | INPUT_PULLUP; COM to GND; sends a button event, never bypasses review |

PCA channel **0 PWM** → servo signal (usually orange/yellow/white); channel 0 V+ → servo red; channel 0 GND → servo brown/black. Add **10 kohm from servo signal to GND** near the servo connector so the signal has a LOW bias if the PCA logic is unpowered while external servo power is on. The PCA already has 220 ohm output series resistance; a 10 kohm pulldown is a small load. This does not guarantee that the particular servo will never twitch at power-up. Verify the actual servo label/color convention. Leave unused PCA outputs full-off. Keep I2C short (<30 cm target), route NeoPixel data beside its ground return, and keep individual data jumps short (<30 cm target). Solder strain-relieved connections; do not carry servo/pixel supply through a solderless breadboard or UNO header.

[Official UNO pinout](https://docs.arduino.cc/resources/pinouts/ABX00080-full-pinout.pdf) confirms A4/SDA, A5/SCL, 8 mA maximum per GPIO and 60 mA overall. [PCA pinouts](https://learn.adafruit.com/16-channel-pwm-servo-driver/pinouts) distinguish VCC from V+ and document the 5 V logic compatibility.

## Boot-inhibit OE wiring: detail that matters

Add **2.2 kohm, 1/4 W resistor from PCA OE to UNO +5V**. D7 connects directly to OE. Adafruit board #815 rev C includes **R7 = 10 kohm from OE to GND**. With D7 floating at reset, this creates approximately 5 × 10/(10+2.2) = **4.10 V**, above the PCA input HIGH minimum of 0.7 × VDD = 3.5 V. With D7 LOW, it sinks about 5/2200 = **2.27 mA**, below the UNO R4 per-pin limit. A generic 10 kohm pullup would make a 2.5 V divider and is unsuitable here. Confirm the actual received board revision/schematic before substituting a clone.

Initialize D7 HIGH at the first opportunity; configure the PCA, full-off unused channels and calibrate/arm before D7 may go LOW. On reset, USB loss, command timeout or sensor fault, OE should become HIGH. **Disabling pulses does not make a positional servo return closed, lock, or resist manual movement.** Treat the mechanism as unpowered and read the switches; never describe this as an automatic fail-closed design.

Sources: [Adafruit rev C schematic](https://github.com/adafruit/Adafruit-16-Channel-PWM-Servo-Driver-PCB/blob/master/Adafruit%20PCA9685%20rev%20C.sch), [PCA9685 datasheet](https://cdn-shop.adafruit.com/datasheets/PCA9685.pdf), [PCA pinouts](https://learn.adafruit.com/16-channel-pwm-servo-driver/pinouts).

## Power wiring

```text
Laptop USB ──USB-C── UNO R4 Minima
                     │ +5V ────────────────── PCA VCC (logic)
                     │ GND ───────────────┐
                     │ D7 ───── PCA OE    │
                     │         │         │
                     │ +5V─2k2─┘         │
                     │ A4/A5 ── PCA SDA/SCL
                     │ D6─470Ω─ Stick A DIN
                     │ D2/D3 ─ OPEN/CLOSED switches ─ GND
                     │
5V 4A regulated PSU  │
 + ─ 2.1mm DC disconnect ─ inline DC fuse ─ +5V load distribution
                                         ├── Stick A +5V
                                         ├── Stick B +5V
                                         ├── Stick C +5V
                                         └── PCA V+ screw terminal ─ Servo red
 - ─────────────────────────────────── Negative star
                                         ├── UNO GND
                                         ├── all Stick GND
                                         └── PCA GND / Servo GND

Stick A DOUT ── Stick B DIN; Stick B DOUT ── Stick C DIN
Stick C DOUT left unconnected.
```

Use a **5 A DC-rated connector**, **Bulgin FX0380/BK 5×20 screw-terminal fuse holder** (10 A, 50 VDC per BOM research), **Schurter FSM 5×20 0034.2521 3.15 A medium-time-lag M fuse**, 20 AWG stranded supply/distribution wires, and short factory servo leads. The Schurter manufacturer datasheet explicitly rates this series at 250 VAC / 125 VDC; part 0034.2521 is the 3.15 A member with 1000 A breaking capacity at 125 VDC. It is **M, not T**. The exact [DigiKey US part](https://www.digikey.com/en/products/detail/schurter-inc/0034-2521/640091) listed $2.18 each and 473 in stock when checked on 23 October 2026; stock/pricing can change. The 3.15 A nominal target is reasonable against the 2.54 A load allowance, but measured inrush, fuse derating, wire/connector ratings and voltage drop must be checked. Supply current limiting does not replace wiring inspection. Do not buy the 2 A Adafruit #1125 inline switch for this 4 A supply; omit a switch and use the accessible 2.1mm DC disconnect during the documented shutdown sequence. A later switch must have a verified DC rating sufficient for the circuit. Main load distribution must be a screw terminal/perfboard distribution assembly, not a breadboard rail. Put the board on insulated standoffs, cover the underside and strain-relieve the barrel input.

[Schurter manufacturer fuse datasheet](https://www.schurter.com/en/datasheet/typ_FSM_5x20.pdf).

At the first LED power entry add **1000 microfarad, 10 V electrolytic capacitor** across load +5V/GND, correct polarity (stripe to GND). Put **470 microfarad, 10 V electrolytic** near the servo/PCA V+ branch to reduce local transients. This is an engineering starting choice, not a guarantee against a stalled servo. Adafruit's LED guidance recommends 500–1000 microfarad at 6.3 V or higher, a 300–500 ohm DIN resistor, separate-supply common ground, and no hot plugging.

**No positive bridge:** external +5V load rail connects to PCA **V+**, pixels and servo only. It must not connect to UNO +5V, UNO VIN, PCA VCC, laptop USB VBUS, or any I2C pin. UNO +5V powers PCA VCC; these two similarly labeled power pins are deliberately different. Common ground is intentional and does not join positive supplies. PCA output pins drive servo signal, not motor power.

Power-up order: install wiring with both supplies disconnected; verify polarity/continuity; turn on regulated external 5 V first, then attach USB. NeoPixel data pin remains LOW/input until firmware and load power are ready. Normal shutdown: stop/disable servo, clear LEDs, drive D6 LOW, disconnect USB, then disconnect external 5 V at its 2.1mm load connector. Adafruit warns that a powered MCU driving an unpowered pixel can feed it through DIN. A physical load-power cut while USB remains connected therefore requires the firmware to keep D6 LOW; do not sell power-order discipline as an electrically interlocked supply. If a true hard power-cut interlock is required, use a rated double-pole switch to disconnect load +5V **and** the D6 data connection (leave ground connected), then verify switch contact timing on the bench. Do not insert an external-rail voltage divider into a powered-off UNO input without accounting for input-diode backfeed.

Sources: [NeoPixel best practices](https://learn.adafruit.com/adafruit-neopixel-uberguide/best-practices), [NeoPixel current estimation](https://learn.adafruit.com/adafruit-neopixel-uberguide/powering-neopixels), [PCA hooking-up guide](https://learn.adafruit.com/16-channel-pwm-servo-driver/hooking-it-up).

## Current budget and brightness

| Load | Conservative design allocation |
|---|---:|
| 24 RGB NeoPixels, 60 mA each at full white | 1.44 A |
| One positional microservo | 1.00 A provisional transient allowance |
| Load reserve | 0.10 A |
| Total load-supply allocation | **2.54 A / 12.7 W** |
| Regulated supply | **5 V 4 A / 20 W** |

The 1 A servo allocation is **not a measured or manufacturer-certified stall rating**. Check the selected servo and measure worst movement current. At 32 pixels, allocation rises to 3.02 A; still within a 4 A supply but requires final wiring/fuse review. Do not silently install a whole 60-pixel meter (3.6 A LED full-white alone) on this budget. Use only 24 pixels and cap brightness to approximately 25% initially, then tune for ambient venue visibility. Size power for the uncapped worst case above; dimming is an operating choice. Avoid full-white strobing and do not use LED color as the only explanation.

UNO/PCA logic current comes from USB separately and is not included as a load powered by the external PSU. No motor current passes through the Arduino regulator.

## Mechanical position confirmation

Use two independent normally-open lever microswitches mounted at the ends of a lightweight hinged partition's travel. The flap/servo cam should press OPEN only in its physically clear position and CLOSED only in its blocking position, with clearance to avoid forcing the servo against a hard stop. The link/hinge must stay outside the judge's hand-placement region. A servo reports neither actual angle nor arrival over its ordinary three-wire connector.

| Debounced D2 OPEN | Debounced D3 CLOSED | Truth |
|---|---|---|
| LOW | HIGH | Open confirmed |
| HIGH | LOW | Closed confirmed |
| HIGH | HIGH | Transit/unknown/unplugged; never infer open |
| LOW | LOW | Sensor conflict; inhibit motion, mark fault |

This is a useful consistency check, not a certified redundant safety circuit. A disconnected NO switch reads inactive. Poll around every 5 ms with 40–60 ms debounce; track sensor transitions and reject impossible combinations. Set a **provisional 2 second arrival timeout**, to be tuned from actual travel time with margin. A timeout disables pulses, reports UNKNOWN/FAULT, and leaves the reserve connection unavailable to the accepted scenario. Do not automatically retry a potentially jammed servo. Any manual movement or unexpected switch change invalidates the digital hardware assumption until reconciled.

Calibrate with the horn disconnected: PCA at **50 Hz**, center pulse about **1500 microseconds**, initially tiny travel (e.g. 1450–1550 microseconds), then expand only within the chosen servo's specifications and mechanism clearance. Store measured `closed_us` and `open_us` values in configuration. Do not treat the library example's raw minimum/maximum ticks as safe mechanical endpoints. PCA pulse timing varies with oscillator/servo calibration; verify real travel and, preferably, waveform with a logic analyzer. [Adafruit calibration guidance](https://learn.adafruit.com/16-channel-pwm-servo-driver/using-the-adafruit-library).

## Firmware and serial contract

Dependencies: Arduino Renesas UNO board core for UNO R4 Minima; Wire; Adafruit PWM Servo Driver Library; its Adafruit BusIO dependency; Adafruit NeoPixel; optionally ArduinoJson for bounded NDJSON parsing. Pin tested versions at the first bench milestone. Use USB `Serial` at nominal 115200, not D0/D1 hardware serial. Compile and run a 1-pixel sketch, a PCA-only servo sketch, then integrated hardware before model fabrication.

Keep a nonblocking loop: poll switches, parse bounded complete serial lines, run movement state machine, coalesce LED frames and publish state. Do not perform network/Gemini work on the Arduino. Target <=10 LED updates/second, and update static lights only when state changes. The 0.72 ms show blackout no longer affects PCA waveform generation; still test serial delivery and switch monitoring at peak updates. Host waits for ACK and uses bounded message rates; it should not flood frames or assume every write arrived.

Use the build plan's canonical NDJSON naming: `v:1`, command `type`, `session_id`, unique `command_id`, `expected_boot_id`, expected gate epoch, scenario revision and calibrated target. Host types are `HELLO`, `HEARTBEAT`, `READ_STATE`, `ARM`, `SET_GATE_TARGET` with `OPEN|CLOSED`, `SET_DISPLAY`, and `STOP_OUTPUTS`. Firmware types are `HELLO_ACK`, `ACK`, `OBSERVATION`, `FAULT`; telemetry has increasing `seq` within `boot_id`. The AI never supplies arbitrary pin, pulse width or RGB programs. Firmware clamps to configured travel and LED count/brightness, rejects malformed/oversized lines and motion while faulted/unarmed. Commands are idempotent by command_id within the current boot; after reboot require handshake/reconciliation rather than replaying old motion.

Outgoing events distinguish `command_accepted`, `motion_started`, `position_confirmed`, `motion_timeout`, `sensor_conflict`, `heartbeat`, `device_restarted`. Include hardware revision and raw/debounced switch bits. Receiving `command_accepted` does **not** commit an open connection. Only matching fresh position confirmation allows the host to commit observed hardware state and recompute accepted routes. Predicted alternatives remain labeled predicted beforehand.

Host heartbeat approximately 250 ms; if missing for **1.5 seconds**, firmware disables PCA outputs, cancels pending motion, marks itself unarmed and puts LEDs in a neutral stale pattern if supply remains available. No claim that a servo closes on communication/power loss. On reconnect, the host reads actual switches and reconciles before rearming. Physical USB cable disconnection and software timeout must be rehearsed separately.

Suggested state machine: `BOOT_DISABLED → WAIT_HANDSHAKE → READY_CLOSED|READY_OPEN|UNKNOWN → MOVING → CONFIRMED|FAULT`. From any state STOP → `DISABLED` (position still read). Startup must never perform an automatic homing movement in front of a judge. A deliberate human reset/rearm is required after sensor conflict or motion timeout.

## Judge token / Argon separation

Default judge input remains a large visual blockage token on the floor plan. Overhead camera goes directly to the laptop, not Arduino. Optional D4 button requests one capture. Argon grounding proposes a supported canonical entity (`portal:P1`, `portal:P2`, or `boundary:B2`); host validation plus user review accepts the hypothetical closure. The planner returns checked results and route/queue semantics; a local hardware adapter maps approved states to fixed LED indices. Motor commands require explicit approval of an allowed modeled intervention. Camera interpretation, switch observation and computed metrics have different provenance and must not overwrite each other silently.

## Minimum bench acceptance before final assembly

1. Power off continuity: no short +5V/GND; external +5V does not connect to UNO5V or PCA VCC; both ground networks intentionally join.
2. Meter regulated load voltage/polarity before connecting pixels/servo; inspect capacitor polarity.
3. Observe external-power-first startup and USB attach/reset: OE must stay disabled and no commanded servo sweep may occur. A servo-signal pulldown reduces floating input risk; actual power-on twitch behavior must be checked, not guaranteed.
4. Exercise 24 LEDs at capped brightness; confirm logical mapping by chasing one LED at a time; full-white test only briefly with measured current.
5. Calibrate unloaded servo, attach lightweight mechanism, and verify each switch separately and both truth-table fault cases.
6. At least 30 open/close cycles with LED updates active, no resets/jitter, no sustained stall/buzz, both end states independently confirmed.
7. Simulate missed arrival/unplugged switch without forcing a stalled motor; observe timeout/no automatic retry/no route commit.
8. Disconnect USB/reconnect; verify no automatic replay; manually move flap and show state reconciliation.
9. Rehearse AI-offline manual selection and servo-fault UI; comparison stays a predicted alternative until physical confirmation.

The combined electrical build, current draw, firmware library versions, camera geometry and actual mechanism have not yet been tested. The source inspection supports this design choice; it does not substitute for these acceptance checks.
