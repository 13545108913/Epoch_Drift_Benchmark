import json
import traceback
from pathlib import Path
from typing import List, Dict, Optional, Union

memory_dir = "memory"
path = Path(memory_dir) / "procedural_memory.json"
application_guide: Dict[str, Dict[str, str]] = {}

def _update_application_guide() -> None:
    global application_guide
    try:
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
            if not text.strip():
                print(f"Warning: {path} is empty.")
            else:
                try:
                    application_guide = json.loads(text)
                except json.JSONDecodeError as e:
                    print(f"Error decoding JSON in {path}: {e}")
                    traceback.print_exc()
    except FileNotFoundError:
        print(f"File not found: {path}")
    except Exception as e:
        print(f"Unexpected error reading {path}: {e}")
        traceback.print_exc()

def _access_guides_core(batch_requests: Dict[str, List[str]]) -> str:
    """
    Core renderer for accessing multiple apps and their guide items at once.
    Returns a single formatted string that groups results by application.
    """
    global application_guide
    parts: List[str] = []

    for app_name, item_names in batch_requests.items():
        app_dict = application_guide.get(app_name)
        if app_dict is None:
            parts.append(
                f'<Application name="{app_name}">\n'
                f"  <Error>\n  In the guide, the platform/application `{app_name}` does not exist.\n  </Error>\n"
                f"</Application>"
            )
            continue

        # Normalize item_names: if empty/None -> list all items
        items_to_fetch = item_names or list(app_dict.keys())

        app_section: List[str] = [f'<Application name="{app_name}">']
        for name in items_to_fetch:
            detail = app_dict.get(name)
            if detail is not None:
                app_section.append(f"<{name}>\n{detail}\n</{name}>")
            else:
                app_section.append(
                    f"<{name}>\nThe entry '{name}' does not exist in the application '{app_name}'\n</{name}>"
                )
        app_section.append("</Application>")
        parts.append("\n".join(app_section))

    return "\n\n".join(parts)

async def access_the_application_guide(
    application_name: Optional[str] = None,
    item_names: Optional[List[str]] = None,
    batch_requests: Optional[Dict[str, List[str]]] = None,
):
    """
    Get detailed content of platform/application operation guides.

    Usage patterns:
    1) Single mode (single app):
        access_the_application_guide(application_name="RocketChat", item_names=["Login", "Create Channel"])
    2) Batch mode (multiple apps):
        access_the_application_guide(batch_requests={
            "RocketChat": ["Login", "Create Channel"],
            "GitLab": ["Create Project", "Add SSH Key"]
        })

    Notes:
    - If `item_names` is empty or None in either mode, all entries under that app will be returned.
    - Non-existent apps/items are reported but do not stop other results from being returned.

    Args:
        application_name: Name of the platform/application to query. - Only used in single-app mode. - Ignored if `batch_requests` is provided.
        item_names: A list of guide entry names under the given application. - If empty or None, all entries under that app will be returned. - Only used in single-app mode.
        batch_requests: Batch query specification: - Key: application name (str). - Value: list of entry names (List[str]). - If the list is empty or None, all entries under that app will be returned.
    """
    _update_application_guide()
    global application_guide

    # Normalize inputs into batch_requests
    if batch_requests is None:
        if application_name is None:
            yield {
                "data": "Error: Either provide (application_name, item_names) or batch_requests={app: [items...]}",
                "instruction": ""
            }
            return
        batch_requests = {application_name: item_names or []}

    # Build response for all requested apps
    data = _access_guides_core(batch_requests)
    yield {
        "data": data,
        "instruction": ""
    }
