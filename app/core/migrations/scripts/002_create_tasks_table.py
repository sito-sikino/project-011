"""
002 - Create Tasks Table Migration

Phase 4: Task Management System - tasksテーブル作成

マイグレーション内容:
- tasksテーブル作成（UUID主キー、全フィールド対応）
- status・priority・agent_id・channel_id インデックス作成
- JSONB metadata カラム作成
- タイムスタンプ・トリガー設定
- パフォーマンス最適化インデックス
"""
import logging

logger = logging.getLogger(__name__)


async def up(db_manager):
    """
    tasksテーブル作成マイグレーション実行
    
    Args:
        db_manager: データベース管理インスタンス
    """
    try:
        logger.info("Starting tasks table migration...")
        
        # tasksテーブル作成
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS tasks (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            title VARCHAR(200) NOT NULL,
            description TEXT NOT NULL,
            status VARCHAR(20) NOT NULL DEFAULT 'pending',
            priority VARCHAR(20) NOT NULL DEFAULT 'medium', 
            agent_id VARCHAR(100),
            channel_id VARCHAR(19), -- Discord ID (17-19 digits)
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            metadata JSONB NOT NULL DEFAULT '{}'::jsonb
        );
        """
        
        await db_manager.execute(create_table_sql)
        logger.info("Tasks table created successfully")
        
        # インデックス作成
        indexes = [
            # ステータス検索用インデックス（最も頻繁）
            "CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);",
            
            # 優先度検索用インデックス
            "CREATE INDEX IF NOT EXISTS idx_tasks_priority ON tasks(priority);",
            
            # エージェント別検索用インデックス
            "CREATE INDEX IF NOT EXISTS idx_tasks_agent_id ON tasks(agent_id) WHERE agent_id IS NOT NULL;",
            
            # チャンネル別検索用インデックス
            "CREATE INDEX IF NOT EXISTS idx_tasks_channel_id ON tasks(channel_id) WHERE channel_id IS NOT NULL;",
            
            # 時系列検索用インデックス
            "CREATE INDEX IF NOT EXISTS idx_tasks_created_at ON tasks(created_at);",
            "CREATE INDEX IF NOT EXISTS idx_tasks_updated_at ON tasks(updated_at);",
            
            # 複合インデックス（ステータス + 優先度）
            "CREATE INDEX IF NOT EXISTS idx_tasks_status_priority ON tasks(status, priority);",
            
            # 複合インデックス（エージェント + ステータス）
            "CREATE INDEX IF NOT EXISTS idx_tasks_agent_status ON tasks(agent_id, status) WHERE agent_id IS NOT NULL;",
            
            # 複合インデックス（チャンネル + ステータス）
            "CREATE INDEX IF NOT EXISTS idx_tasks_channel_status ON tasks(channel_id, status) WHERE channel_id IS NOT NULL;",
            
            # メタデータGINインデックス（JSONB検索用）
            "CREATE INDEX IF NOT EXISTS idx_tasks_metadata ON tasks USING gin(metadata);",
        ]
        
        for index_sql in indexes:
            await db_manager.execute(index_sql)
            logger.info(f"Index created: {index_sql.split()[5]}")
        
        # updated_at自動更新トリガー作成
        trigger_function_sql = """
        CREATE OR REPLACE FUNCTION update_tasks_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ language 'plpgsql';
        """
        
        await db_manager.execute(trigger_function_sql)
        logger.info("Updated_at trigger function created")
        
        # トリガー設定
        trigger_sql = """
        CREATE TRIGGER trigger_tasks_updated_at
            BEFORE UPDATE ON tasks
            FOR EACH ROW
            EXECUTE FUNCTION update_tasks_updated_at();
        """
        
        await db_manager.execute(trigger_sql)
        logger.info("Updated_at trigger created")
        
        # ステータスとプライオリティの制約追加
        constraints = [
            """
            ALTER TABLE tasks 
            ADD CONSTRAINT check_tasks_status 
            CHECK (status IN ('pending', 'in_progress', 'completed', 'failed', 'cancelled'));
            """,
            """
            ALTER TABLE tasks 
            ADD CONSTRAINT check_tasks_priority 
            CHECK (priority IN ('low', 'medium', 'high', 'critical'));
            """,
            """
            ALTER TABLE tasks 
            ADD CONSTRAINT check_tasks_title_length 
            CHECK (LENGTH(title) >= 1 AND LENGTH(title) <= 200);
            """,
            """
            ALTER TABLE tasks 
            ADD CONSTRAINT check_tasks_description_length 
            CHECK (LENGTH(description) <= 2000);
            """,
            """
            ALTER TABLE tasks 
            ADD CONSTRAINT check_tasks_agent_id_length 
            CHECK (agent_id IS NULL OR LENGTH(agent_id) <= 100);
            """,
            """
            ALTER TABLE tasks 
            ADD CONSTRAINT check_tasks_channel_id_format 
            CHECK (channel_id IS NULL OR channel_id ~ '^[0-9]{17,19}$');
            """
        ]
        
        for constraint_sql in constraints:
            try:
                await db_manager.execute(constraint_sql)
                logger.info("Constraint added successfully")
            except Exception as e:
                if "already exists" in str(e):
                    logger.info(f"Constraint already exists, skipping: {e}")
                else:
                    raise
        
        # サンプルデータ挿入（開発・テスト用）
        sample_data_sql = """
        INSERT INTO tasks (title, description, status, priority, metadata)
        SELECT 
            'Sample Task', 
            'This is a sample task for testing purposes',
            'pending',
            'medium',
            '{"sample": true, "created_by": "migration"}'::jsonb
        WHERE NOT EXISTS (
            SELECT 1 FROM tasks WHERE metadata->>'sample' = 'true'
        );
        """
        
        await db_manager.execute(sample_data_sql)
        logger.info("Sample task data inserted")
        
        logger.info("Tasks table migration completed successfully")
        
    except Exception as e:
        logger.error(f"Tasks table migration failed: {e}")
        raise


async def down(db_manager):
    """
    tasksテーブル削除マイグレーション（ロールバック）
    
    Args:
        db_manager: データベース管理インスタンス
    """
    try:
        logger.info("Starting tasks table rollback...")
        
        # トリガー削除
        await db_manager.execute("DROP TRIGGER IF EXISTS trigger_tasks_updated_at ON tasks;")
        logger.info("Updated_at trigger dropped")
        
        # トリガー関数削除
        await db_manager.execute("DROP FUNCTION IF EXISTS update_tasks_updated_at();")
        logger.info("Updated_at trigger function dropped")
        
        # テーブル削除（全インデックス・制約も自動削除）
        await db_manager.execute("DROP TABLE IF EXISTS tasks CASCADE;")
        logger.info("Tasks table dropped")
        
        logger.info("Tasks table rollback completed successfully")
        
    except Exception as e:
        logger.error(f"Tasks table rollback failed: {e}")
        raise