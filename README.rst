thoth-s2i
---------

Tooling and a library for Thoth's Python Source-To-Image (s2i) applications.

This application can assist you to port an existing application to Thoth or
expose information about build configs used within the cluster.

How to migrate an existing Python s2i application to use Thoth
==============================================================

If you have a Python application that uses OpenShift s2i and you would like
to benefit from Thoth's recommendations, you can simply port all your OpenShift
templates by executing the following command after installing
`thoth-s2i <https://pypi.org/project/thoth-s2i>`_:

.. code-block:: console

  thoth-s2i patch --s2i-thoth quay.io/thoth-station/s2i-thoth-ubi8-py36 --insert-env-var path/to/openshift/templates

The command above will look for all the templates present in the supplied
directory and will load build configs used. If a build config
uses an s2i image stream, it will simply replace it with Thoth's s2i.

See ``--help`` for more available options and configuration options.

If the application is already deployed, you can check what image streams are
used by build configs in the namespace where your application is built:

.. code-block:: console

  thoth-s2i report --namespace <my-namespace>

The command above will give you a complete report of build configs with
information about image streams, image stream tags and container images
imported that are used by build configs.

If you wish to migrate the application to use Thoth's recommendation engine,
you can issue the following migration script:

.. code-block:: console

  thoth-s2i migrate --namespace <my-namespace> -l app=myapp --s2i-thoth quay.io/thoth-station/s2i-thoth-ubi8-py36 --tag latest --insert-env-vars --from-image-stream-tag 'registry.redhat.io/ubi8/python-36:*' --dry-run

The command above will perform "dry run" operation - it will go through
available build configs matching the given label selector ``app=myapp`` and
will substitute any use of ``registry.redhat.io/ubi8/python-36`` with the
latest Thoth's equivalent UBI 8 image. Besides that, it will inject environment
variables needed for Thoth to properly build and configure OpenShift's build
process.

Once you review the changes done (they are printed to stdout/stderr), you can
actually perform this operation in the cluster:

.. code-block:: console

  thoth-s2i migrate --namespace <my-namespace> -l app=myapp --s2i-thoth quay.io/thoth-station/s2i-thoth-ubi8-py36 --tag latest --insert-env-vars --from-image-stream-tag 'registry.redhat.io/ubi8/python-36:*' --trigger-build --import-image

The command above will apply changes to the cluster. Moreover, if changes done
to the build config do not trigger a new build (no config change build
trigger), ``thoth-s2i`` will trigger OpenShift builds for adjusted build
configs. The used Thoth s2i image will be imported to OpenShift's registry.

See ``thoth-s2i migrate --help`` for more information.

List available Thoth s2i images
===============================

You can list available Thoth s2i container images provided by Thoth:

.. code-block:: console

  thoth-s2i images

See ``--help`` for more info.


Get information about BuildConfig configuration in the cluster
==============================================================

To get information about BuildConfig configuration and image stream
configuration within the namespace, run the following command:

.. code-block:: console

  $ thoth-s2i report --namespace <my-namespace>
  📝 init-job
          🠒 strategy: 'Source'
          🠒 image_stream: 's2i-thoth-ubi8-py36'
          🠒 image_stream_tag: 'latest'
          🠒 is_s2i: True
          🠒 is_s2i_thoth: True
          🠒 s2i_image_name: 'quay.io/thoth-station/s2i-thoth-ubi8-py36'
          🠒 s2i_image_tag: 'v0.8.0'
  📝 inspect-hwinfo
          🠒 strategy: 'Source'
          🠒 image_stream: 's2i-thoth-ubi8-py36'
          🠒 image_stream_tag: 'latest'
          🠒 is_s2i: True
          🠒 is_s2i_thoth: True
          🠒 s2i_image_name: 'quay.io/thoth-station/s2i-thoth-ubi8-py36'
          🠒 s2i_image_tag: 'v0.8.0'
  📝 inspection-test-9ae7a488
          🠒 strategy: 'Docker'
          🠒 is_s2i: False
  📝 inspection-test-ce614dfe
          🠒 strategy: 'Docker'
        🠒 is_s2i: False

See ``--help`` for more info.


Import Thoth s2i container image
================================

To import Thoth's s2i compliant image to the cluster, issue the following
command:

.. code-block:: console

  thoth-s2i import-image --namespace <my-namespace>

See ``--help`` for more info.


Migrate an existing application to use Thoth's recommendation engine
====================================================================

This tool can automatically migrate an existing application that uses Python
s2i (Source-To-Image) to Thoth s2i. This way the application will benefit from
Thoth's recommendations on software stack.  To do so, run the following
command:

.. code-block:: console

  thoth-s2i migrate --namespace <my-namespace> --import-image --s2i-thoth quay.io/thoth-station/s2i-thoth-ubi8-py36 --tag latest --trigger-build -l app=myapp

See ``--help`` for more info.


Patch OpenShift templates for Thoth
===================================

To automatically patch local OpenShift templates so that they use Thoth's s2i,
run the following command:

.. code-block:: console

  thoth-s2i patch openshift/ --s2i-thoth quay.io/thoth-station/s2i-thoth-ubi8-py36 --insert-env-variables

See ``--help`` for more info.


Installation
============

To install thoth-s2i library issue one of the following commands:

.. code-block:: console

  # Using pip:
  pip3 install thoth-s2i

  # or using Pipenv:
  pipenv install thoth-s2i

  # or using directly git branch:
  pip3 install git+https://github.com/thoth-station/thoth-s2i@master

See hosted project on `PyPI <https://pypi.org/project/thoth-s2i>`_ and sources
on `GitHub <https://pypi.org/project/thoth-s2i>`_.


Running from Git
================

To run this utility from Git master branch, run the following commands:

.. code-block:: console

  git clone https://github.com/thoth-station/thoth-s2i
  cd thoth-s2i
  pipenv install --dev
  PYTHONPATH=. pipenv run python3 ./thoth-s2i --help
