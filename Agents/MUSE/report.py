
import os
import json
import pandas as pd
from typing import Dict, List, Optional
from monitor import Monitor

def iter_round_dirs(base_dir: str):
    for agent in os.listdir(base_dir):
        agent_path = os.path.join(base_dir, agent)
        if not os.path.isdir(agent_path):
            continue
        for data_split in os.listdir(agent_path):
            split_path = os.path.join(agent_path, data_split)
            if not os.path.isdir(split_path):
                continue
            for task in os.listdir(split_path):
                task_path = os.path.join(split_path, task)
                if not os.path.isdir(task_path):
                    continue
                for name in os.listdir(task_path):
                    round_path = os.path.join(task_path, name)
                    if os.path.isdir(round_path) and name.startswith("round_"):
                        try:
                            yield agent, data_split, task, int(name[6:]), round_path
                        except ValueError:
                            continue

def compute_score(total: Optional[int], result: Optional[int]) -> float:
    if total and total != 0 and result is not None:
        ratio = result / total
        s_full = 1.0 if result == total else 0.0
        return round(0.5 * ratio + 0.5 * s_full, 4)
    return 0.0

def get_split(task: str, task_split_dict: Optional[Dict[str, List[str]]]) -> str:
    if task_split_dict:
        for split_name, task_list in task_split_dict.items():
            if task in task_list:
                return split_name
    return "unspecified"

def collect_task_records(
    base_dir: str,
    task_split_dict: Optional[Dict[str, List[str]]] = None,
    tools_of_interest: Optional[List[str]] = None,
):
    detail_rows, exception_rows = [], []

    for agent, data_split, task, round_idx, dir_path in iter_round_dirs(base_dir):
        total = result = None
        eval_fp = os.path.join(dir_path, "agent_eval_output.json")
        if os.path.isfile(eval_fp):
            try:
                with open(eval_fp, "r", encoding="utf-8") as f:
                    score = json.load(f).get("final_score", {})
                total, result = score.get("total", 0), score.get("result", 0)
            except Exception:
                total, result = None, None
        final_score = compute_score(total, result)
        checkpoints = f"{result}/{total}" if total not in (None, 0) else "N/A"

        monitor = None
        exception_count = 0
        overall_fp = os.path.join(dir_path, "overall_state.json")
        if os.path.isfile(overall_fp):
            try:
                with open(overall_fp, "r", encoding="utf-8") as f:
                    overall_state = json.load(f)
                monitor = Monitor.from_dict(overall_state.get("monitor_state", {}))

                if monitor and monitor.exception.is_exception():
                    if monitor.exception.subtask_limit_exceeded > 0:
                        exception_rows.append({
                            "Agent": agent,
                            "Task": task,
                            "RoundIndex": round_idx,
                            "DataSplit": data_split,
                            "Split": get_split(task, task_split_dict),
                            "ExceptionType": "subtask_limit_exceeded",
                            "Message": str(monitor.exception.subtask_limit_exceeded),
                        })
                        exception_count += 1
                    for mem_ex in monitor.exception.memory_exception:
                        exception_rows.append({
                            "Agent": agent,
                            "Task": task,
                            "RoundIndex": round_idx,
                            "DataSplit": data_split,
                            "Split": get_split(task, task_split_dict),
                            "ExceptionType": "memory_exception",
                            "Message": str(mem_ex),
                        })
                        exception_count += 1
            except Exception as e:
                print(f"[WARN] Failed to read monitor from {overall_fp}: {e}")

        difficulty_split = get_split(task, task_split_dict)

        row = {
            "Agent": agent,
            "Task": task,
            "RoundIndex": round_idx,
            "DataSplit": data_split,
            "Split": difficulty_split,
            "Checkpoints": checkpoints,
            "FinalScore": final_score,
            "NumActions": (monitor.num_actions if monitor else 0),
            "TimeUsed": (monitor.time_used if monitor else 0),
            "SubtasksUsed": (monitor.subtasks_used if monitor else 0),
            "ExceptionCount": exception_count
        }

        if monitor:
            items = monitor.tool_call.items()
            if tools_of_interest is not None:
                items = [(k, v) for k, v in items if k in tools_of_interest]
            for tname, tstat in items:
                row[tname] = tstat.calls

        detail_rows.append(row)

    df_detail = pd.DataFrame(detail_rows).sort_values(
        ["Agent","DataSplit","Split","Task","RoundIndex"]
    ).reset_index(drop=True)

    df_exceptions = pd.DataFrame(exception_rows).sort_values(
        ["Agent","DataSplit","Split","Task","RoundIndex"]
    ).reset_index(drop=True)

    return df_detail, df_exceptions

def print_grouped_report(df: pd.DataFrame):
    pd.set_option("display.max_columns", None)
    pd.set_option("display.width", 200)

    for agent, agent_group in df.groupby("Agent"):
        print("=" * 50, f" Agent: {agent} ", "=" * 50)

        for data_split, ds_group in agent_group.groupby("DataSplit"):
            print("——" * 30, f" DataSplit: {data_split.upper()} ", "——" * 30)

            for split, split_group in ds_group.groupby("Split"):
                print("  ··", f"Difficulty: {split}")
                cols_to_drop = [c for c in ["Agent","DataSplit","Split"] if c in split_group.columns]
                print(split_group.drop(columns=cols_to_drop).to_string(index=False))

                scores = pd.to_numeric(split_group["FinalScore"], errors='coerce')
                avg_score = scores.mean()

                total_tasks = len(split_group)
                full_completed = (split_group["FinalScore"] == 1.0).sum()
                full_completion_rate = round(full_completed / total_tasks, 4) if total_tasks > 0 else 0.0

                print(f"👉 平均 FinalScore（{data_split} / {split}）: "
                      f"{round(avg_score, 4) if not pd.isna(avg_score) else 'N/A'}")
                print(f"👉 完全完成率（{data_split} / {split}）: {full_completion_rate}")
            print()


def summarize_scores(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (agent, data_split, split), sub in df.groupby(["Agent","DataSplit","Split"]):
        result_sum, total_sum = 0, 0
        for cp in sub["Checkpoints"]:
            if isinstance(cp, str) and "/" in cp and cp != "N/A":
                r, t = cp.split("/")
                result_sum += int(r)
                total_sum += int(t)
        checkpoints_summary = f"{result_sum}/{total_sum}" if total_sum > 0 else "N/A"

        avg_score = pd.to_numeric(sub["FinalScore"], errors="coerce").mean()

        total_tasks = len(sub)
        full_completed = (sub["FinalScore"] == 1.0).sum()
        full_completion_rate = round(full_completed / total_tasks, 4) if total_tasks > 0 else 0.0

        metrics = {
            "Avg_NumActions": sub["NumActions"].mean(),
            "Avg_TimeUsed": sub["TimeUsed"].mean(),
            "Avg_SubtasksUsed": sub["SubtasksUsed"].mean(),
            "Avg_ExceptionCount": sub["ExceptionCount"].mean(),
        }

        rows.append({
            "Agent": agent,
            "DataSplit": data_split,
            "Split": split,
            "Checkpoints": checkpoints_summary,
            "Avg_FinalScore": round(avg_score, 4) if not pd.isna(avg_score) else "N/A",
            "FullCompletionRate": full_completion_rate,
            **{k: round(v, 4) for k,v in metrics.items()}
        })

    return pd.DataFrame(rows).sort_values(["Agent","DataSplit","Split"]).reset_index(drop=True)


if __name__ == "__main__":
    easy = [
        "hr-collect-feedbacks",
        "hr-new-grad-job-description-3",
        "admin-check-employees-budget-and-reply-and-record",
        "ds-sql-exercise",
        "finance-check-attendance-payroll",
        "pm-create-channel-message-medium",
        "pm-update-plane-issue-from-gitlab-status",
        "sde-update-issue-status-on-plane",
        "sde-update-dev-document",
    ]
    medium = [
        "hr-transfer-group",
        "hr-check-attendance-multiple-days-department-with-chat",
        "admin-read-survey-and-summarise",
        "ds-answer-spreadsheet-questions",
        "ds-visualize-data-in-pie-and-bar-chart",
        "finance-budget-variance",
        "pm-ask-for-issue-and-create-in-gitlab",
        "pm-check-backlog-update-issues",
        "sde-add-all-repos-to-docs",
    ]
    hard = [
        "hr-internal-tooling-slides",
        "hr-salary-analysis",
        "finance-invoice-matching",
        "finance-nonqualified-bill-ask-for-reimburse",
        "ds-calculate-spreadsheet-stats",
        "ds-predictive-modeling",
        "admin-mass-forms-filling",
        "pm-present-engineer-group-members",
        "sde-copy-table-from-pdf-to-xlsx",
        "sde-sotopia-create-agent-wo-repo",
        "hr-mass-survey",
        "sde-create-commit-table-for-all-gitlab-users",
        "finance-create-10k-income-report",
    ]

    task_splits = {"1_easy": easy, "2_medium": medium, "3_hard": hard}
    # task_splits = {}
    tools_focus = ["access_the_application_guide"]  # Tools that need to report usage information

    df_report, df_exceptions = collect_task_records("outputs", task_splits, tools_of_interest=tools_focus)

    print_grouped_report(df_report)

    summary_df = summarize_scores(df_report)

    print(summary_df)
    print(df_exceptions)

    with pd.ExcelWriter("REPORT.xlsx") as writer:
        df_report.to_excel(writer, sheet_name="Detailed Report", index=False)
        summary_df.to_excel(writer, sheet_name="Summary", index=False)
        df_exceptions.to_excel(writer, sheet_name="Exceptions", index=False)

    print("\n✅ The report and summary are saved as an Excel file: REPORT.xlsx")
