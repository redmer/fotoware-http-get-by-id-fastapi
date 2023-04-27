from base64 import b32encode
from enum import Enum
from random import choice
from typing import Callable, Iterable
from uuid import uuid4

from .config import (
    FOTOWARE_FIELDNAME_IMGSUBJ,
    FOTOWARE_FIELDNAME_PHASH,
    FOTOWARE_FIELDNAME_SHA256,
    FOTOWARE_FIELDNAME_UUID,
)
from .fotoware import api
from .fotoware.apitypes import Asset


class Task(str, Enum):
    """Tasks when enumerating files"""

    object_detection = "object-detection"
    perceptual_hash = "perceptual-hash"
    sha256 = "sha256"
    uuid = "uuid4"


IDENTIFIER_RE = "^[rjkmtvyz][a-z0-9]+$"


def calc_uuid(asset: Asset) -> tuple[str, str]:
    """
    Generate a globally unique ID. The ID is case-insensitive and always starts with a
    letter, for systems that expect a C-style identifier.
    """

    prefix = choice("rjkmtvyz")  # e.g. LD serializations may expect a C-style localname
    guid = b32encode(uuid4().bytes).decode().replace("=", "").lower()

    return asset["href"], prefix + guid


def calc_sha256(asset: Asset):
    raise NotImplementedError()


def calc_perceptual_hash(asset: Asset):
    raise NotImplementedError()


def calc_object_detection(asset: Asset):
    raise NotImplementedError()


def task_info(
    task: Task,
) -> tuple[str, Callable[[Asset], tuple[str, str]]] | tuple[None, None]:
    """Fieldname used for task"""
    return {
        Task.object_detection: (FOTOWARE_FIELDNAME_IMGSUBJ, calc_object_detection),
        Task.perceptual_hash: (FOTOWARE_FIELDNAME_PHASH, calc_perceptual_hash),
        Task.sha256: (FOTOWARE_FIELDNAME_SHA256, calc_sha256),
        Task.uuid: (FOTOWARE_FIELDNAME_UUID, calc_uuid),
    }.get(task, (None, None))


def exec_update_tasks(*, assets: Iterable[Asset], tasks: Iterable[Task]):
    """
    Execute update tasks for assets. If the file a already has a value for that metadata
    field, it is NOT recalculated.
    """
    combined_updates = dict()

    for asset in assets:
        for task in tasks:
            task_field_name, task_func = task_info(task)

            if task_field_name is None or task_func is None:
                continue  # no field name or task_func configured

            if asset.get("metadata", {}).get(task_field_name) not in [None, ""]:
                continue  # already assigned

            href, value = task_func(asset)  # possibly expensive
            combined_updates[href] = {
                task_field_name: {"value": value},
                **combined_updates.get(href, {}),
            }

    for href, metadata in combined_updates.items():
        api.update_asset_metadata(href, metadata)

    return combined_updates
