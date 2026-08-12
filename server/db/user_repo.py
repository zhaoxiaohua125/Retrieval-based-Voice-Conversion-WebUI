"""bus_user 表数据访问。"""

from datetime import datetime

from sqlalchemy import text

from db.engine import session_scope

_SELECT_BY_NAME = text(
    """
    SELECT user_id, user_name, user_pw, user_real, user_money,
           start_time, end_time, input_time, update_time, login_time
    FROM bus_user
    WHERE user_name = :user_name
    LIMIT 1
    """
)

_UPDATE_LOGIN = text(
    """
    UPDATE bus_user
    SET login_time = :now, update_time = :now
    WHERE user_id = :user_id
    """
)


def find_by_username(user_name: str) -> dict | None:
    with session_scope() as session:
        row = session.execute(_SELECT_BY_NAME, {'user_name': user_name}).mappings().first()
        return dict(row) if row else None


def touch_login(user_id: str, now: datetime | None = None) -> None:
    now = now or datetime.now()
    with session_scope() as session:
        session.execute(_UPDATE_LOGIN, {'user_id': user_id, 'now': now})
