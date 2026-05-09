import sys
from PIL import Image

def make_transparent(img_path, out_path):
    try:
        img = Image.open(img_path)
        img = img.convert("RGBA")
        datas = img.getdata()

        newData = []
        # Assume the top-left pixel is the background color
        bg_color = datas[0]
        # Allow some tolerance for "pure white" compression artifacts
        tolerance = 30
        
        for item in datas:
            # Check if pixel is close to background color
            if (abs(item[0] - bg_color[0]) < tolerance and
                abs(item[1] - bg_color[1]) < tolerance and
                abs(item[2] - bg_color[2]) < tolerance):
                # Replace with transparent pixel
                newData.append((255, 255, 255, 0))
            else:
                newData.append(item)

        img.putdata(newData)
        
        # Save as ICO with multiple sizes
        icon_sizes = [(256, 256), (128, 128), (64, 64), (32, 32), (16, 16)]
        img.save(out_path, format='ICO', sizes=icon_sizes)
        print(f"Successfully created transparent icon: {out_path}")
        
    except Exception as e:
        print(f"Error processing image: {e}")
        sys.exit(1)

if __name__ == "__main__":
    in_img = r"C:\Users\Faheem\.gemini\antigravity\brain\914ab17c-5470-42d6-9941-8946650f2cdb\stealth_assist_3d_icon_1778297038528.png"
    out_ico = r"c:\Users\Faheem\Downloads\Ai APP\app_icon.ico"
    make_transparent(in_img, out_ico)
