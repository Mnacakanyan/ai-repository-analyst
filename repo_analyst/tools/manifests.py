"""
Dependency Manifest Analyzer for Multiple Ecosystems.

Parses requirements.txt, pyproject.toml, package.json, build.gradle, Podfile,
and Unity Packages manifests to extract direct dependencies and frameworks.
"""

from __future__ import annotations
import json
import re
from typing import List, Optional
from repo_analyst.models import DependencyManifest


KNOWN_FRAMEWORKS = {
    # Web & API
    "fastapi": "FastAPI",
    "flask": "Flask",
    "django": "Django",
    "express": "Express.js",
    "react": "React",
    "next": "Next.js",
    "vue": "Vue.js",
    "angular": "Angular",
    # Mobile & Game Engines
    "unity": "Unity",
    "react-native": "React Native",
    "flutter": "Flutter",
    # AI & Agents & Data
    "anthropic": "Anthropic Claude SDK",
    "openai": "OpenAI SDK",
    "mcp": "Model Context Protocol (MCP)",
    "langchain": "LangChain",
    "llamaindex": "LlamaIndex",
    "transformers": "HuggingFace Transformers",
    "torch": "PyTorch",
    "tensorflow": "TensorFlow",
    "pydantic": "Pydantic",
    # Databases & Storage
    "sqlalchemy": "SQLAlchemy",
    "prisma": "Prisma ORM",
    "redis": "Redis",
    "pymongo": "MongoDB",
}


class ManifestParser:
    """Dispatches and parses dependency manifests."""

    @staticmethod
    def parse_manifest(path: str, content: str) -> Optional[DependencyManifest]:
        filename = path.split("/")[-1].lower()

        if filename == "requirements.txt" or filename.endswith("-requirements.txt"):
            return ManifestParser._parse_requirements_txt(path, content)
        elif filename == "package.json":
            return ManifestParser._parse_package_json(path, content)
        elif filename == "pyproject.toml":
            return ManifestParser._parse_pyproject_toml(path, content)
        elif filename in ("build.gradle", "build.gradle.kts"):
            return ManifestParser._parse_gradle(path, content)
        elif filename == "podfile":
            return ManifestParser._parse_podfile(path, content)
        elif filename == "manifest.json" and "packages" in path.lower():
            # Unity Package Manager manifest
            return ManifestParser._parse_unity_manifest(path, content)
        elif filename == "cargo.toml":
            return ManifestParser._parse_cargo_toml(path, content)

        return None

    @staticmethod
    def _detect_frameworks(deps: List[str]) -> List[str]:
        detected = set()
        for dep in deps:
            dep_clean = dep.lower().split("=")[0].split(">")[0].split("<")[0].split("[")[0].strip()
            for key, name in KNOWN_FRAMEWORKS.items():
                if key in dep_clean:
                    detected.add(name)
        return sorted(list(detected))

    @staticmethod
    def _parse_requirements_txt(path: str, content: str) -> DependencyManifest:
        direct = []
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("-"):
                continue
            dep_name = re.split(r"[=<>~!;@]", line)[0].strip()
            if dep_name:
                direct.append(dep_name)

        frameworks = ManifestParser._detect_frameworks(direct)
        return DependencyManifest(
            manifest_type="requirements.txt",
            path=path,
            direct_dependencies=direct,
            dev_dependencies=[],
            frameworks=frameworks,
        )

    @staticmethod
    def _parse_package_json(path: str, content: str) -> DependencyManifest:
        try:
            data = json.loads(content)
        except Exception:
            return DependencyManifest(manifest_type="package.json", path=path)

        deps = list(data.get("dependencies", {}).keys())
        dev_deps = list(data.get("devDependencies", {}).keys())
        frameworks = ManifestParser._detect_frameworks(deps + dev_deps)

        return DependencyManifest(
            manifest_type="package.json",
            path=path,
            direct_dependencies=deps,
            dev_dependencies=dev_deps,
            frameworks=frameworks,
        )

    @staticmethod
    def _parse_pyproject_toml(path: str, content: str) -> DependencyManifest:
        direct = []
        dev = []

        # Simple robust regex parsing for dependencies without requiring tomli
        # Matches dependencies = [ ... ]
        dep_section = re.search(r"dependencies\s*=\s*\[(.*?)\]", content, re.DOTALL)
        if dep_section:
            for item in re.findall(r'"([^"]+)"|\'([^\']+)\'', dep_section.group(1)):
                raw = item[0] or item[1]
                name = re.split(r"[=<>~!;@\[]", raw)[0].strip()
                if name:
                    direct.append(name)

        frameworks = ManifestParser._detect_frameworks(direct + dev)
        return DependencyManifest(
            manifest_type="pyproject.toml",
            path=path,
            direct_dependencies=direct,
            dev_dependencies=dev,
            frameworks=frameworks,
        )

    @staticmethod
    def _parse_gradle(path: str, content: str) -> DependencyManifest:
        direct = []
        # Match implementation("..."), implementation '...', api '...'
        matches = re.findall(r'(?:implementation|api|compileOnly)\s*(?:\(\s*[\'"]([^\'"]+)[\'"]\s*\)|[\'"]([^\'"]+)[\'"])', content)
        for m in matches:
            dep = m[0] or m[1]
            if dep:
                direct.append(dep.strip())

        frameworks = ManifestParser._detect_frameworks(direct)
        return DependencyManifest(
            manifest_type="build.gradle",
            path=path,
            direct_dependencies=direct,
            dev_dependencies=[],
            frameworks=frameworks,
        )

    @staticmethod
    def _parse_podfile(path: str, content: str) -> DependencyManifest:
        direct = []
        matches = re.findall(r"pod\s+['\"]([^'\"]+)['\"]", content)
        for m in matches:
            direct.append(m.strip())

        frameworks = ManifestParser._detect_frameworks(direct)
        return DependencyManifest(
            manifest_type="Podfile",
            path=path,
            direct_dependencies=direct,
            dev_dependencies=[],
            frameworks=frameworks,
        )

    @staticmethod
    def _parse_unity_manifest(path: str, content: str) -> DependencyManifest:
        try:
            data = json.loads(content)
            deps = list(data.get("dependencies", {}).keys())
        except Exception:
            deps = []

        return DependencyManifest(
            manifest_type="Unity Manifest",
            path=path,
            direct_dependencies=deps,
            dev_dependencies=[],
            frameworks=["Unity Engine"],
        )

    @staticmethod
    def _parse_cargo_toml(path: str, content: str) -> DependencyManifest:
        direct = []
        # Find [dependencies] section
        in_deps = False
        for line in content.splitlines():
            line = line.strip()
            if line.startswith("[dependencies"):
                in_deps = True
                continue
            elif line.startswith("[") and in_deps:
                break
            if in_deps and "=" in line and not line.startswith("#"):
                dep_name = line.split("=")[0].strip()
                if dep_name:
                    direct.append(dep_name)

        return DependencyManifest(
            manifest_type="Cargo.toml",
            path=path,
            direct_dependencies=direct,
            dev_dependencies=[],
            frameworks=ManifestParser._detect_frameworks(direct),
        )
