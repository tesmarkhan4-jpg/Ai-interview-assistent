from PIL import Image

# Open the previously generated PNG image
img_path = r"C:\Users\Faheem\.gemini\antigravity\brain\0f9ee9f1-d613-45cb-8400-c716b32cc2e0\zenith_pro_3d_icon_1778734563355.png"
output_path = r"c:\Users\Faheem\Downloads\Ai APP\app_icon.ico"

try:
    img = Image.open(img_path)
    # Convert image to RGBA if it isn't
    if img.mode != 'RGBA':
        img = img.convert('RGBA')
        
    # Generate multiple sizes for the ICO file for best quality
    icon_sizes = [(256, 256), (128, 128), (64, 64), (32, 32), (16, 16)]
    img.save(output_path, format='ICO', sizes=icon_sizes)
    print(f"Successfully generated ICO file at: {output_path}")
except Exception as e:
    print(f"Error converting image: {e}")
