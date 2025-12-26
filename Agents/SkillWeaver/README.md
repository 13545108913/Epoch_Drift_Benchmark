<h1 align="center">SkillWeaver <br> Web Agents can Self-Improve by Discovering and Honing Skills</h1>

<p align="center">
<a href="https://www.python.org/downloads/release/python-3109/"><img src="https://img.shields.io/badge/python-3.10-blue.svg" alt="Python 3.10"></a>
<a href="https://playwright.dev/python/docs/intro"><img src="https://img.shields.io/badge/Playwright-1.44-green.svg" alt="Playwright"></a>
<a href="https://github.com/OSU-NLP-Group/SkillWeaver"><img src="https://img.shields.io/github/stars/OSU-NLP-Group/SkillWeaver?style=social" alt="GitHub Stars"></a>
<a href="https://github.com/OSU-NLP-Group/SkillWeaver/issues"><img src="https://img.shields.io/github/issues-raw/OSU-NLP-Group/SkillWeaver" alt="Open Issues"></a>
<a href="https://twitter.com/osunlp"><img src="https://img.shields.io/twitter/follow/OSU_NLP_Group" alt="Twitter Follow"></a>
</p>

SkillWeaver is a skill-centric framework enabling agents to self-improve by autonomously synthesizing reusable skills as APIs. Given a new website, the agent autonomously discovers skills, executes them for practice, and distills practice experiences into robust APIs. Iterative exploration continually expands a library of lightweight, plug-and-play APIs, significantly enhancing the agent's capabilities. 

![Demo Video GIF](https://raw.githubusercontent.com/OSU-NLP-Group/SkillWeaver/gh-pages/assets/final_drug_baseline_no_terminal.gif)


## Installation

It is recommended to first create a virtual environment:

```bash
conda create -n skillweaver python=3.10
conda activate skillweaver
pip install -r requirements.txt
playwright install
```

## Configuration

```bash
# OpenAI API
export OPENAI_API_KEY=<your_openai_api_key>

# If you'd love to use Azure-hosted OpenAI models instead
export AZURE_OPENAI=1
export AZURE_OPENAI_gpt-4o_ENDPOINT=<endpoint>
export AZURE_OPENAI_gpt-4o_API_KEY=<endpoint API key>
```

## Running A Demo

To attempt a task, you can use the following command:

```bash
python -m skillweaver.attempt_task <start-url> <task> [...options]
```

Arguments:

- `start-url`: The URL to start the task from. You can use `__REDDIT__`, `__MAP__`, `__SHOPPING__`, `__SHOPPING_ADMIN__`, and `__GITLAB__` as the prefix if you would like to load the address from environment variables and perform the login step (required for most WebArena tasks).
- `task`: The task to attempt. This should be a string that describes the task to be attempted.
- `--agent-lm-name [lm_name]`: The name of the LLM to use for the agent. Default: `gpt-4o`.
- `--max-steps`: The agent's time limit to complete the task, as measured in generated actions. Default: 10.
- `--knowledge-base-path-prefix`: The path to the synthesized APIs (without `_code.py`). For example, `logs/explore-reddit-gpt4o/iter_79/kb_post`.
- `--headless`: Whether to attempt the task in headless mode.

For example, to try a task on the `reddit` website, you could use the following command:

```bash
python -m skillweaver.attempt_task __REDDIT__ "Post to the gaming forum to ask about the best games of the year" --knowledge-base-path-prefix skill_library/reddit/reddit_kb_post
```

To compare the performance without the knowledge base, remove the `--knowledge-base-path-prefix` argument:

```bash
python -m skillweaver.attempt_task __REDDIT__ "Post to the gaming forum to ask about the best agmes of the year"
```

### Browser-Use Version

This is an experimental version that uses the agent from [Browser-Use](https://browser-use.com/). It converts our knowledge base into a Browser-Use `Controller` object that can be used to extend the action space of an existing agent.

To attempt a task, you can use the following command:

```bash
python -m skillweaver.attempt_task_browser_use <start-url> <task> [...options]
```

Arguments:

- `start-url`: The URL to start the task from. You can use `__REDDIT__`, `__MAP__`, `__SHOPPING__`, `__SHOPPING_ADMIN__`, and `__GITLAB__` as the prefix if you would like to load the address from environment variables and perform the login step (required for most WebArena tasks).
- `task`: The task to attempt. This should be a string that describes the task to be attempted.
- `--agent-lm-name [lm_name]`: The name of the LLM to use for the agent. Default: `gpt-4o`.
- `--knowledge-base-path-prefix`: The path to the synthesized APIs (without `_code.py`). For example, `logs/explore-reddit-gpt4o/iter_79/kb_post`.
- `--headless`: Whether to attempt the task in headless mode.

For example, to try a task on the `reddit` website, you could use the following command:

```bash
python -m skillweaver.attempt_task_browser_use __REDDIT__ "Post to the gaming forum to ask about the best games of the year" --knowledge-base-path-prefix skill_library/reddit/reddit_kb_post
```

To compare the performance without the knowledge base, remove the `--knowledge-base-path-prefix` argument:

```bash
python -m skillweaver.attempt_task_browser_use __REDDIT__ "Post to the gaming forum to ask about the best agmes of the year"
```

## Explore a Website

Once you have set up your virtual environment and created a `.env` file with the appropriate configuration, you can explore a website using the following command:

```bash
python -m skillweaver.explore [website] [out_dir] --iterations [niter] (... options ...)
```

Arguments:

- `website`: The URL or name of the website to explore. You can specify a WebArena website by passing in the name of the website (e.g., `shopping`). The available WebArena environments are `shopping`, `shopping_admin`, `map`, `reddit`, and `gitlab`.
- `out_dir`: The directory to save the exploration results. Note that if a directory already exists at the specified path, the exploration will not start.
- `--iterations [niter]`: The number of iterations to run the exploration for. Default: 10.
- `--agent-lm-name [lm_name]`: The name of the LLM to use for the agent. Default: `gpt-4o`.
- `--api-synthesis-lm-name [lm_name]`: The name of the LLM to use for API synthesis.
- `--success-check-lm-name [lm_name]`: The name of the LLM to use for success checking. Default: `gpt-4o`.
- `--explore-schedule`: How to perform exploration and testing iterations. Can be of the format `test_probability:X` to test a generated API (if possible) with probability `X`, or `explore:X,test:Y` to alternate between `X` iterations of exploration and `Y` iterations of testing.
- `--allow-recovery`: Whether to allow the agent to "patch" APIs that throw exceptions during testing. Default: `--allow-recovery`. This can be disabled with `--no-allow-recovery`.
  Here is an example command:

```bash
python -m skillweaver.explore reddit logs/explore-reddit-gpt4o --agent-lm-name gpt-4o --api-synthesis-lm-name gpt-4o --iterations 160
```

## Run Evaluations

WebArena recommends using Docker containers to host the websites that are being evaluated. We recommend taking a look at [their guide](https://github.com/web-arena-x/webarena/tree/main/environment_docker) to download the containers. We have an automated way to run evaluations using these containers once downloaded, but you can also run the containers manually, or even specify a custom URL to evaluate with instead of using the containers.

### Managed Containers (Parallel Evaluation)

We orchestrate multiple docker container to allow running experiments in parallel. The Orchestrator Server should run outside of Docker (e.g., with a virtualenv). It exposes REST endpoints on port 5125, used internally by the containers context manager.

Before running experiments, we need to run the orchestrator.

```bash
python -m skillweaver.containerization.serve
ORCHESTRATOR_PORT=5128 python -m skillweaver.containerization.serve
```

#### Networking Setup

The containers will be routed to port `8000`, `8001`, `8002`, etc. Ensure that these ports are accessible externally if you are using a cloud environment. Make sure the `IP` variable is set correctly in your `.env` file if using a cloud environment; otherwise, the containers may redirect you to `127.0.0.1`, which will be incorrect if you are using a server (e.g. AWS) to run the test.

### Existing Container (Single Evaluation)

To evaluate a single website using an existing container, set the following environment variables in your `.env` file:

```bash
SHOPPING=(hostname)
SHOPPING_ADMIN=(hostname)
REDDIT=(hostname)
GITLAB=(hostname)
MAP=(hostname)
CONTAINER_SETUP=manual
```

Use `CONTAINER_SETUP=manual` to use your existing container. If you would like to use the containerization framework, omit this line. The orchestrator server will automatically spin up containers as needed.

### Execution

To run the evaluation, use the following command:

```bash
python -m skillweaver.evaluate_benchmark [website] [out_dir] (... options ...)
```

Arguments:

- `website`: The name of the website to evaluate. This can be one of `shopping`, `shopping_admin`, `reddit`, `gitlab`, or `map`.
- `out_dir`: The directory to save the evaluation results. Note that if a directory already exists at the specified path, the evaluation will not start.
- `--time-limit [time_limit]`: The agent's time limit to complete each evaluation task. Default: 10 actions.
- `--knowledge-base-path-prefix [prefix]`: The prefix of the knowledge base to use for the evaluation. Default: `None` (no knowledge base). This should be of the format `/path/to/iteration/dir/kb_post`.
- `--lm-name [lm_name]`: The name of the LLM to use for the agent. Default: `gpt-4o-2024-08-06`.
- `--pool-size [pool_size]`: The number of subprocesses for evaluation. Each subprocess gets its own Docker container. Default: 8.
- `--use-debugger-eval`: Whether to use the modified WebArena debugger which adds additional information about why a test case failed. Default: `True`.
- `--allow-recovery`: Whether to allow the agent to "patch" APIs that throw exceptions during testing. Default: `True`.
- `--reduced-set`: Whether to use a reduced set of test cases (one test case per unique "intent template" provided in the WebArena benchmark). Default: `True`.
- `--allow-unverified-apis`: Whether to allow the agent to use APIs that have not been executed without a runtime error. Default: `False`.
- `--selected-tasks [task1,task2,...] OR reduced_set`: A list of task indices to evaluate. If specified as `reduced_set`, will select one of each `intent_template` from the WebArena benchmark (approximately 20-40 out of 100+ tasks). If specified as a list of integers, will select tasks by index from the WebArena benchmark. Default: `None`, which will evaluate all tasks in the benchmark for that website.

### Prompt Organization

The prompts have all been organized into separate .md files and put under `skillweaver/templates`.



## Disclaimer

This dataset was collected and released solely for research purposes, with the goal of making the web more accessible via language technologies. The authors are strongly against any potential harmful use of the data or technology to any party. 

```bash
python -m skillweaver.evaluation.evaluate_single_task --task_id 41 --out_dir ./result/ --knowledge_base_path_prefix logs/explore-gitlab/iter_86/kb_post

python -m skillweaver.evaluation.evaluate_benchmark gitlab results/gitlab_with_skills --knowledge-base-path-prefix logs/explore-gitlab/iter_86/kb_post
```

```bash
原：
166/166 [1:52:44<00:00, 40.75s/it, ⏳ Evaluating. ✅ 17/147; ❓ 19; 💰 $0.00 🕐 6.12 (n=147) (remaining=0)]

Drift：
166/166 [1:51:13<00:00, 40.20s/it, ⏳ Evaluating. ✅ 13/77; ❓ 89; 💰 $0.00 🕐 8.31 (n=77) (remaining=0)]

原：
161/162 [2:24:25<00:53, 53.82s/it, ⏳ Evaluating. ✅ 26/144; ❓ 17; 💰 $0.00 🕐 4.54 (n=144) (remaining=1)]

Drift：
161/162 [2:12:56<00:49, 49.55s/it, ⏳ Evaluating. ✅ 22/146; ❓ 15; 💰 $0.00 🕐 5.59 (n=146) (remaining=1)]

重新跑原：
162/162 [1:57:41<00:00, 43.59s/it, ⏳ Evaluating. ✅ 19/150; ❓ 12; 💰 $0.00 🕐 5.58 (n=150) (remaining=0)]

v16:
75/162 [1:19:04<1:31:43, 63.26s/it, ⏳ Evaluating. ✅ 22/74; ❓ 1; 💰 $0.00 🕐 6.68 (n=74) (remaining=87)]

87/87 [1:55:44<00:00, 79.82s/it, ⏳ Evaluating. ✅ 7/87; ❓ 0; 💰 $0.00 🕐 7.71 (n=87) (remaining=0)]

v16_drift：
162/162 [3:14:24<00:00, 72.00s/it, ⏳ Evaluating. ✅ 22/160; ❓ 2; 💰 $0.00 🕐 6.77 (n=160) (remaining=0)]

v12_waber：
162/162 [9:14:17<00:00, 205.30s/it, ⏳ Evaluating. ✅ 4/28; ❓ 134; 💰 $0.00 🕐 9.25 (n=28) (remaining=0)]

132/132 [12:25:33<00:00, 338.89s/it, ⏳ Evaluating. ✅ 4/35; ❓ 97; 💰 $0.00 🕐 7.50 (n=35) (remaining=0)]

94/94 [9:15:28<00:00, 354.56s/it, ⏳ Evaluating. ✅ 4/32; ❓ 62; 💰 $0.00 🕐 10.00 (n=32) (remaining=0)]
```

```bash
91%|███████████████████████████████████▌   | 104/114 [2:20:41<13:31, 81.17s/it, ⏳ Evaluating. ✅ 16/104; ❓ 0; 💰 $0.00 🕐 7.38 (n=104) (remaining=10)]

94%|██████████████████████████████████████▍  | 107/114 [3:02:57<11:58, 102.59s/it, ⏳ Evaluating. ✅ 8/97; ❓ 10; 💰 $0.00 🕐 5.12 (n=97) (remaining=7)]

100%|████████████████████████████████████████| 114/114 [1:42:50<00:00, 54.12s/it, ⏳ Evaluating. ✅ 19/113; ❓ 1; 💰 $0.00 🕐 6.89 (n=113) (remaining=0)]
```