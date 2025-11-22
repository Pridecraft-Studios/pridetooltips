from typing import List

import dotenv

from util.modrinth.api import ModrinthAPI
from util.modrinth.types import DictKV


def simplify_versions(versions: List[DictKV]) -> List[str]:
    """
    Convert a list of GameVersion objects into a simple list of version strings.

    Args:
        versions: A list of GameVersion dicts.

    Returns:
        A list of version names like ["1.21.1", "1.21", "24w36a"].
    """


modrinth = ModrinthAPI(
    token=dotenv.get_key("../../.env", "MODRINTH_TOKEN"),
    api_url="https://api.modrinth.com",
    user_agent="Pridecraft-Studios/pridetooltips testing"
)


loaders = modrinth.get_loaders()
for loader in loaders:
    print(f"Loader: {loader['name']}: {loader['supported_project_types']}")