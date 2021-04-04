#ifndef LOG_ACTIONS_H
#define LOG_ACTIONS_H

void InitializeLogger();
void DestroyLogger();
void SendWhatHappened(unsigned __int64 player_id, long Frame);

enum WhichMouseButton
{
	BUTTON_NONE,
	BUTTON_LEFT,
	BUTTON_RIGHT,
};

void LogMouse(unsigned __int64 player, WhichMouseButton button = BUTTON_NONE);

void SendOnSocket(const char* format, ...);

#endif
