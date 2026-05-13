from __future__ import annotations

from dataclasses import dataclass

from src.models import GameConfig


@dataclass
class BetValidation:
    """Resultado de la validación de una operación de apuesta.

    Attributes:
        valid: Indica si la operación es válida.
        message: Mensaje explicativo en caso de error.
    """

    valid: bool
    message: str = ""


def allowed_options_for_round(round_index: int, cfg: GameConfig | None = None) -> int:
    """Determina cuántas opciones están permitidas para una ronda.

    Args:
        round_index: Índice de la ronda (1-based).
        cfg: Opcional, configuración del juego. Si no se provee, se usa `GameConfig()`.

    Returns:
        Número de opciones permitidas (2, 3 o 4).
    """

    cfg = cfg or GameConfig()
    if round_index in cfg.rounds_with_4_options:
        return 4
    if round_index in cfg.rounds_with_3_options:
        return 3
    return 2


def normalize_bets(options: list[str], bets: dict[str, int]) -> dict[str, int]:
    """Normaliza y sanitiza un diccionario de apuestas.

    Convierte a int y fuerza valores negativos a 0 para cada opción esperada.

    Args:
        options: Lista de opciones válidas.
        bets: Mapeo de opción -> monto apostado (posible entrada no limpia).

    Returns:
        Nuevo diccionario con las apuestas normalizadas para cada opción en `options`.
    """

    return {option: int(max(0, bets.get(option, 0))) for option in options}


def adjust_bet(
    bets: dict[str, int],
    option: str,
    direction: int,
    money_total: int,
    cfg: GameConfig | None = None,
) -> BetValidation:
    """Ajusta la apuesta para una opción incrementando o decrementando por el bloque.

    Args:
        bets: Diccionario mutable de apuestas por opción.
        option: Opción a modificar.
        direction: `1` para aumentar, `-1` para disminuir.
        money_total: Dinero total disponible del jugador.
        cfg: Opcional, configuración del juego.

    Returns:
        `BetValidation` indicando si la operación fue válida y mensaje en caso de error.
    """

    cfg = cfg or GameConfig()
    if option not in bets:
        return BetValidation(False, "Opción inválida")

    delta = cfg.bet_block if direction > 0 else -cfg.bet_block
    current_value = bets[option]
    new_value = current_value + delta

    if new_value < 0:
        return BetValidation(False, "La apuesta no puede ser negativa")

    projected_total = sum(bets.values()) - current_value + new_value
    if projected_total > money_total:
        return BetValidation(False, "No puedes apostar más dinero del disponible")

    bets[option] = new_value
    return BetValidation(True)


def validate_bets(
    bets: dict[str, int],
    money_total: int,
    is_final_round: bool,
    cfg: GameConfig | None = None,
) -> BetValidation:
    """Valida un conjunto de apuestas según las reglas del juego.

    Args:
        bets: Mapeo opción -> monto apostado.
        money_total: Dinero total disponible.
        is_final_round: Indica si es la ronda final (en la final no se exige trampilla vacía).
        cfg: Opcional, configuración del juego.

    Returns:
        `BetValidation` con `valid=True` si todas las reglas se cumplen.
    """

    cfg = cfg or GameConfig()

    for value in bets.values():
        if value < 0:
            return BetValidation(False, "Las apuestas no pueden ser negativas")
        if value % cfg.bet_block != 0:
            return BetValidation(False, f"Las apuestas deben ser múltiplos de {cfg.bet_block}")

    total_bet = sum(bets.values())
    if total_bet == 0:
        return BetValidation(False, "Debes apostar al menos un bloque")

    if total_bet > money_total:
        return BetValidation(False, "Has excedido tu dinero disponible")

    empty_trapdoors = sum(1 for value in bets.values() if value == 0)
    if not is_final_round and empty_trapdoors == 0:
        return BetValidation(False, "Debes dejar al menos una trampilla vacía")

    return BetValidation(True)
