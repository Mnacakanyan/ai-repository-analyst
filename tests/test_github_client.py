"""
Tests for GitHub Client URL Parsing and Handlers.
"""

import pytest
from repo_analyst.tools.github import GitHubClient


def test_parse_repo_url():
    client = GitHubClient()

    owner, repo = client.parse_repo_url("https://github.com/fastapi/fastapi")
    assert owner == "fastapi" and repo == "fastapi"

    owner, repo = client.parse_repo_url("https://github.com/psf/requests.git")
    assert owner == "psf" and repo == "requests"

    owner, repo = client.parse_repo_url("octocat/Spoon-Knife")
    assert owner == "octocat" and repo == "Spoon-Knife"

    with pytest.raises(ValueError):
        client.parse_repo_url("invalid-url-format")
