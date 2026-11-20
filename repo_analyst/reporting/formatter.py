"""
Console Formatter and Visual Reporter using Rich.
"""

from __future__ import annotations
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.markdown import Markdown

from repo_analyst.models import AgentStep, AnalysisReport

console = Console()


class ConsoleFormatter:
    """Renders formatted agent steps and reports to terminal."""

    @staticmethod
    def print_banner():
        banner_text = (
            "[bold cyan]AI Repository Analyst[/bold cyan] "
            "[yellow]| Autonomous Architecture & Quality Auditor[/yellow]\n"
            "[dim]Powered by Anthropic Claude / OpenAI / Official MCP SDK[/dim]"
        )
        console.print(Panel(banner_text, expand=False, border_style="cyan"))

    @staticmethod
    def print_step(step: AgentStep):
        """Displays a single ReAct step in the terminal."""
        title = f"[bold green]Turn {step.step_number}[/bold green]"
        content = f"[italic white]Thought:[/italic white] {step.thought}\n"

        if step.tool_calls:
            content += "\n[bold yellow]Actions Executed:[/bold yellow]\n"
            for tc in step.tool_calls:
                status = "[red]FAILED[/red]" if tc.is_error else "[green]OK[/green]"
                content += f"  • [cyan]{tc.tool_name}[/cyan] ({tc.duration_ms}ms) [{status}]\n"
                # show brief arg preview
                content += f"    [dim]args: {tc.arguments}[/dim]\n"

        console.print(Panel(content, title=title, border_style="blue", expand=False))

    @staticmethod
    def print_summary(report: AnalysisReport):
        """Displays summary table of findings and token costs."""
        cost = report.cost
        tokens = report.tokens
        repo = report.repository

        table = Table(title=f"Analysis Summary: {repo.full_name}", border_style="cyan")
        table.add_column("Category", style="bold white", width=25)
        table.add_column("Value / Details", style="cyan")

        table.add_row("Primary Language", repo.primary_language or "N/A")
        table.add_row("Architecture Style", report.architectural_style)
        table.add_row("Tech Stack", ", ".join(report.technology_stack) if report.technology_stack else "Detected in code")
        table.add_row("Verified Findings", str(len(report.architecture_findings)))
        table.add_row("Identified Risks", str(len(report.technical_risks)))
        table.add_row("Steps Executed", str(report.steps_executed))
        table.add_row("Verified Files Inspected", str(report.verified_files_count))
        table.add_row("Total Tokens", f"{tokens.total_tokens:,} (Prompt: {tokens.prompt_tokens:,}, Comp: {tokens.completion_tokens:,})")
        table.add_row("Run Cost (USD)", f"[bold green]${cost.total_cost_usd:.4f}[/bold green]")

        console.print(table)
