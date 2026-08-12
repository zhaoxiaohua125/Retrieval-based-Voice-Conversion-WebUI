from fastapi import APIRouter
from fastapi.responses import JSONResponse

from auth.schemas import LoginRequest, LoginResponse
from auth.service import AuthError, login
from db.engine import ping_db, ping_db_detail

router = APIRouter(prefix='/api/auth', tags=['auth'])


@router.post('/login', response_model=LoginResponse)
def auth_login(body: LoginRequest):
    ok, err = ping_db_detail()
    if not ok:
        msg = '数据库连接失败，请检查 MySQL 配置'
        if err:
            msg += '（%s）' % err
        return JSONResponse(status_code=503, content={'ok': False, 'message': msg})
    try:
        return login(body.username.strip(), body.password)
    except AuthError as exc:
        status = 403 if exc.code in ('expired', 'not_started') else 401
        return JSONResponse(status_code=status, content={'ok': False, 'message': exc.message})


@router.get('/health')
def auth_health():
    ok = ping_db()
    return {'ok': ok, 'db': ok}
