"""
Docker Compose設定ファイルのテスト

Phase 1.2: docker-compose.yml作成のためのTDDテストスイート
spec.mdの要求仕様に厳密に従ったDocker設定検証
"""

import pytest
import os
import yaml
from pathlib import Path


class TestDockerCompose:
    """docker-compose.yml設定ファイルのテスト"""
    
    @pytest.fixture
    def docker_compose_file(self):
        """docker-compose.ymlファイルのパス"""
        return Path("/home/u/dev/project-011/docker-compose.yml")
    
    @pytest.fixture
    def docker_compose_content(self, docker_compose_file):
        """docker-compose.ymlの内容を読み込み"""
        with open(docker_compose_file, 'r') as f:
            return yaml.safe_load(f)
    
    def test_docker_compose_file_exists(self, docker_compose_file):
        """docker-compose.ymlファイルが存在することを確認"""
        assert docker_compose_file.exists(), "docker-compose.ymlファイルが存在しません"
    
    def test_has_required_services(self, docker_compose_content):
        """必要なサービス（redis, postgres, app）が定義されていることを確認"""
        services = docker_compose_content.get('services', {})
        
        # 必須サービスの存在確認
        assert 'redis' in services, "redisサービスが定義されていません"
        assert 'postgres' in services, "postgresサービスが定義されていません"
        assert 'app' in services, "appサービスが定義されていません"
    
    def test_redis_configuration(self, docker_compose_content):
        """Redisサービスの設定が適切であることを確認"""
        redis = docker_compose_content['services']['redis']
        
        # イメージ確認
        assert redis.get('image') == 'redis:7-alpine', \
            f"Redisイメージが不正です。期待値: redis:7-alpine, 実際: {redis.get('image')}"
        
        # ポート確認
        ports = redis.get('ports', [])
        expected_port = "6379:6379"
        assert expected_port in ports, \
            f"Redisポート設定が不正です。期待値に{expected_port}が含まれていません"
        
        # ヘルスチェック確認
        healthcheck = redis.get('healthcheck', {})
        assert healthcheck is not None, "Redisヘルスチェック設定が存在しません"
        
        # ヘルスチェックコマンド確認
        test_cmd = healthcheck.get('test', [])
        assert test_cmd == ["CMD", "redis-cli", "ping"], \
            f"Redisヘルスチェックコマンドが不正です。期待値: ['CMD', 'redis-cli', 'ping'], 実際: {test_cmd}"
        
        # ヘルスチェック間隔確認（10秒）
        assert healthcheck.get('interval') == '10s', \
            f"Redisヘルスチェック間隔が不正です。期待値: 10s, 実際: {healthcheck.get('interval')}"
        
        # タイムアウト確認
        assert healthcheck.get('timeout') == '5s', \
            f"Redisヘルスチェックタイムアウトが不正です。期待値: 5s, 実際: {healthcheck.get('timeout')}"
        
        # リトライ回数確認（spec.mdではRedisも5回）
        assert healthcheck.get('retries') == 5, \
            f"Redisヘルスチェックリトライ回数が不正です。期待値: 5, 実際: {healthcheck.get('retries')}"
        
        # 開始期間確認
        assert healthcheck.get('start_period') == '10s', \
            f"Redisヘルスチェック開始期間が不正です。期待値: 10s, 実際: {healthcheck.get('start_period')}"
    
    def test_postgres_configuration(self, docker_compose_content):
        """PostgreSQLサービスの設定が適切であることを確認"""
        postgres = docker_compose_content['services']['postgres']
        
        # イメージ確認
        assert postgres.get('image') == 'pgvector/pgvector:pg16', \
            f"PostgreSQLイメージが不正です。期待値: pgvector/pgvector:pg16, 実際: {postgres.get('image')}"
        
        # ポート確認
        ports = postgres.get('ports', [])
        expected_port = "5432:5432"
        assert expected_port in ports, \
            f"PostgreSQLポート設定が不正です。期待値に{expected_port}が含まれていません"
        
        # ヘルスチェック確認
        healthcheck = postgres.get('healthcheck', {})
        assert healthcheck is not None, "PostgreSQLヘルスチェック設定が存在しません"
        
        # ヘルスチェックコマンド確認
        test_cmd = healthcheck.get('test', [])
        expected_cmd = ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-discord_user}"]
        assert test_cmd == expected_cmd, \
            f"PostgreSQLヘルスチェックコマンドが不正です。期待値: {expected_cmd}, 実際: {test_cmd}"
        
        # ヘルスチェック間隔確認（spec.mdでは15秒）
        assert healthcheck.get('interval') == '15s', \
            f"PostgreSQLヘルスチェック間隔が不正です。期待値: 15s, 実際: {healthcheck.get('interval')}"
        
        # タイムアウト確認（spec.mdでは10秒）
        assert healthcheck.get('timeout') == '10s', \
            f"PostgreSQLヘルスチェックタイムアウトが不正です。期待値: 10s, 実際: {healthcheck.get('timeout')}"
        
        # リトライ回数確認
        assert healthcheck.get('retries') == 5, \
            f"PostgreSQLヘルスチェックリトライ回数が不正です。期待値: 5, 実際: {healthcheck.get('retries')}"
        
        # 開始期間確認（spec.mdでは30秒）
        assert healthcheck.get('start_period') == '30s', \
            f"PostgreSQLヘルスチェック開始期間が不正です。期待値: 30s, 実際: {healthcheck.get('start_period')}"
    
    def test_app_service_dependencies(self, docker_compose_content):
        """appサービスの依存関係設定が適切であることを確認"""
        app = docker_compose_content['services']['app']
        
        # depends_on設定確認
        depends_on = app.get('depends_on', {})
        assert depends_on is not None, "appサービスにdepends_on設定が存在しません"
        
        # Redis依存関係確認
        redis_dep = depends_on.get('redis', {})
        assert redis_dep.get('condition') == 'service_healthy', \
            f"Redis依存関係条件が不正です。期待値: service_healthy, 実際: {redis_dep.get('condition')}"
        
        # PostgreSQL依存関係確認
        postgres_dep = depends_on.get('postgres', {})
        assert postgres_dep.get('condition') == 'service_healthy', \
            f"PostgreSQL依存関係条件が不正です。期待値: service_healthy, 実際: {postgres_dep.get('condition')}"
    
    def test_app_service_basic_configuration(self, docker_compose_content):
        """appサービスの基本設定確認"""
        app = docker_compose_content['services']['app']
        
        # ビルド設定確認
        assert 'build' in app, "appサービスにbuild設定が存在しません"
        build_context = app.get('build')
        
        # context確認（現在のディレクトリ）
        if isinstance(build_context, dict):
            assert build_context.get('context') == '.', \
                f"appサービスのビルドコンテキストが不正です。期待値: ., 実際: {build_context.get('context')}"
        elif isinstance(build_context, str):
            assert build_context == '.', \
                f"appサービスのビルドコンテキストが不正です。期待値: ., 実際: {build_context}"
    
    def test_yaml_structure_validity(self, docker_compose_content):
        """YAML構造の妥当性確認"""
        # version指定確認（Docker Compose v3.8以上）
        version = docker_compose_content.get('version', '3.8')
        assert version in ['3.8', '3.9', '3'], \
            f"Docker Composeバージョンが不正です。期待値: 3.8/3.9/3, 実際: {version}"
        
        # services セクションの存在確認
        assert 'services' in docker_compose_content, \
            "docker-compose.ymlにservicesセクションが存在しません"
        
        services = docker_compose_content['services']
        assert isinstance(services, dict), \
            "servicesセクションが辞書形式ではありません"
        
        assert len(services) >= 3, \
            f"サービス数が不足しています。期待値: 3以上, 実際: {len(services)}"
    
    def test_environment_variables_integration(self, docker_compose_content):
        """環境変数統合の確認"""
        postgres = docker_compose_content['services']['postgres']
        
        # 環境変数設定確認
        environment = postgres.get('environment', {})
        if environment:
            # PostgreSQL環境変数の確認（設定されている場合）
            if 'POSTGRES_DB' in environment:
                assert environment['POSTGRES_DB'] == 'discord_agent', \
                    f"POSTGRES_DB設定が不正です。期待値: discord_agent, 実際: {environment.get('POSTGRES_DB')}"
            
            if 'POSTGRES_USER' in environment:
                assert environment['POSTGRES_USER'] == 'discord_user', \
                    f"POSTGRES_USER設定が不正です。期待値: discord_user, 実際: {environment.get('POSTGRES_USER')}"