"""Data generation for MPCBench v2.

Generates per-task source data (calendar, slack, contacts, etc.)
based on task requirements using constraint templates.
"""

import json
import re
import random
from typing import Dict, Any, List, Tuple, Optional
from pathlib import Path
from datetime import datetime

from config import get_generator_config
from task_defs import Task, get_planning_meeting_slots


def assign_distractors_to_sources(
    distractors: List[Dict[str, str]],
    indirection_depth: int,
    min_required_source: int
) -> Dict[str, Optional[Dict[str, str]]]:
    """
    [핵심 함수] Distractor를 각 소스에 할당하는 함수
    
    목적: 각 소스(slack, jira, drive, gmail)에 distractor 1개씩 할당
    - distractor: 정답이 아닌 시간 슬롯 (제거해야 하는 슬롯)
    - 각 소스는 할당받은 distractor를 제거하는 역할을 함
    
    예시:
        distractors = [
            {'date': '2025-12-02', 'slot': '13:00-13:45'},  # distractor 1
            {'date': '2025-12-02', 'slot': '15:00-15:45'}   # distractor 2
        ]
        min_required_source = 3 (calendar + 2개 추가 소스)
        → {'slack': distractor1, 'jira': distractor2}
    
    Args:
        distractors: Calendar에서 생성된 distractor 슬롯 리스트
        indirection_depth: 소스 간 연계 깊이 (1=calendar만, 2=2개 소스 조합, 3+=3개+ 소스 조합)
        min_required_source: 필요한 최소 소스 개수 (calendar 포함)
        
    Returns:
        소스 이름 -> distractor 슬롯 매핑
        예: {'slack': {'date': '2025-12-02', 'slot': '13:00-13:45'}, 'jira': {...}}
    """
    assigned = {}
    
    # Step 1: indirection_depth에 따라 사용 가능한 소스 풀 결정
    # - depth=1: calendar만 사용 (추가 소스 없음)
    # - depth=2: slack, jira, drive, gmail 중 2개 조합 필요
    # - depth>=3: slack, jira, drive, gmail 중 3개+ 조합 필요
    if indirection_depth == 1:
        # calendar만 사용, 추가 소스 없음
        return assigned
    elif indirection_depth == 2:
        # indirection_depth=2: 2개 소스를 조합해야 함
        # 가능한 소스: slack, jira, drive, gmail (모두 사용 가능)
        available_sources = ['slack', 'jira', 'drive', 'gmail']
    else:  # indirection_depth >= 3
        # indirection_depth>=3: 3개 이상 소스를 조합해야 함
        available_sources = ['slack', 'jira', 'drive', 'gmail']
    
    # Step 2: min_required_source에서 calendar를 제외한 추가 소스 개수 계산
    # 예: min_required_source=3 → calendar + 2개 추가 소스 필요
    additional_sources_needed = min_required_source - 1
    
    # Step 3: 검증 - distractor 개수가 충분한지 확인
    if len(distractors) < additional_sources_needed:
        raise ValueError(f"Not enough distractors ({len(distractors)}) for min_required_source ({min_required_source}, needs {additional_sources_needed} additional sources)")
    
    # Step 4: 검증 - 사용 가능한 소스가 충분한지 확인
    if len(available_sources) < additional_sources_needed:
        raise ValueError(f"Not enough available sources ({len(available_sources)}) for min_required_source ({min_required_source}, needs {additional_sources_needed} additional sources)")
    
    # Step 5: 랜덤하게 소스 선택
    # 예: additional_sources_needed=2, available_sources=['slack','jira','drive','gmail']
    # → 가능한 조합: (slack,jira), (slack,drive), (slack,gmail), (jira,drive), (jira,gmail), (drive,gmail)
    # → 이 중 하나를 랜덤 선택
    selected_sources = random.sample(available_sources, additional_sources_needed)
    
    # Step 6: 선택된 각 소스에 distractor 1개씩 할당
    # 예: selected_sources=['slack','jira'], distractors=[distractor1, distractor2]
    # → assigned = {'slack': distractor1, 'jira': distractor2}
    for i, source in enumerate(selected_sources):
        if i < len(distractors):
            assigned[source] = distractors[i]
        else:
            # distractor가 부족한 경우 (이론적으로는 발생하지 않아야 함)
            assigned[source] = None
    
    return assigned


def extract_participant_names(task_description: str) -> List[str]:
    """
    Extract participant names from task description using simple heuristics.
    
    Args:
        task_description: The task description text
        
    Returns:
        List of extracted names (may be empty)
    """
    names = []
    
    # Pattern 1: "for Alice, Bob, and Carol" or "with Alice and Bob"
    patterns = [
        r'\b(for|with)\s+([A-Z][a-z]+(?:\s*,\s*[A-Z][a-z]+)*(?:\s+and\s+[A-Z][a-z]+)?)',
        r'\b([A-Z][a-z]+)\s+and\s+([A-Z][a-z]+)(?:\s+and\s+([A-Z][a-z]+))?',
    ]
    
    for pattern in patterns:
        matches = re.finditer(pattern, task_description, re.IGNORECASE)
        for match in matches:
            text = match.group(0)
            parts = re.split(r'[,,\s]+and\s+|,\s*|\s+', text)
            for part in parts:
                part = part.strip()
                if part and part[0].isupper() and part.isalpha() and len(part) > 2:
                    if part.lower() not in ['for', 'with', 'the', 'and', 'or', 'next', 'week']:
                        if part not in names:
                            names.append(part)
    
    # Pattern 2: Look for capitalized words that aren't at sentence start
    words = task_description.split()
    for i, word in enumerate(words):
        if i > 0 and word[0].isupper() and word.isalpha() and len(word) > 2:
            prev_word = words[i-1].lower() if i > 0 else ""
            if prev_word in ['for', 'with', 'and', 'or'] or prev_word.endswith(','):
                if word not in names:
                    names.append(word)
    
    return names


def generate_participants(task: Task, generator_config: Dict[str, Any]) -> List[Dict[str, str]]:
    """
    Generate participant list for a planning task.
    
    Raises ValueError if required config entries are missing.
    """
    names = extract_participant_names(task.task_description)
    
    if not names:
        fallback_names = generator_config.get("fallback_names", [])
        if not fallback_names:
            raise ValueError("Missing generator_config entry: fallback_names (required when no names extracted from task_description)")
        if len(fallback_names) < 3:
            raise ValueError(f"generator_config.fallback_names must have at least 3 names, got {len(fallback_names)}")
        names = fallback_names[:3]
    
    email_domain = generator_config.get("email_domain", "")
    if not email_domain:
        raise ValueError("Missing generator_config entry: email_domain")
    
    participants = []
    for name in names:
        email = f"{name.lower()}@{email_domain}"
        participants.append({
            "name": name,
            "email": email
        })
    
    return participants


def get_weekday_name(date_str: str) -> str:
    """Get weekday name from YYYY-MM-DD date string."""
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return dt.strftime("%A")
    except:
        return ""


def generate_calendar_events(
    canonical_slot: Dict[str, str],
    participants: List[Dict[str, str]],
    indirection_depth: int,
    fragmentation_depth: int = 1,
    candidate_slots_needed: Optional[int] = None,
    generator_config: Optional[Dict[str, Any]] = None,
    min_required_source: Optional[int] = None
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, str]]]:
    """
    Generate calendar events using constraint templates.
    
    Args:
        fragmentation_depth: Determines number of distractor slots (higher = more distractors)
        candidate_slots_needed: Override for number of candidate slots (if None, computed from fragmentation_depth)
        generator_config: Optional generator config for calendar names
    
    Returns:
        Tuple of (calendars list, events list, candidate_slots list)
    """
    from datetime import datetime, timedelta
    
    # Generate calendars (one per participant)
    calendars = []
    calendar_id_map = {}  # email -> calendar_id mapping
    for idx, participant in enumerate(participants):
        calendar_id = f"cal_{idx:03d}"
        calendar_id_map[participant["email"]] = calendar_id
        calendar_name = f"Primary Calendar"
        if generator_config:
            calendar_config = generator_config.get("calendar", {})
            calendar_names = calendar_config.get("calendar_names", [])
            if calendar_names:
                calendar_name = calendar_names[0]
        
        calendars.append({
            "calendar_id": calendar_id,
            "email": participant["email"],
            "name": calendar_name
        })
    
    events = []
    canonical_date = canonical_slot["date"]
    canonical_time = canonical_slot["slot"]
    candidate_slots = [canonical_slot]
    
    # Determine number of candidate slots needed based on fragmentation_depth and min_required_source
    if candidate_slots_needed is None:
        # Ensure we have enough distractors for min_required_source
        # fragmentation_depth가 높을수록 더 많은 distractor slots 생성
        base_needed = max(3, fragmentation_depth + 2)
        if min_required_source is not None:
            # Need at least min_required_source distractors (plus canonical slots)
            candidate_slots_needed = max(base_needed, min_required_source + 1)
        else:
            candidate_slots_needed = base_needed
    
    if indirection_depth == 1:
        # T_CAL_UNIQUE: canonical slot is the only tri-free slot
        for participant in participants:
            calendar_id = calendar_id_map.get(participant["email"], f"cal_000")
            events.append({
                "calendar_id": calendar_id,
                "email": participant["email"],
                "date": canonical_date,
                "slot": canonical_time,
                "busy": False
            })
        
        # Mark other slots as busy (at least one participant busy)
        if "-" in canonical_time:
            start_hour = int(canonical_time.split("-")[0].split(":")[0])
            for hour_offset in [-2, -1, 1, 2]:
                hour = start_hour + hour_offset
                if 9 <= hour <= 17:
                    distractor_slot = f"{hour:02d}:00-{hour:02d}:45"
                    for i, participant in enumerate(participants):
                        calendar_id = calendar_id_map.get(participant["email"], f"cal_{i:03d}")
                        events.append({
                            "calendar_id": calendar_id,
                            "email": participant["email"],
                            "date": canonical_date,
                            "slot": distractor_slot,
                            "busy": (i == 0)  # First participant busy
                        })
    else:
        # T_CAL_MULTI_CANDIDATES: multiple free slots including canonical
        for participant in participants:
            calendar_id = calendar_id_map.get(participant["email"], f"cal_000")
            events.append({
                "calendar_id": calendar_id,
                "email": participant["email"],
                "date": canonical_date,
                "slot": canonical_time,
                "busy": False
            })
        
        # Generate distractor slots - same day and other days
        canonical_dt = datetime.strptime(canonical_date, "%Y-%m-%d")
        
        # Same day distractors
        if "-" in canonical_time:
            start_hour = int(canonical_time.split("-")[0].split(":")[0])
            distractor_hours = []
            for hour_offset in [-1, 1, 2, 3, -2]:
                hour = start_hour + hour_offset
                if 9 <= hour <= 17:
                    distractor_hours.append(hour)
            
            same_day_needed = min(candidate_slots_needed - 1, len(distractor_hours))
            for hour in distractor_hours[:same_day_needed]:
                distractor_slot = f"{hour:02d}:00-{hour:02d}:45"
                candidate_slots.append({"date": canonical_date, "slot": distractor_slot})
                for participant in participants:
                    calendar_id = calendar_id_map.get(participant["email"], f"cal_000")
                    events.append({
                        "calendar_id": calendar_id,
                        "email": participant["email"],
                        "date": canonical_date,
                        "slot": distractor_slot,
                        "busy": False
                    })
        
        # Other days distractors (if more candidates needed)
        if len(candidate_slots) < candidate_slots_needed:
            days_to_add = candidate_slots_needed - len(candidate_slots)
            for day_offset in [1, -1, 2, -2, 3, -3]:
                if days_to_add <= 0:
                    break
                other_date_dt = canonical_dt + timedelta(days=day_offset)
                other_date = other_date_dt.strftime("%Y-%m-%d")
                
                # Generate 1-2 slots on this other day
                slots_on_day = min(2, days_to_add)
                for slot_idx in range(slots_on_day):
                    # Use similar time slots (morning, afternoon)
                    if slot_idx == 0:
                        hour = 10  # Morning
                    else:
                        hour = 15  # Afternoon
                    distractor_slot = f"{hour:02d}:00-{hour:02d}:45"
                    candidate_slots.append({"date": other_date, "slot": distractor_slot})
                    for participant in participants:
                        calendar_id = calendar_id_map.get(participant["email"], f"cal_000")
                        events.append({
                            "calendar_id": calendar_id,
                            "email": participant["email"],
                            "date": other_date,
                            "slot": distractor_slot,
                            "busy": False
                        })
                    days_to_add -= 1
    
    return calendars, events, candidate_slots


def generate_slack_messages(
    canonical_slot: Dict[str, str],
    candidate_slots: List[Dict[str, str]],
    participants: List[Dict[str, str]],
    indirection_depth: int,
    min_required_source: int,
    fragmentation_depth: int,
    generator_config: Dict[str, Any],
    pattern_type: Optional[str] = None,
    all_canonical_slots: Optional[List[Dict[str, str]]] = None,
    assigned_distractor: Optional[Dict[str, str]] = None,
    linked_source: Optional[str] = None,
    linked_source_id: Optional[str] = None
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    [핵심 함수] Slack 메시지 생성 함수
    
    목적: assigned_distractor를 제거하는 제약을 Slack 메시지로 생성
    - fragmentation_depth: 메시지를 몇 개로 분산할지 (각 메시지는 불완전)
    - indirection_depth: 다른 소스와 연계할지 (linked_source 참조 추가)
    
    생성 패턴:
        fragmentation_depth=2, indirection_depth=2 예시:
        - 메시지1: "Amy가 bob이 언제 안되는지 알던데?" (힌트, 불완전)
        - 메시지2: "나한테 14시 이후만 된다고 했어. jira의 API-121 이슈에 불가능한 시간이 써있어."
                   (제약 정보 + Jira 참조, 불완전)
        → 두 메시지를 조합해야 의미 완성, Jira도 봐야 함
    
    Args:
        assigned_distractor: 이 소스가 제거해야 할 distractor 슬롯
        fragmentation_depth: 메시지 개수 (각 메시지는 불완전하게 생성)
        indirection_depth: 소스 간 연계 깊이
        linked_source: 연계할 다른 소스 이름 (예: "jira")
        linked_source_id: 연계할 소스의 ID (예: "API-121")
    
    Returns:
        (channels 리스트, messages 리스트)
    """
    messages = []
    slack_config = generator_config.get("slack", {})
    
    default_channel = slack_config.get("default_channel", "")
    if not default_channel:
        raise ValueError("Missing generator_config entry: slack.default_channel")
    
    # Generate channels
    channels = []
    channel_names = slack_config.get("channel_names", [default_channel])
    channel_descriptions = slack_config.get("channel_descriptions", [])
    
    channel_id_map = {}  # channel_name -> channel_id mapping
    for idx, channel_name in enumerate(channel_names):
        channel_id = f"channel_{idx:03d}"
        channel_id_map[channel_name] = channel_id
        description = channel_descriptions[idx] if idx < len(channel_descriptions) else f"{channel_name} channel"
        channels.append({
            "channel_id": channel_id,
            "name": channel_name,
            "description": description
        })
    
    # Get default channel_id
    default_channel_id = channel_id_map.get(default_channel, "channel_000")
    
    base_user_names = slack_config.get("base_user_names", [])
    
    if indirection_depth == 1:
        return channels, messages
    
    # Early return: assigned_distractor가 없으면 메시지 생성 안 함
    if assigned_distractor is None:
        return channels, messages
    
    # Helper: 메시지 작성자 이름 가져오기
    def get_user_name(index: int) -> str:
        if participants and index < len(participants):
            return participants[index]["name"].lower()
        elif base_user_names and index < len(base_user_names):
            return base_user_names[index]
        else:
            raise ValueError("Missing generator_config entry: slack.base_user_names (required when no participants available)")
    
    # 제3자 이름 찾기 (참가자가 아닌 사람, 힌트에 사용)
    # 예: "Amy가 bob이 언제 안되는지 알던데?"에서 Amy는 제3자
    generator_config_global = generator_config
    fallback_names = generator_config_global.get("fallback_names", ["Alice", "Bob", "Carol", "Dave", "Eve"])
    participant_names = {p["name"].lower() for p in participants}
    third_party_name = None
    for name in fallback_names:
        if name.lower() not in participant_names:
            third_party_name = name
            break
    if third_party_name is None:
        third_party_name = "Amy"  # Default fallback
    
    # 타임스탬프 패턴 가져오기
    gmail_config = generator_config.get("gmail", {})
    timestamp_patterns = gmail_config.get("timestamp_patterns", [])
    if not timestamp_patterns:
        raise ValueError("Missing generator_config entry: gmail.timestamp_patterns")
    
    # Step 1: 시간 제약 threshold 계산
    # 목적: assigned_distractor는 제외하되, 모든 canonical slot은 허용하는 시간 필터 생성
    # 예: distractor=13:00, canonical=14:00 → threshold=14:00 ("14시 이후만 가능")
    distractor_hour = int(assigned_distractor["slot"].split("-")[0].split(":")[0])
    canonical_slots_to_check = all_canonical_slots if all_canonical_slots else [canonical_slot]
    min_canonical_hour = 14
    for slot in canonical_slots_to_check:
        if "-" in slot["slot"]:
            hour = int(slot["slot"].split("-")[0].split(":")[0])
            min_canonical_hour = min(min_canonical_hour, hour)
    
    # threshold 계산: distractor 제외, canonical 허용
    if distractor_hour < min_canonical_hour:
        # distractor가 canonical보다 이전 → distractor 다음 시간 사용
        threshold_hour = distractor_hour + 1
    else:
        # distractor가 canonical보다 이후 → canonical 최소 시간 사용
        threshold_hour = min_canonical_hour
    
    # 참가자 이름 (제약의 주체)
    participant_name = participants[0]["name"] if participants else "Bob"
    
    # Step 2: fragmentation_depth에 따라 메시지 개수 결정
    num_messages = fragmentation_depth
    
    # ============================================================
    # Step 3: fragmentation_depth 적용 - 불완전한 메시지들 생성
    # ============================================================
    # 각 메시지는 단독으로는 의미가 불완전하며, 조합해야만 distractor를 제거할 수 있음
    for msg_idx in range(num_messages):
        timestamp = timestamp_patterns[msg_idx % len(timestamp_patterns)]
        
        if msg_idx == 0:
            # 메시지1: 힌트/질문 (제3자 언급)
            # 예: "Amy가 bob이 언제 안되는지 알던데?"
            # → 이 메시지만으로는 어떤 제약인지 알 수 없음 (불완전)
            message_text = f"{third_party_name}가 {participant_name.lower()}이 언제 안되는지 알던데?"
        elif msg_idx == 1:
            # 메시지2: 실제 제약 정보 (하지만 메시지1 없이는 모호)
            # 예: "나한테 14시 이후만 된다고 했어."
            # → "나"가 누구인지, "14시 이후"가 누구의 제약인지 불명확 (불완전)
            time_str = f"{threshold_hour:02d}:00"
            message_text = f"나한테 {time_str} 이후만 된다고 했어."
        else:
            # 추가 메시지: 더 많은 힌트나 컨텍스트
            message_text = f"{third_party_name}가 {participant_name.lower()}에게 물어봤는데, {threshold_hour:02d}:00 이후만 가능하다고 했어."
        
        # ============================================================
        # Step 4: indirection_depth 적용 - 다른 소스 참조 추가
        # ============================================================
        # 다른 소스와 연계하여, 각 소스가 단독으로는 불완전하도록 함
        if indirection_depth >= 2 and linked_source and linked_source_id:
            if linked_source == "jira":
                # Jira 이슈 참조 추가
                # 예: "jira의 API-121 이슈에 불가능한 시간이 써있어."
                # → 이제 Slack만으로는 불완전, Jira도 봐야 함
                if msg_idx == num_messages - 1:  # 마지막 메시지에만 참조 추가
                    message_text += f" jira의 {linked_source_id} 이슈에 불가능한 시간이 써있어."
            elif linked_source == "drive":
                # Drive 문서 참조 추가
                if msg_idx == num_messages - 1:
                    drive_config = generator_config.get("drive", {})
                    doc_titles = drive_config.get("doc_title_templates", [])
                    if doc_titles:
                        doc_title = doc_titles[0]
                        message_text += f" '{doc_title}' 문서에 불가능한 시간이 써있어."
        
        # 메시지 추가
        messages.append({
            "channel_id": default_channel_id,
            "channel": default_channel,
            "user": get_user_name(msg_idx % len(participants) if participants else msg_idx),
            "text": message_text,
            "timestamp": timestamp
        })
    
    return channels, messages


def generate_jira_issues(
    canonical_slot: Dict[str, str],
    candidate_slots: List[Dict[str, str]],
    indirection_depth: int,
    fragmentation_depth: int,
    generator_config: Dict[str, Any],
    assigned_distractor: Optional[Dict[str, str]] = None,
    linked_source: Optional[str] = None,
    linked_source_id: Optional[str] = None
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Generate Jira issues using constraint templates (T_JIRA_CONFLICT_SLOT).
    
    Only applies to distractor slots, never canonical_slot.
    fragmentation_depth determines how many distractors to exclude in this source.
    
    Returns:
        Tuple of (projects list, issues list)
    """
    issues = []
    
    # Generate projects
    projects = []
    jira_config = generator_config.get("jira", {})
    project_keys = jira_config.get("project_keys", [])
    if not project_keys:
        raise ValueError("Missing generator_config entry: jira.project_keys")
    
    project_names = jira_config.get("project_names", [])
    project_descriptions = jira_config.get("project_descriptions", [])
    
    for idx, project_key in enumerate(project_keys):
        project_name = project_names[idx] if idx < len(project_names) else f"{project_key} Project"
        project_description = project_descriptions[idx] if idx < len(project_descriptions) else f"{project_key} project"
        projects.append({
            "project_key": project_key,
            "name": project_name,
            "description": project_description
        })
    
    # If no assigned_distractor, return empty issues
    if assigned_distractor is None:
        return projects, issues
    
    if indirection_depth >= 2:
        conflict_templates = jira_config.get("conflict_templates", [])
        if not conflict_templates:
            raise ValueError("Missing generator_config entry: jira.conflict_templates")
        
        # Get third-party name for hints
        fallback_names = generator_config.get("fallback_names", ["Alice", "Bob", "Carol", "Dave", "Eve"])
        third_party_name = fallback_names[0] if fallback_names else "Amy"
        
        # Generate issues based on fragmentation_depth
        num_issues = fragmentation_depth
        
        for issue_idx in range(num_issues):
            if issue_idx == 0:
                # First issue: hint with third-party mention
                # Example: 'Amy의 스케줄 확인 필요'
                summary = f"{third_party_name}의 스케줄 확인 필요"
                description = summary
            elif issue_idx == 1:
                # Second issue: actual conflict time (but incomplete without first issue)
                # Example: 'Team Sync scheduled for 2025-12-02 15:00-15:45'
                template = conflict_templates[issue_idx % len(conflict_templates)]
                summary = template.format(
                    date=assigned_distractor["date"],
                    slot=assigned_distractor["slot"]
                )
                description = summary
            else:
                # Additional issues: more hints or context
                template = conflict_templates[issue_idx % len(conflict_templates)]
                summary = template.format(
                    date=assigned_distractor["date"],
                    slot=assigned_distractor["slot"]
                )
                description = f"{third_party_name}의 스케줄과 관련된 {summary}"
            
            # Step 2: Apply indirection_depth - add reference to other source if needed
            if indirection_depth >= 2 and linked_source and linked_source_id:
                if linked_source == "slack":
                    # Reference to Slack message
                    if issue_idx == num_issues - 1:  # Last issue gets the reference
                        description += f" Slack 메시지에서 언급된 시간입니다."
            
            issues.append({
                "issue_key": f"{project_keys[0]}-{120 + issue_idx}",
                "project_key": project_keys[0],
                "summary": summary,
                "description": description,
                "status": "To Do"
            })
    
    return projects, issues


def generate_drive_files(
    canonical_slot: Dict[str, str],
    candidate_slots: List[Dict[str, str]],
    indirection_depth: int,
    fragmentation_depth: int,
    generator_config: Dict[str, Any],
    all_canonical_slots: List[Dict[str, str]],
    excluded_slots: set = None,
    assigned_distractor: Optional[Dict[str, str]] = None,
    linked_source: Optional[str] = None,
    linked_source_id: Optional[str] = None
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Generate Drive files using constraint templates (T_DRIVE_DOC_TIME_NEGATIVE only).
    
    Only applies to distractor slots, never canonical_slot.
    fragmentation_depth determines how many distractors to exclude in this source.
    all_canonical_slots: all canonical slots from the task (to avoid excluding them).
    excluded_slots: set of (date, slot) tuples already excluded by previous sources.
    
    Returns:
        Tuple of (folders list, files list)
    """
    if excluded_slots is None:
        excluded_slots = set()
    
    files = []
    
    # Generate folders
    folders = []
    drive_config = generator_config.get("drive", {})
    folder_names = drive_config.get("folder_names", ["Documents"])
    folder_descriptions = drive_config.get("folder_descriptions", [])
    
    folder_id_map = {}  # folder_name -> folder_id mapping
    for idx, folder_name in enumerate(folder_names):
        folder_id = f"folder_{idx:03d}"
        folder_id_map[folder_name] = folder_id
        description = folder_descriptions[idx] if idx < len(folder_descriptions) else f"{folder_name} folder"
        folders.append({
            "folder_id": folder_id,
            "name": folder_name,
            "parent_folder_id": None
        })
    
    # Default folder_id (use first folder)
    default_folder_id = folder_id_map.get(folder_names[0], "folder_000") if folder_names else "folder_000"
    
    # If no assigned_distractor, return empty files
    if assigned_distractor is None:
        return folders, files
    
    if indirection_depth >= 3:
        doc_titles = drive_config.get("doc_title_templates", [])
        if not doc_titles:
            raise ValueError("Missing generator_config entry: drive.doc_title_templates")
        
        templates = drive_config.get("doc_time_negative_templates", [])
        if not templates:
            raise ValueError("Missing generator_config entry: drive.doc_time_negative_templates")
        
        # Get third-party name for hints
        fallback_names = generator_config.get("fallback_names", ["Alice", "Bob", "Carol", "Dave", "Eve"])
        third_party_name = fallback_names[0] if fallback_names else "Amy"
        
        # Generate files based on fragmentation_depth
        num_files = fragmentation_depth
        
        for file_idx in range(num_files):
            doc_title = doc_titles[file_idx % len(doc_titles)]
            
            if file_idx == 0:
                # First file: hint with third-party mention
                # Example: '이전 계획에 대한 논의가 있었던 것 같은데'
                text = f"이전 계획에 대한 논의가 있었던 것 같은데, {third_party_name}가 언급했어."
            elif file_idx == 1:
                # Second file: actual exclusion time (but incomplete without first file)
                # Example: 'The previous plan was to meet on 2025-12-02 16:00-16:45, but that time no longer works.'
                template = templates[file_idx % len(templates)]
                text = template.format(
                    date=assigned_distractor["date"],
                    slot=assigned_distractor["slot"]
                )
            else:
                # Additional files: more hints or context
                template = templates[file_idx % len(templates)]
                text = template.format(
                    date=assigned_distractor["date"],
                    slot=assigned_distractor["slot"]
                )
                text = f"{third_party_name}가 언급한 내용: {text}"
            
            # Step 2: Apply indirection_depth - add reference to other source if needed
            if indirection_depth >= 3 and linked_source and linked_source_id:
                if linked_source == "slack":
                    # Reference to Slack message
                    if file_idx == num_files - 1:  # Last file gets the reference
                        text += f" Slack에서 언급된 시간입니다."
            
            files.append({
                "file_id": f"file_{file_idx:03d}",
                "folder_id": default_folder_id,
                "name": doc_title,
                "text": text
            })
    
    return folders, files


def generate_gmail_threads(
    canonical_slot: Dict[str, str],
    candidate_slots: List[Dict[str, str]],
    participants: List[Dict[str, str]],
    indirection_depth: int,
    fragmentation_depth: int,
    generator_config: Dict[str, Any],
    all_canonical_slots: List[Dict[str, str]],
    excluded_slots: set = None,
    assigned_distractor: Optional[Dict[str, str]] = None,
    linked_source: Optional[str] = None,
    linked_source_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Generate Gmail threads using constraint templates (T_GMAIL_CANCEL_SLOT only).
    
    Only applies to distractor slots, never canonical_slot.
    fragmentation_depth determines how many distractors to exclude in this source.
    all_canonical_slots: all canonical slots from the task (to avoid excluding them).
    excluded_slots: set of (date, slot) tuples already excluded by previous sources.
    """
    if excluded_slots is None:
        excluded_slots = set()
    threads = []
    
    if indirection_depth >= 3:
        gmail_config = generator_config.get("gmail", {})
        subject_templates = gmail_config.get("subject_templates", [])
        if not subject_templates:
            raise ValueError("Missing generator_config entry: gmail.subject_templates")
        
        from_candidates = gmail_config.get("from_candidates", [])
        to_candidates = gmail_config.get("to_candidates", [])
        timestamp_patterns = gmail_config.get("timestamp_patterns", [])
        if not timestamp_patterns:
            raise ValueError("Missing generator_config entry: gmail.timestamp_patterns")
        
        cancellation_templates = gmail_config.get("cancellation_templates", [])
        if not cancellation_templates:
            raise ValueError("Missing generator_config entry: gmail.cancellation_templates")
        
        if candidate_slots and len(candidate_slots) > 1:
            # Get all canonical slot keys
            canonical_keys = {(slot["date"], slot["slot"]) for slot in all_canonical_slots}
            
            # Exclude distractors based on fragmentation_depth
            # Only exclude non-canonical slots that haven't been excluded yet
            distractor_candidates = [
                (i, candidate_slots[i]) for i in range(len(candidate_slots))
                if (candidate_slots[i]["date"], candidate_slots[i]["slot"]) not in canonical_keys
                and (candidate_slots[i]["date"], candidate_slots[i]["slot"]) not in excluded_slots
            ]
            
            num_exclusions = min(len(distractor_candidates), max(1, fragmentation_depth))
            
            # Get from/to addresses (once, outside loop)
            if participants and len(participants) > 0:
                from_addr = participants[0]["email"]
                to_addrs = [p["email"] for p in participants[1:2]] if len(participants) > 1 else []
            elif from_candidates:
                from_addr = from_candidates[0]
                to_addrs = to_candidates[:2] if to_candidates else []
            else:
                raise ValueError("Missing generator_config entry: gmail.from_candidates (required when no participants available)")
            
            if not to_addrs:
                if to_candidates:
                    to_addrs = to_candidates[:2]
                else:
                    raise ValueError("Missing generator_config entry: gmail.to_candidates (required when no participants available)")
            
            # Get third-party name for hints
            fallback_names = generator_config.get("fallback_names", ["Alice", "Bob", "Carol", "Dave", "Eve"])
            third_party_name = fallback_names[0] if fallback_names else "Amy"
            
            # Generate threads/messages based on fragmentation_depth
            num_messages = fragmentation_depth
            
            # Create one thread with multiple messages
            subject = subject_templates[0]
            thread_messages = []
            
            for msg_idx in range(num_messages):
                timestamp = timestamp_patterns[msg_idx % len(timestamp_patterns)]
                
                if msg_idx == 0:
                    # First message: hint with third-party mention
                    # Example: 'Amy가 언급한 시간에 문제가 있을 수 있어'
                    text = f"{third_party_name}가 언급한 시간에 문제가 있을 수 있어."
                elif msg_idx == 1:
                    # Second message: actual cancellation (but incomplete without first message)
                    # Example: 'We can't do 2025-12-02 16:00-16:45 anymore.'
                    template = cancellation_templates[msg_idx % len(cancellation_templates)]
                    text = template.format(
                        date=assigned_distractor["date"],
                        slot=assigned_distractor["slot"]
                    )
                else:
                    # Additional messages: more hints or context
                    template = cancellation_templates[msg_idx % len(cancellation_templates)]
                    text = template.format(
                        date=assigned_distractor["date"],
                        slot=assigned_distractor["slot"]
                    )
                    text = f"{third_party_name}가 언급한 내용: {text}"
                
                # Step 2: Apply indirection_depth - add reference to other source if needed
                if indirection_depth >= 3 and linked_source and linked_source_id:
                    if linked_source == "slack":
                        # Reference to Slack message
                        if msg_idx == num_messages - 1:  # Last message gets the reference
                            text += f" Slack 메시지에서 언급된 시간입니다."
                
                thread_messages.append({
                    "from": from_addr,
                    "to": to_addrs,
                    "subject": subject,
                    "text": text,
                    "timestamp": timestamp
                })
            
            threads.append({
                "thread_id": f"thread_001",
                "subject": subject,
                "messages": thread_messages
            })
    
    return threads


def generate_source_data(task: Task, output_dir: Path) -> Dict[str, Path]:
    """
    Generate source data files for a task.
    
    Args:
        task: The task definition
        output_dir: Directory to write generated data files
        
    Returns:
        Dictionary mapping source names to file paths
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    
    if task.is_planning():
        return generate_planning_source_data(task, output_dir)
    elif task.is_document() or task.is_email_reply():
        # TODO: Implement richer generation for document and email_reply tasks
        return {}
    else:
        return {}


def generate_planning_source_data(task: Task, output_dir: Path) -> Dict[str, Path]:
    """
    [메인 함수] Planning task의 모든 소스 데이터를 생성하는 orchestration 함수
    
    전체 흐름:
    1. 참가자 추출/생성
    2. Canonical slots 추출 (정답 슬롯)
    3. Calendar 생성 (canonical + distractor slots)
    4. Distractor 할당 (각 소스에 1개씩)
    5. 각 소스별 데이터 생성 (slack, jira, drive, gmail)
    6. Contacts 생성
    
    핵심 로직:
    - fragmentation_depth: 각 소스 내에서 데이터를 몇 개로 분산할지
    - indirection_depth: 몇 개의 소스를 조합해야 하는지
    - min_required_source: 필요한 최소 소스 개수
    
    Returns:
        소스 이름 -> 파일 경로 매핑
        예: {'calendar': Path(...), 'slack': Path(...), ...}
    """
    source_data = {}
    generator_config = get_generator_config()
    
    # ============================================================
    # Step 1: 참가자 생성
    # ============================================================
    # Task description에서 이름 추출하거나, fallback_names 사용
    participants = generate_participants(task, generator_config)
    
    # ============================================================
    # Step 2: Canonical slots 추출 (정답 슬롯)
    # ============================================================
    # Task의 canonical_answer에서 meeting_slots 추출
    slots = get_planning_meeting_slots(task)
    if not slots:
        return source_data
    
    # 첫 번째 canonical slot을 기준으로 calendar 생성
    # 나머지 canonical slots는 나중에 calendar에 추가됨
    canonical_slot = slots[0]
    
    # Task metadata에서 복잡도 파라미터 추출
    indirection_depth = task.metadata["indirection_depth"]  # 소스 간 연계 깊이
    min_required_source = task.metadata["min_required_source"]  # 필요한 최소 소스 개수
    fragmentation_depth = task.metadata["fragmentation_depth"]  # 한 소스 내 데이터 분산 개수
    
    # ============================================================
    # Step 3: Calendar 생성
    # ============================================================
    # - canonical_slot: 정답 슬롯 (모든 참가자가 비어있음)
    # - distractor slots: 정답이 아닌 슬롯들 (나중에 다른 소스가 제거)
    # - candidate_slots: canonical + distractor 모든 슬롯
    calendars, calendar_events, candidate_slots = generate_calendar_events(
        canonical_slot, participants, indirection_depth, fragmentation_depth, 
        generator_config=generator_config, min_required_source=min_required_source
    )
    
    # ============================================================
    # Step 4: Distractor 추출 및 할당
    # ============================================================
    # canonical slots를 제외한 나머지가 distractor
    canonical_keys = {(slot["date"], slot["slot"]) for slot in slots}
    distractors = [s for s in candidate_slots if (s["date"], s["slot"]) not in canonical_keys]
    
    # 각 소스에 distractor 1개씩 할당
    # 예: min_required_source=3, indirection_depth=2
    # → {'slack': distractor1, 'jira': distractor2}
    assigned_distractors = assign_distractors_to_sources(
        distractors, indirection_depth, min_required_source
    )
    
    # ============================================================
    # Step 5: 나머지 canonical slots를 calendar에 추가
    # ============================================================
    # 첫 번째 canonical slot 외의 다른 canonical slots도 calendar에 추가
    calendar_id_map = {cal["email"]: cal["calendar_id"] for cal in calendars}
    for slot in slots[1:]:
        slot_key = (slot["date"], slot["slot"])
        # 이미 candidate_slots에 없으면 추가
        if not any((s["date"], s["slot"]) == slot_key for s in candidate_slots):
            candidate_slots.append(slot)
            # 모든 참가자에게 이 슬롯을 free로 추가
            for participant in participants:
                calendar_id = calendar_id_map.get(participant["email"], "cal_000")
                calendar_events.append({
                    "calendar_id": calendar_id,
                    "email": participant["email"],
                    "date": slot["date"],
                    "slot": slot["slot"],
                    "busy": False
                })
    
    # Calendar JSON 파일 저장
    calendar_path = output_dir / "calendar.json"
    with open(calendar_path, 'w', encoding='utf-8') as f:
        json.dump({"calendars": calendars, "events": calendar_events}, f, indent=2)
    source_data["calendar"] = calendar_path
    
    # ============================================================
    # Step 6: 추가 소스 생성 (slack, jira, drive, gmail)
    # ============================================================
    # assigned_distractors에 할당된 소스들만 생성
    if indirection_depth == 1:
        # indirection_depth=1: calendar만 사용, 추가 소스 없음
        pass
    elif indirection_depth == 2:
        # ============================================================
        # indirection_depth=2: 2개 소스를 조합해야 함
        # ============================================================
        # 예: slack + jira, slack + drive, jira + drive 등
        # 각 소스는 다른 소스를 참조하여 단독으로는 불완전하도록 함
        
        # 소스 간 연계 정보 초기화
        linked_source = None
        linked_source_id = None
        
        # Slack 생성
        if "slack" in assigned_distractors and assigned_distractors["slack"]:
            # 다른 소스와 연계 설정
            # 예: jira도 할당되어 있으면 jira 참조 추가
            if "jira" in assigned_distractors and assigned_distractors["jira"]:
                linked_source = "jira"
                jira_config = generator_config.get("jira", {})
                project_keys = jira_config.get("project_keys", [])
                linked_source_id = f"{project_keys[0]}-121" if project_keys else "API-121"
            
            # Slack 메시지 생성
            # - assigned_distractor: 이 소스가 제거할 distractor
            # - linked_source: 연계할 다른 소스 (indirection_depth 적용)
            slack_channels, slack_messages = generate_slack_messages(
                canonical_slot, candidate_slots, participants,
                indirection_depth, min_required_source, fragmentation_depth,
                generator_config, pattern_type="time", all_canonical_slots=slots,
                assigned_distractor=assigned_distractors["slack"],
                linked_source=linked_source, linked_source_id=linked_source_id
            )
            if slack_messages:
                slack_path = output_dir / "slack.json"
                with open(slack_path, 'w', encoding='utf-8') as f:
                    json.dump({"channels": slack_channels, "messages": slack_messages}, f, indent=2)
                source_data["slack"] = slack_path
        
        # Jira 생성
        if "jira" in assigned_distractors and assigned_distractors["jira"]:
            # Slack과 연계 설정
            if "slack" in assigned_distractors and assigned_distractors["slack"]:
                linked_source = "slack"
                linked_source_id = "channel_000"  # Default channel
            
            # Jira 이슈 생성
            jira_projects, jira_issues = generate_jira_issues(
                canonical_slot, candidate_slots, indirection_depth,
                fragmentation_depth, generator_config,
                assigned_distractor=assigned_distractors["jira"],
                linked_source=linked_source, linked_source_id=linked_source_id
            )
            if jira_issues:
                jira_path = output_dir / "jira.json"
                with open(jira_path, 'w', encoding='utf-8') as f:
                    json.dump({"projects": jira_projects, "issues": jira_issues}, f, indent=2)
                source_data["jira"] = jira_path
        
        # Drive, Gmail도 동일한 패턴으로 생성 가능 (assigned_distractors에 있으면)
    
    elif indirection_depth >= 3:
        # indirection_depth>=3: slack, jira, drive, gmail can be used
        # Determine linked sources for indirection_depth
        linked_sources = {}  # source_name -> (linked_source, linked_source_id)
        
        # For indirection_depth=3, each source should link to another source
        # Simple strategy: slack -> jira, jira -> slack, drive -> slack, gmail -> slack
        jira_config = generator_config.get("jira", {})
        project_keys = jira_config.get("project_keys", [])
        
        if "slack" in assigned_distractors and assigned_distractors["slack"]:
            # Slack links to jira if jira is assigned, otherwise to drive
            if "jira" in assigned_distractors and assigned_distractors["jira"]:
                linked_sources["slack"] = ("jira", f"{project_keys[0]}-121" if project_keys else "API-121")
            elif "drive" in assigned_distractors and assigned_distractors["drive"]:
                drive_config = generator_config.get("drive", {})
                doc_titles = drive_config.get("doc_title_templates", [])
                linked_sources["slack"] = ("drive", doc_titles[0] if doc_titles else "API Design Doc")
        
        if "jira" in assigned_distractors and assigned_distractors["jira"]:
            # Jira links to slack if slack is assigned
            if "slack" in assigned_distractors and assigned_distractors["slack"]:
                linked_sources["jira"] = ("slack", "channel_000")
        
        if "drive" in assigned_distractors and assigned_distractors["drive"]:
            # Drive links to slack if slack is assigned
            if "slack" in assigned_distractors and assigned_distractors["slack"]:
                linked_sources["drive"] = ("slack", "channel_000")
        
        if "gmail" in assigned_distractors and assigned_distractors["gmail"]:
            # Gmail links to slack if slack is assigned
            if "slack" in assigned_distractors and assigned_distractors["slack"]:
                linked_sources["gmail"] = ("slack", "channel_000")
        
        # Generate sources based on assigned_distractors
        if "slack" in assigned_distractors and assigned_distractors["slack"]:
            linked = linked_sources.get("slack", (None, None))
            slack_channels, slack_messages = generate_slack_messages(
                canonical_slot, candidate_slots, participants,
                indirection_depth, min_required_source, fragmentation_depth,
                generator_config, pattern_type="time", all_canonical_slots=slots,
                assigned_distractor=assigned_distractors["slack"],
                linked_source=linked[0], linked_source_id=linked[1]
            )
            if slack_messages:
                slack_path = output_dir / "slack.json"
                with open(slack_path, 'w', encoding='utf-8') as f:
                    json.dump({"channels": slack_channels, "messages": slack_messages}, f, indent=2)
                source_data["slack"] = slack_path
        
        if "jira" in assigned_distractors and assigned_distractors["jira"]:
            linked = linked_sources.get("jira", (None, None))
            jira_projects, jira_issues = generate_jira_issues(
                canonical_slot, candidate_slots, indirection_depth,
                fragmentation_depth, generator_config,
                assigned_distractor=assigned_distractors["jira"],
                linked_source=linked[0], linked_source_id=linked[1]
            )
            if jira_issues:
                jira_path = output_dir / "jira.json"
                with open(jira_path, 'w', encoding='utf-8') as f:
                    json.dump({"projects": jira_projects, "issues": jira_issues}, f, indent=2)
                source_data["jira"] = jira_path
        
        if "drive" in assigned_distractors and assigned_distractors["drive"]:
            linked = linked_sources.get("drive", (None, None))
            drive_folders, drive_files = generate_drive_files(
                canonical_slot, candidate_slots, indirection_depth, fragmentation_depth, 
                generator_config, all_canonical_slots=slots, excluded_slots=set(),
                assigned_distractor=assigned_distractors["drive"],
                linked_source=linked[0], linked_source_id=linked[1]
            )
            if drive_files:
                drive_path = output_dir / "drive.json"
                with open(drive_path, 'w', encoding='utf-8') as f:
                    json.dump({"folders": drive_folders, "files": drive_files}, f, indent=2)
                source_data["drive"] = drive_path
        
        if "gmail" in assigned_distractors and assigned_distractors["gmail"]:
            linked = linked_sources.get("gmail", (None, None))
            gmail_threads = generate_gmail_threads(
                canonical_slot, candidate_slots, participants,
                indirection_depth, fragmentation_depth, generator_config, 
                all_canonical_slots=slots, excluded_slots=set(),
                assigned_distractor=assigned_distractors["gmail"],
                linked_source=linked[0], linked_source_id=linked[1]
            )
            if gmail_threads:
                gmail_path = output_dir / "gmail.json"
                with open(gmail_path, 'w', encoding='utf-8') as f:
                    json.dump({"threads": gmail_threads}, f, indent=2)
                source_data["gmail"] = gmail_path
            
            # Optional drive with negative constraints
            drive_folders, drive_files = generate_drive_files(
                canonical_slot, candidate_slots, indirection_depth, fragmentation_depth, generator_config, all_canonical_slots=slots, excluded_slots=set()
            )
            if drive_files:
                drive_path = output_dir / "drive.json"
                with open(drive_path, 'w', encoding='utf-8') as f:
                    json.dump({"folders": drive_folders, "files": drive_files}, f, indent=2)
                source_data["drive"] = drive_path
    
    # Generate contacts if needed
    if min_required_source >= 2:
        contacts_path = output_dir / "contacts.json"
        contacts_config = generator_config.get("contacts", {})
        name_patterns = contacts_config.get("contact_name_patterns", [])
        if not name_patterns:
            raise ValueError("Missing generator_config entry: contacts.contact_name_patterns")
        
        pattern = name_patterns[0]
        contacts_list = []
        for p in participants:
            contact_name = pattern.format(name=p["name"])
            contacts_list.append({
                "name": contact_name,
                "email": p["email"]
            })
        
        with open(contacts_path, 'w', encoding='utf-8') as f:
            json.dump({"contacts": contacts_list}, f, indent=2)
        source_data["contacts"] = contacts_path
    
    return source_data
