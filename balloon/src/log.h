#ifndef PEPPER2_LOG_H
#define PEPPER2_LOG_H

#define LOG_LEVEL_ERROR 0
#define LOG_LEVEL_WARN  1
#define LOG_LEVEL_INFO  2
#define LOG_LEVEL_DEBUG 3
#define LOG_LEVEL_TRACE 4

#ifndef MAX_LOG_LEVEL
#define MAX_LOG_LEVEL LOG_LEVEL_DEBUG
#endif

#ifndef LOG_TAG
#define LOG_TAG  "PEPPER-2"
#endif

#define _LOG_TAG "[" LOG_TAG "] "

#define LOG_ERROR(fmt, ...) log(LOG_LEVEL_ERROR, _LOG_TAG fmt, ##__VA_ARGS__)

#if MAX_LOG_LEVEL >= LOG_LEVEL_WARN
#define LOG_WARN(fmt, ...) log(LOG_LEVEL_WARN, _LOG_TAG fmt, ##__VA_ARGS__)
#else
#define LOG_WARN(fmt, ...)
#endif

#if MAX_LOG_LEVEL >= LOG_LEVEL_INFO
#define LOG_INFO(fmt, ...) log(LOG_LEVEL_INFO, _LOG_TAG fmt, ##__VA_ARGS__)
#else
#define LOG_INFO(fmt, ...)
#endif

#if MAX_LOG_LEVEL >= LOG_LEVEL_DEBUG
#define LOG_DEBUG(fmt, ...) log(LOG_LEVEL_DEBUG, _LOG_TAG fmt, ##__VA_ARGS__)
#else
#define LOG_DEBUG(fmt, ...)
#endif

#if MAX_LOG_LEVEL >= LOG_LEVEL_DEBUG
#define LOG_TRACE(fmt, ...) log(LOG_LEVEL_TRACE, _LOG_TAG fmt, ##__VA_ARGS__)
#else
#define LOG_TRACE(fmt, ...)
#endif

namespace pepper2 {

class OBC;

#define LOG_BUFFER_SIZE 255

class Logger {
public:
    Logger(OBC *obc);
    void begin();
    void vlog(uint8_t level, const char *fmt, va_list ap);

    uint8_t getConsoleLevel() { return mConsoleLevel; }
    void setConsoleLevel(uint8_t level) { mConsoleLevel = level; }
    uint8_t getFileLevel() { return mFileLevel; }
    void setFileLevel(uint8_t level) { mFileLevel = level; }

private:
    OBC *mObc;
    uint8_t mConsoleLevel, mFileLevel;
    char mTimestamp[LOG_BUFFER_SIZE];
    char mBuffer[LOG_BUFFER_SIZE];
    bool mFileEnabled;
};

void logInit(OBC *obc);
void log(uint8_t level, const char *fmt, ...);
void setFileLogLevel(int level);
void setConsoleLogLevel(int level);

}

#endif
