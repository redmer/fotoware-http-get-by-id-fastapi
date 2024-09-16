import typing as t
from collections import defaultdict
from enum import Enum
from typing import Awaitable, Callable, Literal

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


type TaskCallable = Callable[[Asset], Awaitable[str | list[str] | None]]


def task_info(
    task: Task,
) -> tuple[str, TaskCallable, bool] | tuple[None, None, Literal[False]]:
    """Returns a tuple of (fieldname, callable, is-mass-updatable) for task."""
    return {
        Task.sha256: (FOTOWARE_FIELDNAME_SHA256, calc_sha256, False),
        Task.uuid: (FOTOWARE_FIELDNAME_UUID, calc_uuid, False),
        Task.aspect_ratio_label: (
            FOTOWARE_ASPECTRATIO_FIELD,
            calc_aspect_ratio_label,
            True,
        ),
    }.get(task, (None, None, False))


async def mass_update_asset_metadata(
    task_field_name: str, value2href: dict[str, list[str]]
):
    """Execute update tasks for asset, that have only a few distinct values"""
    for value, hrefs in value2href.items():
        payload = {
            "assets": [{"href": h} for h in hrefs],
            "job-metadata": [
                {
                    "field": task_field_name,
                    "value": value,
                }
            ],
        }
        r = await api.POST(
            "/fotoweb/me/background-tasks/",
            headers={
                "Content-Type": "application/vnd.fotoware.metadata-edit-request+json"
            },
            data=payload,
        )
        AppLog.info(f"Started mass-update ({task_field_name}, {value}), results: {r}")


async def exec_update_tasks(*, assets: t.AsyncIterable[Asset], tasks: t.Iterable[Task]):
    """
    Execute update tasks for assets. If the file a already has a value for that metadata
    field, it is NOT recalculated.
    """
    report_tasks_names: set[str] = set()
    report_asset_count: int = 0
    masstask_value_hrefs: dict[Task, dict[str, list[str]]] = defaultdict(
        lambda: defaultdict(list)
    )

    async for asset in assets:
        href = asset["href"]
        metadata: dict[str, dict[Literal["value"], str | list[str]]] = dict()

        for task in tasks:
            task_field_name, task_func, is_masstask = task_info(task)
            # masstask = background-batch updatable task: assets just have unique value
            # results from tasks, but some tasks have only a few result values. Those
            # can be efficiently (and rate-limit friendly) be set by a
            # FW background-job.

            if task_field_name is None or task_func is None:
                continue  # no field name or task_func configured

            if asset.get("metadata", {}).get(task_field_name) not in [None, ""]:
                continue  # already assigned

            value = await task_func(asset)  # possibly expensive
            if value is None:
                continue  # no value derived

            if is_masstask:
                if isinstance(value, list):
                    for v in value:
                        masstask_value_hrefs[task][v].append(href)
                else:
                    masstask_value_hrefs[task][value].append(href)
            else:
                metadata.update({task_field_name: {"value": value}})

            report_tasks_names.add(task.value)  # for the final report

        try:
            if len(metadata) == 0:
                continue
            await api.update_asset_metadata(href, metadata)
        except HTTPException as err:
            if err.status_code >= 500:
                AppLog.error(f"Update of '{href}' ({metadata}) failed: {err.detail}")
            else:
                raise err

        report_asset_count += 1

    for task, value2href in masstask_value_hrefs.items():
        task_field_name, _, _ = task_info(task)
        if task_field_name is None:
            continue
        await mass_update_asset_metadata(task_field_name, value2href)

    AppLog.info(f"Did run tasks ({report_tasks_names}) for {report_asset_count} assets")
