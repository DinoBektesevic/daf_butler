# This file is part of daf_butler.
#
# Developed for the LSST Data Management System.
# This product includes software developed by the LSST Project
# (http://www.lsst.org).
# See the COPYRIGHT file at the top-level directory of this distribution
# for details of code ownership.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""
Configuration classes specific to the Butler
"""

__all__ = ("ButlerConfig",)

import os.path
import boto3


from . import utils
from .config import Config
from .datastore import DatastoreConfig
from .schema import SchemaConfig
from .registry import RegistryConfig
from .storageClass import StorageClassConfig
from .dimensions import DimensionConfig
from .composites import CompositesConfig

CONFIG_COMPONENT_CLASSES = (SchemaConfig, RegistryConfig, StorageClassConfig,
                            DatastoreConfig, CompositesConfig, DimensionConfig)


class ButlerConfig(Config):
    """Contains the configuration for a `Butler`

    The configuration is read and merged with default configurations for
    the particular classes. The defaults are read according to the rules
    outlined in `ConfigSubset`. Each component of the configuration associated
    with a configuration class reads its own defaults.

    Parameters
    ----------
    other : `str`, `Config`, optional
        Path to butler configuration YAML file or a directory containing a
        "butler.yaml" file. If `None` the butler will
        be configured based entirely on defaults read from the environment.
        No defaults will be read if a `ButlerConfig` is supplied directly.
    """

    def __init__(self, other=None):

        # If this is already a ButlerConfig we assume that defaults
        # have already been loaded.
        if other is not None and isinstance(other, ButlerConfig):
            super().__init__(other)
            return


        scheme, root, relpath = utils.parsePath2Uri(other)
        if scheme == 'file://':
            if isinstance(other, str) and os.path.isdir(other):
                other = os.path.join(other, "butler.yaml")
        elif scheme == 's3://' and utils.bucketExists(other):
            # authorizing somewhere clever would be a good thing too
            session = boto3.Session(profile_name='default')

            # download stuff where needed the short way for now,
            # but better to have specific functionality somewhere.
            # tempfiles, TransferConfig etc etc...
            other = "/home/dinob/uni/lsstspark/simple_repo/s3_repo/butler.yaml"
            s3client = boto3.client('s3')
            s3client.download_file(root, relpath, other)

        # Create an empty config for us to populate
        super().__init__()

        # Read the supplied config so that we can work out which other
        # defaults to use.
        butlerConfig = Config(other)

        # A Butler config contains defaults defined by each of the component
        # configuration classes. We ask each of them to apply defaults to
        # the values we have been supplied by the user.
        for configClass in CONFIG_COMPONENT_CLASSES:
            # Only send the parent config if the child
            # config component is present (otherwise it assumes that the
            # keys from other components are part of the child)
            localOverrides = None
            if configClass.component in butlerConfig:
                localOverrides = butlerConfig
            config = configClass(localOverrides)
            # Re-attach it using the global namespace
            self.update({configClass.component: config})
            # Remove the key from the butlerConfig since we have already
            # merged that information.
            if configClass.component in butlerConfig:
                del butlerConfig[configClass.component]

        # Now that we have all the defaults we can merge the externally
        # provided config into the defaults.
        # Not needed if there is never information in a butler config file
        # not present in component configurations
        self.update(butlerConfig)
