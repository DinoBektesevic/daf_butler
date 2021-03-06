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

__all__ = ("RegistryConfig",)

from .connectionString import ConnectionStringFactory
from .config import ConfigSubset
from lsst.utils import doImport


class RegistryConfig(ConfigSubset):
    component = "registry"
    requiredKeys = ("db",)
    defaultConfigFile = "registry.yaml"

    def getDialect(self):
        """Parses the `db` key of the config and returns the database dialect.

        Returns
        -------
        dialect : `str`
            Dialect found in the connection string.
        """
        conStr = ConnectionStringFactory.fromConfig(self)
        return conStr.get_backend_name()

    def getRegistryClass(self):
        """Returns registry class targeted by configuration values.

        The appropriate class is determined from the `cls` key, if it exists.
        Otherwise the `db` key is parsed and the correct class is determined
        from a list of aliases found under `clsMap` key of the registry config.

        Returns
        -------
        registry : `type`
           Class of type `Registry` targeted by the registry configuration.
        """
        if self.get("cls") is not None:
            registryClass = self.get("cls")
        else:
            dialect = self.getDialect()
            if dialect not in self["clsMap"]:
                raise ValueError(f"Connection string dialect has no known aliases. Received: {dialect}")
            registryClass = self.get(("clsMap", dialect))

        return doImport(registryClass)

    @property
    def connectionString(self):
        """Return the connection string to the underlying database
        (`sqlalchemy.engine.url.URL`).
        """
        return ConnectionStringFactory.fromConfig(self)
