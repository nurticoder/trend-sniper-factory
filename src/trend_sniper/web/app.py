from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, HttpUrl, model_validator
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .store import Conflict, Missing, Store

STATIC = Path(__file__).parent / 'static'


class OpportunityInput(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    topic: str = Field(min_length=1, max_length=120)
    niche: str = Field(min_length=1, max_length=120)
    hypothesis: str = Field(default='', max_length=3000)
    source_url: HttpUrl | None = None
    evidence_notes: str = Field(default='', max_length=6000)
    observed_at: AwareDatetime | None = None
    archived: bool = False

    @model_validator(mode='after')
    def dated_evidence(self):
        if self.evidence_notes and not self.observed_at:
            raise ValueError('Evidence notes need a timezone-aware observation date')
        return self


class OpportunityUpdate(OpportunityInput):
    expected_revision: int = Field(ge=1)


class IdeaInput(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    title: str = Field(min_length=1, max_length=160)
    hook: str = Field(default='', max_length=1500)
    payoff: str = Field(default='', max_length=1500)
    script: str = Field(default='', max_length=20000)
    storyboard: str = Field(default='', max_length=12000)
    audio_notes: str = Field(default='', max_length=6000)
    stage: Literal['idea', 'writing', 'script_ready'] = 'idea'

    @model_validator(mode='after')
    def complete_brief(self):
        if self.stage == 'script_ready' and not all((self.hook, self.payoff, self.script, self.storyboard)):
            raise ValueError('Script ready requires a hook, payoff, script and storyboard')
        return self


class IdeaUpdate(IdeaInput):
    expected_revision: int = Field(ge=1)


def create_app(db_path: Path | None = None):
    store = Store(db_path or Path(os.environ.get('TSF_DB_PATH', 'local-data/control-room.sqlite3')))
    app = FastAPI(title='Trend Sniper Control Room', version='0.2.0', docs_url=None, redoc_url=None)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=['localhost', '127.0.0.1', '[::1]', 'testserver'])
    app.state.store = store

    @app.middleware('http')
    async def local_requests(request: Request, call_next):
        # No CORS, no external fetches, no remote content in the page. Prevent
        # browser cross-origin writes to this unauthenticated local-only tool.
        if request.method not in {'GET', 'HEAD', 'OPTIONS'}:
            origin = request.headers.get('origin')
            if origin and origin.rstrip('/') != str(request.base_url).rstrip('/'):
                return JSONResponse({'detail': 'Cross-origin writes are not allowed'}, status_code=403)
            if request.headers.get('sec-fetch-site') == 'cross-site':
                return JSONResponse({'detail': 'Cross-site writes are not allowed'}, status_code=403)
        response = await call_next(request)
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' https://i.ytimg.com; "
            "connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        if request.url.path.startswith('/api/'):
            response.headers['Cache-Control'] = 'no-store'
        return response

    @app.exception_handler(Missing)
    async def missing(request, error):
        return JSONResponse({'detail': 'Record not found'}, status_code=404)

    @app.exception_handler(Conflict)
    async def conflict(request, error):
        message = str(error) or 'This record changed in another tab. Reload before saving.'
        return JSONResponse({'detail': message}, status_code=409)

    @app.get('/api/health')
    def health():
        return {'status': 'ok', 'version': '0.2.0'}

    @app.get('/api/workspace')
    def workspace():
        return {**store.workspace(), 'capabilities': {
            'discovery': 'not_connected', 'script_generation': 'manual_only',
            'rendering': 'cli_only', 'youtube': 'not_connected', 'analytics': 'not_connected'}}

    @app.post('/api/opportunities', status_code=201)
    def create_opportunity(body: OpportunityInput):
        return store.create_opportunity(body.model_dump(mode='json'))

    @app.put('/api/opportunities/{key}')
    def update_opportunity(key: str, body: OpportunityUpdate):
        return store.update_opportunity(key, body.expected_revision,
                                        body.model_dump(mode='json', exclude={'expected_revision'}))

    @app.post('/api/opportunities/{key}/ideas', status_code=201)
    def create_idea(key: str, body: IdeaInput):
        return store.create_idea(key, body.model_dump())

    @app.put('/api/ideas/{key}')
    def update_idea(key: str, body: IdeaUpdate):
        return store.update_idea(key, body.expected_revision,
                                 body.model_dump(exclude={'expected_revision'}))

    @app.get('/api/ideas/{key}/versions')
    def versions(key: str):
        return store.versions(key)

    @app.get('/api/opportunities/{key}/export')
    def export(key: str):
        return JSONResponse(store.export(key), headers={
            'Content-Disposition': 'attachment; filename="production-brief.json"'})

    @app.get('/', include_in_schema=False)
    def index():
        return FileResponse(STATIC / 'discover.html')

    @app.get('/steam', include_in_schema=False)
    def steam():
        return FileResponse(STATIC / 'factory.html')

    @app.get('/studio', include_in_schema=False)
    def studio():
        return FileResponse(STATIC / 'index.html')

    app.mount('/static', StaticFiles(directory=STATIC), name='static')
    from .factory import install
    install(app, store)
    from .niches import install as install_niches
    install_niches(app, store)
    return app
