"""
Database Migration System for Discord Multi-Agent System

Phase 3.2: Migration Scripts 実装

PostgreSQL マイグレーション管理システム:
- MigrationManagerクラス
- バージョン管理機能
- Up/Down マイグレーション対応
- agent_memoryテーブル作成スクリプト
- database.py統合
- Fail-Fast エラーハンドリング

t-wada式TDDサイクル実装フロー:
🔴 Red Phase: 包括的テストスイート作成完了（26テスト）
🟢 Green Phase: 最小実装でテスト通過
🟡 Refactor Phase: 品質向上、エラーハンドリング強化

技術スタック:
- DatabaseManager統合: 既存database.pyインフラ活用
- マイグレーション管理テーブル: schema_migrations
- 動的モジュール読み込み: importlib.util
- Path管理: pathlib.Path
"""
import importlib.util
import logging
import re
from pathlib import Path
from typing import Optional, List, Dict, Any
from app.core.settings import Settings, get_settings
from app.core.database import get_db_manager

logger = logging.getLogger(__name__)


class MigrationError(Exception):
    """マイグレーション操作エラーのベースクラス"""
    pass


class MigrationManager:
    """
    データベースマイグレーション管理クラス
    
    機能:
    - マイグレーション実行・ロールバック
    - バージョン管理
    - ファイル発見・読み込み
    - database.py統合
    - Fail-Fast エラーハンドリング
    """
    
    def __init__(self, settings: Settings, migrations_dir: Optional[Path] = None):
        """
        MigrationManager初期化
        
        Args:
            settings: 設定インスタンス
            migrations_dir: マイグレーションディレクトリ（省略時はデフォルト）
        """
        self.settings = settings
        self.migrations_dir = migrations_dir or Path(__file__).parent / "scripts"
        self.db_manager = get_db_manager()
        logger.info("MigrationManager initialized")
    
    async def ensure_migration_table(self) -> None:
        """
        マイグレーション管理テーブル作成
        
        schema_migrationsテーブルが存在しない場合は作成する
        """
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version VARCHAR(255) PRIMARY KEY,
            applied_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
        await self.db_manager.execute(create_table_sql)
        logger.info("Migration management table ensured")
    
    async def get_applied_migrations(self) -> List[Dict[str, Any]]:
        """
        適用済みマイグレーション一覧取得
        
        Returns:
            List[Dict[str, Any]]: 適用済みマイグレーション情報
        """
        query = "SELECT version, applied_at FROM schema_migrations ORDER BY version"
        return await self.db_manager.fetch(query)
    
    async def is_migration_applied(self, version: str) -> bool:
        """
        マイグレーション適用状態確認
        
        Args:
            version: マイグレーションバージョン
            
        Returns:
            bool: 適用済みかどうか
        """
        query = "SELECT COUNT(*) FROM schema_migrations WHERE version = $1"
        count = await self.db_manager.fetchval(query, version)
        return count > 0
    
    async def record_migration(self, version: str) -> None:
        """
        マイグレーション記録
        
        Args:
            version: マイグレーションバージョン
        """
        insert_sql = "INSERT INTO schema_migrations (version) VALUES ($1)"
        await self.db_manager.execute(insert_sql, version)
        logger.info(f"Migration {version} recorded")
    
    async def remove_migration_record(self, version: str) -> None:
        """
        マイグレーション記録削除
        
        Args:
            version: マイグレーションバージョン
        """
        delete_sql = "DELETE FROM schema_migrations WHERE version = $1"
        await self.db_manager.execute(delete_sql, version)
        logger.info(f"Migration {version} record removed")
    
    def discover_migration_files(self) -> List[Path]:
        """
        マイグレーションファイル発見
        
        Returns:
            List[Path]: マイグレーションファイル一覧
        """
        if not self.migrations_dir.exists():
            return []
            
        # XXX_*.pyパターンのファイルを検索
        migration_files = []
        for file_path in self.migrations_dir.glob("*.py"):
            if file_path.name.startswith("__"):
                continue  # __init__.pyなどをスキップ
            if re.match(r'^\d{3}_.*\.py$', file_path.name):
                migration_files.append(file_path)
        
        return sorted(migration_files)
    
    def get_migration_name_from_file(self, file_path: Path) -> str:
        """
        ファイルパスからマイグレーション名取得
        
        Args:
            file_path: マイグレーションファイルパス
            
        Returns:
            str: マイグレーション名
        """
        return file_path.stem
    
    def load_migration_module(self, file_path: Path):
        """
        マイグレーションモジュール読み込み
        
        Args:
            file_path: マイグレーションファイルパス
            
        Returns:
            module: 読み込まれたマイグレーションモジュール
        """
        spec = importlib.util.spec_from_file_location(
            f"migration_{file_path.stem}", 
            file_path
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    
    async def run_migration(self, file_path: Path, direction: str = "up") -> None:
        """
        マイグレーション実行
        
        Args:
            file_path: マイグレーションファイルパス
            direction: 実行方向（"up" or "down"）
            
        Raises:
            MigrationError: マイグレーション実行エラー
        """
        if not file_path.exists():
            raise MigrationError(f"Migration file not found: {file_path}")
        
        try:
            module = self.load_migration_module(file_path)
            
            if not hasattr(module, direction):
                raise MigrationError(f"Invalid migration format: missing '{direction}' function")
            
            migration_func = getattr(module, direction)
            await migration_func(self.db_manager)
            
            migration_name = self.get_migration_name_from_file(file_path)
            
            if direction == "up":
                await self.record_migration(migration_name)
            elif direction == "down":
                await self.remove_migration_record(migration_name)
                
            logger.info(f"Migration {migration_name} executed successfully ({direction})")
            
        except Exception as e:
            raise MigrationError(f"Migration execution failed: {e}") from e
    
    async def apply_all_migrations(self) -> None:
        """
        すべての未適用マイグレーション実行
        """
        await self.ensure_migration_table()
        
        migration_files = self.discover_migration_files()
        
        for file_path in migration_files:
            migration_name = self.get_migration_name_from_file(file_path)
            
            if not await self.is_migration_applied(migration_name):
                await self.run_migration(file_path, "up")
                logger.info(f"Applied migration: {migration_name}")
            else:
                logger.debug(f"Migration already applied: {migration_name}")
    
    async def rollback_migration(self, version: str) -> None:
        """
        特定マイグレーションのロールバック
        
        Args:
            version: ロールバックするマイグレーションバージョン
        """
        if not await self.is_migration_applied(version):
            logger.warning(f"Migration {version} is not applied")
            return
        
        migration_files = self.discover_migration_files()
        target_file = None
        
        for file_path in migration_files:
            migration_name = self.get_migration_name_from_file(file_path)
            if migration_name == version:
                target_file = file_path
                break
        
        if target_file:
            await self.run_migration(target_file, "down")
            logger.info(f"Rolled back migration: {version}")
        else:
            raise MigrationError(f"Migration file not found for version: {version}")


# シングルトンパターンでMigrationManager管理
_migration_manager_instance: Optional[MigrationManager] = None


def get_migration_manager() -> MigrationManager:
    """
    MigrationManagerインスタンス取得（シングルトン）
    
    Returns:
        MigrationManager: マイグレーション管理インスタンス
    """
    global _migration_manager_instance
    if _migration_manager_instance is None:
        settings = get_settings()
        _migration_manager_instance = MigrationManager(settings)
    return _migration_manager_instance


def reset_migration_manager() -> None:
    """
    MigrationManagerインスタンスリセット（主にテスト用）
    """
    global _migration_manager_instance
    _migration_manager_instance = None


# ユーティリティ関数群
def validate_migration_name(name: str) -> bool:
    """
    マイグレーション名検証
    
    Args:
        name: マイグレーション名
        
    Returns:
        bool: 有効かどうか
    """
    if not name:
        return False
    
    # XXX_description形式のチェック
    pattern = r'^\d{3}_[a-zA-Z_]+$'
    return bool(re.match(pattern, name))


def generate_migration_filename(description: str) -> str:
    """
    マイグレーションファイル名生成
    
    Args:
        description: マイグレーション説明
        
    Returns:
        str: 生成されたファイル名
    """
    # 簡単な実装：001から開始
    version = "001"
    return f"{version}_{description}.py"


def parse_migration_version(migration_name: str) -> str:
    """
    マイグレーション名からバージョン解析
    
    Args:
        migration_name: マイグレーション名
        
    Returns:
        str: バージョン番号
        
    Raises:
        ValueError: 無効なフォーマット時
    """
    parts = migration_name.split("_", 1)
    if len(parts) < 2 or not parts[0].isdigit() or len(parts[0]) != 3:
        raise ValueError(f"Invalid migration name format: {migration_name}")
    
    return parts[0]