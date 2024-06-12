import unittest
from unittest.mock import patch

import dbt.exceptions
from dbt.adapters.databricks import connections
from dbt.adapters.databricks.credentials import DatabricksCredentials
from dbt.contracts.graph import model_config
from dbt.contracts.graph import nodes


@patch("dbt.adapters.databricks.credentials.Config")
class TestDatabricksConnectionHTTPPath(unittest.TestCase):
    """Test the various cases for determining a specified warehouse."""

    errMsg = (
        "Compute resource foo does not exist or does not specify http_path, " "relation: a_relation"
    )

    def test_get_http_path_model(self, _):
        default_path = "my_http_path"
        creds = DatabricksCredentials(http_path=default_path)

        path = connections._get_http_path(None, creds)
        self.assertEqual(default_path, path)

        node = nodes.ModelNode(
            relation_name="a_relation",
            database="database",
            schema="schema",
            name="node_name",
            resource_type="model",
            package_name="package",
            path="path",
            original_file_path="orig_path",
            unique_id="uniqueID",
            fqn=[],
            alias="alias",
            checksum=None,
        )
        path = connections._get_http_path(node, creds)
        self.assertEqual(default_path, path)

        node.config = model_config.ModelConfig()
        path = connections._get_http_path(node, creds)
        self.assertEqual(default_path, path)

        node.config._extra = {}
        path = connections._get_http_path(node, creds)
        self.assertEqual(default_path, path)

        node.config._extra["databricks_compute"] = "foo"
        with self.assertRaisesRegex(
            dbt.exceptions.DbtRuntimeError,
            self.errMsg,
        ):
            connections._get_http_path(node, creds)

        creds.compute = {}
        with self.assertRaisesRegex(
            dbt.exceptions.DbtRuntimeError,
            self.errMsg,
        ):
            connections._get_http_path(node, creds)

        creds.compute = {"foo": {}}
        with self.assertRaisesRegex(
            dbt.exceptions.DbtRuntimeError,
            self.errMsg,
        ):
            connections._get_http_path(node, creds)

        creds.compute = {"foo": {"http_path": "alternate_path"}}
        path = connections._get_http_path(node, creds)
        self.assertEqual("alternate_path", path)

    def test_get_http_path_seed(self, _):
        default_path = "my_http_path"
        creds = DatabricksCredentials(http_path=default_path)

        path = connections._get_http_path(None, creds)
        self.assertEqual(default_path, path)

        node = nodes.SeedNode(
            relation_name="a_relation",
            database="database",
            schema="schema",
            name="node_name",
            resource_type="model",
            package_name="package",
            path="path",
            original_file_path="orig_path",
            unique_id="uniqueID",
            fqn=[],
            alias="alias",
            checksum=None,
        )
        path = connections._get_http_path(node, creds)
        self.assertEqual(default_path, path)

        node.config = model_config.SeedConfig()
        path = connections._get_http_path(node, creds)
        self.assertEqual(default_path, path)

        node.config._extra = {}
        path = connections._get_http_path(node, creds)
        self.assertEqual(default_path, path)

        node.config._extra["databricks_compute"] = "foo"
        with self.assertRaisesRegex(
            dbt.exceptions.DbtRuntimeError,
            self.errMsg,
        ):
            connections._get_http_path(node, creds)

        creds.compute = {}
        with self.assertRaisesRegex(
            dbt.exceptions.DbtRuntimeError,
            self.errMsg,
        ):
            connections._get_http_path(node, creds)

        creds.compute = {"foo": {}}
        with self.assertRaisesRegex(
            dbt.exceptions.DbtRuntimeError,
            self.errMsg,
        ):
            connections._get_http_path(node, creds)

        creds.compute = {"foo": {"http_path": "alternate_path"}}
        path = connections._get_http_path(node, creds)
        self.assertEqual("alternate_path", path)

    def test_get_http_path_snapshot(self, _):
        default_path = "my_http_path"
        creds = DatabricksCredentials(http_path=default_path)

        path = connections._get_http_path(None, creds)
        self.assertEqual(default_path, path)

        node = nodes.SnapshotNode(
            config=None,
            relation_name="a_relation",
            database="database",
            schema="schema",
            name="node_name",
            resource_type="model",
            package_name="package",
            path="path",
            original_file_path="orig_path",
            unique_id="uniqueID",
            fqn=[],
            alias="alias",
            checksum=None,
        )

        node.config = model_config.SnapshotConfig()
        path = connections._get_http_path(node, creds)
        self.assertEqual(default_path, path)

        node.config._extra = {}
        path = connections._get_http_path(node, creds)
        self.assertEqual(default_path, path)

        node.config._extra["databricks_compute"] = "foo"
        with self.assertRaisesRegex(
            dbt.exceptions.DbtRuntimeError,
            self.errMsg,
        ):
            connections._get_http_path(node, creds)

        creds.compute = {}
        with self.assertRaisesRegex(
            dbt.exceptions.DbtRuntimeError,
            self.errMsg,
        ):
            connections._get_http_path(node, creds)

        creds.compute = {"foo": {}}
        with self.assertRaisesRegex(
            dbt.exceptions.DbtRuntimeError,
            self.errMsg,
        ):
            connections._get_http_path(node, creds)

        creds.compute = {"foo": {"http_path": "alternate_path"}}
        path = connections._get_http_path(node, creds)
        self.assertEqual("alternate_path", path)
