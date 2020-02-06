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

"""Routines needed for parsing and representing OpenShift's BuildConfig."""

import os
import logging
import yaml
import subprocess
from typing import Any
from typing import Dict
from typing import Mapping
from typing import Generator
from typing import List
from typing import Optional
from typing import Union

import attr

from .exceptions import S2I2ThothException
from .exceptions import OCError
from .helpers import _subprocess_run

_LOGGER = logging.getLogger(__name__)

# A YAML safe loader that does not parse datetime.
_NoDatesSafeLoader = yaml.SafeLoader
_NoDatesSafeLoader.yaml_implicit_resolvers = {
    k: [r for r in v if r[0] != "tag:yaml.org,2002:timestamp"]
    for k, v in _NoDatesSafeLoader.yaml_implicit_resolvers.items()
}


@attr.s(slots=True)
class OpenShiftObject:
    """A wrapper for BuildConfig representation."""

    file_path = attr.ib(type=str)
    raw = attr.ib(type=Dict[str, Any])

    @classmethod
    def load_file(cls, path: str, skip_errors: bool = True) -> Dict[str, Any]:
        """Load the given OpenShift object from a file."""
        raise NotImplementedError

    @classmethod
    def load_all(
        cls, path: str, skip_errors: bool = True
    ) -> Mapping[str, "OpenShiftObject"]:
        """Load the given OpenShift object from a file or files present in a directory, recursively."""
        if os.path.isfile(path):
            return cls.load_file(path)

        if not os.path.isdir(path):
            raise S2I2ThothException(f"Path {path!r} is not a file or directory")

        result: Dict[str, "OpenShiftObject"] = {}
        for root, _, files in os.walk(path, followlinks=True):
            for file in files:
                instances = cls.load_file(
                    os.path.join(root, file), skip_errors=skip_errors
                )
                for instance in instances.values():
                    if instance.name in result:
                        if not skip_errors:
                            raise S2I2ThothException(
                                f"Multiple definitions of {instance.name!r} found"
                            )

                        _LOGGER.warning(
                            f"Multiple definitions of %r found, skipping...",
                            instance.name,
                        )
                        continue

                    result[instance.name] = instance

        return result

    def labels(self) -> Dict[str, str]:
        """Get labels applied to build config."""
        result: Dict[str, str] = self.raw.get("metadata", {}).get("labels", {})
        return result

    @property
    def name(self) -> str:
        """Get name of this object."""
        result: str = self.raw["metadata"]["name"]
        return result

    @staticmethod
    def _load_file_content(
        path: str, skip_errors: bool = True
    ) -> Optional[Union[Dict[str, Any], List[Dict[str, Any]]]]:
        """Load content of the given file."""
        _LOGGER.info("Loading file content from %r", path)

        content = None
        try:
            with open(path, "r") as input_file:
                content = yaml.load(
                    input_file, Loader=_NoDatesSafeLoader
                )  # use BaseLoader not to parse datetime.
        except Exception as exc:
            if not skip_errors:
                raise

            _LOGGER.warning(
                "Failed to load and/or parse file %r, the file will be skipped: %s:",
                path,
                str(exc),
            )

        if content is None:
            if not skip_errors:
                raise S2I2ThothException(f"File {path!r} has value null")

            _LOGGER.warning("File %r holds null, skipping...", path)
            return None

        if not isinstance(content, (list, dict)):
            if not skip_errors:
                raise S2I2ThothException(
                    f"File {path!r} holds a string, does not look like OpenShift YAML/JSON template"
                )

            _LOGGER.warning(
                "File %r holds a string, does not look like OpenShift YAML/JSON template",
                path,
            )
            return None

        return content

    @classmethod
    def _iter_objects(
        cls, content: Union[Dict[str, Any], List[Dict[str, Any]]]
    ) -> Generator[Dict[str, Any], None, None]:
        """Iterate over objects found in the template."""
        if isinstance(content, list):
            for item in content:
                if isinstance(item, (dict, list)):
                    yield from cls._iter_objects(item)
            return

        if content.get("kind", "").strip().lower() == "template":
            for obj in content.get("objects", []):
                yield from cls._iter_objects(obj)
            return

        if content.get("kind", "").strip().lower() == "list":
            for obj in content.get("items", []):
                yield from cls._iter_objects(obj)
            return

        yield content

    @classmethod
    def _instantiate_objects(
        cls,
        path: str,
        content: Union[Dict[str, Any], List[Dict[str, Any]]],
        class_: type,
        kind: str,
        skip_errors: bool = True,
    ) -> Mapping[str, "OpenShiftObject"]:
        """Instantiate objects from from loaded content."""
        result: Dict[str, "OpenShiftObject"] = {}
        for obj in cls._iter_objects(content):
            if obj.get("kind", "").lower().strip() != kind:
                continue

            if not obj.get("metadata", {}).get("name"):
                if not skip_errors:
                    raise S2I2ThothException(
                        f"No name provided in object found in {path!r}: %s", content
                    )

                _LOGGER.error(
                    "No name provided in object found in %r: %s, skipping...",
                    path,
                    content,
                )
                continue

            if obj["metadata"]["name"] in result:
                if not skip_errors:
                    raise S2I2ThothException(
                        f"Duplicate name {path!r}, name already seen: {content}, seen "
                        f"in {result[obj['metadata']['name']]}"
                    )

                _LOGGER.error(
                    "Duplicate name %r, name already seen: %s, seen in %s, skipping...",
                    path,
                    content,
                    result[obj["metadata"]["name"]],
                )
                continue

            _LOGGER.info(
                "Found %r of kind %r in %r", obj["metadata"]["name"], kind, path
            )
            result[obj["metadata"]["name"]] = class_(file_path=path, raw=obj)

        return result

    def to_yaml(self) -> str:
        """Convert the current object to its YAML representation."""
        result: str = yaml.safe_dump(self.raw)
        return result

    def save2file(self) -> None:
        """Save changes made to the file."""
        # This will work if the original file was is/bc. This will not work for templates
        # or list type - we need to find the given object and replace it correctly.
        with open(self.file_path, "w") as output_file:
            yaml.safe_dump(self.raw, output_file)

    def apply(self) -> None:
        """Apply changes to the cluster."""
        _LOGGER.info("Applying changes made to %r to the cluster", self.name)
        subcommand = _subprocess_run(
            ["oc", "apply", "-f", "-"],
            input=self.to_yaml(),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        if subcommand.returncode != 0:
            raise OCError(
                f"Failed to apply {self.name!r} of kind {self.__class__.__name__!r}: {str(subcommand.stderr)}"
            )


@attr.s(slots=True)
class ImageStream(OpenShiftObject):
    """A wrapper for ImageStream representation."""

    @classmethod
    def load_file(cls, path: str, skip_errors: bool = True) -> Dict[str, "ImageStream"]:
        """Load ImageStream from a file."""
        content = cls._load_file_content(path, skip_errors=skip_errors)
        if content is None:
            return {}

        result: Dict[str, ImageStream] = cls._instantiate_objects(  # type: ignore
            path, content, cls, "imagestream", skip_errors=skip_errors
        )
        return result


@attr.s(slots=True)
class BuildConfig(OpenShiftObject):
    """A wrapper for BuildConfig representation."""

    _THOTH_ENV_VARS_DEFAULTS = {
        "ENABLE_PIPENV": "1",
        "UPGRADE_PIP_TO_LATEST": "",
        "THOTH_DRY_RUN": "0",
        "THOTH_ADVISE": "1",
        "THOTH_ASSEMBLE_DEBUG": "1",
        "THOTH_FROM_MASTER": "0",
        "THOTH_ERROR_FALLBACK": "1",
        "THAMOS_VERBOSE": "0",
        "THAMOS_FORCE": "0",
        "THAMOS_DEBUG": "0",
        "THAMOS_CONFIG_TEMPLATE": ".thoth.yaml",
        "THAMOS_CONFIG_EXPAND_ENV": "0",
        "THAMOS_NO_PROGRESSBAR": "1",
        "THAMOS_NO_INTERACTIVE": "1",
    }

    @classmethod
    def load_file(cls, path: str, skip_errors: bool = True) -> Dict[str, "BuildConfig"]:
        """Load BuildConfig from a file."""
        content = cls._load_file_content(path, skip_errors=skip_errors)
        if content is None:
            return {}

        result: Dict[str, BuildConfig] = cls._instantiate_objects(  # type: ignore
            path, content, cls, "buildconfig", skip_errors=skip_errors
        )
        return result

    def get_source_strategy(self) -> Dict[str, Any]:
        """Get source strategy entry out of the image stream."""
        result: Dict[str, Any] = self.raw.get("spec", {}).get("strategy", {}).get("sourceStrategy", {})
        return result

    def get_image_stream_name(self) -> str:
        """Get name of image stream without tag."""
        is_name: str = self.get_source_strategy().get("from", {}).get("name")
        is_name, _ = is_name.rsplit(":", maxsplit=1)
        return is_name

    def get_image_stream_tag_name(self) -> str:
        """Get name of image stream tag."""
        is_name: str = self.get_source_strategy().get("from", {}).get("name")
        _, is_tag = is_name.rsplit(":", maxsplit=1)
        return is_tag

    def get_image_stream_tag(self) -> str:
        """Get name of image stream tag."""
        result: str = self.get_source_strategy().get("from", {}).get("name")
        return result

    def set_image_stream_tag(self, image_stream_tag: str) -> None:
        """Setter for image stream tag."""
        self.get_source_strategy()["from"]["name"] = image_stream_tag

    def replace_in_file(self, old: str, new: str) -> None:
        """Replace the given string in the file."""
        # Note, changes are not reflected to this class - changes are in-file only.
        with open(self.file_path, "r") as f:
            content = f.read()

        # Do replace to keep formatting.
        content = content.replace(old, new)

        with open(self.file_path, "w") as f:
            f.write(content)

    def _do_trigger_build(self) -> None:
        """Trigger the build."""
        _LOGGER.info("Triggering build for %r in namespace %r", self.name, self.raw["metadata"]["namespace"])
        subcommand = _subprocess_run(
            ["oc", "start-build", "-n", self.raw["metadata"]["namespace"], self.name],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        if subcommand.returncode != 0:
            raise OCError(
                f"Failed to start build {self.name!r} in "
                f"namespace {self.raw['metadata']['namespace']!r}: {str(subcommand.stderr)}"
            )

    def trigger_build(self, only_if_no_config_change: bool = False) -> bool:
        """Trigger the build."""
        if only_if_no_config_change:
            for trigger in self.raw.get("triggers", []):
                if trigger.get("type") is not None and trigger["type"].lower() == "configchange":
                    return False
            else:
                self._do_trigger_build()
                return True

        self._do_trigger_build()
        return True

    def insert_thoth_env_vars(self) -> None:
        """Insert Thoth and Thamos specific environment variables."""
        _LOGGER.info("Inserting Thoth and Thamos specific environment variables to %r", self.name)
        source_strategy = self.get_source_strategy()
        if source_strategy is None:
            raise S2I2ThothException(
                "No source strategy defined for {self.name!r}, cannot inject environment variables"
            )

        if "env" not in source_strategy:
            source_strategy["env"] = []

        for thoth_env_name, thoth_env_value in self._THOTH_ENV_VARS_DEFAULTS.items():
            for env_entry in source_strategy["env"]:
                if env_entry["name"] == thoth_env_name:
                    break
            else:
                source_strategy["env"].append({
                    "name": thoth_env_name,
                    "value": thoth_env_value,
                })
