import asyncio
import json
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from threading import Lock

from fastapi import HTTPException, Query

from .formats import eligible
from .discovery import collect, SNAPSHOT


def install(app, store):
    cache = store.path.with_suffix('.niches.json')
    gate = Lock()
    status = {'error': None, 'scanning': False}

    def read():
        seed=json.loads(SNAPSHOT.read_text())
        if not cache.exists(): return seed
        saved=json.loads(cache.read_text())
        return max((saved,seed),key=lambda item:item['observed'])

    def refresh():
        if not gate.acquire(blocking=False):
            return
        status.update(scanning=True,error=None)
        try:
            snapshot = collect(read())
            temp = cache.with_suffix('.tmp')
            temp.write_text(json.dumps(snapshot))
            temp.replace(cache)
        except (OSError, ValueError) as error:
            status['error'] = str(error)
        finally:
            status['scanning'] = False
            gate.release()

    async def daily():
        while True:
            age = datetime.now(timezone.utc) - datetime.fromisoformat(read()['observed'])
            if age.total_seconds() >= 86400:
                await asyncio.to_thread(refresh)
            await asyncio.sleep(600)

    @asynccontextmanager
    async def lifespan(_):
        task = asyncio.create_task(daily())
        try:
            yield
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
    app.router.lifespan_context = lifespan
    with store.connection() as db:
        db.execute('CREATE TABLE IF NOT EXISTS chosen_niche(slot INTEGER PRIMARY KEY, snapshot TEXT NOT NULL)')

    @app.get('/api/niches')
    def niches(offset:int=Query(0,ge=0), category:str='', format:str=''):
        snapshot = read()
        all_cards = eligible(snapshot['cards'])
        entries = [c for c in all_cards if (not category or c['category']==category) and (not format or c['format']==format)]
        end = offset+9
        return dict(cards=entries[offset:end],next=end if end<len(entries) else None,total=len(entries),
                    categories=sorted({c['category'] for c in all_cards}),observed=snapshot['observed'],
                    failed=snapshot['failed'],sources=snapshot['sources'],**status)

    @app.get('/api/niche-selection')
    def selected():
        with store.connection() as db:
            row = db.execute('SELECT snapshot FROM chosen_niche WHERE slot=1').fetchone()
        return json.loads(row[0]) if row else None

    @app.post('/api/niche-selection')
    def select(key:str):
        card = next((c for c in eligible(read()['cards']) if c['id']==key),None)
        if card is None:
            raise HTTPException(404,'This observation has expired. Reload the feed.')
        with store.connection() as db:
            db.execute('INSERT OR REPLACE INTO chosen_niche VALUES (1,?)',(json.dumps(card),))
        return card


    @app.post('/api/niche-production', status_code=202)
    def produce_selected(key:str):
        card = selected()
        if not card or card['id'] != key or not eligible([card]):
            raise HTTPException(409,'Select this format before production.')
        return app.state.enqueue('format/'+key+'/'+card['observed'],{'title':card['name'],'recipe_card':card})
