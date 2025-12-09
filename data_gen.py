"""Data generation for MPCBench v2.

Generates per-task source data (calendar, slack, jira, drive, gmail)
based on task requirements using LLM-based generation.
"""

import json
import re
import random
from typing import Dict, Any, List, Tuple, Optional
from pathlib import Path
from datetime import datetime

from openai import OpenAI

from config import get_generator_config, get_data_generation_model, PROMPT_CONFIG_PATH
from task_defs import Task, get_planning_meeting_slots

# Initialize OpenAI client for data generation
_data_gen_client = None


def get_data_gen_client() -> OpenAI:
    """Get OpenAI client for data generation."""
    global _data_gen_client
    if _data_gen_client is None:
        import os
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set. Please set it in .env file or as an environment variable.")
        _data_gen_client = OpenAI(api_key=api_key)
    return _data_gen_client


def generate_with_llm(
    source_type: str,
    task_description: str,
    participants: List[Dict[str, str]],
    all_canonical_slots: List[Dict[str, str]],
    assigned_distractors: List[Dict[str, str]],
    fragmentation_depth: int,
    indirection_depth: int,
    linked_source: Optional[str] = None,
    linked_source_id: Optional[str] = None,
    additional_context: Optional[Dict[str, Any]] = None
) -> str:
    """
    Generate data using LLM for a specific source.
    
    Args:
        source_type: Type of source ("slack", "jira", "drive", "gmail")
        task_description: Task description
        participants: List of participants
        all_canonical_slots: All canonical slots (must NOT be excluded)
        assigned_distractors: List of distractor slots to exclude
        fragmentation_depth: How many pieces to split (each piece is incomplete)
        indirection_depth: Whether to link with other sources
        linked_source: Linked source name (if indirection_depth >= 2)
        linked_source_id: Linked source ID (if indirection_depth >= 2)
        additional_context: Additional context for generation
        
    Returns:
        Generated text content
    """
    # Load prompt config
    with open(PROMPT_CONFIG_PATH, 'r', encoding='utf-8') as f:
        prompt_config = json.load(f)
    
    data_gen_config = prompt_config.get("data_generation", {})
    source_descriptions = data_gen_config.get("source_descriptions", {})
    source_description = source_descriptions.get(source_type, f"Generate realistic {source_type} data for the given task.")
    
    # Get system message and user prompt template from config
    system_message = data_gen_config.get("system_message", "You are a data generator that creates realistic workplace data. Generate natural, realistic content that meets the specified requirements.")
    user_prompt_template = data_gen_config.get("user_prompt_template", {})
    instructions = user_prompt_template.get("instructions", "Generate realistic, natural content that:")
    requirements = user_prompt_template.get("requirements", [])
    format_instructions = user_prompt_template.get("format_instructions", {})
    
    # Build prompt
    prompt_parts = [
        source_description,
        "",
        f"Task: {task_description}",
        "",
        f"Participants: {', '.join([p['name'] for p in participants])}",
        "",
        f"Canonical slots (must NOT be excluded): {', '.join([s['date'] + ' ' + s['slot'] for s in all_canonical_slots])}",
        "",
        f"Distractor slots to exclude: {', '.join([s['date'] + ' ' + s['slot'] for s in assigned_distractors])}",
        "",
        f"Fragmentation depth: {fragmentation_depth} (split into {fragmentation_depth} incomplete pieces)",
        "",
    ]
    
    if indirection_depth >= 2 and linked_source and linked_source_id:
        prompt_parts.append(f"Link with {linked_source} (ID: {linked_source_id}) - reference this in the generated content.")
        prompt_parts.append("")
    
    if additional_context:
        prompt_parts.append("Additional context:")
        for key, value in additional_context.items():
            prompt_parts.append(f"- {key}: {value}")
        prompt_parts.append("")
    
    # Add instructions and requirements from config
    prompt_parts.append(instructions)
    for idx, req in enumerate(requirements, 1):
        # Filter requirements based on indirection_depth
        if "linked source" in req.lower() and indirection_depth < 2:
            continue
        prompt_parts.append(f"{idx}. {req}")
    
    # Add format instructions if available for this source type
    if source_type in format_instructions:
        format_text = format_instructions[source_type]
        # Replace {fragmentation_depth} placeholder
        format_text = format_text.replace("{fragmentation_depth}", str(fragmentation_depth))
        prompt_parts.append("")
        prompt_parts.append(format_text)
    
    prompt = "\n".join(prompt_parts)
    
    # Call LLM
    client = get_data_gen_client()
    model = get_data_generation_model()
    
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_message},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7
    )
    
    return response.choices[0].message.content.strip()


def validate_generated_data(
    generated_text: str,
    source_type: str,
    all_canonical_slots: List[Dict[str, str]],
    assigned_distractors: List[Dict[str, str]],
    fragmentation_depth: int,
    indirection_depth: int,
    linked_source: Optional[str] = None,
    linked_source_id: Optional[str] = None,
    max_retries: int = 3
) -> Tuple[bool, Optional[str]]:
    """
    Validate generated data using LLM.
    
    Returns:
        (is_valid, error_message)
    """
    # Load prompt config for validation
    with open(PROMPT_CONFIG_PATH, 'r', encoding='utf-8') as f:
        prompt_config = json.load(f)
    
    data_gen_config = prompt_config.get("data_generation", {})
    validation_config = data_gen_config.get("validation", {})
    
    # Get validation prompts from config
    validation_system_message = validation_config.get("system_message", "You are a validator that checks if generated data meets requirements.")
    check_instructions = validation_config.get("check_instructions", "Check:\n- Is each piece incomplete on its own? (fragmentation_depth >= 2)\n- When combined, are distractor slots excluded but canonical slots remain?\n- Is the content natural and realistic?\n- Are linked source references correct? (if applicable)")
    response_format = validation_config.get("response_format", "Respond with \"VALID\" if all checks pass, or \"INVALID: <reason>\" if any check fails.")
    
    # Build validation prompt
    canonical_slots_str = ', '.join([s['date'] + ' ' + s['slot'] for s in all_canonical_slots])
    distractor_slots_str = ', '.join([s['date'] + ' ' + s['slot'] for s in assigned_distractors])
    
    validation_prompt = f"""Validate the following generated {source_type} data:

Generated content:
{generated_text}

Requirements:
1. Fragmentation depth: {fragmentation_depth} - content should be split into {fragmentation_depth} incomplete pieces
2. Canonical slots (must NOT be excluded): {canonical_slots_str}
3. Distractor slots (must be excluded): {distractor_slots_str}
"""
    
    if indirection_depth >= 2 and linked_source and linked_source_id:
        validation_prompt += f"4. Should reference {linked_source} (ID: {linked_source_id})\n"
    
    validation_prompt += f"\n{check_instructions}\n\n{response_format}"
    
    # Call LLM for validation
    client = get_data_gen_client()
    model = get_data_generation_model()
    
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": validation_system_message},
            {"role": "user", "content": validation_prompt}
        ],
        temperature=0.0
    )
    
    result = response.choices[0].message.content.strip()
    
    if result.startswith("VALID"):
        return True, None
    else:
        error_msg = result.replace("INVALID:", "").strip() if "INVALID:" in result else "Validation failed"
        return False, error_msg


def assign_distractors_to_sources(
    distractors: List[Dict[str, str]],
    indirection_depth: int,
    min_required_source: int
) -> Dict[str, List[Dict[str, str]]]:
    """
    [Core function] Assign distractors to sources.
    
    Purpose: Randomly assign distractors to sources (slack, jira, drive, gmail)
    - distractor: Time slots that are not canonical (should be removed)
    - Each source removes assigned distractors
    - Multiple distractors can be assigned to the same source (random selection with replacement)
    
    Example:
        distractors = [
            {'date': '2025-12-02', 'slot': '13:00-13:45'},  # distractor 1
            {'date': '2025-12-02', 'slot': '15:00-15:45'},  # distractor 2
            {'date': '2025-12-02', 'slot': '16:00-16:45'}   # distractor 3
        ]
        min_required_source = 3 (calendar + 2 additional sources)
        additional_sources_needed = 2
        → Randomly select 2 sources (with replacement possible)
        → {'slack': [distractor1, distractor2], 'jira': [distractor3]}
        or {'slack': [distractor1], 'jira': [distractor2, distractor3]}
    
    Args:
        distractors: List of distractor slots from calendar
        indirection_depth: Source linking depth (1=calendar only, 2=2 sources, 3+=3+ sources)
        min_required_source: Minimum required sources (including calendar)
        
    Returns:
        Source name -> list of distractor slots mapping
        Example: {'slack': [{'date': '2025-12-02', 'slot': '13:00-13:45'}, ...], 'jira': [...]}
    """
    assigned = {}
    
    # Step 1: Determine available source pool based on indirection_depth
    # - depth=1: calendar only (no additional sources)
    # - depth=2: 2 sources combination needed
    # - depth>=3: 3+ sources combination needed
    if indirection_depth == 1:
        # indirection_depth=1: calendar + 1 additional source (no linking)
        available_sources = ['slack', 'jira', 'drive', 'gmail']
        additional_sources_needed = 1
    elif indirection_depth == 2:
        # indirection_depth=2: 2 sources combination needed
        available_sources = ['slack', 'jira', 'drive', 'gmail']
        additional_sources_needed = min_required_source - 1
    else:  # indirection_depth >= 3
        # indirection_depth>=3: 3+ sources combination needed
        available_sources = ['slack', 'jira', 'drive', 'gmail']
        additional_sources_needed = min_required_source - 1
    
    # Step 2: Validation - check if enough distractors
    if len(distractors) < additional_sources_needed:
        raise ValueError(f"Not enough distractors ({len(distractors)}) for min_required_source ({min_required_source}, needs {additional_sources_needed} additional sources)")
    
    # Step 3: Validation - check if enough available sources
    if len(available_sources) < additional_sources_needed:
        raise ValueError(f"Not enough available sources ({len(available_sources)}) for min_required_source ({min_required_source}, needs {additional_sources_needed} additional sources)")
    
    # Step 4: Randomly select sources (with replacement allowed)
    # Example: additional_sources_needed=2, available_sources=['slack','jira','drive','gmail']
    # → Randomly select 2 sources (can be same source)
    # → Possible: ['slack', 'slack'], ['slack', 'jira'], ['jira', 'drive'], etc.
    selected_sources = random.choices(available_sources, k=additional_sources_needed)
    
    # Step 5: Assign distractors to selected sources
    # Distribute distractors randomly to selected sources
    # Example: selected_sources=['slack', 'jira'], distractors=[d1, d2, d3]
    # → assigned = {'slack': [d1, d2], 'jira': [d3]}
    # or assigned = {'slack': [d1], 'jira': [d2, d3]}
    for source in selected_sources:
        if source not in assigned:
            assigned[source] = []
    
    # Distribute distractors randomly
    for distractor in distractors:
        # Randomly assign each distractor to one of the selected sources
        target_source = random.choice(selected_sources)
        assigned[target_source].append(distractor)
    
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


def generate_calendar(
    all_canonical_slots: List[Dict[str, str]],
    participants: List[Dict[str, str]],
    fragmentation_depth: int,
    generator_config: Dict[str, Any],
    min_required_source: int,
    indirection_depth: int,
    current_date: Optional[str] = None
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, str]]]:
    """
    Generate calendar events with all canonical slots and distractor slots.
    
    Simplified logic:
    1. Create calendar IDs (one per participant)
    2. Add all canonical slots as free for all participants
    3. Determine number of distractor slots based on fragmentation_depth and min_required_source
    4. Generate distractor slots randomly within time range (9:00-17:00) and date range
    5. All distractor slots are also free for all participants
    
    Args:
        all_canonical_slots: All canonical slots from the task (ground truth)
        participants: List of participants with name and email
        fragmentation_depth: Determines number of distractor slots (higher = more distractors)
        generator_config: Generator config (required)
        min_required_source: Minimum required sources (used to calculate distractor count)
        current_date: Current date reference (YYYY-MM-DD). If None, uses datetime.now()
    
    Returns:
        Tuple of (calendars list, events list, candidate_slots list)
        candidate_slots includes all canonical slots + distractor slots
    """
    from datetime import datetime, timedelta
    
    if current_date is None:
        current_date = datetime.now().strftime("%Y-%m-%d")
    
    # Generate calendars (one per participant)
    calendars = []
    calendar_id_map = {}  # email -> calendar_id mapping
    for idx, participant in enumerate(participants):
        calendar_id = f"cal_{idx:03d}"
        calendar_id_map[participant["email"]] = calendar_id
        calendars.append({
            "calendar_id": calendar_id,
            "email": participant["email"],
            "name": "Primary Calendar"
        })
    
    events = []
    candidate_slots = []
    
    # Step 1: Add all canonical slots as free for all participants
    for canonical_slot in all_canonical_slots:
        canonical_date = canonical_slot["date"]
        canonical_time = canonical_slot["slot"]
        candidate_slots.append(canonical_slot)
        
        for participant in participants:
            calendar_id = calendar_id_map.get(participant["email"], f"cal_000")
            events.append({
                "calendar_id": calendar_id,
                "email": participant["email"],
                "date": canonical_date,
                "slot": canonical_time,
                "busy": False
            })
    
    # Step 2: Determine number of distractor slots needed
    # Based on fragmentation_depth, indirection_depth, and min_required_source
    num_distractors = max(fragmentation_depth + indirection_depth, min_required_source)
    
    # Step 3: Determine date range for distractors based on canonical slots
    # Distractors should be in the same date range as canonical slots
    # to ensure min_required_source and indirection_depth work correctly
    canonical_dates = [datetime.strptime(slot["date"], "%Y-%m-%d") for slot in all_canonical_slots]
    min_canonical_date = min(canonical_dates)
    max_canonical_date = max(canonical_dates)
    
    # Extend range by 1 day on each side to allow some flexibility
    distractor_min_date = min_canonical_date - timedelta(days=1)
    distractor_max_date = max_canonical_date + timedelta(days=1)
    
    # Step 4: Generate distractor slots randomly
    # Date range: same range as canonical slots (with 1 day buffer)
    # Time range: 9:00-17:00 (45-minute slots)
    current_dt = datetime.strptime(current_date, "%Y-%m-%d")
    
    # Generate distractor slots
    distractor_slots = []
    max_attempts = num_distractors * 10  # Prevent infinite loop
    attempts = 0
    
    canonical_keys = {(slot["date"], slot["slot"]) for slot in all_canonical_slots}
    
    while len(distractor_slots) < num_distractors and attempts < max_attempts:
        attempts += 1
        
        # Random date: within canonical slot date range (with 1 day buffer)
        days_range = (distractor_max_date - distractor_min_date).days
        if days_range > 0:
            day_offset = random.randint(0, days_range)
            distractor_date_dt = distractor_min_date + timedelta(days=day_offset)
        else:
            # If all canonical slots are on the same day, use that day ± 1 day
            distractor_date_dt = min_canonical_date + timedelta(days=random.randint(-1, 1))
        distractor_date = distractor_date_dt.strftime("%Y-%m-%d")
        
        # Random time: 9:00-17:00 (45-minute slots)
        hour = random.randint(9, 16)  # 9-16 to allow 45-minute slot
        minute = random.choice([0, 15, 30, 45])
        if minute == 45 and hour == 16:
            # 16:45-17:30 is valid, but we'll use 16:00-16:45 for simplicity
            minute = 0
        
        distractor_slot = f"{hour:02d}:{minute:02d}-{hour:02d}:{minute+45:02d}" if minute < 15 else f"{hour:02d}:{minute:02d}-{hour+1:02d}:{minute-15:02d}"
        
        # Ensure slot doesn't overlap with canonical slots
        slot_key = (distractor_date, distractor_slot)
        if slot_key not in canonical_keys and slot_key not in {(s["date"], s["slot"]) for s in distractor_slots}:
            distractor_slots.append({
                "date": distractor_date,
                "slot": distractor_slot
            })
    
    # Step 5: Add distractor slots to candidate_slots and events
    for distractor_slot in distractor_slots:
        candidate_slots.append(distractor_slot)
        for participant in participants:
            calendar_id = calendar_id_map.get(participant["email"], f"cal_000")
            events.append({
                "calendar_id": calendar_id,
                "email": participant["email"],
                "date": distractor_slot["date"],
                "slot": distractor_slot["slot"],
                "busy": False
            })
    
    return calendars, events, candidate_slots


def generate_slack(
    all_canonical_slots: List[Dict[str, str]],
    candidate_slots: List[Dict[str, str]],
    participants: List[Dict[str, str]],
    indirection_depth: int,
    min_required_source: int,
    fragmentation_depth: int,
    generator_config: Dict[str, Any],
    pattern_type: Optional[str] = None,
    assigned_distractors: Optional[List[Dict[str, str]]] = None,
    distractor_linked_sources: Optional[Dict[Tuple[str, str], Tuple[str, str]]] = None
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    [Core function] Generate Slack messages.
    
    Purpose: Generate Slack messages that remove assigned distractors
    - fragmentation_depth: How many messages to split into (each message is incomplete)
    - indirection_depth: Whether to link with other sources (add linked_source reference)
    
    Generation pattern:
        fragmentation_depth=2, indirection_depth=2 example:
        - Message 1: "Amy mentioned that bob might have availability constraints?" (hint, incomplete)
        - Message 2: "They told me only after 14:00 works. The jira issue API-121 has unavailable times."
                   (constraint info + Jira reference, incomplete)
        → Both messages must be combined to complete meaning, Jira must also be checked
    
    Args:
        all_canonical_slots: All canonical slots from the task
        candidate_slots: All candidate slots (canonical + distractors)
        participants: List of participants
        indirection_depth: Source linking depth
        min_required_source: Minimum required sources
        fragmentation_depth: Number of messages (each message is generated incompletely)
        generator_config: Generator configuration
        pattern_type: Pattern type (e.g., "time", "weekday")
        assigned_distractors: List of distractor slots this source should remove
        distractor_linked_sources: Dict mapping (date, slot) -> (linked_source, linked_source_id)
    
    Returns:
        (channels list, messages list)
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
        # indirection_depth=1: no linking, but still generate messages
        pass
    
    # Helper: Get message author name
    def get_user_name(index: int) -> str:
        if participants and index < len(participants):
            return participants[index]["name"].lower()
        elif base_user_names and index < len(base_user_names):
            return base_user_names[index]
        else:
            raise ValueError("Missing generator_config entry: slack.base_user_names (required when no participants available)")
    
    # Find third-party name (non-participant, used for hints)
    # Example: In "Amy mentioned that bob might have availability constraints", Amy is the third party
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
    
    # Store third_party_name for use in LLM generation
    generator_config["_third_party_name"] = third_party_name
    
    # Get timestamp patterns from calendar config
    calendar_config = generator_config.get("calendar", {})
    timestamp_patterns = calendar_config.get("timestamp_patterns", [])
    if not timestamp_patterns:
        raise ValueError("Missing generator_config entry: calendar.timestamp_patterns")
    
    # Option C: fragmentation_depth * len(assigned_distractors) messages
    # Each distractor gets fragmentation_depth incomplete messages
    # Messages for each distractor must be combined to exclude that distractor
    if not assigned_distractors:
        return channels, messages
    
    # Get task description from generator_config (passed from generate_planning_source_data)
    task_description = generator_config.get("_task_description", "Find a meeting time")
    
    # Process each distractor
    for distractor_idx, assigned_distractor in enumerate(assigned_distractors):
        # Get linked_source for this distractor
        distractor_key = (assigned_distractor["date"], assigned_distractor["slot"])
        linked_source = None
        linked_source_id = None
        if distractor_linked_sources and distractor_key in distractor_linked_sources:
            linked_source, linked_source_id = distractor_linked_sources[distractor_key]
        
        # Generate messages for this distractor using LLM
        # LLM generates fragmentation_depth messages that are incomplete individually
        # but when combined, exclude the distractor while keeping canonical slots
        
        max_retries = 3
        for retry in range(max_retries):
            # Generate messages using LLM
            generated_text = generate_with_llm(
                source_type="slack",
                task_description=task_description,
                participants=participants,
                all_canonical_slots=all_canonical_slots,
                assigned_distractors=[assigned_distractor],  # Single distractor for this call
                fragmentation_depth=fragmentation_depth,
                indirection_depth=indirection_depth,
                linked_source=linked_source,
                linked_source_id=linked_source_id,
                additional_context={
                    "channel": default_channel,
                    "base_user_names": base_user_names,
                    "third_party_name": generator_config.get("_third_party_name", "Amy")
                }
            )
            
            # Log generated text for debugging
            print(f"\n[DEBUG] Slack generation attempt {retry + 1}/{max_retries}")
            print(f"[DEBUG] Generated text:\n{generated_text}\n")
            
            # Validate generated data
            is_valid, error_msg = validate_generated_data(
                generated_text=generated_text,
                source_type="slack",
                all_canonical_slots=all_canonical_slots,
                assigned_distractors=[assigned_distractor],
                fragmentation_depth=fragmentation_depth,
                indirection_depth=indirection_depth,
                linked_source=linked_source,
                linked_source_id=linked_source_id
            )
            
            if is_valid:
                # Parse LLM output - expect JSON array of messages
                try:
                    # Try to parse as JSON first
                    parsed = json.loads(generated_text)
                    if isinstance(parsed, list):
                        # LLM returned list of messages
                        for msg in parsed:
                            if isinstance(msg, dict) and "text" in msg:
                                messages.append({
                                    "channel_id": default_channel_id,
                                    "channel": default_channel,
                                    "user": msg.get("user", get_user_name(len(messages) % len(participants) if participants else len(messages))),
                                    "text": msg["text"],
                                    "timestamp": msg.get("timestamp", timestamp_patterns[len(messages) % len(timestamp_patterns)])
                                })
                            elif isinstance(msg, str):
                                # Simple string message
                                messages.append({
                                    "channel_id": default_channel_id,
                                    "channel": default_channel,
                                    "user": get_user_name(len(messages) % len(participants) if participants else len(messages)),
                                    "text": msg,
                                    "timestamp": timestamp_patterns[len(messages) % len(timestamp_patterns)]
                                })
                    else:
                        # Not a list, treat as single message
                        messages.append({
                            "channel_id": default_channel_id,
                            "channel": default_channel,
                            "user": get_user_name(len(messages) % len(participants) if participants else len(messages)),
                            "text": generated_text,
                            "timestamp": timestamp_patterns[len(messages) % len(timestamp_patterns)]
                        })
                except json.JSONDecodeError:
                    # Not JSON, split by newlines or treat as single message
                    lines = generated_text.strip().split('\n')
                    for line in lines:
                        line = line.strip()
                        if line:
                            messages.append({
                                "channel_id": default_channel_id,
                                "channel": default_channel,
                                "user": get_user_name(len(messages) % len(participants) if participants else len(messages)),
                                "text": line,
                                "timestamp": timestamp_patterns[len(messages) % len(timestamp_patterns)]
                            })
                
                # Track how many messages we added for this distractor
                messages_before = len(messages)
                messages_added = messages_before - (distractor_idx * fragmentation_depth)
                
                # Ensure we have fragmentation_depth messages for this distractor
                # If LLM generated fewer, pad with additional messages
                while messages_added < fragmentation_depth:
                    messages.append({
                        "channel_id": default_channel_id,
                        "channel": default_channel,
                        "user": get_user_name(len(messages) % len(participants) if participants else len(messages)),
                        "text": generated_text.split('\n')[0] if '\n' in generated_text else generated_text,  # Use first line or full text
                        "timestamp": timestamp_patterns[len(messages) % len(timestamp_patterns)]
                    })
                    messages_added += 1
                
                break  # Success, exit retry loop
            else:
                print(f"[DEBUG] Validation failed: {error_msg}")
                if retry == max_retries - 1:
                    # Last retry failed, raise error with generated text
                    raise ValueError(f"Failed to generate valid Slack messages after {max_retries} attempts. Last error: {error_msg}\n\nGenerated text:\n{generated_text}")
    
    return channels, messages


def generate_jira(
    all_canonical_slots: List[Dict[str, str]],
    candidate_slots: List[Dict[str, str]],
    indirection_depth: int,
    fragmentation_depth: int,
    generator_config: Dict[str, Any],
    assigned_distractors: Optional[List[Dict[str, str]]] = None,
    distractor_linked_sources: Optional[Dict[Tuple[str, str], Tuple[str, str]]] = None
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
    
    # If no assigned_distractors, return empty issues
    if not assigned_distractors:
        return projects, issues
    
    # Get task description from generator_config
    task_description = generator_config.get("_task_description", "Find a meeting time")
    
    # Get participants from generator_config (if available)
    participants = generator_config.get("_participants", [])
    
    if indirection_depth >= 2:
        # Get third-party name for hints
        fallback_names = generator_config.get("fallback_names", ["Alice", "Bob", "Carol", "Dave", "Eve"])
        third_party_name = fallback_names[0] if fallback_names else "Amy"
        
        # Option C: fragmentation_depth * len(assigned_distractors) issues
        # Each distractor gets fragmentation_depth incomplete issues
        # Issues for each distractor must be combined to exclude that distractor
        for distractor_idx, assigned_distractor in enumerate(assigned_distractors):
            # Get linked_source for this distractor
            distractor_key = (assigned_distractor["date"], assigned_distractor["slot"])
            linked_source = None
            linked_source_id = None
            if distractor_linked_sources and distractor_key in distractor_linked_sources:
                linked_source, linked_source_id = distractor_linked_sources[distractor_key]
            
            # Generate issues for this distractor using LLM
            max_retries = 3
            for retry in range(max_retries):
                # Generate issue content using LLM
                generated_text = generate_with_llm(
                    source_type="jira",
                    task_description=task_description,
                    participants=participants if participants else [],
                    all_canonical_slots=all_canonical_slots,
                    assigned_distractors=[assigned_distractor],
                    fragmentation_depth=fragmentation_depth,
                    indirection_depth=indirection_depth,
                    linked_source=linked_source,
                    linked_source_id=linked_source_id,
                    additional_context={
                        "project_key": project_keys[0],
                        "third_party_name": third_party_name
                    }
                )
                
                # Log generated text for debugging
                print(f"\n[DEBUG] Jira generation attempt {retry + 1}/{max_retries}")
                print(f"[DEBUG] Generated text:\n{generated_text}\n")
                
                # Validate generated data
                is_valid, error_msg = validate_generated_data(
                    generated_text=generated_text,
                    source_type="jira",
                    all_canonical_slots=all_canonical_slots,
                    assigned_distractors=[assigned_distractor],
                    fragmentation_depth=fragmentation_depth,
                    indirection_depth=indirection_depth,
                    linked_source=linked_source,
                    linked_source_id=linked_source_id
                )
                
                if is_valid:
                    # Parse LLM output - expect JSON array or newline-separated issues
                    try:
                        parsed = json.loads(generated_text)
                        if isinstance(parsed, list):
                            # LLM returned list of issues
                            for issue_data in parsed:
                                if isinstance(issue_data, dict):
                                    description = issue_data.get("description", "")
                                    # Use first sentence or first 50 chars as summary if description exists
                                    if description:
                                        summary = description.split('.')[0][:50] if '.' in description else description[:50]
                                    else:
                                        continue
                                elif isinstance(issue_data, str):
                                    description = issue_data
                                    summary = description.split('.')[0][:50] if '.' in description else description[:50]
                                else:
                                    continue
                                
                                global_issue_idx = distractor_idx * fragmentation_depth + len(issues)
                                issues.append({
                                    "issue_key": f"{project_keys[0]}-{120 + global_issue_idx}",
                                    "project_key": project_keys[0],
                                    "summary": summary,
                                    "description": description,
                                    "status": "To Do"
                                })
                        else:
                            # Not a list, treat as single issue
                            global_issue_idx = distractor_idx * fragmentation_depth
                            description = generated_text
                            summary = description.split('.')[0][:50] if '.' in description else description[:50]
                            issues.append({
                                "issue_key": f"{project_keys[0]}-{120 + global_issue_idx}",
                                "project_key": project_keys[0],
                                "summary": summary,
                                "description": description,
                                "status": "To Do"
                            })
                    except json.JSONDecodeError:
                        # Not JSON, split by newlines or treat as single issue
                        lines = generated_text.strip().split('\n')
                        for line in lines:
                            line = line.strip()
                            if line:
                                global_issue_idx = distractor_idx * fragmentation_depth + len(issues)
                                description = line
                                summary = description.split('.')[0][:50] if '.' in description else description[:50]
                                issues.append({
                                    "issue_key": f"{project_keys[0]}-{120 + global_issue_idx}",
                                    "project_key": project_keys[0],
                                    "summary": summary,
                                    "description": description,
                                    "status": "To Do"
                                })
                    
                    # Ensure we have fragmentation_depth issues for this distractor
                    issues_added = len([i for i in issues if i.get("_distractor_idx") == distractor_idx])
                    while issues_added < fragmentation_depth:
                        global_issue_idx = distractor_idx * fragmentation_depth + len(issues)
                        description = generated_text.split('\n')[0] if '\n' in generated_text else generated_text
                        summary = description.split('.')[0][:50] if '.' in description else description[:50]
                        issues.append({
                            "issue_key": f"{project_keys[0]}-{120 + global_issue_idx}",
                            "project_key": project_keys[0],
                            "summary": summary,
                            "description": description,
                            "status": "To Do",
                            "_distractor_idx": distractor_idx
                        })
                        issues_added += 1
                    
                    break  # Success, exit retry loop
                else:
                    print(f"[DEBUG] Validation failed: {error_msg}")
                    if retry == max_retries - 1:
                        # Last retry failed, raise error with generated text
                        raise ValueError(f"Failed to generate valid Jira issues after {max_retries} attempts. Last error: {error_msg}\n\nGenerated text:\n{generated_text}")
    
    return projects, issues


def generate_drive(
    all_canonical_slots: List[Dict[str, str]],
    candidate_slots: List[Dict[str, str]],
    indirection_depth: int,
    fragmentation_depth: int,
    generator_config: Dict[str, Any],
    excluded_slots: set = None,
    assigned_distractors: Optional[List[Dict[str, str]]] = None,
    distractor_linked_sources: Optional[Dict[Tuple[str, str], Tuple[str, str]]] = None
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
    
    # If no assigned_distractors, return empty files
    if not assigned_distractors:
        return folders, files
    
    # Get task description from generator_config (passed from generate_planning_source_data)
    task_description = generator_config.get("_task_description", "Find a meeting time")
    
    # Get participants from generator_config (if available)
    participants = generator_config.get("_participants", [])
    
    if indirection_depth >= 2:
        # Get third-party name for hints
        fallback_names = generator_config.get("fallback_names", ["Alice", "Bob", "Carol", "Dave", "Eve"])
        third_party_name = fallback_names[0] if fallback_names else "Amy"
        
        # Option C: fragmentation_depth * len(assigned_distractors) files
        # Each distractor gets fragmentation_depth incomplete files
        # Files for each distractor must be combined to exclude that distractor
        for distractor_idx, assigned_distractor in enumerate(assigned_distractors):
            # Get linked_source for this distractor
            distractor_key = (assigned_distractor["date"], assigned_distractor["slot"])
            linked_source = None
            linked_source_id = None
            if distractor_linked_sources and distractor_key in distractor_linked_sources:
                linked_source, linked_source_id = distractor_linked_sources[distractor_key]
            
            # Generate file content for this distractor using LLM
            max_retries = 3
            for retry in range(max_retries):
                # Generate file content using LLM
                generated_text = generate_with_llm(
                    source_type="drive",
                    task_description=task_description,
                    participants=participants if participants else [],
                    all_canonical_slots=all_canonical_slots,
                    assigned_distractors=[assigned_distractor],
                    fragmentation_depth=fragmentation_depth,
                    indirection_depth=indirection_depth,
                    linked_source=linked_source,
                    linked_source_id=linked_source_id,
                    additional_context={
                        "third_party_name": third_party_name
                    }
                )
                
                # Log generated text for debugging
                print(f"\n[DEBUG] Drive generation attempt {retry + 1}/{max_retries}")
                print(f"[DEBUG] Generated text:\n{generated_text}\n")
                
                # Validate generated data
                is_valid, error_msg = validate_generated_data(
                    generated_text=generated_text,
                    source_type="drive",
                    all_canonical_slots=all_canonical_slots,
                    assigned_distractors=[assigned_distractor],
                    fragmentation_depth=fragmentation_depth,
                    indirection_depth=indirection_depth,
                    linked_source=linked_source,
                    linked_source_id=linked_source_id
                )
                
                if is_valid:
                    # Parse LLM output - expect JSON array or newline-separated file contents
                    try:
                        parsed = json.loads(generated_text)
                        if isinstance(parsed, list):
                            # LLM returned list of file contents
                            for file_idx, file_content in enumerate(parsed):
                                global_file_idx = distractor_idx * fragmentation_depth + file_idx
                                doc_title = f"Document {global_file_idx + 1}"
                                
                                if isinstance(file_content, dict):
                                    text = file_content.get("text", file_content.get("content", ""))
                                    name = file_content.get("name", doc_title)
                                elif isinstance(file_content, str):
                                    text = file_content
                                    name = doc_title
                                else:
                                    continue
                                
                                files.append({
                                    "file_id": f"file_{global_file_idx:03d}",
                                    "folder_id": default_folder_id,
                                    "name": name,
                                    "text": text
                                })
                        else:
                            # Not a list, treat as single file
                            global_file_idx = distractor_idx * fragmentation_depth
                            doc_title = f"Document {global_file_idx + 1}"
                            files.append({
                                "file_id": f"file_{global_file_idx:03d}",
                                "folder_id": default_folder_id,
                                "name": doc_title,
                                "text": generated_text
                            })
                    except json.JSONDecodeError:
                        # Not JSON, split by newlines or treat as single file
                        lines = generated_text.strip().split('\n')
                        for file_idx, line in enumerate(lines):
                            line = line.strip()
                            if line:
                                global_file_idx = distractor_idx * fragmentation_depth + file_idx
                                doc_title = f"Document {global_file_idx + 1}"
                                files.append({
                                    "file_id": f"file_{global_file_idx:03d}",
                                    "folder_id": default_folder_id,
                                    "name": doc_title,
                                    "text": line
                                })
                    
                    # Ensure we have fragmentation_depth files for this distractor
                    files_added = len([f for f in files if f.get("_distractor_idx") == distractor_idx])
                    while files_added < fragmentation_depth:
                        global_file_idx = distractor_idx * fragmentation_depth + len(files)
                        doc_title = f"Document {global_file_idx + 1}"
                        files.append({
                            "file_id": f"file_{global_file_idx:03d}",
                            "folder_id": default_folder_id,
                            "name": doc_title,
                            "text": generated_text.split('\n')[0] if '\n' in generated_text else generated_text,
                            "_distractor_idx": distractor_idx
                        })
                        files_added += 1
                    
                    break  # Success, exit retry loop
                else:
                    print(f"[DEBUG] Validation failed: {error_msg}")
                    if retry == max_retries - 1:
                        # Last retry failed, raise error with generated text
                        raise ValueError(f"Failed to generate valid Drive files after {max_retries} attempts. Last error: {error_msg}\n\nGenerated text:\n{generated_text}")
    
    return folders, files


def generate_gmail(
    all_canonical_slots: List[Dict[str, str]],
    candidate_slots: List[Dict[str, str]],
    participants: List[Dict[str, str]],
    indirection_depth: int,
    fragmentation_depth: int,
    generator_config: Dict[str, Any],
    excluded_slots: set = None,
    assigned_distractors: Optional[List[Dict[str, str]]] = None,
    distractor_linked_sources: Optional[Dict[Tuple[str, str], Tuple[str, str]]] = None
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
    
    # Gmail generation works for all indirection_depth values (1, 2, 3+)
    gmail_config = generator_config.get("gmail", {})
    from_candidates = gmail_config.get("from_candidates", [])
    to_candidates = gmail_config.get("to_candidates", [])
    calendar_config = generator_config.get("calendar", {})
    timestamp_patterns = calendar_config.get("timestamp_patterns", [])
    if not timestamp_patterns:
        raise ValueError("Missing generator_config entry: calendar.timestamp_patterns")
    
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
    
    # Get task description from generator_config
    task_description = generator_config.get("_task_description", "Find a meeting time")
    
    # Get third-party name for hints
    fallback_names = generator_config.get("fallback_names", ["Alice", "Bob", "Carol", "Dave", "Eve"])
    third_party_name = fallback_names[0] if fallback_names else "Amy"
    
    # Option C: fragmentation_depth * len(assigned_distractors) messages
    # Each distractor gets fragmentation_depth incomplete messages
    # Messages for each distractor must be combined to exclude that distractor
    if assigned_distractors:
        # Process each distractor
        for distractor_idx, assigned_distractor in enumerate(assigned_distractors):
            # Get linked_source for this distractor
            distractor_key = (assigned_distractor["date"], assigned_distractor["slot"])
            linked_source = None
            linked_source_id = None
            if distractor_linked_sources and distractor_key in distractor_linked_sources:
                linked_source, linked_source_id = distractor_linked_sources[distractor_key]
            
            # Create one thread per distractor with fragmentation_depth messages
            subject = f"Schedule update {distractor_idx + 1}"
            
            # Generate messages for this distractor using LLM
            max_retries = 3
            for retry in range(max_retries):
                # Generate messages using LLM
                generated_text = generate_with_llm(
                    source_type="gmail",
                    task_description=task_description,
                    participants=participants if participants else [],
                    all_canonical_slots=all_canonical_slots,
                    assigned_distractors=[assigned_distractor],
                    fragmentation_depth=fragmentation_depth,
                    indirection_depth=indirection_depth,
                    linked_source=linked_source,
                    linked_source_id=linked_source_id,
                    additional_context={
                        "subject": subject,
                        "from": from_addr,
                        "to": to_addrs,
                        "third_party_name": third_party_name
                    }
                )
                
                # Log generated text for debugging
                print(f"\n[DEBUG] Gmail generation attempt {retry + 1}/{max_retries}")
                print(f"[DEBUG] Generated text:\n{generated_text}\n")
                
                # Validate generated data
                is_valid, error_msg = validate_generated_data(
                    generated_text=generated_text,
                    source_type="gmail",
                    all_canonical_slots=all_canonical_slots,
                    assigned_distractors=[assigned_distractor],
                    fragmentation_depth=fragmentation_depth,
                    indirection_depth=indirection_depth,
                    linked_source=linked_source,
                    linked_source_id=linked_source_id
                )
                
                if is_valid:
                    # Parse LLM output - expect JSON array or newline-separated messages
                    thread_messages = []
                    try:
                        parsed = json.loads(generated_text)
                        if isinstance(parsed, list):
                            # LLM returned list of messages
                            for msg_idx, msg_data in enumerate(parsed):
                                global_msg_idx = distractor_idx * fragmentation_depth + msg_idx
                                timestamp = timestamp_patterns[global_msg_idx % len(timestamp_patterns)]
                                
                                if isinstance(msg_data, dict):
                                    text = msg_data.get("text", msg_data.get("content", ""))
                                elif isinstance(msg_data, str):
                                    text = msg_data
                                else:
                                    continue
                                
                                thread_messages.append({
                                    "from": from_addr,
                                    "to": to_addrs,
                                    "subject": subject,
                                    "text": text,
                                    "timestamp": timestamp
                                })
                        else:
                            # Not a list, treat as single message
                            timestamp = timestamp_patterns[distractor_idx * fragmentation_depth % len(timestamp_patterns)]
                            thread_messages.append({
                                "from": from_addr,
                                "to": to_addrs,
                                "subject": subject,
                                "text": generated_text,
                                "timestamp": timestamp
                            })
                    except json.JSONDecodeError:
                        # Not JSON, split by newlines or treat as single message
                        lines = generated_text.strip().split('\n')
                        for msg_idx, line in enumerate(lines):
                            line = line.strip()
                            if line:
                                global_msg_idx = distractor_idx * fragmentation_depth + msg_idx
                                timestamp = timestamp_patterns[global_msg_idx % len(timestamp_patterns)]
                                thread_messages.append({
                                    "from": from_addr,
                                    "to": to_addrs,
                                    "subject": subject,
                                    "text": line,
                                    "timestamp": timestamp
                                })
                    
                    # Ensure we have fragmentation_depth messages for this distractor
                    while len(thread_messages) < fragmentation_depth:
                        global_msg_idx = distractor_idx * fragmentation_depth + len(thread_messages)
                        timestamp = timestamp_patterns[global_msg_idx % len(timestamp_patterns)]
                        thread_messages.append({
                            "from": from_addr,
                            "to": to_addrs,
                            "subject": subject,
                            "text": generated_text.split('\n')[0] if '\n' in generated_text else generated_text,
                            "timestamp": timestamp
                        })
                    
                    threads.append({
                        "thread_id": f"thread_{distractor_idx + 1:03d}",
                        "subject": subject,
                        "messages": thread_messages
                    })
                    
                    break  # Success, exit retry loop
                else:
                    print(f"[DEBUG] Validation failed: {error_msg}")
                    if retry == max_retries - 1:
                        # Last retry failed, raise error with generated text
                        raise ValueError(f"Failed to generate valid Gmail messages after {max_retries} attempts. Last error: {error_msg}\n\nGenerated text:\n{generated_text}")
    else:
            # Fallback: create one thread with fragmentation_depth messages (old behavior)
            subject = "Schedule update"
            thread_messages = []
            
            for msg_idx in range(fragmentation_depth):
                timestamp = timestamp_patterns[msg_idx % len(timestamp_patterns)]
                text = f"There might be an issue with the time {third_party_name} mentioned."
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
    [Main function] Orchestration function that generates all source data for a planning task.
    
    Flow:
    1. Extract/generate participants
    2. Extract canonical slots (ground truth slots)
    3. Generate calendar (canonical + distractor slots)
    4. Assign distractors to sources (multiple distractors per source possible)
    5. Generate source-specific data (slack, jira, drive, gmail)
    6. Save source data files
    
    Key logic:
    - fragmentation_depth: How many pieces to split data within each source
    - indirection_depth: How many sources to combine
    - min_required_source: Minimum required number of sources
    
    Returns:
        Source name -> file path mapping
        Example: {'calendar': Path(...), 'slack': Path(...), ...}
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    source_data = {}
    generator_config = get_generator_config()
    
    # Add task description to generator_config for LLM-based generation
    generator_config["_task_description"] = task.task_description
    
    # ============================================================
    # Step 1: Generate participants
    # ============================================================
    # Extract names from task description or use fallback_names
    participants = generate_participants(task, generator_config)
    
    # ============================================================
    # Step 2: Extract canonical slots (ground truth slots)
    # ============================================================
    # Extract meeting_slots from task's canonical_answer
    slots = get_planning_meeting_slots(task)
    if not slots:
        return source_data
    
    # Extract complexity parameters from task metadata
    indirection_depth = task.metadata["indirection_depth"]  # Source linking depth
    min_required_source = task.metadata["min_required_source"]  # Minimum required sources
    fragmentation_depth = task.metadata["fragmentation_depth"]  # Data fragmentation within source
    
    # Get current_date from task or use datetime.now()
    current_date = task.current_date
    if current_date is None:
        current_date = datetime.now().strftime("%Y-%m-%d")
    
    # ============================================================
    # Step 3: Generate calendar
    # ============================================================
    # - all_canonical_slots: all ground truth slots (included from the start)
    # - distractor slots: non-ground-truth slots (will be excluded by other sources later)
    # - candidate_slots: all slots (canonical + distractor)
    calendars, calendar_events, candidate_slots = generate_calendar(
        all_canonical_slots=slots,
        participants=participants,
        fragmentation_depth=fragmentation_depth,
        generator_config=generator_config,
        min_required_source=min_required_source,
        indirection_depth=indirection_depth,
        current_date=current_date
    )
    
    # ============================================================
    # Step 4: Extract and assign distractors
    # ============================================================
    # All slots except canonical slots are distractors
    canonical_keys = {(slot["date"], slot["slot"]) for slot in slots}
    distractors = [s for s in candidate_slots if (s["date"], s["slot"]) not in canonical_keys]
    
    # Assign distractors to sources (random, multiple distractors per source possible)
    # Example: min_required_source=3, indirection_depth=2
    # → {'slack': [distractor1, distractor2], 'jira': [distractor3]}
    assigned_distractors = assign_distractors_to_sources(
        distractors, indirection_depth, min_required_source
    )
    
    # Save calendar JSON file
    calendar_path = output_dir / "calendar.json"
    with open(calendar_path, 'w', encoding='utf-8') as f:
        json.dump({"calendars": calendars, "events": calendar_events}, f, indent=2)
    source_data["calendar"] = calendar_path
    
    # ============================================================
    # Step 6: Generate additional sources (slack, jira, drive, gmail)
    # ============================================================
    # Only generate sources assigned in assigned_distractors
    # assigned_distractors is now Dict[str, List[Dict[str, str]]]
    # Each source has a list of distractors assigned
    
    # Determine linked sources for each distractor based on indirection_depth
    distractor_linked_sources = {}  # (date, slot) -> (linked_source, linked_source_id)
    source_linking_map = {}  # source_name -> linked_source_name (for indirection_depth >= 3 chain)
    
    if indirection_depth == 1:
        # indirection_depth=1: No linking between sources
        # distractor_linked_sources remains empty
        pass
    elif indirection_depth == 2:
        # indirection_depth=2: 2 sources combination, A ↔ B (bidirectional or unidirectional, random)
        # Get all assigned sources
        assigned_source_names = [s for s in assigned_distractors.keys() if assigned_distractors[s]]
        if len(assigned_source_names) >= 2:
            # Create linking between 2 sources (random direction, unidirectional only)
            source1, source2 = assigned_source_names[0], assigned_source_names[1]
            
            # Randomly decide linking direction: A → B or B → A (unidirectional only)
            link_direction = random.choice(["A_to_B", "B_to_A"])
            
            if link_direction == "A_to_B":
                source_linking_map[source1] = source2
            else:  # B_to_A
                source_linking_map[source2] = source1
            
            # For each distractor, assign linked_source based on source_linking_map
            for source_name, distractor_list in assigned_distractors.items():
                if not distractor_list:
                    continue
                
                linked_source_name = source_linking_map.get(source_name)
                if not linked_source_name:
                    continue
                
                for distractor in distractor_list:
                    distractor_key = (distractor["date"], distractor["slot"])
                    
                    # Set linked_source_id to None initially (will be updated after source generation)
                    linked_source_id = None
                    distractor_linked_sources[distractor_key] = (linked_source_name, linked_source_id)
    else:  # indirection_depth >= 3
        # indirection_depth>=3: 3+ sources combination, chain A → B → C
        # Get all assigned sources
        assigned_source_names = [s for s in assigned_distractors.keys() if assigned_distractors[s]]
        if len(assigned_source_names) >= 2:
            # Create a chain: A → B → C → ...
            # Shuffle sources to create random chain
            shuffled_sources = assigned_source_names.copy()
            random.shuffle(shuffled_sources)
            
            # Create chain: each source links to the next one
            for i in range(len(shuffled_sources) - 1):
                source_linking_map[shuffled_sources[i]] = shuffled_sources[i + 1]
            # Last source can link back to first (circular) or stay unlinked
            if random.random() < 0.5:  # 50% chance of circular link
                source_linking_map[shuffled_sources[-1]] = shuffled_sources[0]
            
            # For each distractor, assign linked_source based on source_linking_map
            for source_name, distractor_list in assigned_distractors.items():
                if not distractor_list:
                    continue
                
                linked_source_name = source_linking_map.get(source_name)
                if not linked_source_name:
                    continue
                
                for distractor in distractor_list:
                    distractor_key = (distractor["date"], distractor["slot"])
                    
                    # Set linked_source_id to None initially (will be updated after source generation)
                    linked_source_id = None
                    distractor_linked_sources[distractor_key] = (linked_source_name, linked_source_id)
    
    # Helper function to extract actual IDs from generated sources
    def extract_source_id(source_name: str, generated_data: Any) -> Optional[str]:
        """Extract actual ID from generated source data."""
        if source_name == "slack":
            # Extract channel_id from first channel
            if isinstance(generated_data, tuple) and len(generated_data) >= 1:
                channels = generated_data[0]
                if channels and len(channels) > 0:
                    return channels[0].get("channel_id")
        elif source_name == "jira":
            # Extract issue_key from first issue
            if isinstance(generated_data, tuple) and len(generated_data) >= 2:
                issues = generated_data[1]
                if issues and len(issues) > 0:
                    return issues[0].get("issue_key")
        elif source_name == "drive":
            # Extract file_id from first file, or file name if file_id not available
            if isinstance(generated_data, tuple) and len(generated_data) >= 2:
                files = generated_data[1]
                if files and len(files) > 0:
                    return files[0].get("file_id") or files[0].get("name")
        elif source_name == "gmail":
            # Extract thread_id from first thread
            if isinstance(generated_data, list) and len(generated_data) > 0:
                return generated_data[0].get("thread_id")
        return None
    
    # Helper function to update distractor_linked_sources with actual IDs
    def update_linked_source_ids(source_name: str, actual_id: str):
        """Update distractor_linked_sources with actual ID for the given source."""
        if not actual_id:
            return
        for distractor_key, (linked_source_name, linked_source_id) in distractor_linked_sources.items():
            if linked_source_name == source_name and linked_source_id is None:
                distractor_linked_sources[distractor_key] = (linked_source_name, actual_id)
    
    if indirection_depth == 1:
        # indirection_depth=1: calendar + 1 additional source (no linking)
        # Generate sources based on assigned_distractors
        for source_name, distractor_list in assigned_distractors.items():
            if not distractor_list:
                continue
            
            if source_name == "slack":
                slack_channels, slack_messages = generate_slack(
                    all_canonical_slots=slots,
                    candidate_slots=candidate_slots,
                    participants=participants,
                    indirection_depth=indirection_depth,
                    min_required_source=min_required_source,
                    fragmentation_depth=fragmentation_depth,
                    generator_config=generator_config,
                    pattern_type="time",
                    assigned_distractors=distractor_list,
                    distractor_linked_sources=distractor_linked_sources
                )
                if slack_messages:
                    slack_path = output_dir / "slack.json"
                    with open(slack_path, 'w', encoding='utf-8') as f:
                        json.dump({"channels": slack_channels, "messages": slack_messages}, f, indent=2)
                    source_data["slack"] = slack_path
                    # Extract actual channel_id and update distractor_linked_sources
                    actual_id = extract_source_id("slack", (slack_channels, slack_messages))
                    update_linked_source_ids("slack", actual_id)
            elif source_name == "jira":
                jira_projects, jira_issues = generate_jira(
                    all_canonical_slots=slots,
                    candidate_slots=candidate_slots,
                    indirection_depth=indirection_depth,
                    fragmentation_depth=fragmentation_depth,
                    generator_config=generator_config,
                    assigned_distractors=distractor_list,
                    distractor_linked_sources=distractor_linked_sources
                )
                if jira_issues:
                    jira_path = output_dir / "jira.json"
                    with open(jira_path, 'w', encoding='utf-8') as f:
                        json.dump({"projects": jira_projects, "issues": jira_issues}, f, indent=2)
                    source_data["jira"] = jira_path
                    # Extract actual issue_key and update distractor_linked_sources
                    actual_id = extract_source_id("jira", (jira_projects, jira_issues))
                    update_linked_source_ids("jira", actual_id)
            elif source_name == "drive":
                drive_folders, drive_files = generate_drive(
                    all_canonical_slots=slots,
                    candidate_slots=candidate_slots,
                    indirection_depth=indirection_depth,
                    fragmentation_depth=fragmentation_depth,
                    generator_config=generator_config,
                    excluded_slots=set(),
                    assigned_distractors=distractor_list,
                    distractor_linked_sources=distractor_linked_sources
                )
                if drive_files:
                    drive_path = output_dir / "drive.json"
                    with open(drive_path, 'w', encoding='utf-8') as f:
                        json.dump({"folders": drive_folders, "files": drive_files}, f, indent=2)
                    source_data["drive"] = drive_path
                    # Extract actual file_id or file name and update distractor_linked_sources
                    actual_id = extract_source_id("drive", (drive_folders, drive_files))
                    update_linked_source_ids("drive", actual_id)
            elif source_name == "gmail":
                gmail_threads = generate_gmail(
                    all_canonical_slots=slots,
                    candidate_slots=candidate_slots,
                    participants=participants,
                    indirection_depth=indirection_depth,
                    fragmentation_depth=fragmentation_depth,
                    generator_config=generator_config,
                    excluded_slots=set(),
                    assigned_distractors=distractor_list,
                    distractor_linked_sources=distractor_linked_sources
                )
                if gmail_threads:
                    gmail_path = output_dir / "gmail.json"
                    with open(gmail_path, 'w', encoding='utf-8') as f:
                        json.dump({"threads": gmail_threads}, f, indent=2)
                    source_data["gmail"] = gmail_path
                    # Extract actual thread_id and update distractor_linked_sources
                    actual_id = extract_source_id("gmail", gmail_threads)
                    update_linked_source_ids("gmail", actual_id)
    elif indirection_depth == 2:
        # ============================================================
        # indirection_depth=2: 2 sources combination needed
        # ============================================================
        # Example: slack + jira, slack + drive, jira + drive, etc.
        # Each source references another source to make it incomplete alone
        # Each distractor gets a random linked_source (Option B)
        
        # Determine source generation order based on source_linking_map
        # Generate sources in chain order: first source, then linked source
        source_order = []
        if source_linking_map:
            # Find the source that is referenced but doesn't reference anyone (start of chain)
            referenced_sources = set(source_linking_map.values())
            referencing_sources = set(source_linking_map.keys())
            # Start with source that references another but is not referenced
            start_sources = referencing_sources - referenced_sources
            if start_sources:
                current = list(start_sources)[0]
            else:
                # Circular or all sources are referenced, start with first
                current = list(referencing_sources)[0] if referencing_sources else None
            
            # Build chain order
            visited = set()
            while current and current not in visited:
                source_order.append(current)
                visited.add(current)
                current = source_linking_map.get(current)
        
        # Add any sources not in the chain
        for source_name in assigned_distractors.keys():
            if source_name not in source_order:
                source_order.append(source_name)
        
        # Generate sources in order and update linked_source_ids as we go
        for source_name in source_order:
            distractor_list = assigned_distractors.get(source_name, [])
            if not distractor_list:
                continue
            
            if source_name == "slack":
                slack_channels, slack_messages = generate_slack(
                    all_canonical_slots=slots,
                    candidate_slots=candidate_slots,
                    participants=participants,
                    indirection_depth=indirection_depth,
                    min_required_source=min_required_source,
                    fragmentation_depth=fragmentation_depth,
                    generator_config=generator_config,
                    pattern_type="time",
                    assigned_distractors=distractor_list,
                    distractor_linked_sources=distractor_linked_sources
                )
                if slack_messages:
                    slack_path = output_dir / "slack.json"
                    with open(slack_path, 'w', encoding='utf-8') as f:
                        json.dump({"channels": slack_channels, "messages": slack_messages}, f, indent=2)
                    source_data["slack"] = slack_path
                    # Extract actual channel_id and update distractor_linked_sources
                    actual_id = extract_source_id("slack", (slack_channels, slack_messages))
                    update_linked_source_ids("slack", actual_id)
            elif source_name == "jira":
                jira_projects, jira_issues = generate_jira(
                    all_canonical_slots=slots,
                    candidate_slots=candidate_slots,
                    indirection_depth=indirection_depth,
                    fragmentation_depth=fragmentation_depth,
                    generator_config=generator_config,
                    assigned_distractors=distractor_list,
                    distractor_linked_sources=distractor_linked_sources
                )
                if jira_issues:
                    jira_path = output_dir / "jira.json"
                    with open(jira_path, 'w', encoding='utf-8') as f:
                        json.dump({"projects": jira_projects, "issues": jira_issues}, f, indent=2)
                    source_data["jira"] = jira_path
                    # Extract actual issue_key and update distractor_linked_sources
                    actual_id = extract_source_id("jira", (jira_projects, jira_issues))
                    update_linked_source_ids("jira", actual_id)
            elif source_name == "drive":
                drive_folders, drive_files = generate_drive(
                    all_canonical_slots=slots,
                    candidate_slots=candidate_slots,
                    indirection_depth=indirection_depth,
                    fragmentation_depth=fragmentation_depth,
                    generator_config=generator_config,
                    excluded_slots=set(),
                    assigned_distractors=distractor_list,
                    distractor_linked_sources=distractor_linked_sources
                )
                if drive_files:
                    drive_path = output_dir / "drive.json"
                    with open(drive_path, 'w', encoding='utf-8') as f:
                        json.dump({"folders": drive_folders, "files": drive_files}, f, indent=2)
                    source_data["drive"] = drive_path
                    # Extract actual file_id or file name and update distractor_linked_sources
                    actual_id = extract_source_id("drive", (drive_folders, drive_files))
                    update_linked_source_ids("drive", actual_id)
            elif source_name == "gmail":
                gmail_threads = generate_gmail(
                    all_canonical_slots=slots,
                    candidate_slots=candidate_slots,
                    participants=participants,
                    indirection_depth=indirection_depth,
                    fragmentation_depth=fragmentation_depth,
                    generator_config=generator_config,
                    excluded_slots=set(),
                    assigned_distractors=distractor_list,
                    distractor_linked_sources=distractor_linked_sources
                )
                if gmail_threads:
                    gmail_path = output_dir / "gmail.json"
                    with open(gmail_path, 'w', encoding='utf-8') as f:
                        json.dump({"threads": gmail_threads}, f, indent=2)
                    source_data["gmail"] = gmail_path
                    # Extract actual thread_id and update distractor_linked_sources
                    actual_id = extract_source_id("gmail", gmail_threads)
                    update_linked_source_ids("gmail", actual_id)
    
    elif indirection_depth >= 3:
        # ============================================================
        # indirection_depth>=3: 3+ sources combination needed
        # ============================================================
        # Each distractor gets a random linked_source (Option B)
        
        # Determine source generation order based on source_linking_map chain
        # Generate sources in chain order: A → B → C
        source_order = []
        if source_linking_map:
            # Find the source that is referenced but doesn't reference anyone (start of chain)
            referenced_sources = set(source_linking_map.values())
            referencing_sources = set(source_linking_map.keys())
            # Start with source that references another but is not referenced
            start_sources = referencing_sources - referenced_sources
            if start_sources:
                current = list(start_sources)[0]
            else:
                # Circular chain, start with first
                current = list(referencing_sources)[0] if referencing_sources else None
            
            # Build chain order
            visited = set()
            while current and current not in visited:
                source_order.append(current)
                visited.add(current)
                current = source_linking_map.get(current)
        
        # Add any sources not in the chain
        for source_name in assigned_distractors.keys():
            if source_name not in source_order:
                source_order.append(source_name)
        
        # Generate sources in order and update linked_source_ids as we go
        for source_name in source_order:
            distractor_list = assigned_distractors.get(source_name, [])
            if not distractor_list:
                continue
            
            if source_name == "slack":
                slack_channels, slack_messages = generate_slack(
                    all_canonical_slots=slots,
                    candidate_slots=candidate_slots,
                    participants=participants,
                    indirection_depth=indirection_depth,
                    min_required_source=min_required_source,
                    fragmentation_depth=fragmentation_depth,
                    generator_config=generator_config,
                    pattern_type="time",
                    assigned_distractors=distractor_list,
                    distractor_linked_sources=distractor_linked_sources
                )
                if slack_messages:
                    slack_path = output_dir / "slack.json"
                    with open(slack_path, 'w', encoding='utf-8') as f:
                        json.dump({"channels": slack_channels, "messages": slack_messages}, f, indent=2)
                    source_data["slack"] = slack_path
                    # Extract actual channel_id and update distractor_linked_sources
                    actual_id = extract_source_id("slack", (slack_channels, slack_messages))
                    update_linked_source_ids("slack", actual_id)
            elif source_name == "jira":
                jira_projects, jira_issues = generate_jira(
                    all_canonical_slots=slots,
                    candidate_slots=candidate_slots,
                    indirection_depth=indirection_depth,
                    fragmentation_depth=fragmentation_depth,
                    generator_config=generator_config,
                    assigned_distractors=distractor_list,
                    distractor_linked_sources=distractor_linked_sources
                )
                if jira_issues:
                    jira_path = output_dir / "jira.json"
                    with open(jira_path, 'w', encoding='utf-8') as f:
                        json.dump({"projects": jira_projects, "issues": jira_issues}, f, indent=2)
                    source_data["jira"] = jira_path
                    # Extract actual issue_key and update distractor_linked_sources
                    actual_id = extract_source_id("jira", (jira_projects, jira_issues))
                    update_linked_source_ids("jira", actual_id)
            elif source_name == "drive":
                drive_folders, drive_files = generate_drive(
                    all_canonical_slots=slots,
                    candidate_slots=candidate_slots,
                    indirection_depth=indirection_depth,
                    fragmentation_depth=fragmentation_depth,
                    generator_config=generator_config,
                    excluded_slots=set(),
                    assigned_distractors=distractor_list,
                    distractor_linked_sources=distractor_linked_sources
                )
                if drive_files:
                    drive_path = output_dir / "drive.json"
                    with open(drive_path, 'w', encoding='utf-8') as f:
                        json.dump({"folders": drive_folders, "files": drive_files}, f, indent=2)
                    source_data["drive"] = drive_path
                    # Extract actual file_id or file name and update distractor_linked_sources
                    actual_id = extract_source_id("drive", (drive_folders, drive_files))
                    update_linked_source_ids("drive", actual_id)
            elif source_name == "gmail":
                gmail_threads = generate_gmail(
                    all_canonical_slots=slots,
                    candidate_slots=candidate_slots,
                    participants=participants,
                    indirection_depth=indirection_depth,
                    fragmentation_depth=fragmentation_depth,
                    generator_config=generator_config,
                    excluded_slots=set(),
                    assigned_distractors=distractor_list,
                    distractor_linked_sources=distractor_linked_sources
                )
                if gmail_threads:
                    gmail_path = output_dir / "gmail.json"
                    with open(gmail_path, 'w', encoding='utf-8') as f:
                        json.dump({"threads": gmail_threads}, f, indent=2)
                    source_data["gmail"] = gmail_path
                    # Extract actual thread_id and update distractor_linked_sources
                    actual_id = extract_source_id("gmail", gmail_threads)
                    update_linked_source_ids("gmail", actual_id)
    
    return source_data
