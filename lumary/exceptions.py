"""
@Author     : zarkhan
@Date       : 2026/6/14
@Description: 统一业务异常
"""
from starlette import status
from starlette.exceptions import HTTPException


class BadRequestError(HTTPException):
    """请求错误"""

    def __init__(self, detail: str | None = None):
        """初始化请求错误"""
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail or 'Bad request'
        )


class UnauthorizedError(HTTPException):
    """未授权错误"""

    def __init__(self, detail: str | None = None):
        """初始化未授权错误"""
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail or 'Unauthorized'
        )


class PaymentRequiredError(HTTPException):
    """需要付费错误"""

    def __init__(self, detail: str | None = None):
        """初始化需要付费错误"""
        super().__init__(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=detail or 'Payment required'
        )


class ForbiddenError(HTTPException):
    """禁止访问错误"""

    def __init__(self, detail: str | None = None):
        """初始化禁止访问错误"""
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail or 'Forbidden'
        )


class NotFoundError(HTTPException):
    """未找到错误"""

    def __init__(self, detail: str | None = None):
        """初始化未找到错误"""
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=detail or 'Not found'
        )


class MethodNotAllowedError(HTTPException):
    """方法不允许错误"""

    def __init__(self, detail: str | None = None):
        """初始化方法不允许错误"""
        super().__init__(
            status_code=status.HTTP_405_METHOD_NOT_ALLOWED,
            detail=detail or 'Method not allowed'
        )


class NotAcceptableError(HTTPException):
    """不可接受错误"""

    def __init__(self, detail: str | None = None):
        """初始化不可接受错误"""
        super().__init__(
            status_code=status.HTTP_406_NOT_ACCEPTABLE,
            detail=detail or 'Not acceptable'
        )


class RequestTimeoutError(HTTPException):
    """请求超时错误"""

    def __init__(self, detail: str | None = None):
        """初始化请求超时错误"""
        super().__init__(
            status_code=status.HTTP_408_REQUEST_TIMEOUT,
            detail=detail or 'Request timeout'
        )


class ConflictError(HTTPException):
    """资源冲突错误"""

    def __init__(self, detail: str | None = None):
        """初始化资源冲突错误"""
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail=detail or 'Conflict'
        )


class GoneError(HTTPException):
    """资源已永久删除错误"""

    def __init__(self, detail: str | None = None):
        """初始化资源已永久删除错误"""
        super().__init__(
            status_code=status.HTTP_410_GONE,
            detail=detail or 'Gone'
        )


class PreconditionFailedError(HTTPException):
    """前置条件失败错误"""

    def __init__(self, detail: str | None = None):
        """初始化前置条件失败错误"""
        super().__init__(
            status_code=status.HTTP_412_PRECONDITION_FAILED,
            detail=detail or 'Precondition failed'
        )


class PayloadTooLargeError(HTTPException):
    """请求体过大错误"""

    def __init__(self, detail: str | None = None):
        """初始化请求体过大错误"""
        super().__init__(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=detail or 'Payload too large'
        )


class URITooLongError(HTTPException):
    """URI 过长错误"""

    def __init__(self, detail: str | None = None):
        """初始化 URI 过长错误"""
        super().__init__(
            status_code=status.HTTP_414_REQUEST_URI_TOO_LONG,
            detail=detail or 'URI too long'
        )


class UnsupportedMediaTypeError(HTTPException):
    """不支持的媒体类型错误"""

    def __init__(self, detail: str | None = None):
        """初始化不支持的媒体类型错误"""
        super().__init__(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=detail or 'Unsupported media type'
        )


class LockedError(HTTPException):
    """资源锁定错误"""

    def __init__(self, detail: str | None = None):
        """初始化资源锁定错误"""
        super().__init__(
            status_code=status.HTTP_423_LOCKED,
            detail=detail or 'Locked'
        )


class TooManyRequestsError(HTTPException):
    """请求过于频繁错误

    用于限流场景，可设置 Retry-After 头告知客户端重试等待时间
    """

    def __init__(self, detail: str | None = None, retry_after: int | None = None):
        """初始化请求过于频繁错误

        Args:
            detail: 错误详情
            retry_after: 建议重试等待秒数（自动设置 Retry-After 头）
        """
        headers = {'Retry-After': str(retry_after)} if retry_after is not None else None
        super().__init__(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=detail or 'Too many requests',
            headers=headers
        )
