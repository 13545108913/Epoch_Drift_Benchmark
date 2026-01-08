"""
Generating trajectories with an exploration loop. This is a revision of the prior exploration loop that I proposed several weeks ago.
"""

import asyncio
import json
import os
import random
import traceback
from typing import Annotated, Optional
from urllib.parse import urlparse

import dotenv
import nest_asyncio
import numpy as np
import typer
from aioconsole import aprint
from playwright.async_api import async_playwright

from skillweaver.agent import codegen_trajectory_to_string
from skillweaver.attempt_task import _is_function_called_in_act_function, attempt_task
from skillweaver.containerization.containers import containers
from skillweaver.environment import Browser, State, make_browsers
from skillweaver.environment.patches import apply_patches
from skillweaver.evaluation.webarena_login import login_subprocess
from skillweaver.knowledge_base.check_success import check_success_simple
from skillweaver.knowledge_base.knowledge_base import (
    Function,
    KnowledgeBase,
    load_knowledge_base,
)
from skillweaver.lm import LM
from skillweaver.templates import generate_practice_args, propose_skill_templ
from skillweaver.util import J
from skillweaver.util.perfmon import monitor


async def _generate_test_case_arguments(lm: LM, state: State, function: Function):
    args = function["args"].copy()
    args.pop("page", None)
    return await lm(
        [
            {
                "role": "system",
                "content": "You are asked to supply test-case arguments for a function.",
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": generate_practice_args(
                            function["name"],
                            function["source"],
                            state.get_axtree_string(),
                        ),
                    },
                    lm.image_url_content_piece(state.screenshot),
                ],
            },
        ],
        json_schema=J.struct(
            step_by_step_reasoning=J.string(),
            args={
                "schema": {
                    "type": "object",
                    "properties": args,
                    "required": list(args.keys()),
                    "additionalProperties": False,
                }
            },
        ),
    )


async def _choose_test_task(
    lm: LM, state: State, knowledge_base: KnowledgeBase, untested: list[Function]
):
    scores = [(knowledge_base.rate_practice_utility(fn), fn) for fn in untested]
    probs = np.array([score for score, _ in scores])
    probs = np.exp(probs) / np.sum(np.exp(probs))
    idx = np.random.choice(len(untested), p=probs)
    function = untested[idx]
    meta = {}
    meta["practice_utility_scores"] = {fn["name"]: score for score, fn in scores}
    args_result = await _generate_test_case_arguments(lm, state, function)
    task_ = {
        "type": "test",
        "function_name": function["name"],
        "function_args": args_result["args"],
    }
    meta["args_result"] = args_result
    meta["task"] = task_

    return (meta, task_)


async def _choose_explore_task(
    lm: LM, state: State, knowledge_base: KnowledgeBase, is_live_website: bool
):
    meta = {}
    procedural_knowledge = "\n".join(
        [f' - {fn["name"]}' for fn in knowledge_base.get_functions()]
    )
    response = await lm(
        [
            {
                "role": "system",
                "content": "You propose tasks that would make good 'tools' for external users of a website.",
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": propose_skill_templ(
                            procedural_knowledge=procedural_knowledge,
                            semantic_knowledge=knowledge_base.semantic_knowledge,
                            ax_tree=state.get_axtree_string(),
                            is_live_website=is_live_website,
                        ),
                    },
                    lm.image_url_content_piece(state.screenshot),
                ],
            },
        ],
        json_schema=J.cot_schema("proposed_skill"),
    )

    await aprint("Task proposal:\n\n" + response["step_by_step_reasoning"])

    # Propose a new task.
    task_ = {"type": "explore", "task": response["proposed_skill"]}
    meta["task"] = task_
    meta["reasoning"] = response["step_by_step_reasoning"]

    return (meta, task_)


def _successfully_executes_function_without_errors(task, last_action):
    if task["type"] != "test":
        return False
    if "python_code" not in last_action or "result" not in last_action:
        return False
    last_has_call_to_test_function = _is_function_called_in_act_function(
        last_action["python_code"], task["function_name"]
    )
    last_has_exception = last_action["result"]["exception"] is not None
    last_has_recovery_attempts = (
        # Has a recovery, this should be put into the knowledge base.
        last_action["result"]["recovery_results"] is not None
        and len(last_action["result"]["recovery_results"]) > 0
    )
    return last_has_call_to_test_function and not (
        last_has_exception or last_has_recovery_attempts
    )


def _should_perform_test(explore_schedule: str, iter_number: int):
    if explore_schedule.startswith("test_probability:"):
        test_chance = float(explore_schedule.split(":")[1])
        do_test = random.random() < test_chance
    else:
        explore_tag, test_tag = explore_schedule.split(",")
        explore_for_n_iters = int(explore_tag.split(":")[1])
        test_for_n_iters = int(test_tag.split(":")[1])
        period = explore_for_n_iters + test_for_n_iters
        do_test = iter_number % period >= explore_for_n_iters

    return do_test


async def _run_explore_iteration(
    store_dir: str,
    iteration: int,
    browser: Browser,
    agent_lm: LM,
    success_check_lm: LM,
    api_synthesis_lm: LM,
    knowledge_base: KnowledgeBase,
    explore_schedule: str,
    is_live_website: bool,
    allow_recovery: bool,
    allow_retrieval_module: bool,
    return_home_every_n_iterations: int,
    base_url: str,
):
    await aprint("Iteration:", iteration)

    iter_dir = f"{store_dir}/iter_{iteration}"
    os.makedirs(iter_dir)

    state = await browser.observe()

    ### CHOOSE A TASK ###
    async with knowledge_base.lock:
        untested_functions = knowledge_base.get_untested_functions()
        if (
            _should_perform_test(explore_schedule, iteration)
            and len(untested_functions) > 0
        ):
            meta, task = await _choose_test_task(
                agent_lm, state, knowledge_base, untested_functions
            )
        else:
            meta, task = await _choose_explore_task(
                agent_lm, state, knowledge_base, is_live_website
            )

    with open(iter_dir + "/choose_task_meta.json", "w") as f:
        json.dump(meta, f, indent=2)

    await aprint("Task:\n" + json.dumps(task, indent=2))

    ### ATTEMPT THE TASK ###
    try:
        await browser.context.tracing.start(snapshots=True, screenshots=True)

        (states, actions) = await attempt_task(
            browser,
            agent_lm,
            task,
            max_steps=10,
            knowledge_base=knowledge_base,
            store_dir=iter_dir,
            allow_recovery=allow_recovery,
            enable_retrieval_module_for_exploration=allow_retrieval_module,
        )  # type: ignore

        # Write trajectory as string for easy inspection.
        trajectory_string = codegen_trajectory_to_string(states, actions)

        with open(iter_dir + "/trajectory_pretty.txt", "w") as f:
            f.write(trajectory_string)

        if task["type"] == "test":
            task_string = f'Test the function {task["function_name"]} with args {json.dumps(task["function_args"], indent=2)}'
        elif task["type"] == "explore":
            task_string = task["task"]

        # Apply an update to the knowledge base.
        async with knowledge_base.lock:
            if _successfully_executes_function_without_errors(task, actions[-1]):
                knowledge_base.increment_test_count(
                    task["function_name"], "iter_" + str(iteration)
                )
            else:
                # Check for success.
                success_check = await check_success_simple(
                    success_check_lm,
                    task_string,
                    trajectory_string,
                    states[-1].screenshot,
                )
                with open(f"{iter_dir}/success_check.json", "w") as f:
                    json.dump(success_check, f, indent=2)

                if success_check["success"]:
                    await aprint("Successful attempt! Updating knowledge base...")
                    update_diagnostics = await knowledge_base.update(
                        api_synthesis_lm,
                        task,
                        trajectory_string,
                        f"iter_{iteration}",
                    )
                    with open(f"{iter_dir}/kb_update_diagnostics.json", "w") as f:
                        json.dump(update_diagnostics, f, indent=2)

            knowledge_base.save(f"{iter_dir}/kb_post")

        # Store the performance monitoring.
        with open(iter_dir + "/perfmon.json", "w") as f:
            json.dump(monitor.as_dict(), f)
        monitor.reset()

    except Exception as e:
        await aprint(f"Error in iteration {iteration}: {e}")
        await aprint(traceback.format_exc())

        with open(f"{iter_dir}/error.txt", "w") as f:
            f.write(traceback.format_exc())

    finally:
        await browser.context.tracing.stop(path=f"{iter_dir}/trace.zip")

    ### This is ONLY if we want to return to the homepage every iteration. ###
    # Another approach which only returns to homepage if we left the original website
    # (or return_home_every_n_iterations has passed)

    # add information seeksing
    same_host = urlparse(browser.active_page.url).netloc == urlparse(base_url).netloc
    extension_of_root = urlparse(browser.active_page.url).path.startswith(
        urlparse(base_url).path
    )
    go_back_home = (
        not same_host
        or not extension_of_root
        or (iteration + 1) % return_home_every_n_iterations == 0
    )
    if go_back_home:
        await browser.active_page.goto(base_url)


async def explore(
    agent_lm: LM,
    success_check_lm: LM,
    api_synthesis_lm: LM,
    base_urls: list[str],
    storage_states: list[str | None],
    iterations: int,
    store_dir: str,
    is_live_website: bool,
    allow_recovery: bool,
    initial_knowledge_base: KnowledgeBase | None,
    # can be "test_probability:X" or "explore:X,test:Y" to alternate between exploration and testing (explore X iters, and test Y iters)
    explore_schedule: str,
    return_home_every_n_iterations: int,
    allow_retrieval_module: bool,
    # Number of workers to use for parallel exploration.
    num_workers: int,
):
    os.makedirs(store_dir, exist_ok=True)
    with open(store_dir + "/explore_params.json", "w") as f:
        json.dump(
            {
                "agent_lm_name": agent_lm.model,
                "success_check_lm_name": success_check_lm.model,
                "api_synthesis_lm_name": api_synthesis_lm.model,
                "host": base_urls,
                "iterations": iterations,
                "is_live_website": is_live_website,
                "storage_state": storage_states,
                "allow_recovery": allow_recovery,
            },
            f,
            indent=2,
        )

    knowledge_base = initial_knowledge_base or KnowledgeBase()
    worker_availabilities = [True] * num_workers
    worker_semaphore = asyncio.Semaphore(num_workers)
    global_iter_num = 0

    async def _find_worker_and_run_iteration():
        nonlocal global_iter_num

        async with worker_semaphore:
            iteration = global_iter_num
            global_iter_num += 1

            worker_idx = worker_availabilities.index(True)
            worker_availabilities[worker_idx] = False

            browser = browsers[worker_idx]
            base_url = base_urls[worker_idx]

            try:
                await _run_explore_iteration(
                    store_dir,
                    iteration,
                    browser,
                    agent_lm,
                    success_check_lm,
                    api_synthesis_lm,
                    knowledge_base,
                    explore_schedule,
                    is_live_website,
                    allow_recovery,
                    allow_retrieval_module,
                    return_home_every_n_iterations,
                    base_url=base_url,
                )
            finally:
                worker_availabilities[worker_idx] = True

    async with async_playwright() as playwright:
        browsers = await make_browsers(
            playwright,
            base_urls,
            storage_states,
            headless=True,
            video_dirs=[store_dir + "/videos_" + str(i) for i in range(num_workers)],
        )
        try:

            await asyncio.gather(
                *[_find_worker_and_run_iteration() for _ in range(iterations)]
            )

        finally:
            # Close all browsers.
            await asyncio.gather(*[browser.close() for browser in browsers])


def _get_dir(path: str):
    if "{i}" not in path:
        return path
    i = 0
    while os.path.exists(path.format(i=i)):
        i += 1

    return path.format(i=i)


def cli(
    website: str,
    out_dir: str,
    knowledge_base_path_prefix: Optional[str] = None,
    iterations: int = 160,
    agent_lm_name: str = "gpt-4o",
    api_synthesis_lm_name: str = "o3-mini",
    success_check_lm_name: str = "gpt-4o",
    allow_recovery: bool = True,
    allow_retrieval_module: bool = True,
    explore_schedule: Annotated[
        str,
        typer.Option(
            help="Can be 'test_probability:X' or 'explore:X,test:Y' to alternate between exploration and testing (explore X iters, and test Y iters)"
        ),
    ] = "test_probability:0.5",
    num_workers: int = 8,
):
    out_dir = _get_dir(out_dir)
    os.makedirs(out_dir, exist_ok=True)

    # Always apply patches.
    apply_patches()

    initial_knowledge_base = (
        load_knowledge_base(knowledge_base_path_prefix, discard_references=True)
        if knowledge_base_path_prefix is not None
        else None
    )

    agent_lm = LM(agent_lm_name)
    success_check_lm = LM(success_check_lm_name)

    """
    For example, "o3-mini-2025-01-31:medium" would be interpreted as the LM "o3-mini-2025-01-31" with the reasoning effort set to "medium".
    """
    if ":" in api_synthesis_lm_name:
        api_synthesis_lm_name, api_synthesis_reasoning_effort = (
            api_synthesis_lm_name.split(":")
        )
        api_synthesis_lm = LM(
            api_synthesis_lm_name,
            default_kwargs={"reasoning_effort": api_synthesis_reasoning_effort},
        )
    else:
        api_synthesis_lm = LM(api_synthesis_lm_name)

    async def inner():
        try:
            # 1. GitLab 处理逻辑
            if website == "gitlab":
                target_url = os.getenv("GITLAB", "http://172.26.116.102:8080")
                print(f"正在连接远程 GitLab: {target_url}")
                
                base_urls = [target_url] * num_workers
                storage_states = []

                for i in range(num_workers):
                    print(f"Worker {i}: 正在尝试自动登录 GitLab...")
                    try:
                        state = login_subprocess({"gitlab": target_url})
                        storage_states.append(state)
                        print(f"Worker {i}: 登录成功！")
                    except Exception as e:
                        print(f"Worker {i}: 自动登录失败，将以未登录状态继续。错误: {e}")
                        storage_states.append(None)

                await explore(
                    agent_lm=agent_lm,
                    success_check_lm=success_check_lm,
                    api_synthesis_lm=api_synthesis_lm,
                    base_urls=base_urls,
                    storage_states=storage_states,
                    iterations=iterations,
                    store_dir=os.path.abspath(out_dir),
                    is_live_website=False,
                    initial_knowledge_base=initial_knowledge_base,
                    allow_recovery=allow_recovery,
                    explore_schedule=explore_schedule,
                    allow_retrieval_module=allow_retrieval_module,
                    return_home_every_n_iterations=1,
                    num_workers=num_workers,
                )

            # 2. [新增] Shopping Admin 处理逻辑
            elif website == "shopping_admin":
                target_url = "http://dockerized-magento.local/index.php/admin/"
                print(f"正在连接 Shopping Admin: {target_url}")

                base_urls = [target_url] * num_workers
                storage_states = []

                for i in range(num_workers):
                    print(f"Worker {i}: 正在尝试自动登录 Shopping Admin...")
                    try:
                        # 传入 "shopping_admin" 作为 key，以便 login_subprocess 查找对应的账号密码
                        state = login_subprocess({"shopping_admin": target_url})
                        storage_states.append(state)
                        print(f"Worker {i}: 登录成功！")
                    except Exception as e:
                        print(f"Worker {i}: 自动登录失败，将以未登录状态继续。错误: {e}")
                        storage_states.append(None)

                await explore(
                    agent_lm=agent_lm,
                    success_check_lm=success_check_lm,
                    api_synthesis_lm=api_synthesis_lm,
                    base_urls=base_urls,
                    storage_states=storage_states,
                    iterations=iterations,
                    store_dir=os.path.abspath(out_dir),
                    is_live_website=False,
                    initial_knowledge_base=initial_knowledge_base,
                    allow_recovery=allow_recovery,
                    explore_schedule=explore_schedule,
                    allow_retrieval_module=allow_retrieval_module,
                    return_home_every_n_iterations=1,
                    num_workers=num_workers,
                )

            # 3. 其他通用网站处理逻辑
            else:
                target_url = "http://localhost:8000"
                print(f"正在连接 Wordpress: {target_url}")

                base_urls = [target_url] * num_workers
                await explore(
                    agent_lm=agent_lm,
                    success_check_lm=success_check_lm,
                    api_synthesis_lm=api_synthesis_lm,
                    base_urls=base_urls,
                    storage_states=[None] * num_workers,
                    iterations=iterations,
                    store_dir=os.path.abspath(out_dir),
                    is_live_website=False,
                    initial_knowledge_base=initial_knowledge_base,
                    allow_recovery=allow_recovery,
                    explore_schedule=explore_schedule,
                    allow_retrieval_module=allow_retrieval_module,
                    return_home_every_n_iterations=1,
                    num_workers=num_workers,
                )
        except Exception as e:
            await aprint(f"Error: {e}")
            await aprint(traceback.format_exc())
            with open(f"{out_dir}/error.txt", "w") as f:
                f.write(traceback.format_exc())
        finally:
            os._exit(0)

    asyncio.run(inner())


if __name__ == "__main__":
    dotenv.load_dotenv()
    nest_asyncio.apply()

    typer.run(cli)
