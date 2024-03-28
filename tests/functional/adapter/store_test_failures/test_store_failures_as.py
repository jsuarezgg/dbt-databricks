from dbt.tests.adapter.store_test_failures_tests.basic import (
    StoreTestFailuresAsInteractions,
    StoreTestFailuresAsProjectLevelOff,
    StoreTestFailuresAsProjectLevelView,
    StoreTestFailuresAsProjectLevelEphemeral,
    StoreTestFailuresAsGeneric,
    StoreTestFailuresAsExceptions,
)
from dbt.tests.adapter.store_test_failures_tests.test_store_test_failures import (
    BaseStoreTestFailures,
)


class TestDatabricksStoreTestFailuresAsInteractions(StoreTestFailuresAsInteractions):
    pass


class TestDatabricksStoreTestFailuresAsProjectLevelOff(StoreTestFailuresAsProjectLevelOff):
    pass


class TestDatabricksStoreTestFailuresAsProjectLevelView(StoreTestFailuresAsProjectLevelView):
    pass


class TestDatabricksStoreTestFailuresAsProjectLevelEphemeral(
    StoreTestFailuresAsProjectLevelEphemeral
):
    pass


class TestDatabricksStoreTestFailuresAsGeneric(StoreTestFailuresAsGeneric):
    pass


class TestDatabricksStoreTestFailuresAsExceptions(StoreTestFailuresAsExceptions):
    pass


class TestStoreTestFailures(BaseStoreTestFailures):
    pass