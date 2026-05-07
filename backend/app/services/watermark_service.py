"""试卷图片水印服务."""

from __future__ import annotations

import io

from PIL import Image, ImageDraw, ImageFont


class WatermarkService:
    """使用 Pillow 为试卷图片添加半透明文字水印."""

    def add_watermark(self, image_bytes: bytes, text: str) -> bytes:
        """为图片添加右下角半透明文字水印.

        Args:
            image_bytes: 原始图片二进制数据
            text: 水印文字（如用户 ID、考试 ID 或版权信息）

        Returns:
            带水印的 JPEG 图片二进制数据
        """
        img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")

        # 创建透明水印层
        watermark = Image.new("RGBA", img.size, (255, 255, 255, 0))
        draw = ImageDraw.Draw(watermark)

        # 动态计算字体大小（图片高度的 5%，最小 12px）
        font_size = max(12, int(img.size[1] * 0.05))
        font = self._load_font(font_size)

        # 计算文字尺寸
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        # 右下角位置，留边距
        margin = int(font_size * 0.5)
        x = img.size[0] - text_width - margin
        y = img.size[1] - text_height - margin

        # 半透明白色文字（Alpha 128 / 255）
        draw.text((x, y), text, font=font, fill=(255, 255, 255, 128))

        # 合并图层
        result = Image.alpha_composite(img, watermark)

        # 转回 RGB（JPEG 不支持透明度）
        if result.mode == "RGBA":
            background = Image.new("RGB", result.size, (255, 255, 255))
            background.paste(result, mask=result.split()[3])
            result = background

        output = io.BytesIO()
        result.save(output, format="JPEG", quality=90)
        return output.getvalue()

    def _load_font(self, font_size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        """尝试加载系统字体，失败则回退到默认字体."""
        font_paths = [
            "/System/Library/Fonts/PingFang.ttc",
            "/System/Library/Fonts/STHeiti Light.ttc",
            "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]
        for path in font_paths:
            try:
                return ImageFont.truetype(path, font_size)
            except Exception:
                continue
        return ImageFont.load_default()


# 全局实例
watermark_service = WatermarkService()
