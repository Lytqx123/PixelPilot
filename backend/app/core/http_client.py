# 全局共享httpx客户端，复用连接池，启动时创建关闭时释放
import httpx

# 全局共享的 httpx 异步客户端
# 在应用启动时创建(lifespan),关闭时释放
_shared_client: httpx.AsyncClient | None = None


async def init_shared_client() -> None:
    """初始化共享 httpx 客户端(在应用 lifespan 启动时调用)"""
    global _shared_client
    if _shared_client is None or _shared_client.is_closed:
        _shared_client = httpx.AsyncClient(
            timeout=httpx.Timeout(60.0, connect=10.0),
            limits=httpx.Limits(max_connections=50, max_keepalive_connections=20),
        )


async def close_shared_client() -> None:
    """关闭共享 httpx 客户端(在应用 lifespan 关闭时调用)"""
    global _shared_client
    if _shared_client is not None and not _shared_client.is_closed:
        await _shared_client.aclose()
    _shared_client = None


def get_shared_client() -> httpx.AsyncClient:
    """
    获取共享 httpx 客户端实例

    如果客户端未初始化(如单元测试中),则返回一个临时客户端。
    """
    global _shared_client
    if _shared_client is None or _shared_client.is_closed:
        _shared_client = httpx.AsyncClient(
            timeout=httpx.Timeout(60.0, connect=10.0),
            limits=httpx.Limits(max_connections=50, max_keepalive_connections=20),
        )
    return _shared_client
