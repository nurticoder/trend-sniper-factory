"""Production recipes. Reference videos are research only; no media is imported."""
import json
import math
from urllib.request import Request, urlopen

from PIL import Image, ImageDraw

from ..render import font, wrapped


def card_is_letter(card):
    return card['id'].endswith('/letters')


def legacy_recipe(c):
    category=c['category']
    if card_is_letter(c):
        return 'Later-life letters', 'Original fiction for older viewers. Family-story demand is an adjacent signal.'
    if category=='Drama':
        return 'Family drama', 'An original four-scene family drama with a final reveal.'
    if category=='History':
        return 'Later-life letters', 'A fictional memory told by an older adult through four letters.'
    if category=='News':
        return 'News desk', 'A dated bulletin of newly published news reports, with attribution.'
    if category=='Gaming':
        return 'Block-world quest', 'A fictional block-world mini adventure with a choice and payoff.'
    return 'Countdown', 'A visual countdown of the observed uploads by recorded views.'


def recipe(c):
    if c['category']=='Gaming':
        return 'Gaming guide', 'An original mechanic explanation or strategy within this game niche. Draft facts and visuals need review.'
    return 'Topic explainer', 'An original explanation within this niche. Draft facts and visuals need review.'


def eligible(cards):
    results=[]
    for card in cards:
        kind,pitch=recipe(card)
        results.append(dict(card,format=kind,pitch=pitch))
    return sorted(results,key=lambda c:c.get('daily_gain',c['pace']) or 0,reverse=True)


def fiction(kind,subject):
    prompt=(f'Write an original {kind} microfiction inspired by this broad subject: {subject}. '
            'Four short consecutive story beats, first person, concrete opening, complication, decision, payoff. '
            'For later-life letters use a dignified older protagonist. For block-world quests use an original child-friendly puzzle. '
            'No real people, game lore, copyrighted characters or quotations. Each beat must be under 100 characters.')
    schema={'type':'object','properties':{'beats':{'type':'array','minItems':4,'maxItems':4,
            'items':{'type':'string','minLength':1,'maxLength':100}}},'required':['beats']}
    payload=dict(model='llama3.2:3b',stream=False,format=schema,prompt=prompt,options={'num_predict':300})
    try:
        req=Request('http://127.0.0.1:11434/api/generate',data=json.dumps(payload).encode(),
                    headers={'Content-Type':'application/json'})
        with urlopen(req,timeout=75) as response:
            beats=json.loads(json.load(response)['response'])['beats']
        if len(beats)==4 and all(isinstance(b,str) and 0<len(b.strip())<=100 for b in beats):
            return beats,'Local AI fiction'
    except (OSError,ValueError,KeyError,TypeError):
        pass
    scripts={
        'Later-life letters':['At seventy, I finally opened the letter addressed to my younger self.',
            'Inside was a train ticket and a sketch of our old station.',
            'I took the morning train. A woman on the platform held the other half.',
            'My sister smiled. “I hoped you kept yours.”'],
        'Family drama':['Dad left us an empty photo frame. My brother wanted to sell it.',
            'Behind the backing I found two tiny brass keys.',
            'We opened the shed together. Our childhood bikes were waiting.',
            'This time we took a picture before we rode away.'],
        'Block-world quest':['One bridge. Three blocks. A lantern flickers under the middle tile.',
            'I toss a pebble. The bright block vanishes.',
            'I turn the lantern around. Its shadow points to a hidden step.',
            'Across safely. I leave the lantern for the next player.']}
    return scripts[kind],'Built-in original story'


def build(card, *, analytics=False):
    if not analytics:
        from ..production.content import develop
        return develop(card)
    return legacy_build({**card,'category':'News' if card['category']=='News' else 'Analytics'})


def legacy_build(card):
    kind,pitch=legacy_recipe(card)
    items=card['examples']
    if kind in ('Countdown','News desk'):
        news=kind=='News desk'
        entries=sorted(items,key=(lambda v:v['published']) if news else (lambda v:v['views'] or 0),reverse=True)
        if not news: entries=list(reversed([v for v in entries if v['views'] is not None]))
        scenes=[(v['published'][:10] if news else f'#{len(entries)-i}',v['title'],
                 card['channel'] if news else f"{v['views']:,} recorded views") for i,v in enumerate(entries)]
        method='Source-based composition'
    else:
        beats,method=fiction(kind,card['name'])
        scenes=[(f'PART {i+1:02d}',b,'Original fiction') for i,b in enumerate(beats)]
    title=f"{kind} | {card['name']}"[:100]
    links=['https://www.youtube.com/watch?v='+v['video'] for v in items]
    return dict(id=card['id'],title=title,description=title+'\n'+method+'\nReferences:\n'+'\n'.join(links),
        source_url=links[0],trend_status='Channel sample '+card['observed'],hashtags=['Shorts'],
        audience='needs_review',format=kind,method=method,date=card['observed'][:10],
        scenes=[dict(heading=h,value=v,caption=caption,seconds=max(4,min(9,math.ceil(len(v.split())/2.5))),
                     mode='reveal' if i==len(scenes)-1 else 'choice') for i,(h,v,caption) in enumerate(scenes)])


def frame(topic,index,local,elapsed,duration):
    kind=topic['format']
    warm=kind in ('Later-life letters','Family drama')
    bg=(40,26,38) if warm else (15,20,44)
    accent=(254,206,151) if warm else (128,220,255)
    im=Image.new('RGB',(720,1280),bg)
    d=ImageDraw.Draw(im)
    scene=topic['scenes'][index]
    if warm:
        y=275+int(12*math.sin(local))
        d.rounded_rectangle((110,y,610,y+240),18,fill=(110,66,72))
        d.line([(110,y+12),(360,y+155),(610,y+12)],fill=accent,width=5)
    elif kind=='Block-world quest':
        for n in range(6):
            x=70+n*100
            y=450-(n%3)*48
            d.rectangle((x,y,x+80,y+44),fill=(61,173,145))
        x=70+int((elapsed*85)%500)
        d.rectangle((x,310+int(35*math.sin(elapsed*3)),x+48,365+int(35*math.sin(elapsed*3))),fill=accent)
    else:
        for n in range(9):
            x=65+n*68
            d.rectangle((x,480-int(65+65*math.sin(n+elapsed)),x+40,480),fill=(85,105,188))
    d.text((52,85),kind.upper(),font=font(34),fill=accent)
    d.text((55,558),scene['heading'],font=font(36),fill=accent)
    wrapped(d,scene['value'],650,42,'white',575)
    wrapped(d,scene['caption'],1025,26,accent,560)
    d.text((55,1155),topic['date'],font=font(20),fill='white')
    d.rectangle((55,1200,56+600*elapsed/duration,1208),fill=accent)
    return im
