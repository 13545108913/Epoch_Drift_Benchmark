from polyskill.agent.utils import screenshots_differ

SYSTEM_PROMPT = """You are a powerful and precise web agent, executing the following goal: {goal}.

Here is the set of actions you can take, which you can call as python functions supplying the html backend id (the bid attribute) or any relevant field as specified. It is a documentation of all the functions, and it's important that you read it well and carefully: 

{actions}

## Key Instructions:
- The user will provide the webpage and html, which you must operate on using the actions to perform your goal
- Your outputs should be single python function calls, without any additional text, and should follow the correct formatting given in the python function dump
- Some functions operate on the backend id (bid) attribute which will be found in the html dump, and is a number passed as a string object
- Others, particularly mouse operations, use coordinates if applicable
- You will be given context about your previous actions, progress, and any errors - use this information to make intelligent decisions and avoid repeating mistakes
- Learn from the history of actions to build understanding of the webpage structure and user interactions
- If previous actions failed, try alternative approaches rather than repeating the same action
- Pay attention to the current progress to understand what has been accomplished and what still needs to be done

DO NOT PROVIDE MORE THAN ONE STEP AT EACH TURN!"""

GOAL_IMAGES_PROMPT = """Here are the images associated with the goal of the task:"""

GROUNDING_PROMPT_BEFORE_IMG = """Please help me! Here is the current image of the webpage, which you can interact with using the actions and which you should remember coordinates for elements:"""

ANSWER_PROMPT = """\
What should be the SINGLE action call to achieve the goal? If the goal has been achieved already, use `send_msg_to_user`.

Please answer this question in the following format:
<think>Your reasoning about what should be done next based on the current state of the webpage and your goal.</think>
<action description>A natural language description of the action you should perform.</action description>
<action>The python function call you should make.</action>
"""

GROUNDING_PROMPT_AFTER_IMG_PART1 = """Next, here is the HTML content of the webpage (numbers in [] are element bid, not coordinates). Cache the bids for retrieval for action call:
{html}

## Context
### Current Progress
{progress}

### Previously Executed Steps
{previous_steps}

### Recent Action Trace
{trace_string}"""


def grounding_prompt_after_img(html, trace_string, plan=None, screenshot=None, progress="", previous_steps=""):
    res = GROUNDING_PROMPT_AFTER_IMG_PART1.format(
        html=html, 
        trace_string=trace_string or "No previous actions yet.",
        progress=progress or "Starting the task.",
        previous_steps=previous_steps or "None"
    )
    if plan is not None:
        res += f"""Here's a rough plan to achieve this goal from this point on:
{plan}

Pay close attention to the first step in the plan above."""
    res += "If an action could not be performed with bid, consider using coordinates. "

    if screenshot is not None:
        # Add dimensions of the screenshot
        res += f"For reference, the width of the screenshot is {screenshot.shape[1]} pixels and the height is {screenshot.shape[0]} pixels. "

    res += ANSWER_PROMPT

    return res
