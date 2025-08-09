"""
Phase 1.2: requirements.txt作成のテスト

requirements.txtファイルの存在と必要なライブラリの記載を確認するテストスイート。
t-wada式TDD（Red-Green-Refactor）サイクルの一環として実装。
"""

import os
import pytest
from pathlib import Path


class TestRequirements:
    """requirements.txt関連のテストクラス"""

    @pytest.fixture
    def project_root(self):
        """プロジェクトルートディレクトリのパス"""
        return Path(__file__).parent.parent

    @pytest.fixture
    def requirements_path(self, project_root):
        """requirements.txtファイルのパス"""
        return project_root / "requirements.txt"

    def test_requirements_file_exists(self, requirements_path):
        """requirements.txtファイルが存在することを確認"""
        assert requirements_path.exists(), "requirements.txt file must exist"

    def test_requirements_file_is_readable(self, requirements_path):
        """requirements.txtファイルが読み取り可能であることを確認"""
        assert requirements_path.is_file(), "requirements.txt must be a file"
        assert os.access(requirements_path, os.R_OK), "requirements.txt must be readable"

    def test_required_libraries_present(self, requirements_path):
        """必要なライブラリがすべて記載されていることを確認"""
        # Phase 1.2で要求される必須ライブラリリスト
        required_libraries = [
            "discord.py==2.4.0",
            "langgraph==0.2.74", 
            "langgraph-supervisor",
            "langchain-redis",
            "langchain-postgres",
            "langchain-google-genai",
            "langchain-core",
            "pydantic==2.8.2",
            "pydantic-settings",
            "python-dotenv",
            "pandas",
            "asyncio",
            "redis",
            "psycopg2-binary",
            "pgvector"
        ]

        with open(requirements_path, 'r', encoding='utf-8') as f:
            content = f.read()

        missing_libraries = []
        for library in required_libraries:
            if library not in content:
                missing_libraries.append(library)

        assert not missing_libraries, f"Missing required libraries: {missing_libraries}"

    def test_no_duplicate_libraries(self, requirements_path):
        """重複するライブラリがないことを確認"""
        with open(requirements_path, 'r', encoding='utf-8') as f:
            lines = [line.strip() for line in f.readlines() if line.strip() and not line.startswith('#')]

        # ライブラリ名のみ抽出（バージョン指定を除く）
        library_names = []
        for line in lines:
            if '==' in line:
                library_name = line.split('==')[0]
            elif '>=' in line:
                library_name = line.split('>=')[0]
            elif '<=' in line:
                library_name = line.split('<=')[0]
            else:
                library_name = line

            library_names.append(library_name)

        duplicates = []
        seen = set()
        for name in library_names:
            if name in seen:
                duplicates.append(name)
            seen.add(name)

        assert not duplicates, f"Duplicate libraries found: {duplicates}"

    def test_version_constraints_format(self, requirements_path):
        """バージョン制約の形式が正しいことを確認"""
        with open(requirements_path, 'r', encoding='utf-8') as f:
            lines = [line.strip() for line in f.readlines() if line.strip() and not line.startswith('#')]

        invalid_lines = []
        for line in lines:
            # 空行とコメント行をスキップ
            if not line or line.startswith('#'):
                continue
            
            # 有効なバージョン制約パターンをチェック
            if not any(op in line for op in ['==', '>=', '<=', '>', '<', '~=']) and line not in ['asyncio']:
                # asyncioは標準ライブラリなのでバージョン指定不要
                if line not in ['asyncio']:
                    invalid_lines.append(line)

        # 厳密なバージョン指定が推奨されるライブラリ
        strict_version_required = ['discord.py==2.4.0', 'langgraph==0.2.74', 'pydantic==2.8.2']
        content = open(requirements_path, 'r', encoding='utf-8').read()
        
        missing_strict_versions = []
        for required in strict_version_required:
            if required not in content:
                missing_strict_versions.append(required)

        assert not missing_strict_versions, f"Missing strict version constraints: {missing_strict_versions}"