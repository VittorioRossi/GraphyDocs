import os
import zipfile
import shutil
from typing import List, Optional
from pathlib import Path

class FileSystemOps:
    @staticmethod
    def unzip_folder(zip_path: str, extract_path: Optional[str] = None) -> str:
        """
        Unzip a folder to specified path or same directory as zip file.
        
        Args:
            zip_path: Path to zip file
            extract_path: Path to extract files to (optional)
            
        Returns:
            Path where files were extracted
        """
        if not extract_path:
            extract_path = os.path.dirname(zip_path)
            
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_path)
            
        return extract_path

    @staticmethod
    def get_all_files(folder_path: str, pattern: Optional[str] = None) -> List[str]:
        """
        Get all files from a folder, optionally matching a pattern.
        
        Args:
            folder_path: Path to folder
            pattern: File pattern to match (e.g. '*.txt')
            
        Returns:
            List of file paths
        """
        files = []
        for root, _, filenames in os.walk(folder_path):
            for filename in filenames:
                if pattern:
                    if Path(filename).match(pattern):
                        files.append(os.path.join(root, filename))
                else:
                    files.append(os.path.join(root, filename))
        return files

    @staticmethod
    def save_files(files: List[str], destination: str, create_dirs: bool = True) -> None:
        """
        Save files to a destination folder.
        
        Args:
            files: List of file paths to save
            destination: Destination folder path
            create_dirs: Create directories if they don't exist
        """
        if create_dirs:
            os.makedirs(destination, exist_ok=True)
            
        for file_path in files:
            filename = os.path.basename(file_path)
            dest_path = os.path.join(destination, filename)
            shutil.copy2(file_path, dest_path)