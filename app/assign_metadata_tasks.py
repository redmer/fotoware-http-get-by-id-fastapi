from enum import Enum
from typing import Awaitable, Callable, Iterable

from fastapi import HTTPException

from app.tasks.aspect_ratio import calc_aspect_ratio_label

from .config import (
    FOTOWARE_ASPECTRATIO_FIELD,
    FOTOWARE_FIELDNAME_SHA256,
    FOTOWARE_FIELDNAME_UUID,
)
from .fotoware import api
from .fotoware.apitypes import Asset
from .log import AppLog
from .tasks import calc_sha256, calc_uuid


class Task(str, Enum):
    """Tasks when enumerating files"""

    sha256 = "sha256"
    uuid = "uuid4"
    aspect_ratio_label = "aspect-ratio-label"


def task_info(
    task: Task,
) -> (
    tuple[str, Callable[[Asset], Awaitable[str | list[str] | None]]] | tuple[None, None]
):
    """Fieldname used for task"""
    return {
        Task.sha256: (FOTOWARE_FIELDNAME_SHA256, calc_sha256),
        Task.uuid: (FOTOWARE_FIELDNAME_UUID, calc_uuid),
        Task.aspect_ratio_label: (FOTOWARE_ASPECTRATIO_FIELD, calc_aspect_ratio_label),
    }.get(task, (None, None))


async def exec_update_tasks(*, assets: list[Asset], tasks: Iterable[Task]):
    """
    Execute update tasks for assets. If the file a already has a value for that metadata
    field, it is NOT recalculated.
    """
    combined_updates = dict()
    tasks = set([*tasks, Task.aspect_ratio_label])
    AppLog.debug(
        f"Will run tasks ({"".join(map(lambda t: t.value, tasks))}) for {len(assets)} assets"
    )

    for asset in assets:
        href = asset["href"]

        for task in tasks:
            task_field_name, task_func = task_info(task)

            if task_field_name is None or task_func is None:
                continue  # no field name or task_func configured

            if asset.get("metadata", {}).get(task_field_name) not in [None, ""]:
                continue  # already assigned

            value = await task_func(asset)  # possibly expensive
            if value is None:
                continue  # no value derived

            combined_updates[href] = {
                task_field_name: {"value": value},
                **combined_updates.get(href, {}),
            }

    for href, metadata in combined_updates.items():
        try:
            await api.update_asset_metadata(href, metadata)
        except HTTPException as err:
            if err.status_code >= 500:
                AppLog.error(f"Update of '{href}' ({metadata}) failed: {err.detail}")
            else:
                raise err

    return combined_updates
