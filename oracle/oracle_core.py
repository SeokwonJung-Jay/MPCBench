"""
Level-agnostic oracle utilities for MPCBench.
No level-specific logic or policy knowledge here.
"""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from typing import List, Dict, Tuple


def parse_datetime(dt_str: str, tz_str: str = None) -> datetime:
    """
    Parse ISO-8601 datetime string to timezone-aware datetime object.
    ALWAYS returns tz-aware datetime. Prefer calling with tz_str explicitly.
    
    Args:
        dt_str: ISO-8601 datetime string
        tz_str: Timezone string (e.g., "Asia/Seoul"). If None and dt_str has no tz, uses UTC.
    
    Returns:
        Timezone-aware datetime object
    """
    # Handle format: "2026-01-19T13:00:00" or "2026-01-19T13:00:00+09:00"
    if 'T' in dt_str:
        if '+' in dt_str or dt_str.endswith('Z'):
            # Has timezone info, parse as-is but ensure tz-aware
            dt = datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
            if dt.tzinfo is None:
                # Should not happen, but handle it
                if tz_str:
                    dt = dt.replace(tzinfo=ZoneInfo(tz_str))
                else:
                    dt = dt.replace(tzinfo=ZoneInfo("UTC"))
            return dt
        else:
            # No timezone, attach provided timezone or UTC
            dt = datetime.fromisoformat(dt_str)
            if tz_str:
                dt = dt.replace(tzinfo=ZoneInfo(tz_str))
            else:
                dt = dt.replace(tzinfo=ZoneInfo("UTC"))
            return dt
    else:
        raise ValueError(f"Invalid datetime format: {dt_str}")


def to_iso_with_tz(dt: datetime, tz_str: str) -> str:
    """
    Format timezone-aware datetime to ISO-8601 string with timezone offset.
    
    Args:
        dt: Timezone-aware datetime object
        tz_str: Target timezone string (e.g., "Asia/Seoul")
    
    Returns:
        ISO-8601 string with timezone offset (e.g., "2026-01-19T13:00:00+09:00")
    """
    # Convert to target timezone
    target_tz = ZoneInfo(tz_str)
    dt_in_tz = dt.astimezone(target_tz)
    
    # Format with timezone offset (strftime %z gives +0900, we need +09:00)
    offset_str = dt_in_tz.strftime("%z")
    if offset_str:
        # Insert colon: +0900 -> +09:00
        offset_str = offset_str[:3] + ":" + offset_str[3:]
    
    return dt_in_tz.strftime("%Y-%m-%dT%H:%M:%S") + offset_str


def intervals_overlap(start1: datetime, end1: datetime, start2: datetime, end2: datetime) -> bool:
    """
    Check if two intervals overlap. Boundary-touching (end == start) is NOT overlap (half-open interval semantics).
    """
    return start1 < end2 and start2 < end1


def build_daily_interval(anchor_dt: datetime, start_hhmm: str, end_hhmm: str, tz_str: str) -> Tuple[datetime, datetime]:
    """
    Build a daily time interval on the same calendar day as anchor_dt.
    
    Args:
        anchor_dt: Timezone-aware datetime to anchor the day
        start_hhmm: Start time as "HH:MM" string (e.g., "09:00")
        end_hhmm: End time as "HH:MM" string (e.g., "18:00")
        tz_str: Timezone string (e.g., "Asia/Seoul")
    
    Returns:
        Tuple of (start_dt, end_dt) as timezone-aware datetimes on anchor_dt's calendar day.
        If end_dt <= start_dt (cross-midnight window), end_dt is advanced by 1 day.
    """
    target_tz = ZoneInfo(tz_str)
    anchor_in_tz = anchor_dt.astimezone(target_tz)
    
    # Parse HH:MM
    start_hour, start_min = map(int, start_hhmm.split(":"))
    end_hour, end_min = map(int, end_hhmm.split(":"))
    
    # Build on anchor's calendar day
    start_dt = anchor_in_tz.replace(hour=start_hour, minute=start_min, second=0, microsecond=0)
    end_dt = anchor_in_tz.replace(hour=end_hour, minute=end_min, second=0, microsecond=0)
    
    # Handle cross-midnight window
    if end_dt <= start_dt:
        end_dt = end_dt + timedelta(days=1)
    
    return (start_dt, end_dt)


def dt_in_days_of_week(dt: datetime, days_of_week: List[int]) -> bool:
    """
    Check if datetime falls on one of the specified weekdays.
    
    Args:
        dt: Timezone-aware datetime
        days_of_week: List of weekday integers (Mon=0, Tue=1, ..., Sun=6)
    
    Returns:
        True if dt.weekday() is in days_of_week
    """
    return dt.weekday() in days_of_week


def compute_common_free_windows(
    busy_intervals: List[Tuple[datetime, datetime]],
    window_start: datetime,
    window_end: datetime
) -> List[Tuple[datetime, datetime]]:
    """
    Compute common free time windows within a window, given busy intervals.
    
    Args:
        busy_intervals: List of (start, end) tuples for busy periods
        window_start: Start of the time window
        window_end: End of the time window
    
    Returns:
        List of (start, end) tuples for free periods, sorted by start time
    """
    if not busy_intervals:
        return [(window_start, window_end)]
    
    # Sort busy intervals by start time
    sorted_busy = sorted(busy_intervals, key=lambda x: x[0])
    
    free_intervals = []
    current_start = window_start
    
    for busy_start, busy_end in sorted_busy:
        # Skip busy intervals outside the window
        if busy_end <= window_start:
            continue
        if busy_start >= window_end:
            break
        
        # Clamp busy interval to window
        clamped_start = max(busy_start, window_start)
        clamped_end = min(busy_end, window_end)
        
        # If there's a gap before this busy interval, it's free
        if current_start < clamped_start:
            free_intervals.append((current_start, clamped_start))
        
        # Move current_start past this busy interval
        current_start = max(current_start, clamped_end)
    
    # Add remaining free time after last busy interval
    if current_start < window_end:
        free_intervals.append((current_start, window_end))
    
    return free_intervals


def enumerate_candidates(
    free_intervals: List[Tuple[datetime, datetime]],
    duration_min: int,
    time_window_start: datetime,
    time_window_end: datetime,
    tz_str: str,
    grid_minutes: int = 15
) -> List[Dict[str, str]]:
    """
    Enumerate all candidate meeting slots on a grid within free intervals.
    
    Args:
        free_intervals: List of (start, end) free time intervals
        duration_min: Meeting duration in minutes
        time_window_start: Start of the search window
        time_window_end: End of the search window
        tz_str: Timezone string for output formatting
        grid_minutes: Grid size in minutes (default 15)
    
    Returns:
        List of candidate dicts with "start" and "end" keys (ISO-8601 strings with timezone)
    """
    candidates = []
    duration_delta = timedelta(minutes=duration_min)
    grid_delta = timedelta(minutes=grid_minutes)
    
    # Round window start down to nearest grid point
    window_start_rounded = round_to_grid(time_window_start, grid_minutes)
    
    for free_start, free_end in free_intervals:
        # Start from the later of: free_start or window_start_rounded
        candidate_start = max(free_start, window_start_rounded)
        
        # Round candidate_start up to nearest grid point if needed
        if candidate_start.minute % grid_minutes != 0 or candidate_start.second != 0:
            # Round up to next grid point
            minutes_to_add = grid_minutes - (candidate_start.minute % grid_minutes)
            candidate_start = candidate_start.replace(second=0, microsecond=0) + timedelta(minutes=minutes_to_add)
        
        # Generate candidates on grid
        while candidate_start < free_end:
            candidate_end = candidate_start + duration_delta
            
            # Check if candidate fits in free interval and window
            if candidate_end <= free_end and candidate_start >= time_window_start and candidate_end <= time_window_end:
                candidates.append({
                    "start": to_iso_with_tz(candidate_start, tz_str),
                    "end": to_iso_with_tz(candidate_end, tz_str)
                })
            
            candidate_start += grid_delta
    
    return candidates


def round_to_grid(dt: datetime, grid_minutes: int) -> datetime:
    """Round datetime down to nearest grid point."""
    # Round down minutes and zero out seconds/microseconds
    rounded_minutes = (dt.minute // grid_minutes) * grid_minutes
    return dt.replace(minute=rounded_minutes, second=0, microsecond=0)


def sort_candidates(candidates: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """
    Sort candidates deterministically:
    1. start ascending
    2. end ascending
    3. lexicographic start string as fallback
    """
    def sort_key(candidate: Dict[str, str]) -> Tuple[datetime, datetime, str]:
        start_dt = parse_datetime(candidate["start"])
        end_dt = parse_datetime(candidate["end"])
        # (start_dt, end_dt) already fully determines ordering under normal enumeration (unique candidates).
        # The extra fallback key is mostly redundant in normal operation. Python sort is stable, so even if
        # exact duplicates exist, order is deterministic given deterministic candidate generation.
        # We intentionally keep it as-is for now (no need to add enumeration index tie-break unless duplicates become an issue).
        return (start_dt, end_dt, candidate["start"])
    
    return sorted(candidates, key=sort_key)


def select_top_n(candidates: List[Dict[str, str]], n: int) -> List[Dict[str, str]]:
    """Select top N candidates after sorting."""
    sorted_candidates = sort_candidates(candidates)
    return sorted_candidates[:n]
