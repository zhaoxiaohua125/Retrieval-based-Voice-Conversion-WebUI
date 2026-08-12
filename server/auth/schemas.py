from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=1, max_length=50)


class UserProfile(BaseModel):
    user_id: str
    user_name: str
    user_real: str | None = None
    user_money: float | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    input_time: datetime | None = None
    update_time: datetime | None = None
    login_time: datetime | None = None


class LoginResponse(BaseModel):
    ok: bool = True
    message: str = '登录成功'
    token: str
    user: UserProfile


class ErrorResponse(BaseModel):
    ok: bool = False
    message: str


def row_to_profile(row: dict) -> UserProfile:
    money = row.get('user_money')
    if isinstance(money, Decimal):
        money = float(money)
    return UserProfile(
        user_id=str(row.get('user_id') or ''),
        user_name=str(row.get('user_name') or ''),
        user_real=row.get('user_real'),
        user_money=money,
        start_time=row.get('start_time'),
        end_time=row.get('end_time'),
        input_time=row.get('input_time'),
        update_time=row.get('update_time'),
        login_time=row.get('login_time'),
    )
