from __future__ import annotations

import json
import logging

from models.db import Listing as DBListing, SessionLocal
from workflow.state import SessionState

logger = logging.getLogger(__name__)


def upsert_listings(state: SessionState) -> None:
    """Write normalized listings to DB immediately after normalization.

    Uses INSERT OR REPLACE semantics: if the listing id already exists, the row
    is deleted and re-inserted with fresh data.  Safe to call multiple times.
    """
    if not state.normalized_listings:
        return

    db = SessionLocal()
    try:
        existing_ids = {
            row.id
            for row in db.query(DBListing.id)
            .filter(DBListing.session_id == state.session_id)
            .all()
        }

        for listing in state.normalized_listings:
            score = state.scores.get(listing.id)
            row = DBListing(
                id=listing.id,
                session_id=listing.session_id,
                source_primary=listing.source_primary,
                source_variants=json.dumps(listing.source_variants),
                url=listing.url,
                title=listing.title,
                price_rm=listing.price_rm,
                deposit_rm=listing.deposit_rm,
                location_raw=listing.location_raw,
                location_area=listing.location_area,
                location_city=listing.location_city,
                lat=listing.lat,
                lng=listing.lng,
                room_type=listing.room_type,
                furnished_status=listing.furnished_status,
                parking=listing.parking,
                pet_friendly=listing.pet_friendly,
                gender_restriction=listing.gender_restriction,
                nearby_transport=json.dumps(listing.nearby_transport),
                facilities=json.dumps(listing.facilities),
                contact_phone=listing.contact_phone,
                contact_telegram=listing.contact_telegram,
                contact_email=listing.contact_email,
                source_language=listing.source_language,
                posted_date=listing.posted_date,
                description_original=listing.description_original,
                description_en=listing.description_en,
                images=json.dumps(listing.images),
                low_confidence_flags=json.dumps(listing.low_confidence_flags),
                needs_verification=json.dumps(listing.needs_verification),
                match_score=score.total if score else None,
                score_breakdown=json.dumps(score.breakdown) if score else None,
                score_explanation=score.explanation if score else None,
            )
            if listing.id in existing_ids:
                db.merge(row)
            else:
                db.add(row)

        db.commit()
        logger.info(
            "upsert_listings: persisted %d listings for session %s",
            len(state.normalized_listings),
            state.session_id,
        )
    except Exception as exc:
        logger.error("upsert_listings failed for session %s: %s", state.session_id, exc, exc_info=True)
        db.rollback()
    finally:
        db.close()


def update_listing_scores(state: SessionState) -> None:
    """Update match_score, score_breakdown, score_explanation, and needs_verification on existing rows."""
    if not state.scores:
        return

    db = SessionLocal()
    try:
        for listing_id, score in state.scores.items():
            listing = next(
                (l for l in state.normalized_listings if l.id == listing_id), None
            )
            db.query(DBListing).filter(DBListing.id == listing_id).update(
                {
                    "match_score": score.total,
                    "score_breakdown": json.dumps(score.breakdown),
                    "score_explanation": score.explanation,
                    "needs_verification": json.dumps(
                        listing.needs_verification if listing else []
                    ),
                },
                synchronize_session=False,
            )
        db.commit()
        logger.info(
            "update_listing_scores: updated %d scores for session %s",
            len(state.scores),
            state.session_id,
        )
    except Exception as exc:
        logger.error("update_listing_scores failed: %s", exc, exc_info=True)
        db.rollback()
    finally:
        db.close()
