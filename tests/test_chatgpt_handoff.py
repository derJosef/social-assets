"""No-network tests for ChatGPT campaign handoff on an isolated review branch."""
from __future__ import annotations
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from validate_chatgpt_handoff import validate
from social_orchestrator import Blocked

def sample():
    return {
        "format_version":1,"brand":"ai-agent-builder",
        "campaign_id":"2026-10-09-bridge-contract-test","execution_mode":"drafts",
        "topic":"Praktische Kontrolle von Datenflüssen beim KI-Agenten-Einsatz im Mittelstand.",
        "sources":[{"url":"https://example.org/research","published_at":"2026-10-01"},
                   {"url":"https://example.net/report","published_at":"2026-10-02"}],
        "posting_sources":["https://buffer.com/resources/abc","https://sproutsocial.com/insights/abc"],
        "prepared_content":{
            "posts":{k:("Beispiel für "+k+". Prüfe die Datenflüsse und dokumentiere die Ergebnisse. ")*6
                     for k in ("linkedin","facebook","instagram")},
            "visual":{"badge":"KI PRÜFEN","headline":"DATENFLÜSSE",
                      "subtitle":"Kontrollierte KI-Agenten im Mittelstand",
                      "cards":[{"title":"DATEN","description":"Erlaubte Eingaben definieren"},
                               {"title":"WEGE","description":"Dienstleister nachvollziehen"},
                               {"title":"KONTROLLE","description":"Freigaben und Rechte prüfen"}],
                      "closing":"Erst prüfen, dann automatisieren."},
            "six_hats":{k:"Diese Perspektive beschreibt konkrete Risiken und Chancen eines KI-Agenten."
                        for k in ("white","red","black","yellow","green","blue")},
            "risks":["Unvollständige Quellenlage"]
        }
    }

class ContractTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.path="orchestration/briefs/2026-10-09-bridge-contract-test.json"
        (self.root/self.path).parent.mkdir(parents=True)
        self.record=sample()
        self.write()
    def write(self):
        (self.root/self.path).write_text(json.dumps(self.record),encoding="utf-8")
    def test_complete_subscription_handoff_is_accepted_offline(self):
        r=validate(self.path,self.root)
        self.assertEqual(r["status"],"offline_structure_pass")
        self.assertFalse(r["automatic_publication"])
    def test_model_generation_not_accepted_as_subscription_handoff(self):
        del self.record["prepared_content"];self.write()
        with self.assertRaisesRegex(Blocked,"fertig redigierte"):
            validate(self.path,self.root)
    def test_wrong_brand_rejected(self):
        self.record["brand"]="picturefix";self.write()
        with self.assertRaises((ValueError,Blocked)):
            validate(self.path,self.root)
    def test_missing_channel_rejected(self):
        del self.record["prepared_content"]["posts"]["instagram"];self.write()
        with self.assertRaises((ValueError,Blocked)):
            validate(self.path,self.root)
    def test_duplicate_campaign_blocked(self):
        (self.root/"campaign-manifests").mkdir()
        (self.root/"campaign-manifests/2026-10-09-bridge-contract-test.json").write_text("{}")
        with self.assertRaisesRegex(Blocked,"existiert|Kampagnen"):
            validate(self.path,self.root)
    def test_no_path_traversal(self):
        with self.assertRaises((ValueError,Blocked)):
            validate("orchestration/briefs/../bad.json",self.root)

if __name__=="__main__":
    unittest.main()
