from fastapi import APIRouter, HTTPException, Query, status
from app.schemas.agent import AgentInitRequest, AgentInitResponse, FeedResponse
from app.services.agent import AgentService

router = APIRouter()
agent_service = AgentService()

@router.post("/init", response_model=AgentInitResponse)
async def initialize_agent(payload: AgentInitRequest):
    """
    Initialize an autonomous AI agent with a custom technology persona.
    """
    agent_id = agent_service.initialize_agent(payload.persona)
    return AgentInitResponse(agentId=agent_id)

@router.get("/feed", response_model=FeedResponse)
async def get_agent_feed(agentId: str = Query(..., alias="agentId", description="The ID of the initialized agent.")):
    """
    Retrieve the publishing feed for an initialized agent.
    """
    try:
        posts = agent_service.get_agent_feed(agentId)
        return FeedResponse(posts=posts)
    except KeyError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )

@router.get("/status")
async def get_agent_status(agentId: str = Query(..., alias="agentId", description="The ID of the initialized agent.")):
    """
    Retrieve status and persona metadata for the initialized agent.
    """
    try:
        persona = agent_service.get_agent_persona(agentId)
        posts = agent_service.get_agent_feed(agentId)
        return {
            "agentId": agentId,
            "status": "active",
            "persona": persona,
            "postsCount": len(posts)
        }
    except KeyError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
