"""
Test cases for Task CRUD Operations - Discord Multi-Agent System

Phase 4.2: Task Management System - CRUD Operations Tests
t-wada式TDDサイクル実装フロー:
🔴 Red Phase: 包括的なタスクCRUD操作テストを先行作成

技術仕様:
- TaskManager クラスによる非同期CRUD操作
- PostgreSQL 永続化 + Redis キャッシュ
- ハイブリッドストレージ（Redis Hot + PostgreSQL Cold）
- 原子的操作 (Redis + PostgreSQL 同期)
- エラーハンドリング、Fail-Fast設計
- settings.py統合
"""
import pytest
import asyncio
from datetime import datetime, timezone
from uuid import UUID, uuid4
from unittest.mock import AsyncMock, MagicMock, patch
from typing import List, Dict, Any, Optional

# TaskManager初期化・設定テスト
class TestTaskManagerInitialization:
    """TaskManager初期化テスト"""
    
    def test_task_manager_import_should_succeed(self):
        """TaskManagerクラスのimportが成功すること"""
        from app.tasks.manager import TaskManager
        assert TaskManager is not None
    
    def test_task_manager_error_classes_import_should_succeed(self):
        """TaskManager関連エラークラスのimportが成功すること"""
        from app.tasks.manager import TaskError, TaskNotFoundError, TaskValidationError
        assert TaskError is not None
        assert TaskNotFoundError is not None
        assert TaskValidationError is not None
        
    @pytest.mark.asyncio
    async def test_task_manager_initialization_with_settings(self):
        """設定を使ったTaskManager初期化が成功すること"""
        from app.tasks.manager import TaskManager
        from app.core.settings import get_settings
        
        settings = get_settings()
        task_manager = TaskManager(settings)
        
        assert task_manager.settings == settings
        assert task_manager.redis_url == settings.database.redis_url
        assert task_manager.database_url == settings.database.url
        
    @pytest.mark.asyncio
    async def test_task_manager_initialize_should_setup_connections(self):
        """TaskManager初期化時にRedis・DB接続が設定されること"""
        from app.tasks.manager import TaskManager
        from app.core.settings import get_settings
        
        settings = get_settings()
        task_manager = TaskManager(settings)
        
        await task_manager.initialize()
        
        assert task_manager.redis_client is not None
        assert task_manager.db_manager is not None
        
        await task_manager.close()
        
    @pytest.mark.asyncio
    async def test_task_manager_close_should_cleanup_connections(self):
        """TaskManager終了時に接続がクリーンアップされること"""
        from app.tasks.manager import TaskManager
        from app.core.settings import get_settings
        
        settings = get_settings()
        task_manager = TaskManager(settings)
        await task_manager.initialize()
        
        await task_manager.close()
        
        # 接続がクローズされていることを確認
        # 実装に依存する詳細は実装後に調整


# タスク作成 (CREATE) テスト
class TestTaskCreate:
    """タスク作成操作テスト"""
    
    @pytest.mark.asyncio
    async def test_create_task_with_minimal_data_should_succeed(self):
        """最小限のデータでタスク作成が成功すること"""
        from app.tasks.manager import TaskManager, TaskModel
        from app.core.settings import get_settings
        
        settings = get_settings()
        task_manager = TaskManager(settings)
        await task_manager.initialize()
        
        try:
            task = await task_manager.create_task(
                title="Test Task",
                description="Test Description"
            )
            
            assert isinstance(task, TaskModel)
            assert task.title == "Test Task"
            assert task.description == "Test Description"
            assert task.status == "pending"
            assert task.priority == "medium"
            assert isinstance(task.id, UUID)
            
        finally:
            await task_manager.close()
            
    @pytest.mark.asyncio
    async def test_create_task_with_full_data_should_succeed(self):
        """全データ指定でタスク作成が成功すること"""
        from app.tasks.manager import TaskManager, TaskModel, TaskStatus, TaskPriority
        from app.core.settings import get_settings
        
        settings = get_settings()
        task_manager = TaskManager(settings)
        await task_manager.initialize()
        
        try:
            task = await task_manager.create_task(
                title="Complex Task",
                description="Detailed description",
                status=TaskStatus.IN_PROGRESS,
                priority=TaskPriority.HIGH,
                agent_id="test_agent_001",
                channel_id="123456789012345678",
                metadata={"source": "discord", "user_id": "user_123"}
            )
            
            assert task.title == "Complex Task"
            assert task.status == TaskStatus.IN_PROGRESS
            assert task.priority == TaskPriority.HIGH
            assert task.agent_id == "test_agent_001"
            assert task.channel_id == "123456789012345678"
            assert task.metadata["source"] == "discord"
            
        finally:
            await task_manager.close()
            
    @pytest.mark.asyncio
    async def test_create_task_should_store_in_redis_and_postgresql(self):
        """タスク作成時にRedisとPostgreSQLの両方に保存されること"""
        from app.tasks.manager import TaskManager
        from app.core.settings import get_settings
        
        settings = get_settings()
        task_manager = TaskManager(settings)
        await task_manager.initialize()
        
        try:
            task = await task_manager.create_task(
                title="Storage Test Task",
                description="Test storage in both Redis and PostgreSQL"
            )
            
            # Redis確認
            redis_task = await task_manager.get_task_from_redis(task.id)
            assert redis_task is not None
            assert redis_task.title == "Storage Test Task"
            
            # PostgreSQL確認
            pg_task = await task_manager.get_task_from_database(task.id)
            assert pg_task is not None
            assert pg_task.title == "Storage Test Task"
            
        finally:
            await task_manager.close()
            
    @pytest.mark.asyncio
    async def test_create_task_with_invalid_data_should_raise_validation_error(self):
        """無効なデータでタスク作成時にValidationErrorが発生すること"""
        from app.tasks.manager import TaskManager, TaskValidationError
        from app.core.settings import get_settings
        
        settings = get_settings()
        task_manager = TaskManager(settings)
        await task_manager.initialize()
        
        try:
            with pytest.raises(TaskValidationError):
                await task_manager.create_task(
                    title="",  # 空のタイトル（無効）
                    description="Valid description"
                )
                
        finally:
            await task_manager.close()


# タスク取得 (READ) テスト
class TestTaskRead:
    """タスク取得操作テスト"""
    
    @pytest.mark.asyncio
    async def test_get_task_by_id_should_return_task(self):
        """IDによるタスク取得が成功すること"""
        from app.tasks.manager import TaskManager
        from app.core.settings import get_settings
        
        settings = get_settings()
        task_manager = TaskManager(settings)
        await task_manager.initialize()
        
        try:
            # タスク作成
            created_task = await task_manager.create_task(
                title="Retrieve Test Task",
                description="Test task retrieval"
            )
            
            # タスク取得
            retrieved_task = await task_manager.get_task(created_task.id)
            
            assert retrieved_task is not None
            assert retrieved_task.id == created_task.id
            assert retrieved_task.title == "Retrieve Test Task"
            assert retrieved_task.description == "Test task retrieval"
            
        finally:
            await task_manager.close()
            
    @pytest.mark.asyncio
    async def test_get_task_should_check_redis_first_then_database(self):
        """タスク取得時にまずRedisをチェックし、次にデータベースを確認すること"""
        from app.tasks.manager import TaskManager
        from app.core.settings import get_settings
        
        settings = get_settings()
        task_manager = TaskManager(settings)
        await task_manager.initialize()
        
        with patch.object(task_manager, 'get_task_from_redis', return_value=None) as mock_redis:
            with patch.object(task_manager, 'get_task_from_database') as mock_db:
                mock_db.return_value = AsyncMock()
                
                task_id = uuid4()
                await task_manager.get_task(task_id)
                
                mock_redis.assert_called_once_with(task_id)
                mock_db.assert_called_once_with(task_id)
                
        await task_manager.close()
        
    @pytest.mark.asyncio
    async def test_get_nonexistent_task_should_raise_not_found_error(self):
        """存在しないタスクの取得時にTaskNotFoundErrorが発生すること"""
        from app.tasks.manager import TaskManager, TaskNotFoundError
        from app.core.settings import get_settings
        
        settings = get_settings()
        task_manager = TaskManager(settings)
        await task_manager.initialize()
        
        try:
            nonexistent_id = uuid4()
            
            with pytest.raises(TaskNotFoundError):
                await task_manager.get_task(nonexistent_id)
                
        finally:
            await task_manager.close()
            
    @pytest.mark.asyncio
    async def test_get_tasks_by_status_should_return_filtered_tasks(self):
        """ステータスによるタスク取得が正しくフィルタリングされること"""
        from app.tasks.manager import TaskManager, TaskStatus
        from app.core.settings import get_settings
        
        settings = get_settings()
        task_manager = TaskManager(settings)
        await task_manager.initialize()
        
        try:
            # 異なるステータスのタスクを作成
            await task_manager.create_task("Pending Task", "Description", status=TaskStatus.PENDING)
            await task_manager.create_task("In Progress Task", "Description", status=TaskStatus.IN_PROGRESS)
            await task_manager.create_task("Completed Task", "Description", status=TaskStatus.COMPLETED)
            
            # 進行中のタスクのみ取得
            in_progress_tasks = await task_manager.get_tasks_by_status(TaskStatus.IN_PROGRESS)
            
            assert len(in_progress_tasks) >= 1
            assert all(task.status == TaskStatus.IN_PROGRESS for task in in_progress_tasks)
            
        finally:
            await task_manager.close()
            
    @pytest.mark.asyncio
    async def test_get_tasks_by_agent_should_return_filtered_tasks(self):
        """エージェントIDによるタスク取得が正しくフィルタリングされること"""
        from app.tasks.manager import TaskManager
        from app.core.settings import get_settings
        
        settings = get_settings()
        task_manager = TaskManager(settings)
        await task_manager.initialize()
        
        try:
            # 異なるエージェントのタスクを作成
            await task_manager.create_task("Agent 1 Task", "Description", agent_id="agent_001")
            await task_manager.create_task("Agent 2 Task", "Description", agent_id="agent_002")
            await task_manager.create_task("Agent 1 Task 2", "Description", agent_id="agent_001")
            
            # agent_001のタスクのみ取得
            agent_tasks = await task_manager.get_tasks_by_agent("agent_001")
            
            assert len(agent_tasks) >= 2
            assert all(task.agent_id == "agent_001" for task in agent_tasks)
            
        finally:
            await task_manager.close()
            
    @pytest.mark.asyncio
    async def test_get_tasks_by_channel_should_return_filtered_tasks(self):
        """チャンネルIDによるタスク取得が正しくフィルタリングされること"""
        from app.tasks.manager import TaskManager
        from app.core.settings import get_settings
        
        settings = get_settings()
        task_manager = TaskManager(settings)
        await task_manager.initialize()
        
        try:
            # 異なるチャンネルのタスクを作成
            await task_manager.create_task("Channel 1 Task", "Description", channel_id="123456789012345678")
            await task_manager.create_task("Channel 2 Task", "Description", channel_id="987654321098765432")
            
            # 特定チャンネルのタスクのみ取得
            channel_tasks = await task_manager.get_tasks_by_channel("123456789012345678")
            
            assert len(channel_tasks) >= 1
            assert all(task.channel_id == "123456789012345678" for task in channel_tasks)
            
        finally:
            await task_manager.close()


# タスク更新 (UPDATE) テスト
class TestTaskUpdate:
    """タスク更新操作テスト"""
    
    @pytest.mark.asyncio
    async def test_update_task_should_modify_fields_and_timestamp(self):
        """タスク更新時にフィールドと更新時刻が変更されること"""
        from app.tasks.manager import TaskManager, TaskStatus, TaskPriority
        from app.core.settings import get_settings
        
        settings = get_settings()
        task_manager = TaskManager(settings)
        await task_manager.initialize()
        
        try:
            # タスク作成
            task = await task_manager.create_task(
                title="Original Title",
                description="Original Description"
            )
            
            original_updated_at = task.updated_at
            
            # 少し時間をおく
            await asyncio.sleep(0.001)
            
            # タスク更新
            updated_task = await task_manager.update_task(
                task.id,
                title="Updated Title",
                description="Updated Description",
                status=TaskStatus.IN_PROGRESS,
                priority=TaskPriority.HIGH
            )
            
            assert updated_task.title == "Updated Title"
            assert updated_task.description == "Updated Description"
            assert updated_task.status == TaskStatus.IN_PROGRESS
            assert updated_task.priority == TaskPriority.HIGH
            assert updated_task.updated_at > original_updated_at
            
        finally:
            await task_manager.close()
            
    @pytest.mark.asyncio
    async def test_update_task_should_sync_redis_and_database(self):
        """タスク更新時にRedisとデータベースが同期されること"""
        from app.tasks.manager import TaskManager, TaskStatus
        from app.core.settings import get_settings
        
        settings = get_settings()
        task_manager = TaskManager(settings)
        await task_manager.initialize()
        
        try:
            # タスク作成
            task = await task_manager.create_task("Update Test", "Description")
            
            # タスク更新
            await task_manager.update_task(
                task.id,
                status=TaskStatus.COMPLETED
            )
            
            # Redis確認
            redis_task = await task_manager.get_task_from_redis(task.id)
            assert redis_task.status == TaskStatus.COMPLETED
            
            # PostgreSQL確認
            db_task = await task_manager.get_task_from_database(task.id)
            assert db_task.status == TaskStatus.COMPLETED
            
        finally:
            await task_manager.close()
            
    @pytest.mark.asyncio
    async def test_update_nonexistent_task_should_raise_not_found_error(self):
        """存在しないタスクの更新時にTaskNotFoundErrorが発生すること"""
        from app.tasks.manager import TaskManager, TaskNotFoundError
        from app.core.settings import get_settings
        
        settings = get_settings()
        task_manager = TaskManager(settings)
        await task_manager.initialize()
        
        try:
            nonexistent_id = uuid4()
            
            with pytest.raises(TaskNotFoundError):
                await task_manager.update_task(
                    nonexistent_id,
                    title="Updated Title"
                )
                
        finally:
            await task_manager.close()
            
    @pytest.mark.asyncio
    async def test_update_task_with_invalid_data_should_raise_validation_error(self):
        """無効なデータでタスク更新時にValidationErrorが発生すること"""
        from app.tasks.manager import TaskManager, TaskValidationError
        from app.core.settings import get_settings
        
        settings = get_settings()
        task_manager = TaskManager(settings)
        await task_manager.initialize()
        
        try:
            # タスク作成
            task = await task_manager.create_task("Valid Task", "Description")
            
            # 無効なデータで更新試行
            with pytest.raises(TaskValidationError):
                await task_manager.update_task(
                    task.id,
                    title=""  # 空のタイトル（無効）
                )
                
        finally:
            await task_manager.close()
            
    @pytest.mark.asyncio
    async def test_update_task_metadata_should_preserve_existing_data(self):
        """メタデータ更新時に既存データが保持されること"""
        from app.tasks.manager import TaskManager
        from app.core.settings import get_settings
        
        settings = get_settings()
        task_manager = TaskManager(settings)
        await task_manager.initialize()
        
        try:
            # メタデータ付きタスク作成
            task = await task_manager.create_task(
                title="Metadata Test",
                description="Test metadata update",
                metadata={"existing_key": "existing_value"}
            )
            
            # メタデータ追加更新
            updated_task = await task_manager.update_task_metadata(
                task.id,
                {"new_key": "new_value"}
            )
            
            assert "existing_key" in updated_task.metadata
            assert updated_task.metadata["existing_key"] == "existing_value"
            assert updated_task.metadata["new_key"] == "new_value"
            
        finally:
            await task_manager.close()


# タスク削除 (DELETE) テスト
class TestTaskDelete:
    """タスク削除操作テスト"""
    
    @pytest.mark.asyncio
    async def test_delete_task_should_remove_from_redis_and_database(self):
        """タスク削除時にRedisとデータベースの両方から削除されること"""
        from app.tasks.manager import TaskManager, TaskNotFoundError
        from app.core.settings import get_settings
        
        settings = get_settings()
        task_manager = TaskManager(settings)
        await task_manager.initialize()
        
        try:
            # タスク作成
            task = await task_manager.create_task("Delete Test", "Description")
            
            # 削除前確認
            assert await task_manager.get_task(task.id) is not None
            
            # タスク削除
            await task_manager.delete_task(task.id)
            
            # 削除後確認
            with pytest.raises(TaskNotFoundError):
                await task_manager.get_task(task.id)
                
        finally:
            await task_manager.close()
            
    @pytest.mark.asyncio
    async def test_soft_delete_task_should_change_status_to_cancelled(self):
        """ソフト削除時にステータスがcancelledに変更されること"""
        from app.tasks.manager import TaskManager, TaskStatus
        from app.core.settings import get_settings
        
        settings = get_settings()
        task_manager = TaskManager(settings)
        await task_manager.initialize()
        
        try:
            # タスク作成
            task = await task_manager.create_task("Soft Delete Test", "Description")
            
            # ソフト削除
            cancelled_task = await task_manager.soft_delete_task(task.id)
            
            assert cancelled_task.status == TaskStatus.CANCELLED
            
            # タスクは存在するが非アクティブ
            retrieved_task = await task_manager.get_task(task.id)
            assert retrieved_task.status == TaskStatus.CANCELLED
            
        finally:
            await task_manager.close()
            
    @pytest.mark.asyncio
    async def test_delete_nonexistent_task_should_raise_not_found_error(self):
        """存在しないタスクの削除時にTaskNotFoundErrorが発生すること"""
        from app.tasks.manager import TaskManager, TaskNotFoundError
        from app.core.settings import get_settings
        
        settings = get_settings()
        task_manager = TaskManager(settings)
        await task_manager.initialize()
        
        try:
            nonexistent_id = uuid4()
            
            with pytest.raises(TaskNotFoundError):
                await task_manager.delete_task(nonexistent_id)
                
        finally:
            await task_manager.close()
            
    @pytest.mark.asyncio
    async def test_bulk_delete_tasks_should_remove_multiple_tasks(self):
        """一括削除で複数のタスクが削除されること"""
        from app.tasks.manager import TaskManager, TaskNotFoundError
        from app.core.settings import get_settings
        
        settings = get_settings()
        task_manager = TaskManager(settings)
        await task_manager.initialize()
        
        try:
            # 複数タスク作成
            task1 = await task_manager.create_task("Bulk Delete 1", "Description")
            task2 = await task_manager.create_task("Bulk Delete 2", "Description")
            task3 = await task_manager.create_task("Bulk Delete 3", "Description")
            
            task_ids = [task1.id, task2.id, task3.id]
            
            # 一括削除
            deleted_count = await task_manager.bulk_delete_tasks(task_ids)
            
            assert deleted_count == 3
            
            # 全て削除されていることを確認
            for task_id in task_ids:
                with pytest.raises(TaskNotFoundError):
                    await task_manager.get_task(task_id)
                    
        finally:
            await task_manager.close()


# エラーハンドリング・例外処理テスト
class TestTaskManagerErrorHandling:
    """TaskManager エラーハンドリングテスト"""
    
    @pytest.mark.asyncio
    async def test_redis_connection_failure_should_fallback_to_database(self):
        """Redis接続失敗時にデータベースへフォールバックすること"""
        from app.tasks.manager import TaskManager
        from app.core.settings import get_settings
        
        settings = get_settings()
        task_manager = TaskManager(settings)
        await task_manager.initialize()
        
        # Redis接続失敗をシミュレート
        with patch.object(task_manager.redis_client, 'get', side_effect=Exception("Redis connection failed")):
            # タスク作成（データベースに保存）
            task = await task_manager.create_task("Fallback Test", "Description")
            
            # Redis失敗でもデータベースから取得できること
            retrieved_task = await task_manager.get_task(task.id)
            assert retrieved_task is not None
            
        await task_manager.close()
        
    @pytest.mark.asyncio
    async def test_database_connection_failure_should_raise_task_error(self):
        """データベース接続失敗時にTaskErrorが発生すること"""
        from app.tasks.manager import TaskManager, TaskError
        from app.core.settings import get_settings
        
        settings = get_settings()
        task_manager = TaskManager(settings)
        await task_manager.initialize()
        
        # データベース接続失敗をシミュレート
        with patch.object(task_manager.db_manager, 'execute', side_effect=Exception("Database connection failed")):
            with pytest.raises(TaskError):
                await task_manager.create_task("DB Error Test", "Description")
                
        await task_manager.close()
        
    @pytest.mark.asyncio
    async def test_concurrent_task_updates_should_handle_race_conditions(self):
        """同一タスクの同時更新時に競合状態が適切に処理されること"""
        from app.tasks.manager import TaskManager, TaskStatus
        from app.core.settings import get_settings
        
        settings = get_settings()
        task_manager = TaskManager(settings)
        await task_manager.initialize()
        
        try:
            # タスク作成
            task = await task_manager.create_task("Concurrency Test", "Description")
            
            # 同時更新をシミュレート
            async def update_task_status(status: TaskStatus):
                return await task_manager.update_task(task.id, status=status)
            
            # 複数の更新を並行実行
            results = await asyncio.gather(
                update_task_status(TaskStatus.IN_PROGRESS),
                update_task_status(TaskStatus.COMPLETED),
                return_exceptions=True
            )
            
            # 少なくとも一つは成功すること
            successful_results = [r for r in results if not isinstance(r, Exception)]
            assert len(successful_results) > 0
            
        finally:
            await task_manager.close()


# パフォーマンステスト
class TestTaskManagerPerformance:
    """TaskManager パフォーマンステスト"""
    
    @pytest.mark.asyncio
    async def test_bulk_task_creation_should_be_efficient(self):
        """一括タスク作成が効率的に実行されること"""
        from app.tasks.manager import TaskManager
        from app.core.settings import get_settings
        import time
        
        settings = get_settings()
        task_manager = TaskManager(settings)
        await task_manager.initialize()
        
        try:
            start_time = time.time()
            
            # 100個のタスクを一括作成
            tasks = []
            for i in range(100):
                task = await task_manager.create_task(
                    title=f"Bulk Task {i}",
                    description=f"Description {i}"
                )
                tasks.append(task)
            
            end_time = time.time()
            duration = end_time - start_time
            
            # 100個のタスク作成が5秒以内に完了すること
            assert duration < 5.0
            assert len(tasks) == 100
            
        finally:
            await task_manager.close()
            
    @pytest.mark.asyncio
    async def test_redis_cache_should_improve_read_performance(self):
        """Redisキャッシュが読み取り性能を向上させること"""
        from app.tasks.manager import TaskManager
        from app.core.settings import get_settings
        import time
        
        settings = get_settings()
        task_manager = TaskManager(settings)
        await task_manager.initialize()
        
        try:
            # タスク作成
            task = await task_manager.create_task("Performance Test", "Description")
            
            # 初回取得（キャッシュミス）
            start_time = time.time()
            first_retrieval = await task_manager.get_task(task.id)
            first_duration = time.time() - start_time
            
            # 2回目取得（キャッシュヒット）
            start_time = time.time()
            second_retrieval = await task_manager.get_task(task.id)
            second_duration = time.time() - start_time
            
            # キャッシュヒットの方が高速であること
            assert second_duration <= first_duration
            assert first_retrieval.id == second_retrieval.id
            
        finally:
            await task_manager.close()


# ユーティリティ・ヘルパー関数テスト
class TestTaskManagerUtilities:
    """TaskManager ユーティリティ関数テスト"""
    
    @pytest.mark.asyncio
    async def test_get_task_manager_singleton_should_return_same_instance(self):
        """get_task_manager()が同じインスタンスを返すこと"""
        from app.tasks.manager import get_task_manager
        
        manager1 = get_task_manager()
        manager2 = get_task_manager()
        
        assert manager1 is manager2
        
    @pytest.mark.asyncio
    async def test_reset_task_manager_should_clear_singleton(self):
        """reset_task_manager()でシングルトンがクリアされること"""
        from app.tasks.manager import get_task_manager, reset_task_manager
        
        manager1 = get_task_manager()
        reset_task_manager()
        manager2 = get_task_manager()
        
        assert manager1 is not manager2
        
    @pytest.mark.asyncio
    async def test_task_manager_health_check_should_return_status(self):
        """health_check()が正しいステータスを返すこと"""
        from app.tasks.manager import TaskManager
        from app.core.settings import get_settings
        
        settings = get_settings()
        task_manager = TaskManager(settings)
        await task_manager.initialize()
        
        try:
            health_status = await task_manager.health_check()
            
            assert isinstance(health_status, dict)
            assert "redis" in health_status
            assert "database" in health_status
            assert "status" in health_status
            
        finally:
            await task_manager.close()
            
    @pytest.mark.asyncio
    async def test_get_task_statistics_should_return_counts(self):
        """get_statistics()がタスクの統計情報を返すこと"""
        from app.tasks.manager import TaskManager, TaskStatus
        from app.core.settings import get_settings
        
        settings = get_settings()
        task_manager = TaskManager(settings)
        await task_manager.initialize()
        
        try:
            # 異なるステータスのタスクを作成
            await task_manager.create_task("Stats Test 1", "Description", status=TaskStatus.PENDING)
            await task_manager.create_task("Stats Test 2", "Description", status=TaskStatus.IN_PROGRESS)
            await task_manager.create_task("Stats Test 3", "Description", status=TaskStatus.COMPLETED)
            
            stats = await task_manager.get_statistics()
            
            assert isinstance(stats, dict)
            assert "total_tasks" in stats
            assert "pending_tasks" in stats
            assert "in_progress_tasks" in stats
            assert "completed_tasks" in stats
            assert stats["total_tasks"] >= 3
            
        finally:
            await task_manager.close()