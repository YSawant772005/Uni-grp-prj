"""Student profile and onboarding endpoints (own-profile access only)."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.permissions import get_current_user
from app.db.session import get_db
from app.models import User
from app.schemas.profile import OnboardingCompleteIn, ProfileIn, ProfilePatchIn
from app.services import profiles

router = APIRouter(prefix="/profile", tags=["profile"])


@router.get("")
async def get_profile(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    profile = profiles.current_profile(db, user)
    return profiles.profile_out(db, profile)


@router.put("")
async def put_profile(payload: ProfileIn, user: User = Depends(get_current_user),
                      db: Session = Depends(get_db)):
    profile = profiles.update_profile(db, user, payload, replace=True)
    return profiles.profile_out(db, profile)


@router.patch("")
async def patch_profile(payload: ProfilePatchIn, user: User = Depends(get_current_user),
                        db: Session = Depends(get_db)):
    profile = profiles.update_profile(db, user, payload, replace=False)
    return profiles.profile_out(db, profile)


@router.get("/completeness")
async def get_completeness(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    profile = profiles.current_profile(db, user)
    return profiles.completeness(profile)


@router.post("/onboarding/complete")
async def onboarding_complete(payload: OnboardingCompleteIn,
                              user: User = Depends(get_current_user),
                              db: Session = Depends(get_db)):
    return profiles.complete_onboarding(db, user, payload)

