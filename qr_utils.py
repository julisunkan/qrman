import qrcode
from PIL import Image, ImageDraw
import segno
import os
import geoip2.database

def get_country(ip):
    try:
        # Fallback to 'Unknown' as the .mmdb database file is not provided in the environment
        # and requires manual download from MaxMind.
        return "Unknown"
    except Exception:
        return "Unknown"

def generate_all_formats(code, url, fg, bg, logo_path=None):
    qr_dir = os.path.join('static', 'qr_codes')
    
    # PNG
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_H)
    qr.add_data(url)
    qr.make(fit=True)
    img_png = qr.make_image(fill_color=fg, back_color=bg).convert('RGB')
    
    if logo_path:
        logo = Image.open(logo_path).convert("RGBA")
        width, height = img_png.size
        logo_size = width // 4
        logo = logo.resize((logo_size, logo_size), Image.Resampling.LANCZOS)
        pos = ((width - logo_size) // 2, (height - logo_size) // 2)
        img_png.paste(logo, pos, logo)
    
    img_png.save(os.path.join(qr_dir, f"{code}.png"))

    # SVG (segno)
    qr_svg = segno.make(url, error='h')
    qr_svg.save(os.path.join(qr_dir, f"{code}.svg"), scale=10, dark=fg, light=bg)

    # GIF (Animated)
    frames = []
    width, height = img_png.size
    logo_size = width // 4
    pos = ((width - logo_size) // 2, (height - logo_size) // 2)
    
    for i in range(10):
        # Subtle color shift for animation
        frame = qr.make_image(fill_color=fg, back_color=bg).convert('RGB')
        if logo_path:
            logo = Image.open(logo_path).convert("RGBA")
            # Subtly rotate logo
            logo = logo.rotate(i * 36).resize((logo_size, logo_size), Image.Resampling.LANCZOS)
            frame.paste(logo, pos, logo)
        frames.append(frame)
    
    frames[0].save(
        os.path.join(qr_dir, f"{code}.gif"),
        save_all=True,
        append_images=frames[1:],
        duration=100,
        loop=0
    )
