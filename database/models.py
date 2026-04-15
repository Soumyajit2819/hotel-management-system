import enum
import hashlib
import os
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
    inspect,
    text,
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./hotel.db")
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def verify_password(raw_password: str, stored_password: str) -> bool:
    return stored_password == raw_password or stored_password == hash_password(raw_password)


class RoomStatus(str, enum.Enum):
    available = "available"
    occupied = "occupied"
    maintenance = "maintenance"


class PaymentType(str, enum.Enum):
    cash = "cash"
    credit_card = "credit_card"
    debit_card = "debit_card"
    upi = "upi"


class CancelReason(str, enum.Enum):
    personal = "personal"
    misbehaviour = "misbehaviour"
    lack_of_facility = "lack_of_facility"
    non_payment = "non_payment"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    password = Column(String, nullable=False)
    role = Column(String, default="guest", nullable=False)
    fname = Column(String, nullable=False)
    lname = Column(String, nullable=False)
    email = Column(String, nullable=False)
    phone = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    reservations = relationship("Reservation", back_populates="guest_user", foreign_keys="Reservation.guest_user_id")
    login_events = relationship("LoginEvent", back_populates="user")


class Room(Base):
    __tablename__ = "rooms"

    id = Column(Integer, primary_key=True, index=True)
    room_number = Column(String, unique=True, index=True, nullable=False)
    category = Column(String, nullable=False)
    level = Column(Integer, nullable=False)
    view = Column(String, nullable=False)
    beds = Column(Integer, nullable=False)
    smoking = Column(Boolean, default=False)
    style = Column(String, nullable=False)
    default_rate = Column(Float, nullable=False)
    status = Column(String, default=RoomStatus.available.value, nullable=False)
    reservations = relationship("Reservation", back_populates="room")


class Reservation(Base):
    __tablename__ = "reservations"

    id = Column(Integer, primary_key=True, index=True)
    confirmation_no = Column(String, unique=True, index=True, nullable=False)
    room_id = Column(Integer, ForeignKey("rooms.id"), nullable=False)
    guest_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    guest_fname = Column(String, nullable=False)
    guest_lname = Column(String, nullable=False)
    guest_phone = Column(String, nullable=False)
    guest_email = Column(String, nullable=True)
    num_occupants = Column(Integer, default=1)
    check_in = Column(DateTime, nullable=False)
    check_out = Column(DateTime, nullable=False)
    is_guaranteed = Column(Boolean, default=False)
    credit_card_no = Column(String, nullable=True)
    room_rate = Column(Float, nullable=False)
    rate_change_reason = Column(String, nullable=True)
    status = Column(String, default="pending")
    must_pay = Column(Boolean, default=False)
    extra_night_charge = Column(Float, default=0.0)
    staff_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    checked_in_at = Column(DateTime, nullable=True)
    checked_out_at = Column(DateTime, nullable=True)
    room = relationship("Room", back_populates="reservations")
    guest_user = relationship("User", back_populates="reservations", foreign_keys=[guest_user_id])
    payments = relationship("Payment", back_populates="reservation", cascade="all, delete-orphan")
    meal_orders = relationship("MealOrder", back_populates="reservation", cascade="all, delete-orphan")
    feedback = relationship("Feedback", back_populates="reservation", uselist=False, cascade="all, delete-orphan")
    cancellation = relationship("Cancellation", back_populates="reservation", uselist=False, cascade="all, delete-orphan")


class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    reservation_id = Column(Integer, ForeignKey("reservations.id"), nullable=False)
    amount = Column(Float, nullable=False)
    payment_type = Column(String, nullable=False)
    source = Column(String, default="room")
    payment_date = Column(DateTime, default=datetime.utcnow)
    reservation = relationship("Reservation", back_populates="payments")


class MenuItem(Base):
    __tablename__ = "menu_items"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    meal_type = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    default_price = Column(Float, nullable=False)
    price_overridden = Column(Boolean, default=False)
    current_price = Column(Float, nullable=False)
    service_channel = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)


class MealOrder(Base):
    __tablename__ = "meal_orders"

    id = Column(Integer, primary_key=True, index=True)
    reservation_id = Column(Integer, ForeignKey("reservations.id"), nullable=False)
    service_type = Column(String, nullable=False)
    order_date = Column(DateTime, default=datetime.utcnow)
    amount_charged = Column(Float, nullable=False)
    billed_to_room = Column(Boolean, default=False)
    payment_type = Column(String, nullable=True)
    paid = Column(Boolean, default=False)
    reservation = relationship("Reservation", back_populates="meal_orders")
    order_items = relationship("MealOrderItem", back_populates="order", cascade="all, delete-orphan")


class MealOrderItem(Base):
    __tablename__ = "meal_order_items"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("meal_orders.id"), nullable=False)
    menu_item_id = Column(Integer, ForeignKey("menu_items.id"), nullable=False)
    quantity = Column(Integer, default=1)
    unit_price = Column(Float, nullable=False)
    order = relationship("MealOrder", back_populates="order_items")
    menu_item = relationship("MenuItem")


class Feedback(Base):
    __tablename__ = "feedback"

    id = Column(Integer, primary_key=True, index=True)
    reservation_id = Column(Integer, ForeignKey("reservations.id"), unique=True, nullable=False)
    rating = Column(Integer, nullable=False)
    comments = Column(Text, nullable=True)
    submitted_on = Column(DateTime, default=datetime.utcnow)
    reservation = relationship("Reservation", back_populates="feedback")


class Cancellation(Base):
    __tablename__ = "cancellations"

    id = Column(Integer, primary_key=True, index=True)
    reservation_id = Column(Integer, ForeignKey("reservations.id"), unique=True, nullable=False)
    cancel_reason = Column(String, nullable=False)
    cancel_date = Column(DateTime, default=datetime.utcnow)
    staff_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    reservation = relationship("Reservation", back_populates="cancellation")


class LoginEvent(Base):
    __tablename__ = "login_events"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    username = Column(String, nullable=False)
    role = Column(String, nullable=False)
    login_at = Column(DateTime, default=datetime.utcnow)
    client_ip = Column(String, nullable=True)
    user = relationship("User", back_populates="login_events")


def ensure_schema_updates() -> None:
    inspector = inspect(engine)
    if "reservations" in inspector.get_table_names():
        columns = {column["name"] for column in inspector.get_columns("reservations")}
        with engine.begin() as connection:
            if "guest_user_id" not in columns:
                connection.execute(text("ALTER TABLE reservations ADD COLUMN guest_user_id INTEGER"))
            if "guest_email" not in columns:
                connection.execute(text("ALTER TABLE reservations ADD COLUMN guest_email VARCHAR"))
            if "checked_in_at" not in columns:
                connection.execute(text("ALTER TABLE reservations ADD COLUMN checked_in_at DATETIME"))
            if "checked_out_at" not in columns:
                connection.execute(text("ALTER TABLE reservations ADD COLUMN checked_out_at DATETIME"))


def seed_users(db) -> None:
    default_users = [
        {
            "username": "admin",
            "password": "admin123",
            "role": "admin",
            "fname": "Admin",
            "lname": "Manager",
            "email": "admin@hotel.com",
            "phone": "9999999999",
        },
        {
            "username": "receptionist",
            "password": "rec123",
            "role": "receptionist",
            "fname": "Front",
            "lname": "Desk",
            "email": "reception@hotel.com",
            "phone": "8888888888",
        },
        {
            "username": "guest",
            "password": "guest123",
            "role": "guest",
            "fname": "Demo",
            "lname": "Guest",
            "email": "guest@hotel.com",
            "phone": "7777777777",
        },
    ]
    for payload in default_users:
        user = db.query(User).filter(User.username == payload["username"]).first()
        if not user:
            db.add(
                User(
                    username=payload["username"],
                    password=hash_password(payload["password"]),
                    role=payload["role"],
                    fname=payload["fname"],
                    lname=payload["lname"],
                    email=payload["email"],
                    phone=payload["phone"],
                )
            )
        elif len(user.password) != 64:
            user.password = hash_password(payload["password"])


def seed_rooms(db) -> None:
    if db.query(Room).count() > 0:
        return
    rooms_data = [
        Room(room_number="101", category="single", level=1, view="garden", beds=1, smoking=False, style="standard", default_rate=1500.0, status="available"),
        Room(room_number="102", category="double", level=1, view="garden", beds=2, smoking=False, style="standard", default_rate=2600.0, status="available"),
        Room(room_number="201", category="deluxe", level=2, view="city", beds=2, smoking=False, style="modern", default_rate=4200.0, status="available"),
        Room(room_number="202", category="suite", level=2, view="sea", beds=2, smoking=False, style="luxury", default_rate=8200.0, status="available"),
        Room(room_number="301", category="single", level=3, view="city", beds=1, smoking=True, style="standard", default_rate=1900.0, status="maintenance"),
        Room(room_number="302", category="double", level=3, view="sea", beds=2, smoking=False, style="modern", default_rate=5100.0, status="available"),
    ]
    for room in rooms_data:
        db.add(room)


def seed_menu(db) -> None:
    if db.query(MenuItem).count() > 0:
        return
    menu_data = [
        MenuItem(name="Continental Breakfast", meal_type="breakfast", description="Bread, butter, fruit, coffee", default_price=350.0, current_price=350.0, service_channel="both"),
        MenuItem(name="South Indian Combo", meal_type="breakfast", description="Idli, dosa, chutney, filter coffee", default_price=280.0, current_price=280.0, service_channel="both"),
        MenuItem(name="Club Sandwich", meal_type="lunch", description="Triple layer sandwich with fries", default_price=450.0, current_price=450.0, service_channel="both"),
        MenuItem(name="Veg Thali", meal_type="lunch", description="Rice, dal, sabzi, roti, salad", default_price=360.0, current_price=360.0, service_channel="restaurant"),
        MenuItem(name="Grilled Chicken", meal_type="dinner", description="Chicken with mashed potato and vegetables", default_price=760.0, current_price=760.0, service_channel="both"),
        MenuItem(name="Pasta Arrabiata", meal_type="dinner", description="Penne in spicy tomato sauce", default_price=560.0, current_price=560.0, service_channel="restaurant"),
        MenuItem(name="Masala Chai", meal_type="snack", description="Fresh Indian spiced tea", default_price=90.0, current_price=90.0, service_channel="room_service"),
        MenuItem(name="Fruit Platter", meal_type="snack", description="Seasonal fruits platter", default_price=250.0, current_price=250.0, service_channel="both"),
    ]
    for item in menu_data:
        db.add(item)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    ensure_schema_updates()
    db = SessionLocal()
    try:
        seed_users(db)
        seed_rooms(db)
        seed_menu(db)
        db.commit()
    finally:
        db.close()
