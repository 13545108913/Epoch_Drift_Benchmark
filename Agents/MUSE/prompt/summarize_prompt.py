
summarize_success_and_failure_prompt = """\
Task Objective:
Based on the execution of this task, summarize the **lessons learned** from successful subtasks and **reflections** from failed subtasks, so that successful models can be replicated and failure pitfalls avoided in subsequent tasks.

Writing Requirements:
1. Summary of Successful Subtasks:
    - Clarify the task context and objectives
    - Identify key success factors (process, strategy, tool selection, communication methods, etc.)
    - Identify reusable practices or patterns
2. Reflection of Failed Subtasks:
    - Briefly describe the reasons for failure (including key errors or flaws in the process)
    - Analyze the underlying issues (such as insufficient information, misjudgment, execution deviations, etc.)
    - Provide targeted improvement suggestions or alternative strategies
3. Content must be based on real-world task experiences; avoid empty or unactionable descriptions.
4. Each summary or reflection should provide direct guidance for future tasks.
5. If a subtask is partially successful and partially unsuccessful, it can be separated into "Successful Lessons" and "Reflections on Failures" for separate recording.
"""

reflect_tool_enhance_prompt = """\
Task Objective:
Based on the actual usage of each tool in this task, review, summarize, and optimize their tool descriptions and tool instructions.

Term Definitions:
- Tool Description:
    This summarizes the tool's overall functionality, primary purpose, applicable scenarios, precautions, or other important tool-related information. This helps the user understand the tool's value and limitations.
- Tool Instruction:
    After the specific tool completes execution, the post-execution instructions included in the observation are typically used to guide the next step or restrict subsequent behavior, and have the most significant impact on the next action.

Input:
- Existing tool descriptions and tool instructions, in the following format:
<tools>
{tools}
</tools>

Task Requirements:
1. Modify or add only to the existing dictionary; do not re-enter unchanged entries.
2. Optimizations should include:
    - Adding missing important functional information
    - Correcting inaccurate or ambiguous descriptions
    - Adding precautions discovered during actual use
    - Optimizing the language to make it more concise, precise, and easy to understand
3. The output format is JSON, and the final result will be used to perform an `update` operation on the original dictionary.
4. **DO NOT** output any entries you do not want to modify.

Final output format (JSON block must be placed last and occupy a separate paragraph):
```json
{{
    "<tool_name>": {{
        "tool_description": "<description of the tool used to give you a reference>",
        "tool_instruction": "<After the tool has finished executing, the instruction attached to the observation>"
    }}
    ···
}}
```
Note:
You can include any length of thought, summary, or refinement before the JSON output.
However, the JSON block must be formatted correctly and output independently to facilitate subsequent parsing.
"""

reflect_methodology_enhance_prompt = """\
Task Objective:
Reflect on the dilemmas encountered during this task — especially those that were difficult to advance and required multiple attempts to overcome.
You will need to thoroughly analyze and reflect on the situation, then output a structured JSON block containing the "Resolution Patterns" for parsing and subsequent reuse.

Analysis and Summary Phase (feel free to expand to help you refine patterns):
1. Review the context and process of each dilemma in detail.
2. Analyze the core cause of the dilemma (why progress was difficult).
3. Document the key practices that ultimately led to a successful resolution (what methods/strategies/decisions worked).
4. Consider whether these practices are still effective in different contexts and identify reusable patterns or paradigms.
5. Express these patterns in concise, universal language so they can be applied to subsequent tasks, while keeping a short explanatory note to avoid them being empty slogans.

Output Phase (strict formatting requirements):
- Your final output must include a separate JSON block for parsing.
- Each pattern should clearly point to a reusable solution or approach, rather than simply stating facts.
- Prioritize identifying **universal paradigms** while retaining explanatory notes for context.

Final output format (JSON block must be placed last and occupy a separate paragraph):
```json
{
    "<pattern_key>": "<pattern_statement + short explanatory note>",
    ...
}
```
Note:
You can include any length of thought, summary, or refinement before the JSON output.
However, the JSON block must be formatted correctly and output independently to facilitate subsequent parsing.
"""

merge_methodology_prompt = """\
# CONTEXT #
You are the **Resolution Patterns Merge Expert**.  
Your sole responsibility is to integrate and unify two sets of "Resolution Patterns":  
1. **Existing Patterns** (previously accumulated)  
2. **New Patterns** (newly extracted from recent dilemmas and reflections)  

# OBJECTIVE #
- Merge the **existing patterns** with the **new patterns** into a single JSON block.  
- Ensure the merged version is **consistent, non-redundant, and limited to a maximum of 10 items**.  
- Each item must be phrased as a **universal, reusable pattern** (not task-specific facts).  
- If new and old contain similar patterns, consolidate them into one improved, generalized pattern.  
- If any old item is outdated or contradicted by newer insights, remove or refine it.  

# DEPTH REQUIREMENT #
- Each pattern must be concise but meaningful:  
  - Keep the **pattern key short (2–6 words)**.  
  - Each statement must contain both **the action/approach** and **a short rationale** (why it matters / how it helps).  
  - Avoid generic slogans; ensure clarity of both “what to do” and “why to do it.”  

# INPUT #
- Existing "Resolution Patterns":
<Old Resolution Patterns>
{old_methodology}
</Old Resolution Patterns>
- New "Resolution Patterns":
<New Resolution Patterns>
{new_methodology}
</New Resolution Patterns>

# Output Format #
Final output format (JSON block must be placed last and occupy a separate paragraph):
```json
{{
    "<pattern_key>": "<pattern_statement + short rationale>",
    ...
}}
Note:
You can include any length of thought, summary, or refinement before the JSON output.
However, the JSON block must be formatted correctly and output independently to facilitate subsequent parsing.

# RULES #
- Keep patterns clear, concise, and applicable across different tasks.
- Avoid duplication: merge overlapping ideas into stronger unified patterns.
- Maximum of 10 items total.
- Each pattern must balance clarity + rationale, not just abstract phrasing.
"""

merge_application_prompt = """\
# CONTEXT #
You are the **Application Operation Guide Merge Expert**.
Your responsibility is to **merge, deduplicate, normalize, and improve** a dictionary of "Platform/Application Operation Guides".

# INPUT #
- Current "Platform/Application Operation Guides":
<Platform/Application Operation Guides>
{guidance}
</Platform/Application Operation Guides>

# Objective #
- Identify and merge similar/duplicate operation steps.
- Normalize platform/application names into canonical forms.
- Improve unclear or low-quality steps to ensure concise, unambiguous, and reusable guides.

# Merge & Improvement Rules #
1. Platform Canonicalization
    - Merge aliases/variants of the same platform into a single, canonical platform name.
    - Example: `FastAPI Code Development` / `FastAPI Deployment` → `FastAPI`.
    - Use consistent casing and naming (e.g., GitLab, FastAPI, RocketChat).
2. Clustering by Operation Intent
    - Group entries by operation purpose.
    - Example: create/add/new → Create; start/run/launch → Start.
3. Consolidation
    - Keep the clearest, most general operation name.
    - Merge steps, remove redundancy, prefer reliable and safe versions.
4. Preconditions & Notes
    - Add `preconditions` at the start if required (e.g., dependencies installed, logged in).
    - Add `notes` if there are risks or cautions.
5. Clarity
    - Use precise actions. Example: use `Click "New Issue" Button` instead of `Click Button`, replace `parsing` with `direct observation extraction` or `Python-based parsing`.
6. Terminology & Style
    - Use a consistent imperative style: `Open -> Select -> Configure -> Save -> Verify`.
7. Do Not Invent
    - Do not add fake platforms or fake capabilities.
    - Remove entries that are clearly obsolete or unfixable.

# Output Format #
Final output format (JSON block must be placed last and occupy a separate paragraph):
```json
{{
  "<platform_or_application_name>": {{
    "<operation_name>": {{
      "preconditions": "...",
      "steps": "... -> ... -> ...",
      "notes": "..."
    }}
  }}
}}
```
Note:
You can include any length of thought, summary, or refinement before the JSON output.
However, the JSON block must be formatted correctly and output independently to facilitate subsequent parsing.
"""