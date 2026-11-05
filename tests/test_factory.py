import tempfile
import time
import unittest
from pathlib import Path
from fastapi.testclient import TestClient
from trend_sniper.web.app import create_app


class FactoryJourney(unittest.TestCase):
    def test_observation_to_playable_artifact(self):
        with tempfile.TemporaryDirectory() as tmp, TestClient(create_app(Path(tmp)/'qa.db')) as client:
            feed = client.get('/api/radar').json()
            card = feed['cards'][0]
            route = f"/api/radar/{card['appid']}/produce"
            job = client.post(route).json()['id']
            self.assertEqual(client.post(route).json()['id'], job)
            end = time.monotonic()+120
            while time.monotonic()<end:
                result = client.get('/api/productions').json()[0]
                if result['status'] in ('ready','failed'):
                    break
                time.sleep(.2)
            self.assertEqual(result['status'],'ready',result)
            base = '/api/productions/'+job+'/'
            self.assertIn(b'ftyp', client.get(base+'short.mp4').content[:32])
            self.assertIn(card['name'], client.get(base+'metadata.txt').text)
            self.assertIn(str(card['rank']), client.get(base+'script.json').text)
