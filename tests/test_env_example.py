"""
.env.exampleファイルのテストスイート
t-wada式TDDサイクル - Red Phase
"""
import os
import re
from pathlib import Path
import pytest


class TestEnvExample:
    """
    .env.exampleファイルの存在・構造・内容を検証するテスト
    """
    
    def setup_method(self):
        """テスト前準備"""
        self.project_root = Path(__file__).parent.parent
        self.env_example_path = self.project_root / ".env.example"
    
    def test_env_example_exists(self):
        """
        Test: .env.exampleファイルが存在すること
        """
        assert self.env_example_path.exists(), ".env.example file must exist in project root"
    
    def test_env_example_is_file(self):
        """
        Test: .env.exampleがファイルであること（ディレクトリではない）
        """
        assert self.env_example_path.is_file(), ".env.example must be a file, not a directory"
    
    def test_env_example_has_required_discord_tokens(self):
        """
        Test: 必須のDiscord Token設定が含まれていること
        """
        content = self.env_example_path.read_text(encoding='utf-8')
        
        # Discord Token群の検証
        required_discord_tokens = [
            "SPECTRA_TOKEN=",
            "LYNQ_TOKEN=",
            "PAZ_TOKEN="
        ]
        
        for token in required_discord_tokens:
            assert token in content, f"Missing required Discord token: {token}"
    
    def test_env_example_has_gemini_api_config(self):
        """
        Test: Gemini API設定が含まれていること
        """
        content = self.env_example_path.read_text(encoding='utf-8')
        assert "GEMINI_API_KEY=" in content, "Missing GEMINI_API_KEY configuration"
    
    def test_env_example_has_database_configs(self):
        """
        Test: データベース設定が含まれていること
        """
        content = self.env_example_path.read_text(encoding='utf-8')
        
        # Database設定群の検証
        required_db_configs = [
            "REDIS_URL=redis://redis:6379",
            "DATABASE_URL=postgresql://user:pass@postgres:5432/dbname"
        ]
        
        for config in required_db_configs:
            assert config in content, f"Missing required database config: {config}"
    
    def test_env_example_has_environment_configs(self):
        """
        Test: 環境設定が含まれていること
        """
        content = self.env_example_path.read_text(encoding='utf-8')
        
        # Environment設定群の検証
        required_env_configs = [
            "ENV=development",
            "LOG_LEVEL=INFO"
        ]
        
        for config in required_env_configs:
            assert config in content, f"Missing required environment config: {config}"
    
    def test_env_example_has_proper_format(self):
        """
        Test: KEY=VALUE形式であること（コメント行は除く）
        """
        content = self.env_example_path.read_text(encoding='utf-8')
        lines = content.strip().split('\n')
        
        # 空行とコメント行を除外
        config_lines = [
            line.strip() for line in lines 
            if line.strip() and not line.strip().startswith('#')
        ]
        
        # KEY=VALUE形式の検証
        key_value_pattern = re.compile(r'^[A-Z_][A-Z0-9_]*=.*$')
        
        for line in config_lines:
            assert key_value_pattern.match(line), f"Invalid format line: {line}"
    
    def test_env_example_has_appropriate_comments(self):
        """
        Test: 適切なコメントが含まれていること
        """
        content = self.env_example_path.read_text(encoding='utf-8')
        
        # コメント群の検証
        expected_comment_sections = [
            "# Discord Bot Tokens",
            "# Gemini API",
            "# Database", 
            "# Environment"
        ]
        
        for comment in expected_comment_sections:
            assert comment in content, f"Missing required comment section: {comment}"
    
    def test_env_example_contains_no_actual_secrets(self):
        """
        Test: 実際のシークレット値が含まれていないこと
        """
        content = self.env_example_path.read_text(encoding='utf-8')
        
        # 危険なパターンをチェック
        dangerous_patterns = [
            r'TOKEN=[^=\s].*[A-Za-z0-9]{10}',  # 実際のトークンらしき文字列
            r'API_KEY=[^=\s].*[A-Za-z0-9]{10}',  # 実際のAPIキーらしき文字列
            r'password.*[^=]\w+',  # 実際のパスワード
        ]
        
        for pattern in dangerous_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            assert not matches, f"Potential secret detected: {matches}"
    
    def test_env_example_line_count_reasonable(self):
        """
        Test: 適切な行数であること（コメント込みで15-30行程度）
        """
        content = self.env_example_path.read_text(encoding='utf-8')
        lines = content.strip().split('\n')
        
        # 空行を除いた実際のコンテンツ行数
        non_empty_lines = [line for line in lines if line.strip()]
        
        assert 15 <= len(non_empty_lines) <= 30, f"Line count should be 15-30, got {len(non_empty_lines)}"
    
    def test_env_example_encoding_is_utf8(self):
        """
        Test: UTF-8エンコーディングで読み込めること
        """
        try:
            content = self.env_example_path.read_text(encoding='utf-8')
            # UTF-8で読み込めれば成功
            assert len(content) > 0, ".env.example should have content"
        except UnicodeDecodeError:
            pytest.fail(".env.example should be UTF-8 encoded")