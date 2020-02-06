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
# type: ignore

"""A test-suite for OpenShift object manipulation."""

import os

from thoth.s2i.objs import ImageStream
from thoth.s2i.objs import BuildConfig

from base import S2ITestCase


class TestImageStream(S2ITestCase):
    """A test-suite for OpenShift ImageStream manipulation."""

    def test_load_all(self) -> None:
        """Test loading objects from data dir."""
        loaded = ImageStream.load_all(os.path.join(self.data_dir, "template", "is"))
        assert len(loaded) == 11

    def test_load_all_empty(self) -> None:
        """Test loading objects from data dir - no objects loaded."""
        loaded = ImageStream.load_all(os.path.join(self.data_dir, "template", "bc"))
        assert len(loaded) == 0


class TestBuildConfig(S2ITestCase):
    """A test-suite for OpenShift BuildConfig manipulation."""

    def test_load_all(self) -> None:
        """Test loading objects stream from data dir."""
        loaded = BuildConfig.load_all(os.path.join(self.data_dir, "template", "bc"))
        assert len(loaded) == 4

    def test_load_all_empty(self) -> None:
        """Test loading objects stream from data dir."""
        loaded = BuildConfig.load_all(os.path.join(self.data_dir, "template", "is"))
        assert len(loaded) == 0
