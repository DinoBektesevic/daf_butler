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

import os
import pickle
import unittest

from lsst.daf.butler import StorageClass, StorageClassFactory, StorageClassConfig, CompositeAssembler

"""Tests related to the StorageClass infrastructure.
"""

TESTDIR = os.path.abspath(os.path.dirname(__file__))


class PythonType:
    """A dummy class to test the registry of Python types."""
    pass


class StorageClassFactoryTestCase(unittest.TestCase):
    """Tests of the storage class infrastructure.
    """

    def testCreation(self):
        """Test that we can dynamically create storage class subclasses.

        This is critical for testing the factory functions."""
        className = "TestImage"
        sc = StorageClass(className, pytype=dict)
        self.assertIsInstance(sc, StorageClass)
        self.assertEqual(sc.name, className)
        self.assertEqual(str(sc), className)
        self.assertFalse(sc.components)
        self.assertTrue(sc.validateInstance({}))
        self.assertFalse(sc.validateInstance(""))

        r = repr(sc)
        self.assertIn("StorageClass", r)
        self.assertIn(className, r)
        self.assertNotIn("parameters", r)
        self.assertIn("pytype='dict'", r)

        # Ensure we do not have an assembler
        with self.assertRaises(TypeError):
            sc.assembler()

        # Allow no definition of python type
        scn = StorageClass(className)
        self.assertIs(scn.pytype, object)

        # Include some components
        scc = StorageClass(className, pytype=PythonType, components={"comp1": sc})
        self.assertIn("comp1", scc.components)
        r = repr(scc)
        self.assertIn("comp1", r)
        self.assertIn("lsst.daf.butler.core.assembler.CompositeAssembler", r)

        # Ensure that we have an assembler
        self.assertIsInstance(scc.assembler(), CompositeAssembler)

        # Check we can create a storageClass using the name of an importable
        # type.
        sc2 = StorageClass("TestImage2",
                           "lsst.daf.butler.core.storageClass.StorageClassFactory")
        self.assertIsInstance(sc2.pytype(), StorageClassFactory)
        self.assertIn("butler.core", repr(sc2))

    def testParameters(self):
        """Test that we can set parameters and validate them"""
        pt = ("a", "b")
        ps = {"a", "b"}
        pl = ["a", "b"]
        for p in (pt, ps, pl):
            sc1 = StorageClass("ParamClass", pytype=dict, parameters=p)
            self.assertEqual(sc1.parameters, ps)
            sc1.validateParameters(p)

        sc1.validateParameters()
        sc1.validateParameters({"a": None, "b": None})
        sc1.validateParameters(["a", ])
        with self.assertRaises(KeyError):
            sc1.validateParameters({"a", "c"})

    def testEquality(self):
        """Test that StorageClass equality works"""
        className = "TestImage"
        sc1 = StorageClass(className, pytype=dict)
        sc2 = StorageClass(className, pytype=dict)
        self.assertEqual(sc1, sc2)
        sc3 = StorageClass(className + "2", pytype=str)
        self.assertNotEqual(sc1, sc3)

        # Same StorageClass name but different python type
        sc4 = StorageClass(className, pytype=str)
        self.assertNotEqual(sc1, sc4)

        # Parameters
        scp = StorageClass("Params", pytype=PythonType, parameters=["a", "b", "c"])
        scp1 = StorageClass("Params", pytype=PythonType, parameters=["a", "b", "c"])
        scp2 = StorageClass("Params", pytype=PythonType, parameters=["a", "b", "d", "e"])
        self.assertEqual(scp, scp1)
        self.assertNotEqual(scp, scp2)

        # Now with components
        sc5 = StorageClass("Composite", pytype=PythonType,
                           components={"comp1": sc1, "comp2": sc3})
        sc6 = StorageClass("Composite", pytype=PythonType,
                           components={"comp1": sc1, "comp2": sc3})
        self.assertEqual(sc5, sc6)
        self.assertNotEqual(sc5, sc3)
        sc7 = StorageClass("Composite", pytype=PythonType,
                           components={"comp1": sc4, "comp2": sc3})
        self.assertNotEqual(sc5, sc7)
        sc8 = StorageClass("Composite", pytype=PythonType,
                           components={"comp2": sc3})
        self.assertNotEqual(sc5, sc8)
        sc9 = StorageClass("Composite", pytype=PythonType,
                           components={"comp2": sc3}, assembler="lsst.daf.butler.Butler")
        self.assertNotEqual(sc5, sc9)

    def testRegistry(self):
        """Check that storage classes can be created on the fly and stored
        in a registry."""
        className = "TestImage"
        factory = StorageClassFactory()
        newclass = StorageClass(className, pytype=PythonType)
        factory.registerStorageClass(newclass)
        sc = factory.getStorageClass(className)
        self.assertIsInstance(sc, StorageClass)
        self.assertEqual(sc.name, className)
        self.assertFalse(sc.components)
        self.assertEqual(sc.pytype, PythonType)
        self.assertIn(sc, factory)
        newclass2 = StorageClass("Temporary2", pytype=str)
        self.assertNotIn(newclass2, factory)
        factory.registerStorageClass(newclass2)
        self.assertIn(newclass2, factory)
        self.assertIn("Temporary2", factory)
        self.assertNotIn("Temporary3", factory)
        self.assertNotIn({}, factory)

        # Make sure we can't register a storage class with the same name
        # but different values
        newclass3 = StorageClass("Temporary2", pytype=dict)
        with self.assertRaises(ValueError):
            factory.registerStorageClass(newclass3)

        factory._unregisterStorageClass(newclass3.name)
        self.assertNotIn(newclass3, factory)
        self.assertNotIn(newclass3.name, factory)
        factory.registerStorageClass(newclass3)
        self.assertIn(newclass3, factory)
        self.assertIn(newclass3.name, factory)

        # Check you can silently insert something that is already there
        factory.registerStorageClass(newclass3)

    def testFactoryConfig(self):
        factory = StorageClassFactory()
        factory.addFromConfig(StorageClassConfig())
        image = factory.getStorageClass("Image")
        imageF = factory.getStorageClass("ImageF")
        self.assertIsInstance(imageF, type(image))
        self.assertNotEqual(imageF, image)

        # Check component inheritance
        exposure = factory.getStorageClass("Exposure")
        exposureF = factory.getStorageClass("ExposureF")
        self.assertIsInstance(exposureF, type(exposure))
        self.assertIsInstance(exposure.components["image"], type(image))
        self.assertNotIsInstance(exposure.components["image"], type(imageF))
        self.assertIsInstance(exposureF.components["image"], type(image))
        self.assertIsInstance(exposureF.components["image"], type(imageF))
        self.assertIn("wcs", exposure.components)
        self.assertIn("wcs", exposureF.components)

        # Check parameters
        factory.addFromConfig(os.path.join(TESTDIR, "config", "basic", "storageClasses.yaml"))
        thing1 = factory.getStorageClass("ThingOne")
        thing2 = factory.getStorageClass("ThingTwo")
        self.assertIsInstance(thing2, type(thing1))
        param1 = thing1.parameters
        param2 = thing2.parameters
        self.assertIn("param3", thing2.parameters)
        self.assertNotIn("param3", thing1.parameters)
        param2.remove("param3")
        self.assertEqual(param1, param2)

        # Check that we can't have a new StorageClass that does not
        # inherit from StorageClass
        with self.assertRaises(ValueError):
            factory.makeNewStorageClass("ClassName", baseClass=StorageClassFactory)

        sc = factory.makeNewStorageClass("ClassName")
        self.assertIsInstance(sc(), StorageClass)

    def testPickle(self):
        """Test that we can pickle storageclasses.
        """
        className = "TestImage"
        sc = StorageClass(className, pytype=dict)
        self.assertIsInstance(sc, StorageClass)
        self.assertEqual(sc.name, className)
        self.assertFalse(sc.components)
        sc2 = pickle.loads(pickle.dumps(sc))
        self.assertEqual(sc2, sc)


if __name__ == "__main__":
    unittest.main()
