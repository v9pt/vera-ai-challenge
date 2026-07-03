import os
import sys
import unittest
from fastapi.testclient import TestClient
from unittest.mock import patch

# Ensure the app folder is in python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app

class TestBotTick(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.client.post("/v1/teardown")

    def tearDown(self):
        self.client.post("/v1/teardown")

    def push_category(self):
        res = self.client.post("/v1/context", json={
            "scope": "category",
            "context_id": "dentists",
            "version": 1,
            "payload": {
                "slug": "dentists",
                "voice": {
                    "tone": "peer_clinical",
                    "taboos": []
                }
            }
        })
        self.assertEqual(res.status_code, 200)

    def test_1_merchant_only(self):
        """Test 1: Merchant only -> Expected: Generic recommendation"""
        self.push_category()
        
        # Push merchant only (no signals, no trigger)
        res = self.client.post("/v1/context", json={
            "scope": "merchant",
            "context_id": "m_test_1",
            "version": 1,
            "payload": {
                "identity": {
                    "name": "Dr. Meera's Clinic",
                    "owner_first_name": "Meera",
                    "locality": "Lajpat Nagar",
                    "languages": ["en"]
                },
                "category_slug": "dentists"
            }
        })
        self.assertEqual(res.status_code, 200)

        # Call /v1/tick with merchant_id directly
        res = self.client.post("/v1/tick", json={
            "merchant_id": "m_test_1"
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("actions", data)
        self.assertEqual(len(data["actions"]), 1)
        action = data["actions"][0]
        self.assertEqual(action["merchant_id"], "m_test_1")
        body_lower = action["body"].lower()
        self.assertTrue(len(body_lower) > 20)
        self.assertTrue("meera" in body_lower)

    def test_2_merchant_plus_trigger(self):
        """Test 2: Merchant + Trigger -> Expected: Trial reminder"""
        self.push_category()

        # Push merchant
        self.client.post("/v1/context", json={
            "scope": "merchant",
            "context_id": "m_test_2",
            "version": 1,
            "payload": {
                "identity": {
                    "name": "Meera Clinic",
                    "owner_first_name": "Meera",
                    "locality": "Lajpat"
                },
                "category_slug": "dentists",
                "signals": ["trial_ending_soon"]
            }
        })

        # Push trigger context (expected trigger structure)
        self.client.post("/v1/context", json={
            "scope": "trigger",
            "context_id": "trg_test_2",
            "version": 1,
            "payload": {
                "kind": "trial_ending_soon",
                "merchant_id": "m_test_2",
                "payload": {
                    "days_remaining": 3
                }
            }
        })

        res = self.client.post("/v1/tick", json={
            "available_triggers": ["trg_test_2"]
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(len(data["actions"]), 1)
        action = data["actions"][0]
        body_lower = action["body"].lower()
        self.assertTrue(any(k in body_lower for k in ["trial", "ends", "ending", "soon", "concludes", "days"]))

    def test_3_low_ctr(self):
        """Test 3: Low CTR -> Expected: Performance improvement recommendation"""
        self.push_category()

        self.client.post("/v1/context", json={
            "scope": "merchant",
            "context_id": "m_test_3",
            "version": 1,
            "payload": {
                "identity": {
                    "name": "Meera Clinic",
                    "owner_first_name": "Meera"
                },
                "category_slug": "dentists",
                "signals": ["perf_dip_severe"]
            }
        })

        res = self.client.post("/v1/tick", json={
            "merchant_id": "m_test_3"
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(len(data["actions"]), 1)
        action = data["actions"][0]
        body_lower = action["body"].lower()
        self.assertTrue(any(k in body_lower for k in ["performance", "audit", "drop", "opportunities", "visibility", "decline", "lapsed", "growth"]))

    def test_4_expired_subscription(self):
        """Test 4: Expired subscription -> Expected: Renewal recommendation"""
        self.push_category()

        self.client.post("/v1/context", json={
            "scope": "merchant",
            "context_id": "m_test_4",
            "version": 1,
            "payload": {
                "identity": {
                    "name": "Meera Clinic",
                    "owner_first_name": "Meera"
                },
                "category_slug": "dentists",
                "signals": ["renewal_due_soon"]
            }
        })

        res = self.client.post("/v1/tick", json={
            "merchant_id": "m_test_4"
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(len(data["actions"]), 1)
        action = data["actions"][0]
        body_lower = action["body"].lower()
        self.assertTrue(any(k in body_lower for k in ["renew", "subscription", "plan", "opportunities", "expires", "strategy"]))

    def test_5_llm_unavailable(self):
        """Test 5: LLM unavailable -> Expected: Fallback template"""
        self.push_category()

        self.client.post("/v1/context", json={
            "scope": "merchant",
            "context_id": "m_test_5",
            "version": 1,
            "payload": {
                "identity": {
                    "name": "Meera Clinic",
                    "owner_first_name": "Meera"
                },
                "category_slug": "dentists"
            }
        })

        # Mock generate_message to raise an error
        with patch("services.message_builder.generate_message", side_effect=Exception("API limit exceeded")):
            res = self.client.post("/v1/tick", json={
                "merchant_id": "m_test_5"
            })
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(len(data["actions"]), 1)
        body_lower = data["actions"][0]["body"].lower()
        self.assertTrue("quick review" in body_lower or "opportunities" in body_lower)

    def test_6_unknown_trigger(self):
        """Test 6: Unknown trigger -> Expected: General recommendation"""
        self.push_category()

        self.client.post("/v1/context", json={
            "scope": "merchant",
            "context_id": "m_test_6",
            "version": 1,
            "payload": {
                "identity": {
                    "name": "Meera Clinic",
                    "owner_first_name": "Meera"
                },
                "category_slug": "dentists"
            }
        })

        # Push trigger context with unknown trigger kind
        self.client.post("/v1/context", json={
            "scope": "trigger",
            "context_id": "trg_test_6",
            "version": 1,
            "payload": {
                "kind": "some_completely_new_trigger_kind",
                "merchant_id": "m_test_6",
                "payload": {}
            }
        })

        res = self.client.post("/v1/tick", json={
            "available_triggers": ["trg_test_6"]
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(len(data["actions"]), 1)
        body_lower = data["actions"][0]["body"].lower()
        self.assertTrue(any(k in body_lower for k in ["opportunities", "growth", "review", "trigger", "impact", "assess", "opportunity"]))

if __name__ == "__main__":
    unittest.main()
