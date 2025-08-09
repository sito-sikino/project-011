"""
プロジェクト構造の存在確認テスト

Phase 1.1: プロジェクト構造作成のTDDサイクル実装
時刻: 2025-08-09 15:37:05
"""

import os
import pytest
from pathlib import Path


class TestProjectStructure:
    """プロジェクト構造の存在確認"""
    
    @pytest.fixture
    def project_root(self):
        """プロジェクトルートパスを取得"""
        return Path(__file__).parent.parent
    
    def test_app_directory_structure(self, project_root):
        """app/ディレクトリと各サブディレクトリが存在することを確認"""
        app_dir = project_root / "app"
        assert app_dir.exists(), "app/ディレクトリが存在しません"
        assert app_dir.is_dir(), "app/がディレクトリではありません"
        
        # サブディレクトリの確認
        expected_subdirs = ["core", "discord_manager", "langgraph", "tasks"]
        for subdir in expected_subdirs:
            subdir_path = app_dir / subdir
            assert subdir_path.exists(), f"app/{subdir}/ディレクトリが存在しません"
            assert subdir_path.is_dir(), f"app/{subdir}/がディレクトリではありません"
    
    def test_init_files_exist(self, project_root):
        """各ディレクトリの__init__.pyファイルが存在することを確認"""
        app_dir = project_root / "app"
        
        # __init__.pyファイルの確認
        expected_init_files = [
            "core/__init__.py",
            "discord_manager/__init__.py", 
            "langgraph/__init__.py",
            "tasks/__init__.py"
        ]
        
        for init_file in expected_init_files:
            init_path = app_dir / init_file
            assert init_path.exists(), f"app/{init_file}が存在しません"
            assert init_path.is_file(), f"app/{init_file}がファイルではありません"
    
    def test_core_module_files(self, project_root):
        """core/モジュールの各ファイルが存在することを確認"""
        core_dir = project_root / "app" / "core"
        
        expected_files = ["settings.py", "database.py", "memory.py", "report.py"]
        for file_name in expected_files:
            file_path = core_dir / file_name
            assert file_path.exists(), f"app/core/{file_name}が存在しません"
            assert file_path.is_file(), f"app/core/{file_name}がファイルではありません"
    
    def test_discord_manager_files(self, project_root):
        """discord_manager/モジュールファイルが存在することを確認"""
        discord_dir = project_root / "app" / "discord_manager"
        manager_file = discord_dir / "manager.py"
        
        assert manager_file.exists(), "app/discord_manager/manager.pyが存在しません"
        assert manager_file.is_file(), "app/discord_manager/manager.pyがファイルではありません"
    
    def test_langgraph_files(self, project_root):
        """langgraph/モジュールファイルが存在することを確認"""
        langgraph_dir = project_root / "app" / "langgraph"
        
        expected_files = ["supervisor.py", "agents.py"]
        for file_name in expected_files:
            file_path = langgraph_dir / file_name
            assert file_path.exists(), f"app/langgraph/{file_name}が存在しません"
            assert file_path.is_file(), f"app/langgraph/{file_name}がファイルではありません"
    
    def test_tasks_files(self, project_root):
        """tasks/モジュールファイルが存在することを確認"""
        tasks_dir = project_root / "app" / "tasks"
        manager_file = tasks_dir / "manager.py"
        
        assert manager_file.exists(), "app/tasks/manager.pyが存在しません"
        assert manager_file.is_file(), "app/tasks/manager.pyがファイルではありません"
    
    def test_main_py_exists(self, project_root):
        """app/main.pyが存在することを確認"""
        main_file = project_root / "app" / "main.py"
        
        assert main_file.exists(), "app/main.pyが存在しません"
        assert main_file.is_file(), "app/main.pyがファイルではありません"
    
    def test_tests_directory_exists(self, project_root):
        """tests/ディレクトリが存在することを確認"""
        tests_dir = project_root / "tests"
        
        assert tests_dir.exists(), "tests/ディレクトリが存在しません"
        assert tests_dir.is_dir(), "tests/がディレクトリではありません"
        
        # 既存のテストファイルも確認
        existing_test_files = list(tests_dir.glob("test_*.py"))
        assert len(existing_test_files) > 0, "tests/ディレクトリにテストファイルが存在しません"