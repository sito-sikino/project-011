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
- **LLM**: Google Gemini 2.0 Flash API
- **Embedding**: text-embedding-004
- **データストア**:
  - Redis (短期記憶)
  - PostgreSQL + pgvector (長期記憶)
- **コンテナ**: Docker + docker-compose
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

## 5. メモリシステム

### 5.1 短期記憶（Redis）
- **用途**: 24時間分のメッセージキャッシュ
- **データ構造**: List
- **保存内容**: 24時間分のメッセージ
- **保存単位**: 全チャンネル統合
- **リセット**: 日次長期記憶移行後

### 5.2 長期記憶（PostgreSQL + pgvector）
- **用途**: 永続的な記憶とセマンティック検索
- **Embedding**: text-embedding-004
- **単位**: 1メッセージ = 1 embedding
- **メタデータ**:
  - timestamp (timestamptz)
  - channel (varchar)
  - agent (varchar)
  - message_id (bigint)
  - thread_id (bigint, nullable)
- **検索**: コサイン類似度による関連メッセージ取得
- **バックアップ**: 不要

## 6. タスク管理

### 6.1 コマンド仕様
`/task commit <channel> "<内容>"`

- `<channel>`: `creation` または `development`
- `<内容>`: タスク説明（任意）

### 6.2 動作仕様
- `<channel>` のみ → チャンネル移動
- `<内容>` のみ → 内容変更
- 両方指定 → チャンネル変更＋内容変更、または新規指定

※ タスクは常に1件のみ（並列不可）

### 6.3 タスクライフサイクル
- **開始**: ユーザーが `/task commit` で指定
- **継続**: 19:59まで継続（ユーザー更新があれば随時反映）
- **終了**: 翌日06:00の日報生成時に自動リセット
- **他のコマンド**: 存在しない（/task commitのみ）

### 6.4 タスク未指定時の動作
- タスクが指定されていない場合、3体はcommand-centerで19:59まで会議継続
- 自発発言はcommand-centerで実行

## 7. 日報システム

### 7.1 実行仕様
- **実行者**: Spectra
- **実行時刻**: 06:00（PROCESSING モード開始時）
- **処理フロー**:
  1. Redis から前日分メッセージ取得
  2. PostgreSQL へ embedding 化して保存
  3. 活動サマリー生成
  4. Discord Embed 形式 + 会議開始メッセージで command-center へ投稿
  5. Redis リセット

## 8. Docker 構成

### 8.1 サービス構成
```yaml
services:
  app:
    - Discord bot アプリケーション
    - LangGraph Supervisor
    - 環境変数経由で他サービス接続
  
  redis:
    - 短期記憶ストア
    - ポート: 6379
    
  postgres:
    - 長期記憶ストア
    - pgvector 拡張有効化
    - ポート: 5432
```

### 8.2 デプロイ
- VPS 上で 24時間稼働
- docker-compose による一括管理
- ボリュームマウント: ログ、データベース永続化

## 9. エラー処理

### 9.1 Fail-Fast 原則
- すべてのエラーで即座に処理停止
- フォールバック・デグレード禁止
- エラー内容を明示的にログ出力

### 9.2 エラー種別
- API エラー: 即停止、手動復旧待ち
- 接続エラー: 即停止、手動復旧待ち
- データエラー: 即停止、データ修正待ち

## 10. 環境変数

### 10.1 必須設定
```env
# Discord（3体のボット用）
SPECTRA_TOKEN=
LYNQ_TOKEN=
PAZ_TOKEN=

# Gemini
GEMINI_API_KEY=

# Database
REDIS_URL=redis://redis:6379
DATABASE_URL=postgresql://user:pass@postgres:5432/dbname

# Environment
ENV=development|production

# Tick設定
TICK_INTERVAL=15|300  # 秒
TICK_PROBABILITY=1.0|0.33

# Logging
LOG_LEVEL=INFO|DEBUG
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