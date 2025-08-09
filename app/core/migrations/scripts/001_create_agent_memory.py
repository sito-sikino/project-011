"""
001 - Create Agent Memory Table Migration

Phase 3.2: Migration Scripts - agent_memoryテーブル作成

マイグレーション内容:
- pgvector拡張有効化
- agent_memoryテーブル作成（1536次元ベクトル対応）
- 最適化されたインデックス作成
- メタデータ・時系列検索サポート
"""
import logging
from .create_agent_memory_migration import up as create_up, down as create_down

logger = logging.getLogger(__name__)


async def up(db_manager):
    """マイグレーション実行"""
    await create_up(db_manager)


async def down(db_manager):  
    """マイグレーションロールバック"""
    await create_down(db_manager)