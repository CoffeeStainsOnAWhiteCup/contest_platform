import os

# No database connections are made by these tests.
os.environ["DATABASE_URL"] = "postgresql+asyncpg://test:test@localhost/auth_unit_unused"
os.environ["REDIS_URL"] = "redis://localhost:6379/15"
os.environ["JWT_SECRET_KEY"] = "unit-test-only-key-not-for-deployment-123456789"
os.environ["JWT_ACCESS_TOKEN_MINUTES"] = "30"
