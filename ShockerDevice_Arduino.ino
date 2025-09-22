/*  
title: "Shock Device Controller for Electric Shock Avoidance Assay"
author: "Babur Erdem"
date: "2025-09-22"
update date: "2025-09-22"
*/

#include <Arduino.h>
#include <string.h>

const uint8_t PIN_UP = 2;
const uint8_t PIN_DN = 4;

char line[48]; uint8_t llen = 0;

inline void apply(char s){
  digitalWrite(PIN_UP, (s=='U'||s=='A') ? HIGH : LOW);
  digitalWrite(PIN_DN, (s=='D'||s=='A') ? HIGH : LOW);
}

void setup(){
  pinMode(PIN_UP, OUTPUT);
  pinMode(PIN_DN, OUTPUT);
  apply('N');
  Serial.begin(115200);
  Serial.println(F("OK"));
}

void handle_line(){
  if (strncmp(line, "MODE=", 5) == 0) {
    char s = line[5];
    if (s=='U'||s=='D'||s=='A'||s=='N') { apply(s); Serial.println(F("OK")); return; }
  }
  if (strncmp(line, "PING", 4) == 0) { Serial.println(F("PONG")); return; }
  if (line[0]=='X') { apply('N'); Serial.println(F("OK")); return; }
  Serial.println(F("ERR"));
}

void loop(){
  while (Serial.available()){
    char c = Serial.read();
    if (c=='\n'){
      if (llen >= sizeof(line)) llen = sizeof(line)-1;
      line[llen] = '\0'; llen = 0;
      handle_line();
    } else if (c!='\r' && llen < sizeof(line)-1){
      line[llen++] = c;
    }
  }
}
