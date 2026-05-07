"""
文件存储服务 - MinIO 对象存储封装
支持试卷、答题卡、答案文件的上传、下载、预签名 URL
"""

import io
from datetime import timedelta
from uuid import uuid4

from minio import Minio
from minio.error import S3Error

from app.core.config import settings
from app.core.exceptions import BadRequestException


class StorageService:
    """MinIO 存储服务"""

    def __init__(self) -> None:
        self._client: Minio | None = None
        self.bucket_name = settings.MINIO_BUCKET_NAME
        self.endpoint = settings.MINIO_ENDPOINT
        self.access_key = settings.MINIO_ACCESS_KEY
        self.secret_key = settings.MINIO_SECRET_KEY
        self.secure = settings.MINIO_SECURE

    @property
    def client(self) -> Minio:
        if self._client is None:
            self._client = Minio(
                self.endpoint,
                access_key=self.access_key,
                secret_key=self.secret_key,
                secure=self.secure,
            )
        return self._client

    def _ensure_bucket(self) -> None:
        """确保存储桶存在"""
        if not self.client.bucket_exists(self.bucket_name):
            self.client.make_bucket(self.bucket_name)

    def upload_file(
        self,
        file_data: bytes,
        filename: str,
        content_type: str = "application/octet-stream",
        folder: str = "exams",
    ) -> str:
        """
        上传文件到 MinIO

        Args:
            file_data: 文件二进制数据
            filename: 原始文件名
            content_type: MIME 类型
            folder: 存储文件夹

        Returns:
            object_name (存储路径)
        """
        ext = filename.split(".")[-1].lower() if "." in filename else "bin"
        object_name = f"{folder}/{uuid4().hex}.{ext}"

        try:
            self.client.put_object(
                self.bucket_name,
                object_name,
                io.BytesIO(file_data),
                length=len(file_data),
                content_type=content_type,
            )
        except S3Error as e:
            raise BadRequestException(f"文件上传失败: {e}") from e

        return object_name

    def upload_pdf(self, file_data: bytes, filename: str, exam_id: int) -> str:
        """上传 PDF 试卷"""
        return self.upload_file(
            file_data=file_data,
            filename=filename,
            content_type="application/pdf",
            folder=f"exams/{exam_id}/pdf",
        )

    def upload_image(
        self,
        file_data: bytes,
        filename: str,
        exam_id: int,
        page_number: int = 1,
    ) -> str:
        """上传图片（答题卡/试卷页）"""
        ext = filename.split(".")[-1].lower() if "." in filename else "jpg"
        object_name = f"exams/{exam_id}/images/page_{page_number:03d}.{ext}"

        content_type_map = {
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "png": "image/png",
            "webp": "image/webp",
        }
        content_type = content_type_map.get(ext, "image/jpeg")

        self.client.put_object(
            self.bucket_name,
            object_name,
            io.BytesIO(file_data),
            length=len(file_data),
            content_type=content_type,
        )
        return object_name

    def upload_answer_key(
        self, file_data: bytes, filename: str, exam_id: int
    ) -> str:
        """上传标准答案文件"""
        return self.upload_file(
            file_data=file_data,
            filename=filename,
            content_type="application/pdf",
            folder=f"exams/{exam_id}/answer_key",
        )

    def get_presigned_url(self, object_name: str, expires: int = 3600) -> str:
        """获取预签名访问 URL"""
        try:
            return self.client.presigned_get_object(
                self.bucket_name, object_name, expires=timedelta(seconds=expires)
            )
        except S3Error:
            return ""

    def get_file_bytes(self, object_name: str) -> bytes:
        """下载文件为 bytes"""
        try:
            response = self.client.get_object(self.bucket_name, object_name)
            return response.read()
        except S3Error as e:
            raise BadRequestException(f"文件读取失败: {e}") from e

    def delete_file(self, object_name: str) -> None:
        """删除文件"""
        import contextlib

        with contextlib.suppress(S3Error):
            self.client.remove_object(self.bucket_name, object_name)


# 全局实例
storage_service = StorageService()
