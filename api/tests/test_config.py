import pytest
from pydantic import ValidationError

from curo.config import DEV_JWT_SECRET, Settings

ALL = ("public_data", "video", "embedding", "llm", "storage", "monitoring", "auth")


def test_mock_mode_selects_every_mock():
    s = Settings(mock_mode=True)
    assert {name: s.provider(name) for name in ALL} == {
        "public_data": "mock",
        "video": "mock",
        "embedding": "mock",
        "llm": "mock",
        "storage": "local",
        "monitoring": "noop",
        "auth": "local",
    }


def test_real_mode_selects_real_vendors():
    s = Settings(mock_mode=False, supabase_jwt_secret="x" * 32)
    assert s.provider("public_data") == "apify"
    assert s.provider("video") == "gemini"
    assert s.provider("embedding") == "gemini"
    assert s.provider("llm") == "claude"
    assert s.provider("storage") == "supabase"
    assert s.provider("auth") == "supabase"
    assert Settings(mock_mode=False, public_data_primary="brightdata").provider("public_data") == (
        "brightdata"
    )


def test_per_provider_override_beats_mock_mode():
    s = Settings(mock_mode=True, public_data_provider="apify", llm_provider="claude")
    assert s.provider("public_data") == "apify"
    assert s.provider("llm") == "claude"
    assert s.provider("video") == "mock"


def test_supabase_shim_follows_auth_provider():
    assert Settings(mock_mode=True).use_supabase_shim is True
    assert Settings(mock_mode=False).use_supabase_shim is False
    assert Settings(mock_mode=False, apply_supabase_shim=True).use_supabase_shim is True


def test_dev_secret_only_outside_production():
    assert Settings(app_env="development").supabase_jwt_secret == DEV_JWT_SECRET
    with pytest.raises(ValidationError):
        Settings(app_env="production")
    with pytest.raises(ValidationError):
        Settings(app_env="production", supabase_jwt_secret=DEV_JWT_SECRET)


def test_embedding_dim_is_fixed_at_768():
    with pytest.raises(ValidationError):
        Settings(embedding_dim=1024)
