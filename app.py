from __future__ import annotations

import os

import streamlit as st
from dotenv import load_dotenv

from src.betting import adjust_bet, validate_bets
from src.cancel_control import clear_job, get_job, is_request_stale, start_job
from src.game_logic import (
    advance_round_or_finish,
    choose_topic_for_current_pair,
    get_round_option_count,
    initialize_bets_for_current_question,
    load_classic_pairs,
    load_custom_questions,
    pair_topics_for_current_round,
    prepare_custom_topics,
    resolve_current_round,
)
from src.gemini_client import GeminiGenerationError, generate_classic_pairs, generate_custom_questions
from src.models import GameConfig
from src.state import cancel_generation, hard_reset_game, init_session_state, new_generation_cycle

load_dotenv()

st.set_page_config(page_title="Atrapa un Millón IA", layout="wide")
init_session_state()
cfg = GameConfig()


def _sync_classic_background_job() -> None:
    if st.session_state.mode != "clasico":
        return
    if st.session_state.generation_status != "running":
        return

    request_id = st.session_state.generation_request_id
    job = get_job(request_id)
    if not job:
        return

    status = job.get("status")
    if status == "done":
        clear_job(request_id)
        if is_request_stale(request_id):
            st.session_state.generation_status = "cancelled"
            return
        load_classic_pairs(job["result"])
        st.session_state.generation_status = "done"
        st.session_state.current_question = None
    elif status == "error":
        clear_job(request_id)
        if is_request_stale(request_id):
            st.session_state.generation_status = "cancelled"
            return
        st.session_state.generation_status = "error"
        st.session_state.generation_error = job.get("error", "Error desconocido")


def _on_mode_change(new_mode: str) -> None:
    if st.session_state.mode == new_mode:
        return
    if st.session_state.generation_status == "running":
        cancel_generation("Generación previa interrumpida por cambio de modo")
    hard_reset_game(new_mode)


def _render_generation_controls() -> None:
    st.subheader("Configuración")

    selected_mode = st.radio(
        "Modo de juego",
        options=["custom", "clasico"],
        horizontal=True,
        index=0 if st.session_state.mode == "custom" else 1,
    )
    _on_mode_change(selected_mode)

    if st.session_state.mode == "custom":
        topics_text = st.text_area(
            "Temas (hasta 8, una línea por tema)",
            value="Historia\nCiencia\nDeportes\nTecnología",
            height=160,
        )
        topics = [line.strip() for line in topics_text.splitlines() if line.strip()][:8]
        st.caption(f"Temas detectados: {len(topics)}")

        if st.button("Iniciar modo Custom", type="primary", use_container_width=True):
            if st.session_state.generation_status == "running":
                cancel_generation("Se priorizó la nueva solicitud custom")
            hard_reset_game("custom")
            request_id = new_generation_cycle()
            try:
                expanded_topics = prepare_custom_topics(topics, cfg.total_rounds)
                if len(expanded_topics) != 8:
                    raise GeminiGenerationError("Debes ingresar al menos 1 tema para iniciar Custom")
                with st.spinner("Generando 8 preguntas custom con Gemini..."):
                    questions = generate_custom_questions(expanded_topics)
                if is_request_stale(request_id):
                    st.session_state.generation_status = "cancelled"
                    return
                load_custom_questions(questions)
                initialize_bets_for_current_question()
                st.session_state.generation_status = "done"
            except Exception as exc:
                st.session_state.generation_status = "error"
                st.session_state.generation_error = str(exc)

    else:
        if st.button("Iniciar modo Clásico", type="primary", use_container_width=True):
            hard_reset_game("clasico")
            request_id = new_generation_cycle()
            start_job(request_id, generate_classic_pairs)
            st.session_state.generation_status = "running"

        if st.session_state.generation_status == "running":
            st.info("Generación clásica en progreso en segundo plano.")
            st.button("Actualizar estado de generación", use_container_width=True)

    if st.session_state.generation_status == "error":
        st.error(st.session_state.generation_error or "Falló la generación")
    elif st.session_state.generation_status == "cancelled":
        st.warning(st.session_state.generation_error or "Generación cancelada")
    elif st.session_state.generation_status == "done":
        st.success("Partida lista para jugar")


ASSET_CLOSED = "assets/trap_closed.svg"
ASSET_OPEN = "assets/trap_open.svg"
ASSET_CORRECT = "assets/trap_correct.svg"


def _render_trap_column(option: str, idx: int, disabled: bool) -> None:
    image_path = ASSET_CLOSED
    if st.session_state.revealed_correct:
        if option == st.session_state.current_question.respuesta_correcta:
            image_path = ASSET_CORRECT
        else:
            image_path = ASSET_OPEN

    st.image(image_path, use_container_width=True)

    if st.session_state.revealed_correct and option == st.session_state.current_question.respuesta_correcta:
        st.markdown(
            f"<div style='padding:0.5rem;border-radius:8px;background:#1f7a1f;color:white;font-weight:700;'>{option}</div>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(f"**{option}**")

    minus_key = f"minus_{st.session_state.round_index}_{idx}"
    plus_key = f"plus_{st.session_state.round_index}_{idx}"

    c1, c2 = st.columns(2)
    with c1:
        if st.button("-", key=minus_key, disabled=disabled, use_container_width=True):
            result = adjust_bet(st.session_state.bets_by_option, option, -1, st.session_state.money_total)
            if not result.valid:
                st.warning(result.message)
    with c2:
        if st.button("+", key=plus_key, disabled=disabled, use_container_width=True):
            result = adjust_bet(st.session_state.bets_by_option, option, 1, st.session_state.money_total)
            if not result.valid:
                st.warning(result.message)

    st.caption(f"Apuesta: ${st.session_state.bets_by_option.get(option, 0):,}")


def _render_betting_area() -> None:
    question = st.session_state.current_question
    if not question:
        return

    expected_options = get_round_option_count(st.session_state.round_index)
    if len(question.opciones) != expected_options:
        st.error(
            f"La ronda {st.session_state.round_index} requiere {expected_options} opciones, pero llegó {len(question.opciones)}"
        )
        return

    st.markdown(f"### Ronda {st.session_state.round_index}/8")
    st.markdown(f"**Tema:** {question.tema}")
    st.markdown(f"**Pregunta:** {question.pregunta}")

    options = question.opciones
    trap_columns = st.columns(4)
    for idx in range(4):
        with trap_columns[idx]:
            if idx < len(options):
                _render_trap_column(options[idx], idx, st.session_state.question_confirmed)
            else:
                st.image(ASSET_OPEN, use_container_width=True)
                st.caption("Sin trampilla")

    total_bet = sum(st.session_state.bets_by_option.values())
    st.info(f"Apuesta total: ${total_bet:,} / Dinero disponible: ${st.session_state.money_total:,}")

    if not st.session_state.question_confirmed:
        if st.button("Confirmar apuesta", type="secondary", use_container_width=True):
            validation = validate_bets(
                st.session_state.bets_by_option,
                st.session_state.money_total,
                is_final_round=st.session_state.round_index == cfg.total_rounds,
            )
            if not validation.valid:
                st.warning(validation.message)
            else:
                resolve_current_round()
                st.session_state.question_confirmed = True
                st.session_state.revealed_correct = True
    else:
        st.success(f"Respuesta correcta: {question.respuesta_correcta}")
        if st.button("Continuar", type="primary", use_container_width=True):
            advance_round_or_finish()
            if st.session_state.mode == "custom" and st.session_state.current_question is not None:
                initialize_bets_for_current_question()


def _render_classic_topic_selector() -> None:
    topics = pair_topics_for_current_round()
    if topics is None:
        st.session_state.game_over = True
        return

    left_topic, right_topic = topics
    st.markdown(f"### Ronda {st.session_state.round_index}/8")
    st.markdown("Elige 1 de 2 temas antes de ver la pregunta")

    c1, c2 = st.columns(2)
    with c1:
        if st.button(left_topic, use_container_width=True):
            choose_topic_for_current_pair(left_topic)
            initialize_bets_for_current_question()
    with c2:
        if st.button(right_topic, use_container_width=True):
            choose_topic_for_current_pair(right_topic)
            initialize_bets_for_current_question()


def _render_game_area() -> None:
    st.subheader("Partida")
    if st.session_state.generation_status != "done":
        st.info("Genera una partida para comenzar")
        return

    if st.session_state.game_over:
        summary = st.session_state.final_summary or {}
        st.success(f"Partida finalizada. Ganaste ${summary.get('dinero_final', 0):,}")
        st.markdown("### Resumen")
        st.write(
            {
                "dinero_final": summary.get("dinero_final", 0),
                "rondas_jugadas": summary.get("rondas_jugadas", 0),
            }
        )
        if summary.get("historial"):
            st.dataframe(summary["historial"], use_container_width=True)
        return

    if st.session_state.mode == "clasico" and st.session_state.current_question is None:
        _render_classic_topic_selector()
        return

    _render_betting_area()


_sync_classic_background_job()

st.title("Atrapa un Millón IA")
metric_1, metric_2, metric_3 = st.columns(3)
metric_1.metric("Dinero", f"${st.session_state.money_total:,}")
metric_2.metric("Ronda", f"{st.session_state.round_index}/8")
metric_3.metric("Modo", st.session_state.mode.upper())

left, right = st.columns([1, 2])
with left:
    _render_generation_controls()
with right:
    _render_game_area()

st.caption("Nota: en modo clásico, la generación corre en segundo plano. Si pasas a custom, se cancela y se prioriza custom.")
