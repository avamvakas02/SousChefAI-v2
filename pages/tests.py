from django.test import TestCase


class PagesSmokeTests(TestCase):
    def test_landing_page_loads(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)

    def test_privacy_policy_page_loads(self):
        response = self.client.get("/privacy/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Privacy Policy")
