#ifndef LOG_ACTIONS_H
#define LOG_ACTIONS_H

void InitializeLogger();
void DestroyLogger();
void LoggerLog(unsigned __int64 player_id, long Frame);

void SendOnSocket(const char* format, ...);

#endif
