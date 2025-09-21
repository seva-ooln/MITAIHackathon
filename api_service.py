#!/usr/bin/env python3
"""
FastAPI service for Voice Meeting Bot with Zoom integration
Provides REST API endpoints for meeting management and analysis
"""
import asyncio
import sys
import os
from typing import Dict, List, Optional
from datetime import datetime
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse

# Add src to path
sys.path.append('src')
sys.path.append('.')

from zoom_integration_bridge import ZoomMeetingAnalyzer

app = FastAPI(
    title="Voice Meeting Bot API",
    description="API for AI-powered meeting facilitation with Zoom integration",
    version="1.0.0"
)

# Global analyzer instance
analyzer = None
active_meetings = {}

class MeetingStartRequest(BaseModel):
    meeting_url: str
    meeting_password: Optional[str] = None
    expected_participants: Optional[List[str]] = None
    bot_name: Optional[str] = "Alex"

class MeetingResponse(BaseModel):
    status: str
    message: str
    meeting_id: Optional[str] = None
    data: Optional[Dict] = None

@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    global analyzer
    analyzer = ZoomMeetingAnalyzer()
    print("🚀 Voice Meeting Bot API started")

@app.get("/")
async def root():
    """Health check endpoint"""
    return {"message": "Voice Meeting Bot API", "status": "running", "timestamp": datetime.now().isoformat()}

@app.get("/health")
async def health_check():
    """Detailed health check"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "active_meetings": len(active_meetings),
        "services": {
            "analyzer": analyzer is not None,
            "zoom_sdk": True  # Would check SDK availability
        }
    }

@app.post("/meetings/start", response_model=MeetingResponse)
async def start_meeting(request: MeetingStartRequest, background_tasks: BackgroundTasks):
    """Start analyzing a Zoom meeting"""
    global analyzer, active_meetings

    if not analyzer:
        raise HTTPException(status_code=500, detail="Analyzer not initialized")

    try:
        # Start meeting analysis
        result = await analyzer.start_zoom_analysis(
            meeting_url=request.meeting_url,
            meeting_password=request.meeting_password,
            expected_participants=request.expected_participants or []
        )

        if result["status"] == "success":
            meeting_id = result["meeting_id"]
            active_meetings[meeting_id] = {
                "start_time": datetime.now().isoformat(),
                "meeting_url": request.meeting_url,
                "participants": request.expected_participants or [],
                "status": "active"
            }

            return MeetingResponse(
                status="success",
                message="Meeting analysis started successfully",
                meeting_id=meeting_id,
                data=result
            )
        else:
            raise HTTPException(status_code=400, detail=result["message"])

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/meetings/{meeting_id}/status")
async def get_meeting_status(meeting_id: str):
    """Get current status of a meeting"""
    global active_meetings, analyzer

    if meeting_id not in active_meetings:
        raise HTTPException(status_code=404, detail="Meeting not found")

    meeting_info = active_meetings[meeting_id]

    # Get real-time status from analyzer
    if analyzer and analyzer.current_meeting_id == meeting_id:
        meeting_info.update({
            "is_analyzing": analyzer.is_analyzing,
            "introduction_active": analyzer.meeting_bot.introduction_active if analyzer.meeting_bot else False,
            "facilitator_active": analyzer.meeting_bot.facilitator_active if analyzer.meeting_bot else False,
            "participants_identified": len(analyzer.meeting_bot.participant_speakers) if analyzer.meeting_bot else 0,
            "conversation_length": len(analyzer.meeting_bot.conversation_history) if analyzer.meeting_bot else 0
        })

    return meeting_info

@app.get("/meetings/{meeting_id}/conversation")
async def get_conversation_history(meeting_id: str):
    """Get conversation history for a meeting"""
    global active_meetings, analyzer

    if meeting_id not in active_meetings:
        raise HTTPException(status_code=404, detail="Meeting not found")

    if analyzer and analyzer.current_meeting_id == meeting_id and analyzer.meeting_bot:
        return {
            "meeting_id": meeting_id,
            "conversation_history": analyzer.meeting_bot.conversation_history,
            "participants": analyzer.meeting_bot.participant_speakers,
            "speaker_stats": analyzer.meeting_bot.get_speaker_statistics()
        }
    else:
        return {"meeting_id": meeting_id, "conversation_history": [], "message": "No active conversation"}

@app.post("/meetings/{meeting_id}/stop", response_model=MeetingResponse)
async def stop_meeting(meeting_id: str):
    """Stop analyzing a meeting and get summary"""
    global active_meetings, analyzer

    if meeting_id not in active_meetings:
        raise HTTPException(status_code=404, detail="Meeting not found")

    if not analyzer or analyzer.current_meeting_id != meeting_id:
        raise HTTPException(status_code=400, detail="Meeting not currently being analyzed")

    try:
        # Stop analysis and get summary
        result = await analyzer.stop_analysis()

        # Update meeting record
        active_meetings[meeting_id].update({
            "status": "completed",
            "end_time": datetime.now().isoformat(),
            "summary": result.get("summary")
        })

        return MeetingResponse(
            status="success",
            message="Meeting analysis stopped and summary generated",
            meeting_id=meeting_id,
            data=result
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/meetings")
async def list_meetings():
    """List all meetings"""
    global active_meetings
    return {
        "meetings": active_meetings,
        "total": len(active_meetings)
    }

@app.delete("/meetings/{meeting_id}")
async def delete_meeting(meeting_id: str):
    """Delete meeting record"""
    global active_meetings

    if meeting_id not in active_meetings:
        raise HTTPException(status_code=404, detail="Meeting not found")

    # Stop analysis if still active
    if analyzer and analyzer.current_meeting_id == meeting_id:
        try:
            await analyzer.stop_analysis()
        except Exception as e:
            print(f"Error stopping analysis: {e}")

    # Remove from active meetings
    del active_meetings[meeting_id]

    return {"message": f"Meeting {meeting_id} deleted successfully"}

@app.post("/test/mock-meeting")
async def start_mock_meeting():
    """Start a mock meeting for testing without Zoom"""
    global analyzer

    if not analyzer:
        raise HTTPException(status_code=500, detail="Analyzer not initialized")

    try:
        # Use mock connection
        result = await analyzer.start_zoom_analysis(
            meeting_url="https://zoom.us/j/123456789",
            meeting_password=None,
            expected_participants=["Seva", "Sid", "Omar"]
        )

        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)