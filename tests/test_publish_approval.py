"""Offline security tests: never approve a deployment without GitHub API evidence."""
import io
import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from publish_approval import validate_approvals, verify_current_run

RUN_ENV = {
    "GITHUB_REPOSITORY":"derJosef/social-assets",
    "GITHUB_REF":"refs/heads/main",
    "GITHUB_EVENT_NAME":"workflow_dispatch",
    "GITHUB_RUN_ID":"37999990001",
    "GITHUB_TOKEN":"mock-token",
    "GITHUB_ACTOR":"derJosef",
    "GITHUB_TRIGGERING_ACTOR":"derJosef",
    "BUFFER_APPROVER_LOGINS":"independent-reviewer",
}
def approved(state="approved",user="independent-reviewer",environment="buffer-publish"):
    return [{"state":state,"user":{"login":user},"environments":[{"name":environment}]}]

class ApprovalsTests(unittest.TestCase):
    def validate(self,items,**kw):
        args=dict(actor="derJosef",triggering_actor="derJosef",
                  allowed_logins="independent-reviewer")
        args.update(kw)
        return validate_approvals(items,**args)

    def test_independent_approved_reviewer_passes(self):
        self.assertEqual(self.validate(approved()),"independent-reviewer")

    def test_no_approval_blocks(self):
        with self.assertRaisesRegex(RuntimeError,"Keine gültige"):
            self.validate([])

    def test_pending_blocks(self):
        with self.assertRaises(RuntimeError):
            self.validate(approved("pending"))

    def test_rejected_blocks(self):
        with self.assertRaises(RuntimeError):
            self.validate(approved("rejected"))

    def test_wrong_environment_blocks(self):
        with self.assertRaises(RuntimeError):
            self.validate(approved(environment="gate-test"))

    def test_wrong_reviewer_blocks(self):
        with self.assertRaises(RuntimeError):
            self.validate(approved(user="unknown-reviewer"))

    def test_self_approval_by_original_actor_blocks(self):
        with self.assertRaises(RuntimeError):
            self.validate(approved(user="derJosef"),allowed_logins="derJosef")

    def test_self_approval_by_triggering_actor_blocks(self):
        with self.assertRaises(RuntimeError):
            self.validate(approved(user="retry-account"),allowed_logins="retry-account",
                          triggering_actor="retry-account")

    def test_missing_approver_list_blocks(self):
        with self.assertRaises(RuntimeError):
            self.validate(approved(),allowed_logins="")

    def test_invalid_response_format_blocks(self):
        with self.assertRaises(RuntimeError):
            self.validate({"state":"approved"})

    def test_case_insensitive_login(self):
        self.assertEqual(self.validate(approved(user="Independent-Reviewer"),
                                       allowed_logins="independent-reviewer"),
                         "Independent-Reviewer")

    def test_approval_api_actual_run_and_token_bound(self):
        queries=[]
        def fake_open(req,timeout=0):
            queries.append((req.full_url,req.get_header("Authorization")))
            return io.BytesIO(json.dumps(approved()).encode("utf-8"))
        self.assertEqual(verify_current_run(environ=RUN_ENV,urlopen=fake_open),
                         "independent-reviewer")
        self.assertEqual(queries[0][0],"https://api.github.com/repos/derJosef/social-assets/actions/runs/37999990001/approvals")
        self.assertEqual(queries[0][1],"Bearer mock-token")

    def test_wrong_repo_or_event_fails_before_network(self):
        for key,value in (("GITHUB_REPOSITORY","evil/repo"),("GITHUB_REF","refs/heads/feature"),
                          ("GITHUB_EVENT_NAME","push"),("GITHUB_RUN_ID","1\nheader=bad"),
                          ("BUFFER_APPROVER_LOGINS","")):
            with self.subTest(key=key),self.assertRaises(RuntimeError):
                verify_current_run(environ={**RUN_ENV,key:value},
                                   urlopen=lambda *args,**kw:self.fail("network must not be used"))

    def test_api_denial_fails_closed(self):
        import urllib.error
        with self.assertRaisesRegex(RuntimeError,"gesperrt"):
            verify_current_run(environ=RUN_ENV,
                urlopen=lambda *args,**kw:(_ for _ in ()).throw(urllib.error.URLError("denied")))

if __name__=="__main__":
    unittest.main()
