import re
import logging
from typing import List, Optional, Tuple, Dict, Any

logger = logging.getLogger(__name__)

class MediaMatcher:
    @staticmethod
    def score_track(title: str, language: str, preferences: List[str], is_subtitle: bool = False) -> int:
        """
        Calculate a score for a track based on how well it matches preferences.
        """
        score = 0
        text = f"{title} {language}".lower()
        
        # 1. Expand preferences with common mappings
        lang_map = {
            "jpn": ["japanese", "jpn", "ja"],
            "eng": ["english", "eng", "en"],
            "pol": ["polish", "pol", "pl"],
            "rus": ["russian", "rus", "ru"],
            "ger": ["german", "ger", "de"],
            "fra": ["french", "fra", "fr"],
        }
        
        expanded_prefs = []
        for p in preferences:
            p_low = p.lower()
            expanded_prefs.append(p_low)
            if p_low in lang_map:
                expanded_prefs.extend(lang_map[p_low])

        # 2. Check Language Match
        lang_match = False
        for pref in expanded_prefs:
            if pref in text:
                score += 100
                lang_match = True
                break
        
        # 3. Priority for Audio/Subtitles
        if not is_subtitle:
            # Audio: Favor Japanese as a "natural" default for anime if no other preference matches better
            if "japanese" in text or "jpn" in text or " ja " in text or "[ja]" in text:
                score += 30
        else:
            # Subtitles: Favor Dialogue
            if "dialogue" in text:
                score += 50
            # Penalize Signs/Songs (unless it's the only one matching)
            if "signs" in text or "songs" in text:
                score -= 40
            # Higher score if it has BOTH preference AND dialogue
            if "dialogue" in text and lang_match:
                score += 20
        
        if not lang_match and score <= 30:
            return -100 # No strong match
            
        return score

    @staticmethod
    def get_best_track(tracks: List[Dict[str, Any]], preferences: str, is_subtitle: bool = False) -> Optional[int]:
        """
        Given a list of VLC-style tracks (id, name), find the one that fits best.
        VLC name usually looks like: "Dialogue@CR - [English]" or "Track 1 - [Japanese]"
        """
        if not tracks or not preferences:
            return None
            
        pref_list = [p.strip() for p in preferences.split(",") if p.strip()]
        best_id = None
        max_score = -999
        
        for t in tracks:
            track_id = t["id"]
            if track_id == -1: # Disable track
                continue
                
            name = t["name"]
            # VLC name often has [Lang] or is just the title.
            # We treat the whole name as both title and language field for matching.
            score = MediaMatcher.score_track(name, "", pref_list, is_subtitle)
            
            logger.debug(f"Track '{name}' (ID: {track_id}) Score: {score}")
            
            if score > max_score:
                max_score = score
                best_id = track_id
                
        # Only return if we actually found a positive match or at least something better than 'low preference'
        if max_score > -50: 
            return best_id
        return None
