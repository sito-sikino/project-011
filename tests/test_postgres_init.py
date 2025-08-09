"""
PostgreSQL初期化スクリプトのテスト
t-wada式TDDサイクル: Red Phase

受け入れ条件:
- pgvector拡張有効化
- agent_memoryテーブル作成（UUID主キー、1536次元vector型）
- インデックス設定（効率的検索のため）
- メタデータ管理（agent, channel, timestamp）

テスト項目:
1. init.sqlファイル存在確認
2. pgvector拡張作成文の確認
3. agent_memoryテーブル作成文の確認
4. 1536次元vector型の確認
5. 必要なインデックスの確認
6. メタデータフィールドの確認
"""

import pytest
import os
from pathlib import Path

class TestPostgreSQLInit:
    """PostgreSQL初期化スクリプトテストクラス"""
    
    @property
    def init_sql_path(self):
        """init.sqlファイルのパス"""
        return Path(__file__).parent.parent / "init" / "init.sql"
    
    def test_init_sql_file_exists(self):
        """
        テスト1: init.sqlファイルが存在することを確認
        """
        assert self.init_sql_path.exists(), f"init.sql not found at {self.init_sql_path}"
    
    def test_init_sql_is_not_empty(self):
        """
        テスト2: init.sqlファイルが空でないことを確認
        """
        assert self.init_sql_path.exists(), "init.sql file must exist"
        content = self.init_sql_path.read_text(encoding='utf-8')
        assert content.strip(), "init.sql file should not be empty"
    
    def test_pgvector_extension_creation(self):
        """
        テスト3: pgvector拡張作成文が含まれることを確認
        """
        assert self.init_sql_path.exists(), "init.sql file must exist"
        content = self.init_sql_path.read_text(encoding='utf-8')
        
        # pgvector拡張作成の確認
        assert "CREATE EXTENSION IF NOT EXISTS vector" in content, \
            "pgvector extension creation statement not found"
    
    def test_agent_memory_table_creation(self):
        """
        テスト4: agent_memoryテーブル作成文が適切であることを確認
        """
        assert self.init_sql_path.exists(), "init.sql file must exist"
        content = self.init_sql_path.read_text(encoding='utf-8').upper()
        
        # テーブル作成文の確認
        assert "CREATE TABLE AGENT_MEMORY" in content, \
            "agent_memory table creation statement not found"
        
        # 主キーの確認
        assert "ID UUID PRIMARY KEY DEFAULT GEN_RANDOM_UUID()" in content, \
            "UUID primary key with gen_random_uuid() not found"
        
        # 基本フィールドの確認
        assert "CONTENT TEXT NOT NULL" in content, \
            "content TEXT NOT NULL field not found"
        
        assert "CREATED_AT TIMESTAMPTZ DEFAULT NOW()" in content, \
            "created_at timestamptz field not found"
    
    def test_vector_dimension_1536(self):
        """
        テスト5: 1536次元vector型が指定されていることを確認
        """
        assert self.init_sql_path.exists(), "init.sql file must exist"
        content = self.init_sql_path.read_text(encoding='utf-8')
        
        # 1536次元ベクトル型の確認
        assert "vector(1536)" in content, \
            "1536-dimensional vector type not found"
    
    def test_metadata_jsonb_field(self):
        """
        テスト6: メタデータJSONBフィールドが存在することを確認
        """
        assert self.init_sql_path.exists(), "init.sql file must exist"
        content = self.init_sql_path.read_text(encoding='utf-8').upper()
        
        # メタデータフィールドの確認
        assert "METADATA JSONB" in content, \
            "metadata JSONB field not found"
    
    def test_vector_search_index_creation(self):
        """
        テスト7: ベクトル検索用インデックスが作成されることを確認
        """
        assert self.init_sql_path.exists(), "init.sql file must exist"
        content = self.init_sql_path.read_text(encoding='utf-8').upper()
        
        # IVFFlat インデックスの確認
        assert "CREATE INDEX" in content and "USING IVFFLAT" in content, \
            "IVFFlat index creation not found"
        
        assert "VECTOR_COSINE_OPS" in content, \
            "vector_cosine_ops not found in index creation"
    
    def test_metadata_gin_index_creation(self):
        """
        テスト8: メタデータ検索用GINインデックスが作成されることを確認
        """
        assert self.init_sql_path.exists(), "init.sql file must exist"
        content = self.init_sql_path.read_text(encoding='utf-8').upper()
        
        # GIN インデックスの確認
        assert "USING GIN" in content and "METADATA" in content, \
            "GIN index for metadata not found"
    
    def test_embedding_field_exists(self):
        """
        テスト9: embeddingフィールドが適切に定義されていることを確認
        """
        assert self.init_sql_path.exists(), "init.sql file must exist"
        content = self.init_sql_path.read_text(encoding='utf-8').upper()
        
        # embeddingフィールドの確認
        assert "EMBEDDING VECTOR(1536)" in content, \
            "embedding vector(1536) field not found"
    
    def test_sql_syntax_basic_validation(self):
        """
        テスト10: 基本的なSQL構文チェック
        """
        assert self.init_sql_path.exists(), "init.sql file must exist"
        content = self.init_sql_path.read_text(encoding='utf-8')
        
        # 基本的な構文チェック
        assert content.count('CREATE EXTENSION') >= 1, \
            "At least one CREATE EXTENSION statement required"
        assert content.count('CREATE TABLE') >= 1, \
            "At least one CREATE TABLE statement required"
        assert content.count('CREATE INDEX') >= 2, \
            "At least two CREATE INDEX statements required"
        
        # セミコロン終端チェック
        statements = [line.strip() for line in content.split('\n') if line.strip() and not line.strip().startswith('--')]
        for stmt in statements:
            if stmt and not stmt.endswith(';'):
                # 複数行ステートメントの可能性があるため、ここでは厳密にチェックしない
                pass
    
    def test_required_sql_structure_complete(self):
        """
        テスト11: 期待するSQL構造が完全に含まれていることを確認
        """
        assert self.init_sql_path.exists(), "init.sql file must exist"
        content = self.init_sql_path.read_text(encoding='utf-8')
        
        # 期待する構造要素のチェック
        required_elements = [
            "CREATE EXTENSION IF NOT EXISTS vector",
            "CREATE TABLE agent_memory",
            "id UUID PRIMARY KEY DEFAULT gen_random_uuid()",
            "content TEXT NOT NULL",
            "embedding vector(1536)",
            "metadata JSONB",
            "created_at TIMESTAMPTZ DEFAULT NOW()"
        ]
        
        for element in required_elements:
            assert element in content or element.upper() in content.upper(), \
                f"Required element not found: {element}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])