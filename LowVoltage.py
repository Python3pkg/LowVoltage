import base64
import datetime
import glob
import hashlib
import hmac
import io
import json
import numbers
import os
import stat
import subprocess
import sys
import tarfile
import time
import unittest
import urlparse

import requests


class DynamoDbError(Exception):
    pass


class ServerError(DynamoDbError):
    pass


class ClientError(DynamoDbError):
    pass


class ResourceNotFoundException(ClientError):
    pass


class ValidationException(ClientError):
    pass


class Connection:
    def __init__(self, region, key, secret, endpoint=None):
        self.__region = region
        self.__key = key
        self.__secret = secret
        if endpoint is None:
            self.__endpoint = "https://dynamodb.{}.amazonaws.com/".format(region)
        else:
            self.__endpoint = endpoint
        self.__host = urlparse.urlparse(self.__endpoint).hostname
        self.__session = requests.Session()

    def request(self, operation, payload):
        headers, payload = self._sign(datetime.datetime.utcnow(), operation, payload)

        r = self.__session.post(self.__endpoint, data=payload, headers=headers)
        if r.status_code == 200:
            return r.json()
        elif r.status_code == 400:
            typ = r.json().get("__type")
            if typ.endswith("ResourceNotFoundException"):
                raise ResourceNotFoundException(r.json())
            elif typ.endswith("ValidationException"):
                raise ValidationException(r.json())
            else:
                raise ClientError(r.json())  # pragma no cover
        elif r.status_code == 500:
            raise ServerError(r.json())
        else:
            raise DynamoDbError  # pragma no cover

    def _sign(self, now, operation, payload):
        # http://docs.aws.amazon.com/general/latest/gr/sigv4-signed-request-examples.html
        timestamp = now.strftime("%Y%m%dT%H%M%SZ")
        datestamp = now.strftime("%Y%m%d")

        headers = {
            "Content-Type": "application/x-amz-json-1.0",
            "X-Amz-Date": timestamp,
            "X-Amz-Target": "DynamoDB_20120810.{}".format(operation),
            "Host": self.__host,
        }

        payload = json.dumps(payload)

        header_names = ";".join(key.lower() for key in sorted(headers.keys()))
        request = "POST\n/\n\n{}\n{}\n{}".format(
            "".join("{}:{}\n".format(key.lower(), val) for key, val in sorted(headers.iteritems())),
            header_names,
            hashlib.sha256(payload).hexdigest(),
        )
        credentials = "{}/{}/dynamodb/aws4_request".format(
            datestamp,
            self.__region,
        )
        to_sign = "AWS4-HMAC-SHA256\n{}\n{}\n{}".format(
            timestamp,
            credentials,
            hashlib.sha256(request).hexdigest(),
        )

        key = hmac.new(
            hmac.new(
                hmac.new(
                    hmac.new(
                        "AWS4{}".format(self.__secret),
                        datestamp,
                        hashlib.sha256
                    ).digest(),
                    self.__region,
                    hashlib.sha256
                ).digest(),
                "dynamodb",
                hashlib.sha256
            ).digest(),
            "aws4_request",
            hashlib.sha256
        ).digest()

        headers["Authorization"] = "AWS4-HMAC-SHA256 Credential={}/{}, SignedHeaders={}, Signature={}".format(
            self.__key,
            credentials,
            header_names,
            hmac.new(key, to_sign, hashlib.sha256).hexdigest(),
        )

        return headers, payload


class OperationBuilder:
    def _convert_dict(self, attributes):
        return {
            key: self._convert_value(val)
            for key, val in attributes.iteritems()
        }

    def _convert_value(self, value):
        if isinstance(value, basestring):
            return {"S": value}
        elif isinstance(value, numbers.Integral):
            return {"N": str(value)}
        else:
            assert len(value) > 0
            if isinstance(value[0], basestring):
                return {"SS": value}
            elif isinstance(value[0], numbers.Integral):
                return {"NS": [str(n) for n in value]}
            else:
                assert False  # pragma no cover


class UpdateItemBuilder(OperationBuilder):
    def __init__(self, table_name, key):
        self.__table_name = table_name
        self.__key = key
        self.__attribute_updates = {}
        self.__conditional_operator = None
        self.__expected = {}

    def build(self):
        data = {
            "TableName": self.__table_name,
            "Key": self._convert_dict(self.__key),
        }
        if self.__attribute_updates:
            data["AttributeUpdates"] = self.__attribute_updates
        if self.__conditional_operator:
            data["ConditionalOperator"] = self.__conditional_operator
        if self.__expected:
            data["Expected"] = self.__expected
        return data

    def put(self, name, value):
        self.__attribute_updates[name] = {"Action": "PUT", "Value": self._convert_value(value)}
        return self

    def delete(self, name, value=None):
        self.__attribute_updates[name] = {"Action": "DELETE"}
        if value is not None:
            self.__attribute_updates[name]["Value"] = self._convert_value(value)
        return self

    def add(self, name, value):
        self.__attribute_updates[name] = {"Action": "ADD", "Value": self._convert_value(value)}
        return self

    def conditional_operator(self, operator):
        self.__conditional_operator = operator
        return self

    def expect_equal(self, name, value):
        self.__expected[name] = {"ComparisonOperator": "EQ", "AttributeValueList": [self._convert_value(value)]}
        return self


class ConnectionTestCase(unittest.TestCase):
    def setUp(self):
        self.connection = Connection("us-west-2", "DummyKey", "DummySecret", "http://localhost:65432/")

    def test_sign(self):
        self.assertEqual(
            self.connection._sign(datetime.datetime(2014, 10, 4, 6, 33, 2), "Operation", {"Payload": "Value"}),
            (
                {
                    "Host": "localhost",
                    "Content-Type": "application/x-amz-json-1.0",
                    "Authorization": "AWS4-HMAC-SHA256 Credential=DummyKey/20141004/us-west-2/dynamodb/aws4_request, SignedHeaders=content-type;host;x-amz-date;x-amz-target, Signature=f47b4025d95692c1623d01bd7db6d53e68f7a8a28264c1ab3393477f0dae520a",
                    "X-Amz-Date": "20141004T063302Z",
                    "X-Amz-Target": "DynamoDB_20120810.Operation",
                },
                '{"Payload": "Value"}'
            )
        )


class UpdateItemBuilderTestCase(unittest.TestCase):
    def testStringKey(self):
        self.assertEqual(
            UpdateItemBuilder("Table", {"hash": "value"}).build(),
            {
                "TableName": "Table",
                "Key": {"hash": {"S": "value"}},
            }
        )

    def testIntKey(self):
        self.assertEqual(
            UpdateItemBuilder("Table", {"hash": 42}).build(),
            {
                "TableName": "Table",
                "Key": {"hash": {"N": "42"}},
            }
        )

    def testPutInt(self):
        self.assertEqual(
            UpdateItemBuilder("Table", {"hash": "h"}).put("attr", 42).build(),
            {
                "TableName": "Table",
                "Key": {"hash": {"S": "h"}},
                "AttributeUpdates": {"attr": {"Action": "PUT", "Value": {"N": "42"}}},
            }
        )

    def testDelete(self):
        self.assertEqual(
            UpdateItemBuilder("Table", {"hash": "h"}).delete("attr").build(),
            {
                "TableName": "Table",
                "Key": {"hash": {"S": "h"}},
                "AttributeUpdates": {"attr": {"Action": "DELETE"}},
            }
        )

    def testAddInt(self):
        self.assertEqual(
            UpdateItemBuilder("Table", {"hash": "h"}).add("attr", 42).build(),
            {
                "TableName": "Table",
                "Key": {"hash": {"S": "h"}},
                "AttributeUpdates": {"attr": {"Action": "ADD", "Value": {"N": "42"}}},
            }
        )

    def testDeleteSetOfInts(self):
        self.assertEqual(
            UpdateItemBuilder("Table", {"hash": "h"}).delete("attr", [42, 43]).build(),
            {
                "TableName": "Table",
                "Key": {"hash": {"S": "h"}},
                "AttributeUpdates": {"attr": {"Action": "DELETE", "Value": {"NS": ["42", "43"]}}},
            }
        )

    def testAddSetOfStrings(self):
        self.assertEqual(
            UpdateItemBuilder("Table", {"hash": "h"}).add("attr", ["42", "43"]).build(),
            {
                "TableName": "Table",
                "Key": {"hash": {"S": "h"}},
                "AttributeUpdates": {"attr": {"Action": "ADD", "Value": {"SS": ["42", "43"]}}},
            }
        )

    def testConditionalOperator(self):
        self.assertEqual(
            UpdateItemBuilder("Table", {"hash": "h"}).conditional_operator("AND").build(),
            {
                "TableName": "Table",
                "Key": {"hash": {"S": "h"}},
                "ConditionalOperator": "AND",
            }
        )

    def testExpectEqual(self):
        self.assertEqual(
            UpdateItemBuilder("Table", {"hash": "h"}).expect_equal("attr", 42).build(),
            {
                "TableName": "Table",
                "Key": {"hash": {"S": "h"}},
                "Expected": {"attr": {"ComparisonOperator": "EQ", "AttributeValueList": [{"N": "42"}]}},
            }
        )


class RealIntegrationTestCase(unittest.TestCase):
    def setUp(self):
        import AwsCredentials
        self.connection = Connection(AwsCredentials.region, AwsCredentials.key, AwsCredentials.secret)

    def testCreateDeleteTable(self):
        create = self.connection.request(
            "CreateTable",
            dict(
                TableName="LowVoltage.CreateDeleteTable",
                AttributeDefinitions=[dict(AttributeName="the_hash", AttributeType="S")],
                KeySchema=[dict(AttributeName="the_hash", KeyType="HASH")],
                ProvisionedThroughput=dict(ReadCapacityUnits=1, WriteCapacityUnits=1),
            )
        )

        status = create["TableDescription"]["TableStatus"]
        while status == "CREATING":
            time.sleep(5)
            status = self.connection.request(
                "DescribeTable",
                {"TableName": "LowVoltage.CreateDeleteTable"}
            )["Table"]["TableStatus"]

        delete = self.connection.request(
            "DeleteTable",
            {
                "TableName": "LowVoltage.CreateDeleteTable",
            }
        )

        del create["TableDescription"]["CreationDateTime"]
        self.assertEqual(
            create,
            {
                "TableDescription": {
                    "AttributeDefinitions": [
                        {
                            "AttributeName": "the_hash",
                            "AttributeType": "S",
                        },
                    ],
                    # "CreationDateTime": 1.412395289605E9,
                    "ItemCount": 0,
                    "KeySchema": [
                        {
                            "AttributeName": "the_hash",
                            "KeyType": "HASH",
                        }
                    ],
                    "ProvisionedThroughput": {
                        "NumberOfDecreasesToday": 0,
                        "ReadCapacityUnits": 1,
                        "WriteCapacityUnits": 1
                    },
                    "TableName": "LowVoltage.CreateDeleteTable",
                    "TableSizeBytes": 0,
                    "TableStatus": "CREATING"
                }
            }
        )

        self.assertEqual(
            delete,
            {
                "TableDescription": {
                    "ItemCount": 0,
                    "ProvisionedThroughput": {
                        "NumberOfDecreasesToday": 0,
                        "ReadCapacityUnits": 1,
                        "WriteCapacityUnits": 1
                    },
                    "TableName": "LowVoltage.CreateDeleteTable",
                    "TableSizeBytes": 0,
                    "TableStatus": "DELETING"
                }
            }
        )


class LocalIntegrationTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not os.path.exists(".dynamodblocal/DynamoDBLocal.jar"):
            archive = requests.get("http://dynamodb-local.s3-website-us-west-2.amazonaws.com/dynamodb_local_latest").content  # pragma no cover
            tarfile.open(fileobj=io.BytesIO(archive)).extractall(".dynamodblocal")  # pragma no cover
            # Fix permissions, needed at least when running with Cygwin's Python
            for f in glob.glob(".dynamodblocal/DynamoDBLocal_lib/*"):  # pragma no cover
                os.chmod(f, stat.S_IRUSR|stat.S_IWUSR|stat.S_IXUSR)  # pragma no cover

        cls.dynamodblocal = subprocess.Popen(
            ["java", "-Djava.library.path=./DynamoDBLocal_lib", "-jar", "DynamoDBLocal.jar", "-inMemory", "-port", "65432"],
            cwd=".dynamodblocal",
            stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )

        time.sleep(1)
        assert cls.dynamodblocal.poll() is None

        connection = Connection("us-west-2", "DummyKey", "DummySecret", "http://localhost:65432/")
        connection.request(
            "CreateTable",
            dict(
                TableName="TableWithHash",
                AttributeDefinitions=[dict(AttributeName="hash", AttributeType="S")],
                KeySchema=[dict(AttributeName="hash", KeyType="HASH")],
                ProvisionedThroughput=dict(ReadCapacityUnits=1, WriteCapacityUnits=1),
            )
        )

    @classmethod
    def tearDownClass(cls):
        cls.dynamodblocal.kill()

    def setUp(self):
        self.connection = Connection("us-west-2", "DummyKey", "DummySecret", "http://localhost:65432/")

    def testResourceNotFoundException(self):
        with self.assertRaises(ResourceNotFoundException):
            self.connection.request(
                "DescribeTable",
                {"TableName": "UnexistingTable"}
            )

    def testServerError(self):
        # DynamoDBLocal is not as robust as the real one. This is useful for our test coverage :)
        with self.assertRaises(ServerError):
            self.connection.request(
                "PutItem",
                {
                    "TableName": "TableWithHash",
                    "Item": {"hash": 42}
                }
            )

    def testValidationException(self):
        with self.assertRaises(ValidationException):
            self.connection.request(
                "PutItem",
                {
                    "TableName": "TableWithHash",
                }
            )


if __name__ == "__main__":  # pragma no branch
    unittest.main()
