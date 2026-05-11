from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


Mode = Literal["custom", "clasico"]
GenerationStatus = Literal["idle", "running", "done", "error", "cancelled"]


@dataclass
class Question:
    tema: str
    pregunta: str
    opciones: list[str]
    respuesta_correcta: str
    fuente_busqueda: str


@dataclass
class ClassicPayload:
    modo: Literal["clasico"]
    metadata: dict
    candidatas: list[Question]


@dataclass
class RoundResult:
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
    initial_money: int = 1_000_000
    bet_block: int = 25_000
    total_rounds: int = 8
    rounds_with_4_options: set[int] = field(default_factory=lambda: {1, 2, 3, 4})
    rounds_with_3_options: set[int] = field(default_factory=lambda: {5, 6, 7})
    rounds_with_2_options: set[int] = field(default_factory=lambda: {8})
