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
