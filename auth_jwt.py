"""Özgün JWT (HS256) üretimi ve doğrulaması - harici JWT kütüphanesi kullanılmaz."""
import base64
import hashlib
import hmac
import json
import time

from config import JWT_SECRET

if not JWT_SECRET:
    raise RuntimeError(".env dosyasında JWT_SECRET tanımlı olmalı!")

TOKEN_TTL = 60 * 60  # 1 saat


def _b64e(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64d(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _sign(message: bytes) -> str:
    digest = hmac.new(JWT_SECRET.encode(), message, hashlib.sha256).digest()
    return _b64e(digest)


def create_token(user: dict, ttl: int = TOKEN_TTL) -> str:
    """Giriş yapan kullanıcı için imzalı token üretir."""
    header = _b64e(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    now = int(time.time())
    payload = _b64e(
        json.dumps(
            {
                "sub": user["user_id"],
                "username": user["username"],
                "role": user["role"],
                "iat": now,
                "exp": now + ttl,
            },
            separators=(",", ":"),
        ).encode()
    )
    signing_input = f"{header}.{payload}"
    return f"{signing_input}.{_sign(signing_input.encode())}"


def verify_token(token):
    """Token geçerliyse içeriğini (payload) döndürür, değilse None."""
    if not token:
        return None
    try:
        header_b64, payload_b64, signature = token.split(".")
        expected = _sign(f"{header_b64}.{payload_b64}".encode())
        if not hmac.compare_digest(signature, expected):   # imza kontrolü
            return None
        if json.loads(_b64d(header_b64)).get("alg") != "HS256":
            return None
        payload = json.loads(_b64d(payload_b64))
        if payload.get("exp", 0) < time.time():            # süre kontrolü
            return None
        return payload
    except Exception:
        return None