import datetime
from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pytest

from syscontrol import timer_functions
from syscontrol.timer_parameters import timerClassParameters


@pytest.fixture
def clock(monkeypatch):
    clock = SimpleNamespace(wall=datetime.datetime(2026, 11, 1, 1, 59), elapsed=0.0)
    monkeypatch.setattr(
        timer_functions,
        "datetime",
        SimpleNamespace(datetime=SimpleNamespace(now=lambda: clock.wall)),
    )
    monkeypatch.setattr(
        timer_functions,
        "time",
        SimpleNamespace(monotonic=lambda: clock.elapsed),
        raising=False,
    )
    return clock


@pytest.fixture
def make_timer(monkeypatch, clock):
    monkeypatch.setattr(timer_functions, "dataControlProcess", lambda data: data)

    def make_timer(frequency=1, maximum=-1, completion=False, function=None):
        return timer_functions.timerClassWithFunction(
            function_to_execute=Mock() if function is None else function,
            data=Mock(),
            parameters=timerClassParameters(
                method_name="test_method",
                process_name="test_process",
                frequency_minutes=frequency,
                max_executions=maximum,
                run_on_completion_only=completion,
                minutes_between_heartbeats=10,
            ),
            log=Mock(),
        )

    return make_timer


def test_first_run_and_heartbeat_are_immediate(make_timer, clock):
    timer = make_timer()
    assert timer.when_last_run() == timer_functions.A_LONG_LONG_TIME_AGO
    assert timer.when_last_heartbeat() == timer_functions.A_LONG_LONG_TIME_AGO
    assert timer.minutes_until_next_run() == 0

    timer.check_and_run()

    timer._function.assert_called_once_with()
    assert timer.actual_executions == 1
    assert timer.when_last_run() == clock.wall
    assert timer.when_last_heartbeat() == clock.wall
    assert timer.minutes_since_last_run() == 0
    assert timer.minutes_since_last_heartbeat() == 0
    timer.data.log_start_run_for_method.assert_called_once_with(
        "test_process", "test_method"
    )
    timer.data.log_end_run_for_method.assert_called_once_with(
        "test_process", "test_method"
    )


@pytest.mark.parametrize("frequency", [0, 1, 5])
@pytest.mark.parametrize("wall_jump", [-3600, 3600])
def test_wall_clock_jump_does_not_change_elapsed_intervals(
    make_timer, clock, frequency, wall_jump
):
    timer = make_timer(frequency=frequency)
    timer.check_and_run()
    original_wall = clock.wall

    clock.elapsed += 60
    clock.wall += datetime.timedelta(seconds=60 + wall_jump)

    assert timer.minutes_since_last_run() == 1
    assert timer.minutes_since_last_heartbeat() == 1
    assert timer.minutes_until_next_run() == max(frequency - 1, 0)
    assert timer.when_last_run() == original_wall
    assert timer.when_last_heartbeat() == original_wall

    timer.check_and_run()
    assert timer._function.call_count == (2 if frequency <= 1 else 1)


@pytest.mark.parametrize("elapsed", [0, 299.999, 300, 301])
def test_method_runs_at_frequency_boundary(make_timer, clock, elapsed):
    timer = make_timer(frequency=5)
    timer.check_and_run()
    clock.elapsed += elapsed
    clock.wall += datetime.timedelta(seconds=elapsed)

    assert timer.minutes_until_next_run() == pytest.approx(max(5 - elapsed / 60, 0))
    timer.check_and_run()
    assert timer._function.call_count == (2 if elapsed >= 300 else 1)


@pytest.mark.parametrize("wall_jump", [-3600, 3600])
def test_heartbeat_has_independent_elapsed_anchor_and_strict_boundary(
    make_timer, clock, wall_jump
):
    timer = make_timer()
    timer.log_heartbeat()
    first_heartbeat = clock.wall
    clock.elapsed += 60
    clock.wall += datetime.timedelta(seconds=60 + wall_jump)
    timer.set_time_of_last_run()

    assert timer.minutes_since_last_run() == 0
    assert timer.minutes_since_last_heartbeat() == 1
    clock.elapsed = 600
    timer.log_heartbeat_if_required()
    assert timer.when_last_heartbeat() == first_heartbeat

    clock.elapsed += 1
    timer.log_heartbeat_if_required()
    assert timer.when_last_heartbeat() == clock.wall
    assert timer.minutes_since_last_heartbeat() == 0
    assert timer.minutes_since_last_run() == pytest.approx(541 / 60)


def test_frequency_remains_start_to_start_for_long_callback(make_timer, clock):
    def callback():
        clock.elapsed += 120
        clock.wall += datetime.timedelta(seconds=120)

    timer = make_timer(frequency=1, function=callback)
    started = clock.wall
    timer.check_and_run()

    assert timer.when_last_run() == started
    assert timer.minutes_since_last_run() == 2
    assert timer.minutes_until_next_run() == 0
    timer.check_and_run()
    assert timer.actual_executions == 2


def test_completed_methods_do_not_delay_remaining_methods(make_timer, clock):
    completed = make_timer(maximum=1)
    waiting = make_timer(frequency=5)
    timers = timer_functions.listOfTimerFunctions([completed, waiting])
    completed.check_and_run()
    waiting.check_and_run()
    clock.elapsed += 60
    clock.wall -= datetime.timedelta(minutes=59)

    completed.check_and_run()
    assert completed.actual_executions == 1
    assert np.isnan(completed.minutes_until_next_run())
    assert timers.seconds_until_next_method_runs() == 240
    assert not timers.check_all_finished()
    assert timer_functions.listOfTimerFunctions([completed]).check_all_finished()


def test_completion_only_methods_keep_existing_behavior(make_timer):
    normal = make_timer()
    cleanup = make_timer(completion=True)
    cleanup.check_and_run()
    cleanup._function.assert_not_called()
    assert np.isnan(cleanup.minutes_until_next_run())

    timers = timer_functions.listOfTimerFunctions([normal, cleanup])
    timers.run_methods_which_run_on_exit_only(value="test")
    cleanup._function.assert_called_once_with(value="test")
    normal._function.assert_not_called()
    assert cleanup.actual_executions == 1


def test_new_timer_does_not_inherit_previous_elapsed_anchor(make_timer, clock):
    previous = make_timer(frequency=60)
    previous.check_and_run()
    clock.elapsed += 1
    clock.wall += datetime.timedelta(seconds=1)
    fresh = make_timer(frequency=60)

    assert previous.minutes_until_next_run() > 0
    assert fresh.minutes_until_next_run() == 0
    fresh.check_and_run()
    fresh._function.assert_called_once_with()
    assert fresh.minutes_since_last_heartbeat() == 0
