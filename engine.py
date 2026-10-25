"""Transparent baseline probability utilities; not a trained or validated forecasting model."""
import math

def american_to_decimal(odds):
    odds = int(odds)
    if odds == 0: raise ValueError('American odds cannot be zero')
    return 1 + (odds / 100 if odds > 0 else 100 / abs(odds))

def implied_probability(odds):
    return 1 / american_to_decimal(odds)

def normal_cdf(x, mean, sd):
    if sd <= 0: raise ValueError('Standard deviation must be positive')
    return 0.5 * (1 + math.erf((x - mean) / (sd * math.sqrt(2))))

def poisson_cdf(k, lam):
    if lam <= 0: raise ValueError('Poisson mean must be positive')
    if k < 0: return 0.0
    term = math.exp(-lam)
    total = term
    for i in range(1, k + 1):
        term *= lam / i
        total += term
    return min(1.0, total)

def market_probability(market, side, line, mean, sd, distribution):
    """Normal continuity correction for integer props; Poisson for counts.
    For spreads: mean = projected home margin, line = home spread (e.g. -3.5),
    side='over' means home covers, side='under' means home fails to cover.
    For totals: side over/under refers to total score.
    For moneyline: line=0, side over=home wins, under=away wins.
    Push probability is excluded for integer spread/total lines by conditioning on non-push outcomes.
    """
    line = float(line); mean = float(mean)
    if market == 'moneyline':
        line = 0
    if distribution == 'Poisson':
        if market in ('moneyline','spread'): raise ValueError('Poisson is for count props/totals, not margin models')
        if line.is_integer():
            low = poisson_cdf(int(line)-1, mean)
            push = poisson_cdf(int(line), mean) - low
            over = 1 - poisson_cdf(int(line), mean)
            under = low
            return (over if side=='over' else under) / max(1e-12, 1-push)
        under = poisson_cdf(math.floor(line), mean)
        return 1-under if side=='over' else under
    if market == 'spread':
        threshold = -line
    else:
        threshold = line
    if market == 'moneyline': threshold = 0
    # Continuous normal approximation; push mass is zero.
    under = normal_cdf(threshold, mean, sd)
    return 1-under if side=='over' else under

def expected_value(probability, odds):
    return probability * (american_to_decimal(odds)-1) - (1-probability)

def devig_two_way(odds_a, odds_b):
    a,b=implied_probability(odds_a),implied_probability(odds_b)
    return a/(a+b),b/(a+b)
