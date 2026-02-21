import re
import os
from typing import Optional, List

class TitleExtractor:
    """
    Utility class to extract episode titles from filenames based on common patterns.
    """
    
    # regex patterns for extraction
    PATTERNS = [
        # Series name - S00E00 - Episode Title.mkv
        re.compile(r'.*?\s-\sS\d+E\d+\s-\s(.*?)$', re.IGNORECASE),
        # S00E00-Episode Title.mkv
        re.compile(r'S\d+E\d+-(.*?)$', re.IGNORECASE),
        # Series name - 01 - Episode Title.mkv
        re.compile(r'.*?\s-\s\d+\s-\s(.*?)$', re.IGNORECASE),
        # Fallback: anything after S00E00 or EP 00 if there's a delimiter
        re.compile(r'(?:S\d+E\d+|EP\s?\d+)[\s._-]*(.*?)$', re.IGNORECASE),
    ]

    CLEANUP_PATTERNS = [
        re.compile(r'\[.*?\]'),  # [BD], [1080p], etc.
        re.compile(r'\(.*?\)')   # (Dual Audio), etc.
    ]

    @classmethod
    def extract(cls, filename: str) -> Optional[str]:
        """
        Attempts to extract a title from a filename.
        Returns the title string if found, otherwise None.
        """
        # Remove extension first
        name_no_ext = os.path.splitext(filename)[0]
        
        # Initial cleanup of tags to avoid interference
        cleaned_name = name_no_ext
        for p in cls.CLEANUP_PATTERNS:
            cleaned_name = p.sub('', cleaned_name)
        
        cleaned_name = cleaned_name.strip()
        
        # Try each pattern
        for pattern in cls.PATTERNS:
            match = pattern.search(cleaned_name)
            if match:
                title = match.group(1).strip()
                # Secondary cleanup (remove trailing dashes/underscores/dots)
                title = re.sub(r'^[._\-\s]+', '', title)
                title = re.sub(r'[._\-\s]+$', '', title)
                
                if title:
                    return title
                    
        return None

    @classmethod
    def process_filename(cls, filename: str) -> str:
        """
        Processes a filename and returns the best guess title.
        If extraction fails, returns the cleaned filename itself.
        """
        extracted = cls.extract(filename)
        if extracted:
            return extracted
            
        # Fallback: Just clean the filename
        name = os.path.splitext(filename)[0]
        for p in cls.CLEANUP_PATTERNS:
            name = p.sub('', name)
        return name.strip()
