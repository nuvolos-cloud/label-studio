"""Tests for io_storages migration 0017 vendor-specific foreign key handling."""
from unittest.mock import MagicMock, patch
from django.test import TestCase
import importlib.util
import sys
from pathlib import Path


class TestMigration0017ForeignKeySQL(TestCase):
    """Test that migration 0017 properly handles different database vendors."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Import the migration module dynamically since it starts with a number
        migration_path = Path(__file__).parent.parent / 'migrations' / '0017_auto_20240731_1638.py'
        spec = importlib.util.spec_from_file_location("migration_0017", migration_path)
        migration_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration_module)
        cls.create_fk_sql = migration_module.create_fk_sql

    def test_postgresql_uses_deferrable_constraints(self):
        """Test that PostgreSQL gets DEFERRABLE INITIALLY DEFERRED."""
        sql = self.create_fk_sql(
            table_name='test_table',
            constraint_name='test_fk',
            column_name='test_col',
            referenced_table='ref_table',
            referenced_column='ref_col',
            vendor='postgresql'
        )
        
        # Should contain PostgreSQL-specific syntax
        assert 'DEFERRABLE INITIALLY DEFERRED' in sql
        assert 'DROP CONSTRAINT IF EXISTS' in sql
        assert 'ADD CONSTRAINT' in sql
        assert 'FOREIGN KEY' in sql

    def test_mysql_uses_standard_foreign_key(self):
        """Test that MySQL gets standard FK without DEFERRABLE."""
        sql = self.create_fk_sql(
            table_name='test_table',
            constraint_name='test_fk',
            column_name='test_col',
            referenced_table='ref_table',
            referenced_column='ref_col',
            vendor='mysql'
        )
        
        # Should NOT contain PostgreSQL-specific syntax
        assert 'DEFERRABLE' not in sql
        assert 'INITIALLY DEFERRED' not in sql
        
        # Should contain MySQL FK syntax
        assert 'DROP FOREIGN KEY IF EXISTS' in sql
        assert 'ADD CONSTRAINT' in sql
        assert 'FOREIGN KEY' in sql

    def test_sqlite_returns_comment_only(self):
        """Test that SQLite gets a comment (doesn't support FK alteration)."""
        sql = self.create_fk_sql(
            table_name='test_table',
            constraint_name='test_fk',
            column_name='test_col',
            referenced_table='ref_table',
            referenced_column='ref_col',
            vendor='sqlite'
        )
        
        # Should be a comment
        assert '--' in sql
        assert 'Foreign key constraint' in sql
        # Should NOT contain actual SQL commands
        assert 'ADD CONSTRAINT' not in sql

    def test_default_vendor_is_postgresql(self):
        """Test that the default vendor parameter is PostgreSQL."""
        sql = self.create_fk_sql(
            table_name='test_table',
            constraint_name='test_fk',
            column_name='test_col',
            referenced_table='ref_table',
            referenced_column='ref_col'
            # vendor not specified - should default to 'postgresql'
        )
        
        # Should get PostgreSQL-specific syntax by default
        assert 'DEFERRABLE INITIALLY DEFERRED' in sql
