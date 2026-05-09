import sys
from PIL import Image

def make_transparent_png(img_path, out_path):
    try:
        img = Image.open(img_path)
        img = img.convert("RGBA")
        datas = img.getdata()

        newData = []
        bg_color = datas[0]
        tolerance = 30
        
        for item in datas:
            if (abs(item[0] - bg_color[0]) < tolerance and
                abs(item[1] - bg_color[1]) < tolerance and
                abs(item[2] - bg_color[2]) < tolerance):
                newData.append((255, 255, 255, 0))
            else:
                newData.append(item)

        img.putdata(newData)
        
        # Resize to a reasonable size for UI (e.g., 200x200)
        img = img.resize((200, 200), Image.Resampling.LANCZOS)
        img.save(out_path, format='PNG')
        print(f"Successfully created transparent PNG: {out_path}")
        
    except Exception as e:
        print(f"Error processing image: {e}")
        sys.exit(1)

if __name__ == "__main__":
    in_img = r"C:\Users\Faheem\.gemini\antigravity\brain\914ab17c-5470-42d6-9941-8946650f2cdb\stealth_assist_3d_icon_1778297038528.png"
    out_png = r"c:\Users\Faheem\Downloads\Ai APP\logo.png"
    make_transparent_png(in_img, out_png)
