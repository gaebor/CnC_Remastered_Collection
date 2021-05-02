from sys import stderr
from ctypes import *


class RECT(Structure):
    _fields_ = [
        ("left", c_long),
        ("top", c_long),
        ("right", c_long),
        ("bottom", c_long),
    ]


class MOUSEINPUT(Structure):
    _fields_ = [
        ('dx', c_long),
        ('dy', c_long),
        ('mouseData', c_int),
        ('dwFlags', c_int),
        ('time', c_int),
        ('dwExtraInfo', c_void_p),
    ]


class INPUT(Structure):
    _fields_ = [
        ("type", c_int),
        ("mi", MOUSEINPUT),
    ]


user32dll = cdll.LoadLibrary('user32.dll')
kernel32dll = cdll.LoadLibrary('kernel32.dll')

MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010


def MoveMouse(x, y, click=0):
    rect = RECT()
    hwnd = user32dll.FindWindowW(0, "C&C Tiberian Dawn Remastered")
    user32dll.GetClientRect(hwnd, pointer(rect))
    mouse_input = INPUT()
    mouse_input.type = 0  # INPUT_MOUSE

    if click == 1:
        mouse_input.mi.dwFlags = MOUSEEVENTF_MOVE | MOUSEEVENTF_LEFTDOWN | MOUSEEVENTF_LEFTUP
    elif click == 2:
        mouse_input.mi.dwFlags = MOUSEEVENTF_MOVE | MOUSEEVENTF_RIGHTDOWN | MOUSEEVENTF_RIGHTUP
    else:
        mouse_input.mi.dwFlags = MOUSEEVENTF_MOVE

    mouse_input.mi.dx = int(x * (rect.right - rect.left) / 720)
    mouse_input.mi.dy = int(y * (rect.bottom - rect.top) / 405)

    mouse_input.mi.time = 0
    mouse_input.mi.dwExtraInfo = 0

    if 0 == user32dll.SendInput(1, pointer(mouse_input), sizeof(INPUT)):
        print(f"MoveMouse returned 0, GetLastError: {kernel32dll.GetLastError()}", file=stderr)
