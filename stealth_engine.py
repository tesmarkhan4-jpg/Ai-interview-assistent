import ctypes
from ctypes import wintypes

# Windows API Constants
WDA_NONE = 0x00000000
WDA_MONITOR = 0x00000001
WDA_EXCLUDEFROMCAPTURE = 0x00000011

user32 = ctypes.WinDLL('user32', use_last_error=True)

# Function Prototypes
SetWindowDisplayAffinity = user32.SetWindowDisplayAffinity
SetWindowDisplayAffinity.argtypes = [wintypes.HWND, wintypes.DWORD]
SetWindowDisplayAffinity.restype = wintypes.BOOL

def set_stealth_mode(hwnd, enabled=True):
    """
    Enables or disables the 'Invisible to Screen Share' feature.
    When enabled, the window will appear black or empty in screen recordings and video calls.
    """
    affinity = WDA_EXCLUDEFROMCAPTURE if enabled else WDA_NONE
    result = SetWindowDisplayAffinity(hwnd, affinity)
    if not result:
        error = ctypes.get_last_error()
        print(f"[StealthEngine] Error setting display affinity: {error}")
    return result

def set_always_on_top(hwnd, enabled=True):
    """
    Ensures the HUD stays on top of all other windows.
    """
    HWND_TOPMOST = -1
    HWND_NOTOPMOST = -2
    SWP_NOMOVE = 0x0002
    SWP_NOSIZE = 0x0001
    
    flag = HWND_TOPMOST if enabled else HWND_NOTOPMOST
    user32.SetWindowPos(hwnd, flag, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE)
