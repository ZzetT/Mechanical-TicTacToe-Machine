"""2D check of the lift of a dropped card with the EXISTING card geometry.

A dropped card hangs 18.4 mm down and 10.8 mm to the left of its rest
position.  When a lifter pushes it up, the ramps on the corridor floor (the
sloped polygon in create_field_sketch) slide the card back to the right and,
where a rod is in the way of the drop slot, push the rod to the centre.

For every pattern character and every rod position that can occur, this
script builds the field cutout, erodes it by the rod radius and checks that
the rod can travel from the hanging position to the rail at the expected
final position (card back at rest).  It also reports how far up the card is
when it is back at its rest x-position, which sizes the notch in the top-left
corner of the cards (the top-left rod must not stop a card that is still
shifted).  Needs shapely.

    python reset_mod/check_lift_geometry.py
"""
from shapely.geometry import Polygon, box, Point
from shapely.ops import unary_union
from shapely import affinity

# geometry of create_field_sketch (mm, field coordinates)
ROD_R, SHRINK = 2.5, 2.45
MARGIN_H, MARGIN_V, RAIL_W, SLOT_H, FALL, SLOT_W, FIELD_W = 8.0, 4.0, 25.0, 5.4, 18.0, 6.6, 41.0
SHIFT_LEFT, BOTTOM_SHIFT, RIGHT_CLEAR = 9.2, 9.2, 1.6
RAIL_Y1 = MARGIN_V + SLOT_H
X_O, X_C, X_X = MARGIN_H + ROD_R, MARGIN_H + RAIL_W / 2, MARGIN_H + RAIL_W - ROD_R
ROD_X = {'O': X_O, ' ': X_C, 'X': X_X}
SLOT_X = {'O': MARGIN_H, ' ': FIELD_W / 2 - SLOT_W / 2, 'X': FIELD_W - MARGIN_H - SLOT_W}
ALLOWED = {'O': 'O', ' ': ' ', 'X': 'X', '?': 'O X', '!': ' X', '*': 'O '}
ROD_Y_REST = MARGIN_V + ROD_R          # 6.5
CARD_SHIFT = 10.0 + (SLOT_W - 5.0) / 2  # 10.8: rod travel + play in the narrow corridor
HANG = FALL + 0.4                        # 18.4


def original_cutout(char, is_move):
    """Exactly the shapes create_field_sketch adds for one field."""
    parts = [box(MARGIN_H, MARGIN_V, MARGIN_H + RAIL_W, RAIL_Y1)]
    if char == '?':
        parts.append(box(MARGIN_H, MARGIN_V, MARGIN_H + RAIL_W, MARGIN_V + SLOT_H + FALL))
        off, width = SLOT_X['X'], SHIFT_LEFT + SLOT_W + RIGHT_CLEAR
    else:
        xs = [SLOT_X[c] for c in ALLOWED[char]]
        parts.append(box(min(xs), RAIL_Y1, max(xs) + SLOT_W, MARGIN_V + FALL))
        off = min(xs)
        if char == 'O' or char == 'X':
            width = SHIFT_LEFT + SLOT_W + RIGHT_CLEAR
        elif char == ' ':
            width = SLOT_W if is_move else SLOT_W + SHIFT_LEFT + BOTTOM_SHIFT + RIGHT_CLEAR
        elif char == '*':
            right = SLOT_X[' '] + SLOT_W
            width = (right if is_move else right + SHIFT_LEFT + BOTTOM_SHIFT + RIGHT_CLEAR) - off
        else:  # '!'
            width = SLOT_X['X'] + SLOT_W + SHIFT_LEFT + RIGHT_CLEAR - off
    y0 = MARGIN_V + FALL
    parts.append(Polygon([(off, y0), (off, y0 + SLOT_H), (off + width, y0 + SLOT_H),
                          (off + width, y0), (off + SLOT_W, y0 - FALL + SLOT_H + 5)]))
    return unary_union(parts)


def component(region, pt):
    polys = [region] if region.geom_type == 'Polygon' else [g for g in getattr(region, 'geoms', []) if g.geom_type == 'Polygon']
    for p in polys:
        if p.distance(Point(pt)) < 1e-6:
            return p
    return None


def main():
    ok = True
    still_shifted_until = -99.0   # highest "card can be unshifted from" over all fields
    print("field  rod  ->  result (rod ends at)      card back at rest x by cy =")
    for char in " OX!*?":
        for is_move in ([True, False] if char == ' ' else [False]):
            rods = 'O' if is_move else 'OX ' if char in ' ?!*' else ALLOWED[char]
            for rod in rods:
                cut = original_cutout(char, is_move)
                E = cut.buffer(-SHRINK, join_style=2)
                # relative coordinates (u, v) of the rod centre in the field; the rod
                # may move along the frame slot, the card may move right (cx -> 0)
                start = (ROD_X[rod] + CARD_SHIFT, ROD_Y_REST + HANG)
                # target: rod pinned by 'X'/'O'; pushed to the centre otherwise
                if char in 'XO':
                    target_rod = char
                elif rod in ALLOWED[char] and not is_move:
                    target_rod = rod          # accepted as is
                else:
                    target_rod = ' '          # ramp/slot pushes it to the centre
                goal = (ROD_X[target_rod], ROD_Y_REST)
                # rods only move towards the centre, the card only moves right:
                # restrict u to [goal_u, start_u] -> monotone path exists iff connected
                reach = E.intersection(box(min(start[0], goal[0]) - 0.01, -99, max(start[0], goal[0]) + 0.01, 99))
                comp = component(reach, start)
                good = comp is not None and comp.distance(Point(goal)) < 1e-6
                ok &= good
                # how far up can the card be while still shifted (cx < -0.4)?  Only
                # meaningful when the rod stays put: then cx = r - u, i.e. the card is
                # still shifted while u > r + 0.4; the lowest such point gives the
                # height at which the card is finally back at its rest x.
                # At which height does the ramp FORCE the card back to its rest x?
                # Treat the rod as fixed at its world position r (the clip holds it,
                # so the card moves before the rod does): cx = r - u, and at height v
                # the floor allows at most u_max(v); the card is forced right once
                # u_max(v) <= r + 0.4.  The lifter has no sideways force, so this is
                # the height at which the card really is unshifted.
                cy = None
                if comp is not None:
                    v = ROD_Y_REST + HANG
                    while v > ROD_Y_REST:
                        slice_ = comp.intersection(box(-99, v - 0.001, 99, v + 0.001))
                        if slice_.is_empty:
                            break
                        if slice_.bounds[2] <= ROD_X[rod] + 0.4:
                            cy = ROD_Y_REST - v
                            break
                        v -= 0.05
                if cy is not None:
                    still_shifted_until = max(still_shifted_until, cy)
                tag = "move" if is_move else "    "
                print(f" {char!r} {tag}  {rod!r}  ->  {'ok ' if good else 'FAIL'} (rod ends at {target_rod!r})     "
                      + (f"{cy:.1f}" if cy is not None else "never (card unshifted by other fields)"))
    print()
    print(f"worst case: the card is forced back to its rest x-position only when it has risen to cy = {still_shifted_until:.1f} mm;")
    print(f"the top-left rod reaches down to cy = -16.9, so the notch in the card's top-left corner must be")
    print(f"at least {16.9 + still_shifted_until:.1f} mm deep (plus margin).")
    print("ALL LIFT PATHS OK" if ok else "SOME LIFT PATHS FAIL")


if __name__ == "__main__":
    main()
