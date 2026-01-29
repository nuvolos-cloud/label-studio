import logging
from typing import Callable, Dict, Optional, Tuple, Union

from core.redis import start_job_async_or_sync
from django.conf import settings
from django.db import connection
from rq import Retry

logger = logging.getLogger(__name__)


def get_sql_for_vendor(sql_dict: Dict[str, str], vendor: str) -> str:
    """Get SQL for a specific database vendor.
    
    Args:
        sql_dict: Dictionary with vendor-specific SQL. Keys can be:
                 - 'postgresql' or 'postgres'
                 - 'mysql'
                 - 'sqlite'
                 - 'default' (fallback for all vendors)
        vendor: Database vendor name from connection.vendor
    
    Returns:
        SQL string for the vendor, or default SQL if vendor-specific not found
    """
    # Normalize vendor name
    vendor_normalized = vendor.lower()
    if vendor_normalized.startswith('postgres'):
        vendor_normalized = 'postgresql'
    
    # Try to get vendor-specific SQL
    if vendor_normalized in sql_dict:
        return sql_dict[vendor_normalized]
    
    # Fall back to default
    if 'default' in sql_dict:
        return sql_dict['default']
    
    raise ValueError(f"No SQL found for vendor '{vendor}' and no default SQL provided")


def execute_sql_job(*, migration_name: str, sql: str, apply_on_sqlite: bool = False, reverse: bool = False) -> None:
    from core.models import AsyncMigrationStatus

    if not reverse:
        migration, created = AsyncMigrationStatus.objects.get_or_create(
            name=migration_name,
            defaults={'status': AsyncMigrationStatus.STATUS_STARTED},
        )
        if not created and migration.status == AsyncMigrationStatus.STATUS_FINISHED:
            logger.info(f'Migration {migration_name} already executed with status FINISHED')
            return
        if migration.status == AsyncMigrationStatus.STATUS_SCHEDULED:
            migration.status = AsyncMigrationStatus.STATUS_STARTED
            migration.save()

        try:
            if connection.vendor == 'sqlite' and not apply_on_sqlite:
                logger.info('SQLite detected; skipping SQL execution as requested')
            else:
                with connection.cursor() as cursor:
                    cursor.execute(sql)
            migration.status = AsyncMigrationStatus.STATUS_FINISHED
            migration.save()
        except Exception as e:
            logger.exception(f'Migration {migration_name} failed: {e}')
            migration.status = AsyncMigrationStatus.STATUS_ERROR
            if not migration.meta:
                migration.meta = {}
            migration.meta['error'] = str(e)
            migration.save()
            raise
    else:
        # Reverse path: don't create/update AsyncMigrationStatus. Just run SQL.
        try:
            if connection.vendor == 'sqlite' and not apply_on_sqlite:
                logger.info('SQLite detected; skipping SQL execution as requested (reverse)')
                return
            with connection.cursor() as cursor:
                cursor.execute(sql)
        except Exception as e:
            logger.exception(f'Reverse migration {migration_name} failed: {e}')
            raise


def make_sql_migration(
    sql_forwards: str,
    sql_backwards: str,
    *,
    apply_on_sqlite: bool = False,
    execute_immediately: bool = False,
    migration_name: str | None = None,
) -> Tuple[Callable, Callable]:
    """Return (forwards, backwards) for migrations.RunPython.

    - forwards: either schedules job or marks as SCHEDULED
    - backwards: always schedules job to execute reverse SQL
    """
    if not migration_name:
        raise ValueError("make_sql_migration requires explicit migration_name like 'app_label:migration_module'")
    mig_key = migration_name

    def forwards(apps, schema_editor):  # noqa: ARG001
        if schema_editor.connection.vendor == 'sqlite' and not apply_on_sqlite:
            logger.info('Skipping migration for SQLite (apply_on_sqlite=False)')
            return
        should_execute = execute_immediately or not settings.ALLOW_SCHEDULED_MIGRATIONS
        if should_execute:
            start_job_async_or_sync(
                execute_sql_job,
                migration_name=mig_key,
                sql=sql_forwards,
                apply_on_sqlite=apply_on_sqlite,
                reverse=False,
                retry=Retry(max=3, interval=[60, 300, 1800]),
            )
        else:
            AsyncMigrationStatus = apps.get_model('core', 'AsyncMigrationStatus')
            AsyncMigrationStatus.objects.get_or_create(
                name=mig_key,
                defaults={'status': 'SCHEDULED'},
            )

    def backwards(apps, schema_editor):  # noqa: ARG001
        start_job_async_or_sync(
            execute_sql_job,
            migration_name=mig_key,
            sql=sql_backwards,
            apply_on_sqlite=apply_on_sqlite,
            reverse=True,
            retry=Retry(max=3, interval=[60, 300, 1800]),
        )

    return forwards, backwards


def make_sql_migration_for_vendors(
    sql_forwards: Union[Dict[str, str], str],
    sql_backwards: Union[Dict[str, str], str],
    *,
    apply_on_sqlite: bool = False,
    execute_immediately: bool = False,
    migration_name: Optional[str] = None,
) -> Tuple[Callable, Callable]:
    """Return (forwards, backwards) for migrations.RunPython with vendor-specific SQL.
    
    This is similar to make_sql_migration but supports different SQL for different databases.
    
    Args:
        sql_forwards: Either a string (same SQL for all vendors) or a dict with vendor-specific SQL
        sql_backwards: Either a string (same SQL for all vendors) or a dict with vendor-specific SQL
        apply_on_sqlite: Whether to apply on SQLite
        execute_immediately: Whether to execute immediately or schedule
        migration_name: Migration name for tracking
    
    Returns:
        Tuple of (forwards, backwards) functions for migrations.RunPython
    """
    if not migration_name:
        raise ValueError("make_sql_migration_for_vendors requires explicit migration_name")
    
    mig_key = migration_name
    
    def forwards(apps, schema_editor):  # noqa: ARG001
        if schema_editor.connection.vendor == 'sqlite' and not apply_on_sqlite:
            logger.info('Skipping migration for SQLite (apply_on_sqlite=False)')
            return
        
        # Get vendor-specific SQL
        if isinstance(sql_forwards, dict):
            try:
                sql = get_sql_for_vendor(sql_forwards, schema_editor.connection.vendor)
            except ValueError as e:
                logger.warning(f"Skipping migration {mig_key}: {e}")
                return
        else:
            sql = sql_forwards
        
        should_execute = execute_immediately or not settings.ALLOW_SCHEDULED_MIGRATIONS
        if should_execute:
            start_job_async_or_sync(
                execute_sql_job,
                migration_name=mig_key,
                sql=sql,
                apply_on_sqlite=apply_on_sqlite,
                reverse=False,
                retry=Retry(max=3, interval=[60, 300, 1800]),
            )
        else:
            AsyncMigrationStatus = apps.get_model('core', 'AsyncMigrationStatus')
            AsyncMigrationStatus.objects.get_or_create(
                name=mig_key,
                defaults={'status': 'SCHEDULED'},
            )
    
    def backwards(apps, schema_editor):  # noqa: ARG001
        if schema_editor.connection.vendor == 'sqlite' and not apply_on_sqlite:
            logger.info("Skipping reverse migration for SQLite (apply_on_sqlite=False)")
            return
        
        # Get vendor-specific SQL
        if isinstance(sql_backwards, dict):
            try:
                sql = get_sql_for_vendor(sql_backwards, schema_editor.connection.vendor)
            except ValueError as e:
                logger.warning(f"Skipping reverse migration {mig_key}: {e}")
                return
        else:
            sql = sql_backwards
        
        start_job_async_or_sync(
            execute_sql_job,
            migration_name=mig_key,
            sql=sql,
            apply_on_sqlite=apply_on_sqlite,
            reverse=True,
            retry=Retry(max=3, interval=[60, 300, 1800]),
        )
    
    return forwards, backwards

