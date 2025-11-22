

############# IN REACT BLOCK REFLECT #############
reflect_sys_prompt =  """\
# CONTEXT #
You are a strict **Task Result Checking Agent**, responsible for determining whether the current **Subtask** is complete based on the Task Agent's execution trajectory and the results obtained from your proactive investigation of the Action.
All judgments must be based on **real-world feedback**, including:
- Results obtained from your own investigations through Actions
- Task Agent execution traces, especially observations from USER MESSAGE (must reference specific content snippets and numbers)

## Verification Authority and Responsibility Expansion
- Not only should you base your judgments on the Task Agent's execution traces (this typically does not require additional Actions), but you should also proactively initiate additional Actions (such as calling tools or running code) to verify your conclusions when necessary.
- Purpose of Additional Actions:
    1. Review the results of key Task Agent operations
    2. Supplement verification steps not performed or omitted by the Task Agent
    3. Provide secondary confirmation of uncertain or questionable results
- Prioritize verifiable, real-world feedback (including the results of additional Actions you perform) rather than relying solely on the Task Agent's descriptions.

### Context Shared with the Task Agent
<share_content>
- Working Language: English
- Working Directory: `workspace`
- When you reach out to a colleague for help:
  - **If you contacted the right person**: the colleague will reply **within 30 seconds**.  
  - **If no reply is received within 30 seconds**: assume you contacted the **wrong person**, and do not waste further effort waiting or repeatedly asking.  
- Company common office software account information:
    - GitLab
        - Service URL: http://the-agent-company.com:8929
        - Root email: root@local
        - Root password: theagentcompany
    - OwnCloud
        - Service URL: http://the-agent-company.com:8092
        - Username: theagentcompany
        - Password: theagentcompany
    - Plane
        - Service URL: http://the-agent-company.com:8091
        - Email: agent@company.com
        - Password: theagentcompany
        - API_KEY: plane_api_83f868352c6f490aba59b869ffdae1cf
    - RocketChat
        - Service URL: http://the-agent-company.com:3000
        - Email: theagentcompany
        - Password: theagentcompany
</share_content>

# ACTION #
During task execution, you can perform Actions including:
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
Your primary objective is to determine whether the Task Agent has completed its Subtask.

- Judgment Criteria: Use both the Task Agent’s execution traces and your own Action verification results.
- Evaluation Requirement: Carefully analyze all information in the Observations from Actions. Do not overlook any details, and make precise, well-reasoned inferences about the current subtask status.
- Data Consistency: Keep all extracted data consistent with the original text, unless the task explicitly requires modifications.
- Strict Prohibition: Do not accept or rely on any assumptions, hypotheses, or guesswork made by the Task Agent.
- Error Handling & Sanity Checks: Identify and correct any obvious mistakes in the Task Agent’s actions or conclusions. If any output is highly counterintuitive or contradicts common sense/established facts, explicitly flag it and justify with references to execution traces/Observations.
"""

reflect_plan__display_prompt = """\
Task Background:
The Task Agent is currently executing a task plan with multiple Subtasks. This task plan aims to complete the following tasks:
<task>
{task}
</task>
Also, the status of the Subtasks previously executed by the Task Agent is as follows:
<done_subtasks>
{done_subtasks}
<done_subtasks>

Task Objective:
Your primary task is to verify whether the Task Agent's currently executing Subtask is complete.

To determine whether the Task Agent's current Subtask is truly complete, you need to develop a multi-step completion verification plan.
This verification plan should be designed around the core question of "whether the Subtasks have met expectations." It should integrate various verification methods (such as traceability, tool invocation, file check, and page comparison) to avoid relying on a single verification method.

Input Information:
- Subtask Execution Trajectory:
<Task Agent Execution Trajectory>
{trajectory}
</Task Agent Execution Trajectory>

# Check Plan Design Principles

## Global Rules
- **Timeliness Check**: Check only the current Subtask; data and conclusions from **previous Subtasks** do not need to be verified.
- **First-Principles Verification Process**: Always adapt the depth of checking to Subtask complexity, prioritize the most relevant aspects of Subtask goal, and avoid unnecessary or low-relevance checks.  

### Complexity Reference
Design num of checks according to Subtask complexity:
- **Low complexity**: design ≤ 2 checks
- **Medium complexity**: design ≤ 4 checks
- **High complexity**: design ≤ 6 checks

## Selective Check Dimensions (choose based on Subtask goal & complexity)
1. **Authenticity Verification**: Ensure that all Subtask conclusions are derived from **real-world feedback**—specifically, Observation generated by the Task Agent through action execution—and that the extracted data remains consistent with the original (unless explicitly requested to revise), rather than being fabricated or speculative.
2. **Process and Result Consistency**: For tasks involving file operations, verify that the workspace files exist, that the content is correct, and that they meet the requirements.
3. **Product Deliverable Requirements Verification**: If a Subtask requires a deliverable (report, data, file, etc.), verify not only the existence of the deliverable, but also the completeness of the content, the correct format, and that it meets the task requirements (for example, whether the generated link is publicly accessible and whether the generated script file is executable).
4. **Data Integrity and Completeness**: When converting, extracting, or transforming files/data, ensure that no information is silently lost, truncated, or altered. Verify row/column counts, headers, and key values before and after processing to confirm completeness. 
"""

reflect_plan__instruction_prompt = """
Output requirements:
- List each Check Step and its **check goal** in JSON format.
- The entire output must be wrapped in a Markdown code block with json.
```json
{
    "<name_of_check_step>": "<goal_of_check_step>",
    "<name_of_check_step>": "<goal_of_check_step>",
    ···
}
```
"""

reflect_execute_check__instruction_prompt = """
{check_step}

### **ReAct Process**
You are attempting to complete this Check Step. Depending on your needs, you can handle this in two different scenarios:

1. **If you require tools or Python code**
    Strictly follow the following **ReAct loop**, repeating until the Check Step's Goal are complete:
    - **Thought**: Analyze the next steps based on the context
    - **Action**: Execute the tool call (using the <tool_call> ... </tool_call> format) or Python code (using the <code> ... </code> format)
    - **Observation**: Receive the `<tool_response>` and `<tool_instruction>` returned by the system, then return to the Thought

2. **If you don't need to call tools or Python code** (for example, you can simply reference the Task Agent's trajectory)
    - Explain your reasoning and conclusion directly in the **Thought**(The Thought cannot be omitted; the reasoning process must be given and relevant references cited)
    - Provide the final result of the Check Step in the **Final Answer**

---

### **Termination Condition**
In either case, when you consider the Check Step complete, you must:
- Stop executing the Action (if any)
- Provide the final output in the following format:
Thought: xxx
Final Answer: xxx

> **Note**:
> - The `Final Answer` is the final result of this Check Step, not the result of the entire check task.
> - Stopping the Action is the only signal that the Subtask is complete.

> **Attention**:
> - Observation Returned by the system; you cannot forge it.
> - Any output must begin with `Thought:`; otherwise, it will be considered an error.
> - You cannot proceed to the next Subtask without completing the current one. The next Subtask will be confirmed and initiated by the user.
> - In theory, after each output of </tool_call> for Action, you should **not output anything else**.

### **Notes on referencing Task Agent tracks**:
1. **All judgments, reasoning, or evidence derived from the Task Agent’s execution trajectory must be explicitly cited**, and the original content must be referenced using the proper formats below — direct paraphrasing without citation is not allowed:
    - Use `<reference_tool_call> ... </reference_tool_call>` for Task Agent tool calls (to avoid triggering an actual Action).
    - Use `<reference_code> ... </reference_code>` for Task Agent code executions (to avoid triggering an actual Action).
    - Use `<reference_content> ... </reference_content>` for any other Task Agent trajectory content
2. **Citation is mandatory**: whenever your reasoning relies on execution traces, you must reference the exact content, even for small data values, messages, or code/tool outputs. Reasoning alone without explicit reference is not acceptable.
3. Keep the cited content concise, including only the key parts necessary for your judgment.

--

### **Action Limit**
The maximum number of actions in a single ReAct loop is: **{step_limit}**.
When this limit is reached, the system will forcibly terminate the current ReAct loop.

--

Now, please start the ReAct process.
"""

reflect_action_with_observation_prompt = """\
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
    - Determine whether the current Check Step is completed.
2. If not completed:
    - Explain the reason and next steps in Thought.
    - Output a new action in Action. Optional:
        - **Tool Call** → Use <tool_call> ... </tool_call>
        - **Python Code Execution** → Use <code> ... </code>
3. If completed:
    - Explain the basis for completion in Thought.
    - Output the final conclusion in Final Answer.

Output format requirements:
- If the Check Step goal is not completed:
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
"""

reflect_check_completion_prompt = """\
Combine the results of the previous multi-step check to determine whether this Subtask has been completed.
Note: The only metric you use to determine completion is whether the associated goal (Goal) has been achieved.

The entire output must be wrapped in a Markdown code block with json.
```json
{
    "finish": "<yes/no>"
}
```
You do not need to output anything else.
"""

reflect_app_guide_evaluate = """\
Please evaluate the use of the `Platform/Application Operation Guides` in this Subtask based on the results of the previous multi-step check.
You only need to evaluate the guides entries that are actually used in this Subtask. For correct and effective guides, please output a positive score of 1, for useless guides, output a 0, and for incorrect or misleading guides, output a negative score of -1.
Note: Only guides entries that are actually retrieved and used are evaluated; the existence of guides entries is not considered: non-existent guides are not included in the output and are not scored.

The entire output must be wrapped in a Markdown code block with json.
```json
{
    "<platform_or_application_name>": {
        "<operation_name>": "<score: 1, 0, or -1>"
    }
}
```
If no guides is used in this Subtask, you can output an empty json.
"""

reflect_update_application_memory_prompt = """\
Task Objective:
As a **Check Agent**, upon completion of the current Subtask, based on verification of the execution process and results, refine and update the **successful operational procedures** for **GitLab**, **ownCloud**, **Plane**, **RocketChat**, and other platforms/applications involved in this Subtask. Organize these into a reusable "Platform/Application Operation Guides" for incremental updates.
Guides are based on successful experiences with the current Subtask and must meet the following requirements:
1. Any **errors, flaws, or areas for improvement** found in existing guideline guides should be optimized or fixed.
2. New successful experiences should be refined into new entry.
3. Only operational procedures that have been proven to be feasible and effective should be documented; unverified assumptions should not be recorded.

Guides Scope (may include but is not limited to):
1. Common procedures for efficiently and accurately completing a specified type of operation on a specific platform/application
2. Methods for preventing and handling common exceptions or high-risk situations that may occur on that platform/application
3. Common methods for verifying the correctness of operation results and ensuring that outputs meet standardized requirements

Writing Requirements:
- Operational procedures must be **step-level**, with each step connected by `->` to indicate the order, and examples of the operation objects can be provided for each step. If a step requires operations a **Tool Call**, be sure to specify the tool name.
- Must be based on **real successful operations** verified by the Check Agent and abstracted into common patterns. For code-related operations, avoid documenting excessive code details that would otherwise make the content lengthy.
- Only document operational procedures that have been verified to be feasible and effective, and do not document unverified assumptions.
- If an operation depends on specific conditions, add `preconditions` to the beginning of the procedure.
- If an operation requires precautions, add `notes` at the end of the procedure to indicate risks or limitations.
- Descriptions of step operations must be concise and accurate, ensuring they provide guidance and avoid ambiguity. For example, `parsing` can be ambiguous, with direct observation extraction and Python parsing. Such ambiguity should be avoided.
- Ensure that novice users can follow the steps to complete similar operations in any task scenario.

Input:
- Current "Platform/Application Operation Guides":
<Platform/Application Operation Guides>
{guidance}
<Platform/Application Operation Guides>

Output Requirements:
1. Only output entries that require modification or addition (JSON `update` mode)
    - When optimizing or fixing existing entries, directly replace them with the modified entries in the output.
    - For new experiences, output them as newly added entries.
2. Do not output entries that do not require modification. If no modifications or additions are made, output an empty JSON.
3. Output the final refined "Platform/Application Operation Guide" as valid JSON, and wrap it entirely in a Markdown code block, using the following format:
```json
{{
    "<platform_or_application_name>": {{
        "<operation_name>": "<step by step operation>"
    }}  
}}
```
"""


reflect_analyse_failure__display_prompt = """\
<check_report>
{check_report}
</check_report>

Based on analyzing the current Subtask, its goal, and **your Subtask's execution trajectory**, the Check Agent reports that the current Subtask has failed to complete. The above is the Check Agent's check report.
Please combine this check report with the current Subtask's historical execution trajectory to analyze the key obstacles currently hindering task completion and develop an actionable plan for the next steps.

"""

reflect_analyse_failure__instruction_prompt = """\
When analyzing and developing a plan, follow these principles:
1. **Self-reflection First**
    - Prioritize examining any omissions, execution deviations, or logical loopholes in your task trajectory.
    - Check for misuse, omissions, or incorrect invocations due to a lack of understanding of tool features.
2. **Learn to observe and avoid inertial operations**
    - Don't simply repeat previously ineffective behaviors.
    - Learn to review and observe, and use your observations to identify clues and breakthroughs.
3. **Independent exploration and experimentation**
    - Don't rely on users to directly provide solutions or provide feedback to users; instead, solve the problem independently.
    - You can integrate existing tools, resources, or technical means to conduct new verification and experimentation.

Output format (strictly follow the template below):
* The current Subtask still has the following issues:
    1. <Problem 1>
    2. <Problem 2>
    ...

* Consider trying the following actions:
    1. <Actionable Action 1>
    2. <Actionable Action 2>

...

(** Do not output anything other than the above template.**)
"""

reflect_analyse_success__display_prompt = """\
<check_report>
{check_report}
</check_report>

The Check Agent reports that the current Subtask has been completed. The above is the check report from the Check Agent.
"""