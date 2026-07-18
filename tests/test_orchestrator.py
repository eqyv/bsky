import unittest

from adapters.base import SocialAdapter
from core.orchestrator import Orchestrator


class FakeAdapter(SocialAdapter):
    def __init__(self, is_valid: bool):
        self.is_valid = is_valid

    def validate_credentials(self) -> bool:
        return self.is_valid

    def post(self, text, media_paths=None, media_urls=None):
        return {"success": True, "url": None, "error": None}


class OrchestratorValidationTests(unittest.TestCase):
    def test_retains_every_adapter_when_all_credentials_are_valid(self):
        orchestrator = Orchestrator()
        first = FakeAdapter(True)
        second = FakeAdapter(True)
        orchestrator.register_adapter(first)
        orchestrator.register_adapter(second)

        self.assertTrue(orchestrator.validate_all())
        self.assertEqual(orchestrator.adapters, [first, second])

    def test_removes_invalid_adapters_before_crossposting(self):
        orchestrator = Orchestrator()
        invalid = FakeAdapter(False)
        valid = FakeAdapter(True)
        orchestrator.register_adapter(invalid)
        orchestrator.register_adapter(valid)

        self.assertFalse(orchestrator.validate_all())
        self.assertEqual(orchestrator.adapters, [valid])

    def test_removes_all_adapters_when_every_validation_fails(self):
        orchestrator = Orchestrator()
        orchestrator.register_adapter(FakeAdapter(False))

        self.assertFalse(orchestrator.validate_all())
        self.assertEqual(orchestrator.adapters, [])


if __name__ == "__main__":
    unittest.main()
