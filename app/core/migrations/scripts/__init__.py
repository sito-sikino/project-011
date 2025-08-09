"""
Migration scripts package for Discord Multi-Agent System

このパッケージには具体的なマイグレーションスクリプトが含まれます。
各スクリプトはup()とdown()関数を提供し、データベーススキーマの
前進および後退変更を実装します。

スクリプト命名規則:
- XXX_description.py (例: 001_create_agent_memory.py)
- XXX: 3桁の連続番号
- description: 変更内容の説明

各スクリプトの要求事項:
- async def up(db_manager): マイグレーション実行
- async def down(db_manager): マイグレーション取り消し
"""