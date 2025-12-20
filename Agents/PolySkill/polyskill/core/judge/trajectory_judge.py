"""
LLM as Judge for Digital Agent Trajectories.

Adapted from Online-Mind2Web evaluation methods to work with digital agent trajectory data.
"""

import asyncio
import tempfile
import re
from typing import List, Optional, Dict, Any
from PIL import Image

from polyskill.model.fm import FoundationModel
from .utils import (
    load_trajectory_data, 
    extract_screenshots_from_trajectory,
    get_final_response_from_trajectory,
    extract_task_from_trajectory,
    get_trajectory_success_status,
    extract_actions_from_trajectory,
    encode_image
)


class TrajectoryJudge:
    """
    LLM-based judge for evaluating digital agent trajectories.
    
    Provides multiple evaluation methods adapted from Online-Mind2Web:
    - WebJudge General: General web task evaluation
    - WebJudge Online Mind2Web: Specific to Mind2Web-style tasks  
    - WebVoyager: Screenshot-based evaluation
    """
    
    def __init__(self, model_config: Dict[str, Any]):
        """
        Initialize the trajectory judge.
        
        Args:
            model_config: Configuration for the foundation model
        """
        self.model = FoundationModel(**model_config)
        self.max_images = 50
    
    async def identify_key_points(self, task: str, input_image_paths: Optional[List[str]] = None) -> str:
        """
        Identify key points from task description and optional input images.
        
        Args:
            task: Task description
            input_image_paths: Optional paths to input images
            
        Returns:
            Key points as a string
        """
        system_msg = """You are an expert tasked with analyzing a given task to identify the key points explicitly stated in the task description.

**Objective**: Carefully analyze the task description and extract the critical elements explicitly mentioned in the task for achieving its goal.

**Instructions**:
1. Read the task description carefully.
2. Identify and extract **key points** directly stated in the task description.
   - A **key point** is a critical element, condition, or step explicitly mentioned in the task description.
   - Do not infer or add any unstated elements.
   - Words such as "best," "highest," "cheapest," "latest," "most recent," "lowest," "closest," "highest-rated," "largest," and "newest" must go through the sort function(e.g., the key point should be "Filter by highest").

**Respond with**:
- **Key Points**: A numbered list of the explicit key points for completing this task, one per line, without explanations or additional details."""
        
        prompt = f"Task: {task}"
        
        input_images_msg = []
        if input_image_paths:
            for input_image_path in input_image_paths:
                input_images_jpg_base64_str = encode_image(Image.open(input_image_path))
                input_images_msg.append({
                    'type': 'image_url',
                    'image_url': {"url": f"data:image/png;base64,{input_images_jpg_base64_str}", "detail": "high"}
                })

        messages = [
            {"role": "system", "content": system_msg},
            {
                "role": "user",
                "content": [{"type": "text", "text": prompt}] + input_images_msg,
            }
        ]
        
        response = await asyncio.to_thread(self.model.generate, messages=messages)
        return response[0] if isinstance(response, tuple) else response

    async def judge_trajectory_webjudge_general(self, 
                                              trajectory_path: str,
                                              input_image_paths: Optional[List[str]] = None,
                                              temp_dir: Optional[str] = None,
                                              score_threshold: int = 3) -> Dict[str, Any]:
        """
        Evaluate trajectory using WebJudge General method.
        
        Args:
            trajectory_path: Path to trajectory.pb.xz file
            input_image_paths: Optional input images for context
            temp_dir: Temporary directory for screenshots
            score_threshold: Minimum score for screenshots to be included
            
        Returns:
            Evaluation results dictionary
        """
        # Load trajectory data
        trajectory_data = load_trajectory_data(trajectory_path)
        task = extract_task_from_trajectory(trajectory_data)
        actions = extract_actions_from_trajectory(trajectory_data)
        action_thoughts = None  # Could extract from trajectory if available
        
        # Extract screenshots
        if temp_dir is None:
            temp_dir = tempfile.mkdtemp()
        
        screenshot_paths = extract_screenshots_from_trajectory(
            trajectory_data, save_dir=temp_dir, max_images=self.max_images
        )
        
        # Get key points
        key_points_raw = await self.identify_key_points(task, input_image_paths)
        key_points = self._process_key_points(key_points_raw)
        
        # Judge each screenshot in parallel
        print(f"Judging {len(screenshot_paths)} screenshots in parallel...")
        
        async def judge_single_screenshot(i: int, screenshot_path: str):
            """Judge a single screenshot and return processed results."""
            try:
                judgment_response = await self._judge_single_image_detailed(task, screenshot_path, key_points, input_image_paths)
                
                # Extract score from response
                pattern = r"[1-5]"
                score_text = judgment_response.split("### Score")[1] if "### Score" in judgment_response else judgment_response.split("Score:")[1]
                thought = judgment_response.split("### Reasoning:")[-1].strip().split("### Score")[0].replace('\n', ' ') if "### Reasoning:" in judgment_response else ""
                score = int(re.findall(pattern, score_text)[0]) if re.findall(pattern, score_text) else 0
                
                return {
                    'step': i,
                    'screenshot_path': screenshot_path,
                    'judgment': judgment_response,
                    'score': score,
                    'thought': thought
                }
            except Exception as e:
                print(f"Error processing screenshot {i}: {e}")
                return {
                    'step': i,
                    'screenshot_path': screenshot_path,
                    'judgment': f"Error: {str(e)}",
                    'score': 0,
                    'thought': ""
                }
        
        # Process all screenshots in parallel
        judgment_tasks = [
            judge_single_screenshot(i, screenshot_path) 
            for i, screenshot_path in enumerate(screenshot_paths)
        ]
        screenshot_judgments = await asyncio.gather(*judgment_tasks)
        
        # Sort by step to maintain order
        screenshot_judgments.sort(key=lambda x: x['step'])
        
        # Collect high-scoring screenshots
        high_score_images = []
        high_score_thoughts = []
        for judgment in screenshot_judgments:
            if judgment['score'] >= score_threshold:
                high_score_images.append(judgment['screenshot_path'])
                if judgment['thought']:
                    high_score_thoughts.append(judgment['thought'])
        
        # Limit high-scoring images
        high_score_images = high_score_images[:self.max_images]
        high_score_thoughts = high_score_thoughts[:self.max_images]
        
        # Final evaluation with high-scoring screenshots
        final_evaluation = await self._final_webjudge_evaluation(
            task, key_points, actions, action_thoughts, 
            high_score_images, high_score_thoughts, input_image_paths
        )
        
        # Extract success status
        trajectory_success = self._extract_success_from_evaluation(final_evaluation)
        
        return {
            'task': task,
            'trajectory_success': trajectory_success,
            'key_points': key_points,
            'screenshot_judgments': screenshot_judgments,
            'high_score_screenshots': high_score_images,
            'final_evaluation': final_evaluation,
            'num_screenshots': len(screenshot_paths),
            'num_high_score': len(high_score_images)
        }

    async def judge_trajectory_webjudge_online_mind2web(self,
                                                       trajectory_path: str,
                                                       temp_dir: Optional[str] = None,
                                                       score_threshold: int = 3) -> Dict[str, Any]:
        """
        Evaluate trajectory using WebJudge Online Mind2Web method.
        
        Args:
            trajectory_path: Path to trajectory.pb.xz file
            temp_dir: Temporary directory for screenshots
            score_threshold: Minimum score for screenshots to be included
            
        Returns:
            Evaluation results dictionary
        """
        try:
            # Load trajectory data
            print(f"Loading trajectory data from: {trajectory_path}")
            trajectory_data = load_trajectory_data(trajectory_path)
            print(f"Loaded trajectory with {len(trajectory_data.actions)} actions")
            
            task = extract_task_from_trajectory(trajectory_data)
            print(f"Task: {task}")
            
            actions = extract_actions_from_trajectory(trajectory_data)
            print(f"Extracted {len(actions)} actions")
            
            # Extract screenshots
            if temp_dir is None:
                temp_dir = tempfile.mkdtemp()
                
            print(f"Extracting screenshots to: {temp_dir}")
            screenshot_paths = extract_screenshots_from_trajectory(
                trajectory_data, save_dir=temp_dir, max_images=self.max_images
            )
            print(f"Extracted {len(screenshot_paths)} screenshots")
            
            # Get key points (without input images for Mind2Web style)
            print("Identifying key points...")
            key_points_raw = await self.identify_key_points(task)
            key_points = self._process_key_points(key_points_raw)
            print(f"Key points: {key_points[:200]}...")
            
            # Judge each screenshot in parallel
            print(f"Judging {len(screenshot_paths)} screenshots in parallel...")
            
            async def judge_single_screenshot_mind2web(i: int, screenshot_path: str):
                """Judge a single screenshot using Mind2Web method and return processed results."""
                try:
                    judgment_response = await self._judge_single_image_mind2web(task, screenshot_path, key_points)
                    
                    # Extract score from response - Mind2Web format
                    pattern = r"[1-5]"
                    score_text = judgment_response.split("Score")[1] if "Score" in judgment_response else "0"
                    thought = judgment_response.split("**Reasoning**:")[-1].strip().split("\n\n")[0].replace('\n', ' ') if "**Reasoning**:" in judgment_response else ""
                    score = int(re.findall(pattern, score_text)[0]) if re.findall(pattern, score_text) else 0
                    
                    return {
                        'step': i,
                        'screenshot_path': screenshot_path,
                        'judgment': judgment_response,
                        'score': score,
                        'thought': thought
                    }
                except Exception as e:
                    print(f"Error processing screenshot {i}: {e}")
                    return {
                        'step': i,
                        'screenshot_path': screenshot_path,
                        'judgment': f"Error: {str(e)}",
                        'score': 0,
                        'thought': ""
                    }
            
            # Process all screenshots in parallel
            judgment_tasks = [
                judge_single_screenshot_mind2web(i, screenshot_path) 
                for i, screenshot_path in enumerate(screenshot_paths)
            ]
            screenshot_judgments = await asyncio.gather(*judgment_tasks)
            
            # Sort by step to maintain order
            screenshot_judgments.sort(key=lambda x: x['step'])
            
            # Collect high-scoring screenshots
            high_score_images = []
            high_score_thoughts = []
            for judgment in screenshot_judgments:
                if judgment['score'] >= score_threshold:
                    high_score_images.append(judgment['screenshot_path'])
                    if judgment['thought']:
                        high_score_thoughts.append(judgment['thought'])
            
            print(f"Found {len(high_score_images)} high-scoring screenshots")
            
            # Limit high-scoring images
            high_score_images = high_score_images[:self.max_images]
            high_score_thoughts = high_score_thoughts[:self.max_images]
            
            # Final evaluation with high-scoring screenshots
            print("Performing final evaluation...")
            final_evaluation = await self._final_mind2web_evaluation(
                task, key_points, actions, high_score_images, high_score_thoughts
            )
            
            # Extract success status
            trajectory_success = self._extract_success_from_evaluation(final_evaluation)
            print(f"Final trajectory success: {trajectory_success}")
            
            return {
                'task': task,
                'trajectory_success': trajectory_success,
                'key_points': key_points,
                'screenshot_judgments': screenshot_judgments,
                'high_score_screenshots': high_score_images,
                'final_evaluation': final_evaluation,
                'num_screenshots': len(screenshot_paths),
                'num_high_score': len(high_score_images)
            }
            
        except Exception as e:
            print(f"Error in judge_trajectory_webjudge_online_mind2web: {e}")
            import traceback
            traceback.print_exc()
            raise
    
    async def judge_trajectory_webvoyager(self,
                                        trajectory_path: str,
                                        k: int = 0,
                                        temp_dir: Optional[str] = None) -> Dict[str, Any]:
        """
        Evaluate trajectory using WebVoyager method.
        
        Args:
            trajectory_path: Path to trajectory.pb.xz file
            k: Number of final screenshots to use (0 = all)
            temp_dir: Temporary directory for screenshots
            
        Returns:
            Evaluation results dictionary
        """
        # Load trajectory data
        trajectory_data = load_trajectory_data(trajectory_path)
        task = extract_task_from_trajectory(trajectory_data)
        final_response = get_final_response_from_trajectory(trajectory_data)
        
        # Extract screenshots
        if temp_dir is None:
            temp_dir = tempfile.mkdtemp()
            
        screenshot_paths = extract_screenshots_from_trajectory(
            trajectory_data, save_dir=temp_dir, max_images=self.max_images
        )
        
        # Use final k screenshots or all if k=0
        if k > 0:
            screenshot_paths = screenshot_paths[-k:]
        
        # Prepare WebVoyager evaluation
        system_msg = """As an evaluator, you will be presented with three primary components to assist you in your role:

1. Web Task Instruction: This is a clear and specific directive provided in natural language, detailing the online activity to be carried out. These requirements may include conducting searches, verifying information, comparing prices, checking availability, or any other action relevant to the specified web service (such as Amazon, Apple, ArXiv, BBC News, Booking etc).

2. Result Screenshots: This is a visual representation of the screen showing the result or intermediate state of performing a web task. It serves as visual proof of the actions taken in response to the instruction.

3. Result Response: This is a textual response obtained after the execution of the web task. It serves as textual result in response to the instruction.

-- You DO NOT NEED to interact with web pages or perform actions such as booking flights or conducting searches on websites.
-- You SHOULD NOT make assumptions based on information not presented in the screenshot when comparing it to the instructions.
-- Your primary responsibility is to conduct a thorough assessment of the web task instruction against the outcome depicted in the screenshot and in the response, evaluating whether the actions taken align with the given instructions.
-- NOTE that the instruction may involve more than one task, for example, locating the garage and summarizing the review. Failing to complete either task, such as not providing a summary, should be considered unsuccessful.
-- NOTE that the screenshot is authentic, but the response provided by LLM is generated at the end of web browsing, and there may be discrepancies between the text and the screenshots.
-- Note the difference: 1) Result response may contradict the screenshot, then the content of the screenshot prevails, 2) The content in the Result response is not mentioned on the screenshot, choose to believe the content.

You should elaborate on how you arrived at your final evaluation and then provide a definitive verdict on whether the task has been successfully accomplished, either as 'SUCCESS' or 'FAILURE'."""

        prompt = f"""TASK: {task}

Result Response: {final_response}

{len(screenshot_paths)} screenshots at the end: """

        # Prepare image messages
        whole_content_img = []
        for screenshot_path in screenshot_paths:
            jpg_base64_str = encode_image(Image.open(screenshot_path))
            whole_content_img.append({
                'type': 'image_url',
                'image_url': {"url": f"data:image/png;base64,{jpg_base64_str}", "detail": "high"}
            })

        messages = [
            {"role": "system", "content": system_msg},
            {
                "role": "user",
                "content": [{"type": "text", "text": prompt}] 
                + whole_content_img
                + [{'type': 'text', 'text': "Your verdict:\n"}]
            }
        ]
        
        # Get evaluation
        response = await asyncio.to_thread(self.model.generate, messages=messages)
        evaluation = response[0] if isinstance(response, tuple) else response
        
        # Extract success status from evaluation
        trajectory_success = self._extract_success_from_evaluation(evaluation)
        
        return {
            'task': task,
            'final_response': final_response,
            'trajectory_success': trajectory_success,
            'screenshots_used': len(screenshot_paths),
            'evaluation': evaluation,
            'system_msg': system_msg,
            'prompt': prompt
        }

    async def _judge_single_image_detailed(self, task: str, image_path: str, key_points: str, input_image_paths: Optional[List[str]] = None) -> str:
        """
        Judge a single image for task completion evidence (WebJudge General style).
        """
        system_msg = """You are an expert evaluator tasked with determining whether an image contains information about the necessary steps to complete a task.

**Objective**: Analyze the provided image and decide if it shows essential steps or evidence required for completing the task. Use your reasoning to explain your decision before assigning a score.

**Instructions**:
1. Provide a detailed description of the image, including its contents, visible elements, text (if any), and any notable features.

2. Carefully examine the image and evaluate whether it contains necessary steps or evidence crucial to task completion:  
- Identify key points that could be relevant to task completion, such as actions, progress indicators, tool usage, applied filters, or step-by-step instructions.  
- Does the image show actions, progress indicators, or critical information directly related to completing the task?  
- Is this information indispensable for understanding or ensuring task success?
- If the image contains partial but relevant information, consider its usefulness rather than dismissing it outright.

3. Provide your response in the following format:  
- **Reasoning**: Explain your thought process and observations. Mention specific elements in the image that indicate necessary steps, evidence, or lack thereof.  
- **Score**: Assign a score based on the reasoning, using the following scale:  
    - **1**: The image does not contain any necessary steps or relevant information.  
    - **2**: The image contains minimal or ambiguous information, unlikely to be essential.  
    - **3**: The image includes some relevant steps or hints but lacks clarity or completeness.  
    - **4**: The image contains important steps or evidence that are highly relevant but not fully comprehensive.  
    - **5**: The image clearly displays necessary steps or evidence crucial for completing the task.

Respond with:  
### Reasoning**: [Your explanation]  
### Score**: [1-5]"""

        prompt = f"""**Task**: {task}

**Key Points for Task Completion**: {key_points}

The snapshot of the web page is shown in the image."""

        # Prepare input images if provided
        input_images_msg = []
        if input_image_paths:
            for input_image_path in input_image_paths:
                input_images_jpg_base64_str = encode_image(Image.open(input_image_path))
                input_images_msg.append({
                    'type': 'image_url',
                    'image_url': {"url": f"data:image/png;base64,{input_images_jpg_base64_str}", "detail": "high"}
                })

        messages = [{"role": "system", "content": system_msg}]

        if input_images_msg:
            messages.append({
                "role": "user",
                "content": [{"type": "text", "text": "The input images are:"}] + input_images_msg
            })
        
        # Add the screenshot to judge
        jpg_base64_str = encode_image(Image.open(image_path))
        messages.append({
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{jpg_base64_str}", "detail": "high"},
                },
            ]
        })
        
        response = await asyncio.to_thread(self.model.generate, messages=messages)
        return response[0] if isinstance(response, tuple) else response

    async def _judge_single_image_mind2web(self, task: str, image_path: str, key_points: str) -> str:
        """
        Judge a single image for task completion evidence (Mind2Web style).
        """
        system_msg = """You are an expert evaluator tasked with determining whether an image contains information about the necessary steps to complete a task.

**Objective**: Analyze the provided image and decide if it shows essential steps or evidence required for completing the task. Use your reasoning to explain your decision before assigning a score.

**Instructions**:
1. Provide a detailed description of the image, including its contents, visible elements, text (if any), and any notable features.

2. Carefully examine the image and evaluate whether it contains necessary steps or evidence crucial to task completion:  
- Identify key points that could be relevant to task completion, such as actions, progress indicators, tool usage, applied filters, or step-by-step instructions.  
- Does the image show actions, progress indicators, or critical information directly related to completing the task?  
- Is this information indispensable for understanding or ensuring task success?
- If the image contains partial but relevant information, consider its usefulness rather than dismissing it outright.

3. Provide your response in the following format:  
- **Reasoning**: Explain your thought process and observations. Mention specific elements in the image that indicate necessary steps, evidence, or lack thereof.  
- **Score**: Assign a score based on the reasoning, using the following scale:  
    - **1**: The image does not contain any necessary steps or relevant information.  
    - **2**: The image contains minimal or ambiguous information, unlikely to be essential.  
    - **3**: The image includes some relevant steps or hints but lacks clarity or completeness.  
    - **4**: The image contains important steps or evidence that are highly relevant but not fully comprehensive.  
    - **5**: The image clearly displays necessary steps or evidence crucial for completing the task.

Respond with:  
1. **Reasoning**: [Your explanation]  
2. **Score**: [1-5]"""

        jpg_base64_str = encode_image(Image.open(image_path))

        prompt = f"""**Task**: {task}

**Key Points for Task Completion**: {key_points}

The snapshot of the web page is shown in the image."""

        messages = [
            {"role": "system", "content": system_msg},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{jpg_base64_str}", "detail": "high"},
                    },
                ],
            }
        ]

        response = await asyncio.to_thread(self.model.generate, messages=messages)
        return response[0] if isinstance(response, tuple) else response

    def _process_key_points(self, key_points_raw: str) -> str:
        """Process raw key points response to extract clean key points."""
        key_points = key_points_raw.replace("\n\n", "\n")
        
        try:
            key_points = key_points.split("**Key Points**:")[1]
            key_points = "\n".join(line.lstrip() for line in key_points.splitlines())
        except:
            try:
                key_points = key_points.split("Key Points:")[-1]
                key_points = "\n".join(line.lstrip() for line in key_points.splitlines())
            except:
                # Fallback: use raw key points
                pass
        
        return key_points
    
    async def _final_webjudge_evaluation(self, task: str, key_points: str, actions: List[str], 
                                       action_thoughts: Optional[List[str]], high_score_images: List[str], 
                                       high_score_thoughts: List[str], input_image_paths: Optional[List[str]] = None) -> str:
        """Perform final evaluation using WebJudge General method."""
        system_msg = """You are an expert in evaluating the performance of a web navigation agent. The agent is designed to help a human user navigate a website to complete a task. Given the user's task, the agent's action history, key points for task completion, some potentially important web pages in the agent's trajectory and their reasons, your goal is to determine whether the agent has completed the task and achieved all requirements.

Your response must strictly follow the following evaluation criteria!
*Important Evaluation Criteria*:
1: The filtered results must be displayed correctly. If filters were not properly applied (i.e., missing selection, missing confirmation, or no visible effect in results), it should be considered a failure.
2: You must carefully check whether these snapshots and action history meet these key points. Ensure that specific filter conditions, such as "best," "highest," "cheapest," "latest," "most recent," "lowest," "closest," "highest-rated," "largest," and "newest" are correctly applied using the filter function(e.g., sort function).
3: Certain key points or requirements should be applied by the filter. Otherwise, a search with all requirements as input will be deemed a failure since it cannot guarantee that all results meet the requirements!
4: If the task requires filtering by a specific range of money, years, or the number of beds and bathrooms, the applied filter must exactly match the given requirement. Any deviation results in failure. To ensure the task is successful, the applied filter must precisely match the specified range without being too broad or too narrow.
5: Some tasks require a submission action or a display of results to be considered successful. Repeat actions or actions that do not lead to a visible result should be considered a failure.
6: If the agent loops through a sequence of actions that do not make progress toward the goal (including failing to click "Save" or "Submit," etc.), it should be considered a failure.

Format your response into two lines as shown below:
Thoughts: <your thoughts and reasoning process should base on double-checking each key points and the evaluation criteria>
Status: "success" or "failure"""

        # Build prompt based on available data
        if len(high_score_images) == 0:
            prompt = f"""User Task: {task}

Key Points: {key_points}

Action History:
{chr(10).join(f"{i+1}. {action}" for i, action in enumerate(actions))}"""
        else:
            if action_thoughts:
                action_history = chr(10).join(f"{i+1}. {action}. Reasoning: {action_thought}" 
                                            for i, (action, action_thought) in enumerate(zip(actions, action_thoughts)))
            else:
                action_history = chr(10).join(f"{i+1}. {action}" for i, action in enumerate(actions))
            
            prompt = f"""User Task: {task}

Key Points: {key_points}

Action History:
{action_history}

The potentially important snapshots of the webpage in the agent's trajectory and their reasons:
{chr(10).join(f"{i+1}. {thought}" for i, thought in enumerate(high_score_thoughts))}"""

        # Prepare input images
        input_images_msg = []
        if input_image_paths:
            for path in input_image_paths:
                input_images_jpg_base64_str = encode_image(Image.open(path))
                input_images_msg.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{input_images_jpg_base64_str}", "detail": "high"}
                })

        messages = [{"role": "system", "content": system_msg}]

        if input_images_msg:
            messages.append({
                "role": "user",
                "content": [{"type": "text", "text": "The input images are:"}] + input_images_msg
            })

        # Prepare high-score images
        high_score_img_msgs = []
        for image_path in high_score_images:
            jpg_base64_str = encode_image(Image.open(image_path))
            high_score_img_msgs.append({
                'type': 'image_url',
                'image_url': {"url": f"data:image/png;base64,{jpg_base64_str}", "detail": "high"}
            })

        messages.append({
            "role": "user",
            "content": [{"type": "text", "text": prompt}] + high_score_img_msgs
        })
        
        response = await asyncio.to_thread(self.model.generate, messages=messages)
        return response[0] if isinstance(response, tuple) else response
    
    async def _final_mind2web_evaluation(self, task: str, key_points: str, actions: List[str], 
                                       high_score_images: List[str], high_score_thoughts: List[str]) -> str:
        """Perform final evaluation using WebJudge Online Mind2Web method."""
        system_msg = """You are an expert in evaluating the performance of a web navigation agent. The agent is designed to help a human user navigate a website to complete a task. Given the user's task, the agent's action history, key points for task completion, some potentially important web pages in the agent's trajectory and their reasons, your goal is to determine whether the agent has completed the task and achieved all requirements.

Your response must strictly follow the following evaluation criteria!
*Important Evaluation Criteria*:
1: The filtered results must be displayed correctly. If filters were not properly applied (i.e., missing selection, missing confirmation, or no visible effect in results), the task is not considered successful.
2: You must carefully check whether these snapshots and action history meet these key points. Ensure that specific filter conditions, such as "best," "highest," "cheapest," "latest," "most recent," "lowest," "closest," "highest-rated," "largest," and "newest" are correctly applied using the filter function(e.g., sort function).
3: Certain key points or requirements should be applied by the filter. Otherwise, a search with all requirements as input will be deemed a failure since it cannot guarantee that all results meet the requirements!
4: If the task requires filtering by a specific range of money, years, or the number of beds and bathrooms, the applied filter must exactly match the given requirement. Any deviation results in failure. To ensure the task is successful, the applied filter must precisely match the specified range without being too broad or too narrow.
Examples of Failure Cases:
- If the requirement is less than $50, but the applied filter is less than $25, it is a failure.
- If the requirement is $1500-$2500, but the applied filter is $2000-$2500, it is a failure.
- If the requirement is $25-$200, but the applied filter is $0-$200, it is a failure.
- If the required years are 2004-2012, but the filter applied is 2001-2012, it is a failure.
- If the required years are before 2015, but the applied filter is 2000-2014, it is a failure.
- If the task requires exactly 2 beds, but the filter applied is 2+ beds, it is a failure.
5: Some tasks require a submission action or a display of results to be considered successful.
6: If the retrieved information is invalid or empty(e.g., No match was found), but the agent has correctly performed the required action, it should still be considered successful.
7: If the current page already displays all available items, then applying a filter is not necessary. As long as the agent selects items that meet the requirements (e.g., the cheapest or lowest price), the task is still considered successful.

*IMPORTANT*
Format your response into two lines as shown below:

Thoughts: <your thoughts and reasoning process based on double-checking each key points and the evaluation criteria>
Status: "success" or "failure"""

        # Build prompt
        if len(high_score_images) == 0:
            prompt = f"""User Task: {task}

Key Points: {key_points}

Action History:
{chr(10).join(f"{i+1}. {action}" for i, action in enumerate(actions))}"""
        else:
            prompt = f"""User Task: {task}

Key Points: {key_points}

Action History:
{chr(10).join(f"{i+1}. {action}" for i, action in enumerate(actions))}

The potentially important snapshots of the webpage in the agent's trajectory and their reasons:
{chr(10).join(f"{i+1}. {thought}" for i, thought in enumerate(high_score_thoughts))}"""

        # Prepare high-score images
        high_score_img_msgs = []
        for image_path in high_score_images:
            jpg_base64_str = encode_image(Image.open(image_path))
            high_score_img_msgs.append({
                'type': 'image_url',
                'image_url': {"url": f"data:image/png;base64,{jpg_base64_str}", "detail": "high"}
            })

        messages = [
            {"role": "system", "content": system_msg},
            {
                "role": "user",
                "content": [{"type": "text", "text": prompt}] + high_score_img_msgs
            }
        ]
        
        response = await asyncio.to_thread(self.model.generate, messages=messages)
        return response[0] if isinstance(response, tuple) else response
    
    def _extract_success_from_evaluation(self, evaluation: str) -> bool:
        """
        Extract success/failure status from final evaluation.
        
        Uses the exact same logic as Online-Mind2Web's extract_predication function.
        """
        try:
            # This is the exact logic from Online-Mind2Web for WebJudge methods
            if "success" in evaluation.lower().split('status:')[1]:
                return True
            else:
                return False
        except:
            # Fallback if status: format not found
            return False