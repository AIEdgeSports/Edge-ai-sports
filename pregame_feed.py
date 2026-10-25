"""Public ESPN scoreboard discovery (unofficial API, not guaranteed or licensed for resale)."""
import json
from datetime import datetime, timedelta, timezone
from urllib.request import Request, urlopen

SPORTS = {"NFL": ("football", "nfl"), "NBA": ("basketball", "nba"), "MLB": ("baseball", "mlb")}
def upcoming_games(sport, days=7):
    if sport not in SPORTS:
        raise ValueError("Unsupported sport")
    category, league = SPORTS[sport]
    start = datetime.now(timezone.utc).date()
    end = start + timedelta(days=days)
    url = f"https://site.api.espn.com/apis/site/v2/sports/{category}/{league}/scoreboard?dates={start:%Y%m%d}-{end:%Y%m%d}&limit=250"
    request = Request(url, headers={"User-Agent": "EDGE-AI-Research/0.2"})
    with urlopen(request, timeout=12) as response:
        data = json.load(response)
    games = []
    for event in data.get("events", []):
        competitions = event.get("competitions") or []
        if not competitions:
            continue
        game = competitions[0]
        status = (event.get("status") or {}).get("type", {}).get("state")
        if status != "pre":
            continue
        teams = {c.get("homeAway"): c.get("team", {}).get("displayName", "") for c in game.get("competitors", [])}
        games.append({"sport": sport, "start_utc": event.get("date", ""), "away": teams.get("away", ""), "home": teams.get("home", ""), "event_id": event.get("id", "")})
    return sorted(games, key=lambda g: g["start_utc"])
