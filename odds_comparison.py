"""Compare one manually recorded two-way quote against a baseline projection."""

from math import isfinite

from engine import devig_two_way, expected_value, implied_probability, market_probability


PROJECTION_NOTE = (
    'Recent box-score projections can omit games and do not account for injuries, '
    'starting status or sportsbook lines. Standard deviation is supplied manually.'
)


def compare_row(row, row_number):
    result = {key: value for key, value in row.items() if key is not None}
    warnings = ['Unexpected extra CSV fields'] if None in row else []

    def required(field):
        value = (row.get(field) or '').strip()
        if not value:
            warnings.append(f'Missing {field}')
        return value

    def numeric(field, parse=float):
        value = required(field)
        if not value:
            return None
        try:
            number = parse(value)
            if not isfinite(number) or (parse is int and abs(number) < 100):
                raise ValueError
            return number
        except (ValueError, OverflowError):
            warnings.append(f'Invalid {field}')
            return None

    required('sport')
    book = required('sportsbook')
    if row.get('projection_source') == 'recent_box_scores':
        required('event')
    market = required('market').lower()
    side = required('selection').lower()
    distribution = required('distribution').capitalize()
    line = numeric('line')
    mean = numeric('mean')
    sd = numeric('sd') if distribution != 'Poisson' or (row.get('sd') or '').strip() else 0
    odds = numeric('odds', int)
    opposite = numeric('opposing_odds', int)

    valid_market = market in ('player_prop', 'moneyline', 'spread', 'total')
    valid_side = side in ('over', 'under')
    valid_line = line is not None and (market != 'moneyline' or line == 0)
    if market and not valid_market:
        warnings.append('Invalid market')
    if side and not valid_side:
        warnings.append('Selection must be over or under')
    if line is not None and not valid_line:
        warnings.append('Moneyline requires line 0')
    if distribution and distribution not in ('Normal', 'Poisson'):
        warnings.append('Distribution must be Normal or Poisson')

    p = None
    if (valid_market and valid_side and valid_line and mean is not None
            and sd is not None and distribution in ('Normal', 'Poisson')):
        try:
            p = market_probability(market, side, line, mean, sd, distribution)
        except (ValueError, OverflowError) as exc:
            warnings.append(f'Model inputs: {exc}')

    fair = None
    if (book and valid_market and valid_side and valid_line
            and odds is not None and opposite is not None):
        fair, _ = devig_two_way(odds, opposite)
    same_event = row.get('projection_source') != 'recent_box_scores' or (row.get('event') or '').strip()

    result.update(
        csv_row=row_number,
        mean=mean,
        line=line,
        model_probability=round(p, 4) if p is not None else None,
        implied_probability=round(implied_probability(odds), 4) if odds is not None else None,
        expected_return=round(expected_value(p, odds), 4)
        if same_event and p is not None and odds is not None else None,
        no_vig_probability_pct=round(100 * fair, 2) if fair is not None else None,
        model_edge_pp=round(100 * (p - fair), 2)
        if same_event and p is not None and fair is not None else None,
        warning='; '.join(warnings),
    )
    return result
