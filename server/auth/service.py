import hashlib
import hmac
import secrets
from datetime import datetime

from auth.schemas import LoginResponse, row_to_profile
from config.settings import get_settings
from db.user_repo import find_by_username, touch_login


class AuthError(Exception):
    def __init__(self, message: str, code: str = 'auth_failed'):
        super().__init__(message)
        self.message = message
        self.code = code


def _password_match(stored: str, raw: str) -> bool:
    stored = str(stored or '').strip().lower()
    if len(stored) != 32 or not all(c in '0123456789abcdef' for c in stored):
        return False
    md5 = hashlib.md5(raw.encode('utf-8')).hexdigest()
    return hmac.compare_digest(stored, md5)


def _check_account_period(row: dict, now: datetime) -> None:
    start = row.get('start_time')
    end = row.get('end_time')
    if start and now < start:
        raise AuthError('账号尚未生效', 'not_started')
    if end and now > end:
        raise AuthError('账号已过期', 'expired')


def _issue_token(user_id: str) -> str:
    ttl = get_settings().auth_token_ttl_sec
    nonce = secrets.token_urlsafe(16)
    payload = '%s:%d:%s' % (user_id, int(datetime.now().timestamp()) + ttl, nonce)
    sig = hmac.new(b'rvc-client-auth', payload.encode('utf-8'), hashlib.sha256).hexdigest()
    return '%s.%s' % (payload, sig)


def login(username: str, password: str) -> LoginResponse:
    name = (username or '').strip()
    if not name:
        raise AuthError('请输入账号', 'invalid_input')
    row = find_by_username(name)
    if not row:
        raise AuthError('账号或密码错误', 'invalid_credentials')
    if not _password_match(str(row.get('user_pw') or ''), password):
        raise AuthError('账号或密码错误', 'invalid_credentials')
    now = datetime.now()
    _check_account_period(row, now)
    user_id = str(row.get('user_id') or '')
    touch_login(user_id, now)
    row['login_time'] = now
    row['update_time'] = now
    return LoginResponse(token=_issue_token(user_id), user=row_to_profile(row))
