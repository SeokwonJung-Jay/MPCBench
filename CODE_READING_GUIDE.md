# 코드 파악 가이드 (Code Reading Guide)

## 📚 전체 구조 파악 순서

### 1단계: 진입점과 전체 흐름 이해
**파일**: `data_gen.py`의 `generate_source_data()` → `generate_planning_source_data()`

**이해 포인트:**
- Task JSON을 받아서 여러 소스 데이터(calendar, slack, jira 등)를 생성하는 전체 흐름
- Planning task의 경우 `generate_planning_source_data()`가 핵심 함수

### 2단계: 핵심 개념 이해
**핵심 함수들:**
1. `assign_distractors_to_sources()` - Distractor 할당 전략
2. `generate_calendar_events()` - Calendar 데이터 생성
3. `generate_slack_messages()` - Slack 데이터 생성 (fragmentation_depth, indirection_depth 적용 예시)
4. `generate_jira_issues()` - Jira 데이터 생성
5. `generate_drive_files()` - Drive 데이터 생성
6. `generate_gmail_threads()` - Gmail 데이터 생성

**핵심 개념:**
- **canonical_slot**: 정답이 되는 시간 슬롯
- **distractor**: 정답이 아닌 시간 슬롯 (제거해야 함)
- **fragmentation_depth**: 한 소스 내에서 데이터를 몇 개로 분산할지
- **indirection_depth**: 몇 개의 소스를 조합해야 하는지
- **min_required_source**: 필요한 최소 소스 개수 (calendar 포함)

### 3단계: 데이터 생성 로직 상세 이해

#### 3-1. Calendar 생성 (`generate_calendar_events`)
- **목적**: 모든 참가자가 비어있는 시간 슬롯 생성
- **생성 내용**: canonical_slot + distractor slots
- **핵심**: `indirection_depth=1`이면 canonical만, 아니면 여러 distractor도 생성

#### 3-2. Distractor 할당 (`assign_distractors_to_sources`)
- **목적**: 각 소스에 distractor 1개씩 할당
- **로직**: 
  - `indirection_depth`에 따라 사용 가능한 소스 결정
  - `min_required_source - 1`만큼 소스를 랜덤 선택
  - 각 소스에 distractor 1개씩 할당

#### 3-3. 각 소스별 데이터 생성
각 소스 생성 함수는 다음 패턴을 따름:

**Step 1: fragmentation_depth 적용**
- `fragmentation_depth`만큼의 데이터 생성
- 각 데이터는 단독으로는 불완전 (조합 필요)
- 예: 메시지1(힌트) + 메시지2(제약) = 완전한 의미

**Step 2: indirection_depth 적용**
- 다른 소스 참조 추가
- 각 소스가 단독으로는 불완전하도록
- 예: Slack 메시지에 "Jira의 API-121 이슈 참조" 추가

### 4단계: 소스 간 연계 로직 (`generate_planning_source_data`)
- `assigned_distractors`를 기반으로 각 소스 생성
- `indirection_depth`에 따라 소스 간 `linked_source` 설정
- 각 소스 생성 함수에 `assigned_distractor`, `linked_source` 전달

## 🔍 코드 읽기 팁

1. **함수 시그니처 먼저 보기**: 파라미터와 반환값으로 역할 파악
2. **주석의 "Step 1", "Step 2" 확인**: fragmentation_depth → indirection_depth 순서
3. **예시 메시지 확인**: 주석의 예시가 실제 생성 로직과 일치
4. **조건문 분기 확인**: `indirection_depth` 값에 따른 분기 처리

## 📝 주요 함수별 역할

### Data Generation (`data_gen.py`)

| 함수 | 역할 | 핵심 파라미터 |
|------|------|--------------|
| `assign_distractors_to_sources` | Distractor를 소스에 할당 | `indirection_depth`, `min_required_source` |
| `generate_calendar_events` | Calendar 데이터 생성 | `fragmentation_depth`, `min_required_source` |
| `generate_slack_messages` | Slack 메시지 생성 | `assigned_distractor`, `fragmentation_depth`, `indirection_depth`, `linked_source` |
| `generate_jira_issues` | Jira 이슈 생성 | 동일 |
| `generate_drive_files` | Drive 파일 생성 | 동일 |
| `generate_gmail_threads` | Gmail 스레드 생성 | 동일 |
| `generate_planning_source_data` | 전체 orchestration | Task 전체 정보 |

### Agent Execution (`agent_runner.py`)

| 함수 | 역할 | 핵심 파라미터 |
|------|------|--------------|
| `build_tool_schemas` | OpenAI function calling 형식의 tool 정의 생성 | `backend`, `tool_context_mode` |
| `execute_tool_call` | Tool 호출 실행 | `backend`, `tool_name`, `arguments` |
| `run_task` | LLM Agent가 task를 해결하는 메인 함수 | `task`, `source_data`, `agent_model`, `tool_context_mode` |

### Evaluation (`evaluate.py`)

| 함수 | 역할 | 핵심 파라미터 |
|------|------|--------------|
| `score_planning_answer` | Agent 답변을 점수화 | `task`, `agent_answer_text` |
| `evaluate_task` | 단일 task 평가 | `task`, `agent_model`, `generate_data`, `tool_context_mode` |
| `evaluate_all_tasks` | 모든 task 평가 (orchestration) | `agent_models`, `generate_data`, `tool_context_modes` |

## 🔄 전체 파이프라인 흐름

### 1. Data Generation (`data_gen.py`)
```
Task JSON
  ↓
generate_planning_source_data()
  ↓
1. Participants 생성
2. Calendar 생성 (canonical + distractor slots)
3. Distractor 할당 (각 소스에 1개씩)
4. 각 소스 데이터 생성 (slack, jira, drive, gmail)
  ↓
Source Data JSON files
```

### 2. Agent Execution (`agent_runner.py`)
```
Task + Source Data
  ↓
run_task()
  ↓
1. ToolBackend 초기화
2. Tool schemas 빌드
3. Agent loop:
   - LLM API 호출
   - Tool call 있으면 실행 → 결과 전달
   - Tool call 없으면 final answer 파싱
  ↓
Agent Result (final_answer, rationale, tool_calls)
```

### 3. Evaluation (`evaluate.py`)
```
Task + Agent Result
  ↓
evaluate_task()
  ↓
1. Source data 생성/로드
2. Data consistency 검증
3. Agent 실행 (run_task 호출)
4. 답변 점수화 (score_planning_answer)
  ↓
Evaluation Result (scores, agent_result, ...)
```

