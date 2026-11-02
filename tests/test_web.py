import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from trend_sniper.web.app import create_app


class ControlRoomTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name) / 'app.sqlite3'
        self.client = TestClient(create_app(self.path))

    def tearDown(self):
        self.client.close()
        self.directory.cleanup()

    def opportunity(self, **extra):
        response = self.client.post('/api/opportunities', json={
            'topic': 'DONT SPLASH', 'niche': 'Co-op horror fans', **extra})
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def test_persistence_after_new_app_instance_and_no_fake_integrations(self):
        first = self.client.get('/api/workspace').json()
        self.assertEqual(first['opportunities'], [])
        self.assertEqual(first['ideas'], [])
        self.assertEqual(first['capabilities']['script_generation'], 'manual_only')
        self.assertEqual(first['capabilities']['discovery'], 'not_connected')
        saved = self.opportunity(hypothesis='An unverified hypothesis')
        with TestClient(create_app(self.path)) as reopened:
            result = reopened.get('/api/workspace').json()['opportunities'][0]
        self.assertEqual(saved, result)
        self.assertEqual(result['evidence_origin'], 'manual')

    def test_evidence_requires_date_and_valid_reference(self):
        base = {'topic': 'Game', 'niche': 'Audience', 'evidence_notes': 'Observed something'}
        for bad in ({}, {'observed_at': '2026-11-03T12:00:00'},
                    {'observed_at': '2026-11-03T12:00:00Z', 'source_url': 'javascript:alert(1)'}):
            self.assertEqual(self.client.post('/api/opportunities', json={**base, **bad}).status_code, 422)
        saved = self.opportunity(evidence_notes='A manually observed count',
                                 observed_at='2026-11-03T12:00:00+08:00',
                                 source_url='https://www.roblox.com/')
        self.assertEqual(saved['evidence_origin'], 'manual')
        self.assertEqual(self.client.post('/api/opportunities', json={'topic':' ', 'niche':'x'}).status_code, 422)
        self.assertEqual(self.client.post('/api/opportunities', json={'topic':'x', 'niche':'x', 'verified': True}).status_code, 422)

    def test_script_readiness_history_and_export(self):
        parent = self.opportunity()
        route = f"/api/opportunities/{parent['id']}/ideas"
        response = self.client.post(route, json={'title':'Original route puzzle'})
        self.assertEqual(response.status_code, 201)
        idea = response.json()
        update_route = f"/api/ideas/{idea['id']}"
        incomplete = {'title':'Original route puzzle', 'stage':'script_ready', 'expected_revision':1}
        self.assertEqual(self.client.put(update_route, json=incomplete).status_code, 422)
        update = {**incomplete, 'hook':'Which route?', 'payoff':'The quiet route wins',
                  'script':'Original fictional puzzle narration', 'storyboard':'0–3s: draw two paths',
                  'audio_notes':'3s: owned synthesized cue'}
        updated = self.client.put(update_route, json=update)
        self.assertEqual(updated.status_code, 200, updated.text)
        self.assertEqual(updated.json()['revision'], 2)
        self.assertEqual(self.client.put(update_route, json=update).status_code, 409)
        history = self.client.get(update_route + '/versions').json()
        self.assertEqual([v['revision'] for v in history], [2, 1])
        self.assertEqual(history[1]['script'], '')
        exported = self.client.get(f"/api/opportunities/{parent['id']}/export")
        self.assertIn('attachment', exported.headers['content-disposition'])
        self.assertEqual(exported.json()['ideas'][0]['script'], update['script'])
        self.assertEqual(exported.json()['opportunity']['id'], parent['id'])
        self.assertEqual(exported.json()['ideas'][0]['generation_method'], 'manual')

    def test_opportunity_revision_conflict_and_archiving(self):
        parent = self.opportunity()
        url = f"/api/opportunities/{parent['id']}"
        update = {'topic':'Edited', 'niche':'Audience', 'archived':True, 'expected_revision':1}
        self.assertEqual(self.client.put(url, json=update).status_code, 200)
        self.assertEqual(self.client.put(url, json=update).status_code, 409)
        result = self.client.post(url+'/ideas', json={'title':'Blocked while archived'})
        self.assertEqual(result.status_code, 409)
        update['expected_revision'] = 2
        update['archived'] = False
        self.assertEqual(self.client.put(url, json=update).status_code, 200)
        self.assertEqual(self.client.post(url+'/ideas', json={'title':'Allowed'}).status_code, 201)
        self.assertEqual(self.client.get('/api/ideas/missing/versions').status_code, 404)
        self.assertEqual(self.client.post('/api/opportunities/missing/ideas', json={'title':'x'}).status_code, 404)

    def test_local_browser_boundary_and_static_assets(self):
        for origin in ('https://evil.example', 'http://localhost:9999'):
            response = self.client.post('/api/opportunities', json={'topic':'x','niche':'y'}, headers={'Origin':origin})
            self.assertEqual(response.status_code, 403)
        self.assertEqual(self.client.get('/api/workspace', headers={'host':'evil.example'}).status_code, 400)
        page = self.client.get('/')
        self.assertEqual(page.status_code, 200)
        self.assertIn('The control room', page.text)
        self.assertIn("script-src 'self'", page.headers['content-security-policy'])
        for name in ('app.js', 'style.css', 'favicon.svg'):
            self.assertEqual(self.client.get('/static/'+name).status_code, 200)
        self.assertEqual(self.client.get('/api/workspace').headers['cache-control'], 'no-store')


if __name__ == '__main__':
    unittest.main()
