int ledPin = 13;

void setup()
{
    pinMode(ledPin, OUTPUT);
    Serial.begin(9600);
    Serial1.begin(9600);
    Serial1.setTimeout(3000);

    delay(1000);
    Serial.println("finished setup");
}

void loop()
{
    if (Serial1.available()) {
      digitalWrite(ledPin, HIGH);
  
      while (Serial1.available()) {
          int b = Serial1.read();
          Serial.write(b);
      }
  
      digitalWrite(ledPin, LOW);
    }
    
    if (Serial.available()) {
       while (Serial.available()) {
         int b = Serial.read();
         Serial1.write(b);
       }     
    }
}
