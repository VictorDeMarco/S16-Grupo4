from __future__ import annotations

import threading
import uuid

import streamlit as st

from src.models import GameConfig
from src import voice


def _new_request_id() -> str:
    return str(uuid.uuid4())


def init_session_state() -> None:
    cfg = GameConfig()
    defaults = {
        "mode": "custom",
        "money_total": cfg.initial_money,
        "round_index": 1,
        "questions_pool": [],
        "classic_pairs": [],
        "current_pair_index": 0,
        "current_question": None,
        "bets_by_option": {},
        "generation_status": "idle",
        "generation_error": None,
        "generation_request_id": None,
        "active_request_id": _new_request_id(),
        "cancel_event": threading.Event(),
        "interrupted": False,
        "history": [],
        "game_over": False,
        "final_summary": None,
        "revealed_correct": False,
        "question_confirmed": False,
        "selected_topic_in_pair": None,
        "classic_generated_at": None,
        "pending_question_audio": None,
        "question_audio_played": False,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def hard_reset_game(mode: str) -> None:
    cfg = GameConfig()
    # Limpiar audios de preguntas anteriores
    voice.cleanup_question_audio()
    
    st.session_state.mode = mode
    st.session_state.money_total = cfg.initial_money
    st.session_state.round_index = 1
    st.session_state.questions_pool = []
    st.session_state.classic_pairs = []
    st.session_state.current_pair_index = 0
    st.session_state.current_question = None
    st.session_state.bets_by_option = {}
    st.session_state.generation_error = None
    st.session_state.history = []
    st.session_state.game_over = False
    st.session_state.final_summary = None
    st.session_state.revealed_correct = False
    st.session_state.question_confirmed = False
    st.session_state.selected_topic_in_pair = None
    st.session_state.pending_question_audio = None
    st.session_state.question_audio_played = False


def new_generation_cycle() -> str:
    if st.session_state.cancel_event is not None:
        st.session_state.cancel_event.set()
    st.session_state.cancel_event = threading.Event()
    request_id = _new_request_id()
    st.session_state.active_request_id = request_id
    st.session_state.generation_request_id = request_id
    st.session_state.generation_status = "running"
    st.session_state.interrupted = False
    st.session_state.generation_error = None
    return request_id


def cancel_generation(reason: str | None = None) -> None:
    if st.session_state.cancel_event is not None:
        st.session_state.cancel_event.set()
    st.session_state.interrupted = True
    st.session_state.generation_status = "cancelled"
    if reason:
        st.session_state.generation_error = reason
