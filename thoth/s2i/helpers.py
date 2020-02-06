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

"""Helpers used in thoth-s2i library."""

from typing import Any
from typing import List
import logging
import subprocess

_LOGGER = logging.getLogger(__name__)


def _subprocess_run(args: List[str], **kwargs: Any) -> Any:
    """Run the given command as a subprocess - a thin wrapper."""
    _LOGGER.debug("Executing command %r with subprocess flags %r", args, kwargs)
    return subprocess.run(args, universal_newlines=True, **kwargs)
