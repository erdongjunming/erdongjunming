from typing import Literal, TypedDict, TypeAlias

Operation: TypeAlias = Literal["SET", "ADD", "COPY", "SWAP"]
ErrorCode: TypeAlias = Literal[
    "malformed_action", "invalid_argument", "action_forbidden", "state_conflict",
    "idempotency_conflict", "budget_exhausted", "unknown_run", "unknown_branch",
    "unknown_snapshot", "run_exists", "run_closed", "branch_exists", "branch_limit", "snapshot_limit",
    "storage_error", "schema_mismatch", "provider_timeout", "provider_rate_limited",
    "provider_auth", "provider_unavailable", "provider_protocol", "prediction_unavailable",
    "audit_failed", "cancelled", "internal_error",
]
BudgetKind: TypeAlias = Literal["decision_calls", "proposal_count", "exact_queries", "model_queries"]
JsonValue: TypeAlias = None | bool | int | float | str | list["JsonValue"] | dict[str, "JsonValue"]

class ErrorInfo(TypedDict):
    code: ErrorCode
    message: str

class State(TypedDict):
    env_version: Literal["reg4/1.0.0"]
    registers: list[int]

class SetAction(TypedDict):
    op: Literal["SET"]
    index: int
    value: int

class AddAction(TypedDict):
    op: Literal["ADD"]
    index: int
    delta: int

class CopyAction(TypedDict):
    op: Literal["COPY"]
    source: int
    target: int

class SwapAction(TypedDict):
    op: Literal["SWAP"]
    left: int
    right: int

Action: TypeAlias = SetAction | AddAction | CopyAction | SwapAction

class Observation(TypedDict):
    branch_id: str
    revision: int
    state_id: str
    state: State

class Target(TypedDict):
    index: int
    value: int

class Goal(TypedDict):
    targets: list[Target]
    preserve: list[int]

class Task(TypedDict):
    schema_version: Literal["1.0.0"]
    task_id: str
    family: Literal["set", "add", "copy", "swap", "combined", "restricted"]
    initial: State
    goal: Goal
    allowed_ops: list[Operation]
    max_attempts: int
    max_decisions: int
    max_proposals: int
    max_plan_evaluations: int
    seed: int

class TransitionResult(TypedDict):
    before: State
    after: State
    accepted: bool
    error: ErrorInfo | None

class Command(TypedDict):
    schema_version: Literal["1.0.0"]
    run_id: str
    command_id: str
    branch_id: str
    expected_revision: int
    action: dict[str, JsonValue]

class StepReceipt(TypedDict):
    schema_version: Literal["1.0.0"]
    run_id: str
    command_id: str
    disposition: Literal["applied", "invalid", "rejected"]
    attempt_index: int | None
    before: Observation
    after: Observation
    error: ErrorInfo | None

class Snapshot(TypedDict):
    schema_version: Literal["1.0.0"]
    snapshot_id: str
    run_id: str
    observation: Observation

class Violation(TypedDict):
    code: Literal["target_mismatch", "preserve_violation"]
    index: int
    expected: int
    actual: int

class VerificationResult(TypedDict):
    schema_version: Literal["1.0.0"]
    task_id: str
    state_id: str
    success: bool
    violations: list[Violation]

class AuditResult(TypedDict):
    valid: bool
    violations: list[str]

class BudgetUsage(TypedDict):
    action_attempts: int
    decision_calls: int
    proposal_count: int
    exact_queries: int
    model_queries: int

class BudgetRemaining(TypedDict):
    attempts: int
    decisions: int
    proposals: int
    plan_evaluations: int

class BudgetEvent(TypedDict):
    event_seq: int
    kind: Literal["action_attempts", "decision_calls", "proposal_count", "exact_queries", "model_queries"]
    count: int

class Candidate(TypedDict):
    candidate_id: str
    actions: list[Action]
    source: Literal["random", "heuristic", "exact_search", "llm", "world_model"]
    prediction_kind: Literal["none", "exact", "learned"]
    predicted_states: list[State] | None
    confidence: float | None

class DecisionRequest(TypedDict):
    schema_version: Literal["1.0.0"]
    request_id: str
    task: Task
    observation: Observation
    budget: BudgetRemaining
    history: list[StepReceipt]

class Decision(TypedDict):
    schema_version: Literal["1.0.0"]
    request_id: str
    status: Literal["candidates", "stop", "error"]
    candidates: list[Candidate]
    error: ErrorInfo | None

class Prediction(TypedDict):
    schema_version: Literal["1.0.0"]
    model_id: str
    model_version: str
    env_version: Literal["reg4/1.0.0"]
    state_id: str
    action: Action
    status: Literal["predicted", "abstain"]
    next_state: State | None
    confidence: float | None
    error: ErrorInfo | None

class ProviderUsage(TypedDict):
    provider_calls: int
    input_tokens: int | None
    output_tokens: int | None
    provider_ms: float
    cost_amount: float | None
    cost_currency: Literal["USD", "CNY"] | None

class RunConfig(TypedDict):
    run_id: str
    task: Task
    planner_name: str
    run_timeout_ms: int
    provider_timeout_ms: int
    max_provider_calls: int
    max_api_cost: float | None
    cost_currency: Literal["USD", "CNY"] | None

class Metrics(TypedDict):
    action_attempts: int
    applied_actions: int
    invalid_actions: int
    decision_calls: int
    proposal_count: int
    exact_queries: int
    model_queries: int
    cache_hits: int
    provider_calls: int
    input_tokens: int | None
    output_tokens: int | None
    wall_ms: float
    provider_ms: float
    cost_amount: float | None
    cost_currency: Literal["USD", "CNY"] | None

class Provenance(TypedDict):
    git_commit: str
    contract_digest: str
    task_set_digest: str
    env_version: Literal["reg4/1.0.0"]
    seed: int
    provider: str | None
    model: str | None
    config_digest: str

class RunSummary(TypedDict):
    schema_version: Literal["1.0.0"]
    run_id: str
    task_id: str
    status: Literal["success", "failed", "exhausted", "provider_error", "cancelled", "audit_failed"]
    final_observation: Observation
    final_verification: VerificationResult
    metrics: Metrics
    provenance: Provenance

class BranchRecord(TypedDict):
    branch_id: str
    parent_snapshot_id: str | None
    latest: Observation

class ControlEvent(TypedDict):
    event_seq: int
    kind: Literal["snapshot_created", "branch_created", "branch_selected", "decision_recorded", "provider_usage", "run_finished", "run_cancelled"]
    payload: dict[str, JsonValue]

class RunExport(TypedDict):
    schema_version: Literal["1.0.0"]
    run_id: str
    task: Task
    initial_branch_id: str
    branches: list[BranchRecord]
    snapshots: list[Snapshot]
    commands: list[Command]
    receipts: list[StepReceipt]
    budget: BudgetUsage
    budget_events: list[BudgetEvent]
    control_events: list[ControlEvent]
    final_summary: RunSummary | None
