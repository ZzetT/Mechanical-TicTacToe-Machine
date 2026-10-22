"""Check that the dropped cards of every possible game can be lifted back by a
lifter that pushes each card independently (see RESET_PLAN.md).

Model of one card being lifted while shifted 10.8 mm to the left:
  - the ramps on the corridor floor slide the card back to the right and push
    a rod that sits in the way to the centre:  ' ' pushes X and O rods to C,
    '*' pushes an X rod to C, '!' pushes an O rod to C;
  - the walls of the drop slot drag a rod back to the pinned position:
    'X' needs the rod at X, 'O' needs it at O, the card's own move field
    drags its O rod back to C;
  - a card that is still hanging holds its own move rod at O (narrow corridor)
    and holds the rods of its 'O' fields at O (its corridor ends at 25.4 mm).
A card can rise when none of the rods it has to move is held by another card
that is still down.  Cards that dropped together on the same board state have
the same move and never work against each other, so they are lifted as a group.  The script plays every game against the table and, after
every half-move (a child may reset at any time), checks that the dropped cards
can all rise in SOME order (greedy: lift any card that is free), and that the
reverse drop order always works.

    python reset_mod/check_reset_order.py [rules.json]
"""
import json, os, sys

WIN = [(0, 1, 2), (3, 4, 5), (6, 7, 8), (0, 3, 6), (1, 4, 7), (2, 5, 8), (0, 4, 8), (2, 4, 6)]
ALLOWED = {'O': 'O', ' ': ' ', 'X': 'X', '?': 'O X', '!': ' X', '*': 'O '}


def matches(pattern, board):
    return all(b in ALLOWED[p] for p, b in zip(pattern, board))


def won(b, p):
    return any(all(b[i] == p for i in w) for w in WIN)


def needs_push_to_c(char, rod, is_move):
    """Does this field push/drag its rod to the centre when the card rises?"""
    if is_move:
        return rod != ' '
    return (char == ' ' and rod != ' ') or (char == '*' and rod == 'X') or (char == '!' and rod == 'O')


def lift_order(dropped, board, order):
    """Lift the card groups in the given order; return (ok, final rods).
    dropped/order: lists of groups, a group = the cards that dropped together."""
    rods = list(board)
    down = list(dropped)
    for group in order:
        held = set()
        for other in down:
            if other is group:
                continue
            for op, om in other:
                held.add(om)                                      # own move rod at O
                held.update(i for i in range(9) if op[i] == 'O')  # 'O' fields hold their rod
        for pattern, move in group:
            for i in range(9):
                c = pattern[i]
                if needs_push_to_c(c, rods[i], i == move):
                    if i in held:
                        return False, rods
                    rods[i] = ' '
                elif c == 'X':
                    rods[i] = 'X'      # slot walls drag it back if a ramp moved it
                elif c == 'O':
                    if rods[i] != 'O':
                        return False, rods
        down.remove(group)
    return True, rods


def greedy_lift(dropped, board):
    rods = list(board)
    down = list(dropped)
    while down:
        progressed = False
        for group in list(down):
            ok, new_rods = lift_order(down, rods, [group])
            if ok:
                rods, progressed = new_rods, True
                down.remove(group)
                break
        if not progressed:
            return False
    return True


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(here, "..", "minimized_rules.json")
    rules = list(json.load(open(path)).items())
    stats = {"resets": 0, "max_dropped": 0}
    problems = []

    def check(board, dropped, path):
        stats["resets"] += 1
        stats["max_dropped"] = max(stats["max_dropped"], sum(len(g) for g in dropped))
        if not dropped:
            return
        ok_rev, rods = lift_order(dropped, board, list(reversed(dropped)))
        if not ok_rev:
            problems.append(("reverse order fails", board, path))
        elif 'O' in rods:
            problems.append(("an O rod survived the reset", board, path, rods))
        if not greedy_lift(dropped, board):
            problems.append(("greedy any-order deadlocks", board, path))

    def play(b, dropped, path):
        for i in range(9):
            if b[i] != ' ':
                continue
            nb = b[:i] + 'X' + b[i + 1:]
            np = path + [('X', i)]
            if won(nb, 'X'):
                problems.append(("X wins", nb, np)); continue
            check(nb, dropped, np)
            if ' ' not in nb:
                continue
            hits = [(p, m) for p, m in rules if matches(p, nb)]
            moves = {m for _, m in hits}
            if len(moves) != 1:
                problems.append(("no/ambiguous reply", nb, np)); continue
            m = moves.pop()
            ob = nb[:m] + 'O' + nb[m + 1:]
            nd = dropped + [hits]
            check(ob, nd, np + [('O', m)])
            if won(ob, 'O') or ' ' not in ob:
                continue
            play(ob, nd, np + [('O', m)])

    play(' ' * 9, [], [])
    print(f"{len(rules)} cards; {stats['resets']} reset points checked, "
          f"up to {stats['max_dropped']} cards down at once")
    print("(two or three cards can drop on the same board; they are lifted as one group)")
    if problems:
        from collections import Counter
        print("PROBLEMS:", Counter(p[0] for p in problems))
        for p in problems[:10]:
            print("  ", p)
        sys.exit(1)
    print("ALL CHECKS PASSED: reverse drop order always lifts, greedy any-order never deadlocks,"
          " and every O rod ends up in the middle")


if __name__ == "__main__":
    main()
