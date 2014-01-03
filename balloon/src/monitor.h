#ifndef PEPPER2_MONITOR_H
#define PEPPER2_MONITOR_H

namespace pepper2 {

class OBC;
class Monitor {
public:
    Monitor(OBC *obc);
    void begin();
    void draw();

private:
    void println(char *message);

    OBC *mObc;
    Adafruit_SSD1306 mDisplay;
};

}

#endif
