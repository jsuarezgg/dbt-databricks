import itertools
import json
import os
import re
import threading
from dataclasses import dataclass
from typing import Any
from typing import Callable
from typing import cast
from typing import Dict
from typing import Iterable
from typing import List
from typing import Optional
from typing import Tuple

from databricks.sdk import WorkspaceClient
from databricks.sdk.core import Config
from databricks.sdk.credentials_provider import HeaderFactory
from dbt.adapters.contracts.connection import Credentials
from dbt.adapters.databricks import auth
from dbt_common.exceptions import DbtConfigError
from dbt_common.exceptions import DbtValidationError
from mashumaro import DataClassDictMixin
from requests import PreparedRequest
from requests.auth import AuthBase

CATALOG_KEY_IN_SESSION_PROPERTIES = "databricks.catalog"
DBT_DATABRICKS_INVOCATION_ENV = "DBT_DATABRICKS_INVOCATION_ENV"
DBT_DATABRICKS_INVOCATION_ENV_REGEX = re.compile("^[A-z0-9\\-]+$")
EXTRACT_CLUSTER_ID_FROM_HTTP_PATH_REGEX = re.compile(r"/?sql/protocolv1/o/\d+/(.*)")
DBT_DATABRICKS_HTTP_SESSION_HEADERS = "DBT_DATABRICKS_HTTP_SESSION_HEADERS"

REDIRECT_URL = "http://localhost:8020"
CLIENT_ID = "dbt-databricks"
SCOPES = ["all-apis", "offline_access"]
MAX_NT_PASSWORD_SIZE = 1280


@dataclass
class DatabricksCredentials(Credentials):
    database: Optional[str] = None  # type: ignore[assignment]
    schema: Optional[str] = None  # type: ignore[assignment]
    host: Optional[str] = None
    http_path: Optional[str] = None
    token: Optional[str] = None
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    oauth_redirect_url: Optional[str] = None
    oauth_scopes: Optional[List[str]] = None
    session_properties: Optional[Dict[str, Any]] = None
    connection_parameters: Optional[Dict[str, Any]] = None
    auth_type: Optional[str] = None

    # Named compute resources specified in the profile. Used for
    # creating a connection when a model specifies a compute resource.
    compute: Optional[Dict[str, Any]] = None

    connect_retries: int = 1
    connect_timeout: Optional[int] = None
    retry_all: bool = False
    connect_max_idle: Optional[int] = None

    _credentials_manager: Optional["DatabricksCredentialManager"] = None
    _lock = threading.Lock()  # to avoid concurrent auth

    _ALIASES = {
        "catalog": "database",
        "target_catalog": "target_database",
    }

    @classmethod
    def __pre_deserialize__(cls, data: Dict[Any, Any]) -> Dict[Any, Any]:
        data = super().__pre_deserialize__(data)
        if "database" not in data:
            data["database"] = None
        return data

    def __post_init__(self) -> None:
        if "." in (self.schema or ""):
            raise DbtValidationError(
                f"The schema should not contain '.': {self.schema}\n"
                "If you are trying to set a catalog, please use `catalog` instead.\n"
            )

        session_properties = self.session_properties or {}
        if CATALOG_KEY_IN_SESSION_PROPERTIES in session_properties:
            if self.database is None:
                self.database = session_properties[CATALOG_KEY_IN_SESSION_PROPERTIES]
                del session_properties[CATALOG_KEY_IN_SESSION_PROPERTIES]
            else:
                raise DbtValidationError(
                    f"Got duplicate keys: (`{CATALOG_KEY_IN_SESSION_PROPERTIES}` "
                    'in session_properties) all map to "database"'
                )
        self.session_properties = session_properties

        if self.database is not None:
            database = self.database.strip()
            if not database:
                raise DbtValidationError(f"Invalid catalog name : `{self.database}`.")
            self.database = database
        else:
            self.database = "hive_metastore"

        connection_parameters = self.connection_parameters or {}
        for key in (
            "server_hostname",
            "http_path",
            "access_token",
            "client_id",
            "client_secret",
            "session_configuration",
            "catalog",
            "schema",
            "_user_agent_entry",
        ):
            if key in connection_parameters:
                raise DbtValidationError(f"The connection parameter `{key}` is reserved.")
        if "http_headers" in connection_parameters:
            http_headers = connection_parameters["http_headers"]
            if not isinstance(http_headers, dict) or any(
                not isinstance(key, str) or not isinstance(value, str)
                for key, value in http_headers.items()
            ):
                raise DbtValidationError(
                    "The connection parameter `http_headers` should be dict of strings: "
                    f"{http_headers}."
                )
        if "_socket_timeout" not in connection_parameters:
            connection_parameters["_socket_timeout"] = 600
        self.connection_parameters = connection_parameters
        self._credentials_manager = DatabricksCredentialManager.create_from(self)

    def validate_creds(self) -> None:
        for key in ["host", "http_path"]:
            if not getattr(self, key):
                raise DbtConfigError(
                    "The config '{}' is required to connect to Databricks".format(key)
                )
        if not self.token and self.auth_type != "oauth":
            raise DbtConfigError(
                ("The config `auth_type: oauth` is required when not using access token")
            )

        if not self.client_id and self.client_secret:
            raise DbtConfigError(
                (
                    "The config 'client_id' is required to connect "
                    "to Databricks when 'client_secret' is present"
                )
            )

    @classmethod
    def get_invocation_env(cls) -> Optional[str]:
        invocation_env = os.environ.get(DBT_DATABRICKS_INVOCATION_ENV)
        if invocation_env:
            # Thrift doesn't allow nested () so we need to ensure
            # that the passed user agent is valid.
            if not DBT_DATABRICKS_INVOCATION_ENV_REGEX.search(invocation_env):
                raise DbtValidationError(f"Invalid invocation environment: {invocation_env}")
        return invocation_env

    @classmethod
    def get_all_http_headers(cls, user_http_session_headers: Dict[str, str]) -> Dict[str, str]:
        http_session_headers_str: Optional[str] = os.environ.get(
            DBT_DATABRICKS_HTTP_SESSION_HEADERS
        )

        http_session_headers_dict: Dict[str, str] = (
            {
                k: v if isinstance(v, str) else json.dumps(v)
                for k, v in json.loads(http_session_headers_str).items()
            }
            if http_session_headers_str is not None
            else {}
        )

        intersect_http_header_keys = (
            user_http_session_headers.keys() & http_session_headers_dict.keys()
        )

        if len(intersect_http_header_keys) > 0:
            raise DbtValidationError(
                f"Intersection with reserved http_headers in keys: {intersect_http_header_keys}"
            )

        http_session_headers_dict.update(user_http_session_headers)

        return http_session_headers_dict

    @property
    def type(self) -> str:
        return "databricks"

    @property
    def unique_field(self) -> str:
        return cast(str, self.host)

    def connection_info(self, *, with_aliases: bool = False) -> Iterable[Tuple[str, Any]]:
        as_dict = self.to_dict(omit_none=False)
        connection_keys = set(self._connection_keys(with_aliases=with_aliases))
        aliases: List[str] = []
        if with_aliases:
            aliases = [k for k, v in self._ALIASES.items() if v in connection_keys]
        for key in itertools.chain(self._connection_keys(with_aliases=with_aliases), aliases):
            if key in as_dict:
                yield key, as_dict[key]

    def _connection_keys(self, *, with_aliases: bool = False) -> Tuple[str, ...]:
        # Assuming `DatabricksCredentials.connection_info(self, *, with_aliases: bool = False)`
        # is called from only:
        #
        # - `Profile` with `with_aliases=True`
        # - `DebugTask` without `with_aliases` (`False` by default)
        #
        # Thus, if `with_aliases` is `True`, `DatabricksCredentials._connection_keys` should return
        # the internal key names; otherwise it can use aliases to show in `dbt debug`.
        connection_keys = ["host", "http_path", "schema"]
        if with_aliases:
            connection_keys.insert(2, "database")
        elif self.database:
            connection_keys.insert(2, "catalog")
        if self.session_properties:
            connection_keys.append("session_properties")
        return tuple(connection_keys)

    @classmethod
    def extract_cluster_id(cls, http_path: str) -> Optional[str]:
        m = EXTRACT_CLUSTER_ID_FROM_HTTP_PATH_REGEX.match(http_path)
        if m:
            return m.group(1).strip()
        else:
            return None

    @property
    def cluster_id(self) -> Optional[str]:
        return self.extract_cluster_id(self.http_path)  # type: ignore[arg-type]

    def authenticate(self) -> "DatabricksCredentialManager":
        self.validate_creds()
        assert self._credentials_manager is not None, "Credentials manager is not set."
        return self._credentials_manager


class BearerAuth(AuthBase):
    """This mix-in is passed to our requests Session to explicitly
    use the bearer authentication method.

    Without this, a local .netrc file in the user's home directory
    will override the auth headers provided by our header_factory.

    More details in issue #337.
    """

    def __init__(self, header_factory: HeaderFactory):
        self.header_factory = header_factory

    def __call__(self, r: PreparedRequest) -> PreparedRequest:
        r.headers.update(**self.header_factory())
        return r


PySQLCredentialProvider = Callable[[], Callable[[], Dict[str, str]]]


@dataclass
class DatabricksCredentialManager(DataClassDictMixin):
    host: str
    client_id: str
    client_secret: str
    token: Optional[str] = None

    @classmethod
    def create_from(cls, credentials: DatabricksCredentials) -> "DatabricksCredentialManager":
        return DatabricksCredentialManager(
            host=credentials.host or "",
            token=credentials.token,
            client_id=credentials.client_id or "",
            client_secret=credentials.client_secret or "",
        )

    def __post_init__(self) -> None:
        self._config = Config(
            credentials_provider=auth.m2m_auth(self.host, self.client_id, self.client_secret)
        )

    @property
    def api_client(self) -> WorkspaceClient:
        return WorkspaceClient(config=self._config)

    @property
    def credentials_provider(self) -> PySQLCredentialProvider:
        def inner() -> Callable[[], Dict[str, str]]:
            return self.header_factory

        return inner

    @property
    def header_factory(self) -> HeaderFactory:
        header_factory = self._config._header_factory
        assert header_factory is not None, "Header factory is not set."
        return header_factory

    @property
    def config(self) -> Config:
        return self._config
