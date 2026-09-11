from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


def to_camel(value: str) -> str:
    head, *tail = value.split("_")
    return head + "".join(part.capitalize() for part in tail)


class ApiModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, from_attributes=True)


class UserRole(str, Enum):
    elder = "elder"
    family = "family"
    admin = "admin"
    professional = "professional"
    device_operator = "device_operator"


class RiskLevel(str, Enum):
    green = "green"
    yellow = "yellow"
    orange = "orange"
    red = "red"


class RiskStatus(str, Enum):
    new = "new"
    assigned = "assigned"
    reviewing = "reviewing"
    action_required = "action_required"
    escalated = "escalated"
    resolved = "resolved"
    false_positive = "false_positive"
    closed = "closed"


class RiskActionType(str, Enum):
    claim = "claim"
    begin_review = "begin_review"
    request_action = "request_action"
    escalate = "escalate"
    resolve = "resolve"
    mark_false_positive = "mark_false_positive"
    close = "close"
    reopen = "reopen"


class DemoLoginRequest(ApiModel):
    actor_id: str = Field(min_length=1, max_length=64)


class ActorOut(ApiModel):
    id: str
    display_name: str
    role: UserRole


class TokenOut(ApiModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime
    actor: ActorOut


class LoginRequest(ApiModel):
    login_identifier: str = Field(min_length=3, max_length=120)
    password: str = Field(min_length=10, max_length=128)


class RegistrationApplicationCreate(ApiModel):
    display_name: str = Field(min_length=2, max_length=100)
    login_identifier: str = Field(min_length=3, max_length=120)
    relationship: str = Field(min_length=1, max_length=80)
    elder_name: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=10, max_length=128)
    consent_version: str = Field(min_length=1, max_length=32)


class RegistrationStatus(str, Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class RegistrationApplicationOut(ApiModel):
    id: str
    display_name: str
    login_identifier: str
    relationship: str
    elder_name: str
    consent_version: str
    status: RegistrationStatus
    review_note: Optional[str]
    reviewed_at: Optional[datetime]
    created_at: datetime


class RegistrationApplicationListOut(ApiModel):
    items: list[RegistrationApplicationOut]
    total: int


class AuthorizationScope(str, Enum):
    daily_summary = "daily_summary"
    care_actions = "care_actions"


class RegistrationReviewRequest(ApiModel):
    decision: RegistrationStatus
    elder_id: Optional[str] = Field(default=None, max_length=64)
    scopes: list[AuthorizationScope] = Field(default_factory=lambda: [AuthorizationScope.daily_summary, AuthorizationScope.care_actions])
    note: Optional[str] = Field(default=None, max_length=500)


class GrantActionType(str, Enum):
    update_scopes = "update_scopes"
    revoke = "revoke"
    reactivate = "reactivate"


class ElderAccountOut(ApiModel):
    id: str
    display_name: str
    age: int


class ElderAccountListOut(ApiModel):
    items: list[ElderAccountOut]


class FamilyGrantOut(ApiModel):
    family_id: str
    family_name: str
    elder_id: str
    elder_name: str
    relationship: Optional[str]
    consent_version: Optional[str]
    scopes: list[AuthorizationScope]
    is_active: bool
    version: int
    created_at: datetime
    updated_at: datetime
    revoked_at: Optional[datetime]


class FamilyGrantListOut(ApiModel):
    items: list[FamilyGrantOut]
    total: int


class GrantActionRequest(ApiModel):
    action: GrantActionType
    expected_version: int = Field(ge=1)
    scopes: Optional[list[AuthorizationScope]] = None
    note: Optional[str] = Field(default=None, max_length=500)


class PasswordChangeRequest(ApiModel):
    current_password: str = Field(min_length=10, max_length=128)
    new_password: str = Field(min_length=10, max_length=128)


class PasswordRecoveryRequest(ApiModel):
    login_identifier: str = Field(min_length=3, max_length=120)


class PasswordRecoveryConfirm(ApiModel):
    token: str = Field(min_length=32, max_length=256)
    new_password: str = Field(min_length=10, max_length=128)


class MessageOut(ApiModel):
    message: str


class ConversationSessionCreate(ApiModel):
    save_messages: bool = False
    allow_analysis: bool = False


class ConversationSessionOut(ApiModel):
    id: str
    elder_id: str
    save_messages: bool
    allow_analysis: bool
    created_at: datetime
    last_active_at: datetime


class ConversationMessageOut(ApiModel):
    role: str
    content: str
    processing: Optional[str]
    model: Optional[str]
    created_at: datetime


class RiskListItem(ApiModel):
    id: str
    elder_id: str
    elder_name: str
    level: RiskLevel
    status: RiskStatus
    title: str
    assignee_id: Optional[str]
    sla_due_at: Optional[datetime]
    version: int
    created_at: datetime
    updated_at: datetime


class RiskListOut(ApiModel):
    items: list[RiskListItem]
    page: int
    per_page: int
    total: int


class RiskEvidenceOut(ApiModel):
    id: str
    source_type: str
    label: str
    detail: str
    evidence_ref: str
    recorded_at: datetime


class RiskActionOut(ApiModel):
    id: str
    request_id: str
    actor_id: str
    action: RiskActionType
    note: Optional[str]
    from_status: RiskStatus
    to_status: RiskStatus
    event_version: int
    created_at: datetime


class RiskDetailOut(RiskListItem):
    summary: str
    model_version: Optional[str]
    rule_version: str
    evidence: list[RiskEvidenceOut]
    actions: list[RiskActionOut]


class RiskActionRequest(ApiModel):
    request_id: str = Field(min_length=8, max_length=100)
    action: RiskActionType
    note: Optional[str] = Field(default=None, max_length=2000)
    expected_version: int = Field(ge=1)


class RiskActionResult(ApiModel):
    event: RiskDetailOut
    action: RiskActionOut
    duplicate: bool = False


class FamilyElderOut(ApiModel):
    id: str
    name: str
    age: int
    authorization_status: str = "active"


class FamilyElderListOut(ApiModel):
    items: list[FamilyElderOut]


class FamilyStatusOut(ApiModel):
    level: RiskLevel
    label: str
    headline: str
    summary: str
    score: int
    baseline_delta: int


class FamilyTopicOut(ApiModel):
    name: str
    note: str
    tone: str


class FamilySafetyOut(ApiModel):
    has_active_emergency: bool
    message: str


class FamilyTodayOut(ApiModel):
    elder: FamilyElderOut
    status: FamilyStatusOut
    topics: list[FamilyTopicOut]
    safety: FamilySafetyOut
    risk_event_id: Optional[str]


class FamilyActionType(str, Enum):
    contacted = "contacted"
    video_planned = "video_planned"
    referral_requested = "referral_requested"


class FamilyActionRequest(ApiModel):
    request_id: str = Field(min_length=8, max_length=100)
    action: FamilyActionType


class FamilyActionResult(ApiModel):
    status: str = "recorded"
    action: FamilyActionType
    recorded_at: datetime
    duplicate: bool = False


class EmergencySource(str, Enum):
    elder_button = "elder_button"
    device_button = "device_button"


class EmergencyStatus(str, Enum):
    open = "open"
    acknowledged = "acknowledged"
    resolved = "resolved"
    cancelled = "cancelled"


class EmergencyActionType(str, Enum):
    acknowledge = "acknowledge"
    resolve = "resolve"
    cancel = "cancel"
    reopen = "reopen"


class EmergencyCreateRequest(ApiModel):
    request_id: str = Field(min_length=8, max_length=100)
    elder_id: Optional[str] = Field(default=None, max_length=64)
    source: EmergencySource
    note: Optional[str] = Field(default=None, max_length=500)


class EmergencyEventOut(ApiModel):
    id: str
    elder_id: str
    elder_name: str
    trigger_actor_id: str
    source: EmergencySource
    status: EmergencyStatus
    note: Optional[str]
    acknowledged_by: Optional[str]
    acknowledged_at: Optional[datetime]
    resolved_by: Optional[str]
    resolved_at: Optional[datetime]
    version: int
    created_at: datetime
    updated_at: datetime


class EmergencyCreateResult(ApiModel):
    event: EmergencyEventOut
    duplicate: bool = False


class EmergencyListOut(ApiModel):
    items: list[EmergencyEventOut]
    page: int
    per_page: int
    total: int


class EmergencyActionRequest(ApiModel):
    request_id: str = Field(min_length=8, max_length=100)
    action: EmergencyActionType
    expected_version: int = Field(ge=1)
    note: Optional[str] = Field(default=None, max_length=1000)


class EmergencyActionOut(ApiModel):
    id: str
    request_id: str
    actor_id: str
    action: EmergencyActionType
    note: Optional[str]
    from_status: EmergencyStatus
    to_status: EmergencyStatus
    event_version: int
    created_at: datetime


class EmergencyActionResult(ApiModel):
    event: EmergencyEventOut
    action: EmergencyActionOut
    duplicate: bool = False


class AuditLogOut(ApiModel):
    id: str
    actor_id: str
    actor_display_name: Optional[str] = None
    action: str
    target_type: str
    target_id: str
    metadata: dict[str, object]
    created_at: datetime


class AuditListOut(ApiModel):
    items: list[AuditLogOut]
    page: int
    per_page: int
    total: int


class HealthOut(ApiModel):
    status: str
    service: str
