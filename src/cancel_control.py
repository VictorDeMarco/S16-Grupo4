from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any

import streamlit as st


_JOBS_LOCK = threading.Lock()
_JOBS: dict[str, dict[str, Any]] = {}


def is_request_stale(request_id: str) -> bool:
    """Comprueba si un `request_id` ya no es el activo en sesión.

    Args:
        request_id: Identificador de la petición a comprobar.

    Returns:
        `True` si el `request_id` proporcionado difiere del `active_request_id` en
        `st.session_state`.
    """

    return request_id != st.session_state.active_request_id


def should_abort_generation(request_id: str) -> bool:
    """Indica si la generación en curso debe abortarse.

    Se revisa si la petición es stale o si el `cancel_event` de la sesión está activado.

    Args:
        request_id: Identificador de la petición en curso.

    Returns:
        `True` si debe abortarse la generación.
    """

    cancel_event = st.session_state.cancel_event
    return is_request_stale(request_id) or (cancel_event is not None and cancel_event.is_set())


def start_job(request_id: str, worker: Callable[..., Any], *args: Any) -> None:
    """Inicia un trabajo en background y lo registra internamente.

    El worker se ejecuta en un hilo daemon y el resultado (o error) queda almacenado
    en la tabla interna `_JOBS` bajo `request_id`.

    Args:
        request_id: Identificador único de la tarea.
        worker: Callable que ejecuta el trabajo.
        *args: Argumentos a pasar al `worker`.

    Returns:
        None
    """

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
    """Recupera el estado almacenado de un trabajo por `request_id`.

    Args:
        request_id: Identificador del trabajo. Si es `None` devuelve `None`.

    Returns:
        Diccionario con campos `status`, `result` y `error`, o `None` si no existe.
    """

    if not request_id:
        return None
    with _JOBS_LOCK:
        return _JOBS.get(request_id)


def clear_job(request_id: str | None) -> None:
    """Elimina un trabajo almacenado del registro interno.

    Args:
        request_id: Identificador del trabajo a eliminar. Si es `None` no hace nada.

    Returns:
        None
    """

    if not request_id:
        return
    with _JOBS_LOCK:
        _JOBS.pop(request_id, None)
