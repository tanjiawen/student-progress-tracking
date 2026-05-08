"""验证码生成与校验模块.

Security fix V-013: 登录验证码机制，防止暴力破解.
"""

from __future__ import annotations

import hashlib
import random
import string
from io import BytesIO

from PIL import Image, ImageDraw, ImageFont

from app.core.redis_client import redis_client

CAPTCHA_LENGTH = 4
CAPTCHA_TTL_SECONDS = 300  # 5 minutes
CAPTCHA_KEY_PREFIX = "captcha:"


def generate_captcha_text(length: int = CAPTCHA_LENGTH) -> str:
    """Generate random alphanumeric captcha text."""
    # Use digits and uppercase letters, excluding confusing ones (0, O, 1, I, L)
    chars = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"
    return "".join(random.choices(chars, k=length))


def generate_captcha_image(text: str, width: int = 120, height: int = 40) -> bytes:
    """Generate a captcha image from text and return as PNG bytes."""
    image = Image.new("RGB", (width, height), color=(255, 255, 255))
    draw = ImageDraw.Draw(image)

    # Add background noise (random lines)
    for _ in range(5):
        x1 = random.randint(0, width)
        y1 = random.randint(0, height)
        x2 = random.randint(0, width)
        y2 = random.randint(0, height)
        draw.line([(x1, y1), (x2, y2)], fill=(200, 200, 200), width=1)

    # Add noise dots
    for _ in range(100):
        x = random.randint(0, width)
        y = random.randint(0, height)
        draw.point((x, y), fill=(random.randint(150, 220), random.randint(150, 220), random.randint(150, 220)))

    # Draw text with slight rotation per character
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 24)
    except Exception:
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 24)
        except Exception:
            font = ImageFont.load_default()

    char_width = width // len(text)
    for i, char in enumerate(text):
        x = i * char_width + random.randint(5, 10)
        y = random.randint(5, 10)
        color = (
            random.randint(20, 100),
            random.randint(20, 100),
            random.randint(20, 100),
        )
        draw.text((x, y), char, font=font, fill=color)

    # Add border
    draw.rectangle([(0, 0), (width - 1, height - 1)], outline=(180, 180, 180), width=1)

    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


async def create_captcha(captcha_id: str) -> tuple[str, bytes]:
    """Create a new captcha and store the answer in Redis.

    Returns (captcha_text, image_bytes).
    """
    text = generate_captcha_text()
    image_bytes = generate_captcha_image(text)
    key = f"{CAPTCHA_KEY_PREFIX}{captcha_id}"
    await redis_client.setex(key, CAPTCHA_TTL_SECONDS, text)
    return text, image_bytes


async def verify_captcha(captcha_id: str, captcha_code: str) -> bool:
    """Verify a captcha code and delete it from Redis (one-time use).

    Returns True if valid, False otherwise.
    """
    if not captcha_id or not captcha_code:
        return False
    key = f"{CAPTCHA_KEY_PREFIX}{captcha_id}"
    stored = await redis_client.get(key)
    if stored is None:
        return False
    # Delete after verification (one-time use)
    await redis_client.delete(key)
    return stored.upper() == captcha_code.upper()
