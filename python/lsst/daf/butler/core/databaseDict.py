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

__all__ = ("DatabaseDict", "DatabaseDictRecordBase")

from dataclasses import fields, asdict
from collections.abc import MutableMapping
from typing import Dict, Type, Any, ClassVar, Optional, Sequence

from lsst.utils import doImport
from .config import Config
from .registry import Registry


class DatabaseDictRecordBase(Sequence):
    """A base class to be used to define a record to be stored in a
    `DatabaseDict`.

    Expected to be subclassed with a dataclass defining the fields and
    types to be stored in the registry, along with a specification of
    lengths of string fields.

    The fields themselves can be retrieved by index and the number
    of fields defined in the class can be queried.
    """
    __slots__ = ()

    # make a dataclass named tuple-like by accessing fields by index
    def __getitem__(self, i):
        return getattr(self, fields(self)[i].name)

    def __len__(self):
        return len(fields(self))

    lengths: ClassVar[Dict[str, int]] = {}
    """Lengths of string fields (optional)."""

    key_type: ClassVar[Type] = int
    """Type to use for key field."""

    @classmethod
    def fields(cls) -> Sequence[str]:
        """Emulate the namedtuple._fields class attribute"""
        return tuple(f.name for f in fields(cls))

    @classmethod
    def types(cls) -> Dict[str, Type]:
        """Return a dict indexed by name and with the python type as the
        value."""
        return {f.name: f.type for f in fields(cls)}

    def _asdict(self) -> Dict[str, Any]:
        return asdict(self)


class DatabaseDict(MutableMapping):
    """An abstract base class for dict-like objects with a specific key type
    and data class values, backed by a database.

    DatabaseDict subclasses must implement the abstract ``__getitem__``,
    ``__setitem__``, ``__delitem__`, ``__iter__``, and ``__len__`` abstract
    methods defined by `~collections.abc.MutableMapping`.

    They must also provide a constructor that takes the same arguments as that
    of `DatabaseDict` itself, *unless* they are constructed solely by
    `Registry.makeDatabaseDict` (in which case any constructor arguments are
    permitted).

    Parameters
    ----------
    config : `Config`
        Configuration used to identify and construct a subclass.
    key : `str`
        The name of the field to be used as the dictionary key.  Must not be
        present in ``value._fields``.
    value : `type`
        The type used for the dictionary's values, typically a
        `DatabaseDictRecordBase`.  Must have a ``fields`` class method
        that is a tuple of field names; these field names must also appear
        in the return value of the ``types()`` class method, and it must be
        possible to construct it from a sequence of values. Lengths of string
        fields must be obtainable as a `dict` from using the ``lengths``
        property.
    """

    registry: Registry
    """Registry to be used to hold the contents of the DatabaseDict."""

    @staticmethod
    def fromConfig(config: Config, key: str, value: DatabaseDictRecordBase,
                   registry: Optional[Registry] = None):
        """Create a `DatabaseDict` subclass instance from `config`.

        If ``config`` contains a class ``cls`` key, this will be assumed to
        be the fully-qualified name of a DatabaseDict subclass to construct.
        If not, ``registry.makeDatabaseDict`` will be called instead, and
        ``config`` must contain a ``table`` key with the name of the table
        to use.

        Parameters
        ----------
        config : `Config`
            Configuration used to identify and construct a subclass.
        key : `str`
            The name of the field to be used as the dictionary key.  Must not
            be present in ``value.fields()``.
        value : `type`
            The type used for the dictionary's values, typically a
            `DatabaseDictRecordBase`.  Must have a ``fields`` class method
            that is a tuple of field names; these field names must also appear
            in the return value of the ``types()`` class method, and it must be
            possible to construct it from a sequence of values. Lengths of
            string fields must be obtainable as a `dict` from using the
            ``lengths`` property.
        registry : `Registry`, optional
            A registry instance from which a `DatabaseDict` subclass can be
            obtained.  Ignored if ``config["cls"]`` exists; may be None if
            it does.

        Returns
        -------
        dictionary : `DatabaseDict` (subclass)
            A new `DatabaseDict` subclass instance.
        """
        if "cls" in config:
            cls = doImport(config["cls"])
            return cls(config=config, key=key, value=value)
        else:
            table = config["table"]
            if registry is None:
                raise ValueError("Either config['cls'] or registry must be provided.")
            return registry.makeDatabaseDict(table, key=key, value=value)

    def __init__(self, config: Config, key: str, value: DatabaseDictRecordBase):
        # This constructor is currently defined just to clearly document the
        # interface subclasses should conform to.
        pass
