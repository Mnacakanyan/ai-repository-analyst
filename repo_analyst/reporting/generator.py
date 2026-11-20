"""
Report Generation Engine.

Exports structured analysis reports to formatted Markdown and JSON formats
with file citations, line references, token audits, and risk matrices.
"""

from __future__ import annotations
from pathlib import Path
from repo_analyst.models import AnalysisReport
from repo_analyst.config import settings


class ReportGenerator:
    """Generates Markdown and JSON reports from AnalysisReport."""

    @staticmethod
    def to_markdown(report: AnalysisReport) -> str:
        repo = report.repository
        cost = report.cost
        tokens = report.tokens

        md = []
        md.append(f"# Technical Architecture Analysis: {repo.full_name}\n")
        md.append(f"> **Automated Agent Audit Report**  ")
        md.append(f"> **Generated at**: `{report.generated_at}` | **Agent Model**: `{report.agent_model}`  ")
        md.append(f"> **Audit Footprint**: {report.steps_executed} reasoning steps, {report.verified_files_count} files inspected | **Operational Cost**: `${cost.total_cost_usd:.4f}` ({tokens.total_tokens:,} tokens)\n")

        # Repository Overview
        md.append("## 1. Repository Overview\n")
        md.append(f"- **URL**: [{repo.html_url}]({repo.html_url})")
        md.append(f"- **Default Branch**: `{repo.default_branch}`")
        md.append(f"- **Primary Language**: {repo.primary_language or 'Not specified'}")
        md.append(f"- **Stars**: {repo.stars:,} | **Forks**: {repo.forks:,} | **Open Issues**: {repo.open_issues:,}")
        md.append(f"- **License**: `{repo.license or 'None detected'}`")
        if repo.description:
            md.append(f"- **Description**: {repo.description}")
        md.append("")

        # Executive Summary
        md.append("## 2. Executive Summary\n")
        md.append(report.executive_summary)
        md.append("")

        # Tech Stack & Architecture Style
        md.append("## 3. Technology Stack & Architectural Style\n")
        md.append(f"**Identified Architectural Style**: `{report.architectural_style}`\n")
        md.append("**Detected Technologies & Frameworks**:")
        for tech in report.technology_stack:
            md.append(f"- `{tech}`")
        md.append("")

        # Architecture Findings
        md.append("## 4. Architectural Analysis & Component Findings\n")
        if report.architecture_findings:
            md.append("| Component | Pattern / Role | Verification | Evidence Files | Description |")
            md.append("|:---|:---|:---:|:---|:---|")
            for f in report.architecture_findings:
                status = "✅ Verified" if f.is_verified else "⚠️ Inferred"
                files = "<br>".join([f"`{ef}`" for ef in f.evidence_files]) if f.evidence_files else "None cited"
                desc = f.description.replace("\n", " ")
                md.append(f"| **{f.component}** | {f.pattern_observed} | {status} | {files} | {desc} |")
            md.append("")
        else:
            md.append("*No specific architecture findings recorded.*\n")

        # Technical Risks
        md.append("## 5. Potential Technical Risks & Vulnerabilities\n")
        if report.technical_risks:
            severity_emojis = {
                "critical": "🔴 CRITICAL",
                "high": "🟠 HIGH",
                "medium": "🟡 MEDIUM",
                "low": "🔵 LOW",
            }
            for risk in report.technical_risks:
                sev = severity_emojis.get(risk.severity.lower(), risk.severity.upper())
                md.append(f"### {sev}: {risk.title}")
                md.append(f"- **Category**: `{risk.category}`")
                if risk.affected_path:
                    md.append(f"- **Affected Path**: `{risk.affected_path}`")
                md.append(f"- **Details**: {risk.details}")
                md.append(f"- **Recommended Mitigation**: {risk.mitigation}\n")
        else:
            md.append("*No major technical risks detected during inspection.*\n")

        # Code Quality Observations
        md.append("## 6. Code Quality & Engineering Practices\n")
        if report.code_quality:
            status_emojis = {"positive": "✅ Good", "neutral": "ℹ️ Info", "concern": "⚠️ Concern"}
            for q in report.code_quality:
                st = status_emojis.get(q.status, q.status.title())
                file_ref = f" (`{q.file_reference}`)" if q.file_reference else ""
                md.append(f"- **[{st}] {q.category}**: {q.observation}{file_ref}")
            md.append("")
        else:
            md.append("*Standard engineering patterns observed.*\n")

        # Recommendations
        md.append("## 7. Actionable Recommendations\n")
        for i, rec in enumerate(report.recommendations, 1):
            md.append(f"{i}. {rec}")
        md.append("")

        # Operational Token & Cost Audit
        md.append("## 8. Agent Operational Cost & Token Audit\n")
        md.append("| Metric | Count / Cost |")
        md.append("|:---|:---|")
        md.append(f"| LLM Model | `{report.agent_model}` |")
        md.append(f"| Prompt Tokens | {tokens.prompt_tokens:,} |")
        md.append(f"| Completion Tokens | {tokens.completion_tokens:,} |")
        md.append(f"| Cached Prompt Tokens | {tokens.cached_tokens:,} |")
        md.append(f"| Total Tokens | {tokens.total_tokens:,} |")
        md.append(f"| Prompt Cost (USD) | `${cost.prompt_cost_usd:.5f}` |")
        md.append(f"| Completion Cost (USD) | `${cost.completion_cost_usd:.5f}` |")
        md.append(f"| **Total Run Cost (USD)** | **`${cost.total_cost_usd:.5f}`** |")
        md.append(f"| ReAct Turns Executed | {report.steps_executed} |")
        md.append(f"| Verified Source Files | {report.verified_files_count} |")
        md.append("")

        return "\n".join(md)

    @staticmethod
    def save_reports(report: AnalysisReport, output_dir: Path) -> tuple[Path, Path]:
        """Saves both Markdown and JSON files to output directory."""
        output_dir.mkdir(parents=True, exist_ok=True)
        safe_name = f"{report.repository.owner}_{report.repository.name}_analysis"

        md_path = output_dir / f"{safe_name}.md"
        json_path = output_dir / f"{safe_name}.json"

        md_content = ReportGenerator.to_markdown(report)
        md_path.write_text(md_content, encoding="utf-8")

        json_content = report.model_dump_json(indent=2)
        json_path.write_text(json_content, encoding="utf-8")

        return md_path, json_path
