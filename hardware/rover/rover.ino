/*
 * Sunchaser hardware-in-the-loop rover (owner: Harril)
 *
 * A small 2-wheel robot that drives the planned route on a printed map while its
 * light sensor feeds the battery simulation on the laptop (hardware/bridge.py).
 * Shine a lamp on it ("the Sun") and the simulated battery charges; shade it and
 * the battery drains; let it run low and the laptop tells it to stop and wait.
 *
 * Hardware: Arduino Uno, L298N motor driver, 2WD chassis, LDR + 10 kOhm divider.
 *   L298N IN1..IN4 -> pins 5, 6, 9, 10     ENA -> 3 (PWM)     ENB -> 11 (PWM)
 *   LDR between 5V and A0, 10 kOhm between A0 and GND (brighter = higher reading)
 *   Motor battery ground joined to Arduino ground.
 *
 * Serial protocol (115200 baud, one command per line):
 *   F n      drive forward n cells (n may be a decimal, e.g. F 1.41 for a diagonal)
 *   L deg    turn left by deg degrees        R deg    turn right by deg degrees
 *   W s      wait s seconds
 *   STOP     pause immediately (the current command is kept and resumed by GO)
 *   GO       resume
 * The rover answers "DONE" when a command finishes, and prints "LIGHT <0-1023>"
 * ten times a second all the time, including while it is moving or paused.
 *
 * Motion is timed, not measured (no wheel encoders): calibrate the two constants
 * below on the real floor. Nothing here blocks, so STOP always gets through.
 *
 * NOTE: written for the hackathon and checked by reading and by the bridge's
 * simulator; it has not been run on physical hardware by the team yet.
 */

const int IN1 = 5, IN2 = 6, IN3 = 9, IN4 = 10, ENA = 3, ENB = 11;
const int LDR_PIN = A0;

// ---- calibrate these on your floor ----
const unsigned long MS_PER_CELL   = 1200;  // time to drive one grid cell on the printed map
const unsigned long MS_PER_45_DEG = 260;   // time to turn 45 degrees on the spot
const int DRIVE_PWM = 170;                 // 0-255
const int TURN_PWM  = 150;

enum Motion { IDLE, FORWARD, TURN_LEFT, TURN_RIGHT, WAITING };
Motion motion = IDLE;
unsigned long remainingMs = 0;   // time still to run for the current command
unsigned long lastTick = 0;
unsigned long lastLight = 0;
bool paused = false;
String line = "";

void motors(int leftDir, int rightDir, int pwm) {
  // dir: +1 forward, -1 backward, 0 stop
  digitalWrite(IN1, leftDir > 0);   digitalWrite(IN2, leftDir < 0);
  digitalWrite(IN3, rightDir > 0);  digitalWrite(IN4, rightDir < 0);
  analogWrite(ENA, leftDir == 0 ? 0 : pwm);
  analogWrite(ENB, rightDir == 0 ? 0 : pwm);
}

void applyMotion() {
  if (paused) { motors(0, 0, 0); return; }
  switch (motion) {
    case FORWARD:    motors(+1, +1, DRIVE_PWM); break;
    case TURN_LEFT:  motors(-1, +1, TURN_PWM);  break;
    case TURN_RIGHT: motors(+1, -1, TURN_PWM);  break;
    default:         motors(0, 0, 0);           break;
  }
}

void startMotion(Motion m, unsigned long ms) {
  motion = m;
  remainingMs = ms;
  lastTick = millis();
  applyMotion();
  if (ms == 0) { motion = IDLE; applyMotion(); Serial.println("DONE"); }
}

void handle(String cmd) {
  cmd.trim();
  if (cmd.length() == 0) return;
  if (cmd == "STOP") { paused = true;  applyMotion(); return; }
  if (cmd == "GO")   { paused = false; lastTick = millis(); applyMotion(); return; }
  char c = cmd.charAt(0);
  float value = cmd.substring(1).toFloat();
  if (value < 0) value = 0;
  if      (c == 'F') startMotion(FORWARD,    (unsigned long)(value * MS_PER_CELL));
  else if (c == 'L') startMotion(TURN_LEFT,  (unsigned long)(value / 45.0 * MS_PER_45_DEG));
  else if (c == 'R') startMotion(TURN_RIGHT, (unsigned long)(value / 45.0 * MS_PER_45_DEG));
  else if (c == 'W') startMotion(WAITING,    (unsigned long)(value * 1000.0));
  else Serial.println("ERR unknown command");
}

void setup() {
  pinMode(IN1, OUTPUT); pinMode(IN2, OUTPUT); pinMode(IN3, OUTPUT); pinMode(IN4, OUTPUT);
  pinMode(ENA, OUTPUT); pinMode(ENB, OUTPUT);
  motors(0, 0, 0);
  Serial.begin(115200);
  Serial.println("READY");
}

void loop() {
  // 1. read commands, one line at a time
  while (Serial.available()) {
    char ch = Serial.read();
    if (ch == '\n') { handle(line); line = ""; }
    else if (ch != '\r') line += ch;
  }

  // 2. count down the current command (the clock stops while paused)
  unsigned long now = millis();
  if (motion != IDLE && !paused) {
    unsigned long dt = now - lastTick;
    if (dt >= remainingMs) {
      motion = IDLE;
      remainingMs = 0;
      applyMotion();
      Serial.println("DONE");
    } else {
      remainingMs -= dt;
    }
  }
  lastTick = now;

  // 3. report the light level ten times a second
  if (now - lastLight >= 100) {
    lastLight = now;
    Serial.print("LIGHT ");
    Serial.println(analogRead(LDR_PIN));
  }
}
