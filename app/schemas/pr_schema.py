from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from app.core.enums import PRStatus, LLMProvider

class PRSummaryRequest(BaseModel):
    pr_id: int
    force_refresh: bool = False

class PRItem(BaseModel):
    id: int
    number: int
    title: str
    author: str
    author_avatar: Optional[str] = None
    created_at: str
    updated_at: Optional[str] = None
    state: PRStatus = PRStatus.OPEN
    html_url: str
    head_branch: str
    base_branch: str
    diff_url: Optional[str] = None
    summary: Optional[str] = None
    summary_provider: Optional[LLMProvider] = None
    summary_timestamp: Optional[str] = None
    impact_score: Optional[float] = None
    is_overdue: bool = False
    overdue_days: int = 0

class PRListResponse(BaseModel):
    repository: str
    total_prs: int
    prs: List[PRItem]
    message: str
    stale_threshold_days: int = 5

class EngineerImpactStat(BaseModel):
    rank: int
    author: str
    author_avatar: Optional[str] = None
    total_prs: int
    avg_impact_score: float
    total_impact_points: float
    highest_impact_score: float
    tier: str

class DashboardLeaderboardResponse(BaseModel):
    timeframe_days: int
    timeframe_label: str
    total_prs: int
    total_engineers: int
    stale_threshold_days: int = 5
    leaderboard: List[EngineerImpactStat]
    overdue_prs: List[PRItem] = Field(default_factory=list)

class CircuitBreakerStatus(BaseModel):
    state: str
    cooldown_seconds: int
    seconds_remaining: float
    last_failure_time: Optional[float] = None
    active_provider: str

