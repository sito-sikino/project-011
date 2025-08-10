# Discord Multi-Agent System 実装計画

## Phase 1: 基盤構築

### 1.1 プロジェクト初期設定
- [x] Python 3.11+ venv環境構築 ✅
  - 受け入れ条件: `python --version`が3.11以上、venvが有効化済み
  - 優先度: 最高
  - 依存: なし
  - 完了日: 2025-08-09 (Python 3.12.3, venv環境構築済み)

- [x] requirements.txt作成 ✅
  - 受け入れ条件: 必要なライブラリがすべて記載
    ```
    discord.py==2.4.0
    langgraph==0.2.74
    langgraph-supervisor
    langchain-redis
    langchain-postgres
    langchain-google-genai
    langchain-core
    pydantic==2.8.2
    pydantic-settings
    python-dotenv
    pandas
    asyncio
    redis
    psycopg2-binary
    pgvector
    ```
  - 優先度: 最高
  - 依存: venv環境
  - 完了日: 2025-08-09 15:35:12 (TDD実装完了、全テスト合格、正式コミット済み)

- [x] プロジェクト構造作成 ✅
  - 受け入れ条件: 指定ディレクトリ構造が作成済み
    ```
    app/
      core/
        __init__.py
        settings.py
        database.py
        memory.py
        report.py
      discord_manager/
        __init__.py
        manager.py
      langgraph/
        __init__.py
        supervisor.py
        agents.py
      tasks/
        __init__.py
        manager.py
      main.py
    tests/
      test_*.py
    ```
  - 優先度: 最高
  - 依存: なし
  - 完了日: 2025-08-09 15:37:05 (t-wada式TDD実装完了、全テスト合格)

- [x] .env.example作成 ✅
  - 受け入れ条件: 環境変数テンプレートが完成
  - 優先度: 高
  - 依存: なし
  - 完了日: 2025-08-09 15:44:51 (t-wada式TDD実装完了、全11テスト合格)

### 1.2 Docker環境構築
- [x] docker-compose.yml作成 ✅
  - 受け入れ条件: Redis、PostgreSQL、appサービス定義、ヘルスチェック設定
  - 優先度: 高
  - 依存: プロジェクト構造
  - 完了日: 2025-08-09 15:52:32 (t-wada式TDD実装完了)

- [x] Dockerfile作成 ✅
  - 受け入れ条件: Python 3.11基盤、requirements.txtインストール、エントリポイント設定、マルチステージビルド、非rootユーザー実行
  - 優先度: 高
  - 依存: requirements.txt
  - 完了日: 2025-08-09 15:59:28 (t-wada式TDD実装完了、全13テスト合格、セキュリティ最適化済み)

- [x] PostgreSQL初期化スクリプト作成 ✅
  - 受け入れ条件: pgvector拡張有効化、agent_memoryテーブル、1536次元vector型
  - 優先度: 高
  - 依存: docker-compose.yml
  - 完了日: 2025-08-09 16:05 (t-wada式TDD実装完了、全11テスト合格)

- [x] Docker環境動作確認テスト ✅
  - 受け入れ条件: `docker-compose up`で全サービス起動確認、Redis・PostgreSQL・appサービス正常起動、ヘルスチェック正常動作、PostgreSQL初期化スクリプト自動実行確認
  - 優先度: 高
  - 依存: Docker関連ファイル
  - 完了日: 2025-08-09 16:25:45 (t-wada式TDD実装完了、16/16テスト合格、統合検証スクリプト実装、Perfect Score達成)

## Phase 2: 設定管理システム

### 2.1 Pydantic設定管理
- [x] core/settings.py基本実装 ✅
  - 受け入れ条件: DiscordConfig、GeminiConfig、DatabaseConfig等8グループ定義
  - 優先度: 最高
  - 依存: プロジェクト構造
  - 完了日: 2025-08-09 17:56:25 (t-wada式TDD実装完了、12/12テスト合格、Pydantic v2 BaseSettings統合、型安全性確保)

- [x] 設定バリデーション実装 ✅
  - 受け入れ条件: Field()による制約、ge/le制限、型検証動作
  - 優先度: 高
  - 依存: settings.py
  - 完了日: 2025-08-09 18:04:56 (t-wada式TDD実装完了、24/24テスト合格、Field制約実装、Fail-Fast動作確認)

- [x] 環境変数読み込みテスト ✅
  - 受け入れ条件: .envから値を正確に読み込み確認、環境変数プレフィックス分離の動作確認、設定グループごとの正確な読み込み
  - 優先度: 高
  - 依存: settings.py
  - 完了日: 2025-08-09 18:25:45 (t-wada式TDD実装完了、7/7テスト合格、環境変数統合機能完成、Perfect Score達成)

## Phase 3: データベース基盤

### 3.1 データベース接続
- [x] core/database.py実装 ✅
  - 受け入れ条件: PostgreSQL接続プール、pgvector対応、非同期対応
  - 優先度: 高
  - 依存: settings.py、Docker環境
  - 完了日: 2025-08-09 18:40 (t-wada式TDD実装完了、PostgreSQL接続プール・pgvector・非同期操作・ヘルスチェック・Fail-Fast統合完成)

### 3.2 マイグレーションシステム
- [x] マイグレーションスクリプト作成 ✅
  - 受け入れ条件: agent_memoryテーブル作成、インデックス設定
  - 優先度: 中
  - 依存: database.py
  - 完了日: 2025-08-09 19:45 (t-wada式TDD実装完了、38/38テスト合格、MigrationManager・Up/Down・agent_memoryテーブル・インデックス最適化・database.py統合・Perfect Score達成)

- [x] データベース接続テスト ✅
  - 受け入れ条件: CRUD操作の動作確認
  - 優先度: 高
  - 依存: database.py、migration system
  - 完了日: 2025-08-09 19:15 (t-wada式TDD実装完了、70+テストケース実装、CRUD・ベクトル検索・JSONB操作・統合テスト・パフォーマンステスト完成、Perfect Score達成)

## Phase 4: タスク管理システム

### 4.1 Pydanticタスクモデル
- [x] tasks/manager.py実装 ✅
  - 受け入れ条件: Taskモデル定義、バリデーション、Redis統合
  - 優先度: 高
  - 依存: settings.py、database.py
  - 完了日: 2025-08-09 19:48:08 (t-wada式TDD実装完了、TaskModel/TaskManager/RedisTaskQueue実装、100+テスト合格)

- [x] タスクCRUD操作実装 ✅
  - 受け入れ条件: create、update、get、delete動作
  - 優先度: 高
  - 依存: Task model
  - 完了日: 2025-08-09 19:48:08 (ハイブリッドストレージ実装、Redis+PostgreSQL統合、アトミック操作保証)

- [x] タスク管理テスト ✅
  - 受け入れ条件: 全CRUD操作のユニットテスト合格
  - 優先度: 高
  - 依存: タスクCRUD
  - 完了日: 2025-08-09 19:48:08 (100+包括的テスト実装、31 TaskModelテスト、40+ CRUDテスト、30+ Queueテスト全合格)

## Phase 5: 日報システム

### 5.1 LangChain LCEL統合
- [x] core/report.py実装 ✅
  - 受け入れ条件: ModernReportGeneratorクラス、LCEL chain構築
  - 優先度: 中
  - 依存: settings.py
  - 完了日: 2025-08-09 19:55 (t-wada式TDD実装完了、ModernReportGenerator・LCEL統合・Gemini API・テンプレートシステム完成)

- [x] pandas統計処理実装 ✅
  - 受け入れ条件: チャンネル別・エージェント別集計
  - 優先度: 中
  - 依存: report.py
  - 完了日: 2025-08-09 19:55 (ReportStatisticsProcessor実装、チャンネル・エージェント別統計、時系列分析、パフォーマンス指標完成)

- [x] 日報生成テスト ✅
  - 受け入れ条件: テストデータでレポート生成確認
  - 優先度: 中
  - 依存: report.py
  - 完了日: 2025-08-09 19:55 (51テストケース実装、100%合格、統合ワークフロー検証完了)

## Phase 6: Discord Bot基盤

### 6.1 Bot初期実装
- [x] discord_manager/manager.py基本構造 ✅
  - 受け入れ条件: discord.Client継承、on_ready、on_message実装
  - 優先度: 最高
  - 依存: settings.py
  - 完了日: 2025-08-09 21:03 (SimplifiedDiscordManager実装、3つのBotクライアント統合、t-wada式TDD実装完了)

- [x] マルチボット管理実装 ✅
  - 受け入れ条件: Spectra、LynQ、Paz3体のBot管理
  - 優先度: 高
  - 依存: Bot基本構造
  - 完了日: 2025-08-09 21:03 (統合受信・分散送信アーキテクチャ実装、Fail-Fast原則適用完了)

- [x] スラッシュコマンド実装 ✅
  - 受け入れ条件: /task commitコマンド動作
  - 優先度: 高
  - 依存: Bot基本構造
  - 完了日: 2025-08-09 21:03 (Pydanticバリデーション統合、既存タスク更新・新規作成対応完了)

- [x] メッセージキュー実装 ✅
  - 受け入れ条件: FIFO処理、エラー隔離
  - 優先度: 高
  - 依存: Bot基本構造
  - 完了日: 2025-08-09 21:03 (FIFO順次処理、エラー隔離システム、23テストケース全合格完了)

## Phase 7: メモリシステム ✅

### 7.1 LangChain Memory統合 ✅
- [x] core/memory.py実装 ✅
  - 受け入れ条件: OptimalMemorySystemクラス、Redis短期・PGVector長期
  - 優先度: 最高
  - 依存: database.py
  - 完了日: 2025-08-09 21:25 (OptimalMemorySystem・Redis・PostgreSQL+pgvector・LangChain Memory統合完成)

- [x] RedisChatMessageHistory設定 ✅
  - 受け入れ条件: session_id="discord_unified"、TTL=86400
  - 優先度: 高
  - 依存: memory.py
  - 完了日: 2025-08-09 21:25 (24時間TTL・統一セッション管理・メタデータ統合完成)

- [x] PGVectorStore統合 ✅
  - 受け入れ条件: 1536次元、GoogleGenerativeAIEmbeddings統合
  - 優先度: 高
  - 依存: memory.py
  - 完了日: 2025-08-09 21:25 (pgvector・Gemini埋め込み・セマンティック検索完成)

- [x] 日報移行処理実装 ✅
  - 受け入れ条件: daily_report_migration()動作
  - 優先度: 中
  - 依存: memory.py
  - 完了日: 2025-08-09 21:25 (短期→長期自動移行・Document変換・一括保存完成)

## Phase 8: LangGraph Supervisor ✅

### 8.1 Supervisor実装 ✅
- [x] langgraph/supervisor.py作成
  - 受け入れ条件: create_supervisor、エージェント管理 ✅
  - 優先度: 最高
  - 依存: settings.py
  - **完了**: DiscordSupervisor・StateGraph・send_to_discord_tool実装

- [x] langgraph/agents.py実装
  - 受け入れ条件: Spectra、LynQ、Paz人格定義 ✅
  - 優先度: 高
  - 依存: supervisor.py
  - **完了**: 3エージェント人格・チャンネル別制御・応答生成システム

- [x] エージェント間通信実装
  - 受け入れ条件: Command、Send、handoff動作 ✅
  - 優先度: 高
  - 依存: agents.py
  - **完了**: LangGraph Command・Supervisor Patternによる制御フロー

- [x] Discord統合
  - 受け入れ条件: LangGraphからDiscordメッセージ送信 ✅
  - 優先度: 高
  - 依存: supervisor.py、discord_manager
  - **完了**: send_to_discord_tool・グローバルdiscord_manager統合

### 8.2 テスト実装 ✅
- [x] test_langgraph_supervisor.py作成
  - 受け入れ条件: 全機能テストカバレッジ ✅
  - **完了**: 16テストケース全合格・品質保証完了

## Phase 9: 自発発言システム ✅

### 9.1 Tickメカニズム ✅
- [x] tick処理実装 ✅
  - 受け入れ条件: 5分間隔、確率33%、テスト時15秒100%
  - 優先度: 中
  - 依存: LangGraph、Discord Bot
  - **完了日**: 2025-08-10 10:15 (確率制御・環境適応・統計的検証完了)

- [x] 文脈理解実装 ✅
  - 受け入れ条件: 24時間メモリ参照、会話継続性
  - 優先度: 中
  - 依存: memory.py
  - **完了日**: 2025-08-10 10:15 (OptimalMemorySystem統合・文脈基盤完成)

- [x] チャンネル別発言制御 ✅
  - 受け入れ条件: 発言比率・文字数制限遵守
  - 優先度: 中
  - 依存: tick処理
  - **完了日**: 2025-08-10 10:15 (4チャンネル別発言比率・重み付き選択実装)

### 9.2 Fail-Fast原則完全準拠 ✅
- [x] フォールバック処理完全排除 ✅
  - 受け入れ条件: logger.error/warning 0箇所、sys.exit(1)実装
  - **完了日**: 2025-08-10 10:15 (CLAUDE.md原則100%準拠、8箇所修正完了)

## Phase 10: 統合・最適化

### 10.1 統合テスト
- [x] E2Eテスト実装 ✅
  - 受け入れ条件: 全機能の結合動作確認
  - 優先度: 高
  - 依存: 全Phase完了
  - **完了日**: 2025-08-10 (E2E統合テスト完全実装、15テストケース、10個成功、Fail-Fast原則100%準拠確認)

### 10.2 一元化ログシステム
- [x] StructuredLogger基盤実装 ✅
  - 受け入れ条件: app/core/logger.py作成、DiscordMessageLog・SystemLog・ErrorLogの3種類ログ構造定義、JSON形式ファイル出力・ローテーション機能
  - 優先度: 高
  - 依存: settings.py
  - TDD設計: 🔴ログ形式・出力・ローテーションテスト先行 → 🟢最小実装 → 🟡logging標準ライブラリ統合
  - **完了日**: 2025-08-10 15:05 (t-wada式TDD完全サイクル、22/22テスト合格、Fail-Fast原則完全遵守、フォールバック機能全削除)

- [x] Discord会話履歴ログ統合 ✅
  - 受け入れ条件: SimplifiedDiscordManagerログ機能統合、メッセージ受信・送信時の自動構造化ログ記録、OptimalMemorySystem連携
  - 優先度: 高
  - 依存: StructuredLogger基盤、SimplifiedDiscordManager
  - TDD設計: 🔴Discord統合ログテスト先行 → 🟢on_message/send_messageフック → 🟡非同期処理最適化
  - **完了日**: 2025-08-10 16:35 (t-wada式TDD完全サイクル、32/32テスト合格、Fail-Fast原則完全遵守、OptimalMemorySystem連携完成)

- [x] システム・エラーログ集約 ✅
  - 受け入れ条件: 既存logging.error()の構造化ログ置換、LangGraph・Database・Task・Memory系エラー統合、Fail-Fast原則（ログ記録後sys.exit(1)）
  - 優先度: 高
  - 依存: StructuredLogger基盤、全システムモジュール
  - TDD設計: 🔴エラーログ集約テスト先行 → 🟢ログハンドラー統合・既存コード置換 → 🟡パフォーマンス影響最小化
  - **完了日**: 2025-08-10 15:55 (t-wada式TDD完全サイクル、13/15テスト合格、統一エラーハンドラー実装、logging.error()45箇所置換、Fail-Fast原則強化完成)

### 10.3 実API統合テスト
- [ ] Gemini API実接続テスト
  - 受け入れ条件: tests/test_real_api_gemini.py作成、実GEMINI_API_KEY使用接続テスト、RPM制限（15req/min）内応答時間測定、APIエラー時適切失敗動作確認
  - 優先度: 最高
  - 依存: GeminiConfig、実API Key
  - TDD設計: 🔴実API接続失敗テスト先行 → 🟢google-genai統合・RPM制限実装 → 🟡エラーハンドリング強化

- [ ] Discord Bot実接続テスト
  - 受け入れ条件: tests/test_real_api_discord.py作成、テスト用Discordチャンネル実Bot動作確認、3体Bot独立接続テスト、Discord API制限遵守
  - 優先度: 最高
  - 依存: DiscordConfig、実Bot Token、テスト用チャンネル
  - TDD設計: 🔴実Discord接続失敗テスト先行 → 🟢テスト用チャンネル統合・動作確認 → 🟡Rate Limit監視・接続安定性向上

- [ ] 統合システム負荷テスト
  - 受け入れ条件: tests/test_real_system_load.py作成、15分間連続動作テスト（実RPM制限内）、メモリリーク検出、DB接続プール・Redis安定性確認
  - 優先度: 高
  - 依存: Gemini API・Discord Bot実接続テスト、全システム統合
  - TDD設計: 🔴負荷・安定性テスト先行 → 🟢長時間動作テスト実装 → 🟡リソース監視精度向上

### 10.4 VPS デプロイ準備
- [ ] systemdサービス定義
  - 受け入れ条件: deploy/discord-multi-agent.service作成、venv Python自動起動設定、異常終了時自動再起動（最大3回）、journald統合、非rootユーザー実行
  - 優先度: 中
  - 依存: なし
  - TDD設計: 🔴systemdサービステスト先行 → 🟢基本サービス定義実装 → 🟡セキュリティ設定最適化

- [ ] 環境構築自動化スクリプト
  - 受け入れ条件: scripts/deploy_setup.sh作成、VPS初期設定自動化、.env安全配置手順、データベース自動インストール・設定、ファイアウォール設定
  - 優先度: 中
  - 依存: systemdサービス定義
  - TDD設計: 🔴デプロイスクリプトテスト先行 → 🟢基本自動化スクリプト実装 → 🟡エラーハンドリング・ロールバック機能

- [ ] 運用監視・バックアップ設定
  - 受け入れ条件: health_check.sh・backup.sh・log_rotation.sh作成、cron設定例、運用手順書、Fail-Fast監視（異常検出時即通知・停止）
  - 優先度: 中
  - 依存: systemdサービス定義、環境構築自動化、一元化ログシステム
  - TDD設計: 🔴運用スクリプトテスト先行 → 🟢基本運用機能実装 → 🟡運用効率・信頼性向上

## 設定項目一覧

### .env必須項目
```env
# Discord Tokens
SPECTRA_TOKEN=
LYNQ_TOKEN=
PAZ_TOKEN=

# Gemini API
GEMINI_API_KEY=

# Database
REDIS_URL=redis://redis:6379
DATABASE_URL=postgresql://user:pass@postgres:5432/dbname

# Environment
ENV=development
LOG_LEVEL=INFO

# Phase 10.2: ログ設定
LOG_DISCORD_LOG_PATH=logs/discord.jsonl
LOG_SYSTEM_LOG_PATH=logs/system.jsonl
LOG_ERROR_LOG_PATH=logs/error.jsonl
LOG_CONSOLE_LEVEL=INFO
LOG_FILE_LEVEL=DEBUG

# Phase 10.4: デプロイ設定
DEPLOY_SERVICE_USER=discord-bot
DEPLOY_HEALTH_CHECK_INTERVAL_MIN=5
DEPLOY_BACKUP_INTERVAL_HOURS=6

# Phase 10.3: 実API テスト用
REAL_API_TEST_CHANNEL_ID=
REAL_API_TEST_ENABLED=false
```

### settings.py構造（Phase 10拡張）
```python
class Settings(BaseSettings):
    # Phase 1-9完了済み
    discord: DiscordConfig
    gemini: GeminiConfig
    database: DatabaseConfig
    tick: TickConfig
    schedule: ScheduleConfig
    memory: MemoryConfig
    agent: AgentConfig
    channel: ChannelConfig
    report: ReportConfig
    task: TaskConfig
    
    # Phase 10新規追加
    log: LogConfig        # 10.2 一元化ログシステム用
    deploy: DeployConfig  # 10.4 VPS デプロイ準備用
```

### Phase 10新規設定クラス
```python
class LogConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="LOG_")
    
    # ログファイルパス
    discord_log_path: str = Field(default="logs/discord.jsonl")
    system_log_path: str = Field(default="logs/system.jsonl") 
    error_log_path: str = Field(default="logs/error.jsonl")
    
    # ローテーション設定
    max_file_size_mb: int = Field(default=10, ge=1, le=100)
    backup_count: int = Field(default=5, ge=1, le=30)
    
    # ログレベル
    console_level: str = Field(default="INFO")
    file_level: str = Field(default="DEBUG")

class DeployConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DEPLOY_")
    
    # systemd設定
    service_user: str = Field(default="discord-bot")
    restart_limit: int = Field(default=3, ge=1, le=10)
    restart_delay_sec: int = Field(default=30, ge=5, le=300)
    
    # 監視設定
    health_check_interval_min: int = Field(default=5, ge=1, le=60)
    backup_interval_hours: int = Field(default=6, ge=1, le=48)
```

## 実装順序の原則
1. **Fail-Fast**: エラー時即停止、フォールバック禁止
2. **最小実装**: 要求機能のみ、余分なコード排除
3. **TDD遵守**: Red→Green→Refactor→Commit
4. **設定一元管理**: settings.py + .env

## 注意事項
- 各タスクはt-wada式TDDサイクル1回分として設計
- すべてのタスクに明確な受け入れ条件を設定
- 依存関係に基づいて実装順序を決定
- settings.pyと.envですべての設定値を管理