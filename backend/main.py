import os
import random
import string
import sys
from datetime import date, datetime, time
from typing import List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, joinedload

from database.models import (
    Cancellation,
    Feedback,
    LoginEvent,
    MealOrder,
    MealOrderItem,
    MenuItem,
    Payment,
    Reservation,
    Room,
    SessionLocal,
    User,
    hash_password,
    init_db,
    verify_password,
)

try:
    from pymongo import MongoClient
except Exception:
    MongoClient = None

app = FastAPI(title="Hotel Management System API", version="2.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

mongo_collection = None
if os.getenv("MONGODB_URL") and MongoClient:
    mongo_client = MongoClient(os.environ["MONGODB_URL"])
    mongo_db = mongo_client[os.getenv("MONGODB_DB", "hotel_hms")]
    mongo_collection = mongo_db["login_events"]


@app.on_event("startup")
def startup() -> None:
    init_db()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def gen_confirmation() -> str:
    return "HMS-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=8))


def parse_iso(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid date format. Use ISO format.") from exc


def parse_report_range(start_date: str, end_date: str) -> tuple[datetime, datetime]:
    start = datetime.fromisoformat(start_date)
    end = datetime.fromisoformat(end_date)
    if len(end_date) <= 10:
        end = datetime.combine(end.date(), time.max)
    if end < start:
        raise HTTPException(status_code=400, detail="End date must be after start date")
    return start, end


def reservation_nights(reservation: Reservation) -> int:
    return max(1, (reservation.check_out.date() - reservation.check_in.date()).days)


def late_checkout_charge_for_now(reservation: Reservation, current_time: Optional[datetime] = None) -> float:
    now = current_time or datetime.now()
    if reservation.status != "checked_in":
        return reservation.extra_night_charge
    return reservation.room_rate if now.hour >= 11 else 0.0


def update_room_status(room: Room) -> None:
    active_statuses = {"pending", "checked_in"}
    has_active = any(res.status in active_statuses for res in room.reservations)
    room.status = "occupied" if has_active else ("maintenance" if room.status == "maintenance" else "available")


def serialize_room(room: Room) -> dict:
    return {
        "id": room.id,
        "room_number": room.room_number,
        "category": room.category,
        "level": room.level,
        "view": room.view,
        "beds": room.beds,
        "smoking": room.smoking,
        "style": room.style,
        "default_rate": room.default_rate,
        "status": room.status,
    }


def serialize_user(user: User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "role": user.role,
        "fname": user.fname,
        "lname": user.lname,
        "email": user.email,
        "phone": user.phone,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


def serialize_reservation(reservation: Reservation) -> dict:
    return {
        "id": reservation.id,
        "confirmation_no": reservation.confirmation_no,
        "room_id": reservation.room_id,
        "room_number": reservation.room.room_number if reservation.room else None,
        "guest_user_id": reservation.guest_user_id,
        "guest_fname": reservation.guest_fname,
        "guest_lname": reservation.guest_lname,
        "guest_phone": reservation.guest_phone,
        "guest_email": reservation.guest_email,
        "num_occupants": reservation.num_occupants,
        "check_in": reservation.check_in.isoformat(),
        "check_out": reservation.check_out.isoformat(),
        "is_guaranteed": reservation.is_guaranteed,
        "credit_card_no": reservation.credit_card_no,
        "room_rate": reservation.room_rate,
        "rate_change_reason": reservation.rate_change_reason,
        "status": reservation.status,
        "must_pay": reservation.must_pay,
        "extra_night_charge": reservation.extra_night_charge,
        "staff_id": reservation.staff_id,
        "created_at": reservation.created_at.isoformat() if reservation.created_at else None,
        "checked_in_at": reservation.checked_in_at.isoformat() if reservation.checked_in_at else None,
        "checked_out_at": reservation.checked_out_at.isoformat() if reservation.checked_out_at else None,
    }


def serialize_menu_item(item: MenuItem) -> dict:
    return {
        "id": item.id,
        "name": item.name,
        "meal_type": item.meal_type,
        "description": item.description,
        "default_price": item.default_price,
        "current_price": item.current_price,
        "price_overridden": item.price_overridden,
        "service_channel": item.service_channel,
        "is_active": item.is_active,
    }


def serialize_payment(payment: Payment) -> dict:
    return {
        "id": payment.id,
        "reservation_id": payment.reservation_id,
        "amount": payment.amount,
        "payment_type": payment.payment_type,
        "source": payment.source,
        "payment_date": payment.payment_date.isoformat(),
    }


def serialize_meal_order(order: MealOrder) -> dict:
    return {
        "id": order.id,
        "reservation_id": order.reservation_id,
        "service_type": order.service_type,
        "order_date": order.order_date.isoformat(),
        "amount_charged": order.amount_charged,
        "billed_to_room": order.billed_to_room,
        "payment_type": order.payment_type,
        "paid": order.paid,
        "items": [
            {
                "menu_item_id": item.menu_item_id,
                "name": item.menu_item.name if item.menu_item else None,
                "quantity": item.quantity,
                "unit_price": item.unit_price,
            }
            for item in order.order_items
        ],
    }


def calculate_bill(reservation: Reservation) -> dict:
    room_charges = reservation_nights(reservation) * reservation.room_rate
    meal_charges = sum(order.amount_charged for order in reservation.meal_orders if order.billed_to_room or not order.paid)
    payments_made = sum(payment.amount for payment in reservation.payments)
    effective_extra_charge = late_checkout_charge_for_now(reservation)
    total = room_charges + meal_charges + effective_extra_charge
    return {
        "room_charges": room_charges,
        "meal_charges": meal_charges,
        "extra_night_charge": effective_extra_charge,
        "payments_made": payments_made,
        "total": total,
        "balance_due": max(total - payments_made, 0.0),
    }


def log_login_event(db: Session, request: Request, user: User) -> None:
    event = LoginEvent(
        user_id=user.id,
        username=user.username,
        role=user.role,
        client_ip=request.client.host if request.client else None,
    )
    db.add(event)
    db.flush()
    if mongo_collection is not None:
        try:
            mongo_collection.insert_one(
                {
                    "user_id": user.id,
                    "username": user.username,
                    "role": user.role,
                    "login_at": event.login_at,
                    "client_ip": event.client_ip,
                }
            )
        except Exception as exc:
            # MongoDB mirroring is optional; login should still succeed if Atlas is unavailable.
            print(f"Mongo login event mirror failed: {exc}")


class LoginSchema(BaseModel):
    username: str
    password: str


class RegisterSchema(BaseModel):
    username: str
    password: str = Field(min_length=4)
    fname: str
    lname: str
    email: str
    phone: str


class UserCreateSchema(RegisterSchema):
    role: str = "guest"


class PasswordUpdateSchema(BaseModel):
    new_password: str = Field(min_length=4)


class RoomSchema(BaseModel):
    room_number: str
    category: str
    level: int
    view: str
    beds: int
    smoking: bool = False
    style: str
    default_rate: float
    status: str = "available"


class RoomUpdateSchema(BaseModel):
    category: Optional[str] = None
    level: Optional[int] = None
    view: Optional[str] = None
    beds: Optional[int] = None
    smoking: Optional[bool] = None
    style: Optional[str] = None
    default_rate: Optional[float] = None
    status: Optional[str] = None


class ReservationCreate(BaseModel):
    room_id: int
    guest_fname: str
    guest_lname: str
    guest_phone: str
    guest_email: Optional[str] = None
    num_occupants: int = 1
    check_in: str
    check_out: str
    is_guaranteed: bool = False
    credit_card_no: Optional[str] = None
    room_rate: Optional[float] = None
    rate_change_reason: Optional[str] = None
    staff_id: Optional[int] = None
    guest_user_id: Optional[int] = None


class ReservationUpdate(BaseModel):
    guest_fname: Optional[str] = None
    guest_lname: Optional[str] = None
    guest_phone: Optional[str] = None
    guest_email: Optional[str] = None
    num_occupants: Optional[int] = None
    is_guaranteed: Optional[bool] = None
    credit_card_no: Optional[str] = None
    room_rate: Optional[float] = None
    rate_change_reason: Optional[str] = None


class PaymentCreate(BaseModel):
    reservation_id: int
    amount: float
    payment_type: str
    source: str = "room"


class MenuItemSchema(BaseModel):
    name: str
    meal_type: str
    description: str
    default_price: float
    current_price: float
    service_channel: str
    is_active: bool = True


class MenuItemUpdate(BaseModel):
    name: Optional[str] = None
    meal_type: Optional[str] = None
    description: Optional[str] = None
    default_price: Optional[float] = None
    current_price: Optional[float] = None
    service_channel: Optional[str] = None
    is_active: Optional[bool] = None


class MealOrderItemSchema(BaseModel):
    menu_item_id: int
    quantity: int = 1


class MealOrderCreate(BaseModel):
    reservation_id: int
    service_type: str
    items: List[MealOrderItemSchema]
    billed_to_room: bool = False
    payment_type: Optional[str] = None


class FeedbackCreate(BaseModel):
    reservation_id: int
    rating: int = Field(ge=1, le=5)
    comments: Optional[str] = None


class CancellationCreate(BaseModel):
    reservation_id: int
    cancel_reason: str
    staff_id: Optional[int] = None


class CheckoutSchema(BaseModel):
    extra_night_charge: float = 0.0


@app.post("/auth/register")
def register_guest(data: RegisterSchema, db: Session = Depends(get_db)):
    existing = db.query(User).filter(
        (User.username == data.username) | (User.email == data.email)
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username or email already exists")
    user = User(
        username=data.username,
        password=hash_password(data.password),
        role="guest",
        fname=data.fname,
        lname=data.lname,
        email=data.email,
        phone=data.phone,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return serialize_user(user)


@app.post("/auth/login")
def login(data: LoginSchema, request: Request, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == data.username).first()
    if not user or not verify_password(data.password, user.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    log_login_event(db, request, user)
    db.commit()
    return serialize_user(user)


@app.get("/users")
def get_users(db: Session = Depends(get_db)):
    users = db.query(User).order_by(User.created_at.desc()).all()
    return [serialize_user(user) for user in users]


@app.post("/users")
def create_user(data: UserCreateSchema, db: Session = Depends(get_db)):
    if db.query(User).filter(User.username == data.username).first():
        raise HTTPException(status_code=400, detail="Username already exists")
    user = User(
        username=data.username,
        password=hash_password(data.password),
        role=data.role,
        fname=data.fname,
        lname=data.lname,
        email=data.email,
        phone=data.phone,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return serialize_user(user)


@app.put("/users/{user_id}/password")
def update_password(user_id: int, data: PasswordUpdateSchema, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.password = hash_password(data.new_password)
    db.commit()
    return {"message": "Password updated"}


@app.delete("/users/{user_id}")
def delete_user(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.username == "admin":
        raise HTTPException(status_code=400, detail="Admin user cannot be deleted")
    db.delete(user)
    db.commit()
    return {"message": "User deleted"}


@app.get("/login-events")
def get_login_events(limit: int = Query(default=20, le=200), db: Session = Depends(get_db)):
    events = db.query(LoginEvent).order_by(LoginEvent.login_at.desc()).limit(limit).all()
    return [
        {
            "id": event.id,
            "user_id": event.user_id,
            "username": event.username,
            "role": event.role,
            "login_at": event.login_at.isoformat(),
            "client_ip": event.client_ip,
        }
        for event in events
    ]


@app.get("/rooms")
def get_rooms(status: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(Room).order_by(Room.room_number)
    if status and status.lower() != "all":
        query = query.filter(Room.status == status)
    return [serialize_room(room) for room in query.all()]


@app.post("/rooms")
def create_room(data: RoomSchema, db: Session = Depends(get_db)):
    if db.query(Room).filter(Room.room_number == data.room_number).first():
        raise HTTPException(status_code=400, detail="Room number already exists")
    room = Room(**data.model_dump())
    db.add(room)
    db.commit()
    db.refresh(room)
    return serialize_room(room)


@app.put("/rooms/{room_id}")
def update_room(room_id: int, data: RoomUpdateSchema, db: Session = Depends(get_db)):
    room = db.query(Room).filter(Room.id == room_id).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(room, field, value)
    db.commit()
    db.refresh(room)
    return serialize_room(room)


@app.delete("/rooms/{room_id}")
def delete_room(room_id: int, db: Session = Depends(get_db)):
    room = db.query(Room).filter(Room.id == room_id).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    if room.reservations:
        raise HTTPException(status_code=400, detail="Cannot delete a room with reservations")
    db.delete(room)
    db.commit()
    return {"message": "Room deleted"}


@app.get("/reservations")
def list_reservations(
    status: Optional[str] = None,
    guest_lname: Optional[str] = None,
    room_number: Optional[str] = None,
    guest_user_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    query = db.query(Reservation).options(joinedload(Reservation.room)).order_by(Reservation.created_at.desc())
    if status and status.lower() != "all":
        query = query.filter(Reservation.status == status)
    if guest_lname:
        query = query.filter(Reservation.guest_lname.ilike(f"%{guest_lname}%"))
    if room_number:
        query = query.join(Room).filter(Room.room_number.ilike(f"%{room_number}%"))
    if guest_user_id:
        query = query.filter(Reservation.guest_user_id == guest_user_id)
    return [serialize_reservation(reservation) for reservation in query.all()]


@app.post("/reservations")
def create_reservation(data: ReservationCreate, db: Session = Depends(get_db)):
    room = db.query(Room).options(joinedload(Room.reservations)).filter(Room.id == data.room_id).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    if room.status == "maintenance":
        raise HTTPException(status_code=400, detail="Room is under maintenance")

    check_in = parse_iso(data.check_in)
    check_out = parse_iso(data.check_out)
    if check_out <= check_in:
        raise HTTPException(status_code=400, detail="Check-out must be after check-in")

    overlapping = (
        db.query(Reservation)
        .filter(
            Reservation.room_id == data.room_id,
            Reservation.status.in_(["pending", "checked_in"]),
            Reservation.check_out > check_in,
            Reservation.check_in < check_out,
        )
        .first()
    )
    if overlapping:
        raise HTTPException(status_code=400, detail="Room is already reserved for those dates")

    rate = data.room_rate if data.room_rate is not None else room.default_rate
    if abs(rate - room.default_rate) > 0.01 and not data.rate_change_reason:
        raise HTTPException(status_code=400, detail="Rate change reason is required when overriding rate")
    if data.is_guaranteed and not data.credit_card_no:
        raise HTTPException(status_code=400, detail="Credit card number is required for guaranteed reservations")

    reservation = Reservation(
        confirmation_no=gen_confirmation(),
        room_id=data.room_id,
        guest_user_id=data.guest_user_id,
        guest_fname=data.guest_fname,
        guest_lname=data.guest_lname,
        guest_phone=data.guest_phone,
        guest_email=data.guest_email,
        num_occupants=data.num_occupants,
        check_in=check_in,
        check_out=check_out,
        is_guaranteed=data.is_guaranteed,
        credit_card_no=data.credit_card_no,
        room_rate=rate,
        rate_change_reason=data.rate_change_reason,
        staff_id=data.staff_id,
        must_pay=check_in.date() <= date.today(),
        status="pending",
    )
    db.add(reservation)
    room.status = "occupied"
    db.commit()
    db.refresh(reservation)
    reservation = db.query(Reservation).options(joinedload(Reservation.room)).filter(Reservation.id == reservation.id).first()
    return serialize_reservation(reservation)


@app.put("/reservations/{reservation_id}")
def update_reservation(reservation_id: int, data: ReservationUpdate, db: Session = Depends(get_db)):
    reservation = db.query(Reservation).options(joinedload(Reservation.room)).filter(Reservation.id == reservation_id).first()
    if not reservation:
        raise HTTPException(status_code=404, detail="Reservation not found")
    if reservation.status not in {"pending", "checked_in"}:
        raise HTTPException(status_code=400, detail="Reservation can no longer be modified")

    changes = data.model_dump(exclude_none=True)
    if "room_rate" in changes:
        default_rate = reservation.room.default_rate if reservation.room else changes["room_rate"]
        if abs(changes["room_rate"] - default_rate) > 0.01 and not changes.get("rate_change_reason") and not reservation.rate_change_reason:
            raise HTTPException(status_code=400, detail="Rate change reason is required")

    if changes.get("is_guaranteed") and not (changes.get("credit_card_no") or reservation.credit_card_no):
        raise HTTPException(status_code=400, detail="Credit card number is required for guaranteed reservations")

    for field, value in changes.items():
        setattr(reservation, field, value)
    db.commit()
    db.refresh(reservation)
    return serialize_reservation(reservation)


@app.post("/reservations/{reservation_id}/checkin")
def checkin_reservation(reservation_id: int, db: Session = Depends(get_db)):
    reservation = db.query(Reservation).options(joinedload(Reservation.room)).filter(Reservation.id == reservation_id).first()
    if not reservation:
        raise HTTPException(status_code=404, detail="Reservation not found")
    if reservation.status != "pending":
        raise HTTPException(status_code=400, detail="Only pending reservations can be checked in")
    reservation.status = "checked_in"
    reservation.checked_in_at = datetime.utcnow()
    reservation.room.status = "occupied"
    db.commit()
    return serialize_reservation(reservation)


@app.get("/reservations/{reservation_id}/bill")
def get_bill(reservation_id: int, db: Session = Depends(get_db)):
    reservation = (
        db.query(Reservation)
        .options(joinedload(Reservation.payments), joinedload(Reservation.meal_orders))
        .filter(Reservation.id == reservation_id)
        .first()
    )
    if not reservation:
        raise HTTPException(status_code=404, detail="Reservation not found")
    return calculate_bill(reservation)


@app.post("/reservations/{reservation_id}/checkout")
def checkout_reservation(reservation_id: int, data: CheckoutSchema, db: Session = Depends(get_db)):
    reservation = (
        db.query(Reservation)
        .options(joinedload(Reservation.room), joinedload(Reservation.payments), joinedload(Reservation.meal_orders))
        .filter(Reservation.id == reservation_id)
        .first()
    )
    if not reservation:
        raise HTTPException(status_code=404, detail="Reservation not found")
    if reservation.status != "checked_in":
        raise HTTPException(status_code=400, detail="Only checked-in reservations can be checked out")

    now = datetime.now()
    extra_night = max(data.extra_night_charge, 0.0)
    reservation.extra_night_charge = extra_night
    reservation.status = "checked_out"
    reservation.checked_out_at = now
    reservation.room.status = "available"
    bill = calculate_bill(reservation)
    db.commit()
    return {
        "message": "Checked out successfully",
        "extra_night_charge": extra_night,
        "total_owed": bill["total"],
        "balance_due": bill["balance_due"],
    }


@app.post("/cancellations")
def create_cancellation(data: CancellationCreate, db: Session = Depends(get_db)):
    reservation = db.query(Reservation).options(joinedload(Reservation.room)).filter(Reservation.id == data.reservation_id).first()
    if not reservation:
        raise HTTPException(status_code=404, detail="Reservation not found")
    if reservation.status == "checked_out":
        raise HTTPException(status_code=400, detail="Checked-out reservations cannot be cancelled")
    if reservation.cancellation:
        raise HTTPException(status_code=400, detail="Reservation already cancelled")
    cancellation = Cancellation(
        reservation_id=data.reservation_id,
        cancel_reason=data.cancel_reason,
        staff_id=data.staff_id,
    )
    reservation.status = "cancelled"
    db.add(cancellation)
    if reservation.room:
        reservation.room.status = "available"
    db.commit()
    db.refresh(cancellation)
    return {"message": "Reservation cancelled"}


@app.post("/payments")
def create_payment(data: PaymentCreate, db: Session = Depends(get_db)):
    reservation = db.query(Reservation).filter(Reservation.id == data.reservation_id).first()
    if not reservation:
        raise HTTPException(status_code=404, detail="Reservation not found")
    if data.amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be greater than zero")
    payment = Payment(**data.model_dump())
    db.add(payment)
    db.commit()
    db.refresh(payment)
    return serialize_payment(payment)


@app.get("/payments/reservation/{reservation_id}")
def get_payments_for_reservation(reservation_id: int, db: Session = Depends(get_db)):
    payments = db.query(Payment).filter(Payment.reservation_id == reservation_id).order_by(Payment.payment_date.desc()).all()
    return [serialize_payment(payment) for payment in payments]


@app.get("/menu")
def get_menu(db: Session = Depends(get_db)):
    items = db.query(MenuItem).order_by(MenuItem.meal_type, MenuItem.name).all()
    return [serialize_menu_item(item) for item in items]


@app.post("/menu")
def create_menu_item(data: MenuItemSchema, db: Session = Depends(get_db)):
    item = MenuItem(
        **data.model_dump(),
        price_overridden=abs(data.current_price - data.default_price) > 0.01,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return serialize_menu_item(item)


@app.put("/menu/{item_id}")
def update_menu_item(item_id: int, data: MenuItemUpdate, db: Session = Depends(get_db)):
    item = db.query(MenuItem).filter(MenuItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Menu item not found")
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(item, field, value)
    if item.default_price is not None and item.current_price is not None:
        item.price_overridden = abs(item.current_price - item.default_price) > 0.01
    db.commit()
    db.refresh(item)
    return serialize_menu_item(item)


@app.delete("/menu/{item_id}")
def delete_menu_item(item_id: int, db: Session = Depends(get_db)):
    item = db.query(MenuItem).filter(MenuItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Menu item not found")
    db.delete(item)
    db.commit()
    return {"message": "Menu item removed"}


@app.post("/meal-orders")
def create_meal_order(data: MealOrderCreate, db: Session = Depends(get_db)):
    reservation = db.query(Reservation).filter(Reservation.id == data.reservation_id).first()
    if not reservation:
        raise HTTPException(status_code=404, detail="Reservation not found")
    if reservation.status not in {"checked_in", "checked_out"}:
        raise HTTPException(status_code=400, detail="Meal orders require an active stay")
    if not data.items:
        raise HTTPException(status_code=400, detail="At least one menu item is required")

    menu_map = {
        item.id: item
        for item in db.query(MenuItem).filter(MenuItem.id.in_([order_item.menu_item_id for order_item in data.items])).all()
    }
    total = 0.0
    order = MealOrder(
        reservation_id=data.reservation_id,
        service_type=data.service_type,
        billed_to_room=data.billed_to_room,
        paid=not data.billed_to_room,
        payment_type=None if data.billed_to_room else data.payment_type,
        amount_charged=0.0,
    )
    db.add(order)
    db.flush()

    for item_payload in data.items:
        menu_item = menu_map.get(item_payload.menu_item_id)
        if not menu_item:
            raise HTTPException(status_code=404, detail=f"Menu item {item_payload.menu_item_id} not found")
        line_total = menu_item.current_price * item_payload.quantity
        total += line_total
        db.add(
            MealOrderItem(
                order_id=order.id,
                menu_item_id=menu_item.id,
                quantity=item_payload.quantity,
                unit_price=menu_item.current_price,
            )
        )
    order.amount_charged = total
    db.commit()
    order = db.query(MealOrder).options(joinedload(MealOrder.order_items).joinedload(MealOrderItem.menu_item)).filter(MealOrder.id == order.id).first()
    return {
        **serialize_meal_order(order),
        "total": total,
    }


@app.get("/meal-orders/reservation/{reservation_id}")
def get_meal_orders(reservation_id: int, db: Session = Depends(get_db)):
    orders = (
        db.query(MealOrder)
        .options(joinedload(MealOrder.order_items).joinedload(MealOrderItem.menu_item))
        .filter(MealOrder.reservation_id == reservation_id)
        .order_by(MealOrder.order_date.desc())
        .all()
    )
    return [serialize_meal_order(order) for order in orders]


@app.post("/feedback")
def create_feedback(data: FeedbackCreate, db: Session = Depends(get_db)):
    reservation = db.query(Reservation).filter(Reservation.id == data.reservation_id).first()
    if not reservation:
        raise HTTPException(status_code=404, detail="Reservation not found")
    if reservation.feedback:
        raise HTTPException(status_code=400, detail="Feedback already submitted")
    feedback = Feedback(**data.model_dump())
    db.add(feedback)
    db.commit()
    db.refresh(feedback)
    return {"message": "Feedback submitted"}


@app.get("/reports/occupancy")
def occupancy_report(start_date: str, end_date: str, db: Session = Depends(get_db)):
    start, end = parse_report_range(start_date, end_date)
    total_rooms = db.query(Room).count()
    reservations = db.query(Reservation).filter(Reservation.check_in <= end, Reservation.check_out >= start).all()
    occupied = sum(1 for reservation in reservations if reservation.status in {"checked_in", "checked_out"})
    projected = sum(1 for reservation in reservations if reservation.status == "pending")
    denominator = total_rooms or 1
    return {
        "total_rooms": total_rooms,
        "occupied_reservations": occupied,
        "projected_reservations": projected,
        "occupancy_rate": round(((occupied + projected) / denominator) * 100, 2),
    }


@app.get("/reports/room-revenue")
def room_revenue_report(start_date: str, end_date: str, db: Session = Depends(get_db)):
    start, end = parse_report_range(start_date, end_date)
    reservations = (
        db.query(Reservation)
        .options(joinedload(Reservation.room))
        .filter(Reservation.created_at >= start, Reservation.created_at <= end)
        .all()
    )
    breakdown = []
    total = 0.0
    for reservation in reservations:
        revenue = reservation.room_rate * reservation_nights(reservation) + reservation.extra_night_charge
        total += revenue
        breakdown.append(
            {
                "confirmation_no": reservation.confirmation_no,
                "room": reservation.room.room_number if reservation.room else "-",
                "guest": f"{reservation.guest_fname} {reservation.guest_lname}",
                "revenue": revenue,
            }
        )
    return {"total_revenue": total, "breakdown": breakdown}


@app.get("/reports/food-revenue")
def food_revenue_report(start_date: str, end_date: str, db: Session = Depends(get_db)):
    start, end = parse_report_range(start_date, end_date)
    orders = db.query(MealOrder).filter(MealOrder.order_date >= start, MealOrder.order_date <= end).all()
    by_service_type = {}
    total = 0.0
    breakdown = []
    for order in orders:
        total += order.amount_charged
        by_service_type[order.service_type] = by_service_type.get(order.service_type, 0.0) + order.amount_charged
        breakdown.append(
            {
                "order_id": order.id,
                "reservation_id": order.reservation_id,
                "service_type": order.service_type,
                "amount_charged": order.amount_charged,
                "paid": order.paid,
                "billed_to_room": order.billed_to_room,
                "order_date": order.order_date.isoformat(),
            }
        )
    return {
        "total_food_revenue": total,
        "order_count": len(orders),
        "by_service_type": by_service_type,
        "breakdown": breakdown,
    }


@app.get("/reports/exceptions")
def exception_report(db: Session = Depends(get_db)):
    reservations = (
        db.query(Reservation)
        .options(joinedload(Reservation.room))
        .filter(Reservation.rate_change_reason.isnot(None))
        .all()
    )
    menu_items = db.query(MenuItem).filter(MenuItem.price_overridden.is_(True)).all()
    return {
        "room_rate_exceptions": [
            {
                "confirmation_no": reservation.confirmation_no,
                "room_number": reservation.room.room_number if reservation.room else None,
                "default_rate": reservation.room.default_rate if reservation.room else None,
                "booked_rate": reservation.room_rate,
                "reason": reservation.rate_change_reason,
            }
            for reservation in reservations
        ],
        "food_price_exceptions": [
            {
                "menu_item": item.name,
                "default_price": item.default_price,
                "current_price": item.current_price,
            }
            for item in menu_items
        ],
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
