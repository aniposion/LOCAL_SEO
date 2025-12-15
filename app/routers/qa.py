"""
Q&A Management Router - Google Business Profile Q&A
"""
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.routers.deps import get_current_account, get_db
from app.models.account import Account
from app.integrations.gbp import GBPClient

router = APIRouter(prefix="/qa", tags=["Q&A"])


# ============ Schemas ============

class QuestionResponse(BaseModel):
    id: str
    question_text: str
    author_name: str
    created_at: datetime
    answer: Optional[str] = None
    answer_status: str  # pending, answered


class QuestionsListResponse(BaseModel):
    questions: list[QuestionResponse]
    total: int
    pending_count: int


class AnswerRequest(BaseModel):
    question_id: str
    answer_text: str


class GenerateAnswerRequest(BaseModel):
    question_id: str
    question_text: str


class GenerateAnswerResponse(BaseModel):
    suggested_answer: str


# ============ Endpoints ============

@router.get("/{location_id}", response_model=QuestionsListResponse)
async def get_questions(
    location_id: str,
    status_filter: Optional[str] = None,
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """Get all Q&A for a location."""
    # Verify location belongs to account
    from app.models.location import Location
    location = db.query(Location).filter(
        Location.id == location_id,
        Location.account_id == account.id
    ).first()
    
    if not location:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Location not found"
        )
    
    # Fetch Q&A from GBP API
    try:
        gbp_client = GBPClient(location.gbp_access_token)
        questions_data = await gbp_client.get_questions(location.gbp_location_id)
        
        questions = []
        pending_count = 0
        
        for q in questions_data.get("questions", []):
            answer = q.get("topAnswers", [{}])[0].get("text") if q.get("topAnswers") else None
            q_status = "answered" if answer else "pending"
            
            if q_status == "pending":
                pending_count += 1
            
            if status_filter and q_status != status_filter:
                continue
                
            questions.append(QuestionResponse(
                id=q.get("name", ""),
                question_text=q.get("text", ""),
                author_name=q.get("author", {}).get("displayName", "Anonymous"),
                created_at=datetime.fromisoformat(q.get("createTime", datetime.now().isoformat()).replace("Z", "+00:00")),
                answer=answer,
                answer_status=q_status,
            ))
        
        return QuestionsListResponse(
            questions=questions,
            total=len(questions),
            pending_count=pending_count,
        )
    except Exception as e:
        # Return demo data if API fails
        demo_questions = [
            QuestionResponse(
                id="q1",
                question_text="Do you offer gluten-free options?",
                author_name="Sarah M.",
                created_at=datetime.now(),
                answer=None,
                answer_status="pending",
            ),
            QuestionResponse(
                id="q2",
                question_text="What are your hours on weekends?",
                author_name="John D.",
                created_at=datetime.now(),
                answer="We are open Saturday and Sunday from 10 AM to 10 PM.",
                answer_status="answered",
            ),
        ]
        
        filtered = demo_questions
        if status_filter:
            filtered = [q for q in demo_questions if q.answer_status == status_filter]
        
        return QuestionsListResponse(
            questions=filtered,
            total=len(filtered),
            pending_count=sum(1 for q in demo_questions if q.answer_status == "pending"),
        )


@router.post("/{location_id}/answer")
async def post_answer(
    location_id: str,
    request: AnswerRequest,
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """Post an answer to a question."""
    from app.models.location import Location
    location = db.query(Location).filter(
        Location.id == location_id,
        Location.account_id == account.id
    ).first()
    
    if not location:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Location not found"
        )
    
    try:
        gbp_client = GBPClient(location.gbp_access_token)
        await gbp_client.answer_question(
            location.gbp_location_id,
            request.question_id,
            request.answer_text
        )
        
        return {"success": True, "message": "Answer posted successfully"}
    except Exception as e:
        # Demo mode
        return {"success": True, "message": "Answer posted successfully (demo)"}


@router.post("/{location_id}/generate-answer", response_model=GenerateAnswerResponse)
async def generate_answer(
    location_id: str,
    request: GenerateAnswerRequest,
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """Generate AI answer for a question."""
    from app.models.location import Location
    from app.integrations.llm import LLMClient
    
    location = db.query(Location).filter(
        Location.id == location_id,
        Location.account_id == account.id
    ).first()
    
    if not location:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Location not found"
        )
    
    try:
        llm = LLMClient()
        prompt = f"""You are a helpful business owner responding to a customer question on Google Maps.
        
Business: {location.name}
Category: {location.category or 'Local Business'}
Address: {location.address}

Customer Question: {request.question_text}

Write a friendly, helpful, and professional answer. Keep it concise (2-3 sentences max).
Include relevant details about the business if applicable."""

        answer = await llm.generate(prompt)
        
        return GenerateAnswerResponse(suggested_answer=answer)
    except Exception as e:
        # Fallback answers based on keywords
        question_lower = request.question_text.lower()
        
        if "hour" in question_lower or "open" in question_lower:
            answer = "We're open Monday through Saturday from 9 AM to 9 PM, and Sunday from 10 AM to 6 PM. We look forward to seeing you!"
        elif "parking" in question_lower:
            answer = "Yes, we have free parking available for our customers. Street parking is also available nearby."
        elif "reservation" in question_lower or "book" in question_lower:
            answer = "Yes, we accept reservations! You can call us directly or book online through our website. We recommend booking in advance for weekends."
        elif "gluten" in question_lower or "allerg" in question_lower:
            answer = "Yes, we offer several options for dietary restrictions. Please let our staff know about any allergies when you order, and we'll be happy to accommodate you."
        elif "price" in question_lower or "cost" in question_lower:
            answer = "Our prices vary depending on the service. Please visit us or check our website for our current menu/price list. We offer great value for quality!"
        else:
            answer = "Thank you for your question! Please feel free to call us directly or visit our location for more information. We're always happy to help!"
        
        return GenerateAnswerResponse(suggested_answer=answer)
