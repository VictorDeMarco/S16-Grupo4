from __future__ import annotations

from dataclasses import asdict

import streamlit as st

from src.betting import allowed_options_for_round
from src.models import GameConfig, Question, RoundResult


def prepare_custom_topics(topics: list[str], total_rounds: int = 8) -> list[str]:
    cleaned = [item.strip() for item in topics if item.strip()]
    if not cleaned:
        return []
    repeated: list[str] = []
    index = 0
    while len(repeated) < total_rounds:
        repeated.append(cleaned[index % len(cleaned)])
        index += 1
    return repeated


def load_custom_questions(questions: list[Question]) -> None:
    st.session_state.questions_pool = questions
    st.session_state.current_question = questions[0] if questions else None


def load_classic_pairs(classic_pairs: list[tuple[Question, Question]]) -> None:
    st.session_state.classic_pairs = classic_pairs
    st.session_state.current_pair_index = 0
    st.session_state.selected_topic_in_pair = None
    st.session_state.current_question = None


def pair_topics_for_current_round() -> tuple[str, str] | None:
    pair_index = st.session_state.current_pair_index
    pairs = st.session_state.classic_pairs
    if pair_index >= len(pairs):
        return None
    left, right = pairs[pair_index]
    return left.tema, right.tema


def choose_topic_for_current_pair(chosen_topic: str) -> Question | None:
    pair_index = st.session_state.current_pair_index
    if pair_index >= len(st.session_state.classic_pairs):
        return None

    left, right = st.session_state.classic_pairs[pair_index]
    selected = left if left.tema == chosen_topic else right
    st.session_state.selected_topic_in_pair = chosen_topic
    st.session_state.current_question = selected
    return selected


def get_round_option_count(round_index: int) -> int:
    return allowed_options_for_round(round_index, GameConfig())


def initialize_bets_for_current_question() -> None:
    question = st.session_state.current_question
    if not question:
        return
    st.session_state.bets_by_option = {option: 0 for option in question.opciones}
    st.session_state.hidden_options = set()
    st.session_state.all_in_active = False


def replace_current_question(question: Question) -> None:
    st.session_state.current_question = question
    st.session_state.hidden_options = set()
    st.session_state.all_in_active = False

    if st.session_state.mode == "custom":
        question_index = st.session_state.round_index - 1
        if question_index < len(st.session_state.questions_pool):
            st.session_state.questions_pool[question_index] = question

    if st.session_state.mode == "clasico":
        pair_index = st.session_state.current_pair_index
        pairs = st.session_state.classic_pairs
        if pair_index < len(pairs):
            left, right = pairs[pair_index]
            if st.session_state.selected_topic_in_pair == left.tema:
                pairs[pair_index] = (question, right)
            else:
                pairs[pair_index] = (left, question)

    initialize_bets_for_current_question()


def apply_fifty_fifty() -> list[str]:
    question: Question | None = st.session_state.current_question
    if not question:
        return []

    incorrect_options = [option for option in question.opciones if option != question.respuesta_correcta]
    remove_count = min(2, len(incorrect_options))
    removed = incorrect_options[:remove_count]
    st.session_state.hidden_options = set(removed)
    for option in removed:
        st.session_state.bets_by_option[option] = 0
    return removed


def apply_all_in(option: str) -> bool:
    question: Question | None = st.session_state.current_question
    if not question or option not in question.opciones:
        return False

    st.session_state.bets_by_option = {item: 0 for item in question.opciones}
    st.session_state.bets_by_option[option] = st.session_state.money_total
    st.session_state.all_in_active = True
    return True


def resolve_current_round() -> RoundResult | None:
    question: Question | None = st.session_state.current_question
    if not question:
        return None

    money_before = st.session_state.money_total
    bets = st.session_state.bets_by_option
    winning_amount = int(bets.get(question.respuesta_correcta, 0))
    if st.session_state.all_in_active and winning_amount == money_before:
        winning_amount = int(winning_amount * 1.5)
    st.session_state.money_total = winning_amount

    result = RoundResult(
        round_number=st.session_state.round_index,
        tema=question.tema,
        pregunta=question.pregunta,
        apuesta_total=sum(bets.values()),
        apuesta_correcta=winning_amount,
        dinero_antes=money_before,
        dinero_despues=winning_amount,
        correcta=question.respuesta_correcta,
        fuente_busqueda=question.fuente_busqueda,
    )
    st.session_state.history.append(asdict(result))
    return result


def advance_round_or_finish() -> None:
    cfg = GameConfig()
    if st.session_state.money_total <= 0:
        st.session_state.game_over = True
        st.session_state.final_summary = build_final_summary()
        return

    if st.session_state.round_index >= cfg.total_rounds:
        st.session_state.game_over = True
        st.session_state.final_summary = build_final_summary()
        return

    st.session_state.round_index += 1
    st.session_state.revealed_correct = False
    st.session_state.question_confirmed = False
    st.session_state.bets_by_option = {}
    st.session_state.hidden_options = set()
    st.session_state.all_in_active = False
    st.session_state.current_question = None
    st.session_state.selected_topic_in_pair = None

    if st.session_state.mode == "custom":
        next_index = st.session_state.round_index - 1
        if next_index < len(st.session_state.questions_pool):
            st.session_state.current_question = st.session_state.questions_pool[next_index]

    if st.session_state.mode == "clasico":
        st.session_state.current_pair_index += 1


def build_final_summary() -> dict:
    return {
        "dinero_final": st.session_state.money_total,
        "rondas_jugadas": len(st.session_state.history),
        "historial": st.session_state.history,
    }
