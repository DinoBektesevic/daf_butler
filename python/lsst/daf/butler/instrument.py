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

__all__ = ("Instrument", "updateExposureEntryFromObsInfo", "updateVisitEntryFromObsInfo",
           "ObservationDataIdPacker", "addUnboundedCalibrationLabel")

import os.path
from datetime import datetime
from inspect import isabstract
from abc import ABCMeta, abstractmethod

from lsst.daf.butler import DataId, DataIdPacker


# TODO: all code in this module probably needs to be moved to a higher-level
# package (perhaps obs_base), but it is needed by the gen2convert subpackage.
# We should probably move that as well.


class Instrument(metaclass=ABCMeta):
    """Base class for instrument-specific logic for the Gen3 Butler.

    Concrete instrument subclasses should either be directly constructable
    with no arguments or provide a 'factory' `staticmethod`, `classmethod`, or
    other callable class attribute that takes no arguments and returns a new
    `Instrument` instance.
    """

    factories = {}
    """Global dictionary that maps instrument name used in the registry to
    a no-argument callable that can be used to construct a Python instance.
    """

    configPaths = []
    """Paths to config files to read for specific Tasks.

    The paths in this list should contain files of the form `task.py`, for
    each of the Tasks that requires special configuration.
    """

    @property
    @abstractmethod
    def filterDefinitions(self):
        """`~lsst.obs.base.FilterDefinitionCollection`, defining the filters
        for this instrument.
        """
        return None

    def __init__(self, *args, **kwargs):
        self.filterDefinitions.defineFilters()

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if not isabstract(cls):
            factory = getattr(cls, "factory", cls)
            Instrument.factories[cls.getName()] = factory

    @classmethod
    @abstractmethod
    def getName(cls):
        raise NotImplementedError()

    @abstractmethod
    def getCamera(self):
        """Retrieve the cameraGeom representation of this instrument.

        This is a temporary API that should go away once obs_ packages have
        a standardized approach to writing versioned cameras to a Gen3 repo.
        """
        raise NotImplementedError()

    @abstractmethod
    def register(self, registry):
        """Insert instrument, physical_filter, and detector entries into a
        `Registry`.
        """
        raise NotImplementedError()

    def _registerFilters(self, registry):
        """Register the physical and abstract filter Dimension relationships.
        This should be called in the ``register`` implementation.

        Parameters
        ----------
        registry : `lsst.daf.butler.core.Registry`
            The registry to add dimensions to.
        """
        for filter in self.filterDefinitions:
            registry.addDimensionEntry(
                "physical_filter",
                instrument=self.getName(),
                physical_filter=filter.physical_filter,
                abstract_filter=filter.abstract_filter
            )

    @abstractmethod
    def getRawFormatter(self, dataId):
        """Return the Formatter class that should be used to read a particular
        raw file.

        Parameters
        ----------
        dataId : `DataId`
            Dimension-link identifier for the raw file or files being ingested.

        Returns
        -------
        formatter : `Formatter` class
            Class to be used that reads the file into an
            `lsst.afw.image.Exposure` instance.
        """
        raise NotImplementedError()

    @abstractmethod
    def writeCuratedCalibrations(self, butler):
        """Write human-curated calibration Datasets to the given Butler with
        the appropriate validity ranges.

        This is a temporary API that should go away once obs_ packages have
        a standardized approach to this problem.
        """
        raise NotImplementedError()

    def applyConfigOverrides(self, name, config):
        """Apply instrument-specific overrides for a task config.

        Parameters
        ----------
        name : `str`
            Name of the object being configured; typically the _DefaultName
            of a Task.
        config : `lsst.pex.config.Config`
            Config instance to which overrides should be applied.
        """
        for root in self.configPaths:
            path = os.path.join(root, f"{name}.py")
            if os.path.exists(path):
                config.load(path)


class ObservationDataIdPacker(DataIdPacker):
    """A `DataIdPacker` for visit+detector or exposure+detector, given an
    instrument.

    Parameters
    ----------
    dimensions : `DataIdPackerDimensions`
        Struct defining the "given" (at contructoin) and "required" (for
        packing) dimensions of this packer.
    instrument : `str`
        Name of the instrument for which this packer packs IDs.
    obsMax : `int`
        Maximum (exclusive) value for either visit or exposure IDs for this
        instrument, depending on which of those is present in
        ``dimensions.required``.
    detectorMax : `int
        Maximum (exclusive) value for detectors for this instrument.
    """

    def __init__(self, dimensions, instrument, obsMax, detectorMax):
        self._instrumentName = instrument
        if dimensions.required == ("instrument", "visit", "detector"):
            self._observationLink = "visit"
        elif dimensions.required == ("instrument", "exposure", "detector"):
            self._observationLink = "exposure"
        else:
            raise ValueError(f"Invalid dimensions for ObservationDataIdPacker: {dimensions.required}")
        self._detectorMax = detectorMax
        self._maxBits = (obsMax*self._detectorMax).bit_length()

    @property
    def maxBits(self):
        # Docstring inherited from DataIdPacker.maxBits
        return self._maxBits

    def _pack(self, dataId):
        # Docstring inherited from DataIdPacker._pack
        return dataId["detector"] + self._detectorMax*dataId[self._observationLink]

    def unpack(self, packedId):
        # Docstring inherited from DataIdPacker.unpack
        return DataId({"instrument": self._instrumentName,
                       "detector": packedId % self._detectorMax,
                       self._observationLink: packedId // self._detectorMax},
                      dimensions=self.dimensions.required)


def updateExposureEntryFromObsInfo(dataId, obsInfo):
    """Construct an exposure Dimension entry from
    `astro_metadata_translator.ObservationInfo`.

    Parameters
    ----------
    dataId : `dict` or `DataId`
        Dictionary of Dimension link fields for (at least) exposure. If a true
        `DataId`, this object will be modified and returned.
    obsInfo : `astro_metadata_translator.ObservationInfo`
        A `~astro_metadata_translator.ObservationInfo` object corresponding to
        the exposure.

    Returns
    -------
    dataId : `DataId`
        A data ID with the entry for the exposure dimension updated.
    """
    dataId = DataId(dataId)
    dataId.entries[dataId.dimensions()["exposure"]].update(
        datetime_begin=obsInfo.datetime_begin.to_datetime(),
        datetime_end=obsInfo.datetime_end.to_datetime(),
        exposure_time=obsInfo.exposure_time.to_value("s"),
        dark_time=obsInfo.dark_time.to_value("s")
    )
    return dataId


def updateVisitEntryFromObsInfo(dataId, obsInfo):
    """Construct a visit Dimension entry from
    `astro_metadata_translator.ObservationInfo`.

    Parameters
    ----------
    dataId : `dict` or `DataId`
        Dictionary of Dimension link fields for (at least) visit. If a true
        `DataId`, this object will be modified and returned.
    obsInfo : `astro_metadata_translator.ObservationInfo`
        A `~astro_metadata_translator.ObservationInfo` object corresponding to
        the exposure.

    Returns
    -------
    dataId : `DataId`
        A data ID with the entry for the visit dimension updated.
    """
    dataId = DataId(dataId)
    dataId.entries[dataId.dimensions()["visit"]].update(
        datetime_begin=obsInfo.datetime_begin.to_datetime(),
        datetime_end=obsInfo.datetime_end.to_datetime(),
        exposure_time=obsInfo.exposure_time.to_value("s"),
    )
    return dataId


def addUnboundedCalibrationLabel(registry, instrumentName):
    """Add a special 'unbounded' calibration_label dimension entry for the
    given camera that is valid for any exposure.

    If such an entry already exists, this function just returns a `DataId`
    for the existing entry.

    Parameters
    ----------
    registry : `Registry`
        Registry object in which to insert the dimension entry.
    instrumentName : `str`
        Name of the instrument this calibration label is associated with.

    Returns
    -------
    dataId : `DataId`
        New or existing data ID for the unbounded calibration.
    """
    d = dict(instrument=instrumentName, calibration_label="unbounded")
    try:
        return registry.expandDataId(dimension="calibration_label",
                                     metadata=["valid_first", "valid_last"], **d)
    except LookupError:
        pass
    unboundedDataId = DataId(universe=registry.dimensions, **d)
    unboundedDataId.entries["calibration_label"]["valid_first"] = datetime.min
    unboundedDataId.entries["calibration_label"]["valid_last"] = datetime.max
    registry.addDimensionEntry("calibration_label", unboundedDataId)
    return unboundedDataId
