import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
from trend_sniper.web.app import create_app
from trend_sniper.web.discovery import SNAPSHOT
from trend_sniper.web.formats import build, eligible


class ProductionFormats(unittest.TestCase):
    def test_all_advertised_formats_have_complete_scripts(self):
        cards=eligible(json.loads(SNAPSHOT.read_text())['cards'])
        with patch('trend_sniper.web.formats.urlopen',side_effect=OSError):
            for name in ['Family drama','Later-life letters','Block-world quest','News desk','Countdown']:
                card=next(c for c in cards if c['format']==name)
                topic=build(card)
                self.assertEqual(topic['format'],name)
                self.assertTrue(all(s['value'] for s in topic['scenes']))
                self.assertEqual(topic['audience'],'needs_review')

    @patch.dict('os.environ',{'TSF_COMMONS':'0'})
    def test_selected_format_reaches_finished_media(self):
        with tempfile.TemporaryDirectory() as tmp, TestClient(create_app(Path(tmp)/'qa.db')) as client:
            card=client.get('/api/niches?format=Countdown').json()['cards'][0]
            params={'key':card['id']}
            self.assertEqual(client.post('/api/niche-production',params=params).status_code,409)
            client.post('/api/niche-selection',params=params)
            job=client.post('/api/niche-production',params=params).json()['id']
            deadline=time.monotonic()+60
            while time.monotonic()<deadline:
                record=client.get('/api/productions').json()[0]
                if record['status'] in ('failed','ready'): break
                time.sleep(.1)
            self.assertEqual(record['status'],'ready',record)
            self.assertIn(b'ftyp',client.get(f'/api/productions/{job}/short.mp4').content[:32])

            report=self.client_report(client,base='/api/productions/'+job+'/')
            self.assertEqual(report['script_count'],100)
            self.assertEqual(len(report['covers']['candidates']),12)
            self.assertEqual(report['release']['state'],'proposal_only')
            self.assertTrue(all(s['visual_fallback'] for s in report['materials']['scenes']))

    def client_report(self,client,base):
        self.assertEqual(client.get(base+'cover.jpg').headers['content-type'],'image/jpeg')
        self.assertEqual(client.get(base+'cover-options.jpg').status_code,200)
        return client.get(base+'production-report.json').json()
