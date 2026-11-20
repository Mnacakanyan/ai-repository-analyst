"""
Tests for Manifest Parsing (Python, JS, Gradle, Unity).
"""

from repo_analyst.tools.manifests import ManifestParser


def test_parse_requirements_txt():
    content = """
    # Core dependencies
    fastapi>=0.100.0
    pydantic==2.8.2
    anthropic>=0.30.0
    uvicorn[standard]>=0.20.0
    pytest
    """
    manifest = ManifestParser.parse_manifest("requirements.txt", content)
    assert manifest is not None
    assert "fastapi" in manifest.direct_dependencies
    assert "anthropic" in manifest.direct_dependencies
    assert "FastAPI" in manifest.frameworks
    assert "Anthropic Claude SDK" in manifest.frameworks


def test_parse_package_json():
    content = """{
      "name": "sample-app",
      "dependencies": {
        "react": "^18.2.0",
        "next": "14.1.0",
        "prisma": "^5.0.0"
      },
      "devDependencies": {
        "typescript": "^5.0.0"
      }
    }"""
    manifest = ManifestParser.parse_manifest("package.json", content)
    assert manifest is not None
    assert "react" in manifest.direct_dependencies
    assert "React" in manifest.frameworks
    assert "Next.js" in manifest.frameworks
    assert "Prisma ORM" in manifest.frameworks


def test_parse_gradle():
    content = """
    dependencies {
        implementation("androidx.core:core-ktx:1.12.0")
        implementation 'com.google.android.material:material:1.11.0'
    }
    """
    manifest = ManifestParser.parse_manifest("build.gradle", content)
    assert manifest is not None
    assert any("androidx.core" in dep for dep in manifest.direct_dependencies)


def test_parse_unity_manifest():
    content = """{
      "dependencies": {
        "com.unity.modules.ai": "1.0.0",
        "com.unity.modules.physics": "1.0.0"
      }
    }"""
    manifest = ManifestParser.parse_manifest("Packages/manifest.json", content)
    assert manifest is not None
    assert manifest.manifest_type == "Unity Manifest"
    assert "Unity Engine" in manifest.frameworks
