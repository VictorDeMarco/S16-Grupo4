from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

from google import genai
from google.genai import types

from src.betting import allowed_options_for_round
from src.models import Question

from dotenv import load_dotenv
load_dotenv()


class GeminiGenerationError(Exception):
    """Excepción personalizada para errores durante la generación con Gemini."""


def _client() -> genai.Client:
    """Crea y devuelve un cliente `genai.Client` usando la variable de entorno.

    Raises:
        GeminiGenerationError: Si no se encuentra la variable `GEMINI_API_KEY`.

    Returns:
        Instancia de `genai.Client` autenticada.
    """

    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise GeminiGenerationError("Falta GEMINI_API_KEY en variables de entorno")
    return genai.Client(api_key=api_key)


def _extract_json_text(raw_text: str) -> str:
    """Extrae un objeto JSON de un texto crudo que puede contener código o markdown.

    Busca desde la primera llave '{' hasta la última '}' y devuelve ese fragmento.

    Args:
        raw_text: Texto potencialmente envuelto en markdown o con contenido adicional.

    Returns:
        Cadena con el JSON extraído.

    Raises:
        GeminiGenerationError: Si no se encuentra un JSON válido en el texto.
    """

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
    """Valida y convierte un diccionario bruto en una `Question`.

    Args:
        item: Diccionario con los campos esperados.
        expected_options: Número esperado de opciones para la ronda actual.

    Returns:
        Instancia de `Question` validada.

    Raises:
        GeminiGenerationError: Cuando falta un campo o alguna regla no se cumple.
    """

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

    """Construye el prompt que se envía a Gemini para generar pares clásicos.

    Returns:
        Cadena con el prompt formateado.
    """

    return (
        "Eres un Ingeniero de Preguntas experto en 'Atrapa un Millón'. Tu misión es generar un set de 16 preguntas "
        "basadas ÚNICAMENTE en hallazgos específicos obtenidos mediante google_search. \n\n"
        
        "### PROTOCOLO DE BÚSQUEDA ANTI-CLICHÉ (Obligatorio):\n"
        "1. Para cada categoría, NO uses el primer dato que te venga a la mente. Realiza una búsqueda en Google de 'datos curiosos poco conocidos sobre [TEMA]', 'noticias recientes sobre [TEMA]' o 'estadísticas actualizadas de [TEMA]'.\n"
        "2. PROHIBIDO: Preguntar por capitales obvias, autores de obras maestras universales (García Márquez, Cervantes, Shakespeare), o hitos históricos de primaria (descubrimiento de América, Revolución Francesa).\n"
        "3. REGLA DE ORO: Si una pregunta parece sacada de un Trivial convencional en rondas más avanzadas (a partir de la ronda 5), deséchala y busca un ángulo más específico (ej. en lugar de '¿Quién pintó la Mona Lisa?', busca '¿Qué anomalía detectaron científicos en la capa inferior de la Mona Lisa en 2024?').\n\n"

        "### INSTRUCCIONES DE EJECUCIÓN:\n"
        "1. DEFINE 16 sub-categorías ultra-específicas (ej. Micología, Historia del Siglo XIV, Ingeniería Ferroviaria, Lingüística de lenguas muertas, etc.).\n"
        "2. EJECUTA google_search para cada una para extraer un hecho real, verificable y con una cifra o nombre propio específico.\n"
        "3. ESCALA la dificultad: Ronda 1 son curiosidades interesantes; Ronda 8 debe requerir un conocimiento técnico o de nicho extremo.\n"
        "4. FUENTE: Debe ser un medio especializado, paper científico o institución oficial.\n\n"

        "### REGLAS DE DIVERSIDAD:\n"
        "- Ningún tema puede solaparse. Si usas 'Zoología Marina', no puedes usar 'Biología'.\n"
        "- Los dos temas de cada par deben ser contrastados (ej. 'Física Cuántica' vs 'Gastronomía Ancestral').\n\n"
        "REGLAS POR RONDA:\n"
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
        "        { ... segunda pregunta del par, cuyo tema debe ser diferente ... }\n"
        "      ]\n"
        "    }\n"
        "  ]\n"
        "}\n\n"
        "Reglas estrictas:\n"
        "1) Debes usar google_search en cada pregunta antes de escribirla.\n"
        "2) Deben existir exactamente 8 objetos en pares y cada uno con 2 preguntas.\n"
        "3) respuesta_correcta debe coincidir exactamente con una opcion. Para cumplimentar esto, cuando busques la pregunta, añade la respuesta correcta como respuesta_correcta y a opciones directamente\n"
        "4) No repitas en exceso la misma respuesta correcta.\n"  
        "5) Prohibido repetir el valor de 'tema'.\n"
        "6) Cada par de la ronda debe ofrecer dos opciones de juego totalmente distintas entre sí.\n"
        "7) No puede haber más del número de opciones establecido en REGLAS POR RONDA en las preguntas de cada ronda. SI el número de opciones excede el esperado, elimina las opciones suficientes para que se cumplimente este requisito, siempre y cuando no se elimine la opción que es equivalente a respuesta_correcta."
        "7) Si no puedes cumplir, responde: {\"error\":\"NO_SE_PUEDE_CUMPLIR_SCHEMA\", \"motivo\":\"...\"}."
    )


def _build_custom_prompt(expanded_topics: list[str]) -> str:
    rounds_description = []
    for round_index in range(1, 9):
        rounds_description.append(
            f"Ronda {round_index}: {allowed_options_for_round(round_index)} opciones"
        )

    topics_json = json.dumps(expanded_topics, ensure_ascii=False)

    """Construye el prompt para la generación de preguntas en modo custom.

    Args:
        expanded_topics: Lista de 8 temas ya expandidos para cada ronda.

    Returns:
        Cadena con el prompt formateado.
    """

    return (
        "Eres un generador de preguntas para un juego tipo Atrapa un Millón. "
        "Debes usar la herramienta google_search para cada tema y responder solo JSON estricto. "
        "NO incluyas markdown ni texto fuera del JSON. "
        "IMPORTANTE: fuente_busqueda debe ser referencia de la URL.\n\n"
        "El usuario aportara de 1 a 8 temas, iras rotando cada tema en cada ronda, donde en cada ronda va aumentando la dificultad de forma progresiva, llegando a un nivel de dificultad muy elevado en la uĺtima ronda.\n"
        f"Temas a repartir en cada ronda: {topics_json}\n"
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
        "1) Debes usar google_search en cada pregunta antes de escribirla.\n"
        "2) Deben existir exactamente 8 objetos con 4 respuestas solo una respuesta correcta.\n"
        "3) respuesta_correcta debe coincidir exactamente con una opcion. Para cumplimentar esto, cuando busques la pregunta, añade la respuesta correcta como respuesta_correcta y a opciones directamente\n"
        "4) No repitas en exceso la misma respuesta correcta.\n"  
        "5) Si no puedes cumplir, responde exactamente: {\"error\":\"NO_SE_PUEDE_CUMPLIR_SCHEMA\" Y explica por que no puedes cumplir}."
    )


def _call_gemini(prompt: str) -> dict[str, Any]:
    """Llama al modelo Gemini con el prompt y devuelve el payload JSON.

    Args:
        prompt: Texto del prompt a enviar.

    Returns:
        Diccionario resultante del JSON parseado por Gemini.

    Raises:
        GeminiGenerationError: Si la respuesta está vacía o contiene un error.
    """

    model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite").strip() or "gemini-2.0-flash"
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
    """Genera 8 pares de preguntas para el modo clásico llamando a Gemini.

    Returns:
        Lista de 8 tuplas `(Question, Question)` representando cada par por ronda.

    Raises:
        GeminiGenerationError: Si el payload no cumple el esquema esperado.
    """

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
    """Genera exactamente 8 preguntas para modo custom usando Gemini.

    Args:
        expanded_topics: Lista de 8 temas ya expandidos (uno por ronda).

    Returns:
        Lista de 8 instancias `Question` validadas.

    Raises:
        GeminiGenerationError: Si el payload no cumple el esquema esperado.
    """

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
