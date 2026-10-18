def _assign_ranks(entries):
    """Assign sports-convention shared ranks to a pre-sorted entries list.

    Two entries are tied when they share the same total_points, count_exact,
    and count_gap (the full sort key). Tied entries receive the same rank;
    the next rank after a tie of size k skips k-1 positions (1, 1, 3, ...).
    Mutates entries in-place and returns the list.
    """
    rank = 1
    for i, entry in enumerate(entries):
        if i > 0:
            prev = entries[i - 1]
            if (entry['total_points'] != prev['total_points'] or
                    entry['count_exact'] != prev['count_exact'] or
                    entry['count_gap'] != prev['count_gap']):
                rank = i + 1
        entry['rank'] = rank
    return entries
