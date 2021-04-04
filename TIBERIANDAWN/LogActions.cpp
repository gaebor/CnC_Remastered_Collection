#include <Windows.h>
#include <winhttp.h>

#include <stdarg.h>
#include <stdio.h>

// #include <unordered_map>

#include "LogActions.h"

#include "FUNCTION.H"
#include "EXTERNS.H"
#include "DEFINES.H"

static const unsigned int text_buffer_size = 256;

char* mysprintf(const char* format, ...)
{
	static char text_buffer[text_buffer_size];

	va_list args;
	va_start(args, format);
	int result = vsnprintf(text_buffer, text_buffer_size, format, args);
	va_end(args);
	text_buffer[text_buffer_size - 1] = '\0';
	return text_buffer;
}

static HWND hwnd;
static unsigned char* websocket_msg_buf = 0;

static HINTERNET hWebSocketHandle = NULL;
static HINTERNET hSessionHandle = NULL;
static HINTERNET hConnectionHandle = NULL;
static HINTERNET hRequestHandle = NULL;


struct MouseState
{
	MouseState() : pt({0, 0}), button(BUTTON_NONE) {}
	POINT pt;
	WhichMouseButton button;
	void Reset()
	{
		button = BUTTON_NONE;
		// don't erase position
	}
};

// static std::unordered_map<size_t, MouseState> mouse_states;
static MouseState mouse;

void LogMouse(unsigned __int64 player_id, WhichMouseButton button)
{
	// auto& mouse = mouse_states[player_id];
	
	if (button >= mouse.button)
	{// this keeps clicks over movements
		mouse.button = button;

		if (0 == GetCursorPos(&mouse.pt))
		{
			SendOnSocket("{\"GetCursorPos\":%d}", GetLastError());
		}
		else if (0 == ScreenToClient(hwnd, &mouse.pt))
		{
			SendOnSocket("{\"ScreenToClient\":%d}", GetLastError());
		}
	}
}

static void SendOnSocketRaw(PVOID message, DWORD size)
{
	DWORD dwError = WinHttpWebSocketSend(hWebSocketHandle,
		WINHTTP_WEB_SOCKET_BINARY_MESSAGE_BUFFER_TYPE,
		message,
		size);
	if (dwError != NO_ERROR)
	{
		CCDebugString(mysprintf("WinHttpWebSocketSend: %d, GetLastError: %d\n", dwError, GetLastError()));
	}
}

void SendOnSocket(const char* format, ...)
{
	static char text_buffer[text_buffer_size];
	va_list args;
	va_start(args, format);
	vsnprintf(text_buffer, text_buffer_size, format, args);
	va_end(args);
	text_buffer[text_buffer_size - 1] = '\0';
	SendOnSocketRaw((PVOID)text_buffer, strlen(text_buffer) + 1);
}


void InitWebSocket()
{
	DWORD dwError = ERROR_SUCCESS;
	BOOL fStatus = FALSE;
	BYTE rgbBuffer[1024];
	BYTE* pbCurrentBufferPointer = rgbBuffer;
	DWORD dwBufferLength = ARRAYSIZE(rgbBuffer);
	DWORD dwBytesTransferred = 0;
	DWORD dwCloseReasonLength = 0;
	USHORT usStatus = 0;

	//
	// Create session, connection and request handles.
	//

	hSessionHandle = WinHttpOpen(L"CnC WebSocket",
		WINHTTP_ACCESS_TYPE_DEFAULT_PROXY,
		NULL,
		NULL,
		0);
	if (hSessionHandle == NULL)
	{
		dwError = GetLastError();
		goto quit;
	}

	hConnectionHandle = WinHttpConnect(hSessionHandle,
		L"localhost",
		8888,
		0);
	if (hConnectionHandle == NULL)
	{
		dwError = GetLastError();
		goto quit;
	}

	hRequestHandle = WinHttpOpenRequest(hConnectionHandle,
		L"GET",
		L"",
		NULL,
		NULL,
		NULL,
		0);
	if (hRequestHandle == NULL)
	{
		dwError = GetLastError();
		goto quit;
	}

	//
	// Request protocol upgrade from http to websocket.
	//
// #pragma prefast(suppress:6387, "WINHTTP_OPTION_UPGRADE_TO_WEB_SOCKET does not take any arguments.")
	fStatus = WinHttpSetOption(hRequestHandle,
		WINHTTP_OPTION_UPGRADE_TO_WEB_SOCKET,
		NULL,
		0);
	if (!fStatus)
	{
		dwError = GetLastError();
		goto quit;
	}

	//
	// Perform websocket handshake by sending a request and receiving server's response.
	// Application may specify additional headers if needed.
	//

	fStatus = WinHttpSendRequest(hRequestHandle,
		WINHTTP_NO_ADDITIONAL_HEADERS,
		0,
		NULL,
		0,
		0,
		0);
	if (!fStatus)
	{
		dwError = GetLastError();
		goto quit;
	}

	fStatus = WinHttpReceiveResponse(hRequestHandle, 0);
	if (!fStatus)
	{
		dwError = GetLastError();
		goto quit;
	}

	//
	// Application should check what is the HTTP status code returned by the server and behave accordingly.
	// WinHttpWebSocketCompleteUpgrade will fail if the HTTP status code is different than 101.
	//

	hWebSocketHandle = WinHttpWebSocketCompleteUpgrade(hRequestHandle, NULL);
	if (hWebSocketHandle == NULL)
	{
		dwError = GetLastError();
		goto quit;
	}

	//
	// The request handle is not needed anymore. From now on we will use the websocket handle.
	//

	WinHttpCloseHandle(hRequestHandle);
	hRequestHandle = NULL;

	CCDebugString("Succesfully opened websocket\n");
	return;

quit:
	CCDebugString(mysprintf("Last Error: %d\n", dwError));

	if (hRequestHandle != NULL)
	{
		WinHttpCloseHandle(hRequestHandle);
		hRequestHandle = NULL;
	}

	if (hWebSocketHandle != NULL)
	{
		WinHttpCloseHandle(hWebSocketHandle);
		hWebSocketHandle = NULL;
	}

	if (hConnectionHandle != NULL)
	{
		WinHttpCloseHandle(hConnectionHandle);
		hConnectionHandle = NULL;
	}

	if (hSessionHandle != NULL)
	{
		WinHttpCloseHandle(hSessionHandle);
		hSessionHandle = NULL;
	}
}

int GetDesktopResolution(int* horizontal, int* vertical)
{

	HDC hScreenDC = GetDC(GetDesktopWindow());
	int width = GetDeviceCaps(hScreenDC, HORZRES);
	int height = GetDeviceCaps(hScreenDC, VERTRES);
	ReleaseDC(GetDesktopWindow(), hScreenDC);

	RECT desktop;
	const HWND hDesktop = GetDesktopWindow();
	GetWindowRect(hDesktop, &desktop);

	//if (width > 2000)
	//{
	//	const POINT ptZero = { 0, 0 };
	//	HMONITOR mon = MonitorFromPoint(ptZero, MONITOR_DEFAULTTOPRIMARY);

	//	DEVICE_SCALE_FACTOR f;// vers < win 8 = GetScaleFactorForDevice(DEVICE_PRIMARY);
	//	GetScaleFactorForMonitor(mon, &f);
	//	if (f > 110)
	//	{
	//		*horizontal = width * ((f + 10) / 100.0);
	//		*vertical = height * ((f + 10) / 100.0);
	//	}
	//	else
	//	{
	//		*horizontal = width;
	//		*vertical = height;
	//	}
	//}
	//else
	{
		*horizontal = desktop.right;
		*vertical = desktop.bottom;
	}
	return ((desktop.right * 32 + 31) / 32) * 4 * desktop.bottom;
}

static int GetWindowImageSize(HWND hWnd)
{
	RECT rcClient;
	if (GetClientRect(hWnd, &rcClient) == 0)
		return 0;

	const int height = rcClient.bottom - rcClient.top;
	const int width = rcClient.right - rcClient.left;

	return ((width * 32 + 31) / 32) * 4 * height;
}

void InitializeLogger()
{
	int w, h;
	hwnd = FindWindow(0, TEXT("C&C Tiberian Dawn Remastered"));
	int needed_size = GetDesktopResolution(&w, &h);
	if (needed_size <= 0)
	{
		CCDebugString("Unable to obtain desktop size!\n");
		return;
	}
	
	needed_size += 256 + sizeof(BITMAPFILEHEADER) + sizeof(BITMAPINFOHEADER);
	websocket_msg_buf = new unsigned char[needed_size];
	if (!websocket_msg_buf) {
		CCDebugString(mysprintf("Unable to allocate %u for image buffer!\n", needed_size));
		return;
	}
	InitWebSocket();
	SendOnSocket("%s", "\"START\"");
}

void DestroyLogger()
{
	SendOnSocket("%s", "\"END\"");

	if (websocket_msg_buf)
		delete[] websocket_msg_buf;

	//
	// Gracefully close the connection.
	//

	WinHttpWebSocketClose(hWebSocketHandle, WINHTTP_WEB_SOCKET_SUCCESS_CLOSE_STATUS, NULL, 0);

	////
	//// Check close status returned by the server.
	////

	//dwError = WinHttpWebSocketQueryCloseStatus(hWebSocketHandle,
	//	&usStatus,
	//	rgbCloseReasonBuffer,
	//	ARRAYSIZE(rgbCloseReasonBuffer),
	//	&dwCloseReasonLength);
	//if (dwError != ERROR_SUCCESS)
	//{
	//	goto quit;
	//}

	//wprintf(L"The server closed the connection with status code: '%d' and reason: '%.*S'\n",
	//	(int)usStatus,
	//	dwCloseReasonLength,
	//	rgbCloseReasonBuffer);

	if (hRequestHandle != NULL)
	{
		WinHttpCloseHandle(hRequestHandle);
		hRequestHandle = NULL;
	}

	if (hWebSocketHandle != NULL)
	{
		WinHttpCloseHandle(hWebSocketHandle);
		hWebSocketHandle = NULL;
	}

	if (hConnectionHandle != NULL)
	{
		WinHttpCloseHandle(hConnectionHandle);
		hConnectionHandle = NULL;
	}

	if (hSessionHandle != NULL)
	{
		WinHttpCloseHandle(hSessionHandle);
		hSessionHandle = NULL;
	}
}

void SendWhatHappened(unsigned __int64 player_id, long Frame)
{
	if (websocket_msg_buf == 0)
		return;


	HDC hdcScreen;
	HDC hdcWindow;
	HDC hdcMemDC = NULL;
	HBITMAP hbmScreen = NULL;
	BITMAP bmpScreen;
	DWORD dwBytesWritten = 0;
	DWORD dwSizeofDIB = 0;
	HANDLE hFile = NULL;
	DWORD dwBmpSize = 0;

	// Retrieve the handle to a display device context for the client 
	// area of the window. 
	hdcScreen = GetDC(NULL);
	hdcWindow = GetDC(hwnd);

	// Create a compatible DC, which is used in a BitBlt from the window DC.
	hdcMemDC = CreateCompatibleDC(hdcWindow);

	if (!hdcMemDC)
	{
		CCDebugString("CreateCompatibleDC has failed!\n");
		goto done;
	}

	// Get the client area for size calculation.
	RECT rcClient;
	GetClientRect(hwnd, &rcClient);

	/*static char buffer[256];
	snprintf(buffer, 256, "b%d l%d t%d r%d\n", rcClient.bottom, rcClient.left, rcClient.top, rcClient.right);
	CCDebugString(buffer);
	*/
	//// The source DC is the entire screen, and the destination DC is the current window (HWND).
	//if (!StretchBlt(hdcWindow,
	//	0, 0,
	//	rcClient.right, rcClient.bottom,
	//	hdcScreen,
	//	0, 0,
	//	GetSystemMetrics(SM_CXSCREEN),
	//	GetSystemMetrics(SM_CYSCREEN),
	//	SRCCOPY))
	//{
	//	MessageBox(hWnd, L"StretchBlt has failed", L"Failed", MB_OK);
	//	goto done;
	//}

	// Create a compatible bitmap from the Window DC.
	hbmScreen = CreateCompatibleBitmap(hdcWindow, rcClient.right - rcClient.left, rcClient.bottom - rcClient.top);

	if (!hbmScreen)
	{
		CCDebugString("CreateCompatibleBitmap Failed!\n");
		goto done;
	}

	// Select the compatible bitmap into the compatible memory DC.
	SelectObject(hdcMemDC, hbmScreen);

	// Bit block transfer into our compatible memory DC.
	if (!BitBlt(hdcMemDC,
		0, 0,
		rcClient.right - rcClient.left, rcClient.bottom - rcClient.top,
		hdcWindow,
		0, 0,
		SRCCOPY))
	{
		CCDebugString("BitBlt has Failed!\n");
		goto done;
	}

	// Get the BITMAP from the HBITMAP.
	GetObject(hbmScreen, sizeof(BITMAP), &bmpScreen);

	BITMAPFILEHEADER& bmfHeader = *(BITMAPFILEHEADER*)(websocket_msg_buf + 256);
	BITMAPINFOHEADER& bi = *(BITMAPINFOHEADER*)(websocket_msg_buf + 256 + sizeof(BITMAPFILEHEADER));

	bi.biSize = sizeof(BITMAPINFOHEADER);
	bi.biWidth = bmpScreen.bmWidth;
	bi.biHeight = bmpScreen.bmHeight;
	bi.biPlanes = 1;
	bi.biBitCount = 32;
	bi.biCompression = BI_RGB;
	bi.biSizeImage = 0;
	bi.biXPelsPerMeter = 0;
	bi.biYPelsPerMeter = 0;
	bi.biClrUsed = 0;
	bi.biClrImportant = 0;

	dwBmpSize = ((bmpScreen.bmWidth * bi.biBitCount + 31) / 32) * 4 * bmpScreen.bmHeight;

	// Gets the "bits" from the bitmap, and copies them into a buffer 
	// that's pointed to by lpbitmap.
	if (0 == GetDIBits(hdcWindow, hbmScreen, 0, bmpScreen.bmHeight, 
		websocket_msg_buf + 256 + sizeof(BITMAPFILEHEADER) + sizeof(BITMAPINFOHEADER), 
		(BITMAPINFO*)&bi, DIB_RGB_COLORS))
	{
		CCDebugString("GetDIBits failed!\n");
		goto done;
	}
	// snprintf((char*)websocket_msg_buf, 256, "capture%010d.bmp", Frame);
	//// A file is created, this is where we will save the screen capture.
	//hFile = CreateFileA((LPCSTR)websocket_msg_buf,
	//	GENERIC_WRITE,
	//	0,
	//	NULL,
	//	CREATE_ALWAYS,
	//	FILE_ATTRIBUTE_NORMAL, NULL);

	// Add the size of the headers to the size of the bitmap to get the total file size.
	dwSizeofDIB = dwBmpSize + sizeof(BITMAPFILEHEADER) + sizeof(BITMAPINFOHEADER);

	// Offset to where the actual bitmap bits start.
	bmfHeader.bfOffBits = (DWORD)sizeof(BITMAPFILEHEADER) + (DWORD)sizeof(BITMAPINFOHEADER);

	//// Size of the file.
	bmfHeader.bfSize = dwSizeofDIB;

	// bfType must always be BM for Bitmaps.
	bmfHeader.bfType = 0x4D42; // BM.

	//WriteFile(hFile, (LPSTR)&bmfHeader, sizeof(BITMAPFILEHEADER), &dwBytesWritten, NULL);
	//WriteFile(hFile, (LPSTR)&bi, sizeof(BITMAPINFOHEADER), &dwBytesWritten, NULL);
	//WriteFile(hFile, (LPSTR)websocket_msg_buf + 256, dwBmpSize, &dwBytesWritten, NULL);

	//// Close the handle for the file that was created.
	//CloseHandle(hFile);

	// const auto& mouse = mouse_states[player_id];
	snprintf((char*)websocket_msg_buf, 256,
		"{\"player\":%llu,\"frame\":%ld, \"mouse\":{\"x\":%d,\"y\":%d, \"button\":%d}}",
		player_id, Frame, mouse.pt.x, mouse.pt.y, (int)mouse.button);
	websocket_msg_buf[255] = '\0';

	SendOnSocketRaw(websocket_msg_buf, dwSizeofDIB + 256);
	mouse.Reset();

	// Clean up.
done:
	DeleteObject(hbmScreen);
	DeleteObject(hdcMemDC);
	ReleaseDC(NULL, hdcScreen);
	ReleaseDC(hwnd, hdcWindow);
}
