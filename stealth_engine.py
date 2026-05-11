import ctypes
from ctypes import wintypes

# Windows API Constants
WDA_NONE = 0x00000000
WDA_MONITOR = 0x00000001
WDA_EXCLUDEFROMCAPTURE = 0x00000002

user32 = ctypes.WinDLL('user32', use_last_error=True)

# Function Prototypes
SetWindowDisplayAffinity = user32.SetWindowDisplayAffinity
SetWindowDisplayAffinity.argtypes = [wintypes.HWND, wintypes.DWORD]
SetWindowDisplayAffinity.restype = wintypes.BOOL

user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
user32.GetAncestor.restype = wintypes.HWND

def set_stealth_mode(hwnd, enabled=True):
    """
    Enables or disables the 'Invisible to Screen Share' feature.
    Aggressively targets the window hierarchy to ensure the OS locks the shield.
    """
    try:
        # Flags for root finding
        GA_ROOT = 2
        GA_ROOTOWNER = 3
        
        # 1. Target the window itself
        affinity = WDA_EXCLUDEFROMCAPTURE if enabled else WDA_NONE
        SetWindowDisplayAffinity(hwnd, affinity)
        
        # 2. Target the Root Ancestor (The physical window frame)
        root_hwnd = user32.GetAncestor(hwnd, GA_ROOT)
        if root_hwnd and root_hwnd != hwnd:
            SetWindowDisplayAffinity(root_hwnd, affinity)
            
        # 3. Target the Root Owner (For nested shells)
        owner_hwnd = user32.GetAncestor(hwnd, GA_ROOTOWNER)
        if owner_hwnd and owner_hwnd != hwnd and owner_hwnd != root_hwnd:
            SetWindowDisplayAffinity(owner_hwnd, affinity)
            
        print(f"[StealthEngine] Shield Pulse Sent to Hierarchy (Enabled: {enabled})")
        return True
    except Exception as e:
        print(f"[StealthEngine] Aggressive Shield Exception: {e}")
        return False

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
