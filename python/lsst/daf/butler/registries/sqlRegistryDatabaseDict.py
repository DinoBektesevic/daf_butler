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

__all__ = ("SqlRegistryDatabaseDict",)

from datetime import datetime

from sqlalchemy import Table, Column, \
    String, Integer, Boolean, LargeBinary, DateTime, Float
from sqlalchemy import CheckConstraint
from sqlalchemy.sql import select, bindparam, func
from sqlalchemy.exc import IntegrityError, StatementError

from lsst.daf.butler import DatabaseDict


class SqlRegistryDatabaseDict(DatabaseDict):
    """A DatabaseDict backed by a SQL database.

    Configuration for SqlRegistryDatabaseDict must have the following entry:

    ``table``
        Name of the database table used to store the data in the
        dictionary.

    Parameters
    ----------
    config : `Config`
        Configuration used to identify this subclass and connect to a
        database.
    key : `str`
        The name of the field to be used as the dictionary key.  Must not be
        present in ``value.fields()``.
    value : `type` (`DatabaseDictRecordBase`)
        The type used for the dictionary's values, typically a
        `DatabaseDictRecordBase`.  Must have a ``fields`` class method
        that is a tuple of field names; these field names must also appear
        in the return value of the ``types()`` class method, and it must be
        possible to construct it from a sequence of values. Lengths of string
        fields must be obtainable as a `dict` from using the ``lengths``
        property.
    registry : `SqlRegistry`
        A registry object with an open connection and a schema.
    """

    COLUMN_TYPES = {str: String, int: Integer, float: Float,
                    bool: Boolean, bytes: LargeBinary, datetime: DateTime}

    def __init__(self, config, key, value, registry):
        self.registry = registry
        allColumns = []
        allConstraints = []
        lengths = value.lengths
        types = value.types().copy()
        # Add the primary key type
        if key not in types:
            types[key] = value.key_type
        # The order of columns in the table depends on the order returned
        # from the types. This will match the fields() order with the
        # primary key at the end if it was added explicitly.
        for name, type_ in types.items():
            column_type = self.COLUMN_TYPES.get(type_, type_)
            if issubclass(column_type, String) and name in lengths:
                column_type = column_type(length=lengths[name])
                allConstraints.append(CheckConstraint(f"length({name})<={lengths[name]}",
                                                      name=f"ck_{config['table']}_{name}_len"))
            column = Column(name, column_type, primary_key=(name == key))
            allColumns.append(column)
        if key in value.fields():
            raise ValueError("DatabaseDict's key field may not be a part of the value tuple")
        if key not in types.keys():
            raise TypeError("No type provided for key '{}'".format(key))
        if not types.keys() >= frozenset(value.fields()):
            raise TypeError("No type(s) provided for field(s) {}".format(set(value.fields()) - types.keys()))
        if not config["table"].islower():
            raise ValueError(f"DatabaseDict tablename {config['table']} is not lowercase.")
        self._key = key
        self._value = value
        self._table = Table(config["table"], self.registry._schema.metadata, *allColumns, *allConstraints)
        self._table.create(self.registry._connection, checkfirst=True)
        valueColumns = [getattr(self._table.columns, name) for name in self._value.fields()]
        keyColumn = getattr(self._table.columns, key)
        self._getSql = select(valueColumns).where(keyColumn == bindparam("key"))
        self._updateSql = self._table.update().where(keyColumn == bindparam("key"))
        self._delSql = self._table.delete().where(keyColumn == bindparam("key"))
        self._keysSql = select([keyColumn])
        self._lenSql = select([func.count(keyColumn)])

    def __getitem__(self, key):
        row = self.registry._connection.execute(self._getSql, key=key).fetchone()
        if row is None:
            raise KeyError("{} not found".format(key))
        return self._value(*row)

    def __setitem__(self, key, value):
        assert isinstance(value, self._value)
        # Try insert first, as we expect that to be the most commmon usage
        # pattern.
        kwds = value._asdict()
        kwds[self._key] = key
        with self.registry._connection.begin_nested():
            try:
                self.registry._connection.execute(self._table.insert(), **kwds)
                return
            except IntegrityError as e:
                # Swallow the expected IntegrityError (due to i.e. duplicate
                # primary key values)
                # TODO: would be better to explicitly inspect the error, but
                # this is tricky.
                if "CHECK constraint failed" in str(e):
                    raise ValueError(f"{e}") from e
            except StatementError as err:
                raise TypeError("Bad data types in value: {}".format(err)) from err

        # If we fail due to an IntegrityError (i.e. duplicate primary key
        # values), try to do an update instead.
        kwds.pop(self._key, None)
        with self.registry._connection.begin_nested():
            try:
                self.registry._connection.execute(self._updateSql, key=key, **kwds)
            except StatementError as err:
                # n.b. we can't rely on a failure in the insert attempt above
                # to have caught this case, because we trap for IntegrityError
                # first.  And we have to do that because IntegrityError is a
                # StatementError.
                raise TypeError("Bad data types in value: {}".format(err)) from err

    def __delitem__(self, key):
        with self.registry._connection.begin():
            result = self.registry._connection.execute(self._delSql, key=key)
            if result.rowcount == 0:
                raise KeyError("{} not found".format(key))

    def __iter__(self):
        for row in self.registry._connection.execute(self._keysSql).fetchall():
            yield row[0]

    def __len__(self):
        return self.registry._connection.execute(self._lenSql).scalar()

    # TODO: add custom view objects for at views() and items(), so we don't
    # invoke a __getitem__ call for every key.
