"""SQLite 친화 Chainlit Data Layer.

기본 SQLAlchemyDataLayer는 Postgres 배열(tags 등)을 리스트로 바인딩하는데,
SQLite(aiosqlite) 드라이버는 list/dict 파라미터를 바인딩하지 못한다.
execute_sql을 감싸 list/dict 파라미터를 JSON 문자열로 직렬화한다.
"""
import json
from typing import Any

from chainlit.data.sql_alchemy import SQLAlchemyDataLayer


class SQLiteDataLayer(SQLAlchemyDataLayer):
    async def execute_sql(self, query: str, parameters: dict) -> Any:
        safe_params = {
            key: (json.dumps(value) if isinstance(value, (list, dict)) else value)
            for key, value in parameters.items()
        }
        return await super().execute_sql(query=query, parameters=safe_params)
