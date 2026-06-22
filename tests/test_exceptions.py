"""
@Author     : zarkhan
@CreateDate : 2026/6/17
@Description: 业务异常类单元测试，覆盖所有预定义异常的status_code / detail默认值及自定义值
"""
import pytest
from starlette import status

from lumary.exceptions import (
    BadRequestError,
    UnauthorizedError,
    PaymentRequiredError,
    ForbiddenError,
    NotFoundError,
    MethodNotAllowedError,
    NotAcceptableError,
    RequestTimeoutError,
    ConflictError,
    GoneError,
    PreconditionFailedError,
    PayloadTooLargeError,
    URITooLongError,
    UnsupportedMediaTypeError,
    LockedError,
    TooManyRequestsError)


# ──────────────────────────────────────────────
# 参数化测试：(异常类, 期望状态码, 期望默认detail)
# ──────────────────────────────────────────────
_DEFAULT_CASES = [
    (BadRequestError,          status.HTTP_400_BAD_REQUEST,          'Bad request'),
    (UnauthorizedError,        status.HTTP_401_UNAUTHORIZED,         'Unauthorized'),
    (PaymentRequiredError,     status.HTTP_402_PAYMENT_REQUIRED,     'Payment required'),
    (ForbiddenError,           status.HTTP_403_FORBIDDEN,            'Forbidden'),
    (NotFoundError,            status.HTTP_404_NOT_FOUND,            'Not found'),
    (MethodNotAllowedError,    status.HTTP_405_METHOD_NOT_ALLOWED,   'Method not allowed'),
    (NotAcceptableError,       status.HTTP_406_NOT_ACCEPTABLE,       'Not acceptable'),
    (RequestTimeoutError,      status.HTTP_408_REQUEST_TIMEOUT,      'Request timeout'),
    (ConflictError,            status.HTTP_409_CONFLICT,             'Conflict'),
    (GoneError,                status.HTTP_410_GONE,                 'Gone'),
    (PreconditionFailedError,  status.HTTP_412_PRECONDITION_FAILED,  'Precondition failed'),
    (PayloadTooLargeError,     status.HTTP_413_CONTENT_TOO_LARGE,    'Payload too large'),
    (URITooLongError,          status.HTTP_414_URI_TOO_LONG,         'URI too long'),
    (UnsupportedMediaTypeError, status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, 'Unsupported media type'),
    (LockedError,              status.HTTP_423_LOCKED,               'Locked'),
    (TooManyRequestsError,     status.HTTP_429_TOO_MANY_REQUESTS,    'Too many requests'),
]

_IDS = [cls.__name__ for cls, _, _ in _DEFAULT_CASES]


class TestDefaultExceptions:
    @pytest.mark.parametrize('exc_cls, expected_code, expected_detail', _DEFAULT_CASES, ids=_IDS)
    def test_default_status_code(self, exc_cls, expected_code, expected_detail):
        exc = exc_cls()
        assert exc.status_code == expected_code

    @pytest.mark.parametrize('exc_cls, expected_code, expected_detail', _DEFAULT_CASES, ids=_IDS)
    def test_default_detail(self, exc_cls, expected_code, expected_detail):
        exc = exc_cls()
        assert exc.detail == expected_detail

    @pytest.mark.parametrize('exc_cls, expected_code, expected_detail', _DEFAULT_CASES, ids=_IDS)
    def test_custom_detail(self, exc_cls, expected_code, expected_detail):
        exc = exc_cls(detail='自定义错误信息')
        assert exc.detail == '自定义错误信息'


class TestTooManyRequestsError:
    def test_no_retry_after_header(self):
        exc = TooManyRequestsError()
        assert exc.headers is None

    def test_retry_after_header_set(self):
        exc = TooManyRequestsError(retry_after=60)
        assert exc.headers == {'Retry-After': '60'}

    def test_retry_after_zero(self):
        exc = TooManyRequestsError(retry_after=0)
        assert exc.headers == {'Retry-After': '0'}

    def test_default_detail(self):
        assert TooManyRequestsError().detail == 'Too many requests'

    def test_custom_detail_with_retry_after(self):
        exc = TooManyRequestsError(detail='限流中', retry_after=30)
        assert exc.detail == '限流中'
        assert exc.headers == {'Retry-After': '30'}
