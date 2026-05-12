from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

from google import genai
from google.genai import types

from src.betting import allowed_options_for_round
from src.models import Question


class GeminiGenerationError(Exception):
    pass


def _client() -> genai.Client:
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise GeminiGenerationError("Falta GEMINI_API_KEY en variables de entorno")
    return genai.Client(api_key=api_key)


def _extract_json_text(raw_text: str) -> str:
    raw_text = raw_text.strip()
    if raw_text.startswith("```"):
        raw_text = raw_text.strip("`")
        if raw_text.startswith("json"):
            raw_text = raw_text[4:].strip()
    start = raw_text.find("{")
    end = raw_text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise GeminiGenerationError("La IA no devolvió un JSON válido")
    return raw_text[start : end + 1]


def _validate_question_dict(item: dict[str, Any], expected_options: int) -> Question:
    required = ["tema", "pregunta", "opciones", "respuesta_correcta", "fuente_busqueda"]
    for key in required:
        if key not in item:
            raise GeminiGenerationError(f"Falta campo obligatorio: {key}")

    tema = str(item["tema"]).strip()
    pregunta = str(item["pregunta"]).strip()
    opciones = [str(option).strip() for option in item["opciones"]]
    respuesta_correcta = str(item["respuesta_correcta"]).strip()
    fuente_busqueda = str(item["fuente_busqueda"]).strip()

    if len(opciones) != expected_options:
        raise GeminiGenerationError(
            f"Número de opciones inválido. Esperadas: {expected_options}, recibidas: {len(opciones)}"
        )
    if len(set(opciones)) != len(opciones):
        raise GeminiGenerationError("Las opciones no pueden repetirse")
    if respuesta_correcta not in opciones:
        raise GeminiGenerationError("respuesta_correcta debe estar dentro de opciones")
    if fuente_busqueda.startswith("http://") or fuente_busqueda.startswith("https://"):
        raise GeminiGenerationError("fuente_busqueda debe ser referencia textual sin URL")

    return Question(
        tema=tema,
        pregunta=pregunta,
        opciones=opciones,
        respuesta_correcta=respuesta_correcta,
        fuente_busqueda=fuente_busqueda,
    )


def _build_classic_prompt() -> str:
    rounds_description = []
    for round_index in range(1, 9):
        rounds_description.append(
            f"Ronda {round_index}: cada pregunta del par debe tener {allowed_options_for_round(round_index)} opciones"
        )

    return (
        "Eres un generador de preguntas para un juego tipo Atrapa un Millón. "
        "Debes usar la herramienta google_search para cada tema y responder solo JSON estricto. "
        "NO incluyas markdown ni texto fuera del JSON. "
        "IMPORTANTE: fuente_busqueda debe ser referencia textual sin URL (ej. nombre de medio + fecha).\n\n"
        "Genera exactamente 8 pares temáticos (16 preguntas), un par por ronda.\n"
        "Reglas por ronda:\n"
        + "\n".join(rounds_description)
        + "\n\nSchema obligatorio:\n"
        "{\n"
        '  "modo": "clasico",\n'
        '  "metadata": {\n'
        '    "idioma": "es",\n'
        '    "total_candidatas": 16,\n'
        f'    "timestamp_iso": "{datetime.now(timezone.utc).isoformat()}",\n'
        '    "version_schema": "1.0"\n'
        "  },\n"
        '  "pares": [\n'
        "    {\n"
        '      "ronda": 1,\n'
        '      "preguntas": [\n'
        "        {\n"
        '          "tema": "...",\n'
        '          "pregunta": "...",\n'
        '          "opciones": ["..."],\n'
        '          "respuesta_correcta": "...",\n'
        '          "fuente_busqueda": "nombre_fuente y consulta usada"\n'
        "        },\n"
        "        { ... segunda pregunta del par ... }\n"
        "      ]\n"
        "    }\n"
        "  ]\n"
        "}\n\n"
        "Reglas estrictas:\n"
        "1) Debes usar google_search en cada pregunta antes de escribirla.\n"
        "2) Deben existir exactamente 8 objetos en pares y cada uno con 2 preguntas.\n"
        "3) respuesta_correcta debe coincidir exactamente con una opcion.\n"
        "4) No repitas en exceso la misma respuesta correcta.\n"
        "5) Si no puedes cumplir, responde exactamente: {\"error\":\"NO_SE_PUEDE_CUMPLIR_SCHEMA\" Y explica por que no puedes cumplir}."
    )


def _build_custom_prompt(expanded_topics: list[str]) -> str:
    rounds_description = []
    for round_index in range(1, 9):
        rounds_description.append(
            f"Ronda {round_index}: {allowed_options_for_round(round_index)} opciones"
        )

    topics_json = json.dumps(expanded_topics, ensure_ascii=False)

    return (
        "Eres un generador de preguntas para un juego tipo Atrapa un Millón. "
        "Debes usar google_search para cada tema y responder solo JSON estricto. "
        "NO incluyas markdown ni texto adicional. "
        "fuente_busqueda debe ser textual y nunca URL.\n\n"
        f"Temas por ronda (exactamente 8): {topics_json}\n"
        "Opciones por ronda:\n"
        + "\n".join(rounds_description)
        + "\n\n"
        "Schema obligatorio:\n"
        "{\n"
        '  "modo": "custom",\n'
        '  "preguntas": [\n'
        "    {\n"
        '      "tema": "...",\n'
        '      "pregunta": "...",\n'
        '      "opciones": ["..."],\n'
        '      "respuesta_correcta": "...",\n'
        '      "fuente_busqueda": "fuente textual sin URL"\n'
        "    }\n"
        "  ]\n"
        "}\n\n"
        "Reglas:\n"
        "1) Deben ser exactamente 8 preguntas.\n"
        "2) La pregunta i debe usar el tema i del arreglo de temas.\n"
        "3) Debes usar google_search para cada una.\n"
        "4) Si no puedes cumplir, responde {\"error\":\"NO_SE_PUEDE_CUMPLIR_SCHEMA\"}."
    )


def _build_replacement_prompt(topic: str, round_index: int, expected_options: int) -> str:
    return (
        "Eres un generador de preguntas para un juego tipo Atrapa un Millon. "
        "Debes usar google_search y responder solo JSON estricto. "
        "NO incluyas markdown ni texto adicional. "
        "fuente_busqueda debe ser textual y nunca URL.\n\n"
        f"Genera exactamente 1 pregunta nueva para la ronda {round_index} sobre este tema: {topic}.\n"
        f"La pregunta debe tener exactamente {expected_options} opciones.\n\n"
        "Schema obligatorio:\n"
        "{\n"
        '  "tema": "...",\n'
        '  "pregunta": "...",\n'
        '  "opciones": ["..."],\n'
        '  "respuesta_correcta": "...",\n'
        '  "fuente_busqueda": "fuente textual sin URL"\n'
        "}\n\n"
        "Reglas:\n"
        "1) respuesta_correcta debe coincidir exactamente con una opcion.\n"
        "2) No reutilices una pregunta generica; debe ser concreta y verificable.\n"
        "3) Si no puedes cumplir, responde {\"error\":\"NO_SE_PUEDE_CUMPLIR_SCHEMA\"}."
    )


def _call_gemini(prompt: str) -> dict[str, Any]:
    model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash").strip() or "gemini-2.0-flash"
    client = _client()

    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(
            tools=[types.Tool(google_search=types.GoogleSearch())],
            temperature=0.3,
        ),
    )

    text = getattr(response, "text", "") or ""
    if not text:
        raise GeminiGenerationError("Respuesta vacía de Gemini")

    payload = json.loads(_extract_json_text(text))
    if "error" in payload:
        raise GeminiGenerationError(payload["error"])
    return payload


def generate_classic_pairs() -> list[tuple[Question, Question]]:
    payload = _call_gemini(_build_classic_prompt())

    if payload.get("modo") != "clasico":
        raise GeminiGenerationError("Modo inválido en payload clásico")

    pares = payload.get("pares")
    if not isinstance(pares, list) or len(pares) != 8:
        raise GeminiGenerationError("El modo clásico requiere exactamente 8 pares")

    output_pairs: list[tuple[Question, Question]] = []
    for index, pair_item in enumerate(pares, start=1):
        if int(pair_item.get("ronda", index)) != index:
            raise GeminiGenerationError(f"La ronda esperada era {index}")
        preguntas = pair_item.get("preguntas", [])
        if not isinstance(preguntas, list) or len(preguntas) != 2:
            raise GeminiGenerationError("Cada par debe contener 2 preguntas")

        expected_options = allowed_options_for_round(index)
        left = _validate_question_dict(preguntas[0], expected_options)
        right = _validate_question_dict(preguntas[1], expected_options)
        output_pairs.append((left, right))

    return output_pairs


def generate_custom_questions(expanded_topics: list[str]) -> list[Question]:
    if len(expanded_topics) != 8:
        raise GeminiGenerationError("Custom requiere exactamente 8 temas expandidos")

    payload = _call_gemini(_build_custom_prompt(expanded_topics))
    if payload.get("modo") != "custom":
        raise GeminiGenerationError("Modo inválido en payload custom")

    questions = payload.get("preguntas")
    if not isinstance(questions, list) or len(questions) != 8:
        raise GeminiGenerationError("El modo custom requiere exactamente 8 preguntas")

    parsed: list[Question] = []
    for index, item in enumerate(questions, start=1):
        expected_options = allowed_options_for_round(index)
        parsed.append(_validate_question_dict(item, expected_options))

    return parsed


def generate_replacement_question(topic: str, round_index: int) -> Question:
    expected_options = allowed_options_for_round(round_index)
    payload = _call_gemini(_build_replacement_prompt(topic, round_index, expected_options))
    return _validate_question_dict(payload, expected_options)
