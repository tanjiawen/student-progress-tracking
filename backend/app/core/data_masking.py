"""数据脱敏工具."""

from __future__ import annotations

from typing import Any

from app.core.config import settings


class DataMasker:
    """数据脱敏工具 —— 支持手机号、姓名、身份证号、邮箱等字段脱敏."""

    @staticmethod
    def mask_phone(phone: str) -> str:
        """手机号脱敏：138****8888."""
        if not phone or len(phone) < 7:
            return phone
        return phone[:3] + "****" + phone[-4:]

    @staticmethod
    def mask_name(name: str) -> str:
        """姓名脱敏：

        - 2 字 -> 谭*
        - 3 字 -> 谭*凌
        - >3 字 -> 谭**...凌
        """
        if not name:
            return name
        length = len(name)
        if length == 1:
            return name
        if length == 2:
            return name[0] + "*"
        return name[0] + "*" * (length - 2) + name[-1]

    @staticmethod
    def mask_id_card(id_card: str) -> str:
        """身份证号脱敏：保留最后 4 位."""
        if not id_card or len(id_card) < 4:
            return id_card
        return "*" * (len(id_card) - 4) + id_card[-4:]

    @staticmethod
    def mask_email(email: str) -> str:
        """邮箱脱敏：t**t@example.com."""
        if not email or "@" not in email:
            return email
        local, domain = email.split("@", 1)
        if len(local) <= 2:
            masked_local = local[0] + "*" if len(local) == 2 else "*"
        else:
            masked_local = local[0] + "*" * (len(local) - 2) + local[-1]
        return f"{masked_local}@{domain}"

    @staticmethod
    def mask_student_name_in_response(data: Any) -> Any:
        """递归遍历响应数据，对学生姓名相关字段脱敏.

        脱敏规则可通过 config.py 中的 MASKING_ENABLED 开关控制.
        """
        if not settings.MASKING_ENABLED:
            return data

        if isinstance(data, dict):
            result = {}
            for k, v in data.items():
                if isinstance(k, str) and k.lower() in {
                    "name",
                    "real_name",
                    "full_name",
                    "user_name",
                    "username",
                }:
                    result[k] = DataMasker.mask_name(v) if isinstance(v, str) else v
                else:
                    result[k] = DataMasker.mask_student_name_in_response(v)
            return result
        if isinstance(data, list):
            return [DataMasker.mask_student_name_in_response(item) for item in data]
        return data
