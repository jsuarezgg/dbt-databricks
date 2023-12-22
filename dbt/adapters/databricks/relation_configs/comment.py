from typing import Optional, ClassVar
from dbt.contracts.graph.nodes import ModelNode

from dbt.adapters.databricks.relation_configs.base import (
    DatabricksComponentConfig,
    DatabricksComponentProcessor,
)
from dbt.adapters.relation_configs.config_base import RelationResults


class CommentConfig(DatabricksComponentConfig):
    comment: Optional[str] = None

    @property
    def requires_full_refresh(self) -> bool:
        return True


class CommentProcessor(DatabricksComponentProcessor[CommentConfig]):
    name: ClassVar[str] = "comment"

    @classmethod
    def from_results(cls, results: RelationResults) -> CommentConfig:
        table = results["describe_extended"]
        for row in table.rows:
            if row[0] == "Comment":
                return CommentConfig(comment=row[1])
        return CommentConfig()

    @classmethod
    def from_model_node(cls, model_node: ModelNode) -> CommentConfig:
        if model_node.description is not None:
            return CommentConfig(comment=model_node.description)
        return CommentConfig()
