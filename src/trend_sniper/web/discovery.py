"""Group public YouTube feed observations by repeatable editorial angle."""
import json
import re
import statistics
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET

SNAPSHOT = Path(__file__).with_name('static') / 'niches.json'
# One default format per source, plus topic-specific formats inferred from titles.
SOURCES = [
 ('Drama','Family twist stories','UC_hK9fOxyy_TM8FJGXIyG8Q'),
 ('News','Daily news bulletins','UC16niRr50-MSBwiO3YDb3RA'),
 ('Gaming','Roblox community challenges','UCm-X6o81nRsXQTmqpyArkBQ'),
 ('Gaming','Roblox update explainers','UCxsk7hqE_CwZWGEJEkGanbA'),
 ('Gaming','Minecraft redstone experiments','UChFur_NwVSbUozOcF_F2kMg'),
 ('Animation','Family animation storytelling','UCVzLLZkDuFGAE2BGdBuBNBg'),
 ('Movies','Movie trailer breakdowns','UCi8e0iOVk1fEOogdfu4YgfA'),
 ('Movies','Visual effects explained','UCSpFnDQr88xCZ80N-X7t0nQ'),
 ('Education','Physics mysteries','UCHnyfMqiRRG1u-2MsSQLbXA'),
 ('Education','Animated science explainers','UCsXVk37bltHxD1rDPwtNM8Q'),
 ('Education','Visual math puzzles','UCYO_jab_esuFRV4b17AJtAw'),
 ('Technology','Consumer tech comparisons','UCBJycsmduvYEL83R_U4JriQ'),
 ('Food','Cooking technique breakdowns','UCJHA_jMfCvEnv-3kRjTCQXw'),
 ('Space','Space mission explainers','UCLA_DiR1FfKNvjuUpBHmylQ'),
 ('Sports','Basketball tactics and highlights analysis','UCWJ2lWNubArHWmf3FIHbfcQ'),
 ('Music','Music theory through songs','UCJquYOG5EL82sKTfH9aMA9Q'),
 ('Making','Engineering challenge explainers','UCY1kMZp36IQSyNx_9h4mpCg'),
 ('Nature','Wildlife behavior stories','UCwmZiChSryoWQCZMIQezgTg'),
 ('History','Animated history stories','UCNIuvl7V8zACPpTmmNIqP2A'),
 ('Travel','Geography and destination explainers','UCmmPgObSUPw1HL2lq6H4ffA'),
]
TOPICS = {
 'Gaming':['Scary Shawarma Kiosk','The Hollow','Final Life','DONT SPLASH','Blox Fruits','Steal a Brainrot','Grow a Garden','Brookhaven','Dress to Impress','99 Nights','Adopt Me','redstone','Hermitcraft','hardcore','speedrun','Minecraft Live'],
 'Movies':['Marvel','Spider-Man','horror','animation','stunts','CGI','Star Wars'],
 'Education':['quantum','black holes','probability','geometry','gravity','biology'],
 'Technology':['iPhone','Android','camera','MacBook','headphones'],
 'Food':['pasta','pizza','steak','bread','dessert'],
 'Space':['Artemis','Mars','Moon','ISS'],
 'Sports':['Lakers','Warriors','Celtics','dunk'],
}
NS={'a':'http://www.w3.org/2005/Atom','yt':'http://www.youtube.com/xml/schemas/2015','m':'http://search.yahoo.com/mrss/'}


def scan_source(source, now):
    category, default, channel = source
    url='https://www.youtube.com/feeds/videos.xml?channel_id='+channel
    with urlopen(Request(url,headers={'User-Agent':'TrendSniperFactory/1'}),timeout=8) as response:
        feed=ET.fromstring(response.read(2_000_000))
    groups={}
    for entry in feed.findall('a:entry',NS):
        video=entry.findtext('yt:videoId','',NS)
        if not re.fullmatch(r'[\w-]{11}',video): continue
        title=entry.findtext('a:title','',NS)
        published=entry.findtext('a:published','',NS)
        age=(now-datetime.fromisoformat(published.replace('Z','+00:00'))).total_seconds()/86400
        if not 0<=age<=90: continue
        stats=entry.find('.//m:statistics',NS)
        views=int(stats.get('views',0)) if stats is not None else None
        tag=next((t for t in TOPICS.get(category,[]) if t.lower() in title.lower()),None)
        name=f'{tag} · {default}' if tag else default
        groups.setdefault(name,[]).append(dict(video=video,title=title,views=views,published=published,
            pace=round(views/max(1,age)) if views is not None else None))
    result=[]
    for name,items in groups.items():
        items.sort(key=lambda v:v['pace'] or 0,reverse=True)
        pace=round(statistics.median(v['pace'] for v in items if v['pace'] is not None)) if any(v['pace'] is not None for v in items) else None
        result.append(dict(id=channel+'/'+name,category=category,name=name,channel=feed.findtext('a:title','',NS),
            count=len(items),pace=pace,examples=items[:3],observed=now.isoformat()))
    return result


def collect(previous=None):
    now=datetime.now(timezone.utc)
    def read(source):
        try: return scan_source(source,now),None
        except (OSError,ValueError,ET.ParseError) as error:
            return [],source[2]
    with ThreadPoolExecutor(max_workers=6) as pool:
        results=list(pool.map(read,SOURCES))
    cards=[c for group,_ in results for c in group]
    failed={key for _,key in results if key}
    if not cards: raise ValueError('No recent source observations available')
    history={c['id']:c for c in (previous or {}).get('cards',[])}
    for card in cards:
        prior=history.get(card['id'])
        if prior:
            days=(now-datetime.fromisoformat(prior['observed'])).total_seconds()/86400
            counts={v['video']:v['views'] for v in prior['examples'] if v['views'] is not None}
            gains=[(v['views']-counts[v['video']])/days for v in card['examples']
                   if .5<=days<=3 and v['video'] in counts and v['views'] is not None and v['views']>=counts[v['video']]]
            if gains:
                card['daily_gain']=round(statistics.median(gains))
    cards.extend(c for c in (previous or {}).get('cards',[]) if c['id'].split('/')[0] in failed)
    # Interleave categories so the biggest channel cannot occupy the entire feed.
    lanes={}
    for card in sorted(cards,key=lambda c:c['pace'] or 0,reverse=True):
        lanes.setdefault(card['category'],[]).append(card)
    cards=[]
    while any(lanes.values()):
        for lane in lanes.values():
            if lane: cards.append(lane.pop(0))
    return dict(observed=now.isoformat(),sources=len(SOURCES)-len(failed),failed=len(failed),cards=cards)


if __name__=='__main__':
    SNAPSHOT.write_text(json.dumps(collect(),ensure_ascii=False))
