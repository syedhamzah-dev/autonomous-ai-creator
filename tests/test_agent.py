import pytest
from app.repositories.agent import agent_repository
from app.services.persona import PersonaService

def test_agent_init_success(client):
    """
    Test 1: Successful agent initialization returns a cryptographically valid agent ID.
    """
    payload = {
        "persona": {
            "name": "Ada",
            "domain": "AI Security"
        }
    }
    response = client.post("/api/agent/init", json=payload)
    assert response.status_code == 200
    
    data = response.json()
    assert "agentId" in data
    assert isinstance(data["agentId"], str)
    assert len(data["agentId"]) > 0

def test_agent_init_missing_persona(client):
    """
    Test 2: Request is rejected if persona configuration is completely missing.
    """
    payload = {}
    response = client.post("/api/agent/init", json=payload)
    assert response.status_code == 422

def test_agent_init_empty_name(client):
    """
    Test 3: Empty or whitespace-only persona name triggers a 422 validation error.
    """
    # Empty string
    payload_empty = {
        "persona": {
            "name": "",
            "domain": "AI Security"
        }
    }
    response = client.post("/api/agent/init", json=payload_empty)
    assert response.status_code == 422

    # Whitespace only
    payload_whitespace = {
        "persona": {
            "name": "    ",
            "domain": "AI Security"
        }
    }
    response = client.post("/api/agent/init", json=payload_whitespace)
    assert response.status_code == 422

def test_agent_init_empty_domain(client):
    """
    Test 4: Empty or whitespace-only persona domain triggers a 422 validation error.
    """
    # Empty string
    payload_empty = {
        "persona": {
            "name": "Ada",
            "domain": ""
        }
    }
    response = client.post("/api/agent/init", json=payload_empty)
    assert response.status_code == 422

    # Whitespace only
    payload_whitespace = {
        "persona": {
            "name": "Ada",
            "domain": "\t"
        }
    }
    response = client.post("/api/agent/init", json=payload_whitespace)
    assert response.status_code == 422

def test_agent_feed_success(client):
    """
    Test 5: An initialized agent returns an empty list of posts.
    """
    payload = {
        "persona": {
            "name": "Ada",
            "domain": "AI Security"
        }
    }
    init_res = client.post("/api/agent/init", json=payload)
    agent_id = init_res.json()["agentId"]

    feed_res = client.get(f"/api/agent/feed?agentId={agent_id}")
    assert feed_res.status_code == 200
    
    feed_data = feed_res.json()
    assert "posts" in feed_data
    assert feed_data["posts"] == []

def test_agent_feed_unknown_id(client):
    """
    Test 6: Querying feed of an unknown agent ID returns a 404 error.
    """
    response = client.get("/api/agent/feed?agentId=unknown-agent-id-999")
    assert response.status_code == 404

def test_agent_init_unique_ids(client):
    """
    Test 7: Sequential agent initializations generate unique agent IDs.
    """
    payload_ada = {
        "persona": {
            "name": "Ada",
            "domain": "AI Security"
        }
    }
    payload_bob = {
        "persona": {
            "name": "Bob",
            "domain": "DevOps"
        }
    }
    res_ada = client.post("/api/agent/init", json=payload_ada)
    res_bob = client.post("/api/agent/init", json=payload_bob)

    id_ada = res_ada.json()["agentId"]
    id_bob = res_bob.json()["agentId"]
    
    assert id_ada != id_bob


def test_persona_profile_creation_and_stability(client):
    """
    Test 8: Verify a detailed persona profile is created with all expected fields upon initialization
    and remains stable across multiple requests.
    """
    payload = {
        "persona": {
            "name": "Ada",
            "domain": "AI Security"
        }
    }
    response = client.post("/api/agent/init", json=payload)
    assert response.status_code == 200
    agent_id = response.json()["agentId"]

    # Retrieve profile from the repository
    profile_dict = agent_repository.get_agent_persona(agent_id)
    assert profile_dict is not None

    # Check required fields
    for field in ["name", "domain", "identity", "mission", "core_interests", "editorial_principles", "writing_style", "audience", "topics_to_avoid"]:
        assert field in profile_dict
        assert profile_dict[field] is not None

    # Check name and domain preservation
    assert profile_dict["name"] == "Ada"
    assert profile_dict["domain"] == "AI Security"

    # Check stability (identity remains unchanged)
    assert "AI Security researcher" in profile_dict["identity"]
    
    # Retrieve again and ensure identical state (stability)
    profile_dict_second = agent_repository.get_agent_persona(agent_id)
    assert profile_dict == profile_dict_second


def test_persona_profile_differentiation(client):
    """
    Test 9: Verify that different tech domains produce appropriately different profiles.
    """
    res_sec = client.post("/api/agent/init", json={
        "persona": {"name": "Alice", "domain": "AI Security"}
    })
    res_ml = client.post("/api/agent/init", json={
        "persona": {"name": "Bob", "domain": "Machine Learning"}
    })

    id_sec = res_sec.json()["agentId"]
    id_ml = res_ml.json()["agentId"]

    profile_sec = agent_repository.get_agent_persona(id_sec)
    profile_ml = agent_repository.get_agent_persona(id_ml)

    # Core interests and identities should differ significantly
    assert profile_sec["identity"] != profile_ml["identity"]
    assert profile_sec["mission"] != profile_ml["mission"]
    assert "AI security" in profile_sec["core_interests"]
    assert "MLOps" in profile_ml["core_interests"]


def test_persona_profile_dynamic_fallback(client):
    """
    Test 10: Verify that arbitrary technology domains dynamically generate valid profiles.
    """
    domain = "Quantum Computing"
    res = client.post("/api/agent/init", json={
        "persona": {"name": "Quinn", "domain": domain}
    })
    agent_id = res.json()["agentId"]
    profile = agent_repository.get_agent_persona(agent_id)

    assert profile["name"] == "Quinn"
    assert profile["domain"] == domain
    assert "Quantum Computing" in profile["identity"]
    assert "Quantum Computing" in profile["mission"]
    assert any("Quantum Computing" in interest or "quantum computing" in interest for interest in profile["core_interests"])
    assert len(profile["editorial_principles"]) > 0
    assert len(profile["writing_style"]) > 0


def test_persona_service_direct():
    """
    Test 11: Unit test the PersonaService directly to verify profile generation details.
    """
    service = PersonaService()
    
    # Predefined domain
    profile_dev = service.generate_profile("Dave", "Developer Advocate")
    assert profile_dev.name == "Dave"
    assert profile_dev.domain == "Developer Advocate"
    assert "Developer Advocate" in profile_dev.identity
    assert "developer experience (DX)" in profile_dev.core_interests
    
    # Custom/arbitrary domain
    profile_custom = service.generate_profile("Eve", "WebAssembly")
    assert profile_custom.name == "Eve"
    assert profile_custom.domain == "WebAssembly"
    assert "WebAssembly" in profile_custom.identity
    assert any("WebAssembly" in interest for interest in profile_custom.core_interests)
