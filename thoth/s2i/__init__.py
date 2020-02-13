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

"""A library and tooling around Thoth's s2i."""

__version__ = "0.0.1"
__author__ = "Fridolin Pokorny <fridolin.pokorny@gmail.com>"

from .exceptions import ImportImageError
from .exceptions import OCError
from .exceptions import S2I2ThothException
from .lib import get_thoth_s2i_images
from .lib import import_thoth_s2i_image
from .lib import oc_check
from .lib import oc_get_bc
