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

"""Tests for ConnectionStringBuilder.
"""

import unittest
import os
import os.path


from lsst.pex.policy import Policy
from lsst.daf.persistence import DbAuth
from lsst.daf.butler.core.registry import RegistryConfig, ConnectionStringBuilder

TESTDIR = os.path.abspath(os.path.dirname(__file__))


class ConnectionStringBuilderTestCase(unittest.TestCase):
    """Tests for ConnectionStringBuilder."""
    configDir = os.path.join(TESTDIR, "config/basic/connectionStringConfs/")
    configFiles = os.listdir(configDir)

    def setUp(self):
        pol = Policy(os.path.join(TESTDIR, "testDbAuth.paf"))
        DbAuth.setPolicy(pol)

    def tearDown(self):
        DbAuth.resetPolicy()

    def testBuilder(self):
        """Tests ConnectionStringBuilder builds correct connection strings.
        """
        regConfigs = [RegistryConfig(os.path.join(self.configDir, name)) for name in self.configFiles]

        for regConf, fileName in zip(regConfigs, self.configFiles):
            conStr = ConnectionStringBuilder.fromConfig(regConf)
            with self.subTest(confFile=fileName):
                self.assertEqual(conStr, regConf['expected'],
                                 "test connection string built from config")

    def testRelVsAbsPath(self):
        """Tests that relative and absolute paths are preserved."""
        regConf = RegistryConfig(os.path.join(self.configDir, 'conf1.yaml'))

        regConf['db'] = 'sqlite:///relative/path/conf1.sqlite3'
        conStr = ConnectionStringBuilder.fromConfig(regConf)
        self.assertEqual(conStr, 'sqlite+pysqlite:///relative/path/conf1.sqlite3')

        regConf['db'] = 'sqlite+pysqlite:////absolute/path/conf2.sqlite3'
        conStr = ConnectionStringBuilder.fromConfig(regConf)
        self.assertEqual(conStr, 'sqlite+pysqlite:////absolute/path/conf2.sqlite3')

    def testHostKeyIsHostnameOnly(self):
        """Tests that relative and absolute paths are preserved."""
        regConf = RegistryConfig(os.path.join(self.configDir, 'conf2.yaml'))

        regConf['host'] = 'some.host.com:1234'
        with self.assertRaises(ValueError):
            ConnectionStringBuilder.fromConfig(regConf)

        regConf['host'] = 'some.host.com:1234/dbname'
        with self.assertRaises(ValueError):
            ConnectionStringBuilder.fromConfig(regConf)