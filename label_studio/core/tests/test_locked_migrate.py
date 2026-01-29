"""Tests for the locked_migrate management command."""
from unittest.mock import MagicMock, patch, call
from io import StringIO

import pytest
from django.test import TestCase
from django.core.management import call_command


class TestLockedMigrateCommand(TestCase):
    """Test locked_migrate command works with different database vendors."""

    @patch('label_studio.core.management.commands.locked_migrate.connections')
    @patch('label_studio.core.management.commands.locked_migrate.MigrateCommand.handle')
    def test_uses_advisory_lock_for_postgresql(self, mock_super_handle, mock_connections):
        """Test that PostgreSQL advisory locks are used for PostgreSQL."""
        # Setup mock connection
        mock_connection = MagicMock()
        mock_connection.vendor = 'postgresql'
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = [True]  # Lock acquired
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor
        
        mock_connections.create_connection.return_value = mock_connection
        
        # Call command
        out = StringIO()
        call_command('locked_migrate', '--no-color', stdout=out, verbosity=0)
        
        # Verify advisory lock was attempted
        mock_cursor.execute.assert_called_once()
        call_args = mock_cursor.execute.call_args[0][0]
        assert 'pg_try_advisory_xact_lock' in call_args
        
        # Verify migration was executed
        mock_super_handle.assert_called_once()
        
        # Verify connection was closed
        mock_connection.close.assert_called_once()

    @patch('label_studio.core.management.commands.locked_migrate.connections')
    @patch('label_studio.core.management.commands.locked_migrate.MigrateCommand.handle')
    def test_skips_advisory_lock_for_mysql(self, mock_super_handle, mock_connections):
        """Test that advisory locks are skipped for MySQL/MariaDB."""
        # Setup mock connection
        mock_connection = MagicMock()
        mock_connection.vendor = 'mysql'
        mock_cursor = MagicMock()
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor
        
        mock_connections.create_connection.return_value = mock_connection
        
        # Call command
        out = StringIO()
        call_command('locked_migrate', '--no-color', stdout=out, verbosity=0)
        
        # Verify advisory lock was NOT attempted (no cursor execute for MySQL)
        mock_cursor.execute.assert_not_called()
        
        # Verify migration was still executed
        mock_super_handle.assert_called_once()
        
        # Verify connection was closed
        mock_connection.close.assert_called_once()

    @patch('label_studio.core.management.commands.locked_migrate.connections')
    @patch('label_studio.core.management.commands.locked_migrate.MigrateCommand.handle')
    def test_skips_advisory_lock_for_sqlite(self, mock_super_handle, mock_connections):
        """Test that advisory locks are skipped for SQLite."""
        # Setup mock connection
        mock_connection = MagicMock()
        mock_connection.vendor = 'sqlite'
        mock_cursor = MagicMock()
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor
        
        mock_connections.create_connection.return_value = mock_connection
        
        # Call command
        out = StringIO()
        call_command('locked_migrate', '--no-color', stdout=out, verbosity=0)
        
        # Verify advisory lock was NOT attempted
        mock_cursor.execute.assert_not_called()
        
        # Verify migration was still executed
        mock_super_handle.assert_called_once()
        
        # Verify connection was closed
        mock_connection.close.assert_called_once()

    @patch('label_studio.core.management.commands.locked_migrate.connections')
    @patch('label_studio.core.management.commands.locked_migrate.MigrateCommand.handle')
    @patch('label_studio.core.management.commands.locked_migrate.time.sleep')
    def test_retries_lock_acquisition_for_postgresql(self, mock_sleep, mock_super_handle, mock_connections):
        """Test that lock acquisition is retried for PostgreSQL."""
        # Setup mock connection
        mock_connection = MagicMock()
        mock_connection.vendor = 'postgresql'
        mock_cursor = MagicMock()
        # First attempt fails, second succeeds
        mock_cursor.fetchone.side_effect = [[False], [True]]
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor
        
        mock_connections.create_connection.return_value = mock_connection
        
        # Call command
        out = StringIO()
        call_command('locked_migrate', '--no-color', stdout=out, verbosity=0)
        
        # Verify lock acquisition was attempted twice
        assert mock_cursor.execute.call_count == 2
        
        # Verify sleep was called once (between retries)
        mock_sleep.assert_called_once()
        
        # Verify migration was executed
        mock_super_handle.assert_called_once()

    @patch('label_studio.core.management.commands.locked_migrate.connections')
    @patch('label_studio.core.management.commands.locked_migrate.MigrateCommand.handle')
    @patch('label_studio.core.management.commands.locked_migrate.time.time')
    @patch('label_studio.core.management.commands.locked_migrate.time.sleep')
    def test_timeout_when_lock_not_acquired(self, mock_sleep, mock_time, mock_super_handle, mock_connections):
        """Test that TimeoutError is raised when lock cannot be acquired."""
        # Setup mock connection
        mock_connection = MagicMock()
        mock_connection.vendor = 'postgresql'
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = [False]  # Lock never acquired
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor
        
        mock_connections.create_connection.return_value = mock_connection
        
        # Mock time to simulate timeout
        mock_time.side_effect = [0, 0, 301]  # Start, first retry, timeout
        
        # Call command and expect TimeoutError
        with pytest.raises(TimeoutError, match='Failed to acquire PostgreSQL advisory transaction lock'):
            call_command('locked_migrate', '--no-color', verbosity=0)
        
        # Verify connection was closed even on error
        mock_connection.close.assert_called_once()
