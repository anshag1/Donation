from sqlalchemy.orm import Session

from app.config import Settings
from app.core.exceptions import NotFoundError
from app.models.organization import Organization
from app.repositories import donation_repo, donor_repo, event_repo
from app.schemas.donation import DonationInitiateRequest, DonationInitiateResponse
from app.services.payment_service import create_razorpay_order


def initiate_donation(
    db: Session,
    settings: Settings,
    *,
    organization: Organization,
    request: DonationInitiateRequest,
) -> DonationInitiateResponse:
    """Creates the donor/donation/payment rows and a Razorpay order, all in one
    transaction. The donation starts life as `pending` — it is only ever
    flipped to `success` by the verified webhook (webhook_service), never by
    this endpoint or any client callback. See docs/02-user-flows.md §2.1/§2.4.
    """
    event = None
    if request.event_id is not None:
        event = event_repo.get_by_id(db, organization.id, request.event_id)
        if event is None:
            raise NotFoundError("Event not found")

    donor = donor_repo.get_or_create(db, organization.id, request.donor)

    donation = donation_repo.create(
        db,
        organization_id=organization.id,
        donor_id=donor.id,
        event_id=event.id if event else None,
        amount_in_paise=request.amount_in_paise,
        currency="INR",
        purpose=request.purpose or (event.title if event else "General Donation"),
        donor_snapshot_json=request.donor.model_dump(mode="json"),
    )

    razorpay_order_id = create_razorpay_order(
        settings, donation_id=donation.id, amount_in_paise=request.amount_in_paise
    )

    donation_repo.create_payment(
        db,
        organization_id=organization.id,
        donation_id=donation.id,
        razorpay_order_id=razorpay_order_id,
        amount_in_paise=request.amount_in_paise,
    )

    db.commit()

    return DonationInitiateResponse(
        donation_id=donation.id,
        razorpay_order_id=razorpay_order_id,
        razorpay_key_id=settings.razorpay_key_id,
        amount_in_paise=request.amount_in_paise,
    )
