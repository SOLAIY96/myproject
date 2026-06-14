import pytest
from django.contrib.auth import get_user_model

User = get_user_model()

@pytest.fixture
def user(db):
    return User.objects.create_user(
        username="testuser",
        password="testpass"
   )
 
def test_user_creation(user):
    assert user.username == "testuser" 
