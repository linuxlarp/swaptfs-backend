import io
import os
import aiofiles
import re
import config

from core import crud
from core.models import Airport
from core.flights.airport_data import find_airport

from datetime import datetime
from PIL import Image, ImageDraw, ImageFont


logger = config.LOGS

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FONT_DIR = os.path.join(ROOT_DIR, "fonts")
CACHE_DIR = os.path.join(ROOT_DIR, "images", "cache", "printed")

def _font_path(name):
    return os.path.join(FONT_DIR, name)

def _load_font(path, size):
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()

OCR_B = _load_font(_font_path('OCR-B.otf'), 16)
OCR_B_14 = _load_font(_font_path('OCR-B.otf'), 14)
OCR_B_12 = _load_font(_font_path('OCR-B.otf'), 12)
OCR_B_20 = _load_font(_font_path('OCR-B.otf'), 20)
SWA_REG_28 = _load_font(_font_path('SouthwestSans-Regular.ttf'), 28)
SWA_REG_22 = _load_font(_font_path('SouthwestSans-Regular.ttf'), 22)
SWA_REG_20 = _load_font(_font_path('SouthwestSans-Regular.ttf'), 20)
SWA_REG_16 = _load_font(_font_path('SouthwestSans-Regular.ttf'), 16)
SWA_BOLD_100 = _load_font(_font_path('SouthwestSans-Bold.ttf'), 100)
SWA_BOLD_38 = _load_font(_font_path('SouthwestSans-Bold.ttf'), 38)
SWA_BOLD_24 = _load_font(_font_path('SouthwestSans-Bold.ttf'), 24)

def _parse_iso(dt):
    if not dt:
        return None
    if isinstance(dt, datetime):
        return dt
    s = str(dt)
    # handle trailing Z
    if s.endswith('Z'):
        s = s[:-1] + '+00:00'
    try:
        return datetime.fromisoformat(s)
    except Exception:
        try:
            return datetime.strptime(s, '%Y-%m-%dT%H:%M:%S')
        except Exception:
            return None

def _format_date(dt):
    if not dt:
        return ''
    return dt.strftime('%b %d')  # e.g. "Nov 01"

def _format_time(dt):
    if not dt:
        return ''
    s = dt.strftime('%I:%M %p')  # e.g. "08:30 AM"
    return s.lstrip('0')  # "8:30 AM"

def draw_barcode(draw, x, y, width, height, confirmation):
    def hash_code(s):
        h = 0
        for ch in s:
            h = (h << 5) - h + ord(ch)
            h &= 0xFFFFFFFF
        return abs(h)

    seed = hash_code(str(confirmation))

    def random_bit():
        nonlocal seed
        seed = (seed * 1664525 + 1013904223) % 4294967296
        return seed % 2

    # draw vertical bars: step 4, bar width 3
    for px in range(0, width, 4):
        if random_bit():
            draw.rectangle([x + px, y, x + px + 3, y + height], fill='black')

def generate_boarding_pass_image(confirmation_number: str, cache_only = False) -> bytes:
    """
    boarding_pass: dict with keys:
      passenger, confirmationNumber, flightId, gate, departure, from, to,
      aircraft, checkedInAt, boardingPosition. Passed via Booking model.
    Returns PNG bytes.
    """
    width, height = 1000, 400
    image = Image.new('RGB', (width, height), 'white')
    draw = ImageDraw.Draw(image)

    booking = crud.Bookings.get_by_confirmation(confirmation_number)
    if not booking:
        raise logger.error(f"No booking found for confirmation number {confirmation_number}")

    flight = crud.Flights.get_by_id(booking.flightId)
    if not flight:
        raise logger.error(f"No flight found for flight ID {booking.flightId}")

    boarding_pass = booking
    
    passenger = str(boarding_pass.username).strip()

    confirmation = str(boarding_pass.confirmationNumber or f"#{confirmation_number}").strip()
    flight_id = str(boarding_pass.flightId)
    gate = flight.deptGate or 'TBD'
    dep_dt = _parse_iso(flight.departure)
    checked_in_dt = _parse_iso(boarding_pass.checkedInAt)
    frm = flight.from_
    to = flight.to
    aircraft = flight.aircraft or "Unknown"
    boarding_position = boarding_pass.boardingPosition or "N/A"

    from_airport: Airport = find_airport(frm)
    to_airport: Airport = find_airport(to)

    cache_path = os.path.join(CACHE_DIR, flight.id)
    img_cache_path = os.path.join(CACHE_DIR, flight_id, f"{confirmation_number}.png")

    if os.path.exists(img_cache_path):
        try:
            os.makedirs(cache_path, exist_ok=True)

            with open(img_cache_path, 'rb') as f:
                data_bytes = f.read()

            buf = io.BytesIO(data_bytes)

            logger.info(f"Found cached boarding pass image for confirmation code {confirmation_number}")

            if cache_only:
                return data_bytes
                
            return buf.getvalue()
        except Exception as e:
            if cache_only:
                logger.error("Error accessing cached boarding pass image", e)
                return None
                
        
    logger.info(f"Generating boarding pass for {passenger} with confirmation code {confirmation}")

    # border
    draw.rectangle([0, 0, width - 1, height - 1], outline='black', width=2)

    # stub line
    stub_x = int(width * 0.75)
    draw.line([(stub_x, 0), (stub_x, height)], fill='black', width=2)

    left_pad = 40
    y = 60

    # Header
    draw.text((left_pad, y), 'SOUTHWEST AIRLINES', font=SWA_BOLD_38, fill='black')
    draw.text((left_pad, y + 40), 'Boarding Pass', font=OCR_B_20, fill='black')

    y += 70
    draw.text((left_pad, y), passenger, font=SWA_BOLD_24, fill='black')

    y += 50
    draw.text((left_pad, y), f'Flight {flight_id}', font=SWA_BOLD_24, fill='black')
    draw.text((left_pad + 210, y), f'Gate {gate} (Subject to Change)', font=OCR_B_14, fill='black')

    y += 40
    draw.text((left_pad, y), _format_date(dep_dt), font=OCR_B_14, fill='black')
    draw.text((left_pad + 110, y), f'Confirmation Number: #{confirmation}', font=OCR_B_14, fill='black')

    y += 35
    from_text = f"{from_airport.city}, {from_airport.state}"
    to_text = f"{to_airport.city}, {to_airport.state}"
    draw.text((left_pad, y), f"{from_text} -> {to_text}", font=OCR_B_14, fill='black')

    y += 30
    draw.text((left_pad, y), f'Aircraft: {aircraft}', font=OCR_B_14, fill='black')
    y += 30
    draw.text((left_pad, y), f'Boarding Time: {_format_time(dep_dt)}', font=OCR_B_14, fill='black')
    y += 25
    draw.text((left_pad, y), f'Checked In: {_format_date(checked_in_dt)}, {_format_time(checked_in_dt)}', font=OCR_B_14, fill='black')

    # Stub (right side)
    stub_pad = stub_x + 20
    draw.text((stub_pad, 40), 'Southwest Airlines', font=SWA_REG_22, fill='black')
    draw.text((stub_pad, 60), 'Open Seating', font=OCR_B_12, fill='black')

    draw.text((stub_pad, 100), 'Boarding', font=SWA_REG_22, fill='black')
    draw.text((stub_pad, 130), 'Group/Position', font=SWA_REG_22, fill='black')
    draw.text((stub_pad, 160), boarding_position, font=SWA_BOLD_100, fill='black')

    draw.text((stub_pad, 270), re.sub(r'#0$', '', passenger), font=OCR_B_12, fill='black')
    draw.text((stub_pad, 290), f'Conf. #{confirmation}', font=OCR_B_12, fill='black')
    draw.text((stub_pad, 310), f'{flight_id} {from_airport.iata} to {to_airport.iata}', font=OCR_B_12, fill='black')

    # Barcode
    barcode_x = stub_pad
    barcode_y = 330
    barcode_w = width - stub_pad - 20
    barcode_h = 50

    draw_barcode(draw, barcode_x, barcode_y, barcode_w, barcode_h, confirmation)

    buf = io.BytesIO()
    image.save(buf, format='PNG')

    # Cache the image to disk
    try:
        os.makedirs(cache_path, exist_ok=True)
        img_cache_path = os.path.join(CACHE_DIR, flight.id, f"{confirmation_number}.png")
        
        with open(img_cache_path, 'wb') as f:
            logger.success(f"Caching boarding pass image to {img_cache_path} for {confirmation_number}")
            f.write(buf.getvalue())

    except Exception as e:
        logger.error(f"Failed to save boarding pass image to cache for {confirmation_number}", e)

    # return PNG bytes
    return buf.getvalue()
