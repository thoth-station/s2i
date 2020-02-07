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

"""A command line interface to thoth-s2i."""

import sys
import click
import logging
import json
import yaml
import tempfile
import re
from typing import Optional
from typing import List

import daiquiri

from thoth.s2i import __version__
from thoth.s2i.lib import get_thoth_s2i_images
from thoth.s2i.lib import import_thoth_s2i_image
from thoth.s2i.lib import oc_get_bc
from thoth.s2i.lib import oc_get_is
from thoth.s2i.lib import get_build_usage_report
from thoth.s2i.lib import change_image_stream
from thoth.s2i.objs import BuildConfig
from thoth.s2i.objs import ImageStream

from termcolor import colored

daiquiri.setup()
_LOGGER = logging.getLogger("thoth.s2i")
_LOGGER.setLevel(logging.INFO)

_DEFAULT_S2I_THOTH = "quay.io/thoth-station/s2i-thoth-ubi8-py36"
_DEFAULT_NAMESPACE = None

_MARK_OK = colored("✔", "green")
_MARK_BAD = colored("✖", "red")
_MARK_ENTRY = "📝"
_MARK_ARROW = "🠒"


@click.group()
@click.option("--debug/--no-debug", default=False, help="Run in a debug mode.")
def cli(debug: bool) -> None:
    """Convert an OpenShift application to use Thoth."""
    if debug:
        _LOGGER.setLevel(logging.DEBUG)


@cli.command()
def version() -> None:
    """Print thoth-s2i version and exit."""
    click.echo(f"thoth-s2i: {__version__}")
    sys.exit(1)


@cli.command("import-image")
@click.argument(
    "image_names", required=False, metavar="THOTH_S2I_IMAGE_NAME:TAG", nargs=-1
)
@click.option(
    "--namespace",
    "-n",
    required=_DEFAULT_NAMESPACE is None,
    default=_DEFAULT_NAMESPACE,
    show_default=True,
    metavar="NAMESPACE",
    help="OpenShift namespace to import Thoth images to.",
)
@click.option(
    "--all-latest",
    "-a",
    "all_images",
    required=False,
    is_flag=True,
    show_default=True,
    help="Import all images instead of prompting.",
)
@click.option(
    "--check-s2i-thoth/--no-check-s2i-thoth",
    "check_s2i_thoth",
    required=False,
    show_default=True,
    is_flag=True,
    default=True,
    help="Check the given image for availability in Thoth's s2i registry.",
)
def import_image(
    image_names: List[str], namespace: str, all_images: bool, check_s2i_thoth: bool
) -> None:
    """Import Thoth image into an OpenShift deployment."""
    if all_images and image_names:
        _LOGGER.error(
            "Cannot import all images if one or multiple image names were explicitly provided"
        )
        sys.exit(1)

    if not (all_images or image_names):
        _LOGGER.error(
            "No image to import provided, state the image name explicitly or use --all for importing all Thoth images"
        )
        sys.exit(1)

    if not (image_names or all_images):
        image_names = [
            click.prompt(
                "Choose Thoth image to be imported", default=_DEFAULT_S2I_THOTH
            )
        ]

    if image_names and check_s2i_thoth:
        thoth_images = get_thoth_s2i_images()
        error = False
        for image_name in image_names:
            image_name, image_tag = image_name.rsplit(":", maxsplit=1)
            if image_name not in thoth_images:
                _LOGGER.error(
                    "Image %r not found in Thoth's images, available are: %s",
                    image_name,
                    thoth_images,
                )
                error = True

        if error:
            sys.exit(1)

    if not image_names:
        image_names = get_thoth_s2i_images()

    for image_name in image_names:
        _LOGGER.info("Importing image %r to namespace %r", image_name, namespace)
        import_thoth_s2i_image(namespace, image_name)


@cli.command("images")
@click.option(
    "--output-format",
    "-o",
    required=False,
    type=click.Choice(["pretty", "json", "yaml", "text"]),
    default="pretty",
    show_default=True,
    help="Output format for displaying Thoth images.",
)
def images(output_format: str) -> None:
    """Show available Thoth images."""
    thoth_images = get_thoth_s2i_images()

    if output_format == "json":
        click.echo(json.dumps({"s2i_thoth": thoth_images}, indent=2))
    elif output_format == "yaml":
        click.echo(yaml.safe_dump({"s2i_thoth": thoth_images}))
    elif output_format == "pretty":
        for image in thoth_images:
            click.echo(f"{_MARK_OK} {image}")
    elif output_format == "text":
        click.echo("\n".join(thoth_images))
    else:
        raise NotImplementedError(f"Unknown output format {output_format}")


@cli.command("report")
@click.option(
    "--namespace",
    "-n",
    required=_DEFAULT_NAMESPACE is None,
    default=_DEFAULT_NAMESPACE,
    show_default=True,
    metavar="NAMESPACE",
    help="OpenShift namespace to import Thoth images to.",
)
@click.option(
    "--output-format",
    "-o",
    required=False,
    type=click.Choice(["pretty", "json", "yaml"]),
    default="pretty",
    show_default=True,
    help="Output format for displaying Thoth compatibility.",
)
@click.option(
    "--selector",
    "-l",
    type=str,
    required=False,
    default=None,
    metavar="LABEL=SELECTOR",
    show_default=True,
    help="Label selector that should be applied to filter out BuildConfigs that should be migrated to Thoth's s2i.",
)
def report(namespace: str, selector: str, output_format: str) -> None:
    """Check the given namespace for s2i Thoth compatibility."""
    with tempfile.NamedTemporaryFile() as temp_file:
        oc_get_bc(namespace=namespace, selector=selector, path=temp_file.name)
        build_configs = BuildConfig.load_all(temp_file.name, skip_errors=True)

        if not build_configs:
            _LOGGER.warning("No BuildConfig found in namespace %r", namespace)
            sys.exit(1)

        oc_get_is(namespace=namespace, selector=selector, path=temp_file.name)
        image_streams = ImageStream.load_all(temp_file.name, skip_errors=True)

    report_dict = get_build_usage_report(image_streams, build_configs)
    if output_format == "json":
        click.echo(json.dumps(report_dict, indent=2))
    elif output_format == "yaml":
        click.echo(yaml.safe_dump(report_dict))
    elif output_format == "pretty":
        for build_config_name, build_config_value in report_dict.items():
            click.echo(f"{_MARK_ENTRY} {build_config_name}")
            for key, value in build_config_value.items():
                if value is None:
                    continue
                click.echo(f"\t\t{_MARK_ARROW} {key}: {value!r}")
    else:
        raise NotImplementedError(f"Unknown report output format {output_format!r}")


@cli.command("patch")
@click.argument("path", metavar="PATH")
@click.option(
    "--s2i-thoth",
    type=str,
    required=False,
    default=_DEFAULT_S2I_THOTH,
    show_default=True,
    prompt="Use s2i Thoth image",
    metavar="S2I_THOTH_IMAGE_NAME",
    help="Thoth's s2i image to be used.",
)
@click.option(
    "--check-s2i-thoth/--no-check-s2i-thoth",
    "check_s2i_thoth",
    required=False,
    show_default=True,
    is_flag=True,
    default=True,
    help="Check the given image for availability in Thoth's s2i registry.",
)
@click.option(
    "--tag",
    "-t",
    "tag",
    required=True,
    show_default=True,
    default="latest",
    help="Image stream tag to be used.",
)
@click.option(
    "--insert-env-vars/--no-insert-env-vars",
    "-e",
    "insert_env_vars",
    required=False,
    show_default=True,
    is_flag=True,
    default=False,
    help="Insert Thoth and Thamos specific environment variables into adjusted BuildConfigs.",
)
@click.option(
    "--from-image-stream-tag",
    "-f",
    required=False,
    show_default=True,
    type=str,
    default=".*python.*",
    help="A regular expression describing image stream tag that should be "
         "substituted with Thoth s2i image (a full match is applied).",
)
def patch(
    path: str,
    s2i_thoth: str,
    tag: str,
    from_image_stream_tag: str,
    check_s2i_thoth: bool = True,
    insert_env_vars: bool = True,
) -> None:
    """Patch local templates to use Thoth.

    Adjust templates stored on the filesystem to use Thoth's s2i.
    """
    if check_s2i_thoth:
        thoth_images = get_thoth_s2i_images()
        if s2i_thoth not in thoth_images:
            _LOGGER.error(
                "Image %r not found in Thoth's images, available are: %r",
                s2i_thoth,
                thoth_images,
            )
            sys.exit(1)

    _LOGGER.info("Patching files in %r to use %r", path, s2i_thoth)

    build_configs = BuildConfig.load_all(path, skip_errors=True)
    if not build_configs:
        _LOGGER.error("No BuildConfig found in %r", path)
        sys.exit(1)

    from_image_stream_tag_re = re.compile(from_image_stream_tag)

    image_stream_name = s2i_thoth.rsplit("/", maxsplit=1)[-1]
    changed_build_configs = change_image_stream(
        build_configs,
        f"{image_stream_name}:{tag}",
        lambda bc: bool(from_image_stream_tag_re.fullmatch(bc.get_image_stream_tag())),
    )

    if insert_env_vars:
        _LOGGER.warning(
            "Formatting of templates might change when inserting Thoth and Thamos specific environment variables"
        )
        for build_config in changed_build_configs.values():
            build_config.insert_thoth_env_vars()
            build_config.save2file()

    _LOGGER.info(
        "Patching done \\o/, total BuildConfigs patched: %d", len(changed_build_configs)
    )

    if len(changed_build_configs) > 0:
        _LOGGER.warning(
            "Don't forget to create an image stream with image %r and tag %r",
            s2i_thoth,
            tag,
        )


@cli.command("migrate")
@click.option(
    "--namespace",
    "-n",
    type=str,
    required=_DEFAULT_NAMESPACE is None,
    default=_DEFAULT_NAMESPACE,
    show_default=True,
    metavar="NAMESPACE",
    help="OpenShift namespace in which BuilConfigs should be adjusted.",
)
@click.option(
    "--s2i-thoth",
    type=str,
    required=False,
    default=None,
    show_default=True,
    metavar="S2I_THOTH_IMAGE_NAME",
    help="Thoth's s2i image to be used.",
)
@click.option(
    "--selector",
    "-l",
    type=str,
    required=False,
    default=None,
    metavar="LABEL=SELECTOR",
    show_default=True,
    help="Label selector that should be applied to filter out BuildConfigs that should be migrated to Thoth's s2i.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    required=False,
    default=False,
    show_default=True,
    help="Do not propagate changes back to the cluster, rather print them to standard output for a review.",
)
@click.option(
    "--trigger-build",
    is_flag=True,
    required=False,
    default=False,
    show_default=True,
    help="Trigger build if BuildConfig has no build trigger on config change.",
)
@click.option(
    "--check-s2i-thoth/--no-check-s2i-thoth",
    "check_s2i_thoth",
    required=False,
    show_default=True,
    is_flag=True,
    default=True,
    help="Check the given image for availability in Thoth's s2i registry.",
)
@click.option(
    "--tag",
    "-t",
    "tag",
    required=True,
    show_default=True,
    default="latest",
    help="Image stream tag to be used.",
)
@click.option(
    "--import-image/--no-import-image",
    "do_import_image",
    required=False,
    show_default=True,
    is_flag=True,
    default=True,
    help="Image stream tag to be used.",
)
@click.option(
    "--insert-env-vars/--no-insert-env-vars",
    "-e",
    "insert_env_vars",
    required=False,
    show_default=True,
    is_flag=True,
    default=False,
    help="Insert Thoth and Thamos specific environment variables into adjusted BuildConfigs.",
)
@click.option(
    "--from-image-stream-tag",
    "-f",
    required=False,
    show_default=True,
    type=str,
    default=".*python.*",
    help="A regular expression describing image stream tag that should be "
         "substituted with Thoth s2i image (a full match is applied).",
)
def migrate(
    namespace: str,
    s2i_thoth: str,
    tag: str,
    from_image_stream_tag: str,
    selector: Optional[str] = None,
    do_import_image: bool = True,
    dry_run: bool = False,
    trigger_build: bool = False,
    check_s2i_thoth: bool = True,
    insert_env_vars: bool = True,
) -> None:
    """Migrate an existing OpenShift application to use Thoth.

    Adjust an existing OpenShift deployment to use Thoth by adjusting OpenShift's BuildConfigs.
    """
    s2i_thoth = s2i_thoth or click.prompt(
        "Choose Thoth image to be imported", default=_DEFAULT_S2I_THOTH
    )

    if check_s2i_thoth:
        thoth_images = get_thoth_s2i_images()
        if s2i_thoth not in thoth_images:
            _LOGGER.error(
                "Image %r not found in Thoth's images, available are: %r",
                s2i_thoth,
                thoth_images,
            )
            sys.exit(1)

    from_image_stream_tag_re = re.compile(from_image_stream_tag)

    image_stream_name = s2i_thoth.rsplit("/", maxsplit=1)[-1]
    with tempfile.NamedTemporaryFile() as temp_file:
        oc_get_bc(namespace=namespace, selector=selector, path=temp_file.name)
        build_configs = BuildConfig.load_all(path=temp_file.name, skip_errors=True)

        changed_build_configs = change_image_stream(
            build_configs,
            f"{image_stream_name}:{tag}",
            lambda bc: bool(from_image_stream_tag_re.fullmatch(bc.get_image_stream_tag())),
        )

        if insert_env_vars:
            for build_config in changed_build_configs.values():
                build_config.insert_thoth_env_vars()

        if dry_run:
            if trigger_build:
                _LOGGER.warning("Dry run will not trigger build")

            if do_import_image:
                _LOGGER.warning("Dry run will not import image into OpenShift's registry")

            for build_config in changed_build_configs.values():
                click.echo("--")
                click.echo(build_config.to_yaml())
            return

        for build_config in changed_build_configs.values():
            build_config.apply()

        if trigger_build:
            for build_config in changed_build_configs.values():
                build_config.trigger_build(only_if_no_config_change=True)

        if len(changed_build_configs) > 0 and do_import_image:
            import_thoth_s2i_image(namespace, s2i_thoth)


__name__ == "__main__" and cli()
