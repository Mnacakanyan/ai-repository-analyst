"""
Command-Line Interface for AI Repository Analyst.
"""

from __future__ import annotations
import sys
import argparse
from pathlib import Path

from repo_analyst.config import settings
from repo_analyst.core.agent import RepositoryAnalystAgent
from repo_analyst.reporting.generator import ReportGenerator
from repo_analyst.reporting.formatter import ConsoleFormatter, console
from repo_analyst.providers.anthropic import AnthropicProvider
from repo_analyst.providers.openai import OpenAIProvider
from repo_analyst.providers.mock import MockLLMProvider
from repo_analyst.mcp_server.server import run_mcp_server


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="ai-repo-analyst",
        description="Autonomous AI Agent analyzing public GitHub repositories with MCP tool integration.",
    )
    parser.add_argument(
        "--repo",
        type=str,
        help="GitHub repository URL or slug (e.g. 'fastapi/fastapi' or 'https://github.com/psf/requests')",
    )
    parser.add_argument(
        "--provider",
        choices=["anthropic", "openai", "mock"],
        default=None,
        help="LLM provider to use (default: resolved from env variables)",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Model identifier (e.g. 'claude-3-5-sonnet-20241022', 'claude-3-5-haiku-20241022', 'gpt-4o')",
    )
    parser.add_argument(
        "--max-turns",
        type=int,
        default=settings.MAX_TURNS,
        help=f"Maximum ReAct exploration turns (default: {settings.MAX_TURNS})",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=str(settings.OUTPUT_DIR),
        help="Directory to save generated Markdown and JSON reports",
    )
    parser.add_argument(
        "--no-mcp",
        action="store_true",
        help="Use direct tool registry instead of MCP server adapter",
    )
    parser.add_argument(
        "--serve-mcp",
        action="store_true",
        help="Launch the MCP server in stdio mode for Claude Desktop / Antigravity integration",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    # If --serve-mcp was passed, run MCP stdio server and exit
    if args.serve_mcp:
        run_mcp_server()
        return

    ConsoleFormatter.print_banner()

    if not args.repo:
        console.print("[bold red]Error:[/bold red] Please provide a repository via [yellow]--repo <owner/repo>[/yellow]")
        console.print("Example: [cyan]python -m repo_analyst --repo fastapi/fastapi[/cyan]")
        console.print("Or launch MCP server: [cyan]python -m repo_analyst --serve-mcp[/cyan]")
        sys.exit(1)

    # Resolve provider
    chosen_provider_name = args.provider or settings.DEFAULT_PROVIDER
    provider = None

    if chosen_provider_name == "anthropic":
        if not settings.ANTHROPIC_API_KEY:
            console.print("[bold yellow]Warning:[/bold yellow] ANTHROPIC_API_KEY not set. Using Mock provider.")
            provider = MockLLMProvider()
        else:
            model = args.model or settings.DEFAULT_ANTHROPIC_MODEL
            provider = AnthropicProvider(model_name=model)
    elif chosen_provider_name == "openai":
        if not settings.OPENAI_API_KEY:
            console.print("[bold yellow]Warning:[/bold yellow] OPENAI_API_KEY not set. Using Mock provider.")
            provider = MockLLMProvider()
        else:
            model = args.model or settings.DEFAULT_OPENAI_MODEL
            provider = OpenAIProvider(model_name=model)
    elif chosen_provider_name == "mock":
        provider = MockLLMProvider()

    console.print(f"[bold cyan]Target Repository:[/bold cyan] {args.repo}")
    console.print(f"[bold cyan]Provider:[/bold cyan] {provider.__class__.__name__} ({provider.model_name})")
    console.print(f"[bold cyan]Tool Interface:[/bold cyan] {'Direct Registry' if args.no_mcp else 'Official MCP Server Adapter'}")
    console.print(f"[bold cyan]Max Turns:[/bold cyan] {args.max_turns}\n")

    # Initialize agent
    agent = RepositoryAnalystAgent(
        provider=provider,
        use_mcp=not args.no_mcp,
        max_turns=args.max_turns,
        on_step_callback=ConsoleFormatter.print_step,
    )

    console.print("[bold green]Starting autonomous investigation loop...[/bold green]\n")

    try:
        report = agent.analyze(args.repo)
    except Exception as e:
        console.print(f"\n[bold red]Execution Aborted:[/bold red] {e}")
        sys.exit(1)

    # Save reports
    out_dir = Path(args.output_dir)
    md_path, json_path = ReportGenerator.save_reports(report, out_dir)

    console.print("\n[bold green]Autonomous Investigation Complete![/bold green]\n")
    ConsoleFormatter.print_summary(report)

    console.print(f"\n[bold white]Reports Saved:[/bold white]")
    console.print(f"  • Markdown: [cyan]{md_path}[/cyan]")
    console.print(f"  • JSON:     [cyan]{json_path}[/cyan]\n")


if __name__ == "__main__":
    main()
