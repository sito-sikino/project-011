"""
Test cases for Redis Task Queue Operations - Discord Multi-Agent System

Phase 4.3: Task Management System - Redis Task Queue Tests
t-wada式TDDサイクル実装フロー:
🔴 Red Phase: 包括的なRedisタスクキュー操作テストを先行作成

技術仕様:
- RedisTaskQueue クラスによる非同期キュー操作
- FIFO処理、優先度ベースdequeue
- エージェント別キュー管理
- チャンネル別タスクフィルタリング
- タスクリトライ機構（指数バックオフ）
- Redis pub/sub イベント通知
- TTL制御、期限切れタスク自動削除
"""
import pytest
import asyncio
from datetime import datetime, timezone, timedelta
from uuid import UUID, uuid4
from unittest.mock import AsyncMock, MagicMock, patch
from typing import List, Dict, Any, Optional

# RedisTaskQueue初期化・設定テスト
class TestRedisTaskQueueInitialization:
    """RedisTaskQueue初期化テスト"""
    
    def test_redis_task_queue_import_should_succeed(self):
        """RedisTaskQueueクラスのimportが成功すること"""
        from app.tasks.manager import RedisTaskQueue
        assert RedisTaskQueue is not None
    
    def test_queue_error_classes_import_should_succeed(self):
        """TaskQueue関連エラークラスのimportが成功すること"""
        from app.tasks.manager import QueueError, QueueEmptyError, QueueFullError
        assert QueueError is not None
        assert QueueEmptyError is not None
        assert QueueFullError is not None
        
    @pytest.mark.asyncio
    async def test_redis_task_queue_initialization_with_settings(self):
        """設定を使ったRedisTaskQueue初期化が成功すること"""
        from app.tasks.manager import RedisTaskQueue
        from app.core.settings import get_settings
        
        settings = get_settings()
        queue = RedisTaskQueue(settings)
        
        assert queue.settings == settings
        assert queue.redis_url == settings.database.redis_url
        assert queue.max_queue_size == settings.task.max_queue_size
        assert queue.default_ttl == settings.task.default_ttl
        
    @pytest.mark.asyncio
    async def test_redis_task_queue_initialize_should_setup_connection(self):
        """RedisTaskQueue初期化時にRedis接続が設定されること"""
        from app.tasks.manager import RedisTaskQueue
        from app.core.settings import get_settings
        
        settings = get_settings()
        queue = RedisTaskQueue(settings)
        
        await queue.initialize()
        
        assert queue.redis_client is not None
        assert queue.pubsub_client is not None
        
        await queue.close()
        
    @pytest.mark.asyncio
    async def test_redis_task_queue_close_should_cleanup_connections(self):
        """RedisTaskQueue終了時に接続がクリーンアップされること"""
        from app.tasks.manager import RedisTaskQueue
        from app.core.settings import get_settings
        
        settings = get_settings()
        queue = RedisTaskQueue(settings)
        await queue.initialize()
        
        await queue.close()
        
        # 接続がクローズされていることを確認
        # 実装に依存する詳細は実装後に調整


# タスクキューイング（ENQUEUE）テスト
class TestTaskEnqueue:
    """タスクキューイング操作テスト"""
    
    @pytest.mark.asyncio
    async def test_enqueue_task_should_add_to_priority_queue(self):
        """タスクキューイング時に優先度キューに追加されること"""
        from app.tasks.manager import RedisTaskQueue, TaskModel, TaskPriority
        from app.core.settings import get_settings
        
        settings = get_settings()
        queue = RedisTaskQueue(settings)
        await queue.initialize()
        
        try:
            task = TaskModel(
                title="Queue Test Task",
                description="Test task queuing",
                priority=TaskPriority.HIGH
            )
            
            await queue.enqueue(task)
            
            # キューサイズ確認
            queue_size = await queue.get_queue_size()
            assert queue_size >= 1
            
            # 優先度キューに正しく追加されていることを確認
            high_priority_size = await queue.get_queue_size_by_priority(TaskPriority.HIGH)
            assert high_priority_size >= 1
            
        finally:
            await queue.close()
            
    @pytest.mark.asyncio
    async def test_enqueue_task_should_set_ttl(self):
        """タスクキューイング時にTTLが設定されること"""
        from app.tasks.manager import RedisTaskQueue, TaskModel
        from app.core.settings import get_settings
        
        settings = get_settings()
        queue = RedisTaskQueue(settings)
        await queue.initialize()
        
        try:
            task = TaskModel(
                title="TTL Test Task",
                description="Test TTL setting"
            )
            
            await queue.enqueue(task, ttl=3600)  # 1時間TTL
            
            # TTL確認
            ttl = await queue.get_task_ttl(task.id)
            assert ttl > 0
            assert ttl <= 3600
            
        finally:
            await queue.close()
            
    @pytest.mark.asyncio
    async def test_enqueue_task_should_trigger_event_notification(self):
        """タスクキューイング時にイベント通知が送信されること"""
        from app.tasks.manager import RedisTaskQueue, TaskModel
        from app.core.settings import get_settings
        
        settings = get_settings()
        queue = RedisTaskQueue(settings)
        await queue.initialize()
        
        try:
            # イベント購読者設定
            event_received = []
            
            async def event_handler(message):
                event_received.append(message)
            
            await queue.subscribe_to_events("task_enqueued", event_handler)
            
            task = TaskModel(
                title="Event Test Task",
                description="Test event notification"
            )
            
            await queue.enqueue(task)
            
            # 少し待ってイベント処理
            await asyncio.sleep(0.1)
            
            # イベントが受信されたことを確認
            assert len(event_received) >= 1
            
        finally:
            await queue.close()
            
    @pytest.mark.asyncio
    async def test_enqueue_task_when_queue_full_should_raise_queue_full_error(self):
        """キューが満杯の場合にQueueFullErrorが発生すること"""
        from app.tasks.manager import RedisTaskQueue, TaskModel, QueueFullError
        from app.core.settings import get_settings
        
        settings = get_settings()
        queue = RedisTaskQueue(settings)
        await queue.initialize()
        
        # キューサイズを1に制限してテスト
        with patch.object(queue, 'max_queue_size', 1):
            try:
                # 1つ目のタスク（成功）
                task1 = TaskModel(title="Task 1", description="First task")
                await queue.enqueue(task1)
                
                # 2つ目のタスク（エラーになるはず）
                task2 = TaskModel(title="Task 2", description="Second task")
                with pytest.raises(QueueFullError):
                    await queue.enqueue(task2)
                    
            finally:
                await queue.close()


# タスクデキューイング（DEQUEUE）テスト
class TestTaskDequeue:
    """タスクデキューイング操作テスト"""
    
    @pytest.mark.asyncio
    async def test_dequeue_task_should_return_highest_priority_task(self):
        """デキューイング時に最高優先度のタスクが返されること"""
        from app.tasks.manager import RedisTaskQueue, TaskModel, TaskPriority
        from app.core.settings import get_settings
        
        settings = get_settings()
        queue = RedisTaskQueue(settings)
        await queue.initialize()
        
        try:
            # 異なる優先度のタスクを追加
            low_task = TaskModel(title="Low Priority", description="Low", priority=TaskPriority.LOW)
            high_task = TaskModel(title="High Priority", description="High", priority=TaskPriority.HIGH)
            medium_task = TaskModel(title="Medium Priority", description="Medium", priority=TaskPriority.MEDIUM)
            
            await queue.enqueue(low_task)
            await queue.enqueue(high_task)
            await queue.enqueue(medium_task)
            
            # デキュー（最高優先度が返されるはず）
            dequeued_task = await queue.dequeue()
            
            assert dequeued_task is not None
            assert dequeued_task.priority == TaskPriority.HIGH
            assert dequeued_task.title == "High Priority"
            
        finally:
            await queue.close()
            
    @pytest.mark.asyncio
    async def test_dequeue_task_should_follow_fifo_for_same_priority(self):
        """同じ優先度のタスクはFIFO順でデキューされること"""
        from app.tasks.manager import RedisTaskQueue, TaskModel, TaskPriority
        from app.core.settings import get_settings
        
        settings = get_settings()
        queue = RedisTaskQueue(settings)
        await queue.initialize()
        
        try:
            # 同じ優先度のタスクを順次追加
            task1 = TaskModel(title="First Task", description="First", priority=TaskPriority.MEDIUM)
            task2 = TaskModel(title="Second Task", description="Second", priority=TaskPriority.MEDIUM)
            task3 = TaskModel(title="Third Task", description="Third", priority=TaskPriority.MEDIUM)
            
            await queue.enqueue(task1)
            await queue.enqueue(task2)
            await queue.enqueue(task3)
            
            # FIFO順でデキュー
            first_dequeued = await queue.dequeue()
            second_dequeued = await queue.dequeue()
            third_dequeued = await queue.dequeue()
            
            assert first_dequeued.title == "First Task"
            assert second_dequeued.title == "Second Task"
            assert third_dequeued.title == "Third Task"
            
        finally:
            await queue.close()
            
    @pytest.mark.asyncio
    async def test_dequeue_from_empty_queue_should_raise_queue_empty_error(self):
        """空のキューからデキュー時にQueueEmptyErrorが発生すること"""
        from app.tasks.manager import RedisTaskQueue, QueueEmptyError
        from app.core.settings import get_settings
        
        settings = get_settings()
        queue = RedisTaskQueue(settings)
        await queue.initialize()
        
        try:
            with pytest.raises(QueueEmptyError):
                await queue.dequeue()
                
        finally:
            await queue.close()
            
    @pytest.mark.asyncio
    async def test_dequeue_with_timeout_should_wait_for_task(self):
        """タイムアウト付きデキューが新しいタスクを待機すること"""
        from app.tasks.manager import RedisTaskQueue, TaskModel
        from app.core.settings import get_settings
        
        settings = get_settings()
        queue = RedisTaskQueue(settings)
        await queue.initialize()
        
        try:
            # 別のタスクで遅延エンキューを実行
            async def delayed_enqueue():
                await asyncio.sleep(0.1)  # 0.1秒後にタスクを追加
                task = TaskModel(title="Delayed Task", description="Delayed")
                await queue.enqueue(task)
            
            # 遅延エンキューを開始
            enqueue_task = asyncio.create_task(delayed_enqueue())
            
            # タイムアウト付きデキュー（タスクを待機）
            dequeued_task = await queue.dequeue(timeout=1.0)
            
            assert dequeued_task is not None
            assert dequeued_task.title == "Delayed Task"
            
            await enqueue_task
            
        finally:
            await queue.close()
            
    @pytest.mark.asyncio
    async def test_dequeue_should_trigger_event_notification(self):
        """タスクデキューイング時にイベント通知が送信されること"""
        from app.tasks.manager import RedisTaskQueue, TaskModel
        from app.core.settings import get_settings
        
        settings = get_settings()
        queue = RedisTaskQueue(settings)
        await queue.initialize()
        
        try:
            # イベント購読者設定
            event_received = []
            
            async def event_handler(message):
                event_received.append(message)
            
            await queue.subscribe_to_events("task_dequeued", event_handler)
            
            # タスク追加とデキュー
            task = TaskModel(title="Event Test", description="Test event")
            await queue.enqueue(task)
            
            dequeued_task = await queue.dequeue()
            
            # 少し待ってイベント処理
            await asyncio.sleep(0.1)
            
            # イベントが受信されたことを確認
            assert len(event_received) >= 1
            assert dequeued_task is not None
            
        finally:
            await queue.close()


# エージェント別キュー管理テスト
class TestAgentSpecificQueues:
    """エージェント別キュー管理テスト"""
    
    @pytest.mark.asyncio
    async def test_enqueue_to_agent_queue_should_isolate_tasks(self):
        """エージェント別キューイングがタスクを分離すること"""
        from app.tasks.manager import RedisTaskQueue, TaskModel
        from app.core.settings import get_settings
        
        settings = get_settings()
        queue = RedisTaskQueue(settings)
        await queue.initialize()
        
        try:
            # 異なるエージェントのタスクを作成
            agent1_task = TaskModel(title="Agent 1 Task", description="Task for agent 1", agent_id="agent_001")
            agent2_task = TaskModel(title="Agent 2 Task", description="Task for agent 2", agent_id="agent_002")
            
            await queue.enqueue_to_agent(agent1_task, "agent_001")
            await queue.enqueue_to_agent(agent2_task, "agent_002")
            
            # エージェント別キューサイズ確認
            agent1_queue_size = await queue.get_agent_queue_size("agent_001")
            agent2_queue_size = await queue.get_agent_queue_size("agent_002")
            
            assert agent1_queue_size >= 1
            assert agent2_queue_size >= 1
            
        finally:
            await queue.close()
            
    @pytest.mark.asyncio
    async def test_dequeue_from_agent_queue_should_return_agent_task(self):
        """エージェント別デキューがそのエージェントのタスクのみ返すこと"""
        from app.tasks.manager import RedisTaskQueue, TaskModel
        from app.core.settings import get_settings
        
        settings = get_settings()
        queue = RedisTaskQueue(settings)
        await queue.initialize()
        
        try:
            # エージェントのタスクを追加
            agent_task = TaskModel(title="Agent Task", description="For specific agent", agent_id="agent_001")
            await queue.enqueue_to_agent(agent_task, "agent_001")
            
            # エージェント別デキュー
            dequeued_task = await queue.dequeue_from_agent("agent_001")
            
            assert dequeued_task is not None
            assert dequeued_task.agent_id == "agent_001"
            assert dequeued_task.title == "Agent Task"
            
        finally:
            await queue.close()
            
    @pytest.mark.asyncio
    async def test_get_all_agent_queues_should_return_active_agents(self):
        """全エージェントキュー取得がアクティブなエージェント一覧を返すこと"""
        from app.tasks.manager import RedisTaskQueue, TaskModel
        from app.core.settings import get_settings
        
        settings = get_settings()
        queue = RedisTaskQueue(settings)
        await queue.initialize()
        
        try:
            # 複数エージェントのタスクを追加
            agents = ["agent_001", "agent_002", "agent_003"]
            for agent in agents:
                task = TaskModel(title=f"Task for {agent}", description="Agent task", agent_id=agent)
                await queue.enqueue_to_agent(task, agent)
            
            # アクティブエージェント一覧取得
            active_agents = await queue.get_active_agents()
            
            assert len(active_agents) >= 3
            for agent in agents:
                assert agent in active_agents
                
        finally:
            await queue.close()


# チャンネル別タスクフィルタリングテスト
class TestChannelFiltering:
    """チャンネル別タスクフィルタリングテスト"""
    
    @pytest.mark.asyncio
    async def test_get_tasks_by_channel_should_filter_correctly(self):
        """チャンネル別タスク取得が正しくフィルタリングされること"""
        from app.tasks.manager import RedisTaskQueue, TaskModel
        from app.core.settings import get_settings
        
        settings = get_settings()
        queue = RedisTaskQueue(settings)
        await queue.initialize()
        
        try:
            # 異なるチャンネルのタスクを追加
            channel1_task = TaskModel(title="Channel 1 Task", description="Task 1", channel_id="123456789012345678")
            channel2_task = TaskModel(title="Channel 2 Task", description="Task 2", channel_id="987654321098765432")
            
            await queue.enqueue(channel1_task)
            await queue.enqueue(channel2_task)
            
            # チャンネル別取得
            channel1_tasks = await queue.get_tasks_by_channel("123456789012345678")
            
            assert len(channel1_tasks) >= 1
            assert all(task.channel_id == "123456789012345678" for task in channel1_tasks)
            
        finally:
            await queue.close()
            
    @pytest.mark.asyncio
    async def test_enqueue_with_channel_priority_should_respect_channel_limits(self):
        """チャンネル優先度付きキューイングがチャンネル制限を尊重すること"""
        from app.tasks.manager import RedisTaskQueue, TaskModel, QueueFullError
        from app.core.settings import get_settings
        
        settings = get_settings()
        queue = RedisTaskQueue(settings)
        await queue.initialize()
        
        try:
            channel_id = "123456789012345678"
            
            # チャンネル別制限設定（テスト用）
            await queue.set_channel_limit(channel_id, 2)
            
            # 制限内でタスク追加（成功）
            task1 = TaskModel(title="Task 1", description="First", channel_id=channel_id)
            task2 = TaskModel(title="Task 2", description="Second", channel_id=channel_id)
            
            await queue.enqueue(task1)
            await queue.enqueue(task2)
            
            # 制限超過でタスク追加（エラー）
            task3 = TaskModel(title="Task 3", description="Third", channel_id=channel_id)
            
            with pytest.raises(QueueFullError):
                await queue.enqueue(task3)
                
        finally:
            await queue.close()


# タスクリトライ機構テスト
class TestTaskRetry:
    """タスクリトライ機構テスト"""
    
    @pytest.mark.asyncio
    async def test_mark_task_for_retry_should_increment_retry_count(self):
        """リトライマーク時にリトライ回数が増加すること"""
        from app.tasks.manager import RedisTaskQueue, TaskModel
        from app.core.settings import get_settings
        
        settings = get_settings()
        queue = RedisTaskQueue(settings)
        await queue.initialize()
        
        try:
            task = TaskModel(title="Retry Test", description="Test retry mechanism")
            await queue.enqueue(task)
            
            # リトライマーク
            await queue.mark_task_for_retry(task.id, "Processing failed")
            
            # リトライ情報確認
            retry_info = await queue.get_task_retry_info(task.id)
            
            assert retry_info["retry_count"] == 1
            assert "Processing failed" in retry_info["error_message"]
            
        finally:
            await queue.close()
            
    @pytest.mark.asyncio
    async def test_retry_task_should_use_exponential_backoff(self):
        """タスクリトライが指数バックオフを使用すること"""
        from app.tasks.manager import RedisTaskQueue, TaskModel
        from app.core.settings import get_settings
        
        settings = get_settings()
        queue = RedisTaskQueue(settings)
        await queue.initialize()
        
        try:
            task = TaskModel(title="Backoff Test", description="Test exponential backoff")
            await queue.enqueue(task)
            
            # 複数回リトライマーク
            await queue.mark_task_for_retry(task.id, "First failure")
            await queue.mark_task_for_retry(task.id, "Second failure")
            await queue.mark_task_for_retry(task.id, "Third failure")
            
            # バックオフ時間確認
            retry_info = await queue.get_task_retry_info(task.id)
            next_retry_delay = retry_info["next_retry_delay"]
            
            # 指数バックオフ（2^retry_count * base_delay）
            expected_min_delay = 2**3 * queue.base_retry_delay  # 3回目なので8倍
            assert next_retry_delay >= expected_min_delay
            
        finally:
            await queue.close()
            
    @pytest.mark.asyncio
    async def test_max_retry_exceeded_should_move_to_failed_queue(self):
        """最大リトライ回数超過時に失敗キューに移動すること"""
        from app.tasks.manager import RedisTaskQueue, TaskModel
        from app.core.settings import get_settings
        
        settings = get_settings()
        queue = RedisTaskQueue(settings)
        await queue.initialize()
        
        try:
            task = TaskModel(title="Max Retry Test", description="Test max retry limit")
            await queue.enqueue(task)
            
            # 最大リトライ回数まで失敗させる
            max_retries = queue.max_retry_count
            for i in range(max_retries + 1):
                await queue.mark_task_for_retry(task.id, f"Failure {i+1}")
            
            # 失敗キューに移動されていることを確認
            failed_tasks = await queue.get_failed_tasks()
            failed_task_ids = [t.id for t in failed_tasks]
            
            assert task.id in failed_task_ids
            
        finally:
            await queue.close()
            
    @pytest.mark.asyncio
    async def test_retry_ready_tasks_should_return_eligible_tasks(self):
        """リトライ準備完了タスクが適格なタスクを返すこと"""
        from app.tasks.manager import RedisTaskQueue, TaskModel
        from app.core.settings import get_settings
        
        settings = get_settings()
        queue = RedisTaskQueue(settings)
        await queue.initialize()
        
        try:
            task = TaskModel(title="Ready Retry Test", description="Test retry ready")
            await queue.enqueue(task)
            
            # 短いバックオフでリトライマーク
            await queue.mark_task_for_retry(task.id, "Quick retry test", backoff_seconds=0.1)
            
            # 少し待つ
            await asyncio.sleep(0.2)
            
            # リトライ準備完了タスク取得
            retry_ready_tasks = await queue.get_retry_ready_tasks()
            retry_ready_ids = [t.id for t in retry_ready_tasks]
            
            assert task.id in retry_ready_ids
            
        finally:
            await queue.close()


# TTL・期限切れタスク管理テスト
class TestTaskTTL:
    """TTL・期限切れタスク管理テスト"""
    
    @pytest.mark.asyncio
    async def test_expired_task_should_be_automatically_removed(self):
        """期限切れタスクが自動削除されること"""
        from app.tasks.manager import RedisTaskQueue, TaskModel
        from app.core.settings import get_settings
        
        settings = get_settings()
        queue = RedisTaskQueue(settings)
        await queue.initialize()
        
        try:
            task = TaskModel(title="TTL Test", description="Test TTL expiration")
            
            # 短いTTLでエンキュー
            await queue.enqueue(task, ttl=1)  # 1秒TTL
            
            # すぐに存在確認
            assert await queue.task_exists(task.id)
            
            # TTL経過を待つ
            await asyncio.sleep(1.5)
            
            # 期限切れ削除実行
            removed_count = await queue.cleanup_expired_tasks()
            
            # タスクが削除されていることを確認
            assert removed_count >= 1
            assert not await queue.task_exists(task.id)
            
        finally:
            await queue.close()
            
    @pytest.mark.asyncio
    async def test_get_expiring_tasks_should_return_near_expiry_tasks(self):
        """期限切れ間近タスク取得が期限間近のタスクを返すこと"""
        from app.tasks.manager import RedisTaskQueue, TaskModel
        from app.core.settings import get_settings
        
        settings = get_settings()
        queue = RedisTaskQueue(settings)
        await queue.initialize()
        
        try:
            # 短期TTLタスク
            short_ttl_task = TaskModel(title="Short TTL", description="Short TTL task")
            await queue.enqueue(short_ttl_task, ttl=60)  # 1分TTL
            
            # 長期TTLタスク
            long_ttl_task = TaskModel(title="Long TTL", description="Long TTL task")
            await queue.enqueue(long_ttl_task, ttl=3600)  # 1時間TTL
            
            # 期限間近タスク取得（2分以内に期限切れ）
            expiring_tasks = await queue.get_expiring_tasks(threshold_seconds=120)
            
            expiring_ids = [t.id for t in expiring_tasks]
            assert short_ttl_task.id in expiring_ids
            assert long_ttl_task.id not in expiring_ids
            
        finally:
            await queue.close()
            
    @pytest.mark.asyncio
    async def test_extend_task_ttl_should_update_expiration(self):
        """タスクTTL延長が期限を更新すること"""
        from app.tasks.manager import RedisTaskQueue, TaskModel
        from app.core.settings import get_settings
        
        settings = get_settings()
        queue = RedisTaskQueue(settings)
        await queue.initialize()
        
        try:
            task = TaskModel(title="TTL Extend Test", description="Test TTL extension")
            await queue.enqueue(task, ttl=60)  # 1分TTL
            
            # 初期TTL確認
            initial_ttl = await queue.get_task_ttl(task.id)
            assert initial_ttl <= 60
            
            # TTL延長
            await queue.extend_task_ttl(task.id, additional_seconds=3600)  # 1時間追加
            
            # 延長後TTL確認
            extended_ttl = await queue.get_task_ttl(task.id)
            assert extended_ttl > initial_ttl
            assert extended_ttl <= 3660  # 元の60秒 + 3600秒
            
        finally:
            await queue.close()


# パブサブイベント通知テスト
class TestPubSubEvents:
    """パブサブイベント通知テスト"""
    
    @pytest.mark.asyncio
    async def test_subscribe_to_task_events_should_receive_notifications(self):
        """タスクイベント購読が通知を受信すること"""
        from app.tasks.manager import RedisTaskQueue, TaskModel
        from app.core.settings import get_settings
        
        settings = get_settings()
        queue = RedisTaskQueue(settings)
        await queue.initialize()
        
        try:
            received_events = []
            
            async def event_handler(event_type, task_data):
                received_events.append({"type": event_type, "data": task_data})
            
            # イベント購読
            await queue.subscribe_to_task_events(event_handler)
            
            # タスク操作実行
            task = TaskModel(title="Event Test", description="Test events")
            await queue.enqueue(task)
            await queue.dequeue()
            
            # イベント受信を少し待つ
            await asyncio.sleep(0.1)
            
            # イベント受信確認
            assert len(received_events) >= 2  # enqueue + dequeue
            
            event_types = [e["type"] for e in received_events]
            assert "task_enqueued" in event_types
            assert "task_dequeued" in event_types
            
        finally:
            await queue.close()
            
    @pytest.mark.asyncio
    async def test_publish_custom_event_should_notify_subscribers(self):
        """カスタムイベント発行が購読者に通知すること"""
        from app.tasks.manager import RedisTaskQueue
        from app.core.settings import get_settings
        
        settings = get_settings()
        queue = RedisTaskQueue(settings)
        await queue.initialize()
        
        try:
            received_events = []
            
            async def custom_event_handler(message):
                received_events.append(message)
            
            # カスタムイベント購読
            await queue.subscribe_to_events("custom_task_event", custom_event_handler)
            
            # カスタムイベント発行
            custom_data = {"task_id": str(uuid4()), "custom_field": "test_value"}
            await queue.publish_event("custom_task_event", custom_data)
            
            # イベント受信を少し待つ
            await asyncio.sleep(0.1)
            
            # イベント受信確認
            assert len(received_events) >= 1
            assert received_events[0]["custom_field"] == "test_value"
            
        finally:
            await queue.close()


# パフォーマンス・統計情報テスト
class TestQueuePerformanceAndStats:
    """キューパフォーマンス・統計情報テスト"""
    
    @pytest.mark.asyncio
    async def test_get_queue_statistics_should_return_comprehensive_stats(self):
        """キュー統計取得が包括的な統計情報を返すこと"""
        from app.tasks.manager import RedisTaskQueue, TaskModel, TaskPriority
        from app.core.settings import get_settings
        
        settings = get_settings()
        queue = RedisTaskQueue(settings)
        await queue.initialize()
        
        try:
            # 様々なタスクを追加
            tasks = [
                TaskModel(title=f"Task {i}", description=f"Description {i}", 
                         priority=TaskPriority.HIGH if i % 2 == 0 else TaskPriority.LOW)
                for i in range(10)
            ]
            
            for task in tasks:
                await queue.enqueue(task)
            
            # 統計情報取得
            stats = await queue.get_statistics()
            
            assert "total_tasks" in stats
            assert "tasks_by_priority" in stats
            assert "queue_size" in stats
            assert "active_agents" in stats
            assert stats["total_tasks"] >= 10
            
        finally:
            await queue.close()
            
    @pytest.mark.asyncio
    async def test_queue_throughput_should_meet_performance_requirements(self):
        """キュースループットが性能要件を満たすこと"""
        from app.tasks.manager import RedisTaskQueue, TaskModel
        from app.core.settings import get_settings
        import time
        
        settings = get_settings()
        queue = RedisTaskQueue(settings)
        await queue.initialize()
        
        try:
            task_count = 100
            
            # エンキュー性能測定
            start_time = time.time()
            
            enqueue_tasks = []
            for i in range(task_count):
                task = TaskModel(title=f"Performance Task {i}", description=f"Task {i}")
                enqueue_tasks.append(queue.enqueue(task))
            
            await asyncio.gather(*enqueue_tasks)
            
            enqueue_duration = time.time() - start_time
            
            # デキュー性能測定
            start_time = time.time()
            
            dequeue_tasks = []
            for i in range(task_count):
                dequeue_tasks.append(queue.dequeue())
            
            await asyncio.gather(*dequeue_tasks)
            
            dequeue_duration = time.time() - start_time
            
            # 性能要件確認（100タスクを5秒以内で処理）
            assert enqueue_duration < 5.0
            assert dequeue_duration < 5.0
            
            # スループット計算
            enqueue_throughput = task_count / enqueue_duration
            dequeue_throughput = task_count / dequeue_duration
            
            assert enqueue_throughput >= 20  # 最低20タスク/秒
            assert dequeue_throughput >= 20  # 最低20タスク/秒
            
        finally:
            await queue.close()
            
    @pytest.mark.asyncio
    async def test_concurrent_queue_operations_should_be_thread_safe(self):
        """並行キュー操作がスレッドセーフであること"""
        from app.tasks.manager import RedisTaskQueue, TaskModel
        from app.core.settings import get_settings
        
        settings = get_settings()
        queue = RedisTaskQueue(settings)
        await queue.initialize()
        
        try:
            # 並行エンキュー・デキュー操作
            async def enqueue_worker(worker_id: int, task_count: int):
                for i in range(task_count):
                    task = TaskModel(title=f"Worker {worker_id} Task {i}", 
                                   description=f"Concurrent task {i}")
                    await queue.enqueue(task)
            
            async def dequeue_worker(worker_id: int, task_count: int):
                dequeued_count = 0
                for _ in range(task_count):
                    try:
                        task = await queue.dequeue(timeout=1.0)
                        if task:
                            dequeued_count += 1
                    except:
                        break
                return dequeued_count
            
            # 並行ワーカー実行
            worker_tasks = []
            
            # エンキューワーカー（3ワーカー × 20タスク）
            for worker_id in range(3):
                worker_tasks.append(enqueue_worker(worker_id, 20))
            
            # デキューワーカー（2ワーカー × 30タスク）
            for worker_id in range(2):
                worker_tasks.append(dequeue_worker(worker_id, 30))
            
            results = await asyncio.gather(*worker_tasks, return_exceptions=True)
            
            # 例外が発生していないことを確認
            exceptions = [r for r in results if isinstance(r, Exception)]
            assert len(exceptions) == 0
            
        finally:
            await queue.close()


# ユーティリティ・ヘルパー関数テスト
class TestQueueUtilities:
    """キューユーティリティ関数テスト"""
    
    @pytest.mark.asyncio
    async def test_get_redis_queue_singleton_should_return_same_instance(self):
        """get_redis_queue()が同じインスタンスを返すこと"""
        from app.tasks.manager import get_redis_queue
        
        queue1 = get_redis_queue()
        queue2 = get_redis_queue()
        
        assert queue1 is queue2
        
    @pytest.mark.asyncio
    async def test_reset_redis_queue_should_clear_singleton(self):
        """reset_redis_queue()でシングルトンがクリアされること"""
        from app.tasks.manager import get_redis_queue, reset_redis_queue
        
        queue1 = get_redis_queue()
        reset_redis_queue()
        queue2 = get_redis_queue()
        
        assert queue1 is not queue2
        
    @pytest.mark.asyncio
    async def test_queue_health_check_should_return_status(self):
        """キューヘルスチェックが正しいステータスを返すこと"""
        from app.tasks.manager import RedisTaskQueue
        from app.core.settings import get_settings
        
        settings = get_settings()
        queue = RedisTaskQueue(settings)
        await queue.initialize()
        
        try:
            health_status = await queue.health_check()
            
            assert isinstance(health_status, dict)
            assert "redis_connection" in health_status
            assert "queue_size" in health_status
            assert "status" in health_status
            
        finally:
            await queue.close()