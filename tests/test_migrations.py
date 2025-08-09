"""
Test module for database migration functionality

Phase 3.2: Migration Scripts - TDD実装

🔴 Red Phase: 包括的なマイグレーションテストを先行作成
- MigrationManagerクラス機能
- マイグレーション実行・ロールバック機能
- バージョン管理機能
- agent_memoryテーブル作成スクリプト
- インデックス作成・最適化
- database.py統合
- Fail-Fast エラーハンドリング

テスト設計:
1. MigrationManagerクラステスト
2. マイグレーション実行テスト
3. ロールバック機能テスト
4. バージョン管理テスト
5. スキーマ作成テスト
6. インデックス作成テスト
7. database.py統合テスト
8. エラーハンドリングテスト
"""
import pytest
import asyncio
import asyncpg
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from pathlib import Path
import tempfile
import os
from typing import List, Dict, Any
from app.core.settings import get_settings, reset_settings


class TestMigrationManagerInstantiation:
    """MigrationManagerクラスのインスタンス化テスト"""
    
    def test_migration_manager_creation(self):
        """MigrationManager正常作成テスト"""
        from app.core.migrations import MigrationManager
        
        settings = get_settings()
        migration_manager = MigrationManager(settings)
        
        assert migration_manager is not None
        assert migration_manager.settings == settings
        assert migration_manager.migrations_dir is not None
        assert migration_manager.db_manager is not None
        
    def test_migration_manager_with_custom_dir(self):
        """カスタムマイグレーションディレクトリ指定テスト"""
        from app.core.migrations import MigrationManager
        
        settings = get_settings()
        custom_dir = Path("/custom/migrations")
        
        migration_manager = MigrationManager(settings, migrations_dir=custom_dir)
        
        assert migration_manager.migrations_dir == custom_dir
        
    def test_migration_manager_invalid_directory(self):
        """存在しないディレクトリ指定時のテスト"""
        from app.core.migrations import MigrationManager
        
        settings = get_settings()
        invalid_dir = Path("/nonexistent/migrations")
        
        # 存在しないディレクトリでも作成は可能（実行時にエラーチェック）
        migration_manager = MigrationManager(settings, migrations_dir=invalid_dir)
        assert migration_manager is not None


class TestMigrationVersionManagement:
    """マイグレーションバージョン管理テスト"""
    
    @pytest.mark.asyncio
    async def test_migration_table_creation(self):
        """マイグレーション管理テーブル作成テスト"""
        from app.core.migrations import MigrationManager
        
        settings = get_settings()
        migration_manager = MigrationManager(settings)
        
        # データベースマネージャーのモック
        mock_db_manager = AsyncMock()
        migration_manager.db_manager = mock_db_manager
        
        await migration_manager.ensure_migration_table()
        
        # マイグレーション管理テーブル作成SQLが実行されることを確認
        mock_db_manager.execute.assert_called()
        call_args = mock_db_manager.execute.call_args[0][0]
        assert "CREATE TABLE" in call_args
        assert "schema_migrations" in call_args
        assert "version" in call_args
        assert "applied_at" in call_args
        
    @pytest.mark.asyncio
    async def test_get_applied_migrations(self):
        """適用済みマイグレーション取得テスト"""
        from app.core.migrations import MigrationManager
        
        settings = get_settings()
        migration_manager = MigrationManager(settings)
        
        # モックの適用済みマイグレーション
        mock_migrations = [
            {"version": "001_create_agent_memory", "applied_at": "2025-08-09"},
            {"version": "002_add_indexes", "applied_at": "2025-08-09"}
        ]
        
        mock_db_manager = AsyncMock()
        mock_db_manager.fetch.return_value = mock_migrations
        migration_manager.db_manager = mock_db_manager
        
        result = await migration_manager.get_applied_migrations()
        
        assert len(result) == 2
        assert result[0]["version"] == "001_create_agent_memory"
        assert result[1]["version"] == "002_add_indexes"
        
    @pytest.mark.asyncio
    async def test_is_migration_applied(self):
        """マイグレーション適用状態確認テスト"""
        from app.core.migrations import MigrationManager
        
        settings = get_settings()
        migration_manager = MigrationManager(settings)
        
        # モック：マイグレーションが適用済み
        mock_db_manager = AsyncMock()
        mock_db_manager.fetchval.return_value = 1
        migration_manager.db_manager = mock_db_manager
        
        result = await migration_manager.is_migration_applied("001_create_agent_memory")
        
        assert result is True
        
        # 未適用の場合
        mock_db_manager.fetchval.return_value = 0
        result = await migration_manager.is_migration_applied("999_not_applied")
        
        assert result is False
        
    @pytest.mark.asyncio
    async def test_record_migration(self):
        """マイグレーション記録テスト"""
        from app.core.migrations import MigrationManager
        
        settings = get_settings()
        migration_manager = MigrationManager(settings)
        
        mock_db_manager = AsyncMock()
        migration_manager.db_manager = mock_db_manager
        
        await migration_manager.record_migration("001_create_agent_memory")
        
        # マイグレーション記録のINSERT文が実行されることを確認
        mock_db_manager.execute.assert_called()
        call_args = mock_db_manager.execute.call_args[0]
        assert "INSERT INTO schema_migrations" in call_args[0]
        assert "001_create_agent_memory" == call_args[1]


class TestMigrationDiscovery:
    """マイグレーションファイル発見・読み込みテスト"""
    
    def test_discover_migration_files(self):
        """マイグレーションファイル発見テスト"""
        from app.core.migrations import MigrationManager
        
        settings = get_settings()
        
        # 一時的なマイグレーションディレクトリを作成
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            migration_manager = MigrationManager(settings, migrations_dir=temp_path)
            
            # テスト用マイグレーションファイル作成
            (temp_path / "001_create_agent_memory.py").write_text("# migration file")
            (temp_path / "002_add_indexes.py").write_text("# migration file")
            (temp_path / "invalid_file.txt").write_text("# not a migration")
            
            migrations = migration_manager.discover_migration_files()
            
            assert len(migrations) == 2
            assert any("001_create_agent_memory" in str(m) for m in migrations)
            assert any("002_add_indexes" in str(m) for m in migrations)
            
    def test_get_migration_name_from_file(self):
        """ファイルからマイグレーション名取得テスト"""
        from app.core.migrations import MigrationManager
        
        settings = get_settings()
        migration_manager = MigrationManager(settings)
        
        test_path = Path("/migrations/001_create_agent_memory.py")
        name = migration_manager.get_migration_name_from_file(test_path)
        
        assert name == "001_create_agent_memory"
        
    def test_load_migration_module(self):
        """マイグレーションモジュール読み込みテスト"""
        from app.core.migrations import MigrationManager
        
        settings = get_settings()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            migration_manager = MigrationManager(settings, migrations_dir=temp_path)
            
            # テスト用マイグレーションファイル作成
            migration_content = '''
async def up(db_manager):
    """マイグレーション実行"""
    await db_manager.execute("CREATE TABLE test (id SERIAL)")

async def down(db_manager):
    """マイグレーション取り消し"""
    await db_manager.execute("DROP TABLE test")
'''
            migration_file = temp_path / "001_test_migration.py"
            migration_file.write_text(migration_content)
            
            module = migration_manager.load_migration_module(migration_file)
            
            assert hasattr(module, 'up')
            assert hasattr(module, 'down')
            assert callable(module.up)
            assert callable(module.down)


class TestMigrationExecution:
    """マイグレーション実行テスト"""
    
    @pytest.mark.asyncio
    async def test_run_migration_up(self):
        """マイグレーション実行（up）テスト"""
        from app.core.migrations import MigrationManager
        
        settings = get_settings()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            migration_manager = MigrationManager(settings, migrations_dir=temp_path)
            
            # モックデータベースマネージャー
            mock_db_manager = AsyncMock()
            migration_manager.db_manager = mock_db_manager
            
            # テスト用マイグレーション作成
            migration_content = '''
async def up(db_manager):
    await db_manager.execute("CREATE TABLE agent_memory (id UUID PRIMARY KEY)")

async def down(db_manager):
    await db_manager.execute("DROP TABLE agent_memory")
'''
            migration_file = temp_path / "001_create_agent_memory.py"
            migration_file.write_text(migration_content)
            
            await migration_manager.run_migration(migration_file, direction="up")
            
            # CREATE TABLE文が実行されることを確認
            mock_db_manager.execute.assert_called()
            call_args_list = [call[0][0] for call in mock_db_manager.execute.call_args_list]
            create_table_called = any("CREATE TABLE agent_memory" in sql for sql in call_args_list)
            assert create_table_called
            
    @pytest.mark.asyncio
    async def test_run_migration_down(self):
        """マイグレーション取り消し（down）テスト"""
        from app.core.migrations import MigrationManager
        
        settings = get_settings()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            migration_manager = MigrationManager(settings, migrations_dir=temp_path)
            
            mock_db_manager = AsyncMock()
            migration_manager.db_manager = mock_db_manager
            
            migration_content = '''
async def up(db_manager):
    await db_manager.execute("CREATE TABLE agent_memory (id UUID PRIMARY KEY)")

async def down(db_manager):
    await db_manager.execute("DROP TABLE agent_memory")
'''
            migration_file = temp_path / "001_create_agent_memory.py"
            migration_file.write_text(migration_content)
            
            await migration_manager.run_migration(migration_file, direction="down")
            
            # DROP TABLE文が実行されることを確認
            mock_db_manager.execute.assert_called()
            call_args_list = [call[0][0] for call in mock_db_manager.execute.call_args_list]
            drop_table_called = any("DROP TABLE agent_memory" in sql for sql in call_args_list)
            assert drop_table_called
            
    @pytest.mark.asyncio
    async def test_apply_all_migrations(self):
        """全マイグレーション適用テスト"""
        from app.core.migrations import MigrationManager
        
        settings = get_settings()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            migration_manager = MigrationManager(settings, migrations_dir=temp_path)
            
            mock_db_manager = AsyncMock()
            mock_db_manager.fetchval.return_value = 0  # 未適用
            migration_manager.db_manager = mock_db_manager
            
            # 複数のマイグレーションファイル作成
            for i in range(1, 4):
                content = f'''
async def up(db_manager):
    await db_manager.execute("CREATE TABLE test_{i} (id SERIAL)")

async def down(db_manager):
    await db_manager.execute("DROP TABLE test_{i}")
'''
                (temp_path / f"00{i}_test_migration_{i}.py").write_text(content)
                
            await migration_manager.apply_all_migrations()
            
            # すべてのマイグレーションが実行されることを確認
            assert mock_db_manager.execute.call_count >= 3
            
    @pytest.mark.asyncio
    async def test_rollback_migration(self):
        """マイグレーションロールバックテスト"""
        from app.core.migrations import MigrationManager
        
        settings = get_settings()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            migration_manager = MigrationManager(settings, migrations_dir=temp_path)
            
            mock_db_manager = AsyncMock()
            mock_db_manager.fetchval.return_value = 1  # 適用済み
            migration_manager.db_manager = mock_db_manager
            
            migration_content = '''
async def up(db_manager):
    await db_manager.execute("CREATE TABLE agent_memory (id UUID PRIMARY KEY)")

async def down(db_manager):
    await db_manager.execute("DROP TABLE agent_memory")
'''
            migration_file = temp_path / "001_create_agent_memory.py"
            migration_file.write_text(migration_content)
            
            await migration_manager.rollback_migration("001_create_agent_memory")
            
            # ロールバック処理が実行されることを確認
            mock_db_manager.execute.assert_called()


class TestAgentMemoryMigration:
    """agent_memoryテーブル作成マイグレーションテスト"""
    
    @pytest.mark.asyncio
    async def test_agent_memory_table_creation(self):
        """agent_memoryテーブル作成テスト"""
        from app.core.migrations.scripts import create_agent_memory_migration
        
        mock_db_manager = AsyncMock()
        
        # マイグレーションスクリプトの実行
        await create_agent_memory_migration.up(mock_db_manager)
        
        # CREATE TABLE文の実行確認
        mock_db_manager.execute.assert_called()
        call_args_list = [call[0][0] for call in mock_db_manager.execute.call_args_list]
        
        # テーブル作成文を確認
        table_creation = any("CREATE TABLE agent_memory" in sql for sql in call_args_list)
        assert table_creation
        
        # pgvector拡張の確認
        vector_extension = any("CREATE EXTENSION IF NOT EXISTS vector" in sql for sql in call_args_list)
        assert vector_extension
        
        # カラム定義の確認
        has_required_columns = any(all(col in sql for col in [
            "id UUID PRIMARY KEY DEFAULT gen_random_uuid()",
            "content TEXT NOT NULL",
            "embedding vector(1536)",
            "metadata JSONB",
            "created_at TIMESTAMPTZ DEFAULT NOW()"
        ]) for sql in call_args_list)
        assert has_required_columns
        
    @pytest.mark.asyncio
    async def test_agent_memory_indexes_creation(self):
        """agent_memoryインデックス作成テスト"""
        from app.core.migrations.scripts import create_agent_memory_migration
        
        mock_db_manager = AsyncMock()
        
        await create_agent_memory_migration.up(mock_db_manager)
        
        call_args_list = [call[0][0] for call in mock_db_manager.execute.call_args_list]
        
        # ベクトル検索インデックス
        vector_index = any("CREATE INDEX" in sql and "ivfflat" in sql and "vector_cosine_ops" in sql for sql in call_args_list)
        assert vector_index
        
        # メタデータ検索インデックス
        metadata_index = any("CREATE INDEX" in sql and "gin (metadata)" in sql for sql in call_args_list)
        assert metadata_index
        
        # 時系列インデックス
        time_index = any("CREATE INDEX" in sql and "created_at DESC" in sql for sql in call_args_list)
        assert time_index
        
    @pytest.mark.asyncio
    async def test_agent_memory_migration_rollback(self):
        """agent_memoryマイグレーションロールバックテスト"""
        from app.core.migrations.scripts import create_agent_memory_migration
        
        mock_db_manager = AsyncMock()
        
        await create_agent_memory_migration.down(mock_db_manager)
        
        # テーブル削除文の実行確認
        mock_db_manager.execute.assert_called()
        call_args = mock_db_manager.execute.call_args[0][0]
        assert "DROP TABLE" in call_args
        assert "agent_memory" in call_args


class TestMigrationErrorHandling:
    """マイグレーションエラーハンドリング・Fail-Fastテスト"""
    
    @pytest.mark.asyncio
    async def test_migration_file_not_found_error(self):
        """マイグレーションファイル未発見エラーテスト"""
        from app.core.migrations import MigrationManager, MigrationError
        
        settings = get_settings()
        migration_manager = MigrationManager(settings)
        
        with pytest.raises(MigrationError) as exc_info:
            await migration_manager.run_migration(Path("/nonexistent/migration.py"))
        
        assert "Migration file not found" in str(exc_info.value)
        
    @pytest.mark.asyncio
    async def test_migration_execution_error(self):
        """マイグレーション実行エラーテスト"""
        from app.core.migrations import MigrationManager, MigrationError
        
        settings = get_settings()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            migration_manager = MigrationManager(settings, migrations_dir=temp_path)
            
            mock_db_manager = AsyncMock()
            mock_db_manager.execute.side_effect = Exception("SQL Error")
            migration_manager.db_manager = mock_db_manager
            
            # エラーを含むマイグレーション作成
            error_migration = '''
async def up(db_manager):
    await db_manager.execute("INVALID SQL STATEMENT")

async def down(db_manager):
    pass
'''
            migration_file = temp_path / "001_error_migration.py"
            migration_file.write_text(error_migration)
            
            with pytest.raises(MigrationError) as exc_info:
                await migration_manager.run_migration(migration_file)
            
            assert "Migration execution failed" in str(exc_info.value)
            
    @pytest.mark.asyncio
    async def test_invalid_migration_format_error(self):
        """不正なマイグレーションフォーマットエラーテスト"""
        from app.core.migrations import MigrationManager, MigrationError
        
        settings = get_settings()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            migration_manager = MigrationManager(settings, migrations_dir=temp_path)
            
            # up関数が存在しないマイグレーション
            invalid_migration = '''
# No up function defined

async def down(db_manager):
    pass
'''
            migration_file = temp_path / "001_invalid_migration.py"
            migration_file.write_text(invalid_migration)
            
            with pytest.raises(MigrationError) as exc_info:
                await migration_manager.run_migration(migration_file)
            
            assert "Invalid migration format" in str(exc_info.value) or "has no attribute 'up'" in str(exc_info.value)


class TestIntegrationWithDatabase:
    """database.py統合テスト"""
    
    @pytest.mark.asyncio
    async def test_migration_with_real_database_manager(self):
        """実際のDatabaseManagerとの統合テスト"""
        from app.core.migrations import MigrationManager
        from app.core.database import DatabaseManager
        
        with patch.dict(os.environ, {"DATABASE_URL": "postgresql://test:pass@localhost:5432/test_db"}):
            reset_settings()
            settings = get_settings()
            
            db_manager = DatabaseManager(settings)
            migration_manager = MigrationManager(settings)
            migration_manager.db_manager = db_manager
            
            # データベースマネージャーが正しく統合されることを確認
            assert migration_manager.db_manager is db_manager
            
    @pytest.mark.asyncio
    async def test_migration_manager_factory_function(self):
        """MigrationManagerファクトリー関数テスト"""
        from app.core.migrations import get_migration_manager
        
        with patch.dict(os.environ, {"DATABASE_URL": "postgresql://test:pass@localhost:5432/test_db"}):
            reset_settings()
            
            manager1 = get_migration_manager()
            manager2 = get_migration_manager()
            
            # シングルトンパターンの確認
            assert manager1 is manager2
            
    def test_migration_logging(self):
        """マイグレーションログ出力テスト"""
        from app.core.migrations import MigrationManager
        
        settings = get_settings()
        migration_manager = MigrationManager(settings)
        
        # ログ出力設定の確認
        import logging
        logger = logging.getLogger('app.core.migrations')
        assert logger is not None


class TestMigrationUtilities:
    """マイグレーションユーティリティ関数テスト"""
    
    def test_validate_migration_name(self):
        """マイグレーション名検証テスト"""
        from app.core.migrations import validate_migration_name
        
        # 有効な名前
        assert validate_migration_name("001_create_agent_memory")
        assert validate_migration_name("002_add_indexes")
        assert validate_migration_name("010_update_schema")
        
        # 無効な名前
        assert not validate_migration_name("invalid_name")
        assert not validate_migration_name("001")
        assert not validate_migration_name("create_table")
        assert not validate_migration_name("")
        
    def test_generate_migration_filename(self):
        """マイグレーションファイル名生成テスト"""
        from app.core.migrations import generate_migration_filename
        
        filename = generate_migration_filename("create_agent_memory")
        
        # パターン確認: XXX_create_agent_memory.py
        assert filename.endswith("_create_agent_memory.py")
        assert len(filename.split("_")[0]) == 3  # 3桁の番号
        assert filename.split("_")[0].isdigit()
        
    def test_parse_migration_version(self):
        """マイグレーションバージョン解析テスト"""
        from app.core.migrations import parse_migration_version
        
        version = parse_migration_version("001_create_agent_memory")
        assert version == "001"
        
        version = parse_migration_version("042_add_new_feature")
        assert version == "042"
        
        # 無効なフォーマット
        with pytest.raises(ValueError):
            parse_migration_version("invalid_format")