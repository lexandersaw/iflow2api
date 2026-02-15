"""速率限制模块 - 使用滑动窗口算法实现请求限流"""

import time
from collections import defaultdict
from threading import Lock
from typing import Optional

from pydantic import BaseModel


class RateLimitConfig(BaseModel):
    """速率限制配置"""
    enabled: bool = True
    requests_per_minute: int = 60
    requests_per_hour: int = 1000
    requests_per_day: int = 10000


class RateLimiter:
    """速率限制器 - 使用滑动窗口算法
    
    支持每分钟、每小时、每天的请求限制
    """

    def __init__(
        self,
        per_minute: int = 60,
        per_hour: int = 1000,
        per_day: int = 10000,
    ):
        """初始化速率限制器
        
        Args:
            per_minute: 每分钟最大请求数
            per_hour: 每小时最大请求数
            per_day: 每天最大请求数
        """
        self.per_minute = per_minute
        self.per_hour = per_hour
        self.per_day = per_day
        
        # 存储每个客户端的请求时间戳
        # {client_id: [timestamp1, timestamp2, ...]}
        self._requests: dict[str, list[float]] = defaultdict(list)
        self._lock = Lock()
    
    def _clean_old_requests(self, client_id: str, window: float) -> None:
        """清理过期的请求记录
        
        Args:
            client_id: 客户端标识
            window: 时间窗口（秒）
        """
        cutoff = time.time() - window
        self._requests[client_id] = [
            ts for ts in self._requests[client_id] if ts > cutoff
        ]
    
    def _count_requests(self, client_id: str, window: float) -> int:
        """统计时间窗口内的请求数
        
        Args:
            client_id: 客户端标识
            window: 时间窗口（秒）
        
        Returns:
            时间窗口内的请求数
        """
        self._clean_old_requests(client_id, window)
        return len(self._requests[client_id])
    
    def is_allowed(self, client_id: str = "default") -> tuple[bool, Optional[str]]:
        """检查请求是否被允许
        
        Args:
            client_id: 客户端标识（如 IP 地址或 API Key）
        
        Returns:
            (是否允许, 错误消息)
        """
        with self._lock:
            now = time.time()
            
            # 检查每分钟限制
            minute_count = self._count_requests(client_id, 60)
            if minute_count >= self.per_minute:
                return False, f"Rate limit exceeded: {self.per_minute} requests per minute"
            
            # 检查每小时限制
            hour_count = self._count_requests(client_id, 3600)
            if hour_count >= self.per_hour:
                return False, f"Rate limit exceeded: {self.per_hour} requests per hour"
            
            # 检查每天限制
            day_count = self._count_requests(client_id, 86400)
            if day_count >= self.per_day:
                return False, f"Rate limit exceeded: {self.per_day} requests per day"
            
            # 记录请求
            self._requests[client_id].append(now)
            return True, None
    
    def record_request(self, client_id: str = "default") -> None:
        """记录一次请求
        
        Args:
            client_id: 客户端标识
        """
        with self._lock:
            self._requests[client_id].append(time.time())
    
    def get_stats(self, client_id: str = "default") -> dict:
        """获取客户端的请求统计
        
        Args:
            client_id: 客户端标识
        
        Returns:
            统计信息字典
        """
        with self._lock:
            return {
                "minute": self._count_requests(client_id, 60),
                "hour": self._count_requests(client_id, 3600),
                "day": self._count_requests(client_id, 86400),
                "limits": {
                    "per_minute": self.per_minute,
                    "per_hour": self.per_hour,
                    "per_day": self.per_day,
                },
            }
    
    def reset(self, client_id: Optional[str] = None) -> None:
        """重置请求计数
        
        Args:
            client_id: 客户端标识，如果为 None 则重置所有
        """
        with self._lock:
            if client_id is None:
                self._requests.clear()
            elif client_id in self._requests:
                del self._requests[client_id]


# 全局速率限制器实例
_rate_limiter: Optional[RateLimiter] = None
_rate_limiter_lock = Lock()


def get_rate_limiter(
    per_minute: int = 60,
    per_hour: int = 1000,
    per_day: int = 10000,
    force_new: bool = False,
) -> RateLimiter:
    """获取全局速率限制器实例
    
    Args:
        per_minute: 每分钟最大请求数
        per_hour: 每小时最大请求数
        per_day: 每天最大请求数
        force_new: 是否强制创建新实例
    
    Returns:
        RateLimiter 实例
    """
    global _rate_limiter
    
    with _rate_limiter_lock:
        if _rate_limiter is None or force_new:
            _rate_limiter = RateLimiter(
                per_minute=per_minute,
                per_hour=per_hour,
                per_day=per_day,
            )
        return _rate_limiter


def check_rate_limit(client_id: str = "default") -> tuple[bool, Optional[str]]:
    """检查请求是否被速率限制
    
    Args:
        client_id: 客户端标识
    
    Returns:
        (是否允许, 错误消息)
    """
    limiter = get_rate_limiter()
    return limiter.is_allowed(client_id)


def update_rate_limiter_settings(
    per_minute: int,
    per_hour: int,
    per_day: int,
) -> None:
    """更新速率限制器设置
    
    Args:
        per_minute: 每分钟最大请求数
        per_hour: 每小时最大请求数
        per_day: 每天最大请求数
    """
    get_rate_limiter(
        per_minute=per_minute,
        per_hour=per_hour,
        per_day=per_day,
        force_new=True,
    )


# 全局配置
_rate_limit_config: Optional[RateLimitConfig] = None


def init_limiter(config: RateLimitConfig) -> None:
    """初始化速率限制器
    
    Args:
        config: 速率限制配置
    """
    global _rate_limit_config
    _rate_limit_config = config
    
    if config.enabled:
        get_rate_limiter(
            per_minute=config.requests_per_minute,
            per_hour=config.requests_per_hour,
            per_day=config.requests_per_day,
            force_new=True,
        )


def create_rate_limit_middleware():
    """创建速率限制中间件
    
    Returns:
        中间件函数
    """
    from fastapi import Request, Response
    from fastapi.responses import JSONResponse
    
    async def rate_limit_middleware(request: Request, call_next):
        # 检查是否启用速率限制
        if _rate_limit_config is None or not _rate_limit_config.enabled:
            return await call_next(request)
        
        # 获取客户端标识（优先使用 API Key，其次使用 IP）
        client_id = request.headers.get("Authorization", "")
        if client_id:
            # 使用 API Key 的前 20 个字符作为标识
            client_id = client_id[:20]
        else:
            # 使用客户端 IP
            client_id = request.client.host if request.client else "unknown"
        
        # 检查速率限制
        allowed, error_msg = check_rate_limit(client_id)
        
        if not allowed:
            return JSONResponse(
                status_code=429,
                content={
                    "error": {
                        "message": error_msg,
                        "type": "rate_limit_error",
                        "code": "rate_limit_exceeded"
                    }
                }
            )
        
        return await call_next(request)
    
    return rate_limit_middleware
