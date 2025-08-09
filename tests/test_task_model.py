"""
Test cases for Pydantic Task Model - Discord Multi-Agent System

Phase 4.1: Task Management System - Task Model Tests
t-wada式TDDサイクル実装フロー:
🔴 Red Phase: 包括的なPydanticタスクモデルテストを先行作成

技術仕様:
- Pydantic v2 モデル定義・バリデーション
- Task状態管理 (pending, in_progress, completed, failed, cancelled)
- 優先度管理 (low, medium, high, critical)
- UUID ID自動生成、タイムスタンプ管理
- Field制約による堅牢なバリデーション
- JSONB メタデータサポート
"""
import pytest
from datetime import datetime, timezone
from uuid import UUID, uuid4
from typing import Any, Dict
import json

class TestTaskModelInitialization:
    """Task model 初期化テスト"""
    
    def test_task_model_import_should_succeed(self):
        """TaskModelクラスのimportが成功すること"""
        from app.tasks.manager import TaskModel
        assert TaskModel is not None
    
    def test_task_status_enum_import_should_succeed(self):
        """TaskStatus enumのimportが成功すること"""
        from app.tasks.manager import TaskStatus
        assert TaskStatus is not None
        
    def test_task_priority_enum_import_should_succeed(self):
        """TaskPriority enumのimportが成功すること"""
        from app.tasks.manager import TaskPriority
        assert TaskPriority is not None


class TestTaskStatusEnum:
    """TaskStatus Enum テスト"""
    
    def test_task_status_enum_values(self):
        """TaskStatus enumが期待される値を持つこと"""
        from app.tasks.manager import TaskStatus
        
        assert TaskStatus.PENDING == "pending"
        assert TaskStatus.IN_PROGRESS == "in_progress"
        assert TaskStatus.COMPLETED == "completed"
        assert TaskStatus.FAILED == "failed"
        assert TaskStatus.CANCELLED == "cancelled"
        
    def test_task_status_enum_completeness(self):
        """TaskStatus enumが5つの状態を持つこと"""
        from app.tasks.manager import TaskStatus
        
        assert len(list(TaskStatus)) == 5


class TestTaskPriorityEnum:
    """TaskPriority Enum テスト"""
    
    def test_task_priority_enum_values(self):
        """TaskPriority enumが期待される値を持つこと"""
        from app.tasks.manager import TaskPriority
        
        assert TaskPriority.LOW == "low"
        assert TaskPriority.MEDIUM == "medium"  
        assert TaskPriority.HIGH == "high"
        assert TaskPriority.CRITICAL == "critical"
        
    def test_task_priority_enum_completeness(self):
        """TaskPriority enumが4つの優先度を持つこと"""
        from app.tasks.manager import TaskPriority
        
        assert len(list(TaskPriority)) == 4


class TestTaskModelCreation:
    """Task model 作成テスト"""
    
    def test_minimal_task_creation_should_succeed(self):
        """最小限のパラメータでタスク作成が成功すること"""
        from app.tasks.manager import TaskModel
        
        task = TaskModel(
            title="Test Task",
            description="Test Description"
        )
        
        assert task.title == "Test Task"
        assert task.description == "Test Description"
        assert task.status == "pending"  # デフォルト値
        assert task.priority == "medium"  # デフォルト値
        assert isinstance(task.id, UUID)
        assert isinstance(task.created_at, datetime)
        assert isinstance(task.updated_at, datetime)
        assert task.metadata == {}  # デフォルト値
        
    def test_full_task_creation_should_succeed(self):
        """全パラメータ指定でのタスク作成が成功すること"""
        from app.tasks.manager import TaskModel, TaskStatus, TaskPriority
        
        task_id = uuid4()
        agent_id = "test_agent_001"
        channel_id = "123456789012345678"
        metadata = {"source": "discord", "user_id": "user_123"}
        now = datetime.now(timezone.utc)
        
        task = TaskModel(
            id=task_id,
            title="Complex Task",
            description="Detailed task description",
            status=TaskStatus.IN_PROGRESS,
            priority=TaskPriority.HIGH,
            agent_id=agent_id,
            channel_id=channel_id,
            created_at=now,
            updated_at=now,
            metadata=metadata
        )
        
        assert task.id == task_id
        assert task.title == "Complex Task"
        assert task.description == "Detailed task description"
        assert task.status == TaskStatus.IN_PROGRESS
        assert task.priority == TaskPriority.HIGH
        assert task.agent_id == agent_id
        assert task.channel_id == channel_id
        assert task.created_at == now
        assert task.updated_at == now
        assert task.metadata == metadata


class TestTaskModelValidation:
    """Task model バリデーションテスト"""
    
    def test_title_validation_should_reject_empty_string(self):
        """titleが空文字列の場合にバリデーションエラーが発生すること"""
        from app.tasks.manager import TaskModel
        from pydantic import ValidationError
        
        with pytest.raises(ValidationError) as exc_info:
            TaskModel(
                title="",  # 空文字列
                description="Valid description"
            )
        
        assert "title" in str(exc_info.value)
        
    def test_title_validation_should_reject_too_long_string(self):
        """titleが200文字を超える場合にバリデーションエラーが発生すること"""
        from app.tasks.manager import TaskModel
        from pydantic import ValidationError
        
        long_title = "a" * 201  # 201文字
        
        with pytest.raises(ValidationError) as exc_info:
            TaskModel(
                title=long_title,
                description="Valid description"
            )
        
        assert "title" in str(exc_info.value)
        
    def test_description_validation_should_reject_too_long_string(self):
        """descriptionが2000文字を超える場合にバリデーションエラーが発生すること"""
        from app.tasks.manager import TaskModel
        from pydantic import ValidationError
        
        long_description = "a" * 2001  # 2001文字
        
        with pytest.raises(ValidationError) as exc_info:
            TaskModel(
                title="Valid title",
                description=long_description
            )
        
        assert "description" in str(exc_info.value)
        
    def test_channel_id_validation_should_reject_invalid_format(self):
        """channel_idが無効な形式の場合にバリデーションエラーが発生すること"""
        from app.tasks.manager import TaskModel
        from pydantic import ValidationError
        
        with pytest.raises(ValidationError) as exc_info:
            TaskModel(
                title="Valid title",
                description="Valid description",
                channel_id="invalid_channel_id"  # Discord IDは数字のみ
            )
        
        assert "channel_id" in str(exc_info.value)
        
    def test_channel_id_validation_should_accept_valid_discord_id(self):
        """channel_idが有効なDiscord ID形式の場合に受け入れること"""
        from app.tasks.manager import TaskModel
        
        task = TaskModel(
            title="Valid title",
            description="Valid description", 
            channel_id="123456789012345678"  # 18桁のDiscord ID
        )
        
        assert task.channel_id == "123456789012345678"
        
    def test_agent_id_validation_should_reject_too_long_string(self):
        """agent_idが100文字を超える場合にバリデーションエラーが発生すること"""
        from app.tasks.manager import TaskModel
        from pydantic import ValidationError
        
        long_agent_id = "a" * 101  # 101文字
        
        with pytest.raises(ValidationError) as exc_info:
            TaskModel(
                title="Valid title",
                description="Valid description",
                agent_id=long_agent_id
            )
        
        assert "agent_id" in str(exc_info.value)


class TestTaskModelSerialization:
    """Task model シリアライゼーションテスト"""
    
    def test_task_model_to_dict_should_preserve_all_fields(self):
        """TaskModelをdict形式に変換時に全フィールドが保持されること"""
        from app.tasks.manager import TaskModel, TaskStatus, TaskPriority
        
        task = TaskModel(
            title="Serialize Test",
            description="Test serialization",
            status=TaskStatus.COMPLETED,
            priority=TaskPriority.HIGH,
            agent_id="test_agent",
            channel_id="123456789012345678",
            metadata={"test": "data"}
        )
        
        task_dict = task.model_dump()
        
        assert task_dict["title"] == "Serialize Test"
        assert task_dict["description"] == "Test serialization"
        assert task_dict["status"] == "completed"
        assert task_dict["priority"] == "high"
        assert task_dict["agent_id"] == "test_agent"
        assert task_dict["channel_id"] == "123456789012345678"
        assert task_dict["metadata"] == {"test": "data"}
        assert "id" in task_dict
        assert "created_at" in task_dict
        assert "updated_at" in task_dict
        
    def test_task_model_from_dict_should_restore_correctly(self):
        """dict形式からTaskModelを復元時に正しく復元されること"""
        from app.tasks.manager import TaskModel, TaskStatus, TaskPriority
        
        original = TaskModel(
            title="Deserialize Test",
            description="Test deserialization",
            status=TaskStatus.FAILED,
            priority=TaskPriority.CRITICAL
        )
        
        task_dict = original.model_dump()
        restored = TaskModel(**task_dict)
        
        assert restored.id == original.id
        assert restored.title == original.title
        assert restored.description == original.description
        assert restored.status == original.status
        assert restored.priority == original.priority
        assert restored.created_at == original.created_at
        assert restored.updated_at == original.updated_at
        assert restored.metadata == original.metadata
        
    def test_task_model_to_json_should_be_valid(self):
        """TaskModelをJSON形式に変換時に有効なJSONになること"""
        from app.tasks.manager import TaskModel
        
        task = TaskModel(
            title="JSON Test",
            description="Test JSON serialization"
        )
        
        json_str = task.model_dump_json()
        parsed = json.loads(json_str)
        
        assert parsed["title"] == "JSON Test"
        assert parsed["description"] == "Test JSON serialization"
        assert "id" in parsed
        assert "created_at" in parsed


class TestTaskModelDefaults:
    """Task model デフォルト値テスト"""
    
    def test_default_status_should_be_pending(self):
        """デフォルトステータスがpendingであること"""
        from app.tasks.manager import TaskModel, TaskStatus
        
        task = TaskModel(
            title="Default Status Test",
            description="Test default status"
        )
        
        assert task.status == TaskStatus.PENDING
        
    def test_default_priority_should_be_medium(self):
        """デフォルト優先度がmediumであること"""
        from app.tasks.manager import TaskModel, TaskPriority
        
        task = TaskModel(
            title="Default Priority Test",
            description="Test default priority"
        )
        
        assert task.priority == TaskPriority.MEDIUM
        
    def test_default_metadata_should_be_empty_dict(self):
        """デフォルトメタデータが空辞書であること"""
        from app.tasks.manager import TaskModel
        
        task = TaskModel(
            title="Default Metadata Test",
            description="Test default metadata"
        )
        
        assert task.metadata == {}
        assert isinstance(task.metadata, dict)
        
    def test_auto_generated_id_should_be_uuid(self):
        """自動生成IDがUUIDであること"""
        from app.tasks.manager import TaskModel
        
        task = TaskModel(
            title="Auto ID Test",
            description="Test auto-generated ID"
        )
        
        assert isinstance(task.id, UUID)
        
    def test_auto_generated_timestamps_should_be_recent(self):
        """自動生成タイムスタンプが現在時刻に近いこと"""
        from app.tasks.manager import TaskModel
        
        before = datetime.now(timezone.utc)
        task = TaskModel(
            title="Timestamp Test",
            description="Test auto-generated timestamps"
        )
        after = datetime.now(timezone.utc)
        
        assert before <= task.created_at <= after
        assert before <= task.updated_at <= after
        
    def test_created_at_and_updated_at_should_be_same_initially(self):
        """初期作成時はcreated_atとupdated_atが同じであること"""
        from app.tasks.manager import TaskModel
        
        task = TaskModel(
            title="Initial Timestamp Test",
            description="Test initial timestamps"
        )
        
        assert task.created_at == task.updated_at


class TestTaskModelComparison:
    """Task model 比較テスト"""
    
    def test_tasks_with_same_id_should_be_equal(self):
        """同じIDのタスクは等価であること"""
        from app.tasks.manager import TaskModel
        
        task_id = uuid4()
        
        task1 = TaskModel(
            id=task_id,
            title="Task 1",
            description="First task"
        )
        
        task2 = TaskModel(
            id=task_id,
            title="Task 2",  # タイトルは違うが同じID
            description="Second task"
        )
        
        assert task1 == task2
        
    def test_tasks_with_different_id_should_not_be_equal(self):
        """異なるIDのタスクは等価でないこと"""
        from app.tasks.manager import TaskModel
        
        task1 = TaskModel(
            title="Same Title",
            description="Same Description"
        )
        
        task2 = TaskModel(
            title="Same Title",
            description="Same Description"
        )
        
        assert task1 != task2  # 異なるUUIDが生成される


class TestTaskModelMethods:
    """Task model メソッドテスト"""
    
    def test_update_status_method_should_change_status_and_timestamp(self):
        """update_statusメソッドがステータスと更新時刻を変更すること"""
        from app.tasks.manager import TaskModel, TaskStatus
        
        task = TaskModel(
            title="Status Update Test",
            description="Test status update method"
        )
        
        original_updated_at = task.updated_at
        
        # 少し時間をおく
        import time
        time.sleep(0.001)
        
        task.update_status(TaskStatus.IN_PROGRESS)
        
        assert task.status == TaskStatus.IN_PROGRESS
        assert task.updated_at > original_updated_at
        
    def test_is_completed_method_should_return_correct_boolean(self):
        """is_completedメソッドが正しいbool値を返すこと"""
        from app.tasks.manager import TaskModel, TaskStatus
        
        pending_task = TaskModel(
            title="Pending Task",
            description="Test pending task"
        )
        
        completed_task = TaskModel(
            title="Completed Task",
            description="Test completed task",
            status=TaskStatus.COMPLETED
        )
        
        assert not pending_task.is_completed()
        assert completed_task.is_completed()
        
    def test_is_active_method_should_return_correct_boolean(self):
        """is_activeメソッドが正しいbool値を返すこと"""
        from app.tasks.manager import TaskModel, TaskStatus
        
        active_task = TaskModel(
            title="Active Task",
            description="Test active task",
            status=TaskStatus.IN_PROGRESS
        )
        
        completed_task = TaskModel(
            title="Completed Task",
            description="Test completed task",
            status=TaskStatus.COMPLETED
        )
        
        failed_task = TaskModel(
            title="Failed Task",
            description="Test failed task",
            status=TaskStatus.FAILED
        )
        
        assert active_task.is_active()
        assert not completed_task.is_active()
        assert not failed_task.is_active()
        
    def test_add_metadata_method_should_update_metadata_and_timestamp(self):
        """add_metadataメソッドがメタデータと更新時刻を変更すること"""
        from app.tasks.manager import TaskModel
        
        task = TaskModel(
            title="Metadata Test",
            description="Test metadata update"
        )
        
        original_updated_at = task.updated_at
        
        # 少し時間をおく
        import time
        time.sleep(0.001)
        
        task.add_metadata("progress", 50)
        
        assert task.metadata["progress"] == 50
        assert task.updated_at > original_updated_at
        
    def test_get_duration_method_should_return_timedelta(self):
        """get_durationメソッドがtimedeltaを返すこと"""
        from app.tasks.manager import TaskModel
        from datetime import timedelta
        
        task = TaskModel(
            title="Duration Test",
            description="Test duration calculation"
        )
        
        duration = task.get_duration()
        
        assert isinstance(duration, timedelta)
        assert duration.total_seconds() >= 0