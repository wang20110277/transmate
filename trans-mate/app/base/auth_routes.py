"""
认证路由模块
处理登录、注册、Token刷新等认证相关API
"""
from fastapi import APIRouter, Depends, HTTPException, Header, Request, Query
from sqlalchemy.orm import Session
from typing import Optional
from pydantic import BaseModel

from app.core.database import get_db
from app.core.config import WECHAT_LOGIN_ENABLED
from app.schemas import (
    WechatLoginRequest, SMSCodeRequest, SMSCodeResponse, SMSLoginRequest,
    PasswordLoginRequest, TokenResponse, RefreshTokenRequest, RefreshTokenResponse,
    LogoutRequest, MessageResponse, ChangePasswordRequest, UserInfoResponse
)
from app.services.user_service import (
    get_user_by_phone, get_user_by_openid, create_user_by_phone,
    create_user_by_wechat, update_user_password, update_user_phone, update_user_nickname,
    update_last_login, verify_password
)
from app.services.auth_service import (
    create_auth_tokens, refresh_auth_tokens, logout_user, get_current_user_from_token
)
from app.services.sms_service import send_sms_code, verify_sms_code, check_sms_code_exists
from app.services.wechat_service import wechat_service, WeChatLoginStatus
from app.models.user import User

router = APIRouter(prefix="/api/auth", tags=["认证"])


# ==================== 微信扫码登录 ====================

class QRCodeResponse(BaseModel):
    """二维码响应"""
    scene_id: str
    qr_code_url: str
    expire_seconds: int
    message: str = "二维码生成成功"


class LoginStatusResponse(BaseModel):
    """登录状态响应"""
    status: str
    message: str
    user_info: Optional[dict] = None
    auth_code: Optional[str] = None


@router.post("/wechat/qr-code", response_model=QRCodeResponse)
async def create_wechat_qr_code():
    """
    生成微信登录二维码
    
    - 返回二维码URL和scene_id
    - 二维码有效期5分钟
    """
    if not WECHAT_LOGIN_ENABLED:
        raise HTTPException(status_code=503, detail="微信登录未启用")
    
    result = wechat_service.create_qr_code()
    
    return QRCodeResponse(
        scene_id=result["scene_id"],
        qr_code_url=result["qr_code_url"],
        expire_seconds=result["expire_seconds"]
    )


@router.get("/wechat/status/{scene_id}", response_model=LoginStatusResponse)
async def get_wechat_login_status(scene_id: str):
    """
    查询微信登录状态
    
    - pending: 等待扫码
    - scanned: 已扫码
    - authorized: 已授权（返回auth_code用于换取token）
    - rejected: 已拒绝
    - expired: 已过期
    """
    if not WECHAT_LOGIN_ENABLED:
        raise HTTPException(status_code=503, detail="微信登录未启用")
    
    result = wechat_service.get_login_status(scene_id)
    
    return LoginStatusResponse(
        status=result["status"],
        message=result["message"],
        user_info=result.get("user_info"),
        auth_code=result.get("auth_code")
    )


@router.get("/wechat/callback")
async def wechat_callback(
    request: Request,
    code: str = Query(..., description="微信授权码"),
    state: str = Query(..., description="防CSRF参数"),
    db: Session = Depends(get_db)
):
    """
    微信OAuth回调处理
    
    - 验证state参数
    - 用code换取access_token
    - 获取用户信息
    - 查找或创建用户
    - 更新登录状态
    """
    if not WECHAT_LOGIN_ENABLED:
        raise HTTPException(status_code=503, detail="微信登录未启用")
    
    # 验证 state 参数
    scene_id = wechat_service.validate_state(state)
    if not scene_id:
        return {"error": "无效的state参数，请重新扫码"}
    
    # 用 code 换取 access_token
    token_info = wechat_service.exchange_code_for_access_token(code)
    if not token_info:
        # 更新状态为失败
        wechat_service.update_login_status(
            scene_id,
            WeChatLoginStatus.REJECTED,
            user_info={"error": "获取access_token失败"}
        )
        return {"error": "授权失败，请重新扫码"}
    
    # 获取微信用户信息
    user_info = wechat_service.get_user_info(
        token_info["access_token"],
        token_info["openid"]
    )
    
    if not user_info:
        wechat_service.update_login_status(
            scene_id,
            WeChatLoginStatus.REJECTED,
            user_info={"error": "获取用户信息失败"}
        )
        return {"error": "获取用户信息失败，请重新扫码"}
    
    # 查找或创建用户
    try:
        user, is_new = wechat_service.find_or_create_user(db, user_info)
        
        # 更新最后登录时间
        update_last_login(db, user)
        
        # 更新登录状态
        wechat_service.update_login_status(
            scene_id,
            WeChatLoginStatus.AUTHORIZED,
            user_info={
                "openid": user_info.get("openid"),
                "nickname": user_info.get("nickname"),
                "avatar": user_info.get("headimgurl"),
                "user_id": user.id,
                "is_new": is_new
            },
            auth_code=code
        )
        
        # 返回HTML页面，自动关闭或跳转到成功页
        return {
            "message": "授权成功",
            "scene_id": scene_id,
            "user_id": user.id,
            "nickname": user.nickname
        }
        
    except Exception as e:
        wechat_service.update_login_status(
            scene_id,
            WeChatLoginStatus.REJECTED,
            user_info={"error": str(e)}
        )
        return {"error": f"登录处理失败: {str(e)}"}


@router.post("/wechat/qr-login", response_model=TokenResponse)
async def wechat_qr_login(
    request: WechatLoginRequest,
    db: Session = Depends(get_db)
):
    """
    微信扫码登录（用auth_code换取token）
    
    - 前端轮询到authorized状态后，调用此接口
    - 用auth_code完成登录，换取JWT token
    """
    if not WECHAT_LOGIN_ENABLED:
        raise HTTPException(status_code=503, detail="微信登录未启用")
    
    # 实际场景：可以用auth_code再次验证或直接信任之前的登录流程
    # 这里简化处理，通过code获取用户信息
    
    # 查询用户（通过openid）
    # 注意：实际应该用更安全的验证方式
    user = get_user_by_openid(db, request.code)
    
    if user is None:
        raise HTTPException(status_code=400, detail="登录失败，用户不存在")
    
    # 更新最后登录时间
    update_last_login(db, user)
    
    # 创建Token
    access_token, refresh_token, device_id = create_auth_tokens(user.id)
    
    return TokenResponse(
        id=user.id,
        username=user.username,
        access_token=access_token,
        refresh_token=refresh_token,
        device_id=device_id,
        is_first_login=False  # 扫码登录必然是已存在的用户
    )


# ==================== 微信授权登录（原有）====================

@router.post("/wechat/login", response_model=TokenResponse)
async def wechat_login(
    request: WechatLoginRequest,
    db: Session = Depends(get_db)
):
    """
    微信授权登录
    
    - 新用户自动注册
    - 首次登录 is_first_login=true
    """
    # TODO: 实现微信code换取openid的逻辑
    # 当前为演示，使用code作为openid
    openid = request.code  # 实际应调用微信API: wx.login -> code -> openid
    
    # 查询用户是否存在
    user = get_user_by_openid(db, openid)
    is_first_login = False
    
    if user is None:
        # 新用户，创建账号
        # 检查手机号是否已存在其他账号，如果存在则关联
        if request.phone:
            existing_user = get_user_by_phone(db, request.phone)
            if existing_user:
                # 关联已有账号
                existing_user.wechat_openid = openid
                db.commit()
                db.refresh(existing_user)
                user = existing_user
            else:
                # 创建新用户
                user = create_user_by_wechat(db, openid, phone=request.phone)
        else:
            # 创建新用户，手机号为空
            user = create_user_by_wechat(db, openid)
        is_first_login = True
    else:
        # 老用户，如有手机号则更新
        if request.phone and not user.phone:
            user = update_user_phone(db, user, request.phone)
    
    # 更新最后登录时间
    update_last_login(db, user)
    
    # 创建Token
    access_token, refresh_token, device_id = create_auth_tokens(user.id)
    
    return TokenResponse(
        id=user.id,
        username=user.username,
        access_token=access_token,
        refresh_token=refresh_token,
        device_id=device_id,
        is_first_login=is_first_login
    )


# ==================== 短信验证码登录 ====================

@router.post("/sms/send", response_model=SMSCodeResponse)
async def send_sms(
    request: SMSCodeRequest,
    db: Session = Depends(get_db)
):
    """
    发送短信验证码
    
    - 验证码60秒有效
    - 60秒内不能重复发送
    """
    # 检查是否已存在未过期的验证码
    if check_sms_code_exists(request.phone):
        raise HTTPException(status_code=429, detail="验证码已发送，请60秒后重试")
    
    # 发送验证码
    code, expires_in = send_sms_code(request.phone)
    
    # 测试环境返回验证码（生产环境应仅返回message）
    return SMSCodeResponse(
        message=f"验证码已发送",
        expires_in=expires_in
    )


@router.post("/sms/login", response_model=TokenResponse)
async def sms_login(
    request: SMSLoginRequest,
    db: Session = Depends(get_db)
):
    """
    短信验证码登录/注册
    
    - 验证码验证成功后删除（防重用）
    - 新用户自动注册
    """
    # 验证验证码
    if not verify_sms_code(request.phone, request.code):
        raise HTTPException(status_code=400, detail="验证码错误或已过期")
    
    # 查询用户
    user = get_user_by_phone(db, request.phone)
    is_first_login = False
    
    if user is None:
        # 新用户，创建账号
        user = create_user_by_phone(db, request.phone, register_source="SMS")
        is_first_login = True
    
    # 更新最后登录时间
    update_last_login(db, user)
    
    # 创建Token
    access_token, refresh_token, device_id = create_auth_tokens(user.id)
    
    return TokenResponse(
        id=user.id,
        username=user.username,
        access_token=access_token,
        refresh_token=refresh_token,
        device_id=device_id,
        is_first_login=is_first_login
    )


# ==================== 手机号密码登录 ====================

@router.post("/password/login", response_model=TokenResponse)
async def password_login(
    request: PasswordLoginRequest,
    db: Session = Depends(get_db)
):
    """
    手机号密码登录
    
    **首次登录（手机号未注册）:**
    - 需要 confirm_password
    - 自动注册，设置密码
    
    **非首次登录:**
    - 只需 password
    - 验证密码登录
    
    **存量用户（is_password_set=0）:**
    - 首次使用密码登录时，将输入的密码视为设置密码
    - 自动更新密码
    """
    # 查询用户
    user = get_user_by_phone(db, request.phone)
    is_first_login = False
    
    if user is None:
        # 情况A: 用户不存在，首次注册
        if not request.confirm_password:
            raise HTTPException(status_code=400, detail="首次登录需要确认密码")
        
        if request.password != request.confirm_password:
            raise HTTPException(status_code=400, detail="两次密码不一致")
        
        # 创建用户并设置密码
        user = create_user_by_phone(
            db, 
            request.phone, 
            password=request.password,
            register_source="PASSWORD"
        )
        is_first_login = True
    else:
        # 用户已存在
        if user.is_password_set == 0:
            # 情况C: 存量用户，首次设置密码
            if not request.confirm_password:
                raise HTTPException(status_code=400, detail="请设置密码（输入确认密码）")
            
            if request.password != request.confirm_password:
                raise HTTPException(status_code=400, detail="两次密码不一致")
            
            # 更新密码
            user = update_user_password(db, user, request.password)
            is_first_login = True
        else:
            # 情况B: 已设置密码，验证登录
            if not verify_password(request.password, user.password_hash):
                raise HTTPException(status_code=401, detail="密码错误")
    
    # 更新最后登录时间
    update_last_login(db, user)
    
    # 创建Token
    access_token, refresh_token, device_id = create_auth_tokens(user.id)
    
    return TokenResponse(
        id=user.id,
        username=user.username,
        access_token=access_token,
        refresh_token=refresh_token,
        device_id=device_id,
        is_first_login=is_first_login
    )


# ==================== Token管理 ====================

@router.post("/refresh", response_model=RefreshTokenResponse)
async def refresh_token(request: RefreshTokenRequest):
    """
    刷新Token
    
    - 使用refresh_token获取新的access_token
    - 同时返回新的refresh_token
    """
    result = refresh_auth_tokens(
        request.user_id,
        request.device_id,
        request.refresh_token
    )
    
    if result is None:
        raise HTTPException(status_code=401, detail="刷新token无效或已过期")
    
    new_access_token, new_refresh_token = result
    
    return RefreshTokenResponse(
        access_token=new_access_token,
        refresh_token=new_refresh_token
    )


@router.post("/logout", response_model=MessageResponse)
async def logout(
    request: LogoutRequest,
    authorization: str = Header(..., alias="Authorization"),
    db: Session = Depends(get_db)
):
    """
    用户登出
    
    - 删除Redis中的token
    """
    # 解析token获取user_id
    token = authorization.replace("Bearer ", "")
    parts = token.split(":")
    if len(parts) != 3:
        raise HTTPException(status_code=401, detail="无效的token")
    
    try:
        user_id = int(parts[0])
    except ValueError:
        raise HTTPException(status_code=401, detail="无效的token")
    
    # 执行登出
    logout_user(user_id, request.device_id)
    
    return MessageResponse(message="登出成功")


# ==================== 用户信息 ====================

@router.get("/me", response_model=UserInfoResponse)
async def get_me(
    authorization: str = Header(..., alias="Authorization"),
    db: Session = Depends(get_db)
):
    """
    获取当前用户信息
    
    - 需要Authorization header
    """
    user = get_current_user_from_token(db, authorization)
    
    if user is None:
        raise HTTPException(status_code=401, detail="未登录或token已过期")
    
    return UserInfoResponse(
        id=user.id,
        username=user.username,
        nickname=user.nickname,
        avatar_url=user.avatar_url,
        phone=user.phone,
        role=user.role,
        is_password_set=user.is_password_set == 1
    )


# ==================== 密码管理 ====================

@router.post("/password/change", response_model=MessageResponse)
async def change_password(
    request: ChangePasswordRequest,
    authorization: str = Header(..., alias="Authorization"),
    db: Session = Depends(get_db)
):
    """
    修改密码
    
    - 无需验证旧密码，直接设置新密码
    """
    user = get_current_user_from_token(db, authorization)
    
    if user is None:
        raise HTTPException(status_code=401, detail="未登录或token已过期")
    
    # 验证新密码和确认密码
    if request.new_password != request.confirm_password:
        raise HTTPException(status_code=400, detail="两次密码不一致")
    
    # 更新密码
    update_user_password(db, user, request.new_password)
    
    return MessageResponse(message="密码修改成功")




# ==================== 用户信息管理 ====================


class UpdateNicknameRequest(BaseModel):
    """更新昵称请求"""
    nickname: str


@router.put("/user/nickname", response_model=MessageResponse)
async def update_nickname(
    request: UpdateNicknameRequest,
    authorization: str = Header(..., alias="Authorization"),
    db: Session = Depends(get_db)
):
    """
    更新用户昵称
    
    - nickname: 新昵称，最多10个字符
    - 支持中英文、数字和表情符号
    """
    user = get_current_user_from_token(db, authorization)
    
    if user is None:
        raise HTTPException(status_code=401, detail="未登录或token已过期")
    
    # 验证昵称长度（考虑emoji占2个字符显示宽度）
    if len(request.nickname) > 10:
        raise HTTPException(status_code=400, detail="昵称最多10个字符")
    
    if not request.nickname.strip():
        raise HTTPException(status_code=400, detail="昵称不能为空")
    
    # 更新昵称
    update_user_nickname(db, user, request.nickname.strip())
    
    return MessageResponse(message="昵称修改成功")
