# coding: utf8

# Copyright 2014-2015 Vincent Jacques <vincent@vincent-jacques.net>

"""
When given a :class:`DescribeTable`, the connection will return a :class:`DescribeTableResponse`:

>>> r = connection(DescribeTable(table))
>>> r
<LowVoltage.actions.describe_table.DescribeTableResponse ...>
>>> r.table.table_status
u'ACTIVE'
>>> r.table.key_schema[0].attribute_name
u'h'
>>> r.table.key_schema[0].key_type
u'HASH'
"""

import datetime

import LowVoltage as _lv
import LowVoltage.testing as _tst
from .action import Action
from .return_types import TableDescription, _is_dict
from .next_gen_mixins import proxy
from .next_gen_mixins import (
    TableName,
)


class DescribeTableResponse(object):
    """
    The `DescribeTable response <http://docs.aws.amazon.com/amazondynamodb/latest/APIReference/API_DescribeTable.html#API_DescribeTable_ResponseElements>`__.
    """

    def __init__(
        self,
        Table=None,
        **dummy
    ):
        self.__table = Table

    @property
    def table(self):
        """
        The description of the table.

        :type: ``None`` or :class:`.TableDescription`
        """
        if _is_dict(self.__table):  # pragma no branch (Defensive code)
            return TableDescription(**self.__table)


class DescribeTable(Action):
    """
    The `DescribeTable request <http://docs.aws.amazon.com/amazondynamodb/latest/APIReference/API_DescribeTable.html#API_DescribeTable_RequestParameters>`__.
    """

    def __init__(self, table_name=None):
        super(DescribeTable, self).__init__("DescribeTable", DescribeTableResponse)
        self.__table_name = TableName(self, table_name)

    @property
    def payload(self):
        data = {}
        data.update(self.__table_name.payload)
        return data

    @proxy
    def table_name(self, table_name):
        """
        >>> connection(DescribeTable().table_name(table))
        <LowVoltage.actions.describe_table.DescribeTableResponse object at ...>
        """
        return self.__table_name.set(table_name)


class DescribeTableUnitTests(_tst.UnitTests):
    def test_name(self):
        self.assertEqual(DescribeTable("Foo").name, "DescribeTable")

    def test_table_name(self):
        self.assertEqual(DescribeTable().table_name("Foo").payload, {"TableName": "Foo"})

    def test_constuctor(self):
        self.assertEqual(DescribeTable("Foo").payload, {"TableName": "Foo"})


class DescribeTableLocalIntegTests(_tst.LocalIntegTests):
    def setUp(self):
        super(DescribeTableLocalIntegTests, self).setUp()
        self.connection(
            _lv.CreateTable("Aaa").hash_key("h", _lv.STRING).provisioned_throughput(1, 2)
        )

    def tearDown(self):
        self.connection(_lv.DeleteTable("Aaa"))
        super(DescribeTableLocalIntegTests, self).tearDown()

    def test(self):
        r = self.connection(_lv.DescribeTable("Aaa"))

        self.assertDateTimeIsReasonable(r.table.creation_date_time)
        self.assertEqual(r.table.attribute_definitions[0].attribute_name, "h")
        self.assertEqual(r.table.attribute_definitions[0].attribute_type, "S")
        self.assertEqual(r.table.global_secondary_indexes, None)
        self.assertEqual(r.table.item_count, 0)
        self.assertEqual(r.table.key_schema[0].attribute_name, "h")
        self.assertEqual(r.table.key_schema[0].key_type, "HASH")
        self.assertEqual(r.table.local_secondary_indexes, None)
        self.assertEqual(r.table.provisioned_throughput.last_decrease_date_time, datetime.datetime(1970, 1, 1))
        self.assertEqual(r.table.provisioned_throughput.last_increase_date_time, datetime.datetime(1970, 1, 1))
        self.assertEqual(r.table.provisioned_throughput.number_of_decreases_today, 0)
        self.assertEqual(r.table.provisioned_throughput.read_capacity_units, 1)
        self.assertEqual(r.table.provisioned_throughput.write_capacity_units, 2)
        self.assertEqual(r.table.table_name, "Aaa")
        self.assertEqual(r.table.table_size_bytes, 0)
        self.assertEqual(r.table.table_status, "ACTIVE")
