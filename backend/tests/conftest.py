import pytest

from core.models import User, UserPageAccess


@pytest.fixture
def make_user(db):
    def _make(username="user", pages=(), superuser=False):
        user = User.objects.create_user(username=username, password="secret-pass-123")
        if superuser:
            user.is_superuser = True
            user.save(update_fields=["is_superuser"])
        for key in pages:
            UserPageAccess.objects.create(user=user, page_key=key)
        return user

    return _make
