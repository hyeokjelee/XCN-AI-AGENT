"""마스터 에이전트 싱글톤.

기존 main_agent.master_agent.init_master_agent(db_conn)를 그대로 재사용한다.
체크포인터는 SQLite(AsyncSqliteSaver)를 사용하며, 최초 1회만 초기화한다.
"""
import asyncio

import aiosqlite

from database import CHECKPOINT_DB_PATH
from main_agent.master_agent import init_master_agent

_agent = None
_db_conn = None
_lock = asyncio.Lock()


async def get_master_agent():
    """마스터 에이전트(싱글톤)를 반환한다. 최초 호출 시 초기화."""
    global _agent, _db_conn
    if _agent is not None:
        return _agent
    async with _lock:
        if _agent is None:
            _db_conn = await aiosqlite.connect(CHECKPOINT_DB_PATH)
            _agent = await init_master_agent(_db_conn)
    return _agent


async def shutdown() -> None:
    global _agent, _db_conn
    if _db_conn is not None:
        await _db_conn.close()
        _db_conn = None
    _agent = None
