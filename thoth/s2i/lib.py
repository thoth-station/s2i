#!/usr/bin/env python3
# thoth-s2i
# Copyright(C) 2020 Fridolin Pokorny
#
# This program is free software: you can redistribute it and / or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

"""Convert OpenShift Python s2i buildconfigs to use Thoth's s2i."""

from pathlib import Path
from typing import Any
from typing import Callable
from typing import Dict
from typing import List
from typing import Optional
import functools
import logging
import os
import re
import requests
import subprocess
import sys

from .exceptions import ImportImageError
from .exceptions import OCError
from .exceptions import S2I2ThothException
from .objs import ImageStream
from .objs import BuildConfig
from .helpers import _subprocess_run

_LOGGER = logging.getLogger(__name__)

_OC_CHECKED = False
_THOTH_S2I_README = os.getenv(
    "THOTH_S2I_README",
    "https://raw.githubusercontent.com/thoth-station/s2i-thoth/master/README.rst",
)
_RE_S2I = re.compile(r"quay.io/thoth-station/s2i-thoth-\S*")


def oc_check() -> None:
    """Check if oc (OpenShift client binary) is available and if the user is logged in into the cluster."""
    try:
        oc_version = _subprocess_run(["oc", "version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except FileNotFoundError as exc:
        raise OCError(
            f"Failed to obtain information about OpenShift client - make sure oc is "
            f"installed and available on PATH: {str(exc)}"
        ) from exc

    if oc_version.returncode != 0:
        raise OCError(
            f"Failed to obtain information about OpenShift client: {oc_version.stderr}"
        )


@functools.wraps(oc_check)
def oc_check_once(func: Callable[..., Any]) -> Callable[..., Any]:
    """Check oc binary for required functions once this library is run."""
    def inner(*args: Any, **kwargs: Any) -> Any:
        global _OC_CHECKED

        if not _OC_CHECKED:
            oc_check()
            _OC_CHECKED = True

        return func(*args, **kwargs)

    return inner


def _do_import_image(namespace: str, image: str, stdout: Any = None) -> None:
    """Import an image to namespace."""
    parts = image.rsplit("/", maxsplit=1)
    parts = parts[-1].rsplit(":", maxsplit=1)
    imagestream_name = parts[0]

    subcommand = _subprocess_run(
        [
            "oc",
            "import-image",
            "--namespace",
            namespace,
            imagestream_name,
            "--from",
            image,
            "--confirm",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if subcommand.returncode != 0:
        raise ImportImageError(f"Failed to import image {image}: {subcommand.stderr}")

    if stdout is not None:
        print(subcommand.stdout, file=stdout)


@oc_check_once
def import_thoth_s2i_image(
    namespace: str, image: Optional[str] = None, stdout: Any = sys.stdout
) -> None:
    """Import Thoth's s2i image into the given namespace."""
    if image is not None:
        _do_import_image(namespace, image, stdout=stdout)
        return

    for image in get_thoth_s2i_images():
        _do_import_image(namespace, image, stdout=stdout)


def get_thoth_s2i_images() -> List[str]:
    """Get a listing of Thoth's s2i images available."""
    response = requests.get(_THOTH_S2I_README)
    try:
        response.raise_for_status()
    except Exception as exc:
        raise S2I2ThothException(
            "Failed to obtain Thoth's s2i images from GitHub"
        ) from exc

    return sorted(set(_RE_S2I.findall(response.text)), reverse=True)


@oc_check_once
def oc_get_bc(
    namespace: str, selector: Optional[str] = None, path: str = "buildconfigs.yaml"
) -> None:
    """Get buildconfigs installed in the given namespace to the given file described by path."""
    if not os.path.isfile(path):
        try:
            Path(path).touch()
        except Exception as exc:
            raise S2I2ThothException(
                f"Cannot create file {path} for storing buildconfigs"
            ) from exc

    cmd = ["oc", "get", "bc", "--namespace", namespace, "-o", "yaml"]

    if selector:
        cmd.extend(("-l", selector))

    with open(path, "w") as output_file:
        subcommand = _subprocess_run(
            cmd, stdout=output_file.fileno(), stderr=subprocess.PIPE
        )

    if subcommand.returncode != 0:
        raise OCError(
            f"Failed to obtain buildconfigs from namespace {namespace}: {subcommand.stderr}"
        )


@oc_check_once
def oc_get_is(
    namespace: str, selector: Optional[str] = None, path: str = "imagestreams.yaml"
) -> None:
    """Get ImageStreams installed in the given namespace to the given file described by path."""
    if not os.path.isfile(path):
        try:
            Path(path).touch()
        except Exception as exc:
            raise S2I2ThothException(
                f"Cannot create file {path} for storing imagestreams"
            ) from exc

    cmd = ["oc", "get", "is", "--namespace", namespace, "-o", "yaml"]

    if selector:
        cmd.extend(("-l", selector))

    with open(path, "w") as output_file:
        subcommand = _subprocess_run(
            cmd, stdout=output_file.fileno(), stderr=subprocess.PIPE
        )

    if subcommand.returncode != 0:
        raise OCError(
            f"Failed to obtain imagestreams from namespace {namespace}: {subcommand.stderr}"
        )


def get_build_usage_report(
    image_streams: Dict[str, ImageStream], build_configs: Dict[str, BuildConfig]
) -> Dict[str, Any]:
    """Get report usage of build configs."""
    report_dict = {}
    for build_config in build_configs.values():
        strategy_type = build_config.raw.get("spec", {}).get("strategy", {}).get("type")

        report_dict[build_config.name] = {
            "strategy": strategy_type,
            "image_stream": None,
            "image_stream_tag": None,
            "is_s2i": strategy_type.lower() == "source",
            "is_s2i_thoth": None,
            "s2i_image_tag_imported": None,
            "s2i_image_name": None,
            "s2i_image_tag": None,
        }

        if not report_dict[build_config.name]["is_s2i"]:
            _LOGGER.debug(
                "Skipping s2i detection for %r as build strategy is not s2i",
                build_config.name,
            )
            continue

        source_strategy = build_config.get_source_strategy()
        kind = source_strategy.get("from", {}).get("kind")
        if not kind:
            _LOGGER.error(
                "Cannot determine kind for source strategy for %r", build_config.name
            )
            continue

        if kind != "ImageStreamTag":
            continue

        is_name = source_strategy.get("from", {}).get("name")
        is_name, is_tag = is_name.rsplit(":", maxsplit=1)

        report_dict[build_config.name]["image_stream"] = is_name
        report_dict[build_config.name]["image_stream_tag"] = is_tag

        image_stream = image_streams.get(is_name)
        if not image_stream:
            _LOGGER.error(
                "Cannot find image stream %r used by build config %r",
                is_name,
                build_config.name,
            )
            continue

        for tag_record in image_stream.raw.get("spec", {}).get("tags", []):
            if tag_record.get("name") == is_tag:
                image_record = tag_record.get("from", {}).get("name")
                if image_record:
                    image, tag = image_record.rsplit(":", maxsplit=1)
                    report_dict[build_config.name]["s2i_image_tag"] = tag
                    report_dict[build_config.name]["s2i_image_name"] = image
                else:
                    _LOGGER.error(
                        "Cannot parse image record for image stream %r tag %r",
                        is_name,
                        is_tag,
                    )
                break
        else:
            _LOGGER.error(
                "Cannot find tag %r in image stream %r used by %r",
                is_tag,
                is_name,
                build_config.name,
            )
            continue

    s2i_thoth = get_thoth_s2i_images()
    for entry in report_dict.values():
        if not entry["is_s2i"]:
            continue

        if entry["s2i_image_name"] in s2i_thoth:
            entry["is_s2i_thoth"] = True

    return report_dict


def change_image_stream(
    build_configs: Dict[str, BuildConfig], new: str, cond_func: Callable[[BuildConfig], bool],
) -> Dict[str, BuildConfig]:
    """Change image stream in BuildConfigs based on condition."""
    result = {}
    for build_config in build_configs.values():
        if not cond_func(build_config):
            # XXX: do we want something more reliable?!
            continue

        _LOGGER.info(
            "Patching BuildConfig %r, replacing %r with %r",
            build_config.name,
            build_config.get_image_stream_tag(),
            new,
        )
        build_config.replace_in_file(build_config.get_image_stream_tag(), new)
        build_config.set_image_stream_tag(new)
        result[build_config.name] = build_config

    return result
