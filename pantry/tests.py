from django.contrib.auth import get_user_model
from django.test import TestCase

from .models import PantryItem

User = get_user_model()


class PantryItemModelTests(TestCase):
    def test_create_and_str(self):
        user = User.objects.create_user(
            username="pat",
            email="pat@example.com",
            password="testpass123",
        )
        item = PantryItem.objects.create(
            user=user,
            name="Olive oil",
            category=PantryItem.Category.PANTRY,
            quantity="500 ml",
        )
        self.assertIn("Olive oil", str(item))
        self.assertEqual(item.user, user)
