"""
GitHub REST API Client and Tool Implementations.

Interacts directly with the public GitHub REST API using httpx with rate-limit
handling, branch resolution, and line-range extraction.
"""

from __future__ import annotations
import base64
import re
from typing import List, Dict, Any, Optional
import httpx

from repo_analyst.config import settings
from repo_analyst.models import RepoMetadata, FileEntry, FileContent


class GitHubClient:
    """Client for GitHub REST API v3."""

    BASE_URL = "https://api.github.com"

    def __init__(self, token: Optional[str] = None):
        self.token = token or settings.GITHUB_TOKEN
        self.headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "AI-Repository-Analyst/1.0",
        }
        if self.token:
            self.headers["Authorization"] = f"Bearer {self.token}"

    def parse_repo_url(self, repo_input: str) -> tuple[str, str]:
        """
        Parses repository owner and name from varied inputs:
        - "https://github.com/fastapi/fastapi"
        - "github.com/fastapi/fastapi"
        - "fastapi/fastapi"
        """
        cleaned = repo_input.strip().rstrip("/")
        if cleaned.endswith(".git"):
            cleaned = cleaned[:-4]

        # Match github.com/owner/repo or owner/repo
        match = re.search(r"(?:https?://)?(?:www\.)?github\.com/([^/]+)/([^/]+)", cleaned)
        if match:
            return match.group(1), match.group(2)

        parts = cleaned.split("/")
        if len(parts) == 2:
            return parts[0], parts[1]

        raise ValueError(f"Invalid GitHub repository identifier: '{repo_input}'. Expected 'owner/repo' or GitHub URL.")

    def get_repository_info(self, owner: str, repo: str) -> RepoMetadata:
        """Fetches repository high-level metadata."""
        url = f"{self.BASE_URL}/repos/{owner}/{repo}"
        with httpx.Client(headers=self.headers, timeout=15.0) as client:
            resp = client.get(url)
            if resp.status_code == 404:
                raise FileNotFoundError(f"Repository {owner}/{repo} not found on GitHub.")
            if resp.status_code == 403 and "rate limit" in resp.text.lower():
                raise PermissionError("GitHub API rate limit exceeded. Set GITHUB_TOKEN environment variable to increase limit.")
            resp.raise_for_status()
            data = resp.json()

        license_name = data.get("license", {}).get("spdx_id") if data.get("license") else None

        return RepoMetadata(
            owner=data["owner"]["login"],
            name=data["name"],
            full_name=data["full_name"],
            description=data.get("description"),
            default_branch=data.get("default_branch", "main"),
            stars=data.get("stargazers_count", 0),
            forks=data.get("forks_count", 0),
            open_issues=data.get("open_issues_count", 0),
            primary_language=data.get("language"),
            topics=data.get("topics", []),
            license=license_name,
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
            html_url=data["html_url"],
        )

    def get_repository_tree(
        self,
        owner: str,
        repo: str,
        branch: Optional[str] = None,
        recursive: bool = True,
        max_items: int = 400,
    ) -> List[FileEntry]:
        """
        Fetches the file tree for the repository using the Git Trees API.
        """
        target_branch = branch
        if not target_branch:
            # Look up default branch
            meta = self.get_repository_info(owner, repo)
            target_branch = meta.default_branch

        url = f"{self.BASE_URL}/repos/{owner}/{repo}/git/trees/{target_branch}"
        params = {"recursive": "1"} if recursive else {}

        with httpx.Client(headers=self.headers, timeout=20.0) as client:
            resp = client.get(url, params=params)
            resp.raise_for_status()
            tree_data = resp.json()

        raw_tree = tree_data.get("tree", [])
        results: List[FileEntry] = []

        # Filter out common clutter directories (.git, .github/workflows is kept)
        ignored_prefixes = (
            "node_modules/",
            "__pycache__/",
            ".venv/",
            "venv/",
            "dist/",
            "build/",
            ".idea/",
            ".vscode/",
        )

        for item in raw_tree:
            path = item.get("path", "")
            if any(path.startswith(prefix) for prefix in ignored_prefixes):
                continue

            entry_type = "tree" if item.get("type") == "tree" else "blob"
            results.append(FileEntry(
                path=path,
                type=entry_type,
                size=item.get("size"),
                sha=item.get("sha"),
            ))
            if len(results) >= max_items:
                break

        return results

    def read_file(
        self,
        owner: str,
        repo: str,
        path: str,
        start_line: int = 1,
        end_line: Optional[int] = None,
        max_bytes: int = 60_000,
    ) -> FileContent:
        """
        Reads a specific file from the repository, with line-range and truncation support.
        """
        url = f"{self.BASE_URL}/repos/{owner}/{repo}/contents/{path.lstrip('/')}"
        with httpx.Client(headers=self.headers, timeout=15.0) as client:
            resp = client.get(url)
            if resp.status_code == 404:
                raise FileNotFoundError(f"File '{path}' not found in repository {owner}/{repo}.")
            resp.raise_for_status()
            data = resp.json()

        # GitHub contents API returns base64 encoded content
        encoding = data.get("encoding")
        raw_b64 = data.get("content", "")

        if encoding == "base64" and raw_b64:
            raw_bytes = base64.b64decode(raw_b64)
            try:
                text = raw_bytes.decode("utf-8")
            except UnicodeDecodeError:
                text = raw_bytes.decode("latin-1", errors="replace")
        else:
            text = str(raw_b64)

        lines = text.splitlines()
        total_lines = len(lines)

        # Apply line range
        start_idx = max(0, start_line - 1)
        end_idx = total_lines if end_line is None else min(total_lines, end_line)

        selected_lines = lines[start_idx:end_idx]
        selected_text = "\n".join(selected_lines)

        is_truncated = False
        if len(selected_text.encode("utf-8")) > max_bytes:
            selected_text = selected_text[:max_bytes] + "\n... [Content truncated due to size limit]"
            is_truncated = True

        return FileContent(
            path=path,
            total_lines=total_lines,
            start_line=start_idx + 1,
            end_line=end_idx,
            is_truncated=is_truncated,
            content=selected_text,
        )

    def search_code(
        self,
        owner: str,
        repo: str,
        query: str,
        max_results: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Searches code inside the repository using GitHub Search API.
        """
        url = f"{self.BASE_URL}/search/code"
        q = f"{query} repo:{owner}/{repo}"
        params = {"q": q, "per_page": max_results}

        with httpx.Client(headers=self.headers, timeout=15.0) as client:
            resp = client.get(url, params=params)
            if resp.status_code == 403:
                # Code search rate limit or authentication required
                return [{"error": "Search API rate-limited or requires authenticated token. Fall back to reading tree/files."}]
            resp.raise_for_status()
            data = resp.json()

        items = data.get("items", [])
        return [
            {
                "path": item.get("path"),
                "html_url": item.get("html_url"),
                "sha": item.get("sha"),
            }
            for item in items
        ]
