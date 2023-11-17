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
"""Endpoint definitions for pipelines."""
from uuid import UUID

from fastapi import APIRouter, Depends, Security

from zenml.config.pipeline_spec import PipelineSpec
from zenml.constants import API, PIPELINE_SPEC, PIPELINES, RUNS, VERSION_1
from zenml.enums import PermissionType
from zenml.models import (
    Page,
    PipelineFilter,
    PipelineResponse,
    PipelineRunFilter,
    PipelineRunResponse,
    PipelineUpdate,
)
from zenml.zen_server.auth import AuthContext, authorize
from zenml.zen_server.exceptions import error_response
from zenml.zen_server.utils import (
    handle_exceptions,
    make_dependable,
    zen_store,
)

router = APIRouter(
    prefix=API + VERSION_1 + PIPELINES,
    tags=["pipelines"],
    responses={401: error_response},
)


@router.get(
    "",
    response_model=Page[PipelineResponse],
    responses={401: error_response, 404: error_response, 422: error_response},
)
@handle_exceptions
def list_pipelines(
    pipeline_filter_model: PipelineFilter = Depends(
        make_dependable(PipelineFilter)
    ),
    hydrate: bool = False,
    _: AuthContext = Security(authorize, scopes=[PermissionType.READ]),
) -> Page[PipelineResponse]:
    """Gets a list of pipelines.

    Args:
        pipeline_filter_model: Filter model used for pagination, sorting,
            filtering.
        hydrate: Flag deciding whether to hydrate the output model(s)
            by including metadata fields in the response.

    Returns:
        List of pipeline objects.
    """
    return zen_store().list_pipelines(
        pipeline_filter_model=pipeline_filter_model, hydrate=hydrate
    )


@router.get(
    "/{pipeline_id}",
    response_model=PipelineResponse,
    responses={401: error_response, 404: error_response, 422: error_response},
)
@handle_exceptions
def get_pipeline(
    pipeline_id: UUID,
    hydrate: bool = True,
    _: AuthContext = Security(authorize, scopes=[PermissionType.READ]),
) -> PipelineResponse:
    """Gets a specific pipeline using its unique id.

    Args:
        pipeline_id: ID of the pipeline to get.
        hydrate: Flag deciding whether to hydrate the output model(s)
            by including metadata fields in the response.

    Returns:
        A specific pipeline object.
    """
    return zen_store().get_pipeline(pipeline_id=pipeline_id, hydrate=hydrate)


@router.put(
    "/{pipeline_id}",
    response_model=PipelineResponse,
    responses={401: error_response, 404: error_response, 422: error_response},
)
@handle_exceptions
def update_pipeline(
    pipeline_id: UUID,
    pipeline_update: PipelineUpdate,
    _: AuthContext = Security(authorize, scopes=[PermissionType.WRITE]),
) -> PipelineResponse:
    """Updates the attribute on a specific pipeline using its unique id.

    Args:
        pipeline_id: ID of the pipeline to get.
        pipeline_update: the model containing the attributes to update.

    Returns:
        The updated pipeline object.
    """
    return zen_store().update_pipeline(
        pipeline_id=pipeline_id, pipeline_update=pipeline_update
    )


@router.delete(
    "/{pipeline_id}",
    responses={401: error_response, 404: error_response, 422: error_response},
)
@handle_exceptions
def delete_pipeline(
    pipeline_id: UUID,
    _: AuthContext = Security(authorize, scopes=[PermissionType.WRITE]),
) -> None:
    """Deletes a specific pipeline.

    Args:
        pipeline_id: ID of the pipeline to delete.
    """
    zen_store().delete_pipeline(pipeline_id=pipeline_id)


@router.get(
    "/{pipeline_id}" + RUNS,
    response_model=Page[PipelineRunResponse],
    responses={401: error_response, 404: error_response, 422: error_response},
)
@handle_exceptions
def list_pipeline_runs(
    pipeline_run_filter_model: PipelineRunFilter = Depends(
        make_dependable(PipelineRunFilter)
    ),
    hydrate: bool = False,
    _: AuthContext = Security(authorize, scopes=[PermissionType.READ]),
) -> Page[PipelineRunResponse]:
    """Get pipeline runs according to query filters.

    Args:
        pipeline_run_filter_model: Filter model used for pagination, sorting,
            filtering
        hydrate: Flag deciding whether to hydrate the output model(s)
            by including metadata fields in the response.

    Returns:
        The pipeline runs according to query filters.
    """
    return zen_store().list_runs(pipeline_run_filter_model)


@router.get(
    "/{pipeline_id}" + PIPELINE_SPEC,
    response_model=PipelineSpec,
    responses={401: error_response, 404: error_response, 422: error_response},
)
@handle_exceptions
def get_pipeline_spec(
    pipeline_id: UUID,
    _: AuthContext = Security(authorize, scopes=[PermissionType.READ]),
) -> PipelineSpec:
    """Gets the spec of a specific pipeline using its unique id.

    Args:
        pipeline_id: ID of the pipeline to get.

    Returns:
        The spec of the pipeline.
    """
    return zen_store().get_pipeline(pipeline_id).spec
