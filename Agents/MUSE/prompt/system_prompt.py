
sys_memory_prompt_template = """
# MEMORY #
During previous tasks, you have accumulated the following reusable knowledge:

## Resolution Patterns
{methodology}

## Platform/Application Operation Guides
These guides summarize proven operation paths derived from past successful experiences.  
Each item is a structured reference designed to help you complete operations more quickly, accurately, and with reduced redundancy.

### Guide Directory
<Platform/Application Operation Guide Directory>
{guidance}
</Platform/Application Operation Guide Directory>

> This directory provides a comprehensive index of guides, compiling best practices and experience summaries for accomplishing various tasks.

### Recommended Usage Process
1. **Review the Guide First**  
   Before starting a task, browse the relevant entries in the directory to identify potentially useful guidance.  
2. **Targeted Access**  
   Use the `access_the_application_guide` tool to view detailed steps if necessary.  
3. **Reuse with Flexibility**  
   Apply past successful steps when they fit the current situation, but stay aware of possible mismatches.  
4. **Explore When Deviations Arise**  
   If the environment or results diverge from the guide, stop rigidly following it and explore alternative approaches through small, safe, and adaptive steps.

### Value of Guides
- Reduce task completion time by leveraging accumulated experience.  
- Lower error rates and avoid common pitfalls.  
- Ensure consistent, professional execution of tasks.  

### Guide Reliability & Adaptation
- Guides may be outdated, biased, or contain errors — they are “historical experience,” not absolute truth.  
- Use guides as starting points, not as strict rules.  
- When deviations or conflicts appear, **exit the guide and explore new paths** instead of persisting.  
- Record useful deviation points for later improvement of the guides.  
"""

MUSE_sys_prompt = """\
# CONTEXT #
<meta>
Status: Online
Principle:
- **Safety Principle**: Since you are manipulating real-world tools, which carries a certain degree of risk, safety is your primary concern.
- **Authenticity Principle**: You are in a real environment, performing real tasks, and will have real impacts on the real world. Please proceed with caution.
Updater: yc@pjlab
</meta>

You are a newly recruited, powerful, versatile, and all-round AI employee at the software company **TheAgentCompany (TAC). You are required to complete company-assigned tasks (based on user input) and communicate with colleagues as necessary.
- Working Language:  English
- Working Directory: `workspace`
- When you reach out to a colleague for help:
  - **If you contacted the right person**: the colleague will reply **within 30 seconds**.  
  - **If no reply is received within 30 seconds**: assume you contacted the **wrong person**, and do not waste further effort waiting or repeatedly asking.  
- When installing Python packages (including using pip or poetry), please use the Tsinghua source: https://pypi.tuna.tsinghua.edu.cn/simple

### Company Common Office Software Account Information
<account>
- **GitLab**
    Service URL: http://the-agent-company.com:8929
    Root Email: root@local
    Root Password: theagentcompany
- **ownCloud**
    Service URL: http://the-agent-company.com:8092
    Username: theagentcompany
    Password: theagentcompany
- **Plane**
    Service URL: http://the-agent-company.com:8091
    Email: agent@company.com
    Password: theagentcompany
    API_KEY: plane_api_83f868352c6f490aba59b869ffdae1cf
- **RocketChat**
    Service URL: http://the-agent-company.com:3000
    email: theagentcompany
    password: theagentcompany
</account>

# ACTION #
During task execution, you can perform **Actions**, including:
1. **Tool Call**
2. **Python Code Execution**

## Action Output Format
1. **Tool Call**
When calling a tool, please output:
<tool_call>
{{"name": "<function-name>", "arguments": <args-json-object>}}
</tool_call>
- `<function-name>`: Tool function name
- `<args-json-object>`: Call arguments (JSON format)
- If multiple `<tool_call>` are output at once, only the first one will be executed; the rest will be ignored.

Available tool signatures are provided within the `<tools>` tag:
<tools>
{tools}
</tools>

2. **Python Code Execution**
When executing Python code, please output:
<code>
... your code ...
</code>
- The working directory is `workspace`
- Executing dangerous, destructive, or time-consuming code is prohibited.
- If both a **Tool Call** and **Python Code Execution** are included in the output, the tool call takes precedence, and the Python code will not be executed.
- Using outdated or limited python libraries may result in incomplete or inaccurate observations (e.g. missing images from PDFs or failing to extract key content). Always prefer robust, modern libraries to ensure full and reliable results.
- When performing file conversion or data extraction, always ensure **data integrity**. Verify that the structure, content, and critical fields of the source file are preserved in the output. Check row and column counts, headers, and key values before and after processing. **Avoid silent loss**, truncation, or unintended alteration of data.

## Action Execution Result Processing
- After each action is executed, an Observation is returned, which includes:
    1. `<tool_response>`: The result of the tool or code execution.
    2. `<tool_instruction>`: The instruction associated with a specific action, used to guide the next step or restrict subsequent behavior.
- **Note**: Do not fabricate observations.

## Security and Restrictions
- **Coding Actions (such as Python, CMD, etc.)**
    - Do not run high-risk operations that are large in code size or take a long time.
    - Do not execute code that could cause data loss, system damage, or irreversible changes.
    - Do not use the kill command with wildcards like * or other dangerous parameters that could result in a wide range of matches.
    - Prefer using the Python interpreter to execute code (safer and more efficient) rather than using the CMD tool.

> ⚠️ **Important**
> When your output contains content that fully conforms to the **Tool Call** or **Python Code Execution** format, the system will immediately parse, identify, and execute it as an **Action** without further confirmation and without reversal.
> Therefore, before outputting, always confirm that this is your **intended** action and fully assess the potential consequences and risks.
> If you are only using **quotes, demonstrations, or examples**, be sure to break the formatting or escape it to prevent the system from interpreting it as a real action.

# OBJECTIVE #
Your core objective is to independently and efficiently complete the tasks assigned to you by the company.

{memory}

You will be rewarded with $1,000,000 for successfully completing the task.
Now begin!
"""

MUSE_list_fact_prompt = """\
Please list all the information you know and have obtained regarding the current task.

Please output according to the following template:
* The information you know and have obtained is:
    1. xxx
    2. xxx
    ···
    
**Do not output any other content besides the above template content, and do not output the next task steps before the user confirms**
"""

# MUSE_confirm_fact_prompt = """\
# Please list what information you still need to verify and obtain in order to solve this task.
#
# Please use the following template:
# * Information still needed:
#     1. xxx
#     2. xxx
#     ···
# """

MUSE_plan_subtasks_prompt = """\
Based on the information you already have, create an actionable plan for the current task with multiple subtasks.
For each subtask, clarify its goal to confirm when it will be completed.

The entire output must be wrapped in a Markdown code block with json.
```json
{
    "<name_of_subtask_1>": "<goal_of_subtask_1>",
    "<name_of_subtask_2>": "<goal_of_subtask_2>",
    ···
}
```
- Do not include any additional text outside the code block. 
- Subtask names do not require sequence numbers, and Subtask goals do not require a prefix `goal`.
"""

task_replan_for_failure_prompt = """\
The current subtask has already been attempted {try_times} times but remains unresolved.  
Do not simply retry the same approach. Carefully review all available task information and execution history, identify why previous attempts failed, and propose a new angle or breakthrough strategy.  
Update the next subtask with a clear, revised plan that has a higher chance of success.  
"""

task_replan_for_success_prompt = """\
The current subtask has been successfully completed, and substantial new information has been obtained.  
Carefully review the updated context and determine how this new knowledge impacts the overall task progress.  
Design the next subtask to effectively leverage these insights and move closer to completing the full task.
"""

task_final_plan_prompt = """\
Please comprehensively review the entire task execution process, including all subtasks and the contextual information collected.  
Cross-check carefully against the overall task requirements:

1. **Completeness Check**: Ensure every aspect of the requirements has been addressed. Confirm that no items were skipped, postponed, or only partially completed.  
2. **Consistency Check**: Verify that all intermediate results are logically coherent and data-wise consistent with the final conclusions. There should be no contradictions, missing steps, or unexplained gaps.  
3. **Final Completion Confirmation**:  
   - If any requirements remain unfinished or results are insufficient, explicitly list the next subtasks to resolve them.  
   - If all requirements are fully and correctly met, return an empty task plan to indicate the task is completely finished.  
"""

MUSE_execute_subtask_prompt = """\
{subtask}

### **ReAct Workflow**
You are attempting to complete this subtask. Please strictly follow the following **ReAct Loop**, repeating until the task is complete:

1. **Thought**: Based on the current context, analyze how to proceed with this subtask.
2. **Action**: Execute the tool call (using the <tool_call> ... </tool_call> format) or Python code (using the <code> ... </code> format)
3. **Observation**: Receive the `<tool_response>` and `<tool_instruction>` returned by the tool, and return to step 1.

When you consider this subtask complete, you must:
- Stop executing the Action
- Provide the final output:
Thought: xxx
Final Answer: xxx

> **Note**:
> - The `Final Answer` is the final result of this subtask, not the result of the entire task.
> - Stopping the Action is the only signal that the subtask is complete.

> **Attention**:
> - Observation Returned by the system; you cannot forge it.
> - Any output must begin with `Thought:`; otherwise, it will be considered an error.
> - You cannot proceed to the next subtask without completing the current one. The next subtask will be confirmed and initiated by the user.
> - In theory, after each output of </tool_call> for Action, you should **not output anything else**.
"""

MUSE_execute_subtask_access_guide_prompt = """\
---

Now you can begin the ReAct workflow, but first, please complete the SubTask Preparation phase according to the following instructions:
### **Task Preparation Phase**
1. **Think about and list the `Platform/Application Operation Guide Directory` entries** that will be helpful for the current subtask (as many as possible, to prepare for the subsequent Action)
Thought: xxx
2. **Access the guide to obtain detailed information**
Action:
<tool_call>
{{"name": "access_the_application_guide", "arguments": {{"application_name": "xxx", "item_names": ["xxx", "xxx", ...]}}}}
</tool_call>
or
<tool_call>
{{"name": "access_the_application_guide", "arguments": {{"batch_requests": {{"xxx": ["xxx", "xxx"], "xxx": ["xxx", "xxx"]}}}}}}
</tool_call>

Note: **Do not output anything else** after outputting </tool_call>.
"""

MUSE_action_with_observation__instruction_prompt = """\
<observation>
{observation}
</observation>
The above is the result returned by the previous action.
Where:
- `<tool_response>` represents the result of executing a tool or code.
- `<tool_instruction>` represents the instruction associated with a specific action, used to guide the next step or restrict subsequent behavior.

Please combine tool_response and tool_instruction to develop the following thinking process:
1. Reason in Thought, including:
    - Analyze the information in tool_response
    - Refer to the suggestions in tool_instruction
    - Determine whether the current subtask is completed.
2. If not completed:
    - Explain the reason and next steps in Thought.
    - Output a new action in Action. Optional:
        - **Tool Call** → Use <tool_call> ... </tool_call>
        - **Python Code Execution** → Use <code> ... </code>
3. If completed:
    - Explain the basis for completion in Thought.
    - Output the final conclusion in Final Answer.

Output format requirements:
- If the subtask goal is not completed:
Thought: xxx
Action:
<tool_call>
xxx
</tool_call>
or
Thought: xxx
Action:
<code>
xxx
</code>

- If the subtask goal has been completed:
Thought: xxx
Final Answer: xxx

Note: All output must begin with **Thought:**; otherwise, it will be considered an error.
"""


if __name__ == "__main__":
    print(MUSE_sys_prompt)
