"""Discover chart debuts and climbers using Valve's public data."""
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

CHART = 'https://api.steampowered.com/ISteamChartsService/GetMostPlayedGames/v1/'
SEED = Path(__file__).with_name('static') / 'observations.json'


def fetch(url):
    request = Request(url, headers={'User-Agent': 'TrendSniperFactory/1'})
    with urlopen(request, timeout=8) as response:
        return json.load(response)


def observe():
    chart = fetch(CHART)['response']
    choices = [r for r in chart['ranks'] if r['last_week_rank'] == -1 or r['last_week_rank'] > r['rank']]
    choices.sort(key=lambda r: (100 - r['rank'] if r['last_week_rank'] == -1 else r['last_week_rank'] - r['rank']), reverse=True)
    cards = []
    for r in choices[:6]:
        appid = int(r['appid'])
        try:
            game = fetch(f'https://store.steampowered.com/api/appdetails?appids={appid}&l=english')[str(appid)]['data']
        except (OSError, KeyError, ValueError):
            continue
        if game.get('type') != 'game':
            continue
        genres = [g['description'] for g in game.get('genres', []) if g['description'] != 'Free To Play']
        cards.append(dict(r, name=game['name'], niche=' / '.join(genres[:2]) or 'Gaming',
                          url=f'https://store.steampowered.com/app/{appid}/'))
        if len(cards) == 3:
            break
    if not cards:
        raise ValueError('No verified chart movers available')
    return {'date': datetime.fromtimestamp(chart['rollup_date'], timezone.utc).date().isoformat(),
            'source': CHART, 'cards': cards}


if __name__ == '__main__':
    SEED.write_text(json.dumps(observe(), indent=2, ensure_ascii=False))
