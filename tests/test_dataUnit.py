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

import unittest

import lsst.utils
import lsst.utils.tests

from lsst.daf.butler import DataUnit, DataUnitConfig, DataUnitRegistry


class DataUnitRegistryTestCase(lsst.utils.tests.TestCase):
    """Tests for `DataUnitRegistry`.
    """
    def setUp(self):
        self.config = DataUnitConfig()

    def testConstructor(self):
        """Independent check for `Schema` constructor.
        """
        dataUnitRegistry = DataUnitRegistry.fromConfig(self.config)
        self.assertIsInstance(dataUnitRegistry, DataUnitRegistry)
        for dataUnitName, dataUnit in dataUnitRegistry.items():
            self.assertIsInstance(dataUnit, DataUnit)
            for d in dataUnit.dependencies:
                self.assertIsInstance(d, DataUnit)

        # Tests below depend on the schema.yaml definitions as well

        # check all spatial data units names, Detector is there because
        # pair (Visit, Detector) is a spatial entity
        self.assertCountEqual(dataUnitRegistry._spatialDataUnits,
                              ["Tract", "Patch", "Visit", "Detector", "SkyPix"])
        self.assertCountEqual(dataUnitRegistry._dataUnitRegions.keys(),
                              [{'Visit'}, {'SkyPix'}, {'Tract'},
                               {'Patch', 'Tract'}, {'Detector', 'Visit'}])
        self.assertEqual(len(dataUnitRegistry.joins), 11)
        joins = ((['Exposure'], ['Exposure']),
                 (['CalibIdentifier'], ['Exposure']),
                 (['Patch'], ['SkyPix']),
                 (['Detector', 'Visit'], ['Patch']),
                 (['Detector', 'Visit'], ['SkyPix']),
                 (['Detector', 'Visit'], ['Tract']),
                 (['Tract'], ['SkyPix']),
                 (['Visit'], ['Patch']),
                 (['Visit'], ['Detector']),
                 (['Visit'], ['SkyPix']))
        for lhs, rhs in joins:
            self.assertIsNotNone(dataUnitRegistry.getJoin(lhs, rhs))
            self.assertIsNotNone(dataUnitRegistry.getJoin(rhs, lhs))

    def testGetRegionHolder(self):
        """Test that getRegionHolder works for all DataUnits or combinations
        of DataUnits that have regions, regardless of whether those are
        expanded to include required dependencies.
        """
        dataUnitRegistry = DataUnitRegistry.fromConfig(self.config)
        self.assertEqual(dataUnitRegistry.getRegionHolder("Visit"),
                         dataUnitRegistry.getRegionHolder("Instrument", "Visit"))
        self.assertEqual(dataUnitRegistry.getRegionHolder("Visit", "Detector"),
                         dataUnitRegistry.getRegionHolder("Instrument", "Visit", "Detector"))
        self.assertEqual(dataUnitRegistry.getRegionHolder("Patch"),
                         dataUnitRegistry.getRegionHolder("Tract", "Patch"))
        self.assertEqual(dataUnitRegistry.getRegionHolder("Patch"),
                         dataUnitRegistry.getRegionHolder("SkyMap", "Tract", "Patch"))
        with self.assertRaises(KeyError):
            dataUnitRegistry.getRegionHolder("Detector")
        with self.assertRaises(KeyError):
            dataUnitRegistry.getRegionHolder("Instrument", "Detector")


if __name__ == "__main__":
    unittest.main()
