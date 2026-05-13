from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


Mode = Literal["custom", "clasico"]
GenerationStatus = Literal["idle", "running", "done", "error", "cancelled"]


@dataclass
class Question:
    """Representa una pregunta del juego.

    Attributes:
        tema: Tema de la pregunta.
        pregunta: Texto de la pregunta.
        opciones: Lista de opciones de respuesta.
        respuesta_correcta: Texto de la respuesta correcta (debe estar en `opciones`).
        fuente_busqueda: Referencia textual de la fuente o consulta usada.
    """

    tema: str
    pregunta: str
    opciones: list[str]
    respuesta_correcta: str
    fuente_busqueda: str


@dataclass
class ClassicPayload:
    """Estructura esperada para la carga clásica generada por la IA.

    Attributes:
        modo: Debe ser el literal "clasico".
        metadata: Diccionario con metadatos sobre la generación.
        candidatas: Lista de `Question` candidatas.
    """

    modo: Literal["clasico"]
    metadata: dict
    candidatas: list[Question]


@dataclass
class RoundResult:
    """Resultado de una ronda jugada.

    Attributes:
        round_number: Número de la ronda (1-based).
        tema: Tema de la pregunta jugada.
        pregunta: Texto de la pregunta.
        apuesta_total: Suma de todas las apuestas realizadas en la ronda.
        apuesta_correcta: Monto apostado sobre la respuesta correcta.
        dinero_antes: Balance antes de resolver la ronda.
        dinero_despues: Balance después de resolver la ronda.
        correcta: Texto de la respuesta correcta.
        fuente_busqueda: Referencia textual de la fuente usada para la pregunta.
    """

    round_number: int
    tema: str
    pregunta: str
    apuesta_total: int
    apuesta_correcta: int
    dinero_antes: int
    dinero_despues: int
    correcta: str
    fuente_busqueda: str


@dataclass
class GameConfig:
    """Configuración por defecto del juego.

    Attributes:
        initial_money: Dinero inicial con el que empieza el jugador.
        bet_block: Unidad mínima de apuesta.
        total_rounds: Número total de rondas en una partida.
        rounds_with_4_options: Índices de ronda que usan 4 opciones.
        rounds_with_3_options: Índices de ronda que usan 3 opciones.
        rounds_with_2_options: Índices de ronda que usan 2 opciones.
    """

    initial_money: int = 1_000_000
    bet_block: int = 25_000
    total_rounds: int = 8
    rounds_with_4_options: set[int] = field(default_factory=lambda: {1, 2, 3, 4})
    rounds_with_3_options: set[int] = field(default_factory=lambda: {5, 6, 7})
    rounds_with_2_options: set[int] = field(default_factory=lambda: {8})
