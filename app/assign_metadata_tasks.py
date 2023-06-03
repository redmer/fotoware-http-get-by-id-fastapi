from enum import Enum
from typing import Awaitable, Callable, Iterable

from fastapi import HTTPException

from .config import (
    FOTOWARE_FIELDNAME_IMGSUBJ,
    FOTOWARE_FIELDNAME_PHASH,
    FOTOWARE_FIELDNAME_SHA256,
    FOTOWARE_FIELDNAME_UUID,
)
from .fotoware import api
from .fotoware.apitypes import Asset
from .log import AppLog
from .tasks import calc_detectobject, calc_perceptualhash, calc_sha256, calc_uuid


class Task(str, Enum):
    """Tasks when enumerating files"""

    object_detection = "object-detection"
    perceptual_hash = "perceptual-hash"
    sha256 = "sha256"
    uuid = "uuid4"


def task_info(
    task: Task,
) -> (
    tuple[str, Callable[[Asset], Awaitable[str | list[str] | None]]] | tuple[None, None]
):
    """Fieldname used for task"""
    return {
        Task.object_detection: (FOTOWARE_FIELDNAME_IMGSUBJ, calc_detectobject),
        Task.perceptual_hash: (FOTOWARE_FIELDNAME_PHASH, calc_perceptualhash),
        Task.sha256: (FOTOWARE_FIELDNAME_SHA256, calc_sha256),
        Task.uuid: (FOTOWARE_FIELDNAME_UUID, calc_uuid),
    }.get(task, (None, None))


async def exec_update_tasks(*, assets: Iterable[Asset], tasks: Iterable[Task]):
    """
    Execute update tasks for assets. If the file a already has a value for that metadata
    field, it is NOT recalculated.
    """
    combined_updates = dict()

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
