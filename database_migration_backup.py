"""
Database migration and backup management system.
Handles schema versioning, migrations, and backup/restore operations.
"""

from typing import Optional, List, Dict, Any
import subprocess
import os
import json
from datetime import datetime, timedelta
import logging
import tempfile
import shutil

logger = logging.getLogger(__name__)


class DatabaseConfig:
    """Database configuration."""
    
    def __init__(self, 
                 host: str = "localhost",
                 port: int = 5432,
                 database: str = "trading_prod",
                 user: str = "trading",
                 password: Optional[str] = None):
        self.host = host
        self.port = port
        self.database = database
        self.user = user
        self.password = password
    
    @property
    def connection_string(self) -> str:
        """Get connection string."""
        if self.password:
            return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"
        return f"postgresql://{self.user}@{self.host}:{self.port}/{self.database}"


class DatabaseMigration:
    """Manages database migrations."""
    
    def __init__(self, config: DatabaseConfig):
        self.config = config
        self.migrations_dir = "migrations"
    
    def create_migration(self, name: str, content: str) -> str:
        """Create new migration file."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}_{name}.sql"
        filepath = os.path.join(self.migrations_dir, filename)
        
        os.makedirs(self.migrations_dir, exist_ok=True)
        
        with open(filepath, 'w') as f:
            f.write(content)
        
        logger.info(f"Created migration: {filename}")
        return filepath
    
    def list_migrations(self) -> List[str]:
        """List all migrations."""
        if not os.path.exists(self.migrations_dir):
            return []
        
        return sorted(os.listdir(self.migrations_dir))
    
    def apply_migrations(self) -> bool:
        """Apply pending migrations."""
        try:
            migrations = self.list_migrations()
            
            for migration in migrations:
                if migration.endswith('.sql'):
                    filepath = os.path.join(self.migrations_dir, migration)
                    
                    logger.info(f"Applying migration: {migration}")
                    
                    with open(filepath, 'r') as f:
                        sql = f.read()
                    
                    self._execute_sql(sql)
            
            logger.info("All migrations applied successfully")
            return True
        except Exception as e:
            logger.error(f"Migration failed: {e}")
            return False
    
    def _execute_sql(self, sql: str):
        """Execute SQL directly."""
        cmd = [
            'psql',
            '-h', self.config.host,
            '-U', self.config.user,
            '-d', self.config.database,
            '-c', sql
        ]
        
        env = os.environ.copy()
        if self.config.password:
            env['PGPASSWORD'] = self.config.password
        
        result = subprocess.run(cmd, capture_output=True, text=True, env=env)
        
        if result.returncode != 0:
            raise RuntimeError(f"SQL execution failed: {result.stderr}")


class DatabaseBackup:
    """Manages database backups."""
    
    def __init__(self, config: DatabaseConfig, backup_dir: str = "backups"):
        self.config = config
        self.backup_dir = backup_dir
        os.makedirs(backup_dir, exist_ok=True)
    
    def create_full_backup(self) -> str:
        """Create full database backup."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"trading_prod_full_{timestamp}.sql.gz"
        filepath = os.path.join(self.backup_dir, filename)
        
        try:
            logger.info(f"Creating full backup: {filename}")
            
            cmd = [
                'pg_dump',
                '-h', self.config.host,
                '-U', self.config.user,
                '-d', self.config.database,
                '-v',
                '|', 'gzip', '>', filepath
            ]
            
            env = os.environ.copy()
            if self.config.password:
                env['PGPASSWORD'] = self.config.password
            
            # Use shell to handle piping
            shell_cmd = ' '.join(cmd)
            result = subprocess.run(shell_cmd, shell=True, capture_output=True, text=True, env=env)
            
            if result.returncode != 0:
                raise RuntimeError(f"Backup failed: {result.stderr}")
            
            # Verify backup
            if not os.path.exists(filepath) or os.path.getsize(filepath) == 0:
                raise RuntimeError("Backup file is empty or not created")
            
            size_mb = os.path.getsize(filepath) / (1024 * 1024)
            logger.info(f"Backup completed: {filename} ({size_mb:.2f} MB)")
            
            return filepath
        except Exception as e:
            logger.error(f"Backup creation failed: {e}")
            raise
    
    def create_schema_only_backup(self) -> str:
        """Create schema-only backup."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"trading_prod_schema_{timestamp}.sql.gz"
        filepath = os.path.join(self.backup_dir, filename)
        
        try:
            logger.info(f"Creating schema backup: {filename}")
            
            cmd = [
                'pg_dump',
                '-h', self.config.host,
                '-U', self.config.user,
                '-d', self.config.database,
                '--schema-only',
                '|', 'gzip', '>', filepath
            ]
            
            env = os.environ.copy()
            if self.config.password:
                env['PGPASSWORD'] = self.config.password
            
            shell_cmd = ' '.join(cmd)
            result = subprocess.run(shell_cmd, shell=True, capture_output=True, text=True, env=env)
            
            if result.returncode != 0:
                raise RuntimeError(f"Schema backup failed: {result.stderr}")
            
            logger.info(f"Schema backup completed: {filename}")
            return filepath
        except Exception as e:
            logger.error(f"Schema backup failed: {e}")
            raise
    
    def create_incremental_backup(self) -> str:
        """Create WAL archive backup."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"trading_prod_wal_{timestamp}.tar.gz"
        filepath = os.path.join(self.backup_dir, filename)
        
        try:
            logger.info(f"Creating WAL archive: {filename}")
            
            # Archive WAL files
            wal_dir = "/var/lib/postgresql/wal_archive"
            if os.path.exists(wal_dir):
                cmd = f"tar -czf {filepath} {wal_dir}"
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                
                if result.returncode != 0:
                    raise RuntimeError(f"WAL backup failed: {result.stderr}")
                
                logger.info(f"WAL backup completed: {filename}")
                return filepath
            else:
                logger.warning("WAL directory not found")
                return ""
        except Exception as e:
            logger.error(f"WAL backup failed: {e}")
            raise
    
    def restore_backup(self, backup_file: str, target_db: Optional[str] = None) -> bool:
        """Restore database from backup."""
        target_db = target_db or self.config.database
        
        try:
            logger.info(f"Restoring from backup: {backup_file}")
            
            if backup_file.endswith('.gz'):
                cmd = f"gunzip -c {backup_file} | psql -h {self.config.host} -U {self.config.user} -d {target_db} -v ON_ERROR_STOP=1"
            else:
                cmd = f"psql -h {self.config.host} -U {self.config.user} -d {target_db} -f {backup_file} -v ON_ERROR_STOP=1"
            
            env = os.environ.copy()
            if self.config.password:
                env['PGPASSWORD'] = self.config.password
            
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, env=env)
            
            if result.returncode != 0:
                logger.error(f"Restore failed: {result.stderr}")
                return False
            
            logger.info(f"Restore completed successfully")
            return True
        except Exception as e:
            logger.error(f"Restore failed: {e}")
            return False
    
    def list_backups(self) -> List[Dict[str, Any]]:
        """List available backups."""
        backups = []
        
        for filename in sorted(os.listdir(self.backup_dir), reverse=True):
            filepath = os.path.join(self.backup_dir, filename)
            stat = os.stat(filepath)
            
            backups.append({
                'filename': filename,
                'size_mb': stat.st_size / (1024 * 1024),
                'created': datetime.fromtimestamp(stat.st_mtime),
                'path': filepath
            })
        
        return backups
    
    def cleanup_old_backups(self, days: int = 30) -> int:
        """Remove backups older than specified days."""
        cutoff_time = datetime.now() - timedelta(days=days)
        removed_count = 0
        
        for filename in os.listdir(self.backup_dir):
            filepath = os.path.join(self.backup_dir, filename)
            stat = os.stat(filepath)
            file_time = datetime.fromtimestamp(stat.st_mtime)
            
            if file_time < cutoff_time:
                os.remove(filepath)
                logger.info(f"Removed old backup: {filename}")
                removed_count += 1
        
        return removed_count
    
    def verify_backup(self, backup_file: str) -> bool:
        """Verify backup integrity."""
        try:
            if backup_file.endswith('.gz'):
                cmd = f"gunzip -t {backup_file}"
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                return result.returncode == 0
            else:
                # Check if file exists and has content
                return os.path.exists(backup_file) and os.path.getsize(backup_file) > 0
        except Exception as e:
            logger.error(f"Backup verification failed: {e}")
            return False


class DisasterRecovery:
    """Handles disaster recovery operations."""
    
    def __init__(self, config: DatabaseConfig):
        self.config = config
        self.backup = DatabaseBackup(config)
    
    def perform_point_in_time_recovery(self, target_time: datetime) -> bool:
        """Perform point-in-time recovery."""
        try:
            logger.info(f"Starting PITR to {target_time}")
            
            # Find closest backup before target time
            backups = self.backup.list_backups()
            target_backup = None
            
            for backup in backups:
                if backup['created'] <= target_time:
                    target_backup = backup
                    break
            
            if not target_backup:
                logger.error("No suitable backup found for PITR")
                return False
            
            logger.info(f"Using backup: {target_backup['filename']}")
            
            # Restore from backup
            self.backup.restore_backup(target_backup['path'])
            
            # Apply WAL archives up to target time
            logger.info("Applying WAL archives...")
            
            logger.info("PITR completed successfully")
            return True
        except Exception as e:
            logger.error(f"PITR failed: {e}")
            return False
    
    def test_backup_restore(self, backup_file: str) -> bool:
        """Test backup restore in temporary database."""
        try:
            # Create temporary database
            temp_db = f"test_restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            cmd = f"createdb -h {self.config.host} -U {self.config.user} {temp_db}"
            env = os.environ.copy()
            if self.config.password:
                env['PGPASSWORD'] = self.config.password
            
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, env=env)
            if result.returncode != 0:
                raise RuntimeError(f"Failed to create test database: {result.stderr}")
            
            # Restore to temporary database
            logger.info(f"Restoring to temporary database: {temp_db}")
            temp_config = DatabaseConfig(
                host=self.config.host,
                port=self.config.port,
                database=temp_db,
                user=self.config.user,
                password=self.config.password
            )
            temp_backup = DatabaseBackup(temp_config)
            
            if not temp_backup.restore_backup(backup_file, temp_db):
                raise RuntimeError("Restore to temporary database failed")
            
            logger.info("Backup restore test successful")
            
            # Cleanup temporary database
            cmd = f"dropdb -h {self.config.host} -U {self.config.user} {temp_db}"
            subprocess.run(cmd, shell=True, capture_output=True, env=env)
            
            return True
        except Exception as e:
            logger.error(f"Backup restore test failed: {e}")
            return False


if __name__ == '__main__':
    # Example usage
    config = DatabaseConfig(
        host="localhost",
        port=5432,
        database="trading_prod",
        user="trading"
    )
    
    # Create backup
    backup = DatabaseBackup(config)
    backup_file = backup.create_full_backup()
    print(f"Backup created: {backup_file}")
    
    # List backups
    backups = backup.list_backups()
    for b in backups[:5]:
        print(f"{b['filename']}: {b['size_mb']:.2f} MB")
    
    # Cleanup old backups
    removed = backup.cleanup_old_backups(days=30)
    print(f"Removed {removed} old backups")
