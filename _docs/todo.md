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

## Phase 9: 自発発言システム

### 9.1 Tickメカニズム
- [ ] tick処理実装
  - 受け入れ条件: 5分間隔、確率33%、テスト時15秒100%
  - 優先度: 中
  - 依存: LangGraph、Discord Bot

- [ ] 文脈理解実装
  - 受け入れ条件: 24時間メモリ参照、会話継続性
  - 優先度: 中
  - 依存: memory.py

- [ ] チャンネル別発言制御
  - 受け入れ条件: 発言比率・文字数制限遵守
  - 優先度: 中
  - 依存: tick処理

## Phase 10: 統合・最適化

### 10.1 統合テスト
- [ ] E2Eテスト実装
  - 受け入れ条件: 全機能の結合動作確認
  - 優先度: 高
  - 依存: 全Phase完了

- [ ] 性能最適化
  - 受け入れ条件: 15 RPM制限遵守、メモリ使用量最適化
  - 優先度: 中
  - 依存: 統合テスト

- [ ] ログ・モニタリング実装
  - 受け入れ条件: エラーログ、性能メトリクス記録
  - 優先度: 低
  - 依存: 統合テスト

- [ ] デプロイ準備
  - 受け入れ条件: VPS設定手順書、systemdサービス定義
  - 優先度: 中
  - 依存: 全機能完成

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
```

### settings.py構造
```python
class Settings(BaseSettings):
    discord: DiscordConfig
    gemini: GeminiConfig
    database: DatabaseConfig
    tick: TickConfig
    schedule: ScheduleConfig
    memory: MemoryConfig
    agent: AgentConfig
    channel: ChannelConfig
    report: ReportConfig
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