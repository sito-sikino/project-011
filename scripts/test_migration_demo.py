#!/usr/bin/env python3
"""
Migration System Demo Script

Phase 3.2 - Demonstration of the migration system functionality
This script shows how to use the migration system in practice.

Usage:
    python scripts/test_migration_demo.py
"""
import asyncio
import logging
from pathlib import Path
import sys

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.core.database import (
    initialize_database,
    run_migrations, 
    check_migration_status,
    rollback_migration,
    close_database
)
from app.core.migrations import get_migration_manager

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def demo_migration_system():
    """Demonstrate migration system functionality"""
    
    logger.info("🚀 Starting Migration System Demo")
    
    try:
        # Step 1: Initialize database with auto-migration disabled
        logger.info("📂 Step 1: Initialize database (auto_migrate=False)")
        db_manager = await initialize_database(auto_migrate=False)
        logger.info("✅ Database initialized successfully")
        
        # Step 2: Check initial migration status
        logger.info("📋 Step 2: Check migration status")
        status = await check_migration_status()
        logger.info(f"📊 Applied migrations: {len(status)}")
        for migration in status:
            logger.info(f"  - {migration['version']} (applied: {migration['applied_at']})")
        
        # Step 3: Run migrations manually
        logger.info("⚡ Step 3: Apply all migrations")
        await run_migrations()
        logger.info("✅ All migrations applied")
        
        # Step 4: Check migration status after application
        logger.info("📋 Step 4: Check migration status after application")
        status = await check_migration_status()
        logger.info(f"📊 Applied migrations: {len(status)}")
        for migration in status:
            logger.info(f"  - {migration['version']} (applied: {migration['applied_at']})")
        
        # Step 5: Demonstrate migration manager directly
        logger.info("🔧 Step 5: Direct migration manager demo")
        migration_manager = get_migration_manager()
        
        # Discover available migrations
        migration_files = migration_manager.discover_migration_files()
        logger.info(f"📁 Discovered {len(migration_files)} migration files:")
        for file_path in migration_files:
            migration_name = migration_manager.get_migration_name_from_file(file_path)
            is_applied = await migration_manager.is_migration_applied(migration_name)
            status_icon = "✅" if is_applied else "⏳"
            logger.info(f"  {status_icon} {migration_name}")
        
        # Step 6: Demonstrate rollback (if there are migrations to rollback)
        if status:
            latest_migration = status[-1]['version']
            logger.info(f"⏪ Step 6: Demonstrate rollback of {latest_migration}")
            await rollback_migration(latest_migration)
            logger.info("✅ Migration rolled back successfully")
            
            # Check status after rollback
            status_after_rollback = await check_migration_status()
            logger.info(f"📊 Migrations after rollback: {len(status_after_rollback)}")
            
            # Re-apply migration
            logger.info("🔄 Step 7: Re-apply migrations")
            await run_migrations()
            logger.info("✅ Migrations re-applied successfully")
        
        logger.info("🎉 Migration system demo completed successfully!")
        
    except Exception as e:
        logger.error(f"❌ Demo failed: {e}")
        raise
    finally:
        # Clean up
        await close_database()
        logger.info("🔒 Database connection closed")


if __name__ == "__main__":
    asyncio.run(demo_migration_system())