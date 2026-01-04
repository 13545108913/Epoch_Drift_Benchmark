"""Induce Actions on the Full Task Level."""

import os
import gzip
import json
import pickle
import openai 
import argparse
import subprocess
from induce.utils import (
    extract_code_pieces, get_task_id, get_result_dirs,
    get_output_dir
)
import logging  # <--- 新增
import sys      # <--- 新增

# === 【新增】配置日志，确保 HTTP 请求信息能被打印出来 ===
# 只有配置了 logging，openai/httpx 才会输出 "HTTP Request: POST ..."
logging.basicConfig(
    format='%(asctime)s - %(process)d - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    level=logging.INFO,  # 必须是 INFO 级别
    stream=sys.stderr    # 输出到 stderr，主脚本会捕获这个流
)
# 强制设置 httpx 的日志级别，防止被其他库屏蔽
logging.getLogger("httpx").setLevel(logging.INFO) 
# ========================================================

MY_API_KEY = os.getenv("my_api_key")
MY_BASE_URL = os.getenv("my_base_url")
MY_MODEL = os.getenv("my_model")

client = openai.OpenAI(
    api_key=MY_API_KEY,
    base_url=MY_BASE_URL
)
# %% Induce Actions

def get_example_query_filtered(index: int, result_dir: str, config_dir: str) -> tuple[str, str]:
    """Get the string for a past example experience, without invalid actions."""
    cid = get_task_id(result_dir)
    config_path = os.path.join(config_dir, f"{cid}.json")
    config = json.load(open(config_path))
    instruction = config["intent"]
    task = config["intent_template"]

    step_dirs = [f for f in os.listdir(result_dir) if f.startswith("step") and f.endswith(".pkl.gz")]
    step_dirs = sorted(step_dirs, key=lambda x: int(x.split('.')[0].split('_')[1]))
    step_dirs = [os.path.join(result_dir, sd) for sd in step_dirs]
    steps = []
    for sd in step_dirs:
        step_info = pickle.load(gzip.open(sd, 'rb'))
        error_msg = step_info.obs["last_action_error"]
        if len(error_msg) > 0 and (not error_msg.startswith("TimeoutError")):
            continue  # skip error actions
        if len(step_info.obs["last_action"]) == 0:
            continue  # skip empty actions
        steps.append(step_info.obs["last_action"])

    if len(steps) > 0:
        print(f"Collected #{len(steps)} valid steps from a total of #{len(step_dirs)} steps.")
        steps = '\n'.join(steps)
        ex = f"### Example {index} ({config['task_id']}): {instruction}\n{steps}"
    else:
        ex = None
    return ex, task


def get_example_query_cleaned(index: int, result_dir: str, config_dir: str) -> str:
    """Get the string for a past example experience, without invalid actions."""
    # get config
    cid = get_task_id(result_dir)
    config_path = os.path.join(config_dir, f"{cid}.json")
    config = json.load(open(config_path))

    # get instruction
    subtask_inst_path = os.path.join(result_dir, "instruction.txt")
    if os.path.exists(subtask_inst_path):  # sub task
        instruction = open(subtask_inst_path, 'r').read()
        task = instruction
    else:  # full task
        instruction = config["intent"]
        task = config["intent_template"]

    steps = json.load(open(os.path.join(result_dir, "cleaned_steps.json")))
    if len(steps) > 0:
        print(f"Collected #{len(steps)} valid steps.")
        steps = '\n'.join(steps)
        ex = f"### Example {index} ({config['task_id']}): {instruction}\n{steps}"
    else:
        ex = None

    return ex, task

def get_test_query(result_dir_list: str, config_dir: str) -> str:
    """Transform past examples into a test query."""
    task = None
    examples = []
    for rdir in result_dir_list:
        ex, task = get_example_query_cleaned(len(examples)+1, rdir, config_dir)
        if ex is None: continue
        examples.append(ex)
    
    if len(examples) < 1:
        return None
    query = f"## Task: {task}\n" + '\n\n'.join(examples)
    return query


def induce_actions() -> list[str] | None:
    result_dir_list = get_result_dirs(args.results_dir, args.result_id_list, args.template_id, args.config_dir)
    test_query = get_test_query(result_dir_list, args.config_dir)
    if test_query is None: return []
    with open(args.test_query_path, 'w') as fw: fw.write(test_query)

    messages = [{"role": "system", "content": open(args.sys_msg_path).read()}]
    messages += [{"role": "user", "content": open(args.instruction_path).read()}]
    # messages += [{"role": "user", "content": open(args.few_shot_path).read()}]
    # # messages += [{"role": "user", "content": "## Existing Actions\n" + open(args.write_action_path).read()}]
    # messages += [{"role": "user", "content": test_query + '\n\n## Reusable Functions'}]

    # --- 修改开始 ---
    # 不要直接添加 few-shot，而是用指令“包装”它
    messages += [{
        "role": "user", 
        "content": (
            "Here is a complete example of the task, showing the desired input and output format. "
        )
    }]

    # 现在添加示例本身
    messages += [{"role": "user", "content": open(args.few_shot_path).read()}]

    # 添加一个明确的指令，告诉它真实任务现在开始
    messages += [{
        "role": "user",
        "content": (
            "That was the example. "
            "Now, please solve the following new task. "
            "Provide ONLY the answer for this new task."
        )
    }]
    # --- 修改结束 ---

    # messages += [{"role": "user", "content": "## Existing Actions\n" + open(args.write_action_path).read()}]
    messages += [{"role": "user", "content": test_query + '\n\n## Reusable Functions'}]
    # ... 后续代码 ...

    all_responses = []

    # *** 修改部分：替换了 litellm 的 if/else 逻辑块 ***
    response = client.chat.completions.create(
        model=MY_MODEL,
        messages=messages,
        temperature=args.temperature,
        n=args.num_responses,
    )
    for i, resp in enumerate(response.choices):
        curr_resp = resp.message.content
        curr_path = os.path.join(args.output_dir, f"{i}.md")
        with open(curr_path, 'w') as fw:
            fw.write(test_query + '\n\n\n' + curr_resp)
        all_responses.append(curr_resp)
    # *** 修改结束 ***

    return all_responses



# %% Process Actions
from induce.utils import count_function_calls, get_function_names

def write_actions(response: str) -> tuple[str, list[str]]:
    """Extract actions from response and write actions to agent action loading file."""
    existing_action_names = get_function_names(open(args.write_action_path, 'r').read())
    # extract induced actions from the response
    actions = extract_code_pieces(response, start="```python", end="```", do_split=False)
    actions = [a for a in actions if "def " in a and count_function_calls(a, 2)]
    new_actions, action_names = [], []
    for a in actions:
        if ("def " in a) and count_function_calls(a, 2):
            a_names = get_function_names(a, existing_action_names)
            if len(a_names) > 0:
                action_names.extend(a_names)
                new_actions.append(a)

    print(
        f"Induced #{len(new_actions)}|{len(action_names)} Actions, ",
        [a.split("\n")[0] for a in new_actions],
        action_names
    )
    # cont = input("Continue? (y/n): ")
    if len(new_actions) == 0: return None, None

    tmp_path = args.write_action_path + ".tmp"
    process = subprocess.Popen(["cp", args.write_action_path, tmp_path])
    process.wait()

    with open(args.write_action_path, 'a+') as fw:
        fw.write('\n\n'+ '\n\n'.join(new_actions))
    return tmp_path, action_names



# %% Run Tests
from induce.utils import parse_tests

def write_tests(response: str, result_id_list: list[str], action_names: list[str] = []) -> bool:
    """Extract tests, write tests to file, and run tests.
    Args:
        response: model generated response including induced actions, tests, and texts.
        result_id_list: list of task result IDs.
        action_names: list of names of the induced actions to test on.
    Returns:
        bool: If all tests passed the check.
    """
    tests = parse_tests(response, action_names)
    assert len(tests) == len(result_id_list), f"Got #{len(tests)} tests but for #{len(result_id_list)} results."
    
    # write tests and script
    script_content = []
    for i, (t, r) in enumerate(zip(tests, result_id_list)):
        # write test trajectory
        test_path = os.path.join(args.write_tests_dir, f"test_{i}.txt")
        test_str = '\n'.join([f"```{tl.strip()}```" for tl in t.split('\n') if tl.strip()])
        with open(test_path, 'w') as fw:  # overwrite existing content
            fw.write(test_str)
        
        # write test script
        script_content.append(f"# Run test for task {r}")
        script_content.append(
            f"python run_demo.py --websites {args.website} --headless "
            f"--task_name myBenchmark.{r.split('_')[0]} "
            f"--action_path {test_path} "
            f"--rename_to myBenchmark.{r.split('_')[0]}_test",
        )
        script_content.append("\n")
    
    test_script_path = os.path.join(args.write_tests_dir, "run_tests.sh")
    with open(test_script_path, 'w') as fw:
        fw.write('\n'.join(script_content))
    
    # === 【修改】优化子进程调用，确保孙子进程的日志能实时传给主脚本 ===
    # 使用 sys.stdout/stderr 作为输出目标，确保流式透传
    print(f"Running tests via {test_script_path} ...")
    process = subprocess.Popen(
        ["bash", test_script_path],
        stdout=sys.stdout, # 显式指向标准输出
        stderr=sys.stderr  # 显式指向标准错误 (log在这里)
    )
    
    try:
        # 等待结束，而不是用 communicate() 缓冲所有输出
        process.wait(timeout=500) 
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()
        print(f"Process timed out after 500 seconds.")
        return True  # revert
    # =================================================================

    # check test results
    scores = []
    for r in result_id_list:
        if True:
            eval_path = os.path.join(args.results_dir, f"myBenchmark.{r}_test", "summary_info.json")
            if os.path.exists(eval_path):
                scores.append(json.load(open(eval_path))["cum_reward"] == 1.0)
            else:
                scores.append(False)
        else:
            process = subprocess.Popen([
                "python", "-m", "autoeval.evaluate_trajectory",
                "--result_dir", os.path.join(args.results_dir, f"myBenchmark.{r}_test")
            ])
            process.wait()

            eval_path = os.path.join(args.results_dir, f"myBenchmark.{r}_test", "autoeval.json")
            if os.path.exists(eval_path):
                scores.append(json.load(open(eval_path))[0]["rm"] == True)
            else:
                scores.append(False)

        # check step valid and use actions
        command = [
            "python", "-m", "results.calc_valid_steps",
            "--result_dir", os.path.join(args.results_dir, f"myBenchmark.{r}_test"),
            "--action_names"] + action_names
        process = subprocess.Popen(command, stdout=subprocess.PIPE)
        process.wait()
        output = process.communicate()[0].decode("utf-8").strip()
        output = output.split('\n')[-1].strip()
        print("Validity Check: ", output)
        if output == 'False': scores[-1] = False

        if scores[-1] == False: break
    
    print("Scores: ", scores)
    if all([s == True for s in scores]):
        print("All Tests Passed!")
        return False
    else:
        return True


# %% Overall pipeline

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=str, default="claude", choices=["gpt-4o", "claude"])
    parser.add_argument("--num_responses", type=int, default=1, help="Number of responses to generate.")
    parser.add_argument("--temperature", type=float, default=1.0, help="Temperature for sampling.")

    parser.add_argument("--sys_msg_path", type=str, default="induce/prompt/system_message.txt")
    parser.add_argument("--instruction_path", type=str, default="induce/prompt/instruction.txt")
    parser.add_argument("--few_shot_path", type=str, default="induce/prompt/shopping.md")
    parser.add_argument("--test_query_path", type=str, default="induce/prompt/test_query.txt")

    parser.add_argument("--template_id", type=str, default=None)
    parser.add_argument("--website", type=str, required=True,
                        choices=["shopping", "admin", "reddit", "gitlab", "map", "wordpress"])
    parser.add_argument("--config_dir", type=str, default="config_files")
    parser.add_argument("--results_dir", type=str, default="results")
    parser.add_argument("--result_id_list", type=str, nargs="+", default=None, help="E.g., '110 111'.")

    parser.add_argument("--write_action_path", type=str, default=None)
    parser.add_argument("--write_tests_dir", type=str, default="debug_actions")
    # parser.add_argument("--eval_with_gold", action="store_true", help="If perform evaluation with ground-truth.")
    args = parser.parse_args()

    # decide model name
    if args.model == "claude":
        args.model = "litellm/neulab/claude-3-5-sonnet-20241022"
    # args.model = args.model.replace("litellm", "openai")

    # decide path to write actions
    if args.write_action_path is None:
        args.write_action_path = os.path.join("actions", f"{args.website}.py")

    # decide path for entire model output
    args = get_output_dir(args)
    if os.path.exists(args.output_dir):
        print(f"Output directory already exists: {args.output_dir}")
        names = sorted(os.listdir(args.output_dir), key=lambda x: int(x.split('.')[0]))
        paths = [os.path.join(args.output_dir, f) for f in names]
        responses = [open(p, 'r').read() for p in paths]
    else:  # induce new actions
        os.makedirs(args.output_dir, exist_ok=True)
        responses = induce_actions()
    
    # write actions and run tests
    print(f"Collected {len(responses)} Responses..")
    for i, resp in enumerate(responses):
        print(f"\n\n** Start Evaluating Response {i}: ", resp, "**")
        tmp_path, action_names = write_actions(resp)
        if tmp_path is None: continue

        if_revert = write_tests(resp, args.result_id_list, action_names)
        print("If Revert: ", if_revert)
        if if_revert:
            process = subprocess.Popen(["mv", tmp_path, args.write_action_path])
            process.wait()
            # cont = input("Continue? (y/n): ")
            for i, r in enumerate(args.result_id_list):
                print("Command: ", ["rm", "-rf", f"results/myBenchmark.{r}_test"])
                process = subprocess.Popen(["rm", "-rf", f"results/myBenchmark.{r}_test"])
                process.wait()
                # cont = input("Continue? (y/n): ")
        else:
            process = subprocess.Popen(["rm", tmp_path])
            process.wait()
            break
            
        print(f"** Finish Evaluating Response {i}: ", resp, "**\n\n")
        