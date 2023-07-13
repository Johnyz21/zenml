from typing import Any, Dict, Optional

from pydantic import BaseModel


class MlstacksSpec(BaseModel):
    """Pydantic model for stack components."""

    provider: str
    stack_name: str
    region: str
    import_stack_flag: bool = False
    mlops_platform: Optional[str] = None
    artifact_store: Optional[bool] = None
    orchestrator: Optional[str] = None
    container_registry: Optional[bool] = None
    model_deployer: Optional[str] = None
    experiment_tracker: Optional[str] = None
    secrets_manager: Optional[bool] = None
    step_operator: Optional[str] = None
    tags: Optional[Dict[str, Any]] = None
