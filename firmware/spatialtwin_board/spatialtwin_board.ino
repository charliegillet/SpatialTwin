/*
 * SpatialTwin Tabletop Firmware
 * Target: Arduino UNO R4 Minima + Adafruit PCA9685 #815 + 24 NeoPixels
 * Protocol: NDJSON (v: 1) over USB Serial @ 115200 baud
 *
 * Pin Map:
 *   D2: OPEN microswitch (NO, INPUT_PULLUP, COM to GND)
 *   D3: CLOSED microswitch (NO, INPUT_PULLUP, COM to GND)
 *   D6: NeoPixel DIN (24 LEDs through 470 ohm series resistor)
 *   D7: PCA9685 OE (Active LOW, 2.2k ohm pullup to +5V)
 *   A4: I2C SDA
 *   A5: I2C SCL
 */

#include <Wire.h>
#include <Adafruit_PWMServoDriver.h>
#include <Adafruit_NeoPixel.h>
#include "px_codec.h"

#define PIN_OPEN_SW    2
#define PIN_CLOSED_SW  3
#define PIN_PIXEL_DATA 6
#define PIN_PCA_OE     7

#define NUM_PIXELS     24
#define PCA_I2C_ADDR   0x40
#define SERVO_CHANNEL  0
#define SERVO_FREQ_HZ  50

// Calibrated 50Hz servo tick counts (4096 counts per 20ms period = 4.88 us/tick)
#define SERVO_PULSE_CLOSED_TICKS 205  // ~1000 us
#define SERVO_PULSE_OPEN_TICKS   410  // ~2000 us

#define HEARTBEAT_TIMEOUT_MS  1500
#define MOVEMENT_TIMEOUT_MS   2000
#define DEBOUNCE_DELAY_MS     50
#define BLINK_PERIOD_MS       400

Adafruit_PWMServoDriver pca = Adafruit_PWMServoDriver(PCA_I2C_ADDR);
Adafruit_NeoPixel strip = Adafruit_NeoPixel(NUM_PIXELS, PIN_PIXEL_DATA, NEO_GRB + NEO_KHZ800);

enum GateState {
  STATE_UNKNOWN,
  STATE_MOVING,
  STATE_OPEN,
  STATE_CLOSED,
  STATE_FAULT
};

String bootId = "";
uint32_t seq = 0;
uint32_t gateEpoch = 1;
bool isArmed = false;
GateState currentState = STATE_UNKNOWN;
String pendingCommandId = "";
uint32_t movementStartTime = 0;
uint32_t lastHeartbeatTime = 0;
String currentTarget = "CLOSED";

// Debounce trackers
int lastOpenRead = HIGH;
int debouncedOpen = HIGH;
uint32_t lastOpenDebounceTime = 0;

int lastClosedRead = HIGH;
int debouncedClosed = HIGH;
uint32_t lastClosedDebounceTime = 0;

// A SET_DISPLAY line is ~110 bytes; 384 leaves headroom for every other host command.
char rxBuffer[384];
uint16_t rxIndex = 0;

// LED frame from the last accepted SET_DISPLAY. Flashing pixels are shown while blinkPhase is true.
uint32_t pxRgb[PX_COUNT];
uint8_t pxFlash[PX_COUNT];
bool blinkPhase = true;
uint32_t lastBlinkToggle = 0;
// STOP_OUTPUTS darkens the LEDs and keeps them dark: SET_DISPLAY is refused until the next ARM.
bool displayStopped = false;

void emitMessage(const char* type, const String& extraJson) {
  seq++;
  Serial.print("{\"v\":1,\"type\":\"");
  Serial.print(type);
  Serial.print("\",\"boot_id\":\"");
  Serial.print(bootId);
  Serial.print("\",\"seq\":");
  Serial.print(seq);
  Serial.print(",\"gate_epoch\":");
  Serial.print(gateEpoch);
  if (extraJson.length() > 0) {
    Serial.print(",");
    Serial.print(extraJson);
  }
  Serial.println("}");
}

void renderPixels() {
  for (uint8_t i = 0; i < PX_COUNT; i++) {
    uint32_t rgb = (pxFlash[i] && !blinkPhase) ? 0 : pxRgb[i];
    strip.setPixelColor(i, rgb);
  }
  strip.show();
}

// Non-blocking blink: toggles blinkPhase every BLINK_PERIOD_MS and redraws only if a pixel flashes.
void updateBlink() {
  uint32_t now = millis();
  if (now - lastBlinkToggle < BLINK_PERIOD_MS) return;
  lastBlinkToggle = now;
  blinkPhase = !blinkPhase;
  if (displayStopped) return;
  for (uint8_t i = 0; i < PX_COUNT; i++) {
    if (pxFlash[i]) { renderPixels(); return; }
  }
}

void emitObservation(const char* cmdId = nullptr, const char* fault = nullptr) {
  String extra = "\"gate_id\":\"G1\",\"state\":\"";
  switch (currentState) {
    case STATE_OPEN: extra += "OPEN"; break;
    case STATE_CLOSED: extra += "CLOSED"; break;
    case STATE_MOVING: extra += "TRANSIT"; break;
    case STATE_FAULT: extra += "FAULT"; break;
    default: extra += "UNKNOWN"; break;
  }
  extra += "\",\"open_switch\":";
  extra += (debouncedOpen == LOW) ? "true" : "false";
  extra += ",\"closed_switch\":";
  extra += (debouncedClosed == LOW) ? "true" : "false";

  if (cmdId && strlen(cmdId) > 0) {
    extra += ",\"command_id\":\"";
    extra += cmdId;
    extra += "\"";
  }
  if (fault && strlen(fault) > 0) {
    extra += ",\"fault\":\"";
    extra += fault;
    extra += "\"";
  }
  emitMessage("OBSERVATION", extra);
}

void pollSwitches() {
  uint32_t now = millis();

  // Read raw pin states (Active LOW with pull-up)
  int rOpen = digitalRead(PIN_OPEN_SW);
  int rClosed = digitalRead(PIN_CLOSED_SW);

  if (rOpen != lastOpenRead) {
    lastOpenDebounceTime = now;
    lastOpenRead = rOpen;
  }
  if ((now - lastOpenDebounceTime) > DEBOUNCE_DELAY_MS) {
    debouncedOpen = rOpen;
  }

  if (rClosed != lastClosedRead) {
    lastClosedDebounceTime = now;
    lastClosedRead = rClosed;
  }
  if ((now - lastClosedDebounceTime) > DEBOUNCE_DELAY_MS) {
    debouncedClosed = rClosed;
  }
}

void updateGateStateMachine() {
  pollSwitches();
  uint32_t now = millis();

  // Check sensor contradiction (both switches pressed is impossible)
  if (debouncedOpen == LOW && debouncedClosed == LOW) {
    if (currentState != STATE_FAULT) {
      currentState = STATE_FAULT;
      digitalWrite(PIN_PCA_OE, HIGH); // disable outputs
      emitMessage("FAULT", "\"fault\":\"SENSOR_CONTRADICTION_BOTH_PRESSED\"");
      emitObservation(pendingCommandId.c_str(), "SENSOR_CONTRADICTION");
    }
    return;
  }

  if (currentState == STATE_MOVING) {
    if (currentTarget == "OPEN" && debouncedOpen == LOW) {
      currentState = STATE_OPEN;
      gateEpoch++;
      emitObservation(pendingCommandId.c_str());
      pendingCommandId = "";
    } else if (currentTarget == "CLOSED" && debouncedClosed == LOW) {
      currentState = STATE_CLOSED;
      gateEpoch++;
      emitObservation(pendingCommandId.c_str());
      pendingCommandId = "";
    } else if (now - movementStartTime > MOVEMENT_TIMEOUT_MS) {
      // Movement timed out without reaching endpoint switch!
      currentState = STATE_FAULT;
      digitalWrite(PIN_PCA_OE, HIGH);
      emitMessage("FAULT", "\"fault\":\"MOVEMENT_TIMEOUT\"");
      emitObservation(pendingCommandId.c_str(), "MOVEMENT_TIMEOUT");
      pendingCommandId = "";
    }
  } else if (currentState != STATE_FAULT) {
    // Determine state from switches if stationary
    if (debouncedOpen == LOW && debouncedClosed == HIGH) {
      currentState = STATE_OPEN;
    } else if (debouncedOpen == HIGH && debouncedClosed == LOW) {
      currentState = STATE_CLOSED;
    } else {
      currentState = STATE_UNKNOWN;
    }
  }

  // Heartbeat watchdog: disarm if host communication stops
  if (isArmed && (now - lastHeartbeatTime > HEARTBEAT_TIMEOUT_MS)) {
    isArmed = false;
    digitalWrite(PIN_PCA_OE, HIGH);
    emitMessage("FAULT", "\"fault\":\"HEARTBEAT_TIMEOUT_DISARMED\"");
  }
}

// Returns the command_id of a host envelope, or "" if absent. Every reply that answers a command
// echoes this id, so the host can match it to exactly one outstanding command.
String extractCommandId(const String& s) {
  int idIdx = s.indexOf("\"command_id\":\"");
  if (idIdx < 0) return "";
  int endIdx = s.indexOf("\"", idIdx + 14);
  if (endIdx <= idIdx) return "";
  return s.substring(idIdx + 14, endIdx);
}

void parseCommand(char* jsonStr) {
  // Simple bounded key-value scanner to keep memory footprint minimal
  String s = String(jsonStr);

  if (s.indexOf("\"type\":\"HELLO\"") >= 0) {
    lastHeartbeatTime = millis();
    emitMessage("HELLO_ACK", "\"status\":\"READY\"");
    emitObservation();
  }
  else if (s.indexOf("\"type\":\"HEARTBEAT\"") >= 0) {
    lastHeartbeatTime = millis();
  }
  else if (s.indexOf("\"type\":\"ARM\"") >= 0) {
    lastHeartbeatTime = millis();
    isArmed = true;
    displayStopped = false;
    digitalWrite(PIN_PCA_OE, LOW); // Enable PCA9685 driver outputs
    emitMessage("ACK", "\"command_id\":\"" + extractCommandId(s) + "\",\"status\":\"ARMED\"");
    emitObservation();
  }
  else if (s.indexOf("\"type\":\"SET_GATE_TARGET\"") >= 0) {
    lastHeartbeatTime = millis();
    if (!isArmed) {
      emitMessage("FAULT", "\"command_id\":\"" + extractCommandId(s) + "\",\"fault\":\"NOT_ARMED\"");
      return;
    }

    String target = "CLOSED";
    if (s.indexOf("\"target\":\"OPEN\"") >= 0) {
      target = "OPEN";
    }

    // Extract command_id if present
    int idIdx = s.indexOf("\"command_id\":\"");
    String cmdId = "";
    if (idIdx >= 0) {
      int endIdx = s.indexOf("\"", idIdx + 14);
      if (endIdx > idIdx) {
        cmdId = s.substring(idIdx + 14, endIdx);
      }
    }

    pendingCommandId = cmdId;
    currentTarget = target;
    currentState = STATE_MOVING;
    movementStartTime = millis();

    // Command PCA9685 servo pulse
    if (target == "OPEN") {
      pca.setPWM(SERVO_CHANNEL, 0, SERVO_PULSE_OPEN_TICKS);
    } else {
      pca.setPWM(SERVO_CHANNEL, 0, SERVO_PULSE_CLOSED_TICKS);
    }

    // Acknowledge command acceptance (NOT arrival!)
    String ackExtra = "\"command_id\":\"" + cmdId + "\",\"status\":\"ACCEPTED\"";
    emitMessage("ACK", ackExtra);
    emitObservation(cmdId.c_str());
  }
  else if (s.indexOf("\"type\":\"SET_DISPLAY\"") >= 0) {
    // Informational only: does not need ARM and never touches the servo path. The reply always
    // echoes command_id so the host can match it; a rejected frame leaves the LEDs unchanged.
    String cmdId = extractCommandId(s);
    if (displayStopped) {
      emitMessage("FAULT", "\"command_id\":\"" + cmdId + "\",\"fault\":\"DISPLAY_STOPPED\"");
      return;
    }
    uint32_t newRgb[PX_COUNT];
    uint8_t newFlash[PX_COUNT];
    if (px_parse(jsonStr, newRgb, newFlash) != PX_OK) {
      emitMessage("FAULT", "\"command_id\":\"" + cmdId + "\",\"fault\":\"BAD_PX\"");
      return;
    }
    memcpy(pxRgb, newRgb, sizeof(pxRgb));
    memcpy(pxFlash, newFlash, sizeof(pxFlash));
    blinkPhase = true;
    lastBlinkToggle = millis();
    renderPixels();
    emitMessage("ACK", "\"command_id\":\"" + cmdId + "\",\"status\":\"DISPLAY_UPDATED\"");
  }
  else if (s.indexOf("\"type\":\"STOP_OUTPUTS\"") >= 0) {
    isArmed = false;
    displayStopped = true;
    digitalWrite(PIN_PCA_OE, HIGH);
    memset(pxRgb, 0, sizeof(pxRgb));
    memset(pxFlash, 0, sizeof(pxFlash));
    strip.clear();
    strip.show();
    emitMessage("ACK", "\"command_id\":\"" + extractCommandId(s) + "\",\"status\":\"STOPPED\"");
  }
}

void setup() {
  Serial.begin(115200);

  // Microswitches with internal pullups
  pinMode(PIN_OPEN_SW, INPUT_PULLUP);
  pinMode(PIN_CLOSED_SW, INPUT_PULLUP);

  // PCA Output Enable pin (Active LOW) - start HIGH to inhibit servo twitch
  pinMode(PIN_PCA_OE, OUTPUT);
  digitalWrite(PIN_PCA_OE, HIGH);

  // Initialize NeoPixels
  strip.begin();
  strip.setBrightness(60); // Conservative ~25% brightness limit
  strip.clear();
  strip.show();

  // Initialize I2C and PCA9685
  Wire.begin();
  pca.begin();
  pca.setPWMFreq(SERVO_FREQ_HZ);

  // Generate random boot ID from analog noise
  randomSeed(analogRead(0));
  bootId = "uno-" + String(random(100000, 999999));

  lastHeartbeatTime = millis();
}

void loop() {
  updateGateStateMachine();
  updateBlink();

  // Read incoming NDJSON from USB serial
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n' || c == '\r') {
      if (rxIndex > 0) {
        rxBuffer[rxIndex] = '\0';
        parseCommand(rxBuffer);
        rxIndex = 0;
      }
    } else {
      if (rxIndex < sizeof(rxBuffer) - 1) {
        rxBuffer[rxIndex++] = c;
      }
    }
  }
}
