from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Optional, List, Dict, Any, Iterator, IO, Callable
from contextlib import ExitStack
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

from pridexyz.modrinth.types import NewProject, DictKV, NewVersion, GalleryImage, ProjectUpdate


class ModrinthAPIError(Exception):
    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        response: Optional[Dict[str, Any]] = None
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.response = response or {}


def cut_game_versions_until(cutoff_version: str, versions: List[DictKV]) -> List[DictKV]:
    result: List[DictKV] = []
    for version in versions:
        result.append(version)
        if version.get("version") == cutoff_version:
            break
    return result


class ModrinthAPI:
    def __init__(
        self, token: str, api_url: str = "https://api.modrinth.com", user_agent: str = "requests/2.32.5"
    ) -> None:
        self.api_url = api_url
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": token,
                "User-Agent": user_agent
            }
        )
        self._ratelimit_lock = threading.Lock()
        self._ratelimit_limit = 300
        self._ratelimit_remaining = 300
        self._ratelimit_reset = 0
        self._ratelimit_last_checked = time.time()

    def _update_ratelimit(self, response: requests.Response):
        with self._ratelimit_lock:
            try:
                limit = int(response.headers.get("X-Ratelimit-Limit", self._ratelimit_limit))
                remaining = int(response.headers.get("X-Ratelimit-Remaining", self._ratelimit_remaining))
                reset = int(response.headers.get("X-Ratelimit-Reset", 0))
            except Exception:
                limit = self._ratelimit_limit
                remaining = self._ratelimit_remaining
                reset = 0

            self._ratelimit_limit = limit
            self._ratelimit_remaining = remaining
            self._ratelimit_reset = reset
            self._ratelimit_last_checked = time.time()

    def _respect_ratelimit(self):
        with self._ratelimit_lock:
            if self._ratelimit_remaining <= 0:
                sleep_time = self._ratelimit_reset
                if sleep_time > 0:
                    time.sleep(sleep_time)
                self._ratelimit_remaining = self._ratelimit_limit
                self._ratelimit_reset = 0

    def _request(self, method: str, endpoint: str, api_version: int = 2, **kwargs) -> Any:
        url = f"{self.api_url}/v{api_version}{endpoint}"
        response = None
        self._respect_ratelimit()
        try:
            response = self.session.request(method, url, **kwargs)
            self._update_ratelimit(response)
            response.raise_for_status()
            return response.json() if response.text else {}
        except requests.HTTPError as e:
            try:
                error_json = response.json()
            except Exception:
                error_json = {"error": response.text if response else "No response"}
            raise ModrinthAPIError(
                str(e),
                status_code=response.status_code if response else None,
                response=error_json
            ) from e

    @staticmethod
    def _to_dict(obj: Any) -> Dict[str, Any]:
        return {key: value for key, value in obj.__dict__.items() if value is not None}

    @staticmethod
    def _open_files(paths: List[Path]) -> Iterator[Dict[str, IO[bytes]]]:
        with ExitStack() as stack:
            files = {f"file{idx}": stack.enter_context(p.open("rb")) for idx, p in enumerate(paths)}
            yield files

    def create_project(self, project: NewProject, icon_path: Optional[Path] = None) -> DictKV:
        payload = self._to_dict(project)
        if "donation_urls" in payload:
            payload["donation_urls"] = [du.__dict__ for du in payload["donation_urls"]]

        if icon_path:
            with icon_path.open("rb") as icon_file:
                return self._request(
                    "POST",
                    "/project",
                    data={"data": json.dumps(payload)},
                    files={"icon": icon_file}
                )
        return self._request("POST", "/project", data={"data": json.dumps(payload)})

    def get_project(self, id_or_slug: str) -> DictKV:
        return self._request("GET", f"/project/{id_or_slug}")

    def get_version(self, version_id: str) -> DictKV:
        return self._request("GET", f"/version/{version_id}")

    def get_organization_projects(self, organization_id: str) -> DictKV:
        return self._request("GET", f"/organization/{organization_id}/projects", 3)

    def modify_project(self, id_or_slug: str, update: ProjectUpdate) -> None:
        payload = self._to_dict(update)
        self._request("PATCH", f"/project/{id_or_slug}", json=payload)

    def change_project_icon(self, id_or_slug: str, icon_path: Path, ext: str) -> None:
        with icon_path.open("rb") as icon_file:
            self._request(
                "PATCH",
                f"/project/{id_or_slug}/icon",
                params={"ext": ext},
                data=icon_file
            )

    def create_version(self, version: NewVersion, file_paths: List[Path], primary_file: Optional[str] = None) -> DictKV:
        with ExitStack() as stack:
            files = {
                f"file{idx}": stack.enter_context(path.open("rb"))
                for idx, path in enumerate(file_paths)
            }
            payload: DictKV = {
                **version.__dict__,
                "file_parts": list(files.keys()),
            }
            if primary_file:
                payload["primary_file"] = primary_file

            return self._request(
                "POST",
                "/version",
                data={"data": json.dumps(payload)},
                files=files
            )

    def add_gallery_image(self, id_or_slug: str, image: GalleryImage) -> None:
        params: DictKV = {"ext": image.ext, "featured": str(image.featured).lower()}
        if image.title:
            params["title"] = image.title
        if image.description:
            params["description"] = image.description
        if image.ordering is not None:
            params["ordering"] = image.ordering

        with image.image_path.open("rb") as img_file:
            self._request(
                "POST",
                f"/project/{id_or_slug}/gallery",
                params=params,
                data=img_file
            )

    def delete_gallery_image(self, id_or_slug: str, image_url: str) -> None:
        self._request(
            "DELETE",
            f"/project/{id_or_slug}/gallery",
            params={"url": image_url}
        )

    def delete_version(self, version_id: str) -> None:
        self._request(
            "DELETE",
            f"/version/{version_id}"
        )

    def get_game_versions(self) -> List[DictKV]:
        return self._request("GET", "/tag/game_version")

    def get_loaders(self) -> List[DictKV]:
        return self._request("GET", "/tag/loader")

    def get_game_versions_until(self, cutoff_version: str) -> List[DictKV]:
        versions = self.get_game_versions()
        result: List[DictKV] = []
        for version in versions:
            result.append(version)
            if version.get("version") == cutoff_version:
                break
        return result

    def parallel_requests(self, requests_list: List[Callable[[], Any]], max_parallel: int = 6) -> List[Any]:
        """Execute several API calls in parallel, whilst respecting Modrinth rate limits."""
        results = [None] * len(requests_list)

        def run_with_ratelimit(index: int, fn: Callable[[], Any]):
            self._respect_ratelimit()
            try:
                return fn()
            except Exception as e:
                return e

        with ThreadPoolExecutor(max_workers=max_parallel) as executor:
            future_to_index = {
                executor.submit(run_with_ratelimit, i, fn): i
                for i, fn in enumerate(requests_list)
            }
            for future in as_completed(future_to_index):
                idx = future_to_index[future]
                result = future.result()
                results[idx] = result

        for r in results:
            if isinstance(r, Exception):
                raise r

        return results

    def get_project_versions(self, id_or_slug):
        return self._request("GET", f"/project/{id_or_slug}/version")
