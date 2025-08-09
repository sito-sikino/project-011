"""
Dockerfile設定のテスト

受け入れ条件:
- Python 3.11基盤、requirements.txtインストール、エントリポイント設定
- マルチステージビルド（効率性考慮）
- 適切なワーキングディレクトリ設定
- 非rootユーザーでの実行（セキュリティ）
"""

import os
import re
from pathlib import Path


class TestDockerfile:
    """Dockerfileが正しく設定されているかテスト"""
    
    def test_dockerfile_exists(self):
        """Dockerfileファイルが存在することを確認"""
        dockerfile_path = Path("Dockerfile")
        assert dockerfile_path.exists(), "Dockerfileが存在しません"
    
    def test_dockerfile_uses_python_311(self):
        """Python 3.11基盤を使用していることを確認"""
        with open("Dockerfile", "r") as f:
            content = f.read()
        
        # Python 3.11を使用している
        assert re.search(r"FROM\s+python:3\.11", content), \
            "Python 3.11基盤が設定されていません"
    
    def test_dockerfile_has_requirements_handling(self):
        """requirements.txtの処理が含まれることを確認"""
        with open("Dockerfile", "r") as f:
            content = f.read()
        
        # requirements.txtをコピー
        assert "COPY requirements.txt" in content, \
            "requirements.txtのコピーが設定されていません"
        
        # pip installでrequirements.txtをインストール
        assert re.search(r"RUN\s+pip\s+install.*requirements\.txt", content), \
            "requirements.txtのインストールが設定されていません"
    
    def test_dockerfile_has_workdir(self):
        """適切なワーキングディレクトリが設定されていることを確認"""
        with open("Dockerfile", "r") as f:
            content = f.read()
        
        assert re.search(r"WORKDIR\s+/app", content), \
            "ワーキングディレクトリ(/app)が設定されていません"
    
    def test_dockerfile_has_entrypoint(self):
        """エントリポイントが適切に設定されていることを確認"""
        with open("Dockerfile", "r") as f:
            content = f.read()
        
        # CMDまたはENTRYPOINTでmain.pyの実行が設定されている
        assert (re.search(r"CMD.*python.*main", content) or 
                re.search(r"ENTRYPOINT.*python.*main", content)), \
            "エントリポイント設定がありません"
    
    def test_dockerfile_has_app_copy(self):
        """アプリケーションファイルのコピーが設定されていることを確認"""
        with open("Dockerfile", "r") as f:
            content = f.read()
        
        # app/ディレクトリをコピー
        assert re.search(r"COPY.*app.*app", content), \
            "app/ディレクトリのコピーが設定されていません"
    
    def test_dockerfile_uses_multistage_build(self):
        """マルチステージビルドが使用されていることを確認"""
        with open("Dockerfile", "r") as f:
            content = f.read()
        
        # マルチステージビルドの形跡（ASまたは複数のFROM）
        from_count = len(re.findall(r"^FROM\s+", content, re.MULTILINE))
        as_usage = re.search(r"AS\s+\w+", content)
        
        assert from_count >= 2 or as_usage, \
            "マルチステージビルドが設定されていません"
    
    def test_dockerfile_has_security_practices(self):
        """セキュリティベストプラクティスが適用されていることを確認"""
        with open("Dockerfile", "r") as f:
            content = f.read()
        
        # 非rootユーザーの作成・使用
        assert re.search(r"RUN.*adduser|useradd", content), \
            "非rootユーザーの作成が設定されていません"
        
        assert re.search(r"USER\s+\w+", content), \
            "非rootユーザーでの実行が設定されていません"
    
    def test_dockerfile_has_pip_optimization(self):
        """pip最適化オプションが設定されていることを確認"""
        with open("Dockerfile", "r") as f:
            content = f.read()
        
        # --no-cache-dirオプションを使用
        assert "--no-cache-dir" in content, \
            "pip最適化オプション(--no-cache-dir)が設定されていません"


class TestDockerignore:
    """dockerignoreファイルのテスト"""
    
    def test_dockerignore_exists(self):
        """.dockerignoreファイルが存在することを確認"""
        dockerignore_path = Path(".dockerignore")
        assert dockerignore_path.exists(), ".dockerignoreが存在しません"
    
    def test_dockerignore_excludes_unnecessary_files(self):
        """.dockerignoreで不要ファイルが除外されていることを確認"""
        with open(".dockerignore", "r") as f:
            content = f.read()
        
        # 基本的な除外項目
        required_excludes = [
            "__pycache__",
            "*.pyc", 
            ".git",
            ".env",
            "venv",
            "tests",
            "_docs"
        ]
        
        for exclude in required_excludes:
            assert exclude in content, f"{exclude}が.dockerignoreに含まれていません"


class TestDockerfileStructure:
    """Dockerfileの構造的テスト"""
    
    def test_dockerfile_layer_optimization(self):
        """レイヤー最適化が適切に行われていることを確認"""
        with open("Dockerfile", "r") as f:
            lines = f.readlines()
        
        # requirements.txtのコピーとインストールが、アプリコピーより前にある
        req_copy_line = -1
        app_copy_line = -1
        
        for i, line in enumerate(lines):
            if "COPY requirements.txt" in line:
                req_copy_line = i
            elif re.search(r"COPY.*app", line):
                app_copy_line = i
        
        assert req_copy_line < app_copy_line, \
            "レイヤー最適化: requirements.txtコピーはapp/コピーより前に配置してください"
    
    def test_dockerfile_minimal_base_image(self):
        """最小限のベースイメージが使用されていることを確認"""
        with open("Dockerfile", "r") as f:
            content = f.read()
        
        # slimまたはalpineベースの使用を推奨
        assert re.search(r"python:3\.11-(slim|alpine)", content), \
            "最小限のベースイメージ(slim/alpine)の使用を推奨"