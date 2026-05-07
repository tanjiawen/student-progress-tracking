"""
PDF 处理服务
支持 PDF 转图片、分页提取、图像预处理（增强 OCR 效果）
"""

import io

import fitz  # PyMuPDF
from PIL import Image, ImageEnhance, ImageFilter

from app.core.exceptions import BadRequestException


class PDFService:
    """PDF 处理服务"""

    DEFAULT_DPI = 300  # OCR 推荐 300 DPI 以上
    MAX_IMAGE_SIZE = 4096  # 多模态模型通常有尺寸限制

    @staticmethod
    def pdf_to_images(
        pdf_bytes: bytes,
        dpi: int = DEFAULT_DPI,
        enhance: bool = True,
    ) -> list[tuple[int, bytes, str]]:
        """
        将 PDF 转换为图片列表

        Args:
            pdf_bytes: PDF 二进制数据
            dpi: 输出分辨率
            enhance: 是否进行图像增强

        Returns:
            [(page_number, image_bytes, format), ...]
        """
        try:
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        except Exception as e:
            raise BadRequestException(f"无法解析 PDF: {e}") from e

        images = []
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)

            # 使用矩阵提高分辨率
            mat = fitz.Matrix(dpi / 72, dpi / 72)
            pix = page.get_pixmap(matrix=mat, alpha=False)

            # 转换为 PIL Image
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

            # 图像增强（提高 OCR 准确率）
            if enhance:
                img = PDFService._enhance_image(img)

            # 限制最大尺寸（避免超出模型输入限制）
            img = PDFService._resize_if_needed(img)

            # 转为 bytes
            img_bytes = io.BytesIO()
            img.save(img_bytes, format="PNG", optimize=True)
            img_bytes.seek(0)

            images.append((page_num + 1, img_bytes.getvalue(), "png"))

        doc.close()
        return images

    @staticmethod
    def _enhance_image(img: Image.Image) -> Image.Image:
        """图像增强：对比度、锐化、去噪"""
        # 自动对比度
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(1.2)

        # 锐化
        img = img.filter(ImageFilter.SHARPEN)

        # 轻微去噪（保持文字清晰）
        img = img.filter(ImageFilter.MedianFilter(size=3))

        return img

    @staticmethod
    def _resize_if_needed(img: Image.Image) -> Image.Image:
        """如果图片过大，等比例缩小"""
        width, height = img.size
        max_dim = max(width, height)

        if max_dim > PDFService.MAX_IMAGE_SIZE:
            ratio = PDFService.MAX_IMAGE_SIZE / max_dim
            new_size = (int(width * ratio), int(height * ratio))
            img = img.resize(new_size, Image.Resampling.LANCZOS)

        return img

    @staticmethod
    def extract_text_from_pdf(pdf_bytes: bytes) -> str:
        """从 PDF 提取纯文本（备用方案）"""
        try:
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            text = ""
            for page in doc:
                text += page.get_text()
            doc.close()
            return text
        except Exception as e:
            raise BadRequestException(f"PDF 文本提取失败: {e}") from e

    @staticmethod
    def get_pdf_info(pdf_bytes: bytes) -> dict:
        """获取 PDF 基本信息"""
        try:
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            info = {
                "page_count": len(doc),
                "title": doc.metadata.get("title", ""),
                "author": doc.metadata.get("author", ""),
            }
            doc.close()
            return info
        except Exception as e:
            raise BadRequestException(f"无法读取 PDF 信息: {e}") from e

    @staticmethod
    def crop_answer_area(
        image_bytes: bytes,
        bbox: tuple[float, float, float, float],
    ) -> bytes:
        """
        从图片中裁剪指定区域（作答区）

        Args:
            image_bytes: 原始图片
            bbox: (x1, y1, x2, y2) 相对坐标 0-1 或绝对像素

        Returns:
            裁剪后的图片 bytes
        """
        img = Image.open(io.BytesIO(image_bytes))
        width, height = img.size

        # 如果 bbox 是相对坐标（0-1），转换为像素
        x1, y1, x2, y2 = bbox
        if all(0 <= v <= 1 for v in bbox):
            x1, y1, x2, y2 = int(x1 * width), int(y1 * height), int(x2 * width), int(y2 * height)

        cropped = img.crop((x1, y1, x2, y2))

        output = io.BytesIO()
        cropped.save(output, format="PNG")
        output.seek(0)
        return output.getvalue()


# 全局实例
pdf_service = PDFService()
