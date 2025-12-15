"""Reset onboarding data for test user."""

import sys
sys.path.insert(0, ".")

from app.db.session import SessionLocal
from app.models.account import Account
from app.models.onboarding import OnboardingAudit

def reset_onboarding():
    """Delete onboarding data for test user."""
    db = SessionLocal()
    try:
        user = db.query(Account).filter(Account.email == "test@example.com").first()
        if not user:
            print("Test user not found")
            return
        
        # Delete existing onboarding audits
        deleted = db.query(OnboardingAudit).filter(
            OnboardingAudit.account_id == user.id
        ).delete()
        
        db.commit()
        print(f"Deleted {deleted} onboarding audit(s) for test@example.com")
        print("\n✅ Onboarding reset complete!")
        print("You can now test the onboarding flow at: http://localhost:3000/onboarding")
        
    finally:
        db.close()

if __name__ == "__main__":
    reset_onboarding()
