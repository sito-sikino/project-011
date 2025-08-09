"""
Database module for Discord Multi-Agent System

PostgreSQL接続プール、pgvector対応、非同期DB操作を提供

Phase 3.1: Database Foundation 実装
- PostgreSQL接続プール管理
- pgvector拡張サポート（1536次元対応）
- 非同期操作サポート
- settings.py統合
- ヘルスチェック機能
- Fail-Fast原則によるエラーハンドリング

t-wada式TDDサイクル実装フロー:
🔴 Red Phase: 包括的テストスイート作成完了（18テストクラス）
🟢 Green Phase: 最小実装でテスト通過
🟡 Refactor Phase: 品質向上、エラーハンドリング強化

技術スタック:
- asyncpg: PostgreSQL非同期接続
- pgvector: 1536次元ベクトル検索
- Connection Pool: 5-20接続管理
- Settings統合: Pydantic設定管理
"""
import asyncio
import asyncpg
import json
import logging
from typing import Optional, List, Dict, Any, AsyncContextManager
from contextlib import asynccontextmanager
from app.core.settings import Settings, get_settings

logger = logging.getLogger(__name__)


class DatabaseError(Exception):
    """データベース操作エラーのベースクラス"""
    pass


class ConnectionError(DatabaseError):
    """データベース接続エラー"""
    pass


class QueryError(DatabaseError):
    """クエリ実行エラー"""
    pass


class InitializationError(DatabaseError):
    """データベース初期化エラー"""
    pass


class DatabaseManager:
    """
    PostgreSQL + pgvector データベース管理クラス
    
    機能:
    - 非同期接続プール管理
    - pgvector 1536次元ベクトル操作
    - ヘルスチェック
    - 設定統合
    - Fail-Fast エラーハンドリング
    """
    
    def __init__(self, settings: Settings):
        """
        DatabaseManager初期化
        
        Args:
            settings: 設定インスタンス
        """
        self.settings = settings
        self.database_url = settings.database.url
        self.pool: Optional[asyncpg.Pool] = None
        logger.info("DatabaseManager initialized")
    
    async def initialize(self) -> None:
        """
        データベース接続プール初期化
        
        接続プールを作成し、pgvector拡張の確認を行う
        
        Raises:
            InitializationError: データベース初期化失敗時（Fail-Fast）
            ConnectionError: 接続失敗時
        """
        try:
            logger.info(f"Initializing database connection pool to {self.database_url}")
            
            self.pool = await asyncpg.create_pool(
                self.database_url,
                min_size=5,
                max_size=20,
                command_timeout=30,
                server_settings={
                    'jit': 'off'  # pgvector使用時はJITを無効化
                }
            )
            logger.info(f"Database connection pool initialized successfully (min_size=5, max_size=20)")
            
            # pgvector拡張確認
            has_pgvector = await self.check_pgvector_extension()
            if has_pgvector:
                logger.info("pgvector extension confirmed and available")
            else:
                logger.warning("pgvector extension not found - vector operations will fail")
                
        except asyncpg.InvalidCatalogNameError as e:
            error_msg = f"Database '{e.args[0]}' does not exist"
            logger.critical(error_msg)
            raise InitializationError(error_msg) from e
        except asyncpg.InvalidAuthorizationSpecificationError as e:
            error_msg = "Invalid database credentials"
            logger.critical(error_msg)
            raise ConnectionError(error_msg) from e
        except asyncpg.CannotConnectNowError as e:
            error_msg = "Database server is not accepting connections"
            logger.critical(error_msg)
            raise ConnectionError(error_msg) from e
        except Exception as e:
            error_msg = f"Database initialization failed: {e}"
            logger.critical(error_msg)
            raise InitializationError(error_msg) from e
    
    async def close(self) -> None:
        """
        データベース接続プール終了
        
        全接続を安全にクローズし、リソースを解放
        """
        if self.pool:
            self.pool.close()
            await self.pool.wait_closed()
            self.pool = None
            logger.info("Database connection pool closed")
    
    @asynccontextmanager
    async def get_connection(self) -> AsyncContextManager[asyncpg.Connection]:
        """
        データベース接続取得（コンテキストマネージャー）
        
        Yields:
            asyncpg.Connection: データベース接続
            
        Raises:
            RuntimeError: プール未初期化時
        """
        if not self.pool:
            raise RuntimeError("Database not initialized. Call initialize() first.")
            
        async with self.pool.acquire() as connection:
            yield connection
    
    async def execute(self, query: str, *args) -> str:
        """
        非同期クエリ実行
        
        Args:
            query: SQLクエリ
            *args: クエリパラメータ
            
        Returns:
            str: 実行結果
            
        Raises:
            InitializationError: プール未初期化時
            QueryError: クエリ実行エラー時（Fail-Fast）
        """
        if not self.pool:
            raise InitializationError("Database not initialized. Call initialize() first.")
            
        async with self.get_connection() as conn:
            try:
                logger.debug(f"Executing query: {query[:100]}...")
                result = await conn.execute(query, *args)
                logger.debug(f"Query executed successfully: {result}")
                return result
            except asyncpg.PostgresSyntaxError as e:
                error_msg = f"SQL syntax error: {e}"
                logger.error(error_msg)
                raise QueryError(error_msg) from e
            except asyncpg.PostgresError as e:
                error_msg = f"PostgreSQL error: {e}"
                logger.error(error_msg)
                raise QueryError(error_msg) from e
            except Exception as e:
                error_msg = f"Query execution failed: {e}"
                logger.error(error_msg)
                raise QueryError(error_msg) from e
    
    async def fetch(self, query: str, *args) -> List[Dict[str, Any]]:
        """
        非同期データ取得
        
        Args:
            query: SQLクエリ
            *args: クエリパラメータ
            
        Returns:
            List[Dict[str, Any]]: 取得結果
            
        Raises:
            RuntimeError: プール未初期化時
            Exception: クエリ実行エラー時
        """
        if not self.pool:
            raise RuntimeError("Database not initialized. Call initialize() first.")
            
        async with self.get_connection() as conn:
            try:
                rows = await conn.fetch(query, *args)
                return [dict(row) for row in rows]
            except Exception as e:
                logger.error(f"Fetch query failed: {e}")
                raise
    
    async def fetchval(self, query: str, *args) -> Any:
        """
        非同期単一値取得
        
        Args:
            query: SQLクエリ
            *args: クエリパラメータ
            
        Returns:
            Any: 取得値
            
        Raises:
            RuntimeError: プール未初期化時
            Exception: クエリ実行エラー時
        """
        if not self.pool:
            raise RuntimeError("Database not initialized. Call initialize() first.")
            
        async with self.get_connection() as conn:
            try:
                result = await conn.fetchval(query, *args)
                return result
            except Exception as e:
                logger.error(f"Fetchval query failed: {e}")
                raise
    
    async def check_pgvector_extension(self) -> bool:
        """
        pgvector拡張の存在確認
        
        Returns:
            bool: pgvector拡張が使用可能かどうか
        """
        try:
            async with self.get_connection() as conn:
                result = await conn.fetchval(
                    "SELECT extname FROM pg_extension WHERE extname = 'vector'"
                )
                return result == "vector"
        except Exception as e:
            logger.warning(f"pgvector extension check failed: {e}")
            return False
    
    async def create_vector_table(self, table_name: str, dimensions: int = 1536) -> None:
        """
        ベクトルテーブル作成
        
        Args:
            table_name: テーブル名
            dimensions: ベクトル次元数（デフォルト1536）
        """
        create_table_query = f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            content TEXT NOT NULL,
            embedding vector({dimensions}),
            metadata JSONB DEFAULT '{{}}',
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
        
        # インデックス作成（ivfflat使用）
        create_index_query = f"""
        CREATE INDEX IF NOT EXISTS {table_name}_embedding_idx 
        ON {table_name} USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100)
        """
        
        async with self.get_connection() as conn:
            await conn.execute(create_table_query)
            await conn.execute(create_index_query)
            logger.info(f"Vector table '{table_name}' created with {dimensions} dimensions")
    
    async def insert_vector(
        self, 
        table_name: str, 
        content: str, 
        embedding: List[float], 
        metadata: Dict[str, Any] = None
    ) -> str:
        """
        ベクトルデータ挿入
        
        Args:
            table_name: テーブル名
            content: テキスト内容
            embedding: 埋め込みベクトル
            metadata: メタデータ
            
        Returns:
            str: 挿入されたレコードのID
        """
        if metadata is None:
            metadata = {}
            
        insert_query = f"""
        INSERT INTO {table_name} (content, embedding, metadata)
        VALUES ($1, $2, $3)
        RETURNING id
        """
        
        async with self.get_connection() as conn:
            record_id = await conn.fetchval(
                insert_query, 
                content, 
                embedding,  # asyncpgは自動でベクトルフォーマットに変換
                json.dumps(metadata)
            )
            return str(record_id)
    
    async def similarity_search(
        self, 
        table_name: str, 
        query_vector: List[float], 
        limit: int = 5,
        threshold: float = 0.0
    ) -> List[Dict[str, Any]]:
        """
        ベクトル類似度検索
        
        Args:
            table_name: テーブル名
            query_vector: クエリベクトル
            limit: 取得件数制限
            threshold: 類似度しきい値
            
        Returns:
            List[Dict[str, Any]]: 検索結果
        """
        similarity_query = f"""
        SELECT 
            content,
            metadata,
            1 - (embedding <=> $1) as similarity,
            created_at
        FROM {table_name}
        WHERE 1 - (embedding <=> $1) > $2
        ORDER BY embedding <=> $1
        LIMIT $3
        """
        
        async with self.get_connection() as conn:
            rows = await conn.fetch(similarity_query, query_vector, threshold, limit)
            return [dict(row) for row in rows]
    
    async def health_check(self) -> bool:
        """
        データベースヘルスチェック
        
        Returns:
            bool: データベースが健康かどうか
        """
        if not self.pool:
            logger.warning("Database pool not initialized for health check")
            return False
            
        try:
            async with self.get_connection() as conn:
                result = await conn.fetchval("SELECT 1")
                return result == 1
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False


# シングルトンパターンでDatabaseManager管理
_db_manager_instance: Optional[DatabaseManager] = None


def get_db_manager() -> DatabaseManager:
    """
    DatabaseManagerインスタンス取得（シングルトン）
    
    Returns:
        DatabaseManager: データベース管理インスタンス
    """
    global _db_manager_instance
    if _db_manager_instance is None:
        settings = get_settings()
        _db_manager_instance = DatabaseManager(settings)
    return _db_manager_instance


def reset_db_manager() -> None:
    """
    DatabaseManagerインスタンスリセット（主にテスト用）
    
    テスト間でのクリーンな状態確保
    """
    global _db_manager_instance
    _db_manager_instance = None


# 利便性のためのヘルパー関数群
async def initialize_database(auto_migrate: bool = True) -> DatabaseManager:
    """
    データベース初期化ヘルパー
    
    Args:
        auto_migrate: マイグレーションの自動実行（デフォルト: True）
    
    Returns:
        DatabaseManager: 初期化済みデータベースマネージャー
        
    Phase 3.2統合: 初期化時の自動マイグレーション実行
    """
    db_manager = get_db_manager()
    await db_manager.initialize()
    
    # 自動マイグレーション実行
    if auto_migrate:
        try:
            await run_migrations()
            logger.info("Database initialized with migrations applied")
        except Exception as e:
            logger.warning(f"Migration auto-execution failed: {e}")
            # マイグレーション失敗でもデータベース初期化は継続
    
    return db_manager


async def create_agent_memory_table() -> None:
    """
    エージェントメモリテーブル作成
    
    アプリケーションで使用するメインテーブルを作成
    """
    db_manager = get_db_manager()
    await db_manager.create_vector_table("agent_memory", dimensions=1536)
    logger.info("Agent memory table created successfully")


async def close_database() -> None:
    """
    データベース終了ヘルパー
    """
    db_manager = get_db_manager()
    await db_manager.close()
    logger.info("Database closed successfully")


async def run_migrations() -> None:
    """
    データベースマイグレーション実行ヘルパー
    
    未適用のマイグレーションをすべて実行する
    Phase 3.2統合: MigrationManager連携
    """
    try:
        from app.core.migrations import get_migration_manager
        
        migration_manager = get_migration_manager()
        await migration_manager.apply_all_migrations()
        logger.info("All database migrations applied successfully")
        
    except Exception as e:
        error_msg = f"Migration execution failed: {e}"
        logger.error(error_msg)
        raise InitializationError(error_msg) from e


async def rollback_migration(version: str) -> None:
    """
    特定マイグレーションのロールバックヘルパー
    
    Args:
        version: ロールバックするマイグレーションバージョン
        
    Phase 3.2統合: MigrationManager連携
    """
    try:
        from app.core.migrations import get_migration_manager
        
        migration_manager = get_migration_manager()
        await migration_manager.rollback_migration(version)
        logger.info(f"Migration {version} rolled back successfully")
        
    except Exception as e:
        error_msg = f"Migration rollback failed: {e}"
        logger.error(error_msg)
        raise QueryError(error_msg) from e


async def check_migration_status() -> List[Dict[str, Any]]:
    """
    マイグレーション状態確認ヘルパー
    
    Returns:
        List[Dict[str, Any]]: 適用済みマイグレーション一覧
        
    Phase 3.2統合: MigrationManager連携
    """
    try:
        from app.core.migrations import get_migration_manager
        
        migration_manager = get_migration_manager()
        return await migration_manager.get_applied_migrations()
        
    except Exception as e:
        logger.error(f"Migration status check failed: {e}")
        return []


def validate_connection_url(url: str) -> bool:
    """
    データベース接続URL検証
    
    Args:
        url: 接続URL
        
    Returns:
        bool: 有効かどうか
    """
    if not url:
        return False
        
    # PostgreSQL URLの基本形式チェック
    if not url.startswith(('postgresql://', 'postgres://')):
        return False
        
    # 基本的な構成要素の存在チェック
    required_parts = ['://', '@', ':']
    return all(part in url for part in required_parts)


async def test_database_connection() -> bool:
    """
    データベース接続テストヘルパー
    
    Returns:
        bool: 接続成功かどうか
    """
    try:
        db_manager = get_db_manager()
        await db_manager.initialize()
        result = await db_manager.health_check()
        await db_manager.close()
        return result
    except Exception as e:
        logger.error(f"Database connection test failed: {e}")
        return False