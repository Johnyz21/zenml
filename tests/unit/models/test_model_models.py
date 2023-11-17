#  Copyright (c) ZenML GmbH 2023. All Rights Reserved.
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

from datetime import datetime
from unittest.mock import patch
from uuid import uuid4

import pytest

from tests.unit.steps.test_external_artifact import MockZenmlClient
from zenml.models.model_models import (
    ModelResponseModel,
    ModelVersionResponseModel,
)

ARTIFACT_IDS = [uuid4(), uuid4()]


@pytest.mark.parametrize(
    "artifact_object_ids,query_name,query_pipe,query_step,query_version,expected",
    (
        (
            {"foo::bar::artifact": {"1": ARTIFACT_IDS[0]}},
            "artifact",
            None,
            None,
            None,
            ARTIFACT_IDS[0],
        ),
        (
            {
                "bar::bar::artifact": {"1": ARTIFACT_IDS[0]},
                "foo::foo::artifact": {"1": ARTIFACT_IDS[1]},
            },
            "artifact",
            None,
            None,
            None,
            "RuntimeError",
        ),
        (
            {
                "bar::bar::artifact": {"1": ARTIFACT_IDS[0]},
                "foo::foo::artifact": {"1": ARTIFACT_IDS[1]},
            },
            "artifact",
            None,
            "bar",
            None,
            ARTIFACT_IDS[0],
        ),
        (
            {
                "bar::bar::artifact": {"1": ARTIFACT_IDS[0]},
                "foo::foo::artifact": {"1": ARTIFACT_IDS[1]},
            },
            "artifact",
            "bar",
            None,
            None,
            ARTIFACT_IDS[0],
        ),
        (
            {
                "bar::bar::artifact": {"1": ARTIFACT_IDS[0]},
                "foo::foo::artifact": {"1": ARTIFACT_IDS[1]},
            },
            "artifact",
            "foo",
            "foo",
            None,
            ARTIFACT_IDS[1],
        ),
        (
            {
                "foo::bar::artifact": {
                    "1": ARTIFACT_IDS[0],
                    "2": ARTIFACT_IDS[1],
                }
            },
            "artifact",
            None,
            None,
            None,
            ARTIFACT_IDS[1],
        ),
        (
            {
                "foo::bar::artifact": {
                    "1": ARTIFACT_IDS[0],
                    "2": ARTIFACT_IDS[1],
                }
            },
            "artifact",
            None,
            None,
            "1",
            ARTIFACT_IDS[0],
        ),
        (
            {},
            "artifact",
            None,
            "bar",
            None,
            None,
        ),
    ),
    ids=[
        "No collision",
        "Collision - only name",
        "Collision resolved - name+step",
        "Collision resolved - name+pipeline",
        "Collision resolved - name+step+pipeline",
        "Latest version",
        "Specific version",
        "Not found",
    ],
)
def test_getters(
    artifact_object_ids,
    query_name,
    query_pipe,
    query_step,
    query_version,
    expected,
    sample_workspace_model,
):
    """Test that the getters work as expected."""
    with patch.dict(
        "sys.modules",
        {
            "zenml.client": MockZenmlClient,
        },
    ):
        model = ModelResponseModel(
            id=uuid4(),
            name="model",
            workspace=sample_workspace_model,
            created=datetime.now(),
            updated=datetime.now(),
            tags=[],
        )
        mv = ModelVersionResponseModel(
            name="foo",
            model=model,
            number=-1,
            workspace=sample_workspace_model,
            created=datetime.now(),
            updated=datetime.now(),
            id=uuid4(),
            data_artifact_ids=artifact_object_ids,
        )
        if expected != "RuntimeError":
            got = mv.get_data_artifact(
                name=query_name,
                pipeline_name=query_pipe,
                step_name=query_step,
                version=query_version,
            )
            if got is not None:
                assert got.id == expected
            else:
                assert expected is None
        else:
            with pytest.raises(RuntimeError):
                mv.get_data_artifact(
                    name=query_name,
                    pipeline_name=query_pipe,
                    step_name=query_step,
                    version=query_version,
                )
