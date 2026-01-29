from django.db import migrations, connections
from django.conf import settings
from core.redis import start_job_async_or_sync
from core.models import AsyncMigrationStatus
import logging

logger = logging.getLogger(__name__)
migration_name = '0030_project_search_vector_index'

# Actual DDL to run
def forward_migration(migration_name, db_alias):
    migration = AsyncMigrationStatus.objects.using(db_alias).create(
        name=migration_name,
        status=AsyncMigrationStatus.STATUS_STARTED,
    )
    logger.debug(f'Start async migration {migration_name}')
    
    # Check database backend and use appropriate SQL
    # PostgreSQL: Use CONCURRENTLY and specific index types (BRIN, GIN, etc.)
    # MySQL: GIN indexes are not supported, skip this index as search_vector is PostgreSQL-specific
    conn = connections[db_alias]
    
    if conn.vendor == 'postgresql':
        sql = '''
        CREATE INDEX CONCURRENTLY IF NOT EXISTS project_search_vector_idx ON project USING GIN (search_vector);
        '''
        with conn.cursor() as cursor:
            cursor.execute(sql)
    elif conn.vendor == 'mysql':
        # MySQL doesn't support tsvector or GIN indexes
        # This index is PostgreSQL-specific for full-text search, skip on MySQL
        logger.info('MySQL detected; skipping GIN index creation (search_vector is PostgreSQL-specific)')
    else:
        logger.debug('SQLite or other database; skipping index creation')
    
    migration.status = AsyncMigrationStatus.STATUS_FINISHED
    migration.save(using=db_alias)
    logger.debug(f'Async migration {migration_name} complete')

# Reverse DDL
def reverse_migration(migration_name, db_alias):
    migration = AsyncMigrationStatus.objects.using(db_alias).create(
        name=migration_name,
        status=AsyncMigrationStatus.STATUS_STARTED,
    )
    logger.debug(f'Start async migration rollback {migration_name}')
    
    # Drop index (handle database differences)
    conn = connections[db_alias]
    
    if conn.vendor == 'postgresql':
        sql = 'DROP INDEX CONCURRENTLY IF EXISTS "project_search_vector_idx";'
        with conn.cursor() as cursor:
            cursor.execute(sql)
    elif conn.vendor == 'mysql':
        # Index wasn't created on MySQL, nothing to drop
        logger.info('MySQL detected; skipping index drop (index was not created)')
    else:
        logger.debug('SQLite or other database; skipping index drop')
    
    migration.status = AsyncMigrationStatus.STATUS_FINISHED
    migration.save(using=db_alias)
    logger.debug(f'Async migration rollback {migration_name} complete')

# Hook into Django migration
def forwards(apps, schema_editor):
    db_alias = schema_editor.connection.alias
    conn = connections[db_alias]
    if conn.vendor in ('postgresql', 'mysql'):
        start_job_async_or_sync(forward_migration, migration_name=migration_name, db_alias=db_alias)
    else:
        logger.debug(f'Database vendor {conn.vendor}; skipping index creation')

def backwards(apps, schema_editor):
    db_alias = schema_editor.connection.alias
    conn = connections[db_alias]
    if conn.vendor in ('postgresql', 'mysql'):
        start_job_async_or_sync(reverse_migration, migration_name=migration_name, db_alias=db_alias) 
    else:
        logger.debug(f'Database vendor {conn.vendor}; skipping index drop')

class Migration(migrations.Migration):
    atomic = False
    dependencies = [
        ('projects', '0029_project_search_vector_and_more'),
    ]
    operations = [
        migrations.RunPython(forwards, backwards),
    ]
