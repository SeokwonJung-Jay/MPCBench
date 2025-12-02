"""Evaluation runner for MPCBench v2.

Runs evaluation over many tasks, computes scores, and writes logs.
"""

from typing import Dict, Any, List
from pathlib import Path
import json

from config import LOGS_DIR, MODEL_CONFIG_PATH
from task_defs import load_all_tasks, Task, get_planning_meeting_slots
from data_gen import generate_source_data
from agent_runner import run_task
from oracle_validator import validate_data_consistency


def score_planning_answer(task: Task, agent_answer_text: str) -> float:
    """
    [핵심 함수] Planning task의 agent 답변을 점수화하는 함수
    
    목적: Agent가 제시한 시간 슬롯이 canonical answer와 얼마나 일치하는지 평가
    
    점수 계산 방식:
        1. Perfect match (1.0): 모든 canonical slot 포함 + extra slot 없음
        2. Partial match: 일부 canonical slot 포함 → 비율 계산
        3. Penalty: extra slot이 있으면 점수 감점 (최대 50% 감점)
        4. 최종 점수 = (matched_canonical / total_canonical) * (1.0 - penalty * 0.5)
    
    예시:
        canonical: [(2025-12-02, 14:00-14:45), (2025-12-03, 13:00-13:45)]
        agent: [(2025-12-02, 14:00-14:45), (2025-12-03, 13:00-13:45), (2025-12-02, 15:00-15:45)]
        → matched=2, extra=1 → base_score=1.0, penalty=1/3 → score=1.0*(1-0.33*0.5)=0.835
    
    Args:
        task: Task 정의 (canonical_answer 포함)
        agent_answer_text: Agent가 생성한 답변 텍스트
        
    Returns:
        0.0 ~ 1.0 사이의 점수
    """
    # Planning task가 아니면 점수 0
    if task.category != "planning":
        return 0.0
    
    # Canonical slots 추출 (정답 슬롯)
    slots = get_planning_meeting_slots(task)
    if not slots:
        return 0.0
    
    # ============================================================
    # Step 1: Agent 답변에서 날짜-시간 쌍 추출
    # ============================================================
    # Agent가 다양한 형식으로 날짜/시간을 표현할 수 있으므로
    # 여러 패턴으로 추출하고 정규화
    
    answer_lower = agent_answer_text.lower()
    import re
    
    # 날짜 패턴들 (다양한 형식 지원)
    date_patterns = [
        r'(\d{4}-\d{2}-\d{2})',  # 2025-12-02
        r'((?:january|february|...)\s+\d{1,2},?\s+\d{4})',  # December 2, 2025
        r'((?:jan|feb|...)\s+\d{1,2},?\s+\d{4})',  # Dec 2, 2025
        r'(\d{1,2}[/-]\d{1,2}[/-]\d{4})',  # 12/02/2025
    ]
    
    # 시간 패턴 (시작-종료 시간 범위)
    time_patterns = [
        r'(\d{1,2}:\d{2}\s*[-–—to]+\s*\d{1,2}:\d{2})',  # 14:00 - 14:45
    ]
    
    # 답변에서 모든 날짜와 시간 추출
    found_dates = []
    found_times = []
    
    for pattern in date_patterns:
        for match in re.finditer(pattern, answer_lower):
            found_dates.append((match.start(), match.group(1)))  # (위치, 날짜 문자열)
    
    for pattern in time_patterns:
        for match in re.finditer(pattern, answer_lower):
            found_times.append((match.start(), match.group(1)))  # (위치, 시간 문자열)
    
    # 날짜와 시간을 쌍으로 매칭
    # 각 날짜 뒤에 나오는 시간들을 해당 날짜와 매칭
    date_time_pairs = []
    for i, (date_pos, date_str) in enumerate(found_dates):
        # 다음 날짜까지의 범위
        next_date_pos = found_dates[i+1][0] if i+1 < len(found_dates) else len(answer_lower)
        # 이 범위 내의 시간들을 모두 매칭
        for time_pos, time_str in found_times:
            if date_pos < time_pos < next_date_pos:
                date_time_pairs.append((date_str, time_str))
    
    # 구조화된 쌍이 없으면 모든 날짜-시간 조합 시도 (덜 엄격한 매칭)
    if not date_time_pairs and found_dates and found_times:
        for date_str, _ in found_dates:
            for _, time_str in found_times:
                date_time_pairs.append((date_str, time_str))
    
    # ============================================================
    # Step 2: 날짜/시간 형식 정규화
    # ============================================================
    # 다양한 형식의 날짜/시간을 canonical 형식(YYYY-MM-DD, HH:MM-HH:MM)으로 변환
    
    def normalize_date(date_str):
        """다양한 날짜 형식을 YYYY-MM-DD로 변환"""
        import datetime
        formats = [
            "%Y-%m-%d",  # 2025-12-02
            "%B %d, %Y",  # December 2, 2025
            "%b %d, %Y",  # Dec 2, 2025
            "%m/%d/%Y",  # 12/02/2025
            "%d/%m/%Y",  # 02/12/2025
            "%m-%d-%Y",  # 12-02-2025
        ]
        for fmt in formats:
            try:
                dt = datetime.datetime.strptime(date_str, fmt)
                return dt.strftime("%Y-%m-%d")
            except:
                continue
        return None
    
    def normalize_time(time_str):
        """다양한 시간 형식을 HH:MM-HH:MM로 변환"""
        time_str_clean = re.sub(r'\s+', '', time_str.lower())
        # 시작-종료 시간 모두 추출
        times = re.findall(r'(\d{1,2}):(\d{2})', time_str_clean)
        if len(times) >= 2:
            start_h, start_m = times[0]
            end_h, end_m = times[1]
            return f"{int(start_h):02d}:{start_m}-{int(end_h):02d}:{end_m}"
        return None
    
    # Agent가 언급한 슬롯들을 정규화하여 집합으로 변환
    agent_slots = set()
    for date_str, time_str in date_time_pairs:
        norm_date = normalize_date(date_str)
        norm_time = normalize_time(time_str)
        if norm_date and norm_time:
            agent_slots.add((norm_date, norm_time))
    
    # Canonical slots도 같은 형식으로 변환
    canonical_slots = {(slot["date"], slot["slot"]) for slot in slots}
    
    # ============================================================
    # Step 3: 점수 계산
    # ============================================================
    matched_canonical = len(agent_slots & canonical_slots)  # 일치하는 canonical slot 개수
    extra_slots = len(agent_slots - canonical_slots)  # Agent가 추가로 제시한 슬롯 개수
    missing_canonical = len(canonical_slots - agent_slots)  # 누락된 canonical slot 개수
    
    # Perfect match: 모든 canonical 포함 + extra 없음
    if matched_canonical == len(canonical_slots) and extra_slots == 0:
        return 1.0
    
    # Partial match: 일부만 일치하거나 extra가 있는 경우
    if extra_slots > 0 or missing_canonical > 0:
        # Base score: 일치한 canonical 비율
        base_score = matched_canonical / len(canonical_slots) if len(canonical_slots) > 0 else 0.0
        # Penalty: extra slot 비율 (최대 50% 감점)
        penalty = min(extra_slots / max(len(agent_slots), 1), 1.0)
        return max(0.0, base_score * (1.0 - penalty * 0.5))
    
    return 0.0


def evaluate_task(
    task: Task,
    agent_model: str = "gpt-4o-mini",
    generate_data: bool = True,
    tool_context_mode: str = "detailed"
) -> Dict[str, Any]:
    """
    [핵심 함수] 단일 task를 평가하는 함수
    
    전체 흐름:
        1. Source data 생성 또는 로드
        2. Data consistency 검증
        3. Agent 실행 (LLM이 tool을 사용하여 답변 생성)
        4. 답변 점수화
        5. 결과 저장
    
    Args:
        task: 평가할 task 정의
        agent_model: 사용할 LLM 모델 이름
        generate_data: 데이터가 없으면 생성할지 여부
        tool_context_mode: "minimal" 또는 "detailed" (tool 설명의 상세도)
        
    Returns:
        평가 결과 딕셔너리:
        {
            "task_id": ...,
            "agent_model": ...,
            "agent_result": {...},  # final_answer, rationale, tool_calls
            "scores": {
                "answer_requirements_satisfaction": 0.0~1.0
            },
            ...
        }
    """
    # ============================================================
    # Step 1: Source data 생성 또는 로드
    # ============================================================
    task_data_dir = LOGS_DIR / task.id / "data"
    if generate_data:
        # 데이터 생성 (data_gen.py의 generate_source_data 호출)
        source_data = generate_source_data(task, task_data_dir)
    else:
        # 기존 데이터 로드
        source_data = {}
        source_files = {
            "calendar": task_data_dir / "calendar.json",
            "contacts": task_data_dir / "contacts.json",
            "slack": task_data_dir / "slack.json",
            "jira": task_data_dir / "jira.json",
            "drive": task_data_dir / "drive.json",
            "gmail": task_data_dir / "gmail.json"
        }
        for source_name, file_path in source_files.items():
            if file_path.exists():
                source_data[source_name] = file_path

    # ============================================================
    # Step 2: Data consistency 검증
    # ============================================================
    # 생성된 데이터가 task의 canonical answer와 일관성 있는지 검증
    validation_errors = validate_data_consistency(task, source_data)
    
    # ============================================================
    # Step 3: Agent 실행
    # ============================================================
    # LLM이 tool을 사용하여 task를 해결하고 답변 생성
    run_log_path = LOGS_DIR / task.id / f"agent-{agent_model}_{tool_context_mode}_run.json"
    agent_result = run_task(task, source_data, agent_model, run_log_path, tool_context_mode=tool_context_mode)

    # ============================================================
    # Step 4: 답변 점수화
    # ============================================================
    agent_answer_text = agent_result.get("final_answer", "")
    
    if validation_errors:
        # 검증 실패 시 점수 0
        answer_score = 0.0
    else:
        # Task 카테고리별 점수 계산
        if task.is_planning():
            answer_score = score_planning_answer(task, agent_answer_text)
        else:
            answer_score = 0.0  # TODO: 다른 카테고리 구현 필요

    result = {
        "task_id": task.id,
        "agent_model": agent_model,
        "task_category": task.category,
        "metadata": task.metadata,
        "canonical_answer": task.canonical_answer,
        "agent_result": agent_result,
        "validation_errors": validation_errors,
        "scores": {
            "answer_requirements_satisfaction": answer_score
        }
    }

    # Save evaluation result
    eval_log_path = LOGS_DIR / task.id / f"agent-{agent_model}_{tool_context_mode}_eval.json"
    eval_log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(eval_log_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2)

    return result


def evaluate_all_tasks(
    agent_models: List[str] = None,
    generate_data: bool = True,
    tool_context_modes: List[str] = None
) -> Dict[str, Any]:
    """
    [메인 함수] 모든 task를 평가하는 orchestration 함수
    
    전체 흐름:
        - 모든 task × 모든 agent model × 모든 tool_context_mode 조합 평가
        - 각 조합에 대해 evaluate_task() 호출
        - 진행 상황 출력
    
    Args:
        agent_models: 평가할 모델 리스트 (None이면 model_config.json에서 로드)
        generate_data: 데이터가 없으면 생성할지 여부
        tool_context_modes: 평가할 tool context mode 리스트 (None이면 ["minimal", "detailed"])
        
    Returns:
        모든 task-model-mode 조합의 평가 결과 딕셔너리
        key: "{task_id}__{model}__{mode}"
    """
    if agent_models is None:
        # Load from model_config.json
        try:
            with open(MODEL_CONFIG_PATH, 'r', encoding='utf-8') as f:
                model_config = json.load(f)
                agent_models = model_config.get("agent_models", ["gpt-4o-mini"])
        except Exception:
            agent_models = ["gpt-4o-mini"]

    if tool_context_modes is None:
        tool_context_modes = ["minimal", "detailed"]
    
    tasks = load_all_tasks()
    results = {}
    
    total_combinations = len(tasks) * len(agent_models) * len(tool_context_modes)
    current = 0

    for task_idx, task in enumerate(tasks, 1):
        for model in agent_models:
            for mode in tool_context_modes:
                current += 1
                key = f"{task.id}__{model}__{mode}"
                print(f"[{mode}] Task {task_idx}/{len(tasks)} ({model}): {task.id}...", end=" ", flush=True)
                try:
                    results[key] = evaluate_task(task, model, generate_data, tool_context_mode=mode)
                    print(f"✓")
                except Exception as e:
                    print(f"⚠️  Error: {e}")
                    # Skip this mode and continue with next
                    continue

    return results
