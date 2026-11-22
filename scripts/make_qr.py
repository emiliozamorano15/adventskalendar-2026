"""Claim QR codes into qr_out/ (git-ignored: anyone holding them can claim the coins).
Writes one PNG per day and qr_out/qr_codes.pdf: A4 pages, six codes each, sorted by day, labelled with the day
and the hiding place. Usage: python scripts/make_qr.py"""
import io, pathlib, sys, segno
from PIL import Image, ImageDraw, ImageFont
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from scripts._client import client

sb, cfg = client()
base = cfg["APP_URL"].rstrip("/")
if not base.startswith("https://") or "CHANGE-ME" in base:
    sys.exit("Set APP_URL in .streamlit/secrets.toml to the deployed https://... address first: it is printed into every code.")

out = pathlib.Path("qr_out"); out.mkdir(exist_ok=True)
days = sb.table("days").select("date,secret,answer").order("date").execute().data

W, H, COLS, ROWS = 2480, 3508, 2, 3            # A4 at 300 dpi
cell_w, cell_h = W // COLS, H // ROWS
def font(size: int):
    """A TrueType font with accents (Día, lámpara); Pillow's built-in one has none."""
    for name in ("DejaVuSans.ttf", "/System/Library/Fonts/Supplemental/Arial.ttf", "C:/Windows/Fonts/arial.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    return ImageFont.load_default(size=size)

big, small = font(110), font(50)
pages = []
for i, d in enumerate(days):
    url = f"{base}/?claim={d['secret']}"
    qr = segno.make(url, error="m")
    qr.save(out / f"dia_{d['date'][-2:]}.png", scale=10, border=2)
    if i % (COLS * ROWS) == 0:
        pages.append(Image.new("RGB", (W, H), "white"))
    page, slot = pages[-1], i % (COLS * ROWS)
    x0, y0 = (slot % COLS) * cell_w, (slot // COLS) * cell_h
    buf = io.BytesIO()
    qr.save(buf, kind="png", scale=24, border=2)
    img = Image.open(buf).convert("RGB")
    page.paste(img, (x0 + (cell_w - img.width) // 2, y0 + 170))
    draw = ImageDraw.Draw(page)
    draw.text((x0 + cell_w // 2, y0 + 90), f"Día {int(d['date'][-2:])}", font=big, fill="black", anchor="mm")
    draw.text((x0 + cell_w // 2, y0 + 190 + img.height), f"Esconder en: {d['answer'] or '-'}", font=small, fill="gray", anchor="mm")
    draw.rectangle([x0 + 20, y0 + 20, x0 + cell_w - 20, y0 + cell_h - 20], outline="lightgray", width=4)   # cut line
    print(d["date"], url)
pages[0].save(out / "qr_codes.pdf", save_all=True, append_images=pages[1:], resolution=300)
print(f"{len(days)} codes, {len(pages)} pages: {out / 'qr_codes.pdf'}")
