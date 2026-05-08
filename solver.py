from __future__ import annotations

from dataclasses import dataclass, field
from time import perf_counter
from typing import Callable, Dict, List, Optional, Sequence, Tuple
import math
import random


ROWS = 6
COLS = 7

EMPTY = 0
HUMAN = 1
COMPUTER = 2

PLAYER_NAMES = {
    EMPTY: "EMPTY",
    HUMAN: "HUMAN",
    COMPUTER: "COMPUTER",
}

SYMBOLS = {
    EMPTY: ".",
    HUMAN: "H",
    COMPUTER: "C",
}

CENTER_FIRST_ORDER = [3, 2, 4, 1, 5, 0, 6]
TERMINAL_UTILITY_SCALE = 100000


Board = List[List[int]]
HeuristicFn = Callable[[Board], int]


@dataclass
class SearchStats:
    nodes_expanded: int = 0
    leaf_evaluations: int = 0
    pruned_branches: int = 0
    max_depth_reached: int = 0


@dataclass
class SearchResult:
    algorithm: str
    best_column: Optional[int]
    value: float
    nodes_expanded: int
    leaf_evaluations: int
    pruned_branches: int
    running_time: float
    tree_trace: List[str] = field(default_factory=list)


_active_heuristic: HeuristicFn


def create_board() -> Board:
    return [[EMPTY for _ in range(COLS)] for _ in range(ROWS)]


def copy_board(board: Board) -> Board:
    return [row[:] for row in board]


def is_valid_column(board: Board, col: int) -> bool:
    return 0 <= col < COLS and board[0][col] == EMPTY


def get_valid_columns(board: Board) -> List[int]:
    return [col for col in range(COLS) if is_valid_column(board, col)]


def order_columns(valid_columns: Sequence[int]) -> List[int]:
    valid_set = set(valid_columns)
    return [col for col in CENTER_FIRST_ORDER if col in valid_set]


def get_next_open_row(board: Board, col: int) -> Optional[int]:
    for row in range(ROWS - 1, -1, -1):
        if board[row][col] == EMPTY:
            return row
    return None


def drop_piece(board: Board, col: int, piece: int) -> bool:
    row = get_next_open_row(board, col)
    if row is None:
        return False
    board[row][col] = piece
    return True


def is_board_full(board: Board) -> bool:
    return all(board[0][col] != EMPTY for col in range(COLS))


def board_to_string(board: Board) -> str:
    lines = ["  " + " ".join(str(c) for c in range(COLS))]
    lines.append(" +" + "--" * COLS + "+")
    for row in board:
        lines.append(" |" + " ".join(SYMBOLS[cell] for cell in row) + " |")
    lines.append(" +" + "--" * COLS + "+")
    return "\n".join(lines)


def print_board(board: Board) -> None:
    print(board_to_string(board))


def all_windows(board: Board) -> List[List[int]]:
    windows: List[List[int]] = []

    for row in range(ROWS):
        for col in range(COLS - 3):
            windows.append([board[row][col + i] for i in range(4)])

    for row in range(ROWS - 3):
        for col in range(COLS):
            windows.append([board[row + i][col] for i in range(4)])

    for row in range(ROWS - 3):
        for col in range(COLS - 3):
            windows.append([board[row + i][col + i] for i in range(4)])

    for row in range(3, ROWS):
        for col in range(COLS - 3):
            windows.append([board[row - i][col + i] for i in range(4)])

    return windows


def count_connected_fours(board: Board, piece: int) -> int:
    return sum(1 for window in all_windows(board) if window.count(piece) == 4)


def utility(board: Board) -> int:
    return count_connected_fours(board, COMPUTER) - count_connected_fours(board, HUMAN)


def current_scores(board: Board) -> Tuple[int, int]:
    return count_connected_fours(board, COMPUTER), count_connected_fours(board, HUMAN)


def winner_summary(board: Board) -> str:
    computer_score, human_score = current_scores(board)
    if computer_score > human_score:
        winner = "Computer wins"
    elif human_score > computer_score:
        winner = "Human wins"
    else:
        winner = "Draw"
    return f"{winner}: Computer {computer_score}, Human {human_score}"


def evaluate_window(window: List[int]) -> int:
    score = 0

    computer_count = window.count(COMPUTER)
    human_count = window.count(HUMAN)
    empty_count = window.count(EMPTY)

    if computer_count == 3 and empty_count == 1:
        score += 120
    elif human_count == 3 and empty_count == 1:
        score -= 150
    elif computer_count == 2 and empty_count == 2:
        score += 15
    elif human_count == 2 and empty_count == 2:
        score -= 20
    elif computer_count == 1 and empty_count == 3:
        score += 2
    elif human_count == 1 and empty_count == 3:
        score -= 2

    return score


def center_control_score(board: Board) -> int:
    center_col = COLS // 2
    center_cells = [board[row][center_col] for row in range(ROWS)]
    return 6 * center_cells.count(COMPUTER) - 6 * center_cells.count(HUMAN)


def heuristic(board: Board) -> int:
    score = 0
    computer_fours, human_fours = current_scores(board)
    score += TERMINAL_UTILITY_SCALE * (computer_fours - human_fours)

    for window in all_windows(board):
        score += evaluate_window(window)

    score += center_control_score(board)
    return score


def heuristic_v2(board: Board) -> int:
    score = 0

    for window in all_windows(board):
        computer_count = window.count(COMPUTER)
        human_count = window.count(HUMAN)
        empty_count = window.count(EMPTY)

        if computer_count == 4:
            score += TERMINAL_UTILITY_SCALE
        elif human_count == 4:
            score -= TERMINAL_UTILITY_SCALE
        elif computer_count == 3 and empty_count == 1:
            score += 50
        elif human_count == 3 and empty_count == 1:
            score -= 80

    score += center_control_score(board)
    return score


_active_heuristic = heuristic


def evaluate_search_leaf(board: Board) -> Tuple[float, str]:
    if is_board_full(board):
        return TERMINAL_UTILITY_SCALE * utility(board), "terminal_utility"
    return _active_heuristic(board), "heuristic"


def add_trace(lines: List[str], text: str, max_lines: int = 2000) -> None:
    if len(lines) < max_lines - 1:
        lines.append(text)
    elif len(lines) == max_lines - 1:
        lines.append("[tree trace truncated; search still continued]")


def _leaf_trace(board: Board, indent: str, value: float, evaluation_name: str) -> str:
    board_rows = [indent + "  " + " ".join(SYMBOLS[cell] for cell in row) for row in board]
    return (
        indent
        + "LEAF board:\n"
        + "\n".join(board_rows)
        + "\n"
        + indent
        + evaluation_name
        + "="
        + str(value)
    )


def maximize_plain(
    board: Board,
    depth: int,
    stats: SearchStats,
    lines: List[str],
    level: int = 0,
    max_trace_depth: int = 4,
) -> Tuple[Optional[int], float]:
    stats.nodes_expanded += 1
    stats.max_depth_reached = max(stats.max_depth_reached, level)
    indent = "  " * level

    if depth == 0 or is_board_full(board):
        value, evaluation_name = evaluate_search_leaf(board)
        stats.leaf_evaluations += 1
        if level <= max_trace_depth:
            add_trace(lines, _leaf_trace(board, indent, value, evaluation_name))
        return None, value

    valid_columns = order_columns(get_valid_columns(board))
    if not valid_columns:
        value, _ = evaluate_search_leaf(board)
        stats.leaf_evaluations += 1
        return None, value

    max_child = valid_columns[0]
    max_utility = -math.inf

    if level <= max_trace_depth:
        add_trace(lines, f"{indent}MAX depth={depth}")

    for child_col in valid_columns:
        child_board = copy_board(board)
        drop_piece(child_board, child_col, COMPUTER)
        _, utility_value = minimize_plain(
            child_board, depth - 1, stats, lines, level + 1, max_trace_depth
        )

        if level <= max_trace_depth:
            add_trace(lines, f"{indent}  column {child_col} -> value {utility_value}")

        if utility_value > max_utility:
            max_child = child_col
            max_utility = utility_value

    if level <= max_trace_depth:
        add_trace(lines, f"{indent}MAX returns column={max_child}, value={max_utility}")

    return max_child, max_utility


def minimize_plain(
    board: Board,
    depth: int,
    stats: SearchStats,
    lines: List[str],
    level: int = 0,
    max_trace_depth: int = 4,
) -> Tuple[Optional[int], float]:
    stats.nodes_expanded += 1
    stats.max_depth_reached = max(stats.max_depth_reached, level)
    indent = "  " * level

    if depth == 0 or is_board_full(board):
        value, evaluation_name = evaluate_search_leaf(board)
        stats.leaf_evaluations += 1
        if level <= max_trace_depth:
            add_trace(lines, _leaf_trace(board, indent, value, evaluation_name))
        return None, value

    valid_columns = order_columns(get_valid_columns(board))
    if not valid_columns:
        value, _ = evaluate_search_leaf(board)
        stats.leaf_evaluations += 1
        return None, value

    min_child = valid_columns[0]
    min_utility = math.inf

    if level <= max_trace_depth:
        add_trace(lines, f"{indent}MIN depth={depth}")

    for child_col in valid_columns:
        child_board = copy_board(board)
        drop_piece(child_board, child_col, HUMAN)
        _, utility_value = maximize_plain(
            child_board, depth - 1, stats, lines, level + 1, max_trace_depth
        )

        if level <= max_trace_depth:
            add_trace(lines, f"{indent}  column {child_col} -> value {utility_value}")

        if utility_value < min_utility:
            min_child = child_col
            min_utility = utility_value

    if level <= max_trace_depth:
        add_trace(lines, f"{indent}MIN returns column={min_child}, value={min_utility}")

    return min_child, min_utility


def maximize_ab(
    board: Board,
    depth: int,
    alpha: float,
    beta: float,
    stats: SearchStats,
    lines: List[str],
    level: int = 0,
    max_trace_depth: int = 4,
) -> Tuple[Optional[int], float]:
    stats.nodes_expanded += 1
    stats.max_depth_reached = max(stats.max_depth_reached, level)
    indent = "  " * level

    if depth == 0 or is_board_full(board):
        value, evaluation_name = evaluate_search_leaf(board)
        stats.leaf_evaluations += 1
        if level <= max_trace_depth:
            add_trace(lines, _leaf_trace(board, indent, value, evaluation_name))
        return None, value

    valid_columns = order_columns(get_valid_columns(board))
    if not valid_columns:
        value, _ = evaluate_search_leaf(board)
        stats.leaf_evaluations += 1
        return None, value

    max_child = valid_columns[0]
    max_utility = -math.inf

    if level <= max_trace_depth:
        add_trace(lines, f"{indent}MAX depth={depth}, alpha={alpha}, beta={beta}")

    for index, child_col in enumerate(valid_columns):
        child_board = copy_board(board)
        drop_piece(child_board, child_col, COMPUTER)
        _, utility_value = minimize_ab(
            child_board, depth - 1, alpha, beta, stats, lines, level + 1, max_trace_depth
        )

        if utility_value > max_utility:
            max_child = child_col
            max_utility = utility_value

        alpha = max(alpha, max_utility)

        if level <= max_trace_depth:
            add_trace(
                lines,
                f"{indent}  column {child_col} -> value {utility_value}, alpha={alpha}, beta={beta}",
            )

        if alpha >= beta:
            remaining = len(valid_columns) - index - 1
            stats.pruned_branches += remaining
            if level <= max_trace_depth:
                add_trace(lines, f"{indent}  PRUNE remaining {remaining} branch(es)")
            break

    if level <= max_trace_depth:
        add_trace(lines, f"{indent}MAX returns column={max_child}, value={max_utility}")

    return max_child, max_utility


def minimize_ab(
    board: Board,
    depth: int,
    alpha: float,
    beta: float,
    stats: SearchStats,
    lines: List[str],
    level: int = 0,
    max_trace_depth: int = 4,
) -> Tuple[Optional[int], float]:
    stats.nodes_expanded += 1
    stats.max_depth_reached = max(stats.max_depth_reached, level)
    indent = "  " * level

    if depth == 0 or is_board_full(board):
        value, evaluation_name = evaluate_search_leaf(board)
        stats.leaf_evaluations += 1
        if level <= max_trace_depth:
            add_trace(lines, _leaf_trace(board, indent, value, evaluation_name))
        return None, value

    valid_columns = order_columns(get_valid_columns(board))
    if not valid_columns:
        value, _ = evaluate_search_leaf(board)
        stats.leaf_evaluations += 1
        return None, value

    min_child = valid_columns[0]
    min_utility = math.inf

    if level <= max_trace_depth:
        add_trace(lines, f"{indent}MIN depth={depth}, alpha={alpha}, beta={beta}")

    for index, child_col in enumerate(valid_columns):
        child_board = copy_board(board)
        drop_piece(child_board, child_col, HUMAN)
        _, utility_value = maximize_ab(
            child_board, depth - 1, alpha, beta, stats, lines, level + 1, max_trace_depth
        )

        if utility_value < min_utility:
            min_child = child_col
            min_utility = utility_value

        beta = min(beta, min_utility)

        if level <= max_trace_depth:
            add_trace(
                lines,
                f"{indent}  column {child_col} -> value {utility_value}, alpha={alpha}, beta={beta}",
            )

        if alpha >= beta:
            remaining = len(valid_columns) - index - 1
            stats.pruned_branches += remaining
            if level <= max_trace_depth:
                add_trace(lines, f"{indent}  PRUNE remaining {remaining} branch(es)")
            break

    if level <= max_trace_depth:
        add_trace(lines, f"{indent}MIN returns column={min_child}, value={min_utility}")

    return min_child, min_utility


def chance_outcomes(board: Board, intended_col: int) -> List[Tuple[int, float]]:
    raw_outcomes = [
        (intended_col, 0.6),
        (intended_col - 1, 0.2),
        (intended_col + 1, 0.2),
    ]

    valid_outcomes: List[Tuple[int, float]] = []
    for actual_col, probability in raw_outcomes:
        if is_valid_column(board, actual_col):
            valid_outcomes.append((actual_col, probability))

    total_probability = sum(prob for _, prob in valid_outcomes)
    if total_probability == 0:
        return []

    return [(col, prob / total_probability) for col, prob in valid_outcomes]


def choose_stochastic_actual_column(
    board: Board,
    intended_col: int,
    rng: Optional[random.Random] = None,
) -> Optional[int]:
    outcomes = chance_outcomes(board, intended_col)
    if not outcomes:
        return None

    generator = rng if rng is not None else random
    threshold = generator.random()
    cumulative_probability = 0.0

    for actual_col, probability in outcomes:
        cumulative_probability += probability
        if threshold <= cumulative_probability:
            return actual_col

    return outcomes[-1][0]


def apply_game_move(
    board: Board,
    intended_col: int,
    piece: int,
    stochastic: bool = False,
    rng: Optional[random.Random] = None,
) -> Optional[int]:
    if stochastic:
        actual_col = choose_stochastic_actual_column(board, intended_col, rng=rng)
    else:
        actual_col = intended_col if is_valid_column(board, intended_col) else None

    if actual_col is None:
        return None

    drop_piece(board, actual_col, piece)
    return actual_col


def expected_maximize(
    board: Board,
    depth: int,
    stats: SearchStats,
    lines: List[str],
    level: int = 0,
    max_trace_depth: int = 3,
) -> Tuple[Optional[int], float]:
    stats.nodes_expanded += 1
    stats.max_depth_reached = max(stats.max_depth_reached, level)
    indent = "  " * level

    if depth == 0 or is_board_full(board):
        value, evaluation_name = evaluate_search_leaf(board)
        stats.leaf_evaluations += 1
        if level <= max_trace_depth:
            add_trace(lines, _leaf_trace(board, indent, value, evaluation_name))
        return None, value

    valid_columns = order_columns(get_valid_columns(board))
    if not valid_columns:
        value, _ = evaluate_search_leaf(board)
        stats.leaf_evaluations += 1
        return None, value

    best_col = valid_columns[0]
    best_expected_value = -math.inf

    if level <= max_trace_depth:
        add_trace(lines, f"{indent}EXPECTED MAX depth={depth}")

    for intended_col in valid_columns:
        expected_value = 0.0
        outcomes = chance_outcomes(board, intended_col)

        for actual_col, probability in outcomes:
            child_board = copy_board(board)
            drop_piece(child_board, actual_col, COMPUTER)
            _, child_value = expected_minimize(
                child_board, depth - 1, stats, lines, level + 1, max_trace_depth
            )
            expected_value += probability * child_value
            if level <= max_trace_depth:
                add_trace(
                    lines,
                    f"{indent}    actual {actual_col} with p={probability:.2f} -> value {child_value:.2f}",
                )

        if level <= max_trace_depth:
            add_trace(lines, f"{indent}  intended {intended_col} -> expected value {expected_value:.2f}")

        if expected_value > best_expected_value:
            best_expected_value = expected_value
            best_col = intended_col

    if level <= max_trace_depth:
        add_trace(lines, f"{indent}EXPECTED MAX returns column={best_col}, value={best_expected_value:.2f}")

    return best_col, best_expected_value


def expected_minimize(
    board: Board,
    depth: int,
    stats: SearchStats,
    lines: List[str],
    level: int = 0,
    max_trace_depth: int = 3,
) -> Tuple[Optional[int], float]:
    stats.nodes_expanded += 1
    stats.max_depth_reached = max(stats.max_depth_reached, level)
    indent = "  " * level

    if depth == 0 or is_board_full(board):
        value, evaluation_name = evaluate_search_leaf(board)
        stats.leaf_evaluations += 1
        if level <= max_trace_depth:
            add_trace(lines, _leaf_trace(board, indent, value, evaluation_name))
        return None, value

    valid_columns = order_columns(get_valid_columns(board))
    if not valid_columns:
        value, _ = evaluate_search_leaf(board)
        stats.leaf_evaluations += 1
        return None, value

    best_col = valid_columns[0]
    best_expected_value = math.inf

    if level <= max_trace_depth:
        add_trace(lines, f"{indent}EXPECTED MIN depth={depth}")

    for intended_col in valid_columns:
        expected_value = 0.0
        outcomes = chance_outcomes(board, intended_col)

        for actual_col, probability in outcomes:
            child_board = copy_board(board)
            drop_piece(child_board, actual_col, HUMAN)
            _, child_value = expected_maximize(
                child_board, depth - 1, stats, lines, level + 1, max_trace_depth
            )
            expected_value += probability * child_value
            if level <= max_trace_depth:
                add_trace(
                    lines,
                    f"{indent}    actual {actual_col} with p={probability:.2f} -> value {child_value:.2f}",
                )

        if level <= max_trace_depth:
            add_trace(lines, f"{indent}  intended {intended_col} -> expected value {expected_value:.2f}")

        if expected_value < best_expected_value:
            best_expected_value = expected_value
            best_col = intended_col

    if level <= max_trace_depth:
        add_trace(lines, f"{indent}EXPECTED MIN returns column={best_col}, value={best_expected_value:.2f}")

    return best_col, best_expected_value


def choose_ai_move(
    board: Board,
    algorithm: str,
    k: int,
    trace: bool = True,
    max_trace_depth: int = 4,
    heuristic_fn: Optional[HeuristicFn] = None,
) -> SearchResult:
    global _active_heuristic
    if k < 1:
        raise ValueError("K must be at least 1 because the AI must search at least one move.")

    _active_heuristic = heuristic_fn if heuristic_fn is not None else heuristic
    algorithm = algorithm.lower().strip()
    stats = SearchStats()
    lines: List[str] = []
    effective_trace_depth = max_trace_depth if trace else -1

    start_time = perf_counter()

    if algorithm in {"minimax", "plain", "normal"}:
        best_col, value = maximize_plain(board, k, stats, lines, max_trace_depth=effective_trace_depth)
        algorithm_name = "Minimax"
    elif algorithm in {"alpha-beta", "alphabeta", "ab"}:
        best_col, value = maximize_ab(
            board, k, -math.inf, math.inf, stats, lines, max_trace_depth=effective_trace_depth
        )
        algorithm_name = "Alpha-Beta"
    elif algorithm in {"expected", "expected-minimax", "expectiminimax"}:
        best_col, value = expected_maximize(board, k, stats, lines, max_trace_depth=effective_trace_depth)
        algorithm_name = "Expected Minimax"
    else:
        raise ValueError("Unknown algorithm. Use: minimax, alpha-beta, or expected-minimax.")

    running_time = perf_counter() - start_time

    return SearchResult(
        algorithm=algorithm_name,
        best_column=best_col,
        value=value,
        nodes_expanded=stats.nodes_expanded,
        leaf_evaluations=stats.leaf_evaluations,
        pruned_branches=stats.pruned_branches,
        running_time=running_time,
        tree_trace=lines,
    )


def compare_minimax_and_alpha_beta(
    board: Board,
    k_values: Sequence[int] = (1, 2, 3, 4),
) -> List[Dict[str, float | int | str | None]]:
    rows: List[Dict[str, float | int | str | None]] = []

    for k in k_values:
        for algorithm in ["minimax", "alpha-beta"]:
            result = choose_ai_move(board, algorithm=algorithm, k=k, trace=False)
            rows.append(
                {
                    "K": k,
                    "Algorithm": result.algorithm,
                    "Best Column": result.best_column,
                    "Value": result.value,
                    "Nodes Expanded": result.nodes_expanded,
                    "Leaf Evaluations": result.leaf_evaluations,
                    "Pruned Branches": result.pruned_branches,
                    "Time (seconds)": result.running_time,
                }
            )

    return rows


def play_scripted_game(
    human_moves: Sequence[int],
    algorithm: str = "alpha-beta",
    k: int = 3,
    max_trace_depth: int = 2,
    stochastic_seed: int = 0,
    print_trees: bool = False,
    heuristic_fn: Optional[HeuristicFn] = None,
) -> Tuple[Board, List[Dict[str, object]]]:
    board = create_board()
    rng = random.Random(stochastic_seed)
    stochastic = algorithm.lower().strip() in {"expected", "expected-minimax", "expectiminimax"}
    move_log: List[Dict[str, object]] = []

    for turn_number, human_col in enumerate(human_moves, start=1):
        if is_board_full(board):
            break
        if not is_valid_column(board, human_col):
            raise ValueError(f"Invalid human move at turn {turn_number}: column {human_col}")

        actual_human_col = apply_game_move(board, human_col, HUMAN, stochastic=stochastic, rng=rng)
        move_log.append({"turn": turn_number, "player": "human", "intended": human_col, "actual": actual_human_col})

        if is_board_full(board):
            break

        result = choose_ai_move(
            board,
            algorithm=algorithm,
            k=k,
            trace=print_trees,
            max_trace_depth=max_trace_depth,
            heuristic_fn=heuristic_fn,
        )
        actual_computer_col = apply_game_move(board, result.best_column, COMPUTER, stochastic=stochastic, rng=rng)
        move_log.append(
            {
                "turn": turn_number,
                "player": "computer",
                "intended": result.best_column,
                "actual": actual_computer_col,
                "value": result.value,
                "nodes": result.nodes_expanded,
                "time": result.running_time,
            }
        )

        if print_trees:
            print(f"\nTurn {turn_number} AI tree trace:")
            for line in result.tree_trace:
                print(line)

    return board, move_log
