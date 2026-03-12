#include <PulseSensorPlayground.h>
#include <LiquidCrystal.h>

// ---------------- LCD Connections ----------------
const int RS = 12;
const int E = 11;
const int D4 = 5;
const int D5 = 4;
const int D6 = 3;
const int D7 = 2;
LiquidCrystal lcd(RS, E, D4, D5, D6, D7);

// ---------------- Sensor and Buzzer ----------------
const int PulseWire = A0;
const int BUZZER = 13;
const int Threshold = 523;
PulseSensorPlayground pulseSensor;

// ---------------- Alarm Settings ----------------
const int ALARM_HOUR = 8;     // Set alarm hour (24h format)
const int ALARM_MINUTE = 10;  // Set alarm minute
const unsigned long SAMPLE_DURATION = 90000UL; // 90 sec window for avg BPM

// ---------------- Variables ----------------
int currentHour = 0;
int currentMinute = 0;
String timeString = "";
bool alarmActive = false;
int chosenTone = 0;
unsigned long lastSampleTime = 0;
long bpmSum = 0;
int bpmCount = 0;
int lastBPM = 0;
String currentStage = "Unknown";

void setup() {
  Serial.begin(115200);
  lcd.begin(16, 2);
  lcd.print("Initializing...");

  pinMode(BUZZER, OUTPUT);
  digitalWrite(BUZZER, LOW);

  pulseSensor.analogInput(PulseWire);
  pulseSensor.setThreshold(Threshold);

  if (pulseSensor.begin()) {
    lcd.setCursor(0, 1);
    lcd.print("Sensor Ready");
    Serial.println("PulseSensor Ready");
  }

  delay(2000);
  lcd.clear();
  lcd.print("System Ready");
  delay(1000);
  lcd.clear();
}

// ---------------- LOOP ----------------
void loop() {
  // ----------- Get current time from Python script -----------  
  if (Serial.available() > 0) {
    timeString = Serial.readStringUntil('\n'); // expecting "HH:MM"
    timeString.trim();

    int colonIndex = timeString.indexOf(':');
    if (colonIndex > 0) {
      currentHour = timeString.substring(0, colonIndex).toInt();
      currentMinute = timeString.substring(colonIndex + 1).toInt();
    }
  }

  // ----------- Read and display real-time BPM continuously -----------  
  if (pulseSensor.sawStartOfBeat()) {
    int bpm = pulseSensor.getBeatsPerMinute();
    if (bpm >= 30 && bpm <= 120) {
      bpmSum += bpm;
      bpmCount++;
      lastBPM = bpm;

      // Determine real-time stage (for display)
      if (bpm >= 40 && bpm <= 60) currentStage = "Sleeping";
      else if (bpm > 60 && bpm <= 100) currentStage = "Awake   ";
      else currentStage = "Abnormal";

      // Display live BPM and stage
      lcd.setCursor(0, 0);
      lcd.print("BPM:");
      lcd.print(bpm);
      lcd.print(" ");
      lcd.setCursor(8, 0);
      lcd.print(currentStage);
    }
  }

  // ----------- Every 90 seconds, evaluate average BPM -----------  
  if (millis() - lastSampleTime >= SAMPLE_DURATION) {
    int avgBPM = (bpmCount > 0) ? bpmSum / bpmCount : 0;
    bpmSum = 0;
    bpmCount = 0;
    lastSampleTime = millis();

    bool isSleeping = false;
    String stage = "";

    if (avgBPM >= 40 && avgBPM <= 60) {
      stage = "Sleep";
      isSleeping = true;
    } else if (avgBPM > 60 && avgBPM <= 100) {
      stage = "Awake";
      isSleeping = false;
    } else {
      stage = "Abnorm";
      isSleeping = false;
    }

    // Display summary on LCD for a short time
    lcd.clear();
    lcd.setCursor(0, 0);
    lcd.print("Avg BPM:");
    lcd.print(avgBPM);
    lcd.setCursor(0, 1);
    lcd.print("Stage:");
    lcd.print(stage);
    delay(2000);
    lcd.clear();

    // Alarm ON only when alarm time and sleeping
    if (currentHour == ALARM_HOUR && currentMinute == ALARM_MINUTE) {
      if (isSleeping) {
        if (!alarmActive) {
          alarmActive = true;
          chosenTone = random(1, 11);
        }
        playTone(chosenTone);
      } else {
        noTone(BUZZER);
        alarmActive = false;
      }
    } else {
      noTone(BUZZER);
      alarmActive = false;
    }
  }

  delay(20); // Small delay for stable readings
}

// ---------------- Tone Player ----------------
void playTone(int choice) {
  switch (choice) {
    case 1: radarTone(); break;
    case 2: beepBeepBeep(); break;
    case 3: morningFlower(); break;
    case 4: classicBell(); break;
    case 5: digitalBuzzer(); break;
    case 6: chimes(); break;
    case 7: roosterCrowing(); break;
    case 8: reveille(); break;
    case 9: varyingTones(); break;
    case 10: natureSounds(); break;
  }
}

// ---------------- Tone Definitions ----------------
void radarTone() { for (int i=0;i<6;i++){tone(BUZZER,600+(i*150),200);delay(200);} delay(300); for (int i=0;i<4;i++){tone(BUZZER,1200-(i*100),150);delay(150);} noTone(BUZZER);}
void beepBeepBeep() { for (int i=0;i<5;i++){tone(BUZZER,1000,200);delay(250);} noTone(BUZZER);}
void morningFlower() { int melody[]={523,659,784,988,784,659,523}; for(int i=0;i<7;i++){tone(BUZZER,melody[i],250);delay(300);} noTone(BUZZER);}
void classicBell() { for(int i=0;i<3;i++){tone(BUZZER,1000,100);delay(100);tone(BUZZER,800,100);delay(200);} noTone(BUZZER);}
void digitalBuzzer() { tone(BUZZER,900); delay(2000); noTone(BUZZER);}
void chimes() { int melody[]={523,659,784,1046}; for(int i=0;i<4;i++){tone(BUZZER,melody[i],400);delay(450);} noTone(BUZZER);}
void roosterCrowing() { for(int i=0;i<3;i++){tone(BUZZER,800,200);delay(100);tone(BUZZER,1000,300);delay(150);tone(BUZZER,700,500);delay(300);} noTone(BUZZER);}
void reveille() { int melody[]={784,988,784,988,784,988,784}; for(int i=0;i<7;i++){tone(BUZZER,melody[i],200);delay(220);} noTone(BUZZER);}
void varyingTones() { for(int i=0;i<10;i++){tone(BUZZER,500+i*100,100);delay(120);} noTone(BUZZER);}
void natureSounds() { for(int i=0;i<5;i++){tone(BUZZER,1200+random(-200,200),150);delay(400);} noTone(BUZZER);}
