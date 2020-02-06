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

"""Exceptions within thoth-s2i library."""


class S2I2ThothException(Exception):
    """An exception raised within s2i2thoth library."""


class ImportImageError(S2I2ThothException):
    """An exception raised on error during importing an image."""


class OCError(S2I2ThothException):
    """An exception raised on error when calling OpenShift client binary."""
