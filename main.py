
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import DateTime, Float, String, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from database import Base, SessionLocal, engine


app = FastAPI(
    title="Emergency Green Corridor",
    description="Ambulance trip tracking and simulated corridor alerts",
    version="1.0.0",
)


class Trip(Base):
    __tablename__ = "trips"

    trip_id: Mapped[str] = mapped_column(
        String(40), primary_key=True
    )
    driver_name: Mapped[str] = mapped_column(String(100))
    ambulance_number: Mapped[str] = mapped_column(String(30))
    destination: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE")
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    location_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


# Create any missing tables when the application starts.
Base.metadata.create_all(bind=engine)


def current_time():
    return datetime.now(timezone.utc)


def trip_response(trip: Trip):
    location = None

    if trip.latitude is not None and trip.longitude is not None:
        location = {
            "latitude": trip.latitude,
            "longitude": trip.longitude,
            "updated_at": (
                trip.location_updated_at.isoformat()
                if trip.location_updated_at else None
            ),
        }

    return {
        "driver_name": trip.driver_name,
        "ambulance_number": trip.ambulance_number,
        "destination": trip.destination,
        "status": trip.status,
        "current_location": location,
        "started_at": trip.started_at.isoformat(),
        "ended_at": (
            trip.ended_at.isoformat() if trip.ended_at else None
        ),
    }


class TripRequest(BaseModel):
    driver_name: str = Field(min_length=1, max_length=100)
    ambulance_number: str = Field(min_length=1, max_length=30)
    destination: str = Field(min_length=1, max_length=200)


class LocationUpdate(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


@app.get("/")
def home():
    return {
        "message": "Emergency Green Corridor Backend is running!",
        "version": "1.0.0",
    }


@app.post("/trip/start", status_code=201)
def start_trip(request: TripRequest):
    with SessionLocal() as session:
        trip = Trip(
            trip_id=f"TRIP-{uuid4().hex[:12].upper()}",
            driver_name=request.driver_name,
            ambulance_number=request.ambulance_number,
            destination=request.destination,
            status="ACTIVE",
            started_at=current_time(),
        )

        session.add(trip)
        session.commit()
        session.refresh(trip)

        return {
            "message": "Emergency trip started",
            "trip_id": trip.trip_id,
            **trip_response(trip),
        }


@app.get("/trip/{trip_id}")
def get_trip(trip_id: str):
    with SessionLocal() as session:
        trip = session.get(Trip, trip_id)

        if trip is None:
            raise HTTPException(status_code=404, detail="Trip not found")

        return trip_response(trip)


@app.put("/trip/{trip_id}/location")
def update_location(trip_id: str, location: LocationUpdate):
    with SessionLocal() as session:
        trip = session.get(Trip, trip_id)

        if trip is None:
            raise HTTPException(status_code=404, detail="Trip not found")

        if trip.status != "ACTIVE":
            raise HTTPException(status_code=400, detail="Trip is not active")

        trip.latitude = location.latitude
        trip.longitude = location.longitude
        trip.location_updated_at = current_time()

        session.commit()

        return {
            "message": "Ambulance location updated",
            "trip_id": trip.trip_id,
            "current_location": {
                "latitude": trip.latitude,
                "longitude": trip.longitude,
                "updated_at": trip.location_updated_at.isoformat(),
            },
        }


@app.post("/trip/{trip_id}/corridor-alert")
def simulate_corridor_alert(trip_id: str):
    with SessionLocal() as session:
        trip = session.get(Trip, trip_id)

        if trip is None:
            raise HTTPException(status_code=404, detail="Trip not found")

        if trip.status != "ACTIVE":
            raise HTTPException(status_code=400, detail="Trip is not active")

        if trip.latitude is None or trip.longitude is None:
            raise HTTPException(
                status_code=400,
                detail="Update ambulance location before simulating an alert",
            )

        # DEMO ONLY: no route calculation or actual driver notifications.
        return {
            "trip_id": trip.trip_id,
            "alert_status": "SIMULATED",
            "ambulance_location": {
                "latitude": trip.latitude,
                "longitude": trip.longitude,
                "updated_at": (
                    trip.location_updated_at.isoformat()
                    if trip.location_updated_at else None
                ),
            },
            "simulated_nearby_drivers": 3,
            "message": (
                "Demo corridor alert generated. "
                "No actual drivers were notified."
            ),
            "generated_at": current_time().isoformat(),
        }


@app.post("/trip/{trip_id}/end")
def end_trip(trip_id: str):
    with SessionLocal() as session:
        trip = session.get(Trip, trip_id)

        if trip is None:
            raise HTTPException(status_code=404, detail="Trip not found")

        if trip.status != "ACTIVE":
            raise HTTPException(status_code=400, detail="Trip is not active")

        trip.status = "COMPLETED"
        trip.ended_at = current_time()
        session.commit()

        return {
            "message": "Emergency trip completed",
            "trip_id": trip.trip_id,
            "status": trip.status,
            "ended_at": trip.ended_at.isoformat(),
        }

