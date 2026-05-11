from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any

import streamlit as st


_JOBS_LOCK = threading.Lock()
_JOBS: dict[str, dict[str, Any]] = {}


def is_request_stale(request_id: str) -> bool:
    return request_id != st.session_state.active_request_id


def should_abort_generation(request_id: str) -> bool:
    cancel_event = st.session_state.cancel_event
    return is_request_stale(request_id) or (cancel_event is not None and cancel_event.is_set())


def start_job(request_id: str, worker: Callable[..., Any], *args: Any) -> None:
    with _JOBS_LOCK:
        _JOBS[request_id] = {"status": "running", "result": None, "error": None}

    def _run() -> None:
        try:
            result = worker(*args)
            with _JOBS_LOCK:
                _JOBS[request_id] = {"status": "done", "result": result, "error": None}
        except Exception as exc:
            with _JOBS_LOCK:
                _JOBS[request_id] = {"status": "error", "result": None, "error": str(exc)}

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()


def get_job(request_id: str | None) -> dict[str, Any] | None:
    if not request_id:
        return None
    with _JOBS_LOCK:
        return _JOBS.get(request_id)


def clear_job(request_id: str | None) -> None:
    if not request_id:
        return
    with _JOBS_LOCK:
        _JOBS.pop(request_id, None)
