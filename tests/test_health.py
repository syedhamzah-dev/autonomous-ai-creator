def test_health_check(client):
    """
    Test that GET /health returns status 200 and indicates the service is healthy.
    """
    response = client.get("/health")
    assert response.status_code == 200
    
    data = response.json()
    assert data["status"] == "healthy"
    assert "app_name" in data
    assert "app_env" in data


def test_global_exception_handler():
    """
    Test that generic server-side errors are caught by the global handler
    and formatted safely without trace leaks.
    """
    from fastapi.testclient import TestClient
    from app.main import app
    from unittest.mock import patch

    with TestClient(app, raise_server_exceptions=False) as test_client:
        with patch("app.api.endpoints.health.settings", new=None):
            response = test_client.get("/health")
            assert response.status_code == 500
            
            data = response.json()
            assert data["detail"] == "Internal Server Error. Please contact server administration."
