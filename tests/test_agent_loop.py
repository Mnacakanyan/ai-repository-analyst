"""
Tests for Agent ReAct Execution Loop and Synthesis.
"""

from unittest.mock import MagicMock
from repo_analyst.core.agent import RepositoryAnalystAgent
from repo_analyst.providers.mock import MockLLMProvider
from repo_analyst.models import RepoMetadata, FileEntry, FileContent


def test_agent_loop_with_mock_provider(monkeypatch):
    agent = RepositoryAnalystAgent(
        provider=MockLLMProvider(),
        use_mcp=False,
        max_turns=10,
    )

    # Mock GitHubClient responses to avoid network calls during loop unit test
    fake_meta = RepoMetadata(
        owner="test_owner",
        name="test_repo",
        full_name="test_owner/test_repo",
        stars=120,
        forks=15,
        default_branch="main",
        primary_language="Python",
        html_url="https://github.com/test_owner/test_repo",
    )
    fake_tree = [
        FileEntry(path="requirements.txt", type="blob", size=50),
        FileEntry(path="main.py", type="blob", size=500),
    ]
    fake_content = FileContent(
        path="requirements.txt",
        total_lines=2,
        start_line=1,
        end_line=2,
        is_truncated=False,
        content="fastapi>=0.100.0\npydantic>=2.0.0",
    )

    monkeypatch.setattr(agent.github_client, "get_repository_info", lambda o, r: fake_meta)
    monkeypatch.setattr(agent.github_client, "get_repository_tree", lambda o, r, branch=None, recursive=True: fake_tree)
    monkeypatch.setattr(agent.github_client, "read_file", lambda o, r, p, start_line=1, end_line=None: fake_content)
    # Also update tool_registry github instance
    agent.tool_registry.github = agent.github_client

    report = agent.analyze("test_owner/test_repo")

    assert report is not None
    assert report.repository.full_name == "test_owner/test_repo"
    assert report.steps_executed > 1
    assert report.tokens.total_tokens > 0
    assert report.cost.total_cost_usd >= 0.0
    assert len(report.recommendations) > 0
