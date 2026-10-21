"""Deterministic, network-free checks for the Slim-by-default CI policy."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_actions_runner_policy.py"
spec = importlib.util.spec_from_file_location("runner_policy", SCRIPT)
policy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(policy)


def workflow(runner="ubuntu-slim", job="offline"):
    return (
        "name: synthetic\non:\n  pull_request:\n"
        "permissions:\n  contents: read\n"
        f"jobs:\n  {job}:\n    runs-on: {runner}\n"
        "    steps:\n      - run: echo test\n"
    )


class TestRunnerPolicy(unittest.TestCase):
    def test_new_job_must_default_to_slim(self):
        self.assertEqual(policy.evaluate(workflow(), "fresh-workflow.yml"), [])

    def test_new_standard_job_is_rejected(self):
        self.assertTrue(policy.evaluate(workflow("ubuntu-24.04"), "fresh-workflow.yml"))

    def test_existing_legacy_job_remains_allowed(self):
        self.assertEqual(
            policy.evaluate(workflow("ubuntu-24.04", "create-drafts"), "buffer-auto-drafts.yml"), []
        )

    def test_new_standard_job_inside_legacy_file_is_rejected(self):
        self.assertTrue(
            policy.evaluate(workflow("ubuntu-24.04", "brand-new"), "buffer-auto-drafts.yml")
        )

    def test_standard_rollback_from_slim_is_rejected(self):
        self.assertTrue(
            policy.evaluate(workflow("ubuntu-latest", "offline"), "brief-approval-offline-pr.yml")
        )

    def test_nonstandard_runner_expression_requires_review(self):
        self.assertTrue(policy.evaluate(workflow("${{ inputs.runner }}"), "fresh-workflow.yml"))

    def test_repository_files_are_parseable_and_in_policy(self):
        self.assertEqual(policy.scan(Path(__file__).resolve().parents[1]), [])

    def test_tracked_workflow_without_runner_is_rejected(self):
        self.assertTrue(policy.evaluate("name: test\njobs:\n  build:\n    steps:\n      - run: echo x\n", "no-runner.yml"))

    def test_reusable_job_is_allowed(self):
        source = "name: x\njobs:\n  reused:\n    uses: org/repo/.github/workflows/a.yml@main\n"
        self.assertEqual(policy.evaluate(source, "reusable.yml"), [])


if __name__ == "__main__":
    unittest.main()
