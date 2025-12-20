"""
WALT CLI

Main command-line interface for WALT (Web Agents that Learn Tools).
"""

import asyncio
import sys
import os  # 新增: 用于设置环境变量
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

# [新增] 引入 LangChain 回调用于统计 Token
try:
    from langchain_community.callbacks import get_openai_callback
except ImportError:
    # 兼容旧版本
    from langchain.callbacks import get_openai_callback

# ==============================================================================
# DeepSeek Configuration (User Provided)
# ==============================================================================
DEEPSEEK_CONFIG = {
    "api_key": "sk-41fae6597fd14d6fa2c5c4068c0e5760",
    "base_url": "https://api.deepseek.com",
    "model": "deepseek-chat"
}

app = typer.Typer(
    name="walt",
    help="🪄 WALT: Web Agents that Learn Tools - Automatic tool discovery from websites",
    no_args_is_help=True,
    add_completion=False,
)

console = Console()

def setup_deepseek_env(model_name: str):
    """
    Helper: If the model is DeepSeek, inject environment variables 
    to force underlying OpenAI clients to use DeepSeek.
    """
    if "deepseek" in model_name.lower():
        os.environ["OPENAI_API_KEY"] = DEEPSEEK_CONFIG["api_key"]
        os.environ["OPENAI_BASE_URL"] = DEEPSEEK_CONFIG["base_url"]
        os.environ["OPENAI_API_BASE"] = DEEPSEEK_CONFIG["base_url"] # 兼容不同版本的 SDK
        console.print(f"[dim]🚀 Switched to DeepSeek Endpoint: {DEEPSEEK_CONFIG['base_url']}[/dim]")

@app.command()
def init():
    """Initialize WALT configuration with .env file."""
    console.print("[bold cyan]🚀 Initializing WALT configuration[/bold cyan]")

    # 修改: 默认 .env 模板包含 DeepSeek 配置
    env_content = f"""# WALT Configuration

# ==============================================================================
# LLM API Keys
# ==============================================================================

# DeepSeek Configuration (Active)
OPENAI_API_KEY={DEEPSEEK_CONFIG['api_key']}
OPENAI_BASE_URL={DEEPSEEK_CONFIG['base_url']}

# Keep standard keys if needed for fallback
# ANTHROPIC_API_KEY=your-anthropic-key-here
# GOOGLE_API_KEY=your-google-key-here

# ==============================================================================
# Benchmark URLs (For research reproduction only)
# ==============================================================================
# VisualWebArena URLs
# DATASET=visualwebarena
# CLASSIFIEDS=http://localhost:9980
# CLASSIFIEDS_RESET_TOKEN=4b61655535e7ed388f0d40a93600254c
# SHOPPING=http://localhost:7770  
# REDDIT=http://localhost:9999

# ==============================================================================
# Advanced Settings
# ==============================================================================
ANONYMIZED_TELEMETRY=false
BROWSER_USE_LOGGING_LEVEL=info
"""

    if Path(".env").exists():
        console.print("[yellow]⚠️  .env file already exists[/yellow]")
        overwrite = typer.confirm("Overwrite existing .env file?")
        if not overwrite:
            console.print("[dim]Cancelled[/dim]")
            return

    with open(".env", "w") as f:
        f.write(env_content)

    console.print("[green]✅ Created .env file configured for DeepSeek[/green]")


@app.command()
def version():
    """Show WALT version."""
    from walt import __version__
    console.print(f"[bold cyan]WALT[/bold cyan] version {__version__}")


@app.command()
def discover(
    url: str = typer.Option(
        ..., "--url", help="Base URL to discover tools from (e.g., https://example.com)"
    ),
    output_dir: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output directory for discovered tools"
    ),
    # 修改: 默认模型改为 deepseek-chat
    llm: str = typer.Option(DEEPSEEK_CONFIG["model"], "--llm", help="LLM model to use"),
    planner_llm: Optional[str] = typer.Option(
        None, "--planner-llm", help="Planner LLM model (defaults to same as --llm)"
    ),
    auth_file: Optional[str] = typer.Option(
        None, "--auth-file", help="Playwright storage_state JSON file for authentication"
    ),
    max_processes: int = typer.Option(8, "--max-processes", "-p", help="Max concurrent processes"),
    force_regenerate: bool = typer.Option(
        False, "--force-regenerate", help="Force regeneration of existing tools"
    ),
    skip_test: bool = typer.Option(False, "--skip-test", help="Skip testing generated tools"),
    optimize: bool = typer.Option(False, "--optimize", help="Generate optimized versions of tools"),
):
    """Discover and generate tools from any website."""
    
    # 注入 DeepSeek 环境
    setup_deepseek_env(llm)
    if planner_llm:
        setup_deepseek_env(planner_llm)

    console.print(f"[bold cyan]🔍 Discovering tools from:[/bold cyan] {url}")

    from types import SimpleNamespace
    args = SimpleNamespace(
        url=url,
        base_url=url,
        llm=llm,
        planner_llm=planner_llm or llm,
        auth_file=auth_file,
        max_processes=max_processes,
        force_regenerate=force_regenerate,
        test=not skip_test,
        optimize=optimize,
        discover=True,
        generate=True
    )

    if not output_dir:
        domain = url.replace("https://", "").replace("http://", "").split("/")[0]
        args.output_dir = f"walt-tools/{domain}"
    else:
        args.output_dir = output_dir

    if auth_file:
        console.print(f"[dim]🔑 Using authentication: {auth_file}[/dim]")

    try:
        asyncio.run(discovery_main_async(args))
        console.print(f"\n[bold green]✅ Discovery complete![/bold green]")
        console.print(f"[dim]Tools saved to: {args.output_dir}[/dim]")
    except KeyboardInterrupt:
        console.print("\n[yellow]⚠️  Discovery interrupted by user[/yellow]")
        raise typer.Exit(130)
    except Exception as e:
        console.print(f"\n[bold red]❌ Error:[/bold red] {e}")
        import traceback
        console.print(f"[dim]{traceback.format_exc()}[/dim]")
        raise typer.Exit(1)


async def discovery_main_async(args):
    """Run the generic discovery pipeline."""
    from walt.tools.discovery import propose, generate
    import os
    import json
    import time
    from datetime import datetime

    # 确保输出目录存在
    os.makedirs(args.output_dir, exist_ok=True)

    console.print(f"[dim]📁 Output directory: {args.output_dir}[/dim]")

    # [新增] 开启统计上下文
    with get_openai_callback() as cb:
        # Phase 1: Discovery
        console.print("\n[bold cyan]🔍 Phase 1: Discovering candidate tools...[/bold cyan]")
        # tools_json = await propose.discover_candidates(args)
        # console.print(f"[green]✅ Found {len(tools_json)} candidate tools[/green]")

        # Phase 2: Generation
        console.print("\n[bold cyan]🚀 Phase 2: Generating tools...[/bold cyan]")
        tools_json = propose.load_existing_candidates(args)
        
        success_count = 0
        if not tools_json:
            console.print("[yellow]⚠️  No candidates found[/yellow]")
        else:
            success_count = await generate.generate_tools(args, tools_json)
            console.print(
                f"[green]✅ Generated {success_count}/{len(tools_json)} tools successfully[/green]"
            )

        # ------------------------------------------------------------------
        # [修改] 统计结果保存到文件，而不是打印到控制台
        # ------------------------------------------------------------------
        
        # 构造统计数据字典
        usage_stats = {
            "timestamp": datetime.now().isoformat(),
            "directory": args.output_dir,
            "success_count": success_count,
            "total_candidates": len(tools_json) if tools_json else 0,
            "deepseek_usage": {
                "total_calls": cb.successful_requests,
                "total_tokens": cb.total_tokens,
                "prompt_tokens": cb.prompt_tokens,
                "completion_tokens": cb.completion_tokens,
                # 如果你想估算成本，可以在这里添加计算逻辑
                # "estimated_cost_usd": cb.total_tokens * PRICE_PER_TOKEN 
            }
        }

        # 为了防止并行写入冲突，建议使用包含时间戳或唯一ID的文件名
        # 或者如果 args.output_dir 对每个任务是唯一的，直接用 usage_report.json 也可以
        report_filename = f"usage_report_{int(time.time())}.json"
        report_path = os.path.join(args.output_dir, report_filename)

        try:
            with open(report_path, "w", encoding='utf-8') as f:
                json.dump(usage_stats, f, indent=4, ensure_ascii=False)
            
            # 只在控制台打印一行简单的提示，避免刷屏
            console.print(f"[dim]📄 Usage report saved to: {report_filename}[/dim]")
            
        except Exception as e:
            console.print(f"[red]❌ Failed to save usage report: {e}[/red]")


async def generate_main_async(args, goals: list[str]):
    """Run targeted tool generation without exploration."""
    from walt.tools.discovery import generate
    import os
    import json
    import re

    os.makedirs(args.output_dir, exist_ok=True)
    console.print(f"[dim]📁 Output directory: {args.output_dir}[/dim]")

    tools_json = []
    for goal in goals:
        tool_name = re.sub(r"[^a-z0-9_]+", "_", goal.lower())[:50].strip("_")
        tools_json.append(
            {
                "name": tool_name,
                "description": goal,
                "start_url": args.base_url,
                "elements": [],
            }
        )

    exploration_file = os.path.join(args.output_dir, "exploration_result.json")
    with open(exploration_file, "w") as f:
        json.dump({"tools": tools_json}, f, indent=4)

    console.print(f"[green]✅ Created {len(tools_json)} tool candidate(s) from goals[/green]")
    console.print("\n[bold cyan]🚀 Generating tools...[/bold cyan]")
    success_count = await generate.generate_tools(args, tools_json)
    console.print(
        f"[green]✅ Generated {success_count}/{len(tools_json)} tools successfully[/green]"
    )


@app.command()
def generate(
    url: str = typer.Option(
        ..., "--url", help="Base URL for the tools (e.g., https://example.com)"
    ),
    goal: str = typer.Option(
        ..., "--goal", help="Tool goal/description"
    ),
    output_dir: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output directory for generated tools"
    ),
    # 修改: 默认模型改为 deepseek-chat
    llm: str = typer.Option(DEEPSEEK_CONFIG["model"], "--llm", help="LLM model to use"),
    planner_llm: Optional[str] = typer.Option(
        None, "--planner-llm", help="Planner LLM model (defaults to same as --llm)"
    ),
    auth_file: Optional[str] = typer.Option(
        None, "--auth-file", help="Playwright storage_state JSON file for authentication"
    ),
    max_processes: int = typer.Option(16, "--max-processes", "-p", help="Max concurrent processes"),
    force_regenerate: bool = typer.Option(
        False, "--force-regenerate", help="Force regeneration of existing tools"
    ),
    skip_test: bool = typer.Option(False, "--skip-test", help="Skip testing generated tools"),
):
    """Generate a specific tool from a website without exploration."""
    
    # 注入 DeepSeek 环境
    setup_deepseek_env(llm)
    
    goals = [goal]
    console.print(f"[bold cyan]🎯 Generating tool from:[/bold cyan] {url}")
    console.print(f"[dim]Goal: {goal}[/dim]")

    from types import SimpleNamespace
    args = SimpleNamespace(
        url=url,
        base_url=url,
        llm=llm,
        planner_llm=planner_llm or llm,
        auth_file=auth_file,
        max_processes=max_processes,
        force_regenerate=force_regenerate,
        test=not skip_test,
        optimize=False
    )

    if not output_dir:
        domain = url.replace("https://", "").replace("http://", "").split("/")[0]
        args.output_dir = f"walt-tools/{domain}"
    else:
        args.output_dir = output_dir

    if auth_file:
        console.print(f"[dim]🔑 Using authentication: {auth_file}[/dim]")

    try:
        asyncio.run(generate_main_async(args, goals))
        console.print(f"\n[bold green]✅ Generation complete![/bold green]")
        console.print(f"[dim]Tools saved to: {args.output_dir}[/dim]")
    except KeyboardInterrupt:
        console.print("\n[yellow]⚠️  Generation interrupted by user[/yellow]")
        raise typer.Exit(130)
    except Exception as e:
        console.print(f"\n[bold red]❌ Error:[/bold red] {e}")
        import traceback
        console.print(f"[dim]{traceback.format_exc()}[/dim]")
        raise typer.Exit(1)


@app.command()
def serve(
    tool_dir: str = typer.Argument(..., help="Directory containing tool JSON files"),
    port: int = typer.Option(8000, "--port", "-p", help="Port to run MCP server on"),
):
    """Start an MCP server with discovered tools."""
    console.print(f"[bold cyan]🚀 Starting MCP server with tools from:[/bold cyan] {tool_dir}")

    tool_path = Path(tool_dir)
    if not tool_path.exists():
        console.print(f"[red]❌ Directory not found:[/red] {tool_dir}")
        raise typer.Exit(1)

    tool_files = list(tool_path.glob("*.tool.json"))
    if not tool_files:
        console.print(f"[yellow]⚠️  No .tool.json files found in {tool_dir}[/yellow]")
        raise typer.Exit(1)

    console.print(f"[green]Found {len(tool_files)} tools[/green]")

    try:
        from walt.tools.mcp.service import run_mcp_server
        asyncio.run(run_mcp_server(tool_dir, port))
    except ImportError:
        console.print("[red]❌ MCP server not available[/red]")
        raise typer.Exit(1)


def infer_provider(model_name: str) -> str:
    """Infer LLM provider from model name."""
    model_lower = model_name.lower()
    
    # 修改: 优先检测 DeepSeek，并将其指向 OpenAI (兼容协议)
    if "deepseek" in model_lower:
        return "openai"
        
    if model_lower.startswith(("gpt-", "o1-", "o3-", "o4-", "gpt-5")):
        return "openai"
    elif model_lower.startswith(("gemini-", "models/gemini")):
        return "google"
    elif "bedrock" in model_lower or model_lower.startswith(("claude-", "anthropic")):
        return "bedrock"
    else:
        # Default to OpenAI
        console.print(f"[yellow]⚠️  Unknown model prefix, defaulting to OpenAI compatible[/yellow]")
        return "openai"


@app.command()
def agent(
    task: str = typer.Argument(..., help="Task for the agent to perform"),
    tools: Optional[str] = typer.Option(
        None, "--tools", "-t", help="Directory with tool JSON files"
    ),
    start_url: Optional[str] = typer.Option(
        None,
        "--start-url",
        "-u",
        help="Starting URL for the agent (if not provided, LLM will infer)",
    ),
    # 修改: 默认模型改为 deepseek-chat
    llm: str = typer.Option(DEEPSEEK_CONFIG["model"], "--llm", help="LLM model to use"),
    planner_llm: Optional[str] = typer.Option(
        DEEPSEEK_CONFIG["model"], "--planner-llm", help="LLM for planning"
    ),
    planner_interval: int = typer.Option(
        15, "--planner-interval", help="Run planner every N steps"
    ),
    headless: bool = typer.Option(
        False, "--headless/--headed", help="Run browser in headless mode"
    ),
    stealth: bool = typer.Option(
        True, "--stealth/--no-stealth", help="Use patchright for bot detection evasion"
    ),
    max_steps: int = typer.Option(30, "--max-steps", help="Maximum agent steps"),
    save_gif: Optional[str] = typer.Option(
        None,
        "--save-gif",
        "-g",
        help="Save agent history as GIF",
    ),
):
    """Run an agent with optional tool augmentation."""
    
    # 注入 DeepSeek 环境
    setup_deepseek_env(llm)
    if planner_llm:
        setup_deepseek_env(planner_llm)

    console.print(f"[bold cyan]🤖 Running agent:[/bold cyan] {task}")
    if start_url:
        console.print(f"[dim]Start URL: {start_url}[/dim]")
    if tools:
        console.print(f"[dim]Tools: {tools}[/dim]")

    from walt.browser_use.browser.browser import BrowserConfig
    from walt.browser_use.custom.utils import create_llm
    from walt.browser_use.custom.agent_zoo import VWA_Agent
    from walt.browser_use.custom.eval_envs.VWA import (
        VWABrowser,
        VWABrowserContext,
        VWABrowserContextConfig,
    )

    async def run_agent():
        provider = infer_provider(llm)
        # 即使这里传入 deepseek-chat, 因为环境变量已被 setup_deepseek_env 修改，
        # 且 provider 为 openai，所以它会连接 DeepSeek 服务器
        llm_instance = create_llm(provider, llm, temperature=0.0)

        # Create planner LLM
        planner_provider = infer_provider(planner_llm)
        planner_llm_instance = create_llm(planner_provider, planner_llm, temperature=0.0)

        browser_config = BrowserConfig(headless=headless, use_stealth=stealth)
        browser = VWABrowser(browser_config)

        from walt.browser_use import Controller
        from walt.browser_use.custom.skills import register_generic_skills

        controller = Controller()
        register_generic_skills(controller)

        tool_count = 0
        if tools:
            from walt.tools.discovery.register import register_tools_from_directory

            tool_count = register_tools_from_directory(
                controller=controller,
                tool_dir=tools,
                llm=llm_instance,
                logger=console.log,
            )
            console.print(f"[green]Loaded {tool_count} tools[/green]")

        from walt.prompts import build_extended_system_message

        extend_system_message = build_extended_system_message(
            tool_count=tool_count,
        )

        context_config = VWABrowserContextConfig(
            browser_window_size={"width": 1280, "height": 720},
            trace_path=None,
        )
        browser_context = VWABrowserContext(
            browser=browser, config=context_config, som_color="black_transparent"
        )

        from walt.browser_use.custom.skills import verify_with_judge
        from walt.browser_use.custom.skills.models import VerifyAction

        async def verify_callback(
            task_str: str, task_image, agent_history, browser_ctx
        ):
            params = VerifyAction(
                task=task_str,
                task_image_paths=task_image,
                score_threshold=5,
            )
            return await verify_with_judge(params, agent_history, browser_ctx)

        full_task = task
        if start_url:
            full_task = f"{task}\n\nStart by navigating to: {start_url}"

        gif_output = False
        if save_gif is not None:
            gif_output = save_gif if save_gif else "agent_history.gif"

        agent = VWA_Agent(
            task=full_task,
            task_image=None,
            llm=llm_instance,
            browser=browser,
            browser_context=browser_context,
            controller=controller,
            planner_llm=planner_llm_instance,
            planner_interval=planner_interval,
            extend_system_message=extend_system_message,
            expose_tool_actions=tool_count > 0,
            expose_multimodal_actions=True,
            max_actions_per_step=max_steps,
            register_done_callback=verify_callback,
            generate_gif=gif_output,
            retry_delay=1,
        )

        console.print(f"\n[bold cyan]🤖 Starting WALT Agent with DeepSeek[/bold cyan]")
        console.print(f"[dim]├─[/dim] [bold]LLM:[/bold] {llm} ({provider})")
        # ... rest of the logging ...

        history, final_page = await agent.run()
        console.print(f"\n[bold green]✅ Task completed[/bold green]")

        if gif_output:
            console.print(f"[green]📹 GIF saved to {gif_output}[/green]")

        if history.is_done() and history.final_result():
            final_text = history.final_result()
            if final_text and len(final_text) < 200:
                console.print(f"[dim]Result: {final_text}[/dim]")

        # Cleanup code ...
        try:
            await asyncio.wait_for(browser_context.close(), timeout=30.0)
        except Exception:
            pass
        try:
            await asyncio.wait_for(browser.close(), timeout=30.0)
        except Exception:
            pass
        import gc
        gc.collect()

    try:
        asyncio.run(run_agent())
    except KeyboardInterrupt:
        console.print("\n[yellow]⚠️  Interrupted by user[/yellow]")
        raise typer.Exit(0)
    except Exception as e:
        console.print(f"[bold red]❌ Error:[/bold red] {e}")
        raise typer.Exit(1)


@app.command(name="list")
def list_tools(
    tool_dir: str = typer.Argument("walt-tools/", help="Directory containing tools"),
    detailed: bool = typer.Option(False, "--detailed", "-d", help="Show detailed information"),
):
    """List discovered tools."""
    tool_path = Path(tool_dir)

    if not tool_path.exists():
        console.print(f"[yellow]⚠️  Directory not found:[/yellow] {tool_dir}")
        raise typer.Exit(1)

    tool_files = list(tool_path.rglob("*.tool.json"))
    if not tool_files:
        console.print(f"[yellow]No tools found in {tool_dir}[/yellow]")
        raise typer.Exit(0)

    console.print(f"[bold cyan]Found {len(tool_files)} tools in {tool_dir}[/bold cyan]\n")

    if detailed:
        from walt.tools.schema import ToolDefinitionSchema
        table = Table(show_header=True, header_style="bold cyan")
        table.add_column("Tool Name", style="green")
        table.add_column("Description")
        table.add_column("Steps", justify="right")

        for tool_file in sorted(tool_files):
            try:
                schema = ToolDefinitionSchema.load_from_json(str(tool_file))
                table.add_row(
                    tool_file.stem.replace(".tool", ""),
                    (schema.description[:60] + "..." if len(schema.description) > 60 else schema.description),
                    str(len(schema.steps)),
                )
            except Exception as e:
                table.add_row(tool_file.stem, f"[red]Error: {e}[/red]", "-")
        console.print(table)
    else:
        for tool_file in sorted(tool_files):
            console.print(f"  • {tool_file.relative_to(tool_path)}")


@app.command()
def record(
    url: str = typer.Argument(..., help="Website URL to record demonstration on"),
    output: str = typer.Option(
        "recording.tool.json", "--output", "-o", help="Output file for tool"
    ),
    name: str = typer.Option(None, "--name", "-n", help="Tool name"),
    description: str = typer.Option(None, "--description", "-d", help="Tool description"),
):
    """Record a human demonstration and convert to a tool."""
    console.print(f"[bold cyan]🎥 Recording demonstration on:[/bold cyan] {url}")
    try:
        from walt.tools.recorder.service import record_tool
        result = asyncio.run(
            record_tool(
                url=url,
                output_file=output,
                tool_name=name,
                tool_description=description,
            )
        )
        if result:
            console.print(f"\n[bold green]✅ Tool saved to:[/bold green] {output}")
        else:
            console.print("[yellow]⚠️  Recording cancelled[/yellow]")
            raise typer.Exit(1)
    except Exception as e:
        console.print(f"[bold red]❌ Error:[/bold red] {e}")
        raise typer.Exit(1)


def main():
    """Main entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()