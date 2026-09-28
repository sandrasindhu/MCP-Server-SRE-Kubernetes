def test_project_imports():
    from app.config import settings
    assert settings is not None
