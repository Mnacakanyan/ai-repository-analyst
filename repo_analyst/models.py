"""
Pydantic Models representing Domain Data, Tools Schemas, and Structured Reports.
"""

from __future__ import annotations
from typing import List, Dict, Optional, Literal, Any
from pydantic import BaseModel, Field
from datetime import datetime, timezone


class RepoMetadata(BaseModel):
    """Core metadata of a GitHub repository."""
    owner: str
    name: str
    full_name: str
    description: Optional[str] = None
    default_branch: str = "main"
    stars: int = 0
    forks: int = 0
    open_issues: int = 0
    primary_language: Optional[str] = None
    topics: List[str] = Field(default_factory=list)
    license: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    html_url: str


class FileEntry(BaseModel):
    """A file or directory entry in the repository tree."""
    path: str
    type: Literal["blob", "tree"]
    size: Optional[int] = None
    sha: Optional[str] = None


class FileContent(BaseModel):
    """Retrieved file content with range context."""
    path: str
    total_lines: int
    start_line: int
    end_line: int
    is_truncated: bool
    content: str


class DependencyManifest(BaseModel):
    """Parsed dependency information from a project manifest."""
    manifest_type: str  # e.g., "requirements.txt", "package.json", "build.gradle", "Podfile"
    path: str
    direct_dependencies: List[str] = Field(default_factory=list)
    dev_dependencies: List[str] = Field(default_factory=list)
    frameworks: List[str] = Field(default_factory=list)


class ArchitectureFinding(BaseModel):
    """Verified or inferred architectural design finding."""
    component: str
    pattern_observed: str
    description: str
    evidence_files: List[str] = Field(default_factory=list)
    is_verified: bool = True  # True if confirmed by file content/AST; False if LLM inference


class TechnicalRisk(BaseModel):
    """Identified technical or architectural risk."""
    severity: Literal["low", "medium", "high", "critical"]
    category: str  # e.g., "Security", "Scalability", "Maintainability", "Dependency"
    title: str
    details: str
    affected_path: Optional[str] = None
    mitigation: str


class CodeQualityObservation(BaseModel):
    """Quality and engineering practice assessment."""
    category: str  # "Testing", "Typing", "CI/CD", "Documentation", "Structure"
    status: Literal["positive", "neutral", "concern"]
    observation: str
    file_reference: Optional[str] = None


class TokenUsage(BaseModel):
    """Token accounting for a single call or entire run."""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cached_tokens: int = 0
    total_tokens: int = 0


class RunCost(BaseModel):
    """Calculated cost in USD based on provider pricing tiers."""
    provider: str
    model: str
    prompt_cost_usd: float = 0.0
    completion_cost_usd: float = 0.0
    total_cost_usd: float = 0.0


class ToolCallRecord(BaseModel):
    """Record of a tool invocation in the agent trace."""
    tool_name: str
    arguments: Dict[str, Any]
    output_preview: str
    duration_ms: float
    is_error: bool = False


class AgentStep(BaseModel):
    """A single turn in the ReAct execution loop."""
    step_number: int
    thought: str
    tool_calls: List[ToolCallRecord] = Field(default_factory=list)
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class AnalysisReport(BaseModel):
    """Structured technical analysis report produced by the agent."""
    repository: RepoMetadata
    generated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    agent_model: str
    
    # Core Analysis Sections
    executive_summary: str
    technology_stack: List[str]
    architectural_style: str
    architecture_findings: List[ArchitectureFinding]
    dependencies: List[DependencyManifest]
    technical_risks: List[TechnicalRisk]
    code_quality: List[CodeQualityObservation]
    recommendations: List[str]
    
    # Audit & Accounting
    tokens: TokenUsage
    cost: RunCost
    steps_executed: int
    verified_files_count: int
