"""
Tests for Data Models and Serialization.
"""

from repo_analyst.models import (
    RepoMetadata,
    FileEntry,
    FileContent,
    DependencyManifest,
    ArchitectureFinding,
    TechnicalRisk,
    TokenUsage,
    RunCost,
    AnalysisReport,
)


def test_repo_metadata_model():
    meta = RepoMetadata(
        owner="fastapi",
        name="fastapi",
        full_name="fastapi/fastapi",
        stars=75000,
        forks=6000,
        default_branch="master",
        primary_language="Python",
        html_url="https://github.com/fastapi/fastapi",
    )
    assert meta.owner == "fastapi"
    assert meta.stars == 75000
    dumped = meta.model_dump()
    assert dumped["full_name"] == "fastapi/fastapi"


def test_analysis_report_serialization():
    repo = RepoMetadata(
        owner="test-owner",
        name="test-repo",
        full_name="test-owner/test-repo",
        stars=100,
        forks=20,
        default_branch="main",
        primary_language="TypeScript",
        html_url="https://github.com/test-owner/test-repo",
    )
    report = AnalysisReport(
        repository=repo,
        agent_model="claude-3-5-sonnet-20241022",
        executive_summary="Modern modular web application.",
        technology_stack=["TypeScript", "React", "Node.js"],
        architectural_style="Modular Monolith",
        architecture_findings=[
            ArchitectureFinding(
                component="API Gateway",
                pattern_observed="Facade",
                description="Routes incoming client requests.",
                evidence_files=["src/gateway.ts"],
                is_verified=True,
            )
        ],
        dependencies=[],
        technical_risks=[
            TechnicalRisk(
                severity="low",
                category="Maintenance",
                title="Outdated dependency",
                details="Minor patch available.",
                mitigation="Update lockfile.",
            )
        ],
        code_quality=[],
        recommendations=["Add end-to-end integration tests."],
        tokens=TokenUsage(prompt_tokens=1000, completion_tokens=200, total_tokens=1200),
        cost=RunCost(provider="Anthropic", model="claude-3-5-sonnet-20241022", total_cost_usd=0.006),
        steps_executed=4,
        verified_files_count=3,
    )

    json_str = report.model_dump_json()
    assert "Modular Monolith" in json_str
    assert "API Gateway" in json_str
