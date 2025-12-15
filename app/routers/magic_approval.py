"""Magic Link approval router for passwordless content approval."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.magic_link import ApprovalWorkflowService

router = APIRouter(prefix="/approve", tags=["approval"])


class EditContentRequest(BaseModel):
    """Request to edit content via magic link."""
    title: str | None = None
    body: str
    token: str


class ApprovalResponse(BaseModel):
    """Response after approval action."""
    success: bool
    action: str
    message: str
    post_id: str | None = None


# ============ Magic Link Endpoints (No Auth Required) ============

@router.get("/{post_id}")
async def handle_approval_link(
    post_id: UUID,
    token: str = Query(...),
    action: str = Query(...),
    db: Session = Depends(get_db),
):
    """
    Handle magic link approval action.
    
    This endpoint processes approve/reject/edit actions without login.
    The token contains the security signature.
    """
    service = ApprovalWorkflowService(db)
    result = await service.process_approval_action(
        post_id=post_id,
        token=token,
        action=action,
    )

    if not result["success"]:
        # Return error page
        return HTMLResponse(
            content=_generate_error_page(result.get("error", "Unknown error")),
            status_code=400,
        )

    # Return success page based on action
    if action == "approve":
        return HTMLResponse(content=_generate_success_page(
            title="Content Approved! ✅",
            message="Your content has been approved and will be published shortly.",
            post_id=str(post_id),
        ))

    elif action == "reject":
        return HTMLResponse(content=_generate_success_page(
            title="Content Rejected",
            message="The content has been rejected. We'll generate a new version for you.",
            post_id=str(post_id),
        ))

    elif action == "edit":
        # Return edit form
        return HTMLResponse(content=_generate_edit_page(
            post_id=str(post_id),
            token=token,
            title=result.get("post_data", {}).get("title", ""),
            body=result.get("post_data", {}).get("body", ""),
        ))

    return HTMLResponse(content=_generate_error_page("Invalid action"))


@router.post("/{post_id}/save")
async def save_edited_content(
    post_id: UUID,
    request: EditContentRequest,
    db: Session = Depends(get_db),
):
    """
    Save edited content and approve.
    
    Called after user edits content via magic link.
    """
    from app.models.post import Post, PostStatus
    from app.models.location import Location
    from app.services.magic_link import MagicLinkService
    from datetime import datetime, timezone

    # Get post
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    # Get location for account_id
    location = db.query(Location).filter(Location.id == post.location_id).first()
    if not location:
        raise HTTPException(status_code=404, detail="Location not found")

    # Validate token
    magic_link = MagicLinkService()
    validation = magic_link.validate_token(
        token=request.token,
        post_id=post_id,
        action="edit",
        account_id=location.account_id,
    )

    if not validation["valid"]:
        raise HTTPException(status_code=400, detail=validation["error"])

    # Update post
    if request.title:
        post.title = request.title
    post.body = request.body
    post.status = PostStatus.APPROVED
    post.approved_at = datetime.now(timezone.utc)

    db.commit()

    return {
        "success": True,
        "message": "Content saved and approved!",
        "post_id": str(post_id),
    }


# ============ HTML Page Generators ============

def _generate_success_page(title: str, message: str, post_id: str) -> str:
    """Generate success confirmation page."""
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{title} - Local SEO Optimizer</title>
        <style>
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
                padding: 20px;
            }}
            .card {{
                background: white;
                border-radius: 16px;
                padding: 40px;
                max-width: 500px;
                text-align: center;
                box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            }}
            .icon {{ font-size: 64px; margin-bottom: 20px; }}
            h1 {{ color: #333; margin-bottom: 16px; }}
            p {{ color: #666; line-height: 1.6; margin-bottom: 24px; }}
            .btn {{
                display: inline-block;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 12px 32px;
                border-radius: 8px;
                text-decoration: none;
                font-weight: bold;
            }}
            .post-id {{ font-size: 12px; color: #999; margin-top: 20px; }}
        </style>
    </head>
    <body>
        <div class="card">
            <div class="icon">🎉</div>
            <h1>{title}</h1>
            <p>{message}</p>
            <a href="https://app.localseooptimizer.com/dashboard" class="btn">Go to Dashboard</a>
            <p class="post-id">Post ID: {post_id}</p>
        </div>
    </body>
    </html>
    """


def _generate_error_page(error: str) -> str:
    """Generate error page."""
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Error - Local SEO Optimizer</title>
        <style>
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                background: #f8f9fa;
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
                padding: 20px;
            }}
            .card {{
                background: white;
                border-radius: 16px;
                padding: 40px;
                max-width: 500px;
                text-align: center;
                box-shadow: 0 4px 20px rgba(0,0,0,0.1);
            }}
            .icon {{ font-size: 64px; margin-bottom: 20px; }}
            h1 {{ color: #dc3545; margin-bottom: 16px; }}
            p {{ color: #666; line-height: 1.6; margin-bottom: 24px; }}
            .error-detail {{ background: #fff3f3; padding: 12px; border-radius: 8px; color: #dc3545; }}
        </style>
    </head>
    <body>
        <div class="card">
            <div class="icon">⚠️</div>
            <h1>Something went wrong</h1>
            <p class="error-detail">{error}</p>
            <p>This link may have expired or is invalid. Please request a new approval link from your dashboard.</p>
        </div>
    </body>
    </html>
    """


def _generate_edit_page(post_id: str, token: str, title: str, body: str) -> str:
    """Generate content edit page."""
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Edit Content - Local SEO Optimizer</title>
        <style>
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                background: #f8f9fa;
                min-height: 100vh;
                padding: 20px;
            }}
            .container {{ max-width: 700px; margin: 0 auto; }}
            .header {{
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 30px;
                border-radius: 16px 16px 0 0;
            }}
            .form-card {{
                background: white;
                padding: 30px;
                border-radius: 0 0 16px 16px;
                box-shadow: 0 4px 20px rgba(0,0,0,0.1);
            }}
            .form-group {{ margin-bottom: 20px; }}
            label {{ display: block; font-weight: bold; margin-bottom: 8px; color: #333; }}
            input, textarea {{
                width: 100%;
                padding: 12px;
                border: 2px solid #e9ecef;
                border-radius: 8px;
                font-size: 16px;
                transition: border-color 0.2s;
            }}
            input:focus, textarea:focus {{
                outline: none;
                border-color: #667eea;
            }}
            textarea {{ min-height: 200px; resize: vertical; }}
            .buttons {{ display: flex; gap: 12px; margin-top: 24px; }}
            .btn {{
                flex: 1;
                padding: 14px 24px;
                border: none;
                border-radius: 8px;
                font-size: 16px;
                font-weight: bold;
                cursor: pointer;
                transition: transform 0.2s;
            }}
            .btn:hover {{ transform: translateY(-2px); }}
            .btn-primary {{
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
            }}
            .btn-secondary {{ background: #e9ecef; color: #333; }}
            .char-count {{ text-align: right; font-size: 12px; color: #999; margin-top: 4px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>✏️ Edit Your Content</h1>
                <p>Make any changes and save to approve</p>
            </div>
            
            <div class="form-card">
                <form id="editForm">
                    <div class="form-group">
                        <label for="title">Title (optional)</label>
                        <input type="text" id="title" name="title" value="{title or ''}" placeholder="Enter a catchy title...">
                    </div>
                    
                    <div class="form-group">
                        <label for="body">Content</label>
                        <textarea id="body" name="body" placeholder="Your post content...">{body or ''}</textarea>
                        <div class="char-count"><span id="charCount">0</span> characters</div>
                    </div>
                    
                    <div class="buttons">
                        <button type="button" class="btn btn-secondary" onclick="window.history.back()">Cancel</button>
                        <button type="submit" class="btn btn-primary">Save & Approve ✅</button>
                    </div>
                </form>
            </div>
        </div>
        
        <script>
            const bodyTextarea = document.getElementById('body');
            const charCount = document.getElementById('charCount');
            
            function updateCharCount() {{
                charCount.textContent = bodyTextarea.value.length;
            }}
            
            bodyTextarea.addEventListener('input', updateCharCount);
            updateCharCount();
            
            document.getElementById('editForm').addEventListener('submit', async (e) => {{
                e.preventDefault();
                
                const data = {{
                    title: document.getElementById('title').value,
                    body: document.getElementById('body').value,
                    token: '{token}'
                }};
                
                try {{
                    const response = await fetch('/api/v1/approve/{post_id}/save', {{
                        method: 'POST',
                        headers: {{ 'Content-Type': 'application/json' }},
                        body: JSON.stringify(data)
                    }});
                    
                    const result = await response.json();
                    
                    if (result.success) {{
                        document.body.innerHTML = `
                            <div style="display:flex;align-items:center;justify-content:center;min-height:100vh;background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);">
                                <div style="background:white;padding:40px;border-radius:16px;text-align:center;max-width:500px;">
                                    <div style="font-size:64px;margin-bottom:20px;">🎉</div>
                                    <h1 style="color:#333;margin-bottom:16px;">Content Saved!</h1>
                                    <p style="color:#666;">Your edited content has been approved and will be published shortly.</p>
                                </div>
                            </div>
                        `;
                    }} else {{
                        alert('Error: ' + (result.detail || result.message || 'Unknown error'));
                    }}
                }} catch (err) {{
                    alert('Error saving content: ' + err.message);
                }}
            }});
        </script>
    </body>
    </html>
    """
