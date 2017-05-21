# coding: utf8

# Copyright 2014-2015 Vincent Jacques <vincent@vincent-jacques.net>

import LowVoltage as _lv
import LowVoltage.testing as _tst


class PutItemLocalIntegTests(_tst.LocalIntegTestsWithTableH):
    def test_simple_put(self):
        self.connection(_lv.PutItem("Aaa", {"h": "simple"}))

        self.assertEqual(self.connection(_lv.GetItem("Aaa", {"h": "simple"})).item, {"h": "simple"})

    def test_put_all_types(self):
        self.connection(_lv.PutItem("Aaa", {
            "h": "all",
            "number": 42,
            "string": "àoé",
            "binary": b"\xFF\x00\xFF",
            "bool 1": True,
            "bool 2": False,
            "null": None,
            "number set": set([42, 43]),
            "string set": set(["éoà", "bar"]),
            "binary set": set([b"\xFF", b"\xAB"]),
            "list": [True, 42],
            "map": {"a": True, "b": 42},
        }))

        self.assertEqual(
            self.connection(_lv.GetItem("Aaa", {"h": "all"})).item,
            {
                "h": "all",
                "number": 42,
                "string": "àoé",
                "binary": b"\xFF\x00\xFF",
                "bool 1": True,
                "bool 2": False,
                "null": None,
                "number set": set([42, 43]),
                "string set": set(["éoà", "bar"]),
                "binary set": set([b"\xFF", b"\xAB"]),
                "list": [True, 42],
                "map": {"a": True, "b": 42},
            }
        )

    def test_return_old_values(self):
        self.connection(_lv.PutItem("Aaa", {"h": "return", "a": b"yyy"}))

        r = self.connection(
            _lv.PutItem("Aaa", {"h": "return", "b": b"xxx"}).return_values_all_old()
        )

        self.assertEqual(r.attributes, {"h": "return", "a": b"yyy"})


class PutItemConnectedIntegTests(_tst.ConnectedIntegTestsWithTable):
    def tearDown(self):
        self.connection(_lv.DeleteItem(self.table, self.tab_key))
        super(PutItemConnectedIntegTests, self).tearDown()

    def test_return_consumed_capacity_indexes(self):
        r = self.connection(_lv.PutItem(self.table, self.item).return_consumed_capacity_indexes())

        self.assertEqual(r.consumed_capacity.capacity_units, 3.0)
        self.assertEqual(r.consumed_capacity.global_secondary_indexes["gsi"].capacity_units, 1.0)
        self.assertEqual(r.consumed_capacity.local_secondary_indexes["lsi"].capacity_units, 1.0)
        self.assertEqual(r.consumed_capacity.table.capacity_units, 1.0)
        self.assertEqual(r.consumed_capacity.table_name, self.table)

    def test_return_item_collection_metrics_size(self):
        r = self.connection(_lv.PutItem(self.table, self.item).return_item_collection_metrics_size())

        self.assertEqual(r.item_collection_metrics.item_collection_key, {"tab_h": "0"})
        self.assertEqual(r.item_collection_metrics.size_estimate_range_gb[0], 0.0)
        self.assertEqual(r.item_collection_metrics.size_estimate_range_gb[1], 1.0)
