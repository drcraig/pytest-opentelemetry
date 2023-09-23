from _pytest.pytester import Pytester
from opentelemetry.trace import SpanKind

from . import SpanRecorder


def test_simple_pytest_functions(
    pytester: Pytester, span_recorder: SpanRecorder
) -> None:
    pytester.makepyfile(
        """
        def test_one():
            assert 1 + 2 == 3

        def test_two():
            assert 2 + 2 == 4
    """
    )
    pytester.runpytest().assert_outcomes(passed=2)

    assert sorted(span_recorder.span_names()) == sorted(
        [
            # Not sure why these first two appear in the unit tests.
            # When run as a standalone file, they are not there.
            "span_recorder setup",
            "test_simple_pytest_functions setup",
            "test run",
            "test_one",
            "test_one setup",
            "test_one call",
            "test_one teardown",
            "test_two",
            "test_two setup",
            "test_two call",
            "test_two teardown",
        ]
    )

    spans = span_recorder.spans_by_name()
    span = spans['test run']
    assert span.status.is_ok
    assert span.attributes
    assert span.attributes["pytest.span_type"] == "run"

    span = spans['test_one']
    assert span.kind == SpanKind.INTERNAL
    assert span.status.is_ok
    assert span.attributes
    assert span.attributes['code.function'] == 'test_one'
    assert span.attributes['code.filepath'] == 'test_simple_pytest_functions.py'
    assert 'code.lineno' not in span.attributes
    assert span.attributes["pytest.span_type"] == "test"
    assert (
        span.attributes["pytest.nodeid"] == "test_simple_pytest_functions.py::test_one"
    )

    span = spans['test_one setup']
    assert span.kind == SpanKind.INTERNAL
    assert span.status.is_ok
    assert span.attributes
    assert span.attributes['code.function'] == 'test_one'
    assert span.attributes['code.filepath'] == 'test_simple_pytest_functions.py'
    assert 'code.lineno' not in span.attributes
    assert span.attributes["pytest.span_type"] == "test setup"
    assert (
        span.attributes["pytest.nodeid"] == "test_simple_pytest_functions.py::test_one"
    )

    span = spans['test_one call']
    assert span.kind == SpanKind.INTERNAL
    assert span.status.is_ok
    assert span.attributes
    assert span.attributes['code.function'] == 'test_one'
    assert span.attributes['code.filepath'] == 'test_simple_pytest_functions.py'
    assert 'code.lineno' not in span.attributes
    assert span.attributes["pytest.span_type"] == "test call"
    assert (
        span.attributes["pytest.nodeid"] == "test_simple_pytest_functions.py::test_one"
    )

    span = spans['test_one teardown']
    assert span.kind == SpanKind.INTERNAL
    assert span.status.is_ok
    assert span.attributes
    assert span.attributes['code.function'] == 'test_one'
    assert span.attributes['code.filepath'] == 'test_simple_pytest_functions.py'
    assert 'code.lineno' not in span.attributes
    assert span.attributes["pytest.span_type"] == "test teardown"
    assert (
        span.attributes["pytest.nodeid"] == "test_simple_pytest_functions.py::test_one"
    )

    span = spans['test_two']
    assert span.kind == SpanKind.INTERNAL
    assert span.status.is_ok
    assert span.attributes
    assert span.attributes['code.function'] == 'test_two'
    assert span.attributes['code.filepath'] == 'test_simple_pytest_functions.py'
    assert span.attributes['code.lineno'] == 3
    assert span.attributes["pytest.span_type"] == "test"
    assert (
        span.attributes["pytest.nodeid"] == "test_simple_pytest_functions.py::test_two"
    )

    span = spans['test_two setup']
    assert span.kind == SpanKind.INTERNAL
    assert span.status.is_ok
    assert span.attributes
    assert span.attributes['code.function'] == 'test_two'
    assert span.attributes['code.filepath'] == 'test_simple_pytest_functions.py'
    assert span.attributes['code.lineno'] == 3
    assert span.attributes["pytest.span_type"] == "test setup"
    assert (
        span.attributes["pytest.nodeid"] == "test_simple_pytest_functions.py::test_two"
    )

    span = spans['test_two call']
    assert span.kind == SpanKind.INTERNAL
    assert span.status.is_ok
    assert span.attributes
    assert span.attributes['code.function'] == 'test_two'
    assert span.attributes['code.filepath'] == 'test_simple_pytest_functions.py'
    assert span.attributes['code.lineno'] == 3
    assert span.attributes["pytest.span_type"] == "test call"
    assert (
        span.attributes["pytest.nodeid"] == "test_simple_pytest_functions.py::test_two"
    )

    span = spans['test_two teardown']
    assert span.kind == SpanKind.INTERNAL
    assert span.status.is_ok
    assert span.attributes
    assert span.attributes['code.function'] == 'test_two'
    assert span.attributes['code.filepath'] == 'test_simple_pytest_functions.py'
    assert span.attributes['code.lineno'] == 3
    assert span.attributes["pytest.span_type"] == "test teardown"
    assert (
        span.attributes["pytest.nodeid"] == "test_simple_pytest_functions.py::test_two"
    )


def test_failures_and_errors(pytester: Pytester, span_recorder: SpanRecorder) -> None:
    pytester.makepyfile(
        """
        import pytest

        def test_one():
            assert 1 + 2 == 3

        def test_two():
            assert 2 + 2 == 5

        def test_three():
            raise ValueError('woops')

        def test_four():
            # Test did not raise case
            with pytest.raises(ValueError):
                pass
    """
    )
    result = pytester.runpytest()
    result.assert_outcomes(passed=1, failed=3)

    assert sorted(span_recorder.span_names()) == sorted(
        [
            'span_recorder setup',
            'test_failures_and_errors setup',
            'test run',
            'test_one',
            'test_one setup',
            'test_one call',
            'test_one teardown',
            'test_two',
            'test_two setup',
            'test_two call',
            'test_two teardown',
            'test_three',
            'test_three setup',
            'test_three call',
            'test_three teardown',
            'test_four',
            'test_four setup',
            'test_four call',
            'test_four teardown',
        ]
    )

    spans = span_recorder.spans_by_name()
    span = spans['test run']
    assert not span.status.is_ok

    span = spans['test_one']
    assert span.status.is_ok
    span = spans['test_one setup']
    assert span.status.is_ok
    span = spans['test_one call']
    assert span.status.is_ok
    span = spans['test_one teardown']
    assert span.status.is_ok

    span = spans['test_two']
    assert not span.status.is_ok
    assert span.attributes
    assert span.attributes['code.function'] == 'test_two'
    assert span.attributes['code.filepath'] == 'test_failures_and_errors.py'
    assert span.attributes['code.lineno'] == 5
    assert 'exception.stacktrace' not in span.attributes
    assert len(span.events) == 1
    event = span.events[0]
    assert event.attributes
    assert event.attributes['exception.type'] == 'AssertionError'

    span = spans["test_two setup"]
    assert span.status.is_ok
    # QUESTION: is it okay that the call span doesn't contain the error?
    span = spans['test_two call']
    assert span.status.is_ok
    span = spans['test_two teardown']
    assert span.status.is_ok

    span = spans['test_three']
    assert not span.status.is_ok
    assert span.attributes
    assert span.attributes['code.function'] == 'test_three'
    assert span.attributes['code.filepath'] == 'test_failures_and_errors.py'
    assert span.attributes['code.lineno'] == 8
    assert 'exception.stacktrace' not in span.attributes
    assert len(span.events) == 1
    event = span.events[0]
    assert event.attributes
    assert event.attributes['exception.type'] == 'ValueError'
    assert event.attributes['exception.message'] == 'woops'

    span = spans["test_three setup"]
    assert span.status.is_ok
    # QUESTION: is it okay that the call span doesn't contain the error?
    span = spans['test_three call']
    assert span.status.is_ok
    span = spans['test_three teardown']
    assert span.status.is_ok

    span = spans['test_four']
    assert not span.status.is_ok
    assert span.attributes
    assert span.attributes['code.function'] == 'test_four'
    assert span.attributes['code.filepath'] == 'test_failures_and_errors.py'
    assert span.attributes['code.lineno'] == 11
    assert 'exception.stacktrace' not in span.attributes
    assert len(span.events) == 1
    event = span.events[0]
    assert event.attributes
    assert event.attributes['exception.type'] == 'Failed'
    assert event.attributes['exception.message'] == "DID NOT RAISE <class 'ValueError'>"

    span = spans["test_four setup"]
    assert span.status.is_ok
    # QUESTION: is it okay that the call span doesn't contain the error?
    span = spans['test_four call']
    assert span.status.is_ok
    span = spans['test_four teardown']
    assert span.status.is_ok


def test_failures_in_fixtures(pytester: Pytester, span_recorder: SpanRecorder) -> None:
    pytester.makepyfile(
        """
        import pytest

        @pytest.fixture
        def borked_fixture():
            raise ValueError('newp')

        def test_one():
            assert 1 + 2 == 3

        def test_two(borked_fixture):
            assert 2 + 2 == 5

        def test_three(borked_fixture):
            assert 2 + 2 == 4

        def test_four():
            assert 2 + 2 == 5
    """
    )
    result = pytester.runpytest()
    result.assert_outcomes(passed=1, failed=1, errors=2)

    assert sorted(span_recorder.span_names()) == sorted(
        [
            'span_recorder setup',
            'test_failures_in_fixtures setup',
            'test run',
            'test_one',
            'test_one setup',
            'test_one call',
            'test_one teardown',
            'test_two',
            'test_two setup',
            'borked_fixture setup',
            'test_two teardown',
            'borked_fixture teardown',
            'test_three',
            'test_three setup',
            'borked_fixture setup',
            'test_three teardown',
            'borked_fixture teardown',
            'test_four',
            'test_four setup',
            'test_four call',
            'test_four teardown',
        ]
    )

    spans = span_recorder.spans_by_name()
    # Tests with fixtures that failed in setup are never called.
    assert "test_two call" not in spans
    assert "test_three call" not in spans

    assert 'test run' in spans

    span = spans['test_one']
    assert span.status.is_ok

    span = spans['test_two']
    assert not span.status.is_ok

    span = spans['test_three']
    assert not span.status.is_ok

    span = spans['test_four']
    assert not span.status.is_ok


def test_parametrized_tests(pytester: Pytester, span_recorder: SpanRecorder) -> None:
    pytester.makepyfile(
        """
        import pytest

        @pytest.mark.parametrize('hello', ['world', 'people'])
        def test_one(hello):
            assert 1 + 2 == 3

        def test_two():
            assert 2 + 2 == 4
    """
    )
    pytester.runpytest().assert_outcomes(passed=3)

    assert sorted(span_recorder.span_names()) == sorted(
        [
            'span_recorder setup',
            'test_parametrized_tests setup',
            'test run',
            'test_one[world]',
            'hello setup',
            'test_one[world] setup',
            'test_one[world] call',
            'test_one[world] teardown',
            'hello teardown',
            'test_one[people]',
            'hello setup',
            'test_one[people] setup',
            'test_one[people] call',
            'test_one[people] teardown',
            'hello teardown',
            'test_two',
            'test_two setup',
            'test_two call',
            'test_two teardown',
        ]
    )

    spans = span_recorder.spans_by_name()
    assert 'test run' in spans

    span = spans['test_one[world]']
    assert span.status.is_ok
    assert span.attributes
    assert (
        span.attributes["pytest.nodeid"]
        == "test_parametrized_tests.py::test_one[world]"
    )

    span = spans['test_one[people]']
    assert span.status.is_ok
    assert span.attributes
    assert (
        span.attributes["pytest.nodeid"]
        == "test_parametrized_tests.py::test_one[people]"
    )

    span = spans['test_two']
    assert span.status.is_ok
    assert span.attributes
    assert span.attributes["pytest.nodeid"] == "test_parametrized_tests.py::test_two"


def test_parametrized_fixture(pytester: Pytester, span_recorder: SpanRecorder) -> None:
    pytester.makepyfile(
        """
        import pytest

        @pytest.fixture(params=["foo", "bar"])
        def fixture_a(request):
            yield request.param

        def test_one(fixture_a):
            assert fixture_a in ("foo", "bar")
    """
    )
    pytester.runpytest().assert_outcomes(passed=2)
    assert sorted(span_recorder.span_names()) == sorted(
        [
            'span_recorder setup',
            'test_parametrized_fixture setup',
            'test run',
            'test_one[foo]',
            'fixture_a setup',
            'test_one[foo] setup',
            'test_one[foo] call',
            'test_one[foo] teardown',
            'fixture_a teardown',
            'test_one[bar]',
            'fixture_a setup',
            'test_one[bar] setup',
            'test_one[bar] call',
            'test_one[bar] teardown',
            'fixture_a teardown',
        ]
    )


# TODO: test_module_scope_fixtures
# TODO: test_session_scope_fixtures
def test_fixture_teardown_error(
    pytester: Pytester, span_recorder: SpanRecorder
) -> None:
    pytester.makepyfile(
        """
        import pytest

        @pytest.fixture
        def fixture_a():
            return

        @pytest.fixture
        def fixture_b(fixture_a):
            yield
            raise ValueError("woops")

        def test_one(fixture_b):
            assert True
    """
    )
    pytester.runpytest().assert_outcomes(passed=1, errors=1)
    assert sorted(span_recorder.span_names()) == sorted(
        [
            'span_recorder setup',
            'test_fixture_teardown_error setup',
            'test run',
            'test_one',
            'test_one setup',
            'fixture_a setup',
            'fixture_b setup',
            'test_one call',
            'test_one teardown',
            'fixture_b teardown',
            # TODO: I don't understand why there is a second b teardown
            'fixture_b teardown',
            'fixture_a teardown',
        ]
    )


def test_class_tests(pytester: Pytester, span_recorder: SpanRecorder) -> None:
    pytester.makepyfile(
        """
        class TestThings:
            def test_one(self):
                assert 1 + 2 == 3

            def test_two(self):
                assert 2 + 2 == 4
    """
    )
    pytester.runpytest().assert_outcomes(passed=2)

    assert sorted(span_recorder.span_names()) == sorted(
        [
            'span_recorder setup',
            'test_class_tests setup',
            'test run',
            'test_one',
            'test_one setup',
            'test_one call',
            'test_one teardown',
            'test_two',
            'test_two setup',
            'test_two call',
            'test_two teardown',
        ]
    )

    spans = span_recorder.spans_by_name()
    assert 'test run' in spans

    span = spans['test_one']
    assert span.status.is_ok
    assert span.attributes
    assert (
        span.attributes["pytest.nodeid"] == "test_class_tests.py::TestThings::test_one"
    )

    span = spans['test_two']
    assert span.status.is_ok
    assert span.attributes
    assert (
        span.attributes["pytest.nodeid"] == "test_class_tests.py::TestThings::test_two"
    )


def test_test_spans_are_children_of_sessions(
    pytester: Pytester, span_recorder: SpanRecorder
) -> None:
    pytester.makepyfile(
        """
        def test_one():
            assert 1 + 2 == 3
    """
    )
    pytester.runpytest().assert_outcomes(passed=1)

    assert sorted(span_recorder.span_names()) == sorted(
        [
            'span_recorder setup',
            'test_test_spans_are_children_of_sessions setup',
            'test run',
            'test_one',
            'test_one setup',
            'test_one call',
            'test_one teardown',
        ]
    )

    spans = span_recorder.spans_by_name()

    test_run = spans['test run']
    test = spans['test_one']

    assert test_run.context.trace_id
    assert test.context.trace_id == test_run.context.trace_id

    assert test.parent
    assert test.parent.span_id == test_run.context.span_id


def test_spans_within_tests_are_children_of_test_spans(
    pytester: Pytester, span_recorder: SpanRecorder
) -> None:
    pytester.makepyfile(
        """
        from opentelemetry import trace

        tracer = trace.get_tracer('inside')

        def test_one():
            with tracer.start_as_current_span('inner'):
                assert 1 + 2 == 3
    """
    )
    pytester.runpytest().assert_outcomes(passed=1)

    assert sorted(span_recorder.span_names()) == sorted(
        [
            'span_recorder setup',
            'test_spans_within_tests_are_children_of_test_spans setup',
            'test run',
            'test_one',
            'test_one setup',
            'test_one call',
            'inner',
            'test_one teardown',
        ]
    )

    spans = span_recorder.spans_by_name()
    test_run = spans['test run']
    test = spans['test_one']
    test_call = spans['test_one call']
    inner = spans['inner']

    assert test_run.context.trace_id
    assert test.context.trace_id == test_run.context.trace_id
    assert inner.context.trace_id == test.context.trace_id

    assert test.parent
    assert test.parent.span_id == test_run.context.span_id

    assert test_call.parent
    assert test_call.parent.span_id == test.context.span_id

    assert inner.parent
    assert inner.parent.span_id == test_call.context.span_id
