import pytest
import time
import hmac
import hashlib
import urllib.parse
from backend.api.auth import validate_init_data, AuthError

BOT_TOKEN = "123456:ABC-test-token"

def make_init_data(user_id: int, bot_token: str, age_seconds: int = 0) -> str:
    auth_date = int(time.time()) - age_seconds
    data_dict = {
        "user": f'{{"id":{user_id},"first_name":"Test"}}',
        "auth_date": str(auth_date),
        "query_id": "test",
    }
    data_check_string = "\n".join(
        f"{k}={v}" for k, v in sorted(data_dict.items())
    )
    secret_key = hmac.HMAC(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    hash_value = hmac.HMAC(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    data_dict["hash"] = hash_value
    return urllib.parse.urlencode(data_dict)

def test_valid_init_data_returns_user_id():
    init_data = make_init_data(user_id=42, bot_token=BOT_TOKEN)
    user_id = validate_init_data(init_data, bot_token=BOT_TOKEN)
    assert user_id == 42

def test_expired_init_data_raises():
    init_data = make_init_data(user_id=42, bot_token=BOT_TOKEN, age_seconds=7200)
    with pytest.raises(AuthError, match="expired"):
        validate_init_data(init_data, bot_token=BOT_TOKEN)

def test_invalid_hash_raises():
    init_data = make_init_data(user_id=42, bot_token=BOT_TOKEN)
    tampered = init_data + "&extra=evil"
    with pytest.raises(AuthError, match="invalid"):
        validate_init_data(tampered, bot_token=BOT_TOKEN)
