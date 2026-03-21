import hmac
import hashlib
import json
import time
import urllib.parse
from typing import Optional

class AuthError(Exception):
    pass

def validate_init_data(init_data: str, bot_token: str, max_age: int = 3600) -> int:
    """
    Validate Telegram Mini App initData string.
    Returns the user's Telegram ID on success.
    Raises AuthError on failure.
    """
    params = dict(urllib.parse.parse_qsl(init_data))
    received_hash = params.pop("hash", None)
    if not received_hash:
        raise AuthError("invalid: missing hash")

    auth_date = int(params.get("auth_date", 0))
    if time.time() - auth_date > max_age:
        raise AuthError(f"expired: auth_date is {int(time.time() - auth_date)}s old")

    data_check_string = "\n".join(
        f"{k}={v}" for k, v in sorted(params.items())
    )
    secret_key = hmac.HMAC(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    expected_hash = hmac.HMAC(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected_hash, received_hash):
        raise AuthError("invalid: hash mismatch")

    user_data = json.loads(params.get("user", "{}"))
    user_id = user_data.get("id")
    if not user_id:
        raise AuthError("invalid: missing user.id")
    return int(user_id)

from fastapi import Request, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security = HTTPBearer()

async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> int:
    if not credentials or credentials.scheme.lower() != "tma":
        raise HTTPException(status_code=401, detail="Missing or invalid auth scheme")
    try:
        return validate_init_data(
            credentials.credentials,
            bot_token=request.app.state.bot_token,
        )
    except AuthError as e:
        raise HTTPException(status_code=401, detail=str(e))

async def require_admin(
    request: Request,
    user_id: int = Depends(get_current_user),
) -> int:
    from backend.db import is_admin
    if not await is_admin(request.app.state.pool, user_id):
        raise HTTPException(status_code=403, detail="Admin required")
    return user_id
