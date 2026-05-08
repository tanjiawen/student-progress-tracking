# Fix bcrypt 4.2+ compatibility with passlib
import bcrypt
import hashlib
import re
if not hasattr(bcrypt, "__about__"):
    bcrypt.__about__ = type("obj", (object,), {"__version__": bcrypt.__version__})()

from datetime import UTC, datetime, timedelta
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings
from app.core.exceptions import BadRequestException

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
ALGORITHM = "HS256"


def validate_password(password: str) -> None:
    """密码策略：最小 8 位，最大 128 位，包含大小写+数字+特殊字符."""
    if len(password) < 8:
        raise BadRequestException("密码至少需要 8 位字符")
    if len(password) > 128:
        raise BadRequestException("密码不能超过 128 位字符")
    if not re.search(r"[A-Z]", password):
        raise BadRequestException("密码需要包含至少一个大写字母")
    if not re.search(r"[a-z]", password):
        raise BadRequestException("密码需要包含至少一个小写字母")
    if not re.search(r"\d", password):
        raise BadRequestException("密码需要包含至少一个数字")
    if not re.search(r"[!@#$%^&*()_+\-=\[\]{}|;:,.<>?]", password):
        raise BadRequestException("密码需要包含至少一个特殊字符（如 !@#$%^&* 等）")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password with backward-compatible SHA-256 pre-hash for long passwords."""
    password_bytes = plain_password.encode("utf-8")
    # Try direct verify first (backward compatible with existing hashes and short passwords)
    if pwd_context.verify(password_bytes, hashed_password):
        return True
    # Fall back to pre-hash for passwords > 72 bytes to avoid silent bcrypt truncation
    if len(password_bytes) > 72:
        prehashed = hashlib.sha256(password_bytes).hexdigest().encode("utf-8")
        return pwd_context.verify(prehashed, hashed_password)
    return False


def get_password_hash(password: str) -> str:
    """Hash password using SHA-256 pre-hash for passwords > 72 bytes."""
    password_bytes = password.encode("utf-8")
    if len(password_bytes) > 72:
        # Pre-hash with SHA-256 to avoid silent bcrypt truncation, then bcrypt the hex digest
        password_bytes = hashlib.sha256(password_bytes).hexdigest().encode("utf-8")
    return pwd_context.hash(password_bytes)


def create_access_token(subject: str | Any, expires_delta: timedelta | None = None) -> str:
    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode = {"exp": expire, "sub": str(subject), "type": "access"}
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def create_refresh_token(subject: str | Any) -> str:
    expire = datetime.now(UTC) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode = {"exp": expire, "sub": str(subject), "type": "refresh"}
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_token(token: str) -> dict[str, Any] | None:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None


# Security fix V-007: SSRF protection for AI fetch-url
import ipaddress
import socket
from urllib.parse import urlparse

BLOCKED_IP_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]

BLOCKED_HOST_SUFFIXES = {".internal", ".local", ".cluster.local"}


def validate_url_for_ssrf(url: str) -> None:
    """Validate URL to prevent SSRF attacks.

    Raises BadRequestException if URL points to private IP ranges or uses non-http(s) protocols.
    """
    from app.core.exceptions import BadRequestException

    parsed = urlparse(url)

    # Only allow http and https
    if parsed.scheme not in {"http", "https"}:
        raise BadRequestException("仅支持 http 和 https 协议")

    # Reject URLs with username/password
    if parsed.username or parsed.password:
        raise BadRequestException("URL 中不允许包含用户名或密码")

    hostname = parsed.hostname
    if not hostname:
        raise BadRequestException("无效的 URL")

    # Check blocked host suffixes
    lowered = hostname.lower()
    for suffix in BLOCKED_HOST_SUFFIXES:
        if lowered.endswith(suffix):
            raise BadRequestException(f"禁止访问内部域名: {hostname}")

    # Check if hostname is already an IP address
    try:
        addr = ipaddress.ip_address(hostname)
        if any(addr in net for net in BLOCKED_IP_NETWORKS):
            raise BadRequestException(f"禁止访问内网 IP 地址: {hostname}")
    except ValueError:
        # Not an IP, resolve via DNS and check resolved IPs
        try:
            resolved = socket.getaddrinfo(hostname, None)
            seen_ips = set()
            for family, _, _, _, sockaddr in resolved:
                ip_str = sockaddr[0]
                if ip_str in seen_ips:
                    continue
                seen_ips.add(ip_str)
                try:
                    addr = ipaddress.ip_address(ip_str)
                    if any(addr in net for net in BLOCKED_IP_NETWORKS):
                        raise BadRequestException(
                            f"域名 {hostname} 解析到内网 IP {ip_str}，禁止访问"
                        )
                except ValueError:
                    continue
        except socket.gaierror:
            raise BadRequestException(f"无法解析域名: {hostname}")
        except BadRequestException:
            raise
        except Exception as exc:
            raise BadRequestException(f"URL 安全校验失败: {exc}") from exc
