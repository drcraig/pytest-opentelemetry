import os
from pathlib import Path
from typing import Any, Dict, Generator, Optional, Union

import pytest
from _pytest.config import Config
from _pytest.fixtures import (
    FixtureDef,
    SubRequest,
    getfslineno,
    resolve_fixture_function,
)
from _pytest.main import Session
from _pytest.nodes import Item, Node
from _pytest.reports import TestReport
from _pytest.runner import CallInfo
from opentelemetry import propagate, trace
from opentelemetry.context.context import Context
from opentelemetry.sdk.resources import OTELResourceDetector
from opentelemetry.semconv.trace import SpanAttributes
from opentelemetry.trace import Status, StatusCode
from opentelemetry_container_distro import (
    OpenTelemetryContainerConfigurator,
    OpenTelemetryContainerDistro,
)

from .resource import CodebaseResourceDetector

tracer = trace.get_tracer('pytest-opentelemetry')

PYTEST_SPAN_TYPE = "pytest.span_type"


class OpenTelemetryPlugin:
    """A pytest plugin which produces OpenTelemetry spans around test sessions and
    individual test runs."""

    @property
    def session_name(self):
        # Lazy initialise session name
        if not hasattr(self, '_session_name'):
            self._session_name = os.environ.get('PYTEST_RUN_NAME', 'test run')
        return self._session_name

    @session_name.setter
    def session_name(self, name):
        self._session_name = name

    @classmethod
    def get_trace_parent(cls, config: Config) -> Optional[Context]:
        if trace_parent := config.getvalue('--trace-parent'):
            return propagate.extract({'traceparent': trace_parent})

        if trace_parent := os.environ.get('TRACEPARENT'):
            return propagate.extract({'traceparent': trace_parent})

        return None

    @classmethod
    def try_force_flush(cls) -> bool:
        provider = trace.get_tracer_provider()

        # Not all providers (e.g. ProxyTraceProvider) implement force flush
        if hasattr(provider, 'force_flush'):
            provider.force_flush()
            return True
        else:
            return False

    def pytest_configure(self, config: Config) -> None:
        self.trace_parent = self.get_trace_parent(config)

        # This can't be tested both ways in one process
        if config.getoption('--export-traces'):  # pragma: no cover
            OpenTelemetryContainerDistro().configure()

        configurator = OpenTelemetryContainerConfigurator()
        configurator.resource_detectors.append(CodebaseResourceDetector())
        configurator.resource_detectors.append(OTELResourceDetector())
        configurator.configure()

    def pytest_sessionstart(self, session: Session) -> None:
        self.session_span = tracer.start_span(
            self.session_name,
            context=self.trace_parent,
            attributes={
                PYTEST_SPAN_TYPE: "run",
            },
        )
        self.has_error = False

    def pytest_sessionfinish(self, session: Session) -> None:
        self.session_span.set_status(
            StatusCode.ERROR if self.has_error else StatusCode.OK
        )

        self.session_span.end()
        self.try_force_flush()

    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_protocol(self, item: Item) -> Generator[None, None, None]:
        context = trace.set_span_in_context(self.session_span)
        filepath, line_number, _ = item.location
        attributes: Dict[str, Union[str, int]] = {
            SpanAttributes.CODE_FILEPATH: filepath,
            SpanAttributes.CODE_FUNCTION: item.name,
            "pytest.nodeid": item.nodeid,
            PYTEST_SPAN_TYPE: "test",
        }
        # In some cases like tavern, line_number can be 0
        if line_number:
            attributes[SpanAttributes.CODE_LINENO] = line_number
        with tracer.start_as_current_span(
            item.name, attributes=attributes, context=context
        ):
            yield

    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_setup(self, item: Item) -> Generator[None, None, None]:
        filepath, line_number, _ = item.location
        attributes: Dict[str, Union[str, int]] = {
            SpanAttributes.CODE_FILEPATH: filepath,
            SpanAttributes.CODE_FUNCTION: item.name,
            "pytest.nodeid": item.nodeid,
            PYTEST_SPAN_TYPE: "test setup",
        }
        # In some cases like tavern, line_number can be 0
        if line_number:
            attributes[SpanAttributes.CODE_LINENO] = line_number
        with tracer.start_as_current_span(
            f"{item.name} setup",
            attributes=attributes,
        ):
            yield

    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_call(self, item: Item) -> Generator[None, None, None]:
        filepath, line_number, _ = item.location
        attributes: Dict[str, Union[str, int]] = {
            SpanAttributes.CODE_FILEPATH: filepath,
            SpanAttributes.CODE_FUNCTION: item.name,
            "pytest.nodeid": item.nodeid,
            PYTEST_SPAN_TYPE: "test call",
        }
        # In some cases like tavern, line_number can be 0
        if line_number:
            attributes[SpanAttributes.CODE_LINENO] = line_number
        with tracer.start_as_current_span(
            f"{item.name} call",
            attributes=attributes,
        ):
            yield

    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_teardown(self, item: Item) -> Generator[None, None, None]:
        filepath, line_number, _ = item.location
        attributes: Dict[str, Union[str, int]] = {
            SpanAttributes.CODE_FILEPATH: filepath,
            SpanAttributes.CODE_FUNCTION: item.name,
            "pytest.nodeid": item.nodeid,
            PYTEST_SPAN_TYPE: "test teardown",
        }
        # In some cases like tavern, line_number can be 0
        if line_number:
            attributes[SpanAttributes.CODE_LINENO] = line_number
        with tracer.start_as_current_span(
            f"{item.name} teardown",
            attributes=attributes,
        ):
            # Since there is no pytest_fixture_teardown hook, we have to be a
            # little clever to capture the spans for each fixture's teardown.
            # The pytest_fixture_post_finalizer hook is called at the end of a
            # fixture's teardown, but we don't know when the fixture actually
            # began tearing down.
            #
            # Instead start a span here for the first fixture to be torn down,
            # but give it a temporary name, since we don't know which fixture it
            # will be. Then, in pytest_fixture_post_finalizer, when we do know
            # which fixture is being torn down, update the name and attributes
            # to the actual fixture, end the span, and create the span for the
            # next fixture in line to be torn down.
            self.fixture_teardown_span = tracer.start_span("fixture teardown")
            yield

        # The last call to pytest_fixture_post_finalizer will create
        # a span that is unneeded, so delete it.
        del self.fixture_teardown_span

    @pytest.hookimpl(hookwrapper=True)
    def pytest_fixture_setup(
        self, fixturedef: FixtureDef, request: SubRequest
    ) -> Generator[None, None, None]:
        attributes: Dict[str, Union[str, int]] = {
            PYTEST_SPAN_TYPE: "fixture setup",
        }

        if fixturedef.has_location:
            func = resolve_fixture_function(fixturedef, request)
            filepath, line_number = getfslineno(func)
            if Path(filepath).is_relative_to(request.config.rootpath):
                filepath = Path(filepath).relative_to(request.config.rootpath)
            attributes[SpanAttributes.CODE_FILEPATH] = str(filepath)

            if line_number:  # pragma: no branch
                attributes[SpanAttributes.CODE_LINENO] = line_number

        with tracer.start_as_current_span(
            f"{fixturedef.argname} setup",
            attributes=attributes,
        ):
            yield

    @pytest.hookimpl(hookwrapper=True)
    def pytest_fixture_post_finalizer(
        self, fixturedef: FixtureDef, request: SubRequest
    ) -> Generator[None, None, None]:
        """When the span for a fixture teardown is created by
        pytest_runtest_teardown or a previous pytest_fixture_post_finalizer, we
        need to update the name and attributes now that we know which fixture it
        was for."""

        # Passing `-x` option to pytest can cause it to exit early
        # so it may not have this span attribute.
        if not hasattr(self, 'fixture_teardown_span'):  # pragma: no cover
            yield
            self.fixture_teardown_span = tracer.start_span("fixture teardown")
            return

        # If the fixture has already been torn down, then it will have no cached result.
        # and we can skip this one. Create a new span for the next one.
        if fixturedef.cached_result is None:
            yield
            self.fixture_teardown_span = tracer.start_span("fixture teardown")
            return

        name = f"{fixturedef.argname} teardown"
        self.fixture_teardown_span.update_name(name)

        attributes: Dict[str, Union[str, int]] = {
            PYTEST_SPAN_TYPE: "fixture teardown",
        }
        if fixturedef.has_location:
            func = resolve_fixture_function(fixturedef, request)
            filepath, line_number = getfslineno(func)

            if Path(filepath).is_relative_to(request.config.rootpath):
                filepath = Path(filepath).relative_to(request.config.rootpath)
            attributes[SpanAttributes.CODE_FILEPATH] = str(filepath)

            if line_number:  # pragma: no branch
                attributes[SpanAttributes.CODE_LINENO] = line_number
        self.fixture_teardown_span.set_attributes(attributes)
        yield
        self.fixture_teardown_span.end()

        # Create the span for the next fixture to be torn down. When there are
        # no more fixtures remaining, this will be an empty, useless span, so it
        # needs to be deleted by pytest_runtest_teardown.
        self.fixture_teardown_span = tracer.start_span("fixture teardown")

    @staticmethod
    def pytest_exception_interact(
        node: Node,
        call: CallInfo[Any],
        report: TestReport,
    ) -> None:
        excinfo = call.excinfo
        assert excinfo
        assert isinstance(excinfo.value, BaseException)

        test_span = trace.get_current_span()

        test_span.record_exception(
            # Interface says Exception, but BaseException seems to work fine
            # This is needed because pytest's Failed exception inherits from
            # BaseException, not Exception
            exception=excinfo.value,  # type: ignore[arg-type]
            attributes={
                SpanAttributes.EXCEPTION_STACKTRACE: str(report.longrepr),
            },
        )
        test_span.set_status(
            Status(
                status_code=StatusCode.ERROR,
                description=f"{excinfo.type}: {excinfo.value}",
            )
        )

    def pytest_runtest_logreport(self, report: TestReport) -> None:
        if report.when != 'call':
            return

        has_error = report.outcome == 'failed'
        status_code = StatusCode.ERROR if has_error else StatusCode.OK
        self.has_error |= has_error
        trace.get_current_span().set_status(status_code)


try:
    from xdist.workermanage import WorkerController  # pylint: disable=unused-import
except ImportError:  # pragma: no cover
    WorkerController = None


class XdistOpenTelemetryPlugin(OpenTelemetryPlugin):
    """An xdist-aware version of the OpenTelemetryPlugin"""

    @classmethod
    def get_trace_parent(cls, config: Config) -> Optional[Context]:
        if workerinput := getattr(config, 'workerinput', None):
            return propagate.extract(workerinput)

        return super().get_trace_parent(config)

    def pytest_configure(self, config: Config) -> None:
        super().pytest_configure(config)
        worker_id = getattr(config, 'workerinput', {}).get('workerid')
        self.session_name = (
            f'test worker {worker_id}' if worker_id else self.session_name
        )

    def pytest_configure_node(self, node: WorkerController) -> None:  # pragma: no cover
        with trace.use_span(self.session_span, end_on_exit=False):
            propagate.inject(node.workerinput)

    def pytest_xdist_node_collection_finished(node, ids):  # pragma: no cover
        super().try_force_flush()
