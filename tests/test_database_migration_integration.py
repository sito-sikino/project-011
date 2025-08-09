"""
Test module for database and migration system integration

Phase 3.2: Migration Scripts - database.py統合テスト

統合テスト内容:
- database.py migration helper functions
- initialize_database with auto_migrate
- run_migrations() helper
- rollback_migration() helper  
- check_migration_status() helper
- エラーハンドリング統合

t-wada式TDDアプローチ:
🟢 Green Phase: 既存機能の統合検証
"""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from app.core.database import (
    initialize_database, 
    run_migrations, 
    rollback_migration,
    check_migration_status
)
from app.core.settings import get_settings, reset_settings
import os


class TestDatabaseMigrationIntegration:
    """database.pyとmigration systemの統合テスト"""
    
    @pytest.mark.asyncio
    async def test_initialize_database_with_auto_migrate(self):
        """auto_migrate=Trueでのデータベース初期化テスト"""
        with patch.dict(os.environ, {"DATABASE_URL": "postgresql://test:pass@localhost:5432/test_db"}):
            reset_settings()
            
            with patch('app.core.database.get_db_manager') as mock_get_db_manager:
                mock_db_manager = AsyncMock()
                mock_get_db_manager.return_value = mock_db_manager
                
                with patch('app.core.database.run_migrations') as mock_run_migrations:
                    result = await initialize_database(auto_migrate=True)
                    
                    # データベース初期化確認
                    mock_db_manager.initialize.assert_called_once()
                    
                    # マイグレーション実行確認
                    mock_run_migrations.assert_called_once()
                    
                    assert result == mock_db_manager
                    
    @pytest.mark.asyncio
    async def test_initialize_database_without_auto_migrate(self):
        """auto_migrate=Falseでのデータベース初期化テスト"""
        with patch.dict(os.environ, {"DATABASE_URL": "postgresql://test:pass@localhost:5432/test_db"}):
            reset_settings()
            
            with patch('app.core.database.get_db_manager') as mock_get_db_manager:
                mock_db_manager = AsyncMock()
                mock_get_db_manager.return_value = mock_db_manager
                
                with patch('app.core.database.run_migrations') as mock_run_migrations:
                    result = await initialize_database(auto_migrate=False)
                    
                    # データベース初期化確認
                    mock_db_manager.initialize.assert_called_once()
                    
                    # マイグレーション実行されないことを確認
                    mock_run_migrations.assert_not_called()
                    
                    assert result == mock_db_manager
                    
    @pytest.mark.asyncio
    async def test_initialize_database_migration_failure_handling(self):
        """マイグレーション失敗時のデータベース初期化処理テスト"""
        with patch.dict(os.environ, {"DATABASE_URL": "postgresql://test:pass@localhost:5432/test_db"}):
            reset_settings()
            
            with patch('app.core.database.get_db_manager') as mock_get_db_manager:
                mock_db_manager = AsyncMock()
                mock_get_db_manager.return_value = mock_db_manager
                
                with patch('app.core.database.run_migrations') as mock_run_migrations:
                    mock_run_migrations.side_effect = Exception("Migration failed")
                    
                    # マイグレーション失敗でもデータベース初期化は成功する
                    result = await initialize_database(auto_migrate=True)
                    
                    mock_db_manager.initialize.assert_called_once()
                    mock_run_migrations.assert_called_once()
                    
                    assert result == mock_db_manager


class TestMigrationHelperFunctions:
    """migration helper functions テスト"""
    
    @pytest.mark.asyncio
    async def test_run_migrations_helper(self):
        """run_migrations() ヘルパー関数テスト"""
        with patch('app.core.migrations.get_migration_manager') as mock_get_migration_manager:
            mock_migration_manager = AsyncMock()
            mock_get_migration_manager.return_value = mock_migration_manager
            
            await run_migrations()
            
            mock_migration_manager.apply_all_migrations.assert_called_once()
            
    @pytest.mark.asyncio
    async def test_run_migrations_error_handling(self):
        """run_migrations() エラーハンドリングテスト"""
        from app.core.database import InitializationError
        
        with patch('app.core.migrations.get_migration_manager') as mock_get_migration_manager:
            mock_migration_manager = AsyncMock()
            mock_migration_manager.apply_all_migrations.side_effect = Exception("Migration failed")
            mock_get_migration_manager.return_value = mock_migration_manager
            
            with pytest.raises(InitializationError) as exc_info:
                await run_migrations()
            
            assert "Migration execution failed" in str(exc_info.value)
            
    @pytest.mark.asyncio
    async def test_rollback_migration_helper(self):
        """rollback_migration() ヘルパー関数テスト"""
        with patch('app.core.migrations.get_migration_manager') as mock_get_migration_manager:
            mock_migration_manager = AsyncMock()
            mock_get_migration_manager.return_value = mock_migration_manager
            
            await rollback_migration("001_create_agent_memory")
            
            mock_migration_manager.rollback_migration.assert_called_once_with("001_create_agent_memory")
            
    @pytest.mark.asyncio
    async def test_rollback_migration_error_handling(self):
        """rollback_migration() エラーハンドリングテスト"""
        from app.core.database import QueryError
        
        with patch('app.core.migrations.get_migration_manager') as mock_get_migration_manager:
            mock_migration_manager = AsyncMock()
            mock_migration_manager.rollback_migration.side_effect = Exception("Rollback failed")
            mock_get_migration_manager.return_value = mock_migration_manager
            
            with pytest.raises(QueryError) as exc_info:
                await rollback_migration("001_create_agent_memory")
            
            assert "Migration rollback failed" in str(exc_info.value)
            
    @pytest.mark.asyncio
    async def test_check_migration_status_helper(self):
        """check_migration_status() ヘルパー関数テスト"""
        mock_migrations = [
            {"version": "001_create_agent_memory", "applied_at": "2025-08-09"},
            {"version": "002_add_indexes", "applied_at": "2025-08-09"}
        ]
        
        with patch('app.core.migrations.get_migration_manager') as mock_get_migration_manager:
            mock_migration_manager = AsyncMock()
            mock_migration_manager.get_applied_migrations.return_value = mock_migrations
            mock_get_migration_manager.return_value = mock_migration_manager
            
            result = await check_migration_status()
            
            assert result == mock_migrations
            mock_migration_manager.get_applied_migrations.assert_called_once()
            
    @pytest.mark.asyncio
    async def test_check_migration_status_error_handling(self):
        """check_migration_status() エラーハンドリングテスト"""
        with patch('app.core.migrations.get_migration_manager') as mock_get_migration_manager:
            mock_migration_manager = AsyncMock()
            mock_migration_manager.get_applied_migrations.side_effect = Exception("Status check failed")
            mock_get_migration_manager.return_value = mock_migration_manager
            
            # エラー時は空リストを返す
            result = await check_migration_status()
            
            assert result == []


class TestIntegrationScenarios:
    """統合シナリオテスト"""
    
    @pytest.mark.asyncio
    async def test_full_database_setup_scenario(self):
        """完全なデータベース設定シナリオテスト"""
        with patch.dict(os.environ, {"DATABASE_URL": "postgresql://test:pass@localhost:5432/test_db"}):
            reset_settings()
            
            # Step 1: データベース初期化（マイグレーション付き）
            with patch('app.core.database.get_db_manager') as mock_get_db_manager, \
                 patch('app.core.migrations.get_migration_manager') as mock_get_migration_manager:
                
                mock_db_manager = AsyncMock()
                mock_get_db_manager.return_value = mock_db_manager
                
                mock_migration_manager = AsyncMock()
                mock_get_migration_manager.return_value = mock_migration_manager
                
                # 初期化実行
                result = await initialize_database(auto_migrate=True)
                
                # 検証
                mock_db_manager.initialize.assert_called_once()
                mock_migration_manager.apply_all_migrations.assert_called_once()
                
                assert result == mock_db_manager
                
    @pytest.mark.asyncio
    async def test_migration_management_workflow(self):
        """マイグレーション管理ワークフローテスト"""
        with patch('app.core.migrations.get_migration_manager') as mock_get_migration_manager:
            mock_migration_manager = AsyncMock()
            mock_get_migration_manager.return_value = mock_migration_manager
            
            # Step 1: マイグレーション状態確認
            mock_migration_manager.get_applied_migrations.return_value = []
            status = await check_migration_status()
            assert status == []
            
            # Step 2: マイグレーション実行
            await run_migrations()
            mock_migration_manager.apply_all_migrations.assert_called_once()
            
            # Step 3: 再度状態確認
            mock_migration_manager.get_applied_migrations.return_value = [
                {"version": "001_create_agent_memory", "applied_at": "2025-08-09"}
            ]
            status = await check_migration_status()
            assert len(status) == 1
            
            # Step 4: ロールバック実行
            await rollback_migration("001_create_agent_memory")
            mock_migration_manager.rollback_migration.assert_called_once_with("001_create_agent_memory")
            
    @pytest.mark.asyncio
    async def test_error_isolation_between_systems(self):
        """システム間エラー分離テスト"""
        with patch.dict(os.environ, {"DATABASE_URL": "postgresql://test:pass@localhost:5432/test_db"}):
            reset_settings()
            
            # データベース初期化は成功、マイグレーションは失敗のケース
            with patch('app.core.database.get_db_manager') as mock_get_db_manager, \
                 patch('app.core.migrations.get_migration_manager') as mock_get_migration_manager:
                
                mock_db_manager = AsyncMock()
                mock_get_db_manager.return_value = mock_db_manager
                
                mock_migration_manager = AsyncMock()
                mock_migration_manager.apply_all_migrations.side_effect = Exception("Migration failed")
                mock_get_migration_manager.return_value = mock_migration_manager
                
                # マイグレーション失敗でもデータベース初期化は成功する
                result = await initialize_database(auto_migrate=True)
                
                mock_db_manager.initialize.assert_called_once()
                assert result == mock_db_manager