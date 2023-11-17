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

from typing import Tuple
from unittest import mock
from uuid import uuid4

import pytest
from tests.integration.functional.utils import model_killer
from typing_extensions import Annotated

from zenml import get_step_context, pipeline, step
from zenml.artifacts.external_artifact import ExternalArtifact
from zenml.client import Client
from zenml.enums import ModelStages
from zenml.model import DataArtifactConfig, ModelVersion, link_output_to_model


@step
def _assert_that_model_version_set(name="foo"):
    """Step asserting that passed model name and version is in model context."""
    assert get_step_context().model_version.name == name
    assert get_step_context().model_version.version == "1"


def test_model_version_passed_to_step_context_via_step():
    """Test that model version was passed to step context via step."""

    @pipeline(name="bar", enable_cache=False)
    def _simple_step_pipeline():
        _assert_that_model_version_set.with_options(
            model_version=ModelVersion(name="foo"),
        )()

    with model_killer():
        _simple_step_pipeline()


def test_model_version_passed_to_step_context_via_pipeline():
    """Test that model version was passed to step context via pipeline."""

    @pipeline(
        name="bar",
        model_version=ModelVersion(name="foo"),
        enable_cache=False,
    )
    def _simple_step_pipeline():
        _assert_that_model_version_set()

    with model_killer():
        _simple_step_pipeline()


def test_model_version_passed_to_step_context_via_step_and_pipeline():
    """Test that model version was passed to step context via both, but step is dominating."""

    @pipeline(
        name="bar",
        model_version=ModelVersion(name="bar"),
        enable_cache=False,
    )
    def _simple_step_pipeline():
        _assert_that_model_version_set.with_options(
            model_version=ModelVersion(name="foo"),
        )()

    with model_killer():
        _simple_step_pipeline()


def test_model_version_passed_to_step_context_and_switches():
    """Test that model version was passed to step context via both and switches possible."""

    @pipeline(
        name="bar",
        model_version=ModelVersion(name="bar"),
        enable_cache=False,
    )
    def _simple_step_pipeline():
        # this step will use ModelVersion from itself
        _assert_that_model_version_set.with_options(
            model_version=ModelVersion(name="foo"),
        )()
        # this step will use ModelVersion from pipeline
        _assert_that_model_version_set(name="bar")
        # and another switch of context
        _assert_that_model_version_set.with_options(
            model_version=ModelVersion(name="foobar"),
        )(name="foobar")

    with model_killer():
        _simple_step_pipeline()


@step(model_version=ModelVersion(name="foo"))
def _this_step_creates_a_version():
    return 1


@step
def _this_step_does_not_create_a_version():
    return 1


def test_create_new_versions_both_pipeline_and_step():
    """Test that model version on step and pipeline levels can create new model versions at the same time."""
    desc = "Should be the best version ever!"

    @pipeline(
        name="bar",
        model_version=ModelVersion(name="bar", description=desc),
        enable_cache=False,
    )
    def _this_pipeline_creates_a_version():
        _this_step_creates_a_version()
        _this_step_does_not_create_a_version()

    with model_killer():
        client = Client()

        _this_pipeline_creates_a_version()

        foo = client.get_model("foo")
        assert foo.name == "foo"
        foo_version = client.get_model_version("foo", ModelStages.LATEST)
        assert foo_version.number == 1

        bar = client.get_model("bar")
        assert bar.name == "bar"
        bar_version = client.get_model_version("bar", ModelStages.LATEST)
        assert bar_version.number == 1
        assert bar_version.description == desc

        _this_pipeline_creates_a_version()

        foo_version = client.get_model_version("foo", ModelStages.LATEST)
        assert foo_version.number == 2

        bar_version = client.get_model_version("bar", ModelStages.LATEST)
        assert foo_version.number == 2
        assert bar_version.description == desc


def test_create_new_version_only_in_step():
    """Test that model version on step level only can create new model version."""

    @pipeline(name="bar", enable_cache=False)
    def _this_pipeline_does_not_create_a_version():
        _this_step_creates_a_version()
        _this_step_does_not_create_a_version()

    with model_killer():
        client = Client()

        _this_pipeline_does_not_create_a_version()

        bar = client.get_model("foo")
        assert bar.name == "foo"
        bar_version = client.get_model_version("foo", ModelStages.LATEST)
        assert bar_version.number == 1

        _this_pipeline_does_not_create_a_version()

        bar_version = client.get_model_version("foo", ModelStages.LATEST)
        assert bar_version.number == 2


def test_create_new_version_only_in_pipeline():
    """Test that model version on pipeline level only can create new model version."""

    @pipeline(
        name="bar",
        model_version=ModelVersion(name="bar"),
        enable_cache=False,
    )
    def _this_pipeline_creates_a_version():
        _this_step_does_not_create_a_version()

    with model_killer():
        client = Client()

        _this_pipeline_creates_a_version()

        foo = client.get_model("bar")
        assert foo.name == "bar"
        foo_version = client.get_model_version("bar", ModelStages.LATEST)
        assert foo_version.number == 1

        _this_pipeline_creates_a_version()

        foo_version = client.get_model_version("bar", ModelStages.LATEST)
        assert foo_version.number == 2


@step
def _this_step_produces_output() -> (
    Annotated[int, "data", DataArtifactConfig(overwrite=False)]
):
    return 1


@step
def _this_step_tries_to_recover(run_number: int):
    mv = get_step_context().model_version._get_or_create_model_version()
    assert (
        len(mv.data_artifact_ids["bar::_this_step_produces_output::data"])
        == run_number
    ), "expected AssertionError"

    raise Exception("make pipeline fail")


@pytest.mark.parametrize(
    "model_version",
    [
        ModelVersion(
            name="foo",
        ),
        ModelVersion(
            name="foo",
            version="test running version",
        ),
    ],
    ids=["default_running_name", "custom_running_name"],
)
def test_recovery_of_steps(model_version: ModelVersion):
    """Test that model version can recover states after previous fails."""

    @pipeline(
        name="bar",
        enable_cache=False,
    )
    def _this_pipeline_will_recover(run_number: int):
        _this_step_produces_output()
        _this_step_tries_to_recover(
            run_number, after=["_this_step_produces_output"]
        )

    with model_killer():
        client = Client()

        with pytest.raises(Exception, match="make pipeline fail"):
            _this_pipeline_will_recover.with_options(
                model_version=model_version
            )(1)
        if model_version.version is None:
            model_version.version = "1"
        with pytest.raises(Exception, match="make pipeline fail"):
            _this_pipeline_will_recover.with_options(
                model_version=model_version
            )(2)
        with pytest.raises(Exception, match="make pipeline fail"):
            _this_pipeline_will_recover.with_options(
                model_version=model_version
            )(3)

        mv = client.get_model_version(
            model_name_or_id="foo",
            model_version_name_or_number_or_id=model_version.version,
        )
        mv = client.zen_store.get_model_version(mv.id)
        assert mv.name == model_version.version
        assert len(mv.data_artifact_ids) == 1
        assert (
            len(mv.data_artifact_ids["bar::_this_step_produces_output::data"])
            == 3
        )


@step(model_version=ModelVersion(name="foo"))
def _new_version_step():
    return 1


@step
def _no_model_version_step():
    return 1


@pipeline(
    enable_cache=False,
    model_version=ModelVersion(name="foo"),
)
def _new_version_pipeline_overridden_warns():
    _new_version_step()


@pipeline(
    enable_cache=False,
    model_version=ModelVersion(name="foo"),
)
def _new_version_pipeline_not_warns():
    _no_model_version_step()


@pipeline(enable_cache=False)
def _no_new_version_pipeline_not_warns():
    _new_version_step()


@pipeline(enable_cache=False)
def _no_new_version_pipeline_warns_on_steps():
    _new_version_step()
    _new_version_step()


@pipeline(
    enable_cache=False,
    model_version=ModelVersion(name="foo"),
)
def _new_version_pipeline_warns_on_steps():
    _new_version_step()
    _no_model_version_step()


@pytest.mark.parametrize(
    "pipeline, expected_warning",
    [
        (
            _new_version_pipeline_overridden_warns,
            "is overridden in all steps",
        ),
        (_new_version_pipeline_not_warns, ""),
        (_no_new_version_pipeline_not_warns, ""),
        (
            _no_new_version_pipeline_warns_on_steps,
            "is configured only in one place of the pipeline",
        ),
        (
            _new_version_pipeline_warns_on_steps,
            "is configured only in one place of the pipeline",
        ),
    ],
    ids=[
        "Pipeline with one step, which overrides model_version - warns that pipeline conf is useless.",
        "Configuration in pipeline only - not warns.",
        "Configuration in step only - not warns.",
        "Two steps ask to create new versions - warning to keep it in one place.",
        "Pipeline and one of the steps ask to create new versions - warning to keep it in one place.",
    ],
)
def test_multiple_definitions_create_new_version_warns(
    pipeline, expected_warning
):
    """Test that setting conflicting model versions are raise warnings to user."""
    with model_killer():
        with mock.patch(
            "zenml.new.pipelines.pipeline.logger.warning"
        ) as logger:
            pipeline()
            if expected_warning:
                logger.assert_called_once()
                assert expected_warning in logger.call_args[0][0]
            else:
                logger.assert_not_called()


@pipeline(name="bar", enable_cache=False)
def _pipeline_run_link_attached_from_pipeline_context_single_step():
    _this_step_produces_output()


@pipeline(name="bar", enable_cache=False)
def _pipeline_run_link_attached_from_pipeline_context_multiple_steps():
    _this_step_produces_output()
    _this_step_produces_output()


@pytest.mark.parametrize(
    "pipeline",
    (
        _pipeline_run_link_attached_from_pipeline_context_single_step,
        _pipeline_run_link_attached_from_pipeline_context_multiple_steps,
    ),
    ids=["Single step pipeline", "Multiple steps pipeline"],
)
def test_pipeline_run_link_attached_from_pipeline_context(pipeline):
    """Tests that current pipeline run information is attached to model version by pipeline context."""
    with model_killer():
        client = Client()

        run_name_1 = f"bar_run_{uuid4()}"
        pipeline.with_options(
            run_name=run_name_1,
            model_version=ModelVersion(
                name="foo",
            ),
        )()
        run_name_2 = f"bar_run_{uuid4()}"
        pipeline.with_options(
            run_name=run_name_2,
            model_version=ModelVersion(name="foo", version=ModelStages.LATEST),
        )()

        mv = client.get_model_version(
            model_name_or_id="foo",
            model_version_name_or_number_or_id=ModelStages.LATEST,
        )
        mv = client.zen_store.get_model_version(mv.id)

        assert len(mv.pipeline_run_ids) == 2
        assert {run_name for run_name in mv.pipeline_run_ids} == {
            run_name_1,
            run_name_2,
        }


@pipeline(name="bar", enable_cache=False)
def _pipeline_run_link_attached_from_step_context_single_step(
    mv: ModelVersion,
):
    _this_step_produces_output.with_options(model_version=mv)()


@pipeline(name="bar", enable_cache=False)
def _pipeline_run_link_attached_from_step_context_multiple_step(
    mv: ModelVersion,
):
    _this_step_produces_output.with_options(model_version=mv)()
    _this_step_produces_output.with_options(model_version=mv)()


@pytest.mark.parametrize(
    "pipeline",
    (
        _pipeline_run_link_attached_from_step_context_single_step,
        _pipeline_run_link_attached_from_step_context_multiple_step,
    ),
    ids=["Single step pipeline", "Multiple steps pipeline"],
)
def test_pipeline_run_link_attached_from_step_context(pipeline):
    """Tests that current pipeline run information is attached to model version by step context."""
    with model_killer():
        client = Client()

        run_name_1 = f"bar_run_{uuid4()}"
        pipeline.with_options(
            run_name=run_name_1,
        )(
            ModelVersion(
                name="foo",
            )
        )
        run_name_2 = f"bar_run_{uuid4()}"
        pipeline.with_options(
            run_name=run_name_2,
        )(ModelVersion(name="foo", version=ModelStages.LATEST))

        mv = client.get_model_version(
            model_name_or_id="foo",
            model_version_name_or_number_or_id=ModelStages.LATEST,
        )
        mv = client.zen_store.get_model_version(mv.id)

        assert len(mv.pipeline_run_ids) == 2
        assert {run_name for run_name in mv.pipeline_run_ids} == {
            run_name_1,
            run_name_2,
        }


@step
def _this_step_has_model_version_on_artifact_level() -> (
    Tuple[
        Annotated[
            int,
            "declarative_link",
            DataArtifactConfig(
                model_name="declarative", model_version=ModelStages.LATEST
            ),
        ],
        Annotated[int, "functional_link"],
    ]
):
    link_output_to_model(
        DataArtifactConfig(
            model_name="functional", model_version=ModelStages.LATEST
        ),
        output_name="functional_link",
    )
    return 1, 2


@pipeline(enable_cache=False)
def _pipeline_run_link_attached_from_artifact_context_single_step():
    _this_step_has_model_version_on_artifact_level()


@pipeline(enable_cache=False)
def _pipeline_run_link_attached_from_artifact_context_multiple_step():
    _this_step_has_model_version_on_artifact_level()
    _this_step_has_model_version_on_artifact_level()


@pipeline(
    enable_cache=False,
    model_version=ModelVersion(name="pipeline", version=ModelStages.LATEST),
)
def _pipeline_run_link_attached_from_mixed_context_single_step():
    _this_step_has_model_version_on_artifact_level()
    _this_step_produces_output()
    _this_step_produces_output.with_options(
        model_version=ModelVersion(name="step", version=ModelStages.LATEST),
    )()


@pipeline(
    enable_cache=False,
    model_version=ModelVersion(name="pipeline", version=ModelStages.LATEST),
)
def _pipeline_run_link_attached_from_mixed_context_multiple_step():
    _this_step_has_model_version_on_artifact_level()
    _this_step_produces_output()
    _this_step_produces_output.with_options(
        model_version=ModelVersion(name="step", version=ModelStages.LATEST),
    )()
    _this_step_has_model_version_on_artifact_level()
    _this_step_produces_output()
    _this_step_produces_output.with_options(
        model_version=ModelVersion(name="step", version=ModelStages.LATEST),
    )()


@pytest.mark.parametrize(
    "pipeline,model_names",
    (
        (
            _pipeline_run_link_attached_from_artifact_context_single_step,
            ["declarative", "functional"],
        ),
        (
            _pipeline_run_link_attached_from_artifact_context_multiple_step,
            ["declarative", "functional"],
        ),
        (
            _pipeline_run_link_attached_from_mixed_context_single_step,
            ["declarative", "functional", "step", "pipeline"],
        ),
        (
            _pipeline_run_link_attached_from_mixed_context_multiple_step,
            ["declarative", "functional", "step", "pipeline"],
        ),
    ),
    ids=[
        "Single step pipeline (declarative+functional)",
        "Multiple steps pipeline (declarative+functional)",
        "Single step pipeline (declarative+functional+step+pipeline)",
        "Multiple steps pipeline (declarative+functional+step+pipeline)",
    ],
)
def test_pipeline_run_link_attached_from_mixed_context(pipeline, model_names):
    """Tests that current pipeline run information is attached to model version by artifact context.

    Here we use 2 models and Artifacts has different configs to link there.
    """
    with model_killer():
        client = Client()

        models = []
        for model_name in model_names:
            models.append(
                client.create_model(
                    name=model_name,
                )
            )
            client.create_model_version(
                model_name_or_id=model_name,
                name="good_one",
            )

        run_name_1 = f"bar_run_{uuid4()}"
        pipeline.with_options(
            run_name=run_name_1,
        )()
        run_name_2 = f"bar_run_{uuid4()}"
        pipeline.with_options(
            run_name=run_name_2,
        )()

        for model in models:
            mv = client.get_model_version(
                model_name_or_id=model.id,
                model_version_name_or_number_or_id=ModelStages.LATEST,
            )
            mv = client.zen_store.get_model_version(mv.id)

            assert len(mv.pipeline_run_ids) == 2
            assert {run_name for run_name in mv.pipeline_run_ids} == {
                run_name_1,
                run_name_2,
            }


@step
def _consumer_step(a: int, b: int):
    assert a == b


@step(model_version=ModelVersion(name="step"))
def _producer_step() -> Tuple[int, int, int]:
    return 1, 2, 3


@pipeline
def _consumer_pipeline_with_step_context():
    _consumer_step.with_options(
        model_version=ModelVersion(name="step", version=ModelStages.LATEST)
    )(ExternalArtifact(model_artifact_name="output_0"), 1)


@pipeline
def _consumer_pipeline_with_artifact_context():
    _consumer_step(
        ExternalArtifact(
            model_artifact_name="output_1",
            model_name="step",
            model_version=ModelStages.LATEST,
        ),
        2,
    )


@pipeline(model_version=ModelVersion(name="step", version=ModelStages.LATEST))
def _consumer_pipeline_with_pipeline_context():
    _consumer_step(
        ExternalArtifact(model_artifact_name="output_2"),
        3,
    )


@pipeline
def _producer_pipeline():
    _producer_step()


def test_that_consumption_also_registers_run_in_model_version():
    """Test that consumption scenario also registers run in model version."""
    with model_killer():
        producer_run = f"producer_run_{uuid4()}"
        consumer_run_1 = f"consumer_run_1_{uuid4()}"
        consumer_run_2 = f"consumer_run_2_{uuid4()}"
        consumer_run_3 = f"consumer_run_3_{uuid4()}"
        _producer_pipeline.with_options(
            run_name=producer_run, enable_cache=False
        )()
        _consumer_pipeline_with_step_context.with_options(
            run_name=consumer_run_1
        )()
        _consumer_pipeline_with_artifact_context.with_options(
            run_name=consumer_run_2
        )()
        _consumer_pipeline_with_pipeline_context.with_options(
            run_name=consumer_run_3
        )()

        client = Client()
        mv = client.get_model_version(
            model_name_or_id="step",
            model_version_name_or_number_or_id=ModelStages.LATEST,
        )
        mv = client.zen_store.get_model_version(mv.id)

        assert len(mv.pipeline_run_ids) == 4
        assert {run_name for run_name in mv.pipeline_run_ids} == {
            producer_run,
            consumer_run_1,
            consumer_run_2,
            consumer_run_3,
        }


def test_that_if_some_steps_request_new_version_but_cached_new_version_is_still_created():
    """Test that if one of the steps requests a new version but was cached a new version is still created for other steps."""
    with model_killer():

        @pipeline(
            model_version=ModelVersion(name="step", version=ModelStages.LATEST)
        )
        def _inner_pipeline():
            # this step requests a new version, but can be cached
            _this_step_produces_output.with_options(
                model_version=ModelVersion(name="step")
            )()
            # this is an always run step
            _this_step_produces_output.with_options(enable_cache=False)()

        # this will run all steps, including one requesting new version
        run_1 = f"run_{uuid4()}"
        _inner_pipeline.with_options(run_name=run_1)()
        # here the step requesting new version is cached
        run_2 = f"run_{uuid4()}"
        _inner_pipeline.with_options(run_name=run_2)()

        client = Client()
        model = client.get_model(model_name_or_id="step")
        mvs = model.versions
        assert len(mvs) == 2
        for mv, run_name in zip(mvs, (run_1, run_2)):
            assert (
                len(client.zen_store.get_model_version(mv.id).pipeline_run_ids)
                == 1
            )
            assert client.zen_store.get_model_version(mv.id).pipeline_run_ids[
                run_name
            ]


def test_that_pipeline_run_is_removed_on_deletion_of_pipeline_run():
    """Test that if pipeline run gets deleted - it is removed from model version."""
    with model_killer():

        @pipeline(
            model_version=ModelVersion(
                name="step", version=ModelStages.LATEST
            ),
            enable_cache=False,
        )
        def _inner_pipeline():
            _this_step_produces_output.with_options(
                model_version=ModelVersion(name="step")
            )()

        run_1 = f"run_{uuid4()}"
        _inner_pipeline.with_options(run_name=run_1)()

        client = Client()
        client.delete_pipeline_run(run_1)
        model = client.get_model(model_name_or_id="step")
        mvs = model.versions
        assert len(mvs) == 1
        assert (
            len(client.zen_store.get_model_version(mvs[0].id).pipeline_run_ids)
            == 0
        )


def test_that_pipeline_run_is_removed_on_deletion_of_pipeline():
    """Test that if pipeline gets deleted - runs are removed from model version."""
    with model_killer():

        @pipeline(
            model_version=ModelVersion(
                name="step", version=ModelStages.LATEST
            ),
            enable_cache=False,
            name="test_that_pipeline_run_is_removed_on_deletion_of_pipeline",
        )
        def _inner_pipeline():
            _this_step_produces_output.with_options(
                model_version=ModelVersion(name="step")
            )()

        run_1 = f"run_{uuid4()}"
        _inner_pipeline.with_options(run_name=run_1)()

        client = Client()
        client.delete_pipeline(
            "test_that_pipeline_run_is_removed_on_deletion_of_pipeline"
        )
        model = client.get_model(model_name_or_id="step")
        mvs = model.versions
        assert len(mvs) == 1
        assert (
            len(client.zen_store.get_model_version(mvs[0].id).pipeline_run_ids)
            == 0
        )


def test_that_artifact_is_removed_on_deletion():
    """Test that if artifact gets deleted - it is removed from model version."""
    with model_killer():

        @pipeline(
            model_version=ModelVersion(
                name="step", version=ModelStages.LATEST
            ),
            enable_cache=False,
        )
        def _inner_pipeline():
            _this_step_produces_output.with_options(
                model_version=ModelVersion(name="step")
            )()

        run_1 = f"run_{uuid4()}"
        _inner_pipeline.with_options(run_name=run_1)()

        client = Client()
        run = client.get_pipeline_run(run_1)
        pipeline_id = run.pipeline.id
        artifact_id = (
            run.steps["_this_step_produces_output"].outputs["data"].id
        )
        client.delete_pipeline(pipeline_id)
        client.delete_artifact(artifact_id)
        model = client.get_model(model_name_or_id="step")
        mvs = model.versions
        assert len(mvs) == 1
        assert (
            len(client.zen_store.get_model_version(mvs[0].id).pipeline_run_ids)
            == 0
        )
