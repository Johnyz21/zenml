#  Copyright (c) ZenML GmbH 2022. All Rights Reserved.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at:
#
#       https://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express
#  or implied. See the License for the specific language governing
#  permissions and limitations under the License.
"""Utilities for inputs."""

from typing import TYPE_CHECKING, Dict, List, Optional, Tuple
from uuid import UUID

from zenml.client import Client
from zenml.config.step_configurations import Step
from zenml.exceptions import InputResolutionError
from zenml.models import StepRunFilter

if TYPE_CHECKING:
    from zenml.model.model_version import ModelVersion
    from zenml.models import ArtifactResponse


def resolve_step_inputs(
    step: "Step",
    run_id: UUID,
    model_version: Optional["ModelVersion"] = None,
) -> Tuple[Dict[str, "ArtifactResponse"], List[UUID]]:
    """Resolves inputs for the current step.

    Args:
        step: The step for which to resolve the inputs.
        run_id: The ID of the current pipeline run.
        model_version: The model version of the step (from step or pipeline).

    Raises:
        InputResolutionError: If input resolving failed due to a missing
            step or output.

    Returns:
        The IDs of the input artifacts and the IDs of parent steps of the
        current step.
    """
    current_run_steps = {
        run_step.name: run_step
        for run_step in Client()
        .zen_store.list_run_steps(StepRunFilter(pipeline_run_id=run_id))
        .items
    }

    input_artifacts: Dict[str, "ArtifactResponse"] = {}
    for name, input_ in step.spec.inputs.items():
        try:
            step_run = current_run_steps[input_.step_name]
        except KeyError:
            raise InputResolutionError(
                f"No step `{input_.step_name}` found in current run."
            )

        try:
            artifact = step_run.outputs[input_.output_name]
        except KeyError:
            raise InputResolutionError(
                f"No output `{input_.output_name}` found for step "
                f"`{input_.step_name}`."
            )

        input_artifacts[name] = artifact

    for (
        name,
        external_artifact,
    ) in step.config.external_input_artifacts.items():
        artifact_id = external_artifact.get_artifact_id(
            model_version=model_version
        )
        input_artifacts[name] = Client().get_artifact(artifact_id=artifact_id)

    parent_step_ids = [
        current_run_steps[upstream_step].id
        for upstream_step in step.spec.upstream_steps
    ]

    return input_artifacts, parent_step_ids
