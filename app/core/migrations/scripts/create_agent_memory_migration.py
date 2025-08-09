"""
Agent Memory Migration Script

Phase 3.2: Migration Scripts - agent_memory テーブル作成

このマイグレーションスクリプトは以下を実装:
- pgvector拡張の有効化
- agent_memoryテーブル作成
- 必要なインデックス作成（ベクトル検索・メタデータ・時系列）
- ロールバック機能

テーブル仕様:
- id: UUID primary key with gen_random_uuid()
- content: TEXT NOT NULL
- embedding: vector(1536) for gemini-embedding-001
- metadata: JSONB for flexible metadata
- created_at: TIMESTAMPTZ with NOW() default

インデックス仕様:
- ベクトル類似度検索: IVFFlat + コサイン距離
- メタデータ検索: GIN
- 時系列検索: B-tree (DESC)
"""
import logging

logger = logging.getLogger(__name__)


async def up(db_manager):
    """
    agent_memoryテーブル作成マイグレーション
    
    Args:
        db_manager: DatabaseManager インスタンス
    """
    logger.info("Creating agent_memory table with pgvector support")
    
    # Step 1: pgvector拡張の有効化
    await db_manager.execute("CREATE EXTENSION IF NOT EXISTS vector")
    logger.info("pgvector extension enabled")
    
    # Step 2: agent_memoryテーブル作成
    create_table_sql = """
    CREATE TABLE agent_memory (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        content TEXT NOT NULL,
        embedding vector(1536),
        metadata JSONB,
        created_at TIMESTAMPTZ DEFAULT NOW()
    )
    """
    await db_manager.execute(create_table_sql)
    logger.info("agent_memory table created")
    
    # Step 3: ベクトル検索用インデックス（IVFFlat + コサイン類似度）
    create_vector_index_sql = """
    CREATE INDEX idx_agent_memory_embedding 
        ON agent_memory 
        USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100)
    """
    await db_manager.execute(create_vector_index_sql)
    logger.info("Vector similarity index created")
    
    # Step 4: メタデータ検索用GINインデックス
    create_metadata_index_sql = """
    CREATE INDEX idx_agent_memory_metadata 
        ON agent_memory 
        USING gin (metadata)
    """
    await db_manager.execute(create_metadata_index_sql)
    logger.info("Metadata GIN index created")
    
    # Step 5: 時系列検索用インデックス
    create_time_index_sql = """
    CREATE INDEX idx_agent_memory_created_at 
        ON agent_memory (created_at DESC)
    """
    await db_manager.execute(create_time_index_sql)
    logger.info("Time-series index created")
    
    logger.info("agent_memory migration completed successfully")


async def down(db_manager):
    """
    agent_memoryテーブル削除マイグレーション（ロールバック）
    
    Args:
        db_manager: DatabaseManager インスタンス
    """
    logger.info("Rolling back agent_memory table creation")
    
    # テーブル削除（インデックスも自動削除される）
    await db_manager.execute("DROP TABLE IF EXISTS agent_memory")
    logger.info("agent_memory table dropped")
    
    logger.info("agent_memory migration rollback completed")