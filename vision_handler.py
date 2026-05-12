import mss
import mss.tools
from PIL import Image
import os
import time

class VisionHandler:
    def __init__(self):
        self.sct = mss.mss()
        # Use an absolute temp path next to the executable or in a reliable location
        # Use APPDATA for user-writable temporary files
        self.temp_dir = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')), "StealthHUD", "temp_stealth")
        
        if not os.path.exists(self.temp_dir):
            os.makedirs(self.temp_dir, exist_ok=True)

    def capture_fullscreen(self):
        """Captures the entire screen and saves it as a temp file."""
        output = os.path.join(self.temp_dir, f"screen_{int(time.time())}.jpg")
        
        # Capture the first monitor
        monitor = self.sct.monitors[1]
        sct_img = self.sct.grab(monitor)
        
        # Convert to RGB and save as JPG (smaller size for API)
        img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
        
        # Optimize size for speed: Downscale large screenshots while maintaining aspect ratio
        max_size = (1600, 900)
        img.thumbnail(max_size, Image.Resampling.LANCZOS)
        
        # Compress slightly to make API upload much faster
        img.save(output, "JPEG", quality=70, optimize=True)
        
        return output

    def cleanup(self):
        """Removes temporary screenshots."""
        for f in os.listdir(self.temp_dir):
            try:
                os.remove(os.path.join(self.temp_dir, f))
            except:
                pass

# Global instance
vision_handler = VisionHandler()
