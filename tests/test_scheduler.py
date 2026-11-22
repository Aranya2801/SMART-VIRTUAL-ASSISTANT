import threading

from aria.scheduler import Scheduler


def test_jobs_fire_in_order_and_can_be_cancelled():
    s = Scheduler()
    fired = []
    done = threading.Event()
    s.add(0.15, "timer", "b", lambda j: (fired.append(j.label), done.set()))
    s.add(0.05, "timer", "a", lambda j: fired.append(j.label))
    c = s.add(0.10, "alarm", "c", lambda j: fired.append(j.label))
    assert len(s.pending()) == 3
    assert s.cancel(job_id=c.id) == 1
    assert done.wait(2)
    assert fired == ["a", "b"]
    assert s.pending() == []
    s.stop()


def test_broken_callback_does_not_kill_thread():
    s = Scheduler()
    ok = threading.Event()
    s.add(0.01, "timer", "bad", lambda j: 1 / 0)
    s.add(0.05, "timer", "good", lambda j: ok.set())
    assert ok.wait(2)
    s.stop()
