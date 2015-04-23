# coding: utf8

# Copyright 2014-2015 Vincent Jacques <vincent@vincent-jacques.net>

import LowVoltage as _lv
import LowVoltage.testing as _tst
from .action import Action, ActionProxy
from .conversion import _convert_dict_to_db, _convert_db_to_dict
from .expression_mixins import ExpressionAttributeNamesMixin, ProjectionExpressionMixin
from .next_gen_mixins import proxy, ReturnConsumedCapacity, ConsistentRead
from .return_types import ConsumedCapacity_, _is_dict, _is_list_of_dict


class BatchGetItem(Action):
    """
    The `BatchGetItem request <http://docs.aws.amazon.com/amazondynamodb/latest/APIReference/API_BatchGetItem.html#API_BatchGetItem_RequestParameters>`__
    """

    # @todo Move all Results out of their Action class.
    # @todo Document return types and Results
    class Result(object):
        """
        The `BatchGetItem response <http://docs.aws.amazon.com/amazondynamodb/latest/APIReference/API_BatchGetItem.html#API_BatchGetItem_ResponseElements>`__
        """

        def __init__(
            self,
            ConsumedCapacity=None,
            Responses=None,
            UnprocessedKeys=None,
            **dummy
        ):
            self.consumed_capacity = None
            if _is_list_of_dict(ConsumedCapacity):  # pragma no branch (Defensive code)
                self.consumed_capacity = [ConsumedCapacity_(**c) for c in ConsumedCapacity]

            self.responses = None
            if _is_dict(Responses):  # pragma no branch (Defensive code)
                self.responses = {t: [_convert_db_to_dict(v) for v in vs] for t, vs in Responses.iteritems()}

            self.unprocessed_keys = UnprocessedKeys

    def __init__(self, previous_unprocessed_keys=None):
        super(BatchGetItem, self).__init__("BatchGetItem")
        self.__return_consumed_capacity = ReturnConsumedCapacity(self)
        self.__previous_unprocessed_keys = previous_unprocessed_keys
        self.__tables = {}
        self.__active_table = None

    def build(self):
        data = {}
        data.update(self.__return_consumed_capacity.build())
        if self.__previous_unprocessed_keys:
            data["RequestItems"] = self.__previous_unprocessed_keys
        if self.__tables:
            data["RequestItems"] = {n: t.build() for n, t in self.__tables.iteritems()}
        return data

    class _Table(ExpressionAttributeNamesMixin, ProjectionExpressionMixin):
        def __init__(self, action, name):
            ExpressionAttributeNamesMixin.__init__(self)
            ProjectionExpressionMixin.__init__(self)
            self.consistent_read = ConsistentRead(action)
            self.keys = []

        def build(self):
            data = {}
            data.update(self._build_expression_attribute_names())
            data.update(self._build_projection_expression())
            data.update(self.consistent_read.build())
            if self.keys:
                data["Keys"] = [_convert_dict_to_db(k) for k in self.keys]
            return data

    def table(self, name):
        """
        Set the active table. Calls to methods like :meth:`keys` or :meth:`consistent_read_true` will apply to this table.
        """
        if name not in self.__tables:
            self.__tables[name] = self._Table(self, name)
        self.__active_table = self.__tables[name]
        return self

    def keys(self, *keys):
        """
        Add keys to get from the active table.
        """
        for key in keys:
            if isinstance(key, dict):
                key = [key]
            self.__active_table.keys.extend(key)
        return self

    @proxy
    def consistent_read_true(self):
        """
        (for the active table)

        >>> c = connection(
        ...   BatchGetItem()
        ...     .table(table).keys({"h": 0})
        ...     .consistent_read_true()
        ...     .return_consumed_capacity_total()
        ... ).consumed_capacity
        >>> c[0].table_name
        u'LowVoltage.DocTests'
        >>> c[0].capacity_units
        1.0
        """
        return self.__active_table.consistent_read.true()

    @proxy
    def consistent_read_false(self):
        """
        (for the active table)

        >>> c = connection(
        ...   BatchGetItem()
        ...     .table(table).keys({"h": 0})
        ...     .consistent_read_false()
        ...     .return_consumed_capacity_total()
        ... ).consumed_capacity
        >>> c[0].table_name
        u'LowVoltage.DocTests'
        >>> c[0].capacity_units
        0.5
        """
        return self.__active_table.consistent_read.false()

    def expression_attribute_name(self, name, path):
        """
        """
        self.__active_table.expression_attribute_name(name, path)
        return self

    def project(self, *names):
        """
        """
        self.__active_table.project(*names)
        return self

    @proxy
    def return_consumed_capacity_total(self):
        """
        >>> c = connection(
        ...   BatchGetItem()
        ...     .table(table).keys({"h": 0}, {"h": 1}, {"h": 2})
        ...     .table(table2).keys({"h": 0, "r1": 0}, {"h": 1, "r1": 0})
        ...     .return_consumed_capacity_total()
        ... ).consumed_capacity
        >>> c[0].table_name
        u'LowVoltage.DocTests'
        >>> c[0].capacity_units
        1.5
        >>> c[1].table_name
        u'LowVoltage.DocTests2'
        >>> c[1].capacity_units
        1.0
        """
        return self.__return_consumed_capacity.total()

    @proxy
    def return_consumed_capacity_none(self):
        """
        >>> print connection(
        ...   BatchGetItem()
        ...     .table(table)
        ...     .keys({"h": 0}, {"h": 1}, {"h": 2})
        ...     .return_consumed_capacity_none()
        ... ).consumed_capacity
        None
        """
        return self.__return_consumed_capacity.none()


class BatchGetItemUnitTests(_tst.UnitTests):
    def testName(self):
        self.assertEqual(BatchGetItem().name, "BatchGetItem")

    def testEmpty(self):
        self.assertEqual(
            BatchGetItem().build(),
            {}
        )

    def testReturnConsumedCapacityNone(self):
        self.assertEqual(
            BatchGetItem().return_consumed_capacity_none().build(),
            {
                "ReturnConsumedCapacity": "NONE",
            }
        )

    def testKeys(self):
        self.assertEqual(
            BatchGetItem().table("Table2").keys({"hash": u"h21"}).table("Table1").keys({"hash": u"h11"}, {"hash": u"h12"}).table("Table2").keys([{"hash": u"h22"}, {"hash": u"h23"}]).build(),
            {
                "RequestItems": {
                    "Table1": {
                        "Keys": [
                            {"hash": {"S": "h11"}},
                            {"hash": {"S": "h12"}},
                        ]
                    },
                    "Table2": {
                        "Keys": [
                            {"hash": {"S": "h21"}},
                            {"hash": {"S": "h22"}},
                            {"hash": {"S": "h23"}},
                        ]
                    },
                }
            }
        )

    def testConsistentRead(self):
        self.assertEqual(
            BatchGetItem().table("Table1").consistent_read_true().table("Table2").consistent_read_false().build(),
            {
                "RequestItems": {
                    "Table1": {
                        "ConsistentRead": True,
                    },
                    "Table2": {
                        "ConsistentRead": False,
                    },
                }
            }
        )

    def testProject(self):
        self.assertEqual(
            BatchGetItem().table("Table1").project("a").build(),
            {
                "RequestItems": {
                    "Table1": {
                        "ProjectionExpression": "a",
                    },
                }
            }
        )

    # @todo pep8 test names (everywhere)
    def testExpressionAttributeName(self):
        self.assertEqual(
            BatchGetItem().table("Table1").expression_attribute_name("a", "p").build(),
            {
                "RequestItems": {
                    "Table1": {
                        "ExpressionAttributeNames": {"#a": "p"},
                    },
                }
            }
        )


class BatchGetItemLocalIntegTests(_tst.LocalIntegTestsWithTableH):
    def testSimpleBatchGet(self):
        self.connection(_lv.BatchWriteItem().table("Aaa").put(
            {"h": u"1", "a": "xxx"},
            {"h": u"2", "a": "yyy"},
            {"h": u"3", "a": "zzz"},
        ))

        r = self.connection(_lv.BatchGetItem().table("Aaa").keys({"h": u"1"}, {"h": u"2"}, {"h": u"3"}))

        with _tst.cover("r", r) as r:
            self.assertEqual(r.consumed_capacity, None)
            self.assertEqual(r.responses.keys(), ["Aaa"])
            self.assertEqual(
                sorted(r.responses["Aaa"], key=lambda i: i["h"]),
                [{"h": u"1", "a": "xxx"}, {"h": u"2", "a": "yyy"}, {"h": u"3", "a": "zzz"}]
            )
            self.assertEqual(r.unprocessed_keys, {})

    def testBatchGetWithProjections(self):
        self.connection(_lv.BatchWriteItem().table("Aaa").put(
            {"h": u"1", "a": "a1", "b": "b1", "c": "c1"},
            {"h": u"2", "a": "a2", "b": "b2", "c": "c2"},
            {"h": u"3", "a": "a3", "b": "b3", "c": "c3"},
        ))

        r = self.connection(
            _lv.BatchGetItem().table("Aaa").keys({"h": u"1"}, {"h": u"2"}, {"h": u"3"}).expression_attribute_name("p", "b").project("h").project("a", ["#p"])
        )

        with _tst.cover("r", r) as r:
            self.assertEqual(r.consumed_capacity, None)
            self.assertEqual(r.responses.keys(), ["Aaa"])
            self.assertEqual(
                sorted(r.responses["Aaa"], key=lambda i: i["h"]),
                [{"h": u"1", "a": "a1", "b": "b1"}, {"h": u"2", "a": "a2", "b": "b2"}, {"h": u"3", "a": "a3", "b": "b3"}]
            )
            self.assertEqual(r.unprocessed_keys, {})

    def test_get_unexisting_keys(self):
        self.connection(_lv.BatchWriteItem().table("Aaa").put(
            {"h": u"1", "a": "xxx"},
            {"h": u"2", "a": "yyy"},
        ))

        r = self.connection(_lv.BatchGetItem().table("Aaa").keys({"h": u"1"}, {"h": u"2"}, {"h": u"3"}))

        with _tst.cover("r", r) as r:
            self.assertEqual(r.consumed_capacity, None)
            self.assertEqual(r.responses.keys(), ["Aaa"])
            self.assertEqual(
                sorted(r.responses["Aaa"], key=lambda i: i["h"]),
                [{"h": u"1", "a": "xxx"}, {"h": u"2", "a": "yyy"}]
            )
            self.assertEqual(r.unprocessed_keys, {})

    def test_get_without_unprocessed_keys(self):
        _lv.BatchPutItem(self.connection, "Aaa", [{"h": unicode(i)} for i in range(100)])

        r = self.connection(_lv.BatchGetItem().table("Aaa").keys({"h": unicode(i)} for i in range(100)))
        self.assertEqual(r.unprocessed_keys, {})
        self.assertEqual(len(r.responses["Aaa"]), 100)

    def test_get_with_unprocessed_keys(self):
        _lv.BatchPutItem(self.connection, "Aaa", [{"h": unicode(i), "xs": "x" * 300000} for i in range(100)])  # 300kB items ensure a single BatchGetItem will return at most 55 items

        r1 = self.connection(_lv.BatchGetItem().table("Aaa").keys({"h": unicode(i)} for i in range(100)))
        self.assertEqual(len(r1.unprocessed_keys["Aaa"]["Keys"]), 45)
        self.assertEqual(len(r1.responses["Aaa"]), 55)


class BatchGetItemConnectedIntegTests(_tst.ConnectedIntegTestsWithTable):
    def setUp(self):
        super(BatchGetItemConnectedIntegTests, self).setUp()
        self.connection(_lv.PutItem(self.table, self.item))

    def tearDown(self):
        self.connection(_lv.DeleteItem(self.table, self.tab_key))
        super(BatchGetItemConnectedIntegTests, self).tearDown()

    def test_return_consumed_capacity_total(self):
        r = self.connection(_lv.BatchGetItem().table(self.table).keys(self.tab_key).return_consumed_capacity_total())
        with _tst.cover("r", r) as r:
            self.assertEqual(r.consumed_capacity[0].capacity_units, 0.5)
            self.assertEqual(r.consumed_capacity[0].global_secondary_indexes, None)
            self.assertEqual(r.consumed_capacity[0].local_secondary_indexes, None)
            self.assertEqual(r.consumed_capacity[0].table, None)
            self.assertEqual(r.consumed_capacity[0].table_name, self.table)
            self.assertEqual(r.responses[self.table][0], self.item)
            self.assertEqual(r.unprocessed_keys, {})
