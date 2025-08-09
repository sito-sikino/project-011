-- ================================================
-- PostgreSQL初期化スクリプト
-- Discord Multi-Agent System用データベース初期化
-- ================================================
-- 
-- 【仕様詳細】
-- - pgvector拡張: 1536次元ベクトル対応、gemini-embedding-001統合
-- - agent_memoryテーブル: 長期記憶ストレージ、LangChain統合
-- - ベクトル検索最適化: IVFFlat + コサイン類似度
-- - メタデータ高速検索: GINインデックス
-- 
-- 【互換性】
-- - pgvector: pg16 compatible
-- - gemini-embedding-001: output_dimensionality=1536
-- - LangChain PGVectorStore統合
-- 
-- 作成日: 2025-08-09 16:05
-- TDD実装: t-wada式サイクル（Red→Green→Refactor）
-- ================================================

-- Step 1: pgvector拡張の有効化
-- 1536次元ベクトル操作を可能にする
CREATE EXTENSION IF NOT EXISTS vector;

-- Step 2: agent_memoryテーブル作成
-- Discord Multi-Agent間の長期記憶共有テーブル
CREATE TABLE agent_memory (
    -- プライマリキー: UUID自動生成
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- メッセージ内容: NULL不可
    content TEXT NOT NULL,
    
    -- 埋め込みベクトル: 1536次元（gemini-embedding-001）
    embedding vector(1536),
    
    -- メタデータ: agent名、channel名、timestamp等
    metadata JSONB,
    
    -- 作成日時: タイムゾーン付きタイムスタンプ
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Step 3: ベクトル検索用インデックス
-- IVFFlat方式 + コサイン類似度による高速セマンティック検索
-- lists=100: 1536次元に最適化されたクラスター数
CREATE INDEX idx_agent_memory_embedding 
    ON agent_memory 
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

-- Step 4: メタデータ検索用GINインデックス
-- agent、channel、timestampなどのJSONBメタデータ高速検索
CREATE INDEX idx_agent_memory_metadata 
    ON agent_memory 
    USING gin (metadata);

-- Step 5: パフォーマンス最適化
-- created_at降順インデックス（時系列データに最適）
CREATE INDEX idx_agent_memory_created_at 
    ON agent_memory (created_at DESC);

-- 初期化完了
-- テーブル構造とインデックスの確認用コメント
-- テーブル: agent_memory (id, content, embedding, metadata, created_at)
-- インデックス: embedding(IVFFlat), metadata(GIN), created_at(BTree)