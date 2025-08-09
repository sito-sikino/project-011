"""
Tasks module for Discord Multi-Agent System

Phase 4: Task Management System 実装完了
タスク管理システム、Pydanticタスクモデル、CRUD操作、Redis キュー管理を提供

公開API:
- TaskModel: Pydantic v2 タスクモデル（バリデーション、シリアライゼーション）
- TaskStatus/TaskPriority: Enum による状態・優先度管理  
- TaskManager: 非同期CRUD操作、ハイブリッドストレージ（Redis + PostgreSQL）
- RedisTaskQueue: 優先度ベースキュー、エージェント別管理、リトライ機構
- TaskError系: カスタム例外クラス群
- ヘルパー関数: シングルトン取得、システム初期化・終了

使用例:
```python
from app.tasks import (
    TaskModel, TaskStatus, TaskPriority,
    TaskManager, RedisTaskQueue,
    get_task_manager, get_redis_queue,
    initialize_task_system, close_task_system
)

# タスクシステム初期化
task_manager, redis_queue = await initialize_task_system()

# タスク作成
task = await task_manager.create_task(
    title="Sample Task",
    description="Task description",
    priority=TaskPriority.HIGH,
    agent_id="agent_001"
)

# キューイング
await redis_queue.enqueue(task)

# デキューイング
dequeued_task = await redis_queue.dequeue()

# システム終了
await close_task_system()
```
"""

# Core Models and Enums
from .manager import (
    TaskModel,
    TaskStatus,
    TaskPriority,
)

# Manager Classes
from .manager import (
    TaskManager,
    RedisTaskQueue,
)

# Exception Classes
from .manager import (
    TaskError,
    TaskNotFoundError,
    TaskValidationError,
    QueueError,
    QueueEmptyError,
    QueueFullError,
)

# Singleton Helpers
from .manager import (
    get_task_manager,
    reset_task_manager,
    get_redis_queue,
    reset_redis_queue,
)

# Convenience Functions
from .manager import (
    initialize_task_system,
    close_task_system,
)

# Public API exports
__all__ = [
    # Models and Enums
    "TaskModel",
    "TaskStatus", 
    "TaskPriority",
    
    # Manager Classes
    "TaskManager",
    "RedisTaskQueue",
    
    # Exception Classes
    "TaskError",
    "TaskNotFoundError",
    "TaskValidationError",
    "QueueError",
    "QueueEmptyError",
    "QueueFullError",
    
    # Singleton Helpers
    "get_task_manager",
    "reset_task_manager",
    "get_redis_queue", 
    "reset_redis_queue",
    
    # Convenience Functions
    "initialize_task_system",
    "close_task_system",
]