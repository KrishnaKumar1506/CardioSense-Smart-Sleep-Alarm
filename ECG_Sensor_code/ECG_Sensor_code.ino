/*
   ECG (AD8232) with BPM & HRV Calculation + Random Buzzer Tones
   Baud rate: 115200
   Sends ECG, BPM, HRV data to Python
   Receives "BEEP_ON"/"BEEP_OFF" commands to control alarm tones
*/

#include <math.h>

// ----------- Pin Definitions -------------
const int ecgPin = A1;
const int buzzerPin = 13;
const int loPlusPin = 10;
const int loMinusPin = 9;

// ----------- ECG & BPM Variables -------------
const int threshold = 520;    // ECG amplitude threshold
const int sampleDelay = 10;   // Sampling every 10ms (~100Hz)
unsigned long lastBeatTime = 0;
unsigned long ibi = 0;        // Inter-beat interval (ms)
int bpm = 0;

// ----------- HRV Variables -------------
const int MAX_BEATS = 10;
unsigned long ibiHistory[MAX_BEATS];
int beatCount = 0;
float SDNN = 0;

// ----------- Tone System -------------
bool alarmActive = false;
int chosenTone = 1;
bool playingTone = false;

// ---------------- Setup ----------------
void setup() {
  Serial.begin(115200);
  pinMode(loPlusPin, INPUT);
  pinMode(loMinusPin, INPUT);
  pinMode(buzzerPin, OUTPUT);
  digitalWrite(buzzerPin, LOW);
  randomSeed(analogRead(0));  // Seed random tone generator
}

// ---------------- Main Loop ----------------
void loop() {
  // ----------- RECEIVE SIGNAL FROM PYTHON -------------
  if (Serial.available() > 0) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();
    if (cmd == "BEEP_ON") {
      alarmActive = true;
      chosenTone = random(1, 11); // Pick random tone 1–10
      playTone(chosenTone);
    } else if (cmd == "BEEP_OFF") {
      alarmActive = false;
      noTone(buzzerPin);
    }
  }

  // ----------- LEAD-OFF DETECTION -------------
  if ((digitalRead(loPlusPin) == 1) || (digitalRead(loMinusPin) == 1)) {
    Serial.println("!");
    delay(sampleDelay);
    return;
  }

  // ----------- READ ECG SIGNAL -------------
  int ecgValue = analogRead(ecgPin);
  Serial.print("ECG:");
  Serial.println(ecgValue);

  // ----------- BEAT DETECTION -------------
  static bool pulseDetected = false;
  if (ecgValue > threshold && !pulseDetected) {
    pulseDetected = true;
    unsigned long now = millis();

    if (lastBeatTime > 0) {
      ibi = now - lastBeatTime;
      bpm = 60000 / ibi;

      // Store IBI for HRV computation
      if (beatCount < MAX_BEATS) {
        ibiHistory[beatCount++] = ibi;
      } else {
        for (int i = 1; i < MAX_BEATS; i++) ibiHistory[i - 1] = ibiHistory[i];
        ibiHistory[MAX_BEATS - 1] = ibi;
      }

      // Compute HRV (SDNN)
      if (beatCount >= 2) {
        float sum = 0;
        for (int i = 0; i < beatCount; i++) sum += ibiHistory[i];
        float mean = sum / beatCount;
        float variance = 0;
        for (int i = 0; i < beatCount; i++) variance += pow(ibiHistory[i] - mean, 2);
        SDNN = sqrt(variance / (beatCount - 1));
      }

      // ----------- SEND BPM + HRV TO PYTHON -------------
      Serial.print("BPM:");
      Serial.print(bpm);
      Serial.print(" HRV:");
      Serial.println(SDNN);
    }

    lastBeatTime = now;
  }

  // Reset pulse detection
  if (ecgValue < threshold - 30) {
    pulseDetected = false;
  }

  delay(sampleDelay);
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
void radarTone() {
  for (int i=0;i<6;i++){tone(buzzerPin,600+(i*150),200);delay(200);}
  delay(300);
  for (int i=0;i<4;i++){tone(buzzerPin,1200-(i*100),150);delay(150);}
  noTone(buzzerPin);
}
void beepBeepBeep() {
  for (int i=0;i<5;i++){tone(buzzerPin,1000,200);delay(250);}
  noTone(buzzerPin);
}
void morningFlower() {
  int melody[]={523,659,784,988,784,659,523};
  for(int i=0;i<7;i++){tone(buzzerPin,melody[i],250);delay(300);}
  noTone(buzzerPin);
}
void classicBell() {
  for(int i=0;i<3;i++){tone(buzzerPin,1000,100);delay(100);tone(buzzerPin,800,100);delay(200);}
  noTone(buzzerPin);
}
void digitalBuzzer() {
  tone(buzzerPin,900); delay(2000); noTone(buzzerPin);
}
void chimes() {
  int melody[]={523,659,784,1046};
  for(int i=0;i<4;i++){tone(buzzerPin,melody[i],400);delay(450);}
  noTone(buzzerPin);
}
void roosterCrowing() {
  for(int i=0;i<3;i++){tone(buzzerPin,800,200);delay(100);tone(buzzerPin,1000,300);delay(150);tone(buzzerPin,700,500);delay(300);}
  noTone(buzzerPin);
}
void reveille() {
  int melody[]={784,988,784,988,784,988,784};
  for(int i=0;i<7;i++){tone(buzzerPin,melody[i],200);delay(220);}
  noTone(buzzerPin);
}
void varyingTones() {
  for(int i=0;i<10;i++){tone(buzzerPin,500+i*100,100);delay(120);}
  noTone(buzzerPin);
}
void natureSounds() {
  for(int i=0;i<5;i++){tone(buzzerPin,1200+random(-200,200),150);delay(400);}
  noTone(buzzerPin);
}
