"""Experimental automatic pregame player projections from recent public box scores.
Not trained, calibrated, sportsbook-linked, or validated. Public ESPN endpoints are unofficial.
"""
import json
import math
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from statistics import mean
from urllib.request import Request, urlopen

LEAGUES = {"NBA": ("basketball", "nba", 18), "NFL": ("football", "nfl", 55)}
MARKETS = {
    "NBA": {"PTS": "Points", "REB": "Rebounds", "AST": "Assists"},
    "NFL": {"YDS": "Passing / rushing / receiving yards", "REC": "Receptions"},
}

def _json(url):
    req = Request(url, headers={"User-Agent": "EDGE-AI-Research/0.3"})
    with urlopen(req, timeout=7) as response:
        return json.load(response)

def _recent_events(sport):
    category, league, days = LEAGUES[sport]
    today = datetime.now(timezone.utc).date()
    start = today - timedelta(days=days)
    url = f"https://site.api.espn.com/apis/site/v2/sports/{category}/{league}/scoreboard?dates={start:%Y%m%d}-{today:%Y%m%d}&limit=300"
    data = _json(url)
    events = [e for e in data.get("events", []) if (e.get("status") or {}).get("type", {}).get("state") == "post"]
    return sorted(events, key=lambda e: e.get("date", ""), reverse=True)

def _boxscore(sport, event_id):
    category, league, _ = LEAGUES[sport]
    return _json(f"https://site.api.espn.com/apis/site/v2/sports/{category}/{league}/summary?event={event_id}")

def _numeric(s):
    try:
        n = float(s)
        return n if math.isfinite(n) else None
    except (TypeError, ValueError):
        return None

def _parse(sport, summary):
    output = []
    for team in (summary.get("boxscore") or {}).get("players", []):
        team_info = team.get("team") or {}
        team_name = team_info.get("displayName", "")
        for group in team.get("statistics", []):
            labels = [str(x).upper() for x in group.get("labels", [])]
            group_name = str(group.get("name", "")).lower()
            for entry in group.get("athletes", []):
                athlete = entry.get("athlete") or {}
                name = athlete.get("displayName")
                values = entry.get("stats", [])
                if not name or len(values) != len(labels):
                    continue
                stats = dict(zip(labels, values))
                if sport == "NBA":
                    for key in ("PTS", "REB", "AST"):
                        value = _numeric(stats.get(key))
                        if value is not None:
                            output.append((team_name, name, MARKETS[sport][key], value))
                else:
                    if "passing" in group_name:
                        markets = [("YDS", "Passing yards")]
                    elif "rushing" in group_name:
                        markets = [("YDS", "Rushing yards"), ("TD", "Anytime touchdown (rushing/receiving)")]
                    elif "receiving" in group_name:
                        markets = [("YDS", "Receiving yards"), ("REC", "Receptions"), ("TD", "Anytime touchdown (rushing/receiving)")]
                    else:
                        markets = []
                    for key, market in markets:
                        value = _numeric(stats.get(key))
                        if value is not None:
                            output.append((team_name, name, market, value))
    return output

def projections(sport, upcoming, max_events=24):
    if sport not in LEAGUES:
        raise ValueError("Only NFL and NBA supported")
    team_names = {name for g in upcoming for name in (g.get("home"), g.get("away")) if name}
    if not team_names:
        return []
    events = _recent_events(sport)
    # Prefer games featuring teams with an upcoming matchup.
    relevant = [e for e in events if any(
        c.get("team", {}).get("displayName") in team_names
        for competition in e.get("competitions", [])
        for c in competition.get("competitors", [])
    )][:max_events]
    history = defaultdict(list)
    with ThreadPoolExecutor(max_workers=6) as pool:
        jobs = {pool.submit(_boxscore, sport, e["id"]): e for e in relevant}
        for job in as_completed(jobs):
            try:
                event = jobs[job]
                game_date = event.get("date", "")
                for team, name, market, value in _parse(sport, job.result()):
                    if team in team_names:
                        history[(team, name, market, game_date)].append(value)
            except Exception:
                continue
    combined = defaultdict(list)
    for (team, name, market, game_date), values in history.items():
        # Rush + receiving TDs are additive; other markets have one group per game.
        combined[(team, name, market)].append((game_date, sum(values)))
    rows = []
    for (team, name, market), samples in combined.items():
        samples.sort(reverse=True)
        values = [value for _, value in samples[:5]]
        if len(values) < 2:
            continue
        # Recency-weighted mean. Not a calibrated betting probability.
        weights = [0.75 ** i for i in range(len(values))]
        projected = sum(v*w for v, w in zip(values, weights)) / sum(weights)
        row = {"Team": team, "Player": name, "Market": market,
               "Projection": round(projected, 1), "Games sampled": len(values),
               "Last game": samples[0][0][:10]}
        if market.startswith("Anytime touchdown"):
            # Observed scoring frequency is NOT a calibrated probability.
            # Only games with an available rush/receiving stat row are counted.
            row["Recent TD game rate"] = f"{sum(v >= 1 for v in values)}/{len(values)}"
            row["Projection"] = round(sum((v >= 1)*w for v, w in zip(values, weights)) / sum(weights), 3)
        rows.append(row)
    return sorted(rows, key=lambda r: (r["Team"], r["Player"], r["Market"]))
