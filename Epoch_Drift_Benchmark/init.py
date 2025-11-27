from browsergym.core.registration import register_task

from . import config
from . import task

ALL_MYBENCHMARK_TASK_IDS = []

def register_myBenchmark():
    for task_id in config.TASK_IDS:
        gym_id = f"myBenchmark.{task_id}"
        register_task(
            gym_id,
            task.GenericMyBenchmarkTask,
            task_kwargs={"task_id": task_id, "site_version": "v1"},
        )
        ALL_MYBENCHMARK_TASK_IDS.append(gym_id)