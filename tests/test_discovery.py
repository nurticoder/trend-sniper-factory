import tempfile
import unittest
from pathlib import Path
from fastapi.testclient import TestClient
from trend_sniper.web.app import create_app


class NicheSelection(unittest.TestCase):
    def test_scroll_filter_choose_and_reopen(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'test.db'
            with TestClient(create_app(path)) as client:
                seen=set()
                offset=0
                while offset is not None:
                    data=client.get('/api/niches',params={'offset':offset}).json()
                    ids={c['id'] for c in data['cards']}
                    self.assertFalse(seen & ids)
                    seen.update(ids)
                    offset=data['next']
                self.assertEqual(len(seen),data['total'])
                games=client.get('/api/niches?category=Gaming').json()['cards']
                self.assertTrue(games)
                self.assertTrue(all(c['category']=='Gaming' and c['examples'] for c in games))
                picked=client.post('/api/niche-selection',params={'key':games[0]['id']}).json()
                self.assertEqual(picked,games[0])
                self.assertEqual(client.get('/api/productions').json(),[])
            with TestClient(create_app(path)) as reopened:
                self.assertEqual(reopened.get('/api/niche-selection').json(),picked)
