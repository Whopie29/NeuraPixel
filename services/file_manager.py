import os
import logging
import hashlib
import shutil
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class FileManager:
    """
    File management service for organizing and maintaining generated images.
    Handles file organization, cleanup, and secure access to generated images.
    """
    
    def __init__(self, base_directory: str = "generated_images", max_age_days: int = 30):
        """
        Initialize the file manager.
        
        Args:
            base_directory: Base directory for storing generated images
            max_age_days: Maximum age in days before images are eligible for cleanup
        """
        self.base_directory = Path(base_directory)
        self.max_age_days = max_age_days
        self.cleanup_log_file = self.base_directory / "cleanup_log.txt"
        
        # Ensure base directory exists
        self._ensure_base_directory()
    
    def _ensure_base_directory(self) -> None:
        """Ensure the base directory structure exists."""
        try:
            self.base_directory.mkdir(parents=True, exist_ok=True)
            logger.info(f"Base directory ensured: {self.base_directory}")
        except Exception as e:
            logger.error(f"Failed to create base directory: {e}")
            raise RuntimeError(f"Could not create base directory: {e}")
    
    def create_filename(self, prompt: str, extension: str = "png") -> str:
        """
        Create a unique filename based on timestamp and prompt hash.
        
        Args:
            prompt: The text prompt used for generation
            extension: File extension (without dot)
            
        Returns:
            Unique filename string
        """
        # Create timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]  # Include milliseconds
        
        # Create hash of prompt for uniqueness and to avoid filesystem issues
        prompt_hash = hashlib.md5(prompt.encode('utf-8')).hexdigest()[:8]
        
        # Sanitize extension
        extension = extension.lstrip('.')
        
        return f"{timestamp}_{prompt_hash}.{extension}"
    
    def get_storage_path(self, date: Optional[datetime] = None) -> Path:
        """
        Get the storage path for a specific date.
        
        Args:
            date: Date for the storage path (defaults to today)
            
        Returns:
            Path object for the storage directory
        """
        if date is None:
            date = datetime.now()
        
        date_dir = date.strftime("%Y-%m-%d")
        return self.base_directory / date_dir
    
    def ensure_storage_directory(self, date: Optional[datetime] = None) -> Path:
        """
        Ensure the storage directory exists for a specific date.
        
        Args:
            date: Date for the storage directory (defaults to today)
            
        Returns:
            Path to the storage directory
        """
        storage_path = self.get_storage_path(date)
        
        try:
            storage_path.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Storage directory ensured: {storage_path}")
            return storage_path
        except Exception as e:
            logger.error(f"Failed to create storage directory {storage_path}: {e}")
            raise RuntimeError(f"Could not create storage directory: {e}")
    
    def save_file(self, file_data: bytes, filename: str, date: Optional[datetime] = None) -> Dict[str, str]:
        """
        Save file data to the organized directory structure.
        
        Args:
            file_data: Binary file data to save
            filename: Name of the file
            date: Date for organization (defaults to today)
            
        Returns:
            Dictionary with file information
        """
        try:
            # Ensure storage directory exists
            storage_dir = self.ensure_storage_directory(date)
            
            # Create full file path
            filepath = storage_dir / filename
            
            # Write file data
            with open(filepath, 'wb') as f:
                f.write(file_data)
            
            # Get file size
            file_size = filepath.stat().st_size
            
            logger.info(f"File saved successfully: {filepath} ({file_size} bytes)")
            
            return {
                "filename": filename,
                "filepath": str(filepath),
                "relative_path": str(filepath.relative_to(self.base_directory)),
                "size": file_size,
                "date": (date or datetime.now()).strftime("%Y-%m-%d")
            }
            
        except Exception as e:
            logger.error(f"Failed to save file {filename}: {e}")
            raise RuntimeError(f"File saving failed: {e}")
    
    def get_file_path(self, filename: str, date: Optional[datetime] = None) -> Optional[Path]:
        """
        Get the full path to a file, searching in date-organized directories.
        
        Args:
            filename: Name of the file to find
            date: Specific date to search in (if None, searches recent dates)
            
        Returns:
            Path to the file if found, None otherwise
        """
        # If date is specified, check only that directory
        if date:
            filepath = self.get_storage_path(date) / filename
            return filepath if filepath.exists() else None
        
        # Search in recent directories (last 7 days)
        for days_back in range(7):
            search_date = datetime.now() - timedelta(days=days_back)
            filepath = self.get_storage_path(search_date) / filename
            if filepath.exists():
                return filepath
        
        return None
    
    def validate_filename(self, filename: str) -> bool:
        """
        Validate filename for security and format compliance.
        
        Args:
            filename: Filename to validate
            
        Returns:
            True if filename is valid, False otherwise
        """
        if not filename:
            return False
        
        # Check for directory traversal attempts
        if '..' in filename or '/' in filename or '\\' in filename:
            return False
        
        # Check for valid characters (alphanumeric, underscore, dot, hyphen)
        allowed_chars = set('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.-')
        if not all(c in allowed_chars for c in filename):
            return False
        
        # Check file extension
        allowed_extensions = {'.png', '.jpg', '.jpeg'}
        file_ext = Path(filename).suffix.lower()
        if file_ext not in allowed_extensions:
            return False
        
        return True
    
    def get_file_info(self, filename: str) -> Optional[Dict[str, any]]:
        """
        Get information about a file.
        
        Args:
            filename: Name of the file
            
        Returns:
            Dictionary with file information or None if not found
        """
        if not self.validate_filename(filename):
            return None
        
        filepath = self.get_file_path(filename)
        if not filepath or not filepath.exists():
            return None
        
        try:
            stat = filepath.stat()
            return {
                "filename": filename,
                "filepath": str(filepath),
                "size": stat.st_size,
                "created": datetime.fromtimestamp(stat.st_ctime),
                "modified": datetime.fromtimestamp(stat.st_mtime),
                "extension": filepath.suffix.lower()
            }
        except Exception as e:
            logger.error(f"Failed to get file info for {filename}: {e}")
            return None
    
    def list_files(self, date: Optional[datetime] = None, limit: Optional[int] = None) -> List[Dict[str, any]]:
        """
        List files in the storage directory.
        
        Args:
            date: Specific date to list files from (if None, lists from all dates)
            limit: Maximum number of files to return
            
        Returns:
            List of file information dictionaries
        """
        files = []
        
        try:
            if date:
                # List files from specific date
                storage_path = self.get_storage_path(date)
                if storage_path.exists():
                    for filepath in storage_path.iterdir():
                        if filepath.is_file() and self.validate_filename(filepath.name):
                            stat = filepath.stat()
                            files.append({
                                "filename": filepath.name,
                                "filepath": str(filepath),
                                "size": stat.st_size,
                                "created": datetime.fromtimestamp(stat.st_ctime),
                                "date": date.strftime("%Y-%m-%d")
                            })
            else:
                # List files from all date directories
                for date_dir in self.base_directory.iterdir():
                    if date_dir.is_dir() and date_dir.name != '__pycache__':
                        for filepath in date_dir.iterdir():
                            if filepath.is_file() and self.validate_filename(filepath.name):
                                stat = filepath.stat()
                                files.append({
                                    "filename": filepath.name,
                                    "filepath": str(filepath),
                                    "size": stat.st_size,
                                    "created": datetime.fromtimestamp(stat.st_ctime),
                                    "date": date_dir.name
                                })
            
            # Sort by creation time (newest first)
            files.sort(key=lambda x: x['created'], reverse=True)
            
            # Apply limit if specified
            if limit:
                files = files[:limit]
            
            return files
            
        except Exception as e:
            logger.error(f"Failed to list files: {e}")
            return []
    
    def get_storage_stats(self) -> Dict[str, any]:
        """
        Get statistics about the storage usage.
        
        Returns:
            Dictionary with storage statistics
        """
        try:
            total_files = 0
            total_size = 0
            directories = []
            
            for date_dir in self.base_directory.iterdir():
                if date_dir.is_dir() and date_dir.name != '__pycache__':
                    dir_files = 0
                    dir_size = 0
                    
                    for filepath in date_dir.iterdir():
                        if filepath.is_file():
                            stat = filepath.stat()
                            dir_files += 1
                            dir_size += stat.st_size
                    
                    if dir_files > 0:
                        directories.append({
                            "date": date_dir.name,
                            "files": dir_files,
                            "size": dir_size
                        })
                    
                    total_files += dir_files
                    total_size += dir_size
            
            return {
                "total_files": total_files,
                "total_size": total_size,
                "total_size_mb": round(total_size / (1024 * 1024), 2),
                "directories": directories,
                "base_directory": str(self.base_directory)
            }
            
        except Exception as e:
            logger.error(f"Failed to get storage stats: {e}")
            return {
                "total_files": 0,
                "total_size": 0,
                "total_size_mb": 0,
                "directories": [],
                "base_directory": str(self.base_directory),
                "error": str(e)
            }
    
    def cleanup_old_files(self, dry_run: bool = False) -> Dict[str, any]:
        """
        Clean up old files based on the configured maximum age.
        
        Args:
            dry_run: If True, only report what would be deleted without actually deleting
            
        Returns:
            Dictionary with cleanup results
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=self.max_age_days)
            files_to_delete = []
            total_size_to_free = 0
            
            # Find files older than cutoff date
            for date_dir in self.base_directory.iterdir():
                if not date_dir.is_dir() or date_dir.name == '__pycache__':
                    continue
                
                try:
                    # Parse directory date
                    dir_date = datetime.strptime(date_dir.name, "%Y-%m-%d")
                    
                    if dir_date < cutoff_date:
                        # Directory is old enough for cleanup
                        for filepath in date_dir.iterdir():
                            if filepath.is_file():
                                stat = filepath.stat()
                                files_to_delete.append({
                                    "filepath": str(filepath),
                                    "filename": filepath.name,
                                    "size": stat.st_size,
                                    "date": date_dir.name,
                                    "age_days": (datetime.now() - dir_date).days
                                })
                                total_size_to_free += stat.st_size
                
                except ValueError:
                    # Skip directories that don't match date format
                    logger.warning(f"Skipping directory with invalid date format: {date_dir.name}")
                    continue
            
            # Perform cleanup if not dry run
            deleted_files = []
            deleted_directories = []
            
            if not dry_run and files_to_delete:
                for file_info in files_to_delete:
                    try:
                        filepath = Path(file_info["filepath"])
                        if filepath.exists():
                            filepath.unlink()
                            deleted_files.append(file_info)
                            logger.info(f"Deleted old file: {filepath}")
                    except Exception as e:
                        logger.error(f"Failed to delete file {filepath}: {e}")
                
                # Remove empty directories
                for date_dir in self.base_directory.iterdir():
                    if date_dir.is_dir() and date_dir.name != '__pycache__':
                        try:
                            if not any(date_dir.iterdir()):  # Directory is empty
                                date_dir.rmdir()
                                deleted_directories.append(date_dir.name)
                                logger.info(f"Deleted empty directory: {date_dir}")
                        except Exception as e:
                            logger.error(f"Failed to delete directory {date_dir}: {e}")
            
            # Log cleanup results
            cleanup_result = {
                "dry_run": dry_run,
                "cutoff_date": cutoff_date.strftime("%Y-%m-%d"),
                "max_age_days": self.max_age_days,
                "files_found": len(files_to_delete),
                "files_deleted": len(deleted_files),
                "directories_deleted": len(deleted_directories),
                "size_freed_bytes": sum(f["size"] for f in deleted_files),
                "size_freed_mb": round(sum(f["size"] for f in deleted_files) / (1024 * 1024), 2),
                "potential_size_to_free_bytes": total_size_to_free,
                "potential_size_to_free_mb": round(total_size_to_free / (1024 * 1024), 2)
            }
            
            self._log_cleanup_results(cleanup_result)
            
            return cleanup_result
            
        except Exception as e:
            logger.error(f"Cleanup operation failed: {e}")
            return {
                "dry_run": dry_run,
                "error": str(e),
                "files_found": 0,
                "files_deleted": 0,
                "size_freed_bytes": 0
            }
    
    def _log_cleanup_results(self, results: Dict[str, any]) -> None:
        """
        Log cleanup results to the cleanup log file.
        
        Args:
            results: Cleanup results dictionary
        """
        try:
            log_entry = (
                f"{datetime.now().isoformat()} - "
                f"Cleanup {'(DRY RUN)' if results['dry_run'] else ''}: "
                f"Found {results['files_found']} files, "
                f"Deleted {results['files_deleted']} files, "
                f"Freed {results.get('size_freed_mb', 0)} MB\n"
            )
            
            with open(self.cleanup_log_file, 'a', encoding='utf-8') as f:
                f.write(log_entry)
                
        except Exception as e:
            logger.error(f"Failed to write cleanup log: {e}")
    
    def schedule_cleanup(self, force: bool = False) -> Dict[str, any]:
        """
        Schedule or perform cleanup based on last cleanup time.
        
        Args:
            force: If True, perform cleanup regardless of last cleanup time
            
        Returns:
            Dictionary with cleanup results
        """
        try:
            # Check when cleanup was last performed
            last_cleanup = self._get_last_cleanup_time()
            now = datetime.now()
            
            # Perform cleanup if forced or if it's been more than 24 hours
            if force or not last_cleanup or (now - last_cleanup).total_seconds() > 86400:
                logger.info("Performing scheduled cleanup")
                return self.cleanup_old_files(dry_run=False)
            else:
                time_until_next = 86400 - (now - last_cleanup).total_seconds()
                return {
                    "cleanup_performed": False,
                    "last_cleanup": last_cleanup.isoformat(),
                    "next_cleanup_in_seconds": int(time_until_next),
                    "message": "Cleanup not needed yet"
                }
                
        except Exception as e:
            logger.error(f"Scheduled cleanup failed: {e}")
            return {"error": str(e), "cleanup_performed": False}
    
    def _get_last_cleanup_time(self) -> Optional[datetime]:
        """
        Get the timestamp of the last cleanup operation.
        
        Returns:
            Datetime of last cleanup or None if no cleanup has been performed
        """
        try:
            if not self.cleanup_log_file.exists():
                return None
            
            # Read the last line of the cleanup log
            with open(self.cleanup_log_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                if not lines:
                    return None
                
                last_line = lines[-1].strip()
                if not last_line:
                    return None
                
                # Extract timestamp from the last line
                timestamp_str = last_line.split(' - ')[0]
                return datetime.fromisoformat(timestamp_str)
                
        except Exception as e:
            logger.error(f"Failed to get last cleanup time: {e}")
            return None
    
    def delete_file(self, filename: str) -> bool:
        """
        Delete a specific file.
        
        Args:
            filename: Name of the file to delete
            
        Returns:
            True if file was deleted successfully, False otherwise
        """
        if not self.validate_filename(filename):
            logger.warning(f"Invalid filename for deletion: {filename}")
            return False
        
        filepath = self.get_file_path(filename)
        if not filepath or not filepath.exists():
            logger.warning(f"File not found for deletion: {filename}")
            return False
        
        try:
            filepath.unlink()
            logger.info(f"File deleted successfully: {filepath}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete file {filename}: {e}")
            return False


class CleanupService:
    """
    Service for managing automated cleanup of old generated images.
    """
    
    def __init__(self, file_manager: FileManager):
        """
        Initialize the cleanup service.
        
        Args:
            file_manager: FileManager instance to use for cleanup operations
        """
        self.file_manager = file_manager
    
    def run_daily_cleanup(self) -> Dict[str, any]:
        """
        Run the daily cleanup routine.
        
        Returns:
            Dictionary with cleanup results
        """
        logger.info("Starting daily cleanup routine")
        return self.file_manager.schedule_cleanup()
    
    def run_manual_cleanup(self, dry_run: bool = False) -> Dict[str, any]:
        """
        Run manual cleanup operation.
        
        Args:
            dry_run: If True, only report what would be deleted
            
        Returns:
            Dictionary with cleanup results
        """
        logger.info(f"Starting manual cleanup {'(dry run)' if dry_run else ''}")
        return self.file_manager.cleanup_old_files(dry_run=dry_run)
    
    def get_cleanup_status(self) -> Dict[str, any]:
        """
        Get the current cleanup status and statistics.
        
        Returns:
            Dictionary with cleanup status information
        """
        try:
            storage_stats = self.file_manager.get_storage_stats()
            last_cleanup = self.file_manager._get_last_cleanup_time()
            
            # Estimate files eligible for cleanup
            dry_run_result = self.file_manager.cleanup_old_files(dry_run=True)
            
            return {
                "storage_stats": storage_stats,
                "last_cleanup": last_cleanup.isoformat() if last_cleanup else None,
                "files_eligible_for_cleanup": dry_run_result.get("files_found", 0),
                "potential_space_to_free_mb": dry_run_result.get("potential_size_to_free_mb", 0),
                "max_age_days": self.file_manager.max_age_days
            }
            
        except Exception as e:
            logger.error(f"Failed to get cleanup status: {e}")
            return {"error": str(e)}