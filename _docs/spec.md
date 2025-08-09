# Discord マルチエージェントシステム要件定義書

## 1. システム概要

### 1.1 目的
Discord サーバー上でマルチエージェント（Spectra, LynQ, Paz）が創作支援・開発支援・議論進行・雑談を自律的に行う環境を実現する。

### 1.2 基本原則
- **Fail-Fast**: すべてのエラーは即時停止、フォールバック禁止
- **最小実装**: 要求機能のみ実装、余分なコード排除
- **TDD**: Red→Green→Refactor→Commit サイクル徹底
- **設定一元管理**: settings.py + .env による動的制御

### 1.3 技術スタック
- **言語**: Python 3.11+
- **仮想環境**: venv（必須）
- **フレームワーク**: 
  - discord.py (Discord bot)
  - LangGraph (Supervisor Pattern)
  - Pydantic v2 (タスク管理・データバリデーション)
  - pydantic-settings (設定管理)
- **LLM**: Google Gemini 2.0 Flash API
- **Embedding**: text-embedding-004
- **LangChainメモリライブラリ**:
  - langchain-redis (短期記憶)
  - langchain-community (PGVector統合)
  - langchain-google-genai (埋め込み)
  - langchain-core (LCEL統合)
  - pandas (統計処理)
- **データストア**:
  - Redis (短期記憶)
  - PostgreSQL + pgvector (長期記憶)
- **コンテナ**: Docker + docker-compose（ヘルスチェック統合で依存関係制御）
- **環境管理**: python-dotenv

## 2. エージェント定義

### 2.1 共通仕様
- Gemini 2.0 のシステムプロンプトで人格ステータスを付与
- 各エージェントは一つのGemini 2.0 flash APIで駆動する
- 各エージェントは独自のTokenを持ち、それぞれのボットアカウントで発言
- 各エージェントは独自の思考パターンと文体を持つ

### 2.2 Spectra
- **役割**: メタ思考・議論進行・方針整理
- **特性**: 俯瞰的視点、構造化思考、進行管理
- **人格パラメータ**: 
  - temperature: 0.5

### 2.3 LynQ
- **役割**: 論理的検証・技術分析・問題解決
- **特性**: 分析的思考、実装指向、品質重視
- **人格パラメータ**:
  - temperature: 0.3

### 2.4 Paz
- **役割**: 発散的アイデア創出・ブレインストーミング
- **特性**: 創造的思考、直感的発想、実験精神
- **人格パラメータ**:
  - temperature: 0.9

## 3. Discord チャンネル構成

### 3.1 Operation Sector
- **command-center**
  - 用途: 中央指揮・タスク管理・会議
  - 発言比率: Spectra 40%, LynQ 30%, Paz 30%
  - 文字数上限: 100文字

### 3.2 Production Sector  
- **creation**
  - 用途: 創作活動・アイデア展開
  - 発言比率: Paz 50%, Spectra 25%, LynQ 25%
  - 文字数上限: 200文字

- **development**
  - 用途: 開発作業・技術実装
  - 発言比率: LynQ 50%, Spectra 25%, Paz 25%
  - 文字数上限: 200文字

### 3.3 Social Sector
- **lounge**
  - 用途: 雑談・自由会話
  - 発言比率: Spectra 34%, LynQ 33%, Paz 33%
  - 文字数上限: 30文字

## 4. 動作モード

### 4.1 時間帯別動作
| モード | 時間帯 | 動作 |
|--------|---------|------|
| STANDBY | 00:00-05:59 | 完全無応答（エコモード） |
| PROCESSING | 06:00（瞬間処理） | 日報処理実行→完了次第会議開始 |
| ACTIVE | 日報完了後-19:59 | command-center会議→タスク実行 |
| FREE | 20:00-23:59 | loungeでソーシャルモード |

### 4.2 モード詳細
- **STANDBY**: 完全無応答（受信はするが一切処理しない真のエコモード）
- **PROCESSING**: 6:00トリガーで日報処理を瞬間実行、完了後すぐACTIVE移行
- **ACTIVE**: 日報処理完了と同時に会議開始、タスク指定があれば指定チャンネル移動
- **FREE**: loungeでのカジュアル交流メイン

### 4.2 自発発言メカニズム
- **トリガー**: tick方式
  - テスト環境: 15秒間隔、確率100%
  - 本番環境: 5分間隔、確率33%
- **発言者選択**: 
  - システムプロンプトで発言者・発言確率・発言内容を制御
- **文脈把握**: 24時間メモリを参照

### 4.3 ユーザー応答
- 通常発言・メンション・スラッシュコマンドに即時応答
- 応答文字数上限: 100文字
- 応答優先度: ユーザー入力 > 自発発言
- メッセージ処理方式: キューベース順次処理（FIFO）
- エラー処理: 個別メッセージ単位で隔離、システム継続

## 5. メモリシステム

### 5.1 OptimalMemorySystem
- **アーキテクチャ**: 単一セッション「discord_unified」
- **共有範囲**: 全エージェント（Spectra、LynQ、Paz）、全チャンネル統合

### 5.2 短期記憶（Redis）
- **実装**: `langchain_redis.RedisChatMessageHistory`
- **セッションID**: `"discord_unified"`
- **TTL**: 24時間（86400秒）
- **保存形式**: LangChain Message objects
- **メタデータ構造**:
  ```python
  additional_kwargs = {
      "agent": str,      # "spectra", "lynq", "paz"
      "channel": str,    # "command-center", "creation", etc.
      "timestamp": str   # ISO format datetime
  }
  ```

### 5.3 長期記憶（PostgreSQL + pgvector）
- **実装**: `langchain_postgres.PGVectorStore`
- **埋め込み**: `langchain_google_genai.GoogleGenerativeAIEmbeddings`
- **モデル**: `text-embedding-004`
- **コレクション名**: `"agent_memory"`
- **メタデータフィールド**:
  - `agent`: varchar（送信者識別）
  - `channel`: varchar（チャンネル名）
  - `timestamp`: timestamptz（送信時刻）
- **検索メソッド**: `asimilarity_search(query, k=limit)`

### 5.4 日報処理
```python
# OptimalMemorySystem.daily_report_migration()による自動処理
migrated_count = await memory_system.daily_report_migration()

# ModernReportGeneratorによるサマリー生成
from app.core.report import ModernReportGenerator
generator = ModernReportGenerator()
summary = await generator.generate_daily_report(recent_context)
```

## 6. タスク管理

### 6.1 Pydantic統合タスク管理システム
- **実装**: Pydantic v2による型安全なデータ管理
- **技術要素**: 型安全性・バリデーション・シリアライゼーション自動化
- **自動機能**: バリデーション、シリアライゼーション、型安全性

### 6.2 コマンド仕様
`/task commit <channel> "<内容>"`

- `<channel>`: `creation` または `development`（Enum型で型安全）
- `<内容>`: タスク説明（Pydanticで自動バリデーション）

### 6.3 動作仕様
- `<channel>` のみ → チャンネル移動（部分更新）
- `<内容>` のみ → 内容変更（部分更新）
- 両方指定 → チャンネル変更＋内容変更、または新規作成

※ タスクは常に1件のみ（並列不可）

### 6.4 Taskモデル定義
```python
from pydantic import BaseModel, Field
from typing import Literal, Optional

class Task(BaseModel):
    description: str = Field(..., min_length=1, max_length=500)
    channel: Literal["creation", "development"]
    created_by: Optional[str] = None
    updated_by: Optional[str] = None
    created_at: str
    updated_at: str
    
    class Config:
        validate_assignment = True
        extra = 'forbid'
```

### 6.5 タスクライフサイクル
- **開始**: ユーザーが `/task commit` で指定（Pydantic自動バリデーション）
- **継続**: 19:59まで継続（ユーザー更新は自動マージ）
- **終了**: 翌日06:00の日報生成時に自動リセット
- **エラー処理**: バリデーションエラー即時通知、Fail-Fast実行

### 6.6 タスク未指定時の動作
- タスクが指定されていない場合、3体はcommand-centerで19:59まで会議継続
- 自発発言はcommand-centerで実行

## 7. 日報システム

### 7.1 実行仕様
- **実行者**: Spectra
- **実行時刻**: 06:00（PROCESSING モード開始時）
- **処理フロー**:
  1. **自動アーカイブ**: `memory_system.daily_archive_and_reset()`で短期→長期移行処理
  2. **サマリー生成**: LangChain LCEL統合による自動日報生成
  3. **会議開始**: サマリー付き会議開始メッセージを command-center へ送信

### 7.2 LangChain LCEL統合
- **実装**: `ModernReportGenerator`クラス
- **技術要素**:
  - `langchain_core.prompts.PromptTemplate`
  - `langchain_core.output_parsers.StrOutputParser`
  - `langchain_google_genai.ChatGoogleGenerativeAI`
  - pandasによる統計処理
- **処理内容**:
  - LangChainメッセージ形式からデータ抽出
  - DataFrame統計処理（チャンネル別・エージェント別集計）
  - LCEL非同期チェーン実行（chain.ainvoke()）
- **統合**: OptimalMemorySystem.get_recent_context()との連携

## 8. Docker 構成

### 8.1 サービス構成
```yaml
services:
  app:
    - Discord bot アプリケーション
    - LangGraph Supervisor
    - 環境変数経由で他サービス接続
    - 依存サービスヘルスチェック待機有効
  
  redis:
    - 短期記憶ストア
    - ポート: 6379
    - ヘルスチェック: redis-cli ping (10秒間隔)
    
  postgres:
    - 長期記憶ストア
    - pgvector 拡張有効化
    - ポート: 5432
    - ヘルスチェック: pg_isready (15秒間隔)
```

### 8.2 デプロイ
- VPS 上で 24時間稼働
- docker-compose による一括管理
- ボリュームマウント: ログ、データベース永続化
- ヘルスチェック統合: 依存サービスの準備完了待機で確実な初期化を実現
- 競合状態排除: コンテナ起動順序の依存関係制御で長期稼働信頼性を向上

## 9. エラー処理

### 9.1 Fail-Fast 原則
- すべてのエラーで即座に処理停止
- フォールバック・デグレード禁止
- エラー内容を明示的にログ出力
- ヘルスチェック統合: 依存サービスの健全性状態のみをシステム稼働条件として判定

### 9.2 エラー種別
- API エラー: 即停止、手動復旧待ち
- 接続エラー: 即停止、手動復旧待ち
- データエラー: 即停止、データ修正待ち
- ヘルスチェック失敗: 依存サービスの不健全状態でアプリケーション起動停止

### 9.3 ヘルスチェック統合
**Redisヘルスチェック:**
- コマンド: `redis-cli ping`
- 間隔: 10秒
- タイムアウト: 5秒
- 再試行回数: 5回
- 初期待機時間: 10秒

**PostgreSQLヘルスチェック:**
- コマンド: `pg_isready -U agent_user -d agent_db`
- 間隔: 15秒
- タイムアウト: 10秒
- 再試行回数: 5回
- 初期待機時間: 30秒

**ヘルスチェック効果:**
- 起動時の依存関係競合状態を完全防止
- システム全体の初期化の確実性を保証
- 24/7 VPSデプロイメントの信頼性向上
- LangChainメモリシステムとの統合互換性を維持

## 10. 環境変数

### 10.1 Pydantic設定管理システム
**実装**: pydantic-settingsによる構造化設定管理
- 型安全性・バリデーション自動化
- 意味的グループ化による保守性向上
- Field()による宣言的制約定義

### 10.2 設定グループ構造
```python
class Settings(BaseSettings):
    discord: DiscordConfig      # Discord Bot設定
    gemini: GeminiConfig        # Gemini API設定  
    database: DatabaseConfig    # データベース設定
    tick: TickConfig           # 自発発言設定
    schedule: ScheduleConfig    # 時間帯管理設定
    memory: MemoryConfig       # メモリ管理設定
    agent: AgentConfig         # エージェント設定
    channel: ChannelConfig     # チャンネル設定
    report: ReportConfig       # LCEL統合日報設定
```

class ReportConfig(BaseModel):
    """LCEL統合日報設定"""
    temperature: float = Field(0.3, ge=0.0, le=2.0)
    model: str = Field("gemini-2.0-flash-exp")
    context_limit: int = Field(50, ge=10, le=200)

### 10.3 環境変数定義
```env
# Discord Tokens（必須）
SPECTRA_TOKEN=
LYNQ_TOKEN=
PAZ_TOKEN=

# Gemini API（必須）
GEMINI_API_KEY=

# Database（必須）
REDIS_URL=redis://redis:6379
DATABASE_URL=postgresql://user:pass@postgres:5432/dbname

# Environment
ENV=development|production
LOG_LEVEL=INFO|DEBUG

# Tick設定（オプション - デフォルト値あり）
TICK_INTERVAL=300  # 15-3600秒、デフォルト300
TICK_PROBABILITY=0.33  # 0.0-1.0、デフォルト0.33

# 時間帯設定（オプション）
STANDBY_START=0    # 0-23時、デフォルト0
PROCESSING_TRIGGER=6  # 0-23時、デフォルト6
ACTIVE_START=6     # 0-23時、デフォルト6  
FREE_START=20      # 0-23時、デフォルト20

# メモリ設定（オプション）
MEMORY_CLEANUP_HOURS=24  # 1-168時間、デフォルト24
MEMORY_RECENT_LIMIT=30   # 5-100件、デフォルト30

# エージェント設定（オプション）
AGENT_SPECTRA_TEMPERATURE=0.5  # 0.0-2.0
AGENT_LYNQ_TEMPERATURE=0.3     # 0.0-2.0  
AGENT_PAZ_TEMPERATURE=0.9      # 0.0-2.0

# チャンネル文字数制限（オプション）
CHANNEL_COMMAND_CENTER_MAX_CHARS=100  # 50-500
CHANNEL_CREATION_MAX_CHARS=200        # 100-1000
CHANNEL_DEVELOPMENT_MAX_CHARS=200     # 100-1000
CHANNEL_LOUNGE_MAX_CHARS=30           # 10-100

# LCEL統合日報設定（オプション）
REPORT_TEMPERATURE=0.3                # 0.0-2.0
REPORT_MODEL=gemini-2.0-flash-exp     # Gemini model
REPORT_CONTEXT_LIMIT=50               # 10-200件
```

## 11. 制約事項

### 11.1 Discord API 制限
- メッセージ送信: 5msg/5sec per channel
- 文字数制限: 2000文字/メッセージ
- Embed 制限: 25フィールド/Embed

### 11.2 Gemini API 制限（無料枠）
- RPM: 15（無料枠）
- TPM: 32,000（無料）
- コンテキストウィンドウ: 1M tokens

### 11.3 システム制約
- Python 3.11 以上必須
- Docker Compose v3.8 以上（ヘルスチェック機能対応）
- 依存サービスヘルスチェック必須：アプリケーション起動前にRedis/PostgreSQLの準備完了を絶対保証

## 12. テスト戦略

### 12.1 開発方針
- TDD（Test-Driven Development）採用
- Red → Green → Refactor サイクル

### 12.2 テスト範囲
- 単体テスト: 各エージェント、各機能
- 統合テスト: エージェント間連携
- E2E テスト: Discord 実環境での動作確認

### 12.3 モック対象
- Discord API（開発時）
- Gemini API（開発時）
- 時刻依存処理（タイマー、スケジューラー）

## 13. インフラストラクチャ統合

### 13.1 ヘルスチェックアーキテクチャ

**概要:**
Dockerヘルスチェック統合で依存サービスの健全性状態を制御し、Fail-Fast原則と一致したシステム起動を実現。

**技術的メリット:**
- **競合状態排除**: アプリケーション起動前に依存サービスの完全な初期化を確認
- **即座失敗検出**: ヘルスチェック失敗でコンテナを即座停止、フォールバックなし
- **LangChain互換性**: メモリシステムが必要とするサービスの健全性を統合管理

### 13.2 稼働信頼性向上

**24/7 VPSデプロイメント最適化:**
- 長期間無人運用での安定性向上
- システム再起動時の確実な初期化手順
- メンテナンスアップデート時のダウンタイム短縮

**システム品質特性:**
- リソース効率化: 無駄な初期化処理の排除
- メモリシステム統合: Redis/PostgreSQLとLangChainメモリの一貫性管理
- 運用品質: 故障時の早期発見と明確なエラー表示