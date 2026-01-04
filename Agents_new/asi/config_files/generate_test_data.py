"""Replace the website placeholders with website domains from env_config
Generate the test data"""

import os
import json

BASE_URL = os.environ.get("BASE_URL")
SHOPPING = f"{BASE_URL}:7770"
SHOPPING_ADMIN = f"{BASE_URL}:7780/admin"
REDDIT = f"{BASE_URL}:9999"
GITLAB = f"{BASE_URL}:8023"
MAP = f"{BASE_URL}:3000"
WIKIPEDIA = f"{BASE_URL}:8888/wikipedia_en_all_maxi_2022-05/A/User:The_other_Kiwix_guy/Landing"


def main() -> None:
    with open("config_files/test.raw.json", "r") as f:
        raw = f.read()
    raw = raw.replace("__GITLAB__", GITLAB)
    raw = raw.replace("__REDDIT__", REDDIT)
    raw = raw.replace("__SHOPPING__", SHOPPING)
    raw = raw.replace("__SHOPPING_ADMIN__", SHOPPING_ADMIN)
    raw = raw.replace("__WIKIPEDIA__", WIKIPEDIA)
    raw = raw.replace("__MAP__", MAP)
    with open("config_files/test.json", "w") as f:
        f.write(raw)
    # split to multiple files
    data = json.loads(raw)
    for idx, item in enumerate(data):
        with open(f"config_files/{idx}.json", "w") as f:
            json.dump(item, f, indent=2)


if __name__ == "__main__":
    main()