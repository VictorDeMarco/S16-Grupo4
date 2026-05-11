from __future__ import annotations

from dataclasses import dataclass

from src.models import GameConfig


@dataclass
class BetValidation:
    valid: bool
    message: str = ""


def allowed_options_for_round(round_index: int, cfg: GameConfig | None = None) -> int:
    cfg = cfg or GameConfig()
    if round_index in cfg.rounds_with_4_options:
        return 4
    if round_index in cfg.rounds_with_3_options:
        return 3
    return 2


def normalize_bets(options: list[str], bets: dict[str, int]) -> dict[str, int]:
    return {option: int(max(0, bets.get(option, 0))) for option in options}


def adjust_bet(
    bets: dict[str, int],
    option: str,
    direction: int,
    money_total: int,
    cfg: GameConfig | None = None,
) -> BetValidation:
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
