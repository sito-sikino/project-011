# Discord Multi-Agent System アーキテクチャ仕様書

## 1. システム概要

### 1.1 全体アーキテクチャ

本システムは、LangGraph Supervisorパターンを中心とした3つの専門AIエージェント（Spectra、LynQ、Paz）がDiscordサーバー上で自律動作するマルチエージェントアーキテクチャです。

```mermaid
graph TB
    subgraph "Discord層"
        U[ユーザーメッセージ]
        DC1[Spectra Bot<br/>主受信者]
        DC2[LynQ Bot<br/>送信専用]
        DC3[Paz Bot<br/>送信専用]
    end
    
    subgraph "アプリケーション層"
        UDM[統合Discord管理]
        TM[ティック管理]
        
        subgraph "LangGraph Supervisorパターン"
            S[Supervisorノード]
            MR[メモリ取得]
            AS[エージェント選択]
            
            subgraph "処理ノード"
                TCP[タスクコマンド処理]
                RP[レポート処理]
                TP[ティック処理]
            end
            
            subgraph "エージェントノード"
                SA[Spectraエージェント]
                LA[LynQエージェント] 
                PA[Pazエージェント]
            end
            
            RS[応答送信]
        end
    end
    
    subgraph "ストレージ層"
        R[(Redis<br/>24時間メモリ)]
        P[(PostgreSQL<br/>+ pgvector<br/>長期記憶)]
    end
    
    subgraph "外部サービス"
        G[Google Gemini 2.0<br/>Flash API]
        E[text-embedding-004]
    end
    
    U --> DC1
    DC1 --> UDM
    UDM --> S
    
    S --> MR
    S --> TCP
    S --> RP
    S --> TP
    
    MR --> AS
    TP --> MR
    AS --> SA
    AS --> LA
    AS --> PA
    
    SA --> RS
    LA --> RS
    PA --> RS
    
    RS --> DC1
    RS --> DC2
    RS --> DC3
    
    TCP --> RS
    RP --> RS
    
    TM --> S
    
    MR --> R
    RP --> R
    RP --> P
    
    SA --> G
    LA --> G
    PA --> G
    
    RP --> E
```

### 1.2 主な特徴

- **統合受信・分散送信**: Spectraが全メッセージを受信、各エージェントが自分のアカウントから送信
- **24時間ベースメモリ**: Redis（短期）とPostgreSQL+pgvector（長期）の階層化メモリ
- **単一直列タスク管理**: 1日1タスク集中、チャンネル間移動対応
- **時間帯別動作モード**: 4つのモード（STANDBY、PROCESSING、ACTIVE、FREE）
- **Fail-Fast原則**: エラー時即停止、フォールバック無し

## 2. Discord接続アーキテクチャ

### 2.1 統合Discord管理クラス

```python
class UnifiedDiscordManager:
    """3つのBotクライアントの統合管理"""
    
    def __init__(self, settings: Settings):
        self.intents = discord.Intents.default()
        self.intents.message_content = True
        
        # 3つの独立Botクライアント
        self.clients = {
            "spectra": discord.Client(intents=self.intents),
            "lynq": discord.Client(intents=self.intents),
            "paz": discord.Client(intents=self.intents)
        }
        
        # 主受信者（Spectra）
        self.primary_client = "spectra"
        
        # LangGraphアプリケーション
        self.graph_app = build_langgraph_app()
        
        # イベントハンドラー登録（Spectraのみ）
        self._setup_event_handlers()
    
    def _setup_event_handlers(self):
        """Spectraクライアント専用イベントハンドラー設定"""
        client = self.clients[self.primary_client]
        
        @client.event
        async def on_ready():
            logger.info(f"{self.primary_client}が準備完了・待機中")
            # 他のボットをログイン
            for name, bot in self.clients.items():
                if name != self.primary_client:
                    asyncio.create_task(
                        bot.start(getattr(settings, f"{name.upper()}_TOKEN"))
                    )
        
        @client.event
        async def on_message(self, message):
            """Spectraがすべてのメッセージを受信"""
            # Botメッセージは無視
            if message.author.bot:
                return
            
            # メモリに記録
            await self._record_message(message)
            
            # LangGraphで処理
            await self.process_with_langgraph(message)
    
    async def send_as_agent(self, agent_name: str, channel_id: int, content: str):
        """指定エージェントのBotアカウントから送信"""
        client = self.clients[agent_name]
        channel = client.get_channel(channel_id)
        
        if channel:
            await channel.send(content)
        else:
            logger.error(f"エージェント{agent_name}用チャンネル{channel_id}が見つかりません")
```

### 2.2 自発発言システム（ティック管理）

```python
class TickManager:
    """定期的な自発発言を管理"""
    
    def __init__(self, discord_manager: UnifiedDiscordManager, settings: Settings):
        self.discord_manager = discord_manager
        self.settings = settings
        self.running = False
    
    async def start(self):
        """ティックループ開始"""
        self.running = True
        logger.info(f"ティック管理開始: {self.settings.TICK_INTERVAL}秒間隔")
        
        while self.running:
            await asyncio.sleep(self.settings.TICK_INTERVAL)
            
            try:
                await self._process_tick()
            except Exception as e:
                logger.critical(f"致命的エラー: ティック処理失敗: {e}")
                sys.exit(1)  # Fail-Fast
    
    async def _process_tick(self):
        """ティック処理実行"""
        # 現在モード確認
        current_mode = get_current_mode()
        if current_mode == "STANDBY":
            return  # 完全無応答モード、何もしない
        
        # PROCESSINGモード: 日報自動実行→会議開始
        if current_mode == "PROCESSING":
            await self._trigger_daily_report_and_start_meeting()
            return
        
        # アクティブチャンネル選択
        target_channels = self._get_active_channels(current_mode)
        if not target_channels:
            return
        
        # ランダムチャンネル選択
        target_channel_name = random.choice(target_channels)
        
        # 仮想ティックメッセージ作成
        state = {
            "messages": [],
            "channel_name": target_channel_name,
            "message_type": "tick"
        }
        
        # LangGraphで処理
        result = await self.discord_manager.graph_app.ainvoke(state)
        
        # レスポンスがあれば送信
        if result.get("response_text") and result.get("response_agent"):
            await self.discord_manager.send_as_agent(
                agent_name=result["response_agent"],
                channel_id=target_channel.id,
                content=result["response_text"]
            )
    
    async def _trigger_daily_report_and_start_meeting(self):
        """spec.md準拠の5ステップ日報処理→会議開始"""
        try:
            # ステップ1: Redis から前日分メッセージ取得
            memory_manager = MemoryManager(self.discord_manager.redis)
            yesterday_messages = await memory_manager.get_all_24h_messages()
            
            if not yesterday_messages:
                logger.info("前日分メッセージなし、日報スキップ")
                return
            
            # ステップ2: PostgreSQL へ embedding 化して保存
            await self._save_messages_to_long_term_memory(yesterday_messages)
            
            # ステップ3: 活動サマリー生成
            summary = await self._generate_activity_summary(yesterday_messages)
            
            # ステップ4: Discord Embed 形式 + 会議開始メッセージで command-center へ投稿
            embed_report = await self._create_daily_report_embed(summary, yesterday_messages)
            await self.discord_manager.send_as_agent(
                agent_name="spectra",
                channel_id=self._get_channel_id("command-center"),
                content="", # Embedのみ
                embed=embed_report
            )
            
            # 会議開始メッセージも送信
            meeting_message = "おはようございます！日報完了しました。今日の会議を開始します。"
            await self.discord_manager.send_as_agent(
                agent_name="spectra",
                channel_id=self._get_channel_id("command-center"),
                content=meeting_message
            )
            
            # ステップ5: Redis リセット
            await memory_manager.clear_after_report()
            
            # 日報完了フラグを設定
            await self._set_daily_report_completed()
            
            logger.info("日報処理完了、ACTIVEモード開始")
            
        except Exception as e:
            logger.critical(f"日報処理失敗: {e}")
            sys.exit(1)  # Fail-Fast
    
    async def _set_daily_report_completed(self):
        """日報完了フラグを設定"""
        # 24時間後に自動削除されるフラグを設定
        await self.discord_manager.redis.setex(
            "daily_report_completed", 
            24 * 60 * 60,  # 24時間
            "1"
        )
    
    def _get_channel_id(self, channel_name: str) -> int:
        """チャンネル名からIDを取得"""
        # 実装例：設定からチャンネルIDマッピングを取得
        channel_mapping = getattr(self.settings, 'CHANNEL_IDS', {})
        return channel_mapping.get(channel_name)
    
    async def _save_messages_to_long_term_memory(self, messages: List[dict]):
        """メッセージをPostgreSQL+pgvectorに保存（ステップ2）"""
        from app.core.embedding import EmbeddingService
        from app.core.database import get_postgres
        
        embedding_service = EmbeddingService()
        postgres = get_postgres()
        
        for message in messages:
            try:
                # text-embedding-004でembedding生成
                embedding = await embedding_service.create_embedding(message["content"])
                
                # PostgreSQLに保存
                await postgres.execute("""
                    INSERT INTO messages_long_term 
                    (timestamp, channel, agent, message_id, thread_id, content, embedding)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                """, 
                    message["timestamp"],
                    message["channel"],
                    message["agent"],
                    message.get("message_id"),
                    message.get("thread_id"),
                    message["content"],
                    embedding
                )
                
            except Exception as e:
                logger.error(f"長期メモリ保存失敗: {message['id']}: {e}")
    
    async def _generate_activity_summary(self, messages: List[dict]) -> str:
        """活動サマリー生成（ステップ3）"""
        from app.core.gemini import GeminiService
        
        gemini = GeminiService()
        
        # メッセージ統計
        total_messages = len(messages)
        by_channel = {}
        by_agent = {}
        
        for msg in messages:
            channel = msg.get("channel", "unknown")
            agent = msg.get("agent", "unknown")
            
            by_channel[channel] = by_channel.get(channel, 0) + 1
            by_agent[agent] = by_agent.get(agent, 0) + 1
        
        # Geminiでサマリー生成
        prompt = f"""
        昨日の活動データから日報を作成してください：
        
        総メッセージ数: {total_messages}
        チャンネル別: {by_channel}
        エージェント別: {by_agent}
        
        最近のメッセージサンプル:
        {messages[:5] if messages else "なし"}
        
        簡潔で要点をまとめた日報を生成してください。
        """
        
        summary = await gemini.generate_text(
            prompt=prompt,
            temperature=0.3  # 事実重視
        )
        
        return summary
    
    async def _create_daily_report_embed(self, summary: str, messages: List[dict]) -> dict:
        """Discord Embed形式の日報作成（ステップ4）"""
        from datetime import datetime
        
        # 統計計算
        total = len(messages)
        by_channel = {}
        for msg in messages:
            channel = msg.get("channel", "unknown")
            by_channel[channel] = by_channel.get(channel, 0) + 1
        
        # Embed構築
        embed = {
            "title": f"📊 日報 - {datetime.now().strftime('%Y-%m-%d')}",
            "description": summary,
            "color": 0x00ff00,  # 緑色
            "fields": [
                {
                    "name": "📈 総メッセージ数",
                    "value": str(total),
                    "inline": True
                },
                {
                    "name": "📍 チャンネル別統計", 
                    "value": "\n".join([f"{ch}: {cnt}" for ch, cnt in by_channel.items()]),
                    "inline": True
                }
            ],
            "timestamp": datetime.now().isoformat(),
            "footer": {
                "text": "by Spectra"
            }
        }
        
        return embed
```

## 3. LangGraph Supervisorパターン実装

### 3.1 エージェント状態定義

```python
from typing import TypedDict, Literal, List, Optional, Annotated
from langgraph.graph import MessagesState

class AgentState(MessagesState):
    # Discordコンテキスト
    channel_id: int
    channel_name: str
    message_type: Literal["normal", "mention", "command", "tick"]
    
    # メモリコンテキスト（24時間ベース）
    recent_memory: Annotated[List[dict], "直近メッセージ履歴"] = []
    current_task: Annotated[Optional[dict], "現在のアクティブタスク"] = None
    
    # 処理コンテキスト
    current_mode: Literal["STANDBY", "PROCESSING", "ACTIVE", "FREE"]
    should_respond: bool = False
    response_probability: float = 0.0
    
    # エージェント決定
    selected_agent: Optional[Literal["spectra", "lynq", "paz"]] = None
    agent_ratios: dict = {}
    
    # レスポンス
    response_text: Optional[str] = None
    response_agent: Optional[str] = None
    
    # フラグ
    task_updated: bool = False
    report_generated: bool = False
```

### 3.2 Supervisorノード実装

```python
def supervisor(state: AgentState) -> Command:
    """中央制御: モード判定 → 処理ルーティング"""
    
    # 現在モード取得・設定
    current_mode = get_current_mode()
    state["current_mode"] = current_mode
    
    message_type = state.get("message_type", "normal")
    
    # STANDBYモード: 完全無応答（真のエコモード）
    if current_mode == "STANDBY":
        return Command(goto=END)  # 一切処理しない
    
    # PROCESSINGモード: 日報処理（06:00自動実行）
    if current_mode == "PROCESSING":
        return Command(goto="report_processor")
    
    # ACTIVEモード: 全機能
    if current_mode == "ACTIVE":
        if message_type == "command":
            return Command(goto="task_command_processor")
        elif message_type == "tick":
            return Command(goto="memory_retriever")  # ティック発言もメモリを参照
        else:  # normal, mention
            return Command(goto="memory_retriever")
    
    # FREEモード: ソーシャル中心
    if current_mode == "FREE":
        if message_type == "command":
            return Command(goto="task_command_processor")
        return Command(goto="memory_retriever")
    
    return Command(goto=END)

def get_current_mode() -> str:
    """現在時刻に基づくモード判定"""
    hour = datetime.now().hour
    
    if 0 <= hour < 6:
        return "STANDBY"
    elif hour == 6:
        # 6:00台でも日報処理完了後はACTIVE
        return "PROCESSING" if not _is_daily_report_completed() else "ACTIVE"
    elif 6 < hour < 20:
        return "ACTIVE"
    else:  # 20 <= hour < 24
        return "FREE"

async def _is_daily_report_completed() -> bool:
    """日報処理完了チェック"""
    try:
        # Redisから日報完了フラグを確認
        from app.core.database import get_redis
        redis = get_redis()
        flag = await redis.get("daily_report_completed")
        return flag is not None
    except Exception as e:
        logger.error(f"日報完了フラグチェック失敗: {e}")
        return False
```

## 4. メモリ管理システム

### 4.1 24時間ベースメモリ管理（Redis）

```python
class MemoryManager:
    """24時間ベースメモリ管理クラス"""
    
    def __init__(self, redis_client):
        self.redis = redis_client
        self.MEMORY_KEY = "messages_24h"
        self.INDEX_KEY = "memory_index"
    
    async def add_message(self, message_data: dict):
        """24時間メモリにメッセージ追加"""
        # タイムスタンプ付きで保存
        message_data["timestamp"] = datetime.now().isoformat()
        message_data["id"] = str(uuid.uuid4())
        
        # リストに追加（新しいものが先頭）
        await self.redis.lpush(self.MEMORY_KEY, json.dumps(message_data))
        
        # インデックス更新
        await self._update_index(message_data)
        
        # 24時間より古いメッセージをクリーンアップ
        await self._cleanup_old_messages()
    
    async def get_recent_messages(self, limit: int = None) -> List[dict]:
        """直近メッセージ取得"""
        try:
            if limit:
                messages_json = await self.redis.lrange(self.MEMORY_KEY, 0, limit - 1)
            else:
                messages_json = await self.redis.lrange(self.MEMORY_KEY, 0, -1)
            
            return [json.loads(msg) for msg in messages_json]
        
        except Exception as e:
            logger.error(f"直近メッセージ取得失敗: {e}")
            return []
    
    async def get_all_24h_messages(self) -> List[dict]:
        """日報用: 全24時間メッセージ"""
        return await self.get_recent_messages()
    
    async def clear_after_report(self):
        """日報作成後のメモリリセット"""
        try:
            await self.redis.delete(self.MEMORY_KEY)
            await self.redis.delete(self.INDEX_KEY)
            logger.info("日報生成後に24時間メモリをクリア")
        except Exception as e:
            logger.error(f"メモリクリア失敗: {e}")
            raise
    
    async def _cleanup_old_messages(self):
        """24時間より古いメッセージを削除"""
        cutoff_time = datetime.now() - timedelta(hours=24)
        
        try:
            # 全メッセージ取得・チェック
            all_messages_json = await self.redis.lrange(self.MEMORY_KEY, 0, -1)
            
            valid_messages = []
            for msg_json in all_messages_json:
                msg = json.loads(msg_json)
                msg_time = datetime.fromisoformat(msg["timestamp"])
                
                if msg_time >= cutoff_time:
                    valid_messages.append(msg_json)
                else:
                    logger.debug(f"古いメッセージを削除: {msg['timestamp']}")
            
            # リスト更新
            if len(valid_messages) != len(all_messages_json):
                await self.redis.delete(self.MEMORY_KEY)
                if valid_messages:
                    await self.redis.rpush(self.MEMORY_KEY, *valid_messages)
                    
        except Exception as e:
            logger.error(f"クリーンアップ失敗: {e}")
    
    async def get_statistics(self) -> dict:
        """24時間メモリ統計"""
        messages = await self.get_all_24h_messages()
        
        if not messages:
            return {"total": 0, "by_channel": {}, "by_agent": {}}
        
        stats = {
            "total": len(messages),
            "by_channel": {},
            "by_agent": {},
            "time_range": {
                "oldest": messages[-1]["timestamp"] if messages else None,
                "newest": messages[0]["timestamp"] if messages else None
            }
        }
        
        # チャンネル別・エージェント別統計
        for msg in messages:
            channel = msg.get("channel_name", "unknown")
            author = msg.get("author", "unknown")
            
            stats["by_channel"][channel] = stats["by_channel"].get(channel, 0) + 1
            stats["by_agent"][author] = stats["by_agent"].get(author, 0) + 1
        
        return stats
```

## 5. タスク管理システム

### 5.1 シンプルなタスク管理

```python
class TaskManager:
    """シンプルな1日1タスク管理システム"""
    
    def __init__(self, redis_client):
        self.redis = redis_client
        self.TASK_KEY = "current_task"
    
    async def get_current_task(self) -> Optional[dict]:
        """現在のタスク取得"""
        try:
            task_json = await self.redis.get(self.TASK_KEY)
            return json.loads(task_json) if task_json else None
        except Exception as e:
            logger.error(f"現在タスク取得失敗: {e}")
            return None
    
    async def commit_task(
        self, 
        task_description: str = None, 
        channel: Literal["creation", "development"] = None, 
        user_id: str = None
    ) -> dict:
        """タスクコミット（新規・更新・チャンネル移動統一処理）"""
        
        current_task = await self.get_current_task()
        now = datetime.now().isoformat()
        
        if current_task:
            # 既存タスクの更新
            task_data = current_task.copy()
            
            if task_description:
                task_data["description"] = task_description
            if channel:
                task_data["channel"] = channel
            if user_id:
                task_data["updated_by"] = user_id
            
            task_data["updated_at"] = now
            action = "updated"
            
        else:
            # 新規タスク作成（両方必須）
            if not task_description or not channel:
                raise ValueError("新規タスクには説明とチャンネルの両方が必要")
                
            task_data = {
                "description": task_description,
                "channel": channel,
                "created_by": user_id,
                "created_at": now,
                "updated_at": now
            }
            action = "created"
        
        # Redisに保存
        try:
            await self.redis.set(self.TASK_KEY, json.dumps(task_data))
            logger.info(f"タスク{action}: {task_data['description']} ({task_data['channel']})")
            
        except Exception as e:
            logger.error(f"タスクコミット失敗: {e}")
            raise
        
        return {
            "task": task_data,
            "action": action
        }
```

## 6. システムフロー図

### 6.1 メインフロー

```mermaid
flowchart TD
    Start([システム開始]) --> Init[初期化]
    Init --> DM[Discord管理開始]
    Init --> TM[ティック管理開始]
    
    DM --> |メッセージ受信| MsgProc{メッセージ処理}
    TM --> |定期実行| TickProc{ティック処理}
    
    MsgProc --> S[Supervisor]
    TickProc --> S
    
    S --> Mode{現在モード?}
    
    Mode --> |STANDBY| StandbyFlow[待機処理]
    Mode --> |PROCESSING| ProcFlow[日報処理]  
    Mode --> |ACTIVE| ActiveFlow[アクティブ処理]
    Mode --> |FREE| FreeFlow[フリー処理]
    
    StandbyFlow --> End([完全無応答])
    
    ProcFlow --> RP[日報処理]
    
    ActiveFlow --> MsgType{メッセージ種別}
    FreeFlow --> MsgType
    
    MsgType --> |command| TCP[タスクコマンド処理]
    MsgType --> |tick| MR
    MsgType --> |mention/normal| MR
    
    MR --> AS[エージェント選択]
    
    AS --> AgentType{選択エージェント}
    AgentType --> |spectra| SA[Spectraエージェント]
    AgentType --> |lynq| LA[LynQエージェント] 
    AgentType --> |paz| PA[Pazエージェント]
    
    SA --> RS[応答送信]
    LA --> RS
    PA --> RS
    TCP --> RS
    RP --> RS
    
    RS --> Send[Discord送信]
    Send --> End
```

### 6.2 メモリ管理フロー

```mermaid
flowchart LR
    subgraph "メッセージ入力"
        UM[ユーザーメッセージ]
        AM[エージェントメッセージ]
    end
    
    subgraph "短期メモリ（Redis）"
        R24[24時間メモリ]
        RC[自動クリーンアップ]
        RI[インデックス管理]
    end
    
    subgraph "長期メモリ（PostgreSQL）"
        PG[メッセージテーブル]
        VEC[ベクトル検索]
        EMB[埋め込み生成]
    end
    
    subgraph "日報"
        RP[日報処理]
        SUM[サマリー生成]
        CLR[メモリクリア]
    end
    
    UM --> R24
    AM --> R24
    R24 --> RC
    R24 --> RI
    
    R24 --> |午前6:00| RP
    RP --> EMB
    EMB --> PG
    PG --> VEC
    RP --> SUM
    SUM --> CLR
    CLR --> R24
    
    VEC --> |関連検索| R24
```

### 6.3 タスク管理フロー

**シンプルなタスク管理**:
1. **会議開始**: command-centerで3体が会議開始
2. **ユーザー指示**: `/task commit creation "タスク内容"`でタスク決定
3. **チャンネル移動**: 指定されたチャンネル（creation or development）に移動
4. **作業継続**: 19:59まで指定タスクに集中
5. **更新対応**: ユーザーが同じコマンドで内容やチャンネルを変更可能

**状態管理**:
- **タスク保存**: Redisに1件のみ保存
- **更新方法**: 既存タスクを上書き
- **リセット**: 日報生成時にクリア

## 7. エージェント・チャンネル設定

### 7.1 チャンネル設定定義

```python
CHANNEL_CONFIGS = {
    "command-center": {
        "ratios": {"spectra": 0.4, "lynq": 0.3, "paz": 0.3},
        "max_chars": 100
    },
    
    "creation": {
        "ratios": {"paz": 0.5, "spectra": 0.25, "lynq": 0.25},
        "max_chars": 200
    },
    
    "development": {
        "ratios": {"lynq": 0.5, "spectra": 0.25, "paz": 0.25},
        "max_chars": 200
    },
    
    "lounge": {
        "ratios": {"spectra": 0.34, "lynq": 0.33, "paz": 0.33},
        "max_chars": 30
    }
}

AGENT_CONFIGS = {
    "spectra": {
        "temperature": 0.5,
        "role": "メタ思考・議論進行・方針整理",
        "characteristics": "俯瞰的視点、構造化思考、進行管理"
    },
    
    "lynq": {
        "temperature": 0.3,
        "role": "論理的検証・技術分析・問題解決",
        "characteristics": "分析的思考、実装指向、品質重視"
    },
    
    "paz": {
        "temperature": 0.9,
        "role": "発散的アイデア創出・ブレインストーミング",
        "characteristics": "創造的思考、直感的発想、実験精神"
    }
}
```

## 8. 設定とデプロイ

### 8.1 環境設定

```python
# settings.py
from pydantic import BaseSettings

class Settings(BaseSettings):
    """アプリケーション設定"""
    
    # 環境
    ENV: str = "development"  # development, production
    LOG_LEVEL: str = "INFO"
    
    # Discord設定
    SPECTRA_TOKEN: str
    LYNQ_TOKEN: str  
    PAZ_TOKEN: str
    
    # Gemini API
    GEMINI_API_KEY: str
    GEMINI_MODEL: str = "gemini-2.0-flash-exp"
    EMBEDDING_MODEL: str = "text-embedding-004"
    
    # データベース
    REDIS_URL: str = "redis://redis:6379"
    DATABASE_URL: str
    
    # ティック設定
    TICK_INTERVAL: int = 300  # 秒 (prod: 300, dev: 15)
    TICK_PROBABILITY: float = 0.33  # prod: 0.33, dev: 1.0
    
    # 時刻設定
    STANDBY_START: int = 0    # 0:00開始
    PROCESSING_TRIGGER: int = 6  # 6:00瞬間実行（時間帯ではない）
    ACTIVE_START: int = 6     # 日報完了後開始
    FREE_START: int = 20      # 20:00開始
    
    # メモリ設定
    MEMORY_CLEANUP_HOURS: int = 24
    RECENT_MEMORY_LIMIT: int = 30
    
    
    @property
    def is_development(self) -> bool:
        return self.ENV == "development"
    
    @property
    def is_production(self) -> bool:
        return self.ENV == "production"
    
    class Config:
        env_file = ".env"
```

### 8.2 Docker設定

```yaml
# docker-compose.yml
version: '3.8'

services:
  app:
    build: 
      context: .
      dockerfile: Dockerfile
    container_name: discord_multi_agent
    restart: unless-stopped
    depends_on:
      - redis
      - postgres
    environment:
      - ENV=production
      - REDIS_URL=redis://redis:6379
      - DATABASE_URL=postgresql://agent_user:agent_pass@postgres:5432/agent_db
    env_file:
      - .env
    volumes:
      - ./logs:/app/logs
    networks:
      - agent_network

  redis:
    image: redis:7-alpine
    container_name: agent_redis
    restart: unless-stopped
    command: redis-server --appendonly yes
    volumes:
      - redis_data:/data
    networks:
      - agent_network

  postgres:
    image: pgvector/pgvector:pg16
    container_name: agent_postgres
    restart: unless-stopped
    environment:
      - POSTGRES_DB=agent_db
      - POSTGRES_USER=agent_user
      - POSTGRES_PASSWORD=agent_pass
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./init.sql:/docker-entrypoint-initdb.d/init.sql
    networks:
      - agent_network

volumes:
  redis_data:
  postgres_data:

networks:
  agent_network:
    driver: bridge
```

## 9. 実装の要点

### 9.1 明确な責任分担

**Discord層の責任:**
- **Spectra Bot**: 全メッセージ受信と記録を担当
- **LynQ Bot**: LynQエージェント応答送信専用
- **Paz Bot**: Pazエージェント応答送信専用

**メモリ管理の責任:**
- **Redis（24時間メモリ）**: 会話参照、日報作成、自動クリーンアップ
- **PostgreSQL + pgvector**: 永続ストレージ、意味検索、統計

**タスク管理の責任:**
- **単一タスク管理**: 1日最大1件、上書き更新
- **チャンネル移動**: creation ↔ development間の移動対応

### 9.2 エラーハンドリング戦略

```python
@safe_invoke
def critical_operation():
    """Fail-Fastデコレーターの例"""
    try:
        return dangerous_operation()
    except Exception as e:
        logger.critical(f"致命的エラー: {e}")
        sys.exit(1)  # 即座停止
```

**Fail-Fast適用対象:**
- Discord接続エラー
- Gemini API呼び出しエラー
- データベース操作エラー
- 日報生成エラー

### 9.3 パフォーマンス最適化

**メモリ効率:**
- 24時間自動クリーンアップ
- インデックスベース高速検索
- 長期メモリ検索は必要時のみ

**API効率:**
- 文字数制限で不要な処理を削減
- バッチ処理で呼び出しを削減
- 適切な温度設定でコスト最適化

## 10. まとめ

### 10.1 設計原則の達成

- **Fail-Fast**: エラー即停止で高信頼性を実現
- **最小実装**: 必要機能のみの簡潔実装
- **統合受信・分散送信**: 効率的なDiscord接続管理
- **24時間ベースメモリ**: 一貫したメモリライフサイクル
- **シンプルなタスク管理**: 1日1件集中、ユーザー指示に従う柔軟な更新
- **真のエコモード**: STANDBY時は完全無応答でリソース節約

### 10.2 システム特性

- **明确な責任分離**: 各コンポーネントの役割が明確
- **柔軟な設定管理**: チャンネル・エージェント設定の簡単変更
- **スケーラブル**: 新エージェント・新機能の簡単追加
- **可観測性**: 運用監視用の豊富なログ・統計情報

本アーキテクチャはDiscord上で自然で効率的なマルチエージェント協作システムを実現します。