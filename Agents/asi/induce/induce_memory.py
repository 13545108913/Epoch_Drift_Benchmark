import os
import json
import openai 
import argparse
from induce.utils import get_output_dir, get_task_id, extract_code_pieces
import logging
import sys

# === 【配置】日志设置 ===
logging.basicConfig(
    format='%(asctime)s - %(process)d - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    level=logging.INFO,
    stream=sys.stderr
)
logging.getLogger("httpx").setLevel(logging.INFO) 
# ========================

# === 【配置】DeepSeek API 设置 ===
DEEPSEEK_API_KEY = "sk-41fae6597fd14d6fa2c5c4068c0e5760"
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-chat"

# 初始化 OpenAI 客户端以调用 Deepseek
client = openai.OpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url=DEEPSEEK_BASE_URL
)

# %% Induce Memory

def get_example_query_cleaned(index: int, result_dir: str, config_dir: str) -> str:
    """Get the string for a past example experience, without invalid actions."""
    cid = get_task_id(result_dir)
    config_path = os.path.join(config_dir, f"{cid}.json")
    config = json.load(open(config_path))

    subtask_inst_path = os.path.join(result_dir, "instruction.txt")
    if os.path.exists(subtask_inst_path):
        instruction = open(subtask_inst_path, 'r').read()
        task = instruction
    else:
        instruction = config["intent"]
        task = config["intent_template"]

    steps_path = os.path.join(result_dir, "cleaned_steps.json")
    if os.path.exists(steps_path):
        steps = json.load(open(steps_path))
        if len(steps) > 0:
            print(f"Collected #{len(steps)} valid steps.")
            steps = '\n'.join(steps)
            ex = f"### Example {index} ({config['task_id']}): {instruction}\n{steps}"
        else:
            ex = None
    else:
        ex = None

    return ex, task
    

def get_test_query(result_dir_list: list, config_dir: str) -> str | None:
    """Transform each result log into an input experience and form a query."""
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


def induce_workflows() -> list[str]:
    # === 修改：根据传入的单个 result_id 查找对应的结果目录 ===
    target_id = args.result_id_list
    result_dir_list = []
    
    # 遍历结果目录，寻找包含该 ID 的文件夹
    if os.path.exists(args.results_dir):
        for d in os.listdir(args.results_dir):
            full_path = os.path.join(args.results_dir, d)
            # 简单匹配：如果文件夹名包含 ID (如 "110" 在 "webarena.110_2_0" 中) 且是文件夹
            if str(target_id) in d and os.path.isdir(full_path):
                result_dir_list.append(full_path)
    
    if not result_dir_list:
        print(f"Warning: No result directories found for ID '{target_id}' in '{args.results_dir}'")
        return []
    
    print(f"Found {len(result_dir_list)} result directories for ID {target_id}: {result_dir_list}")
    # =======================================================

    test_query = get_test_query(result_dir_list, args.config_dir)
    if test_query is None: return []
    with open(args.test_query_path, 'w') as fw:
        fw.write(test_query)

    messages = [{"role": "system", "content": open(args.sys_msg_path).read()}]
    messages += [{"role": "user", "content": open(args.instruction_path).read()}]
    # messages += [{"role": "user", "content": open(args.few_shot_path).read()}]
    # messages += [{"role": "user", "content": "## Existing Workflows\n" + open(args.write_workflow_path).read()}]
    # messages += [{"role": "user", "content": test_query + '\n\n## Reusable Workflows'}]

    messages += [{
        "role": "user", 
        "content": (
            "Here is a complete example of the task, showing the desired input and output format. "
        )
    }]

    # 现在添加示例本身
    messages += [{"role": "user", "content": open(args.few_shot_path).read()}]

    messages += [{
        "role": "user",
        "content": (
            "That was the example. "
            "Now, please solve the following new task. "
            "Provide ONLY the answer for this new task."
        )
    }]
    messages += [{"role": "user", "content": "## Existing Workflows\n" + open(args.write_workflow_path).read()}]
    messages += [{"role": "user", "content": test_query + '\n\n## Reusable Workflows'}]

    all_responses = []

    # === 使用 DeepSeek Client 生成工作流 ===
    print(f"Calling DeepSeek ({DEEPSEEK_MODEL}) for induce_workflows...")
    try:
        response = client.chat.completions.create(
            model=DEEPSEEK_MODEL,
            messages=messages,
            temperature=args.temperature,
            n=args.num_responses, 
            stream=False
        )
        
        for i, resp in enumerate(response.choices):
            curr_resp = resp.message.content
            curr_path = os.path.join(args.output_dir, f"{i}.md")
            with open(curr_path, 'w') as fw:
                fw.write(test_query + '\n\n\n' + curr_resp)
            all_responses.append(curr_resp)
            
    except Exception as e:
        print(f"Error during induce_workflows API call: {e}")
        return []
    # ==========================================

    return all_responses

# %% Write Workflows

def get_workflow_name(workflow: str) -> str:
    """Get the name of the workflow."""
    name = workflow.split('\n')[0].lstrip("Task: ").strip()
    return name


def update_workflows(workflow: str, existing_workflows: list[str]) -> tuple[bool, list[str]]:
    """Update the existing workflows given the potentially topically similar new item."""
    name = get_workflow_name(workflow)
    for ew in existing_workflows:
        ew_name = get_workflow_name(ew)
        messages = [
            {"role": "system", "content": "You are an expert in navigating the web, your task is to check if the two workflows refer to the same task."},
            {"role": "user", "content": "Does the following two workflows refer to the same task? Only return 'yes' or 'no', do not provide any additional information."},
            {"role": "user", "content": f"Workflow 1: {name}\nWorkflow 2: {ew_name}"}
        ]
        
        # === 替换 litellm 为 DeepSeek Client ===
        try:
            response = client.chat.completions.create(
                model=DEEPSEEK_MODEL,
                messages=messages,
                temperature=args.temperature,
            )
            response_text = response.choices[0].message.content.lower()
        except Exception as e:
            print(f"Error checking overlap: {e}")
            response_text = "no" 
        # ===========================================
        
        if 'yes' in response_text: yes_index = response_text.index('yes')
        else: yes_index = 0
        if 'no' in response_text: no_index = response_text.index('no')
        else: no_index = len(response_text)
        
        if yes_index < no_index:
            print(f"Checking Overlap between [{name}] & [{ew_name}] => YES")
            better_workflow = get_better_workflow(workflow, ew)
            if better_workflow is None:
                better_workflow = ew 
                
            action = "KEEP" if better_workflow == ew else "REPLACE"
            print(f"Better Workflow: {get_workflow_name(better_workflow)} \n=> {action}")
            if better_workflow == ew: 
                return False, []
            else:  
                return True, [ew_name]
                
    print(f"Checking Overlap between [{name}] & [{len(existing_workflows)} Existing Workflows] => NO")
    return True, []


def get_better_workflow(workflow1: str, workflow2: str) -> str:
    """Select the better workflow between two topically-overlapping workflows."""
    messages = [
        {"role": "system", "content": "You are an expert in navigating the web, your task is to select the better navigation guidance workflow between the two workflows provided."},
        {"role": "user", "content": "Which workflow is more helpful in guiding web navigation? Only return 'Workflow 1' or 'Workflow 2', do not provide any additional information."},
        {"role": "user", "content": f"Workflow 1:\n{workflow1}\nWorkflow 2:\n{workflow2}"}
    ]
    
    # === 替换 litellm 为 DeepSeek Client ===
    try:
        response = client.chat.completions.create(
            model=DEEPSEEK_MODEL,
            messages=messages,
            temperature=args.temperature,
        )
        response_text = response.choices[0].message.content.lower()
    except Exception as e:
        print(f"Error comparing workflows: {e}")
        return workflow2 
    # ===========================================

    if "workflow 1" in response_text: return workflow1
    elif "workflow 2" in response_text: return workflow2
    else: return None

def write_workflows(response: str) -> None:
    # get newly induced workflows
    workflows = extract_code_pieces(response, start='"""', end='"""', do_split=False)
    workflows = [w for w in workflows if ("Task" in w) and ("Action Trajectory" in w)]

    if not os.path.exists(args.write_workflow_path):
        open(args.write_workflow_path, 'w').close()

    # load existing workflows
    existing_content = open(args.write_workflow_path, 'r').read()
    if existing_content:
        existing_workflows = existing_content.split("Task:")
        existing_workflows = ["Task:"+w for w in existing_workflows if len(w) > 0]
        existing_workflows = [w.strip() for w in existing_workflows]
        existing_workflows = [w for w in existing_workflows if len(w) > 0]
    else:
        existing_workflows = []
        
    existing_workflow_names = [get_workflow_name(w) for w in existing_workflows]

    # update workflows
    new_workflows = []
    for w in workflows:
        add_new, names_to_remove = update_workflows(w, existing_workflows)
        
        temp_existing = []
        temp_names = []
        for n, ew in zip(existing_workflow_names, existing_workflows):
            if n not in names_to_remove:
                temp_existing.append(ew)
                temp_names.append(n)
        
        existing_workflows = temp_existing
        existing_workflow_names = temp_names
        
        if add_new: 
            new_workflows.append(w)

    # rewrite the entire workflow memory
    with open(args.write_workflow_path, 'w') as fw:
        fw.write('\n\n'.join(existing_workflows + new_workflows))


# %% Overall pipeline

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=str, default="claude", choices=["gpt-4o", "claude"])
    parser.add_argument("--num_responses", type=int, default=1, help="Number of responses to generate.")
    parser.add_argument("--temperature", type=float, default=1.0, help="Temperature for sampling.")

    parser.add_argument("--sys_msg_path", type=str, default="induce/prompt/system_message_memory.txt")
    parser.add_argument("--instruction_path", type=str, default="induce/prompt/instruction_memory.txt")
    parser.add_argument("--few_shot_path", type=str, default="induce/prompt/shopping_memory.md")
    parser.add_argument("--test_query_path", type=str, default="induce/prompt/test_query.txt")

    parser.add_argument("--template_id", type=str, default=None)
    parser.add_argument("--website", type=str, required=True,
                        choices=["shopping", "admin", "reddit", "gitlab", "map"])
    parser.add_argument("--config_dir", type=str, default="config_files")
    parser.add_argument("--results_dir", type=str, default="results")
    
    # === 修改：不再是 nargs='+'，而是单个字符串 ===
    parser.add_argument("--result_id_list", type=str, default=None, help="The single ID of the result (e.g. '110').")
    # ==========================================

    parser.add_argument("--write_workflow_path", type=str, default=None)
    parser.add_argument("--write_tests_dir", type=str, default="debug_actions")
    parser.add_argument("--eval_with_gold", action="store_true")
    args = parser.parse_args()

    if args.model == "claude":
        args.model = "litellm/neulab/claude-3-5-sonnet-20241022"
    args.model = args.model.replace("litellm", "openai")

    if args.write_workflow_path is None:
        args.write_workflow_path = os.path.join("workflows", f"{args.website}.txt")

    # decide path for entire model output
    args = get_output_dir(args, key="workflow")
    if os.path.exists(args.output_dir):
        print(f"Output directory already exists: {args.output_dir}")
        names = sorted(os.listdir(args.output_dir), key=lambda x: int(x.split('.')[0]))
        paths = [os.path.join(args.output_dir, f) for f in names]
        responses = [open(p, 'r').read() for p in paths]
    else:  # induce new actions
        os.makedirs(args.output_dir, exist_ok=True)
        responses = induce_workflows()
    
    if len(responses) > 0:
        for i, resp in enumerate(responses):
            print(f"\n\n** Start Evaluating Response {i} **")
            write_workflows(resp)

            print(f"**Finish Evaluating Response {i} **\n\n")

    else:
        print("No responses generated or loaded.")