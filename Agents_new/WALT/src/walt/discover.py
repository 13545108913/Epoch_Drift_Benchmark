import asyncio
import argparse
import sys
import os
import traceback
from types import SimpleNamespace
from pathlib import Path

# 尝试导入依赖，如果环境没配置好给出提示
try:
    from rich.console import Console
    # 假设该脚本与 walt 包在同一级目录，或者 walt 已安装在环境中
    from walt.tools.discovery import propose, generate
except ImportError as e:
    print(f"Error importing dependencies: {e}")
    print("Please ensure you have installed the requirements and the 'walt' package is accessible.")
    sys.exit(1)

console = Console()

async def discovery_main_async(args):
    """
    运行通用的发现流程 (逻辑提取自 cli.py)
    """
    os.makedirs(args.output_dir, exist_ok=True)

    console.print(f"[dim]📁 Output directory: {args.output_dir}[/dim]")

    # Phase 1: Discovery
    console.print("\n[bold cyan]🔍 Phase 1: Discovering candidate tools...[/bold cyan]")
    try:
        tools_json = await propose.discover_candidates(args)
        console.print(f"[green]✅ Found {len(tools_json)} candidate tools[/green]")
    except Exception as e:
        console.print(f"[bold red]❌ Error during discovery phase:[/bold red] {e}")
        console.print(traceback.format_exc())
        return

    # Phase 2: Generation
    console.print("\n[bold cyan]🚀 Phase 2: Generating tools...[/bold cyan]")
    
    # 重新加载 candidates (为了保持与原有逻辑一致，通常 propose 会保存文件)
    tools_json = propose.load_existing_candidates(args)
    if not tools_json:
        console.print("[yellow]⚠️  No candidates found[/yellow]")
        return

    try:
        success_count = await generate.generate_tools(args, tools_json)
        console.print(
            f"[green]✅ Generated {success_count}/{len(tools_json)} tools successfully[/green]"
        )
    except Exception as e:
        console.print(f"[bold red]❌ Error during generation phase:[/bold red] {e}")
        console.print(traceback.format_exc())

def main():
    parser = argparse.ArgumentParser(
        description="🪄 WALT Discovery: Automatic tool discovery from websites (Standalone Script)"
    )

    parser.add_argument(
        "--url", 
        required=True, 
        help="Base URL to discover tools from (e.g., https://example.com)"
    )
    parser.add_argument(
        "--output", "-o", 
        dest="output_dir",
        default=None, 
        help="Output directory for discovered tools"
    )
    parser.add_argument(
        "--llm", 
        default="gpt-5-mini", 
        help="LLM model to use"
    )
    parser.add_argument(
        "--planner-llm", 
        default=None, 
        help="Planner LLM model (defaults to same as --llm)"
    )
    parser.add_argument(
        "--auth-file", 
        default=None, 
        help="Playwright storage_state JSON file for authentication"
    )
    parser.add_argument(
        "--max-processes", "-p", 
        type=int, 
        default=16, 
        help="Max concurrent processes"
    )
    parser.add_argument(
        "--force-regenerate", 
        action="store_true", 
        help="Force regeneration of existing tools"
    )
    parser.add_argument(
        "--skip-test", 
        action="store_true", 
        help="Skip testing generated tools"
    )
    parser.add_argument(
        "--optimize", 
        action="store_true", 
        help="Generate optimized versions of tools"
    )

    args = parser.parse_args()

    console.print(f"[bold cyan]🔍 Discovering tools from:[/bold cyan] {args.url}")

    # 处理 output_dir (如果没有指定，则根据 URL 生成)
    if not args.output_dir:
        domain = args.url.replace("https://", "").replace("http://", "").split("/")[0]
        output_dir = f"walt-tools/{domain}"
    else:
        output_dir = args.output_dir

    if args.auth_file:
        console.print(f"[dim]🔑 Using authentication: {args.auth_file}[/dim]")

    # 构造 SimpleNamespace 以匹配 walt 内部函数期望的参数结构
    # 这一步是为了模拟 Typer/CLI 在原有代码中传递的 context 对象
    internal_args = SimpleNamespace(
        url=args.url,
        base_url=args.url,
        output_dir=output_dir,
        llm=args.llm,
        planner_llm=args.planner_llm or args.llm,
        auth_file=args.auth_file,
        max_processes=args.max_processes,
        force_regenerate=args.force_regenerate,
        test=not args.skip_test, # 注意这里取反
        optimize=args.optimize,
        discover=True,
        generate=True
    )

    # 运行异步主流程
    try:
        asyncio.run(discovery_main_async(internal_args))
        console.print(f"\n[bold green]✅ Discovery complete![/bold green]")
        console.print(f"[dim]Tools saved to: {internal_args.output_dir}[/dim]")
    except KeyboardInterrupt:
        console.print("\n[yellow]⚠️  Discovery interrupted by user[/yellow]")
        sys.exit(130)
    except Exception as e:
        console.print(f"\n[bold red]❌ Error:[/bold red] {e}")
        console.print(f"[dim]{traceback.format_exc()}[/dim]")
        sys.exit(1)

if __name__ == "__main__":
    main()