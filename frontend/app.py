from datetime import date, datetime, timedelta

import pandas as pd
import requests
import streamlit as st

API = "https://hotel-management-system-q42e.onrender.com"

st.set_page_config(page_title="Hotel Management System", page_icon="🏨", layout="wide")

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&display=swap');
    html, body, [class*="css"] { font-family: 'Manrope', sans-serif; }
    .stApp {
        background:
            radial-gradient(circle at top left, rgba(255, 190, 92, 0.25), transparent 28%),
            radial-gradient(circle at top right, rgba(15, 118, 110, 0.22), transparent 24%),
            linear-gradient(180deg, #f8f5ef 0%, #eef4f3 100%);
    }
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #12343b 0%, #1f6f78 100%);
    }
    [data-testid="stSidebar"] * { color: #f4f7f5 !important; }
    .hero {
        padding: 1.5rem 1.75rem;
        border-radius: 18px;
        background: linear-gradient(135deg, #12343b 0%, #1f6f78 55%, #f0b429 100%);
        color: white;
        box-shadow: 0 18px 40px rgba(18, 52, 59, 0.15);
        margin-bottom: 1rem;
    }
    .card {
        background: rgba(255,255,255,0.88);
        border: 1px solid rgba(18, 52, 59, 0.08);
        border-radius: 18px;
        padding: 1rem 1.1rem;
        box-shadow: 0 10px 24px rgba(18, 52, 59, 0.06);
        margin-bottom: 1rem;
    }
    .metric {
        background: white;
        border-radius: 16px;
        padding: 1rem;
        border-top: 4px solid #f0b429;
        box-shadow: 0 8px 20px rgba(18, 52, 59, 0.06);
    }
    .small-note {
        color: #456268;
        font-size: 0.95rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user = None


def api(method: str, endpoint: str, **kwargs):
    try:
        response = requests.request(method.upper(), f"{API}{endpoint}", timeout=15, **kwargs)
        response.raise_for_status()
        if response.content:
            return response.json()
        return None
    except requests.HTTPError as exc:
        try:
            message = exc.response.json().get("detail", str(exc))
        except Exception:
            message = str(exc)
        st.error(message)
        return None
    except Exception as exc:
        st.error(f"Backend connection failed: {exc}")
        return None


def section(title: str, subtitle: str = ""):
    st.markdown(
        f"""
        <div class="hero">
            <div style="font-size: 1.7rem; font-weight: 800;">{title}</div>
            <div style="opacity: 0.9; margin-top: 0.35rem;">{subtitle}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def show_metrics(items):
    columns = st.columns(len(items))
    for column, (label, value, note) in zip(columns, items):
        with column:
            st.markdown(
                f"""
                <div class="metric">
                    <div style="font-size:0.9rem;color:#456268;">{label}</div>
                    <div style="font-size:1.9rem;font-weight:800;color:#12343b;">{value}</div>
                    <div style="font-size:0.82rem;color:#6b7b83;">{note}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def login_page():
    col1, col2 = st.columns([1.2, 1], gap="large")
    with col1:
        st.markdown(
            """
            <div class="hero" style="min-height: 420px; display:flex; flex-direction:column; justify-content:center;">
                <div style="font-size:4rem;">🏨</div>
                <div style="font-size:2.4rem;font-weight:800;margin-top:0.5rem;">Hotel Control Center</div>
                <div style="margin-top:0.75rem;font-size:1.05rem;max-width:540px;">
                    One app, three clear experiences: guests can book and track stays, receptionists can run operations, and admins can manage rooms, staff, menu, reports, and login history.
                </div>
                <div style="margin-top:1.25rem;padding:0.85rem 1rem;background:rgba(255,255,255,0.14);border-radius:14px;">
                    Demo logins: <b>admin / admin123</b>, <b>receptionist / rec123</b>, <b>guest / guest123</b>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col2:
        tab1, tab2 = st.tabs(["Sign In", "Guest Sign Up"])
        with tab1:
            with st.form("login_form"):
                username = st.text_input("Username")
                password = st.text_input("Password", type="password")
                submitted = st.form_submit_button("Sign In", type="primary", use_container_width=True)
            if submitted:
                user = api("post", "/auth/login", json={"username": username, "password": password})
                if user:
                    st.session_state.logged_in = True
                    st.session_state.user = user
                    st.rerun()
        with tab2:
            with st.form("register_form"):
                fname = st.text_input("First name")
                lname = st.text_input("Last name")
                username = st.text_input("Create username")
                email = st.text_input("Email")
                phone = st.text_input("Phone")
                password = st.text_input("Create password", type="password")
                submitted = st.form_submit_button("Create Guest Account", type="primary", use_container_width=True)
            if submitted:
                created = api(
                    "post",
                    "/auth/register",
                    json={
                        "fname": fname,
                        "lname": lname,
                        "username": username,
                        "email": email,
                        "phone": phone,
                        "password": password,
                    },
                )
                if created:
                    st.success("Guest account created. Sign in with the new credentials.")


def logout():
    st.session_state.logged_in = False
    st.session_state.user = None
    st.rerun()


def sidebar():
    user = st.session_state.user
    with st.sidebar:
        st.markdown(f"### {user['fname']} {user['lname']}")
        st.caption(f"{user['role'].title()} portal")
        if user["role"] == "admin":
            options = ["Dashboard", "Rooms", "Reservations", "Users", "Menu", "Reports"]
        elif user["role"] == "receptionist":
            options = ["Dashboard", "Book Room", "Reservations", "Check In / Out", "Food Orders", "Payments"]
        else:
            options = ["Explore Rooms", "Book Stay", "My Bookings", "Order Food", "Feedback"]
        page = st.radio("Navigation", options, label_visibility="collapsed")
        st.divider()
        if st.button("Logout", use_container_width=True):
            logout()
    return page


def booking_form(current_user, title="Create Reservation"):
    rooms = api("get", "/rooms", params={"status": "available"}) or []
    if not rooms:
        st.warning("No rooms are currently available.")
        return
    room_options = {
        f"Room {room['room_number']} | {room['category'].title()} | Rs {room['default_rate']:.0f}": room
        for room in rooms
    }
    with st.form(f"booking_form_{title}"):
        st.subheader(title)
        col1, col2 = st.columns(2)
        with col1:
            fname = st.text_input("Guest first name", value=current_user.get("fname", ""))
            lname = st.text_input("Guest last name", value=current_user.get("lname", ""))
            phone = st.text_input("Phone", value=current_user.get("phone", ""))
            email = st.text_input("Email", value=current_user.get("email", ""))
            occupants = st.number_input("Occupants", min_value=1, max_value=8, value=1)
        with col2:
            selected_label = st.selectbox("Choose room", list(room_options.keys()))
            selected_room = room_options[selected_label]
            check_in_date = st.date_input("Check-in", min_value=date.today(), value=date.today())
            check_out_date = st.date_input("Check-out", min_value=date.today() + timedelta(days=1), value=date.today() + timedelta(days=1))
            override_rate = st.number_input("Custom rate", min_value=0.0, value=float(selected_room["default_rate"]))
        guaranteed = st.checkbox("Guaranteed booking")
        credit_card_no = st.text_input("Credit card number", type="password") if guaranteed else None
        rate_reason = st.text_input("Rate change reason")
        submitted = st.form_submit_button("Save Reservation", type="primary", use_container_width=True)
    if submitted:
        payload = {
            "room_id": selected_room["id"],
            "guest_fname": fname,
            "guest_lname": lname,
            "guest_phone": phone,
            "guest_email": email,
            "num_occupants": occupants,
            "check_in": datetime.combine(check_in_date, datetime.min.time()).isoformat(),
            "check_out": datetime.combine(check_out_date, datetime.min.time()).isoformat(),
            "is_guaranteed": guaranteed,
            "credit_card_no": credit_card_no,
            "room_rate": override_rate,
            "rate_change_reason": rate_reason or None,
            "staff_id": current_user["id"] if current_user["role"] in {"admin", "receptionist"} else None,
            "guest_user_id": current_user["id"] if current_user["role"] == "guest" else None,
        }
        result = api("post", "/reservations", json=payload)
        if result:
            st.success(f"Reservation saved. Confirmation: {result['confirmation_no']}")
            st.rerun()


def admin_dashboard():
    rooms = api("get", "/rooms") or []
    reservations = api("get", "/reservations") or []
    users = api("get", "/users") or []
    logins = api("get", "/login-events") or []
    section("Admin Dashboard", "Manage inventory, people, pricing, and reporting from one place.")
    show_metrics(
        [
            ("Rooms", len(rooms), "Current room inventory"),
            ("Reservations", len(reservations), "All bookings on record"),
            ("Users", len(users), "Admin, receptionist, and guest accounts"),
            ("Recent Logins", len(logins), "Latest saved login events"),
        ]
    )
    col1, col2 = st.columns([1.2, 1], gap="large")
    with col1:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("Latest Reservations")
        if reservations:
            df = pd.DataFrame(reservations[:8])[["confirmation_no", "guest_fname", "guest_lname", "room_number", "status", "check_in", "check_out"]]
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("No reservations yet.")
        st.markdown("</div>", unsafe_allow_html=True)
    with col2:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("Login History")
        if logins:
            df = pd.DataFrame(logins)[["username", "role", "login_at", "client_ip"]]
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("No login data recorded yet.")
        st.markdown("</div>", unsafe_allow_html=True)


def manage_rooms():
    section("Room Management", "Add new inventory, adjust rates, and monitor status.")
    rooms = api("get", "/rooms") or []
    tab1, tab2 = st.tabs(["Current Rooms", "Add Room"])
    with tab1:
        if rooms:
            st.dataframe(pd.DataFrame(rooms), use_container_width=True, hide_index=True)
            selected = st.selectbox("Edit room", [f"{room['room_number']} ({room['status']})" for room in rooms])
            room = next(room for room in rooms if selected.startswith(room["room_number"]))
            with st.form("edit_room"):
                col1, col2 = st.columns(2)
                with col1:
                    category = st.text_input("Category", value=room["category"])
                    view = st.text_input("View", value=room["view"])
                    style = st.text_input("Style", value=room["style"])
                    beds = st.number_input("Beds", min_value=1, max_value=10, value=int(room["beds"]))
                with col2:
                    level = st.number_input("Level", min_value=1, max_value=50, value=int(room["level"]))
                    status = st.selectbox("Status", ["available", "occupied", "maintenance"], index=["available", "occupied", "maintenance"].index(room["status"]))
                    default_rate = st.number_input("Default rate", min_value=0.0, value=float(room["default_rate"]))
                    smoking = st.checkbox("Smoking", value=room["smoking"])
                save = st.form_submit_button("Update Room", type="primary", use_container_width=True)
            if save:
                updated = api(
                    "put",
                    f"/rooms/{room['id']}",
                    json={
                        "category": category,
                        "view": view,
                        "style": style,
                        "beds": beds,
                        "level": level,
                        "status": status,
                        "default_rate": default_rate,
                        "smoking": smoking,
                    },
                )
                if updated:
                    st.success("Room updated.")
                    st.rerun()
        else:
            st.info("No rooms available.")
    with tab2:
        with st.form("add_room"):
            col1, col2 = st.columns(2)
            with col1:
                room_number = st.text_input("Room number")
                category = st.selectbox("Category", ["single", "double", "deluxe", "suite"])
                level = st.number_input("Level", min_value=1, max_value=50, value=1)
                beds = st.number_input("Beds", min_value=1, max_value=10, value=1)
            with col2:
                view = st.text_input("View", value="city")
                style = st.text_input("Style", value="modern")
                default_rate = st.number_input("Default rate", min_value=0.0, value=3000.0)
                smoking = st.checkbox("Smoking allowed")
            submitted = st.form_submit_button("Add Room", type="primary", use_container_width=True)
        if submitted:
            created = api(
                "post",
                "/rooms",
                json={
                    "room_number": room_number,
                    "category": category,
                    "level": level,
                    "view": view,
                    "beds": beds,
                    "style": style,
                    "default_rate": default_rate,
                    "smoking": smoking,
                },
            )
            if created:
                st.success("Room added.")
                st.rerun()


def reservations_panel(guest_only=False):
    params = {}
    if guest_only:
        params["guest_user_id"] = st.session_state.user["id"]
        section("My Bookings", "Review upcoming stays and completed reservations.")
    else:
        section("Reservations", "Track bookings, updates, and guest details.")
    reservations = api("get", "/reservations", params=params) or []
    if reservations:
        st.dataframe(pd.DataFrame(reservations), use_container_width=True, hide_index=True)
        editable = [reservation for reservation in reservations if reservation["status"] in {"pending", "checked_in"}]
        if editable:
            choice = st.selectbox("Edit reservation", [f"{item['confirmation_no']} | {item['guest_fname']} {item['guest_lname']}" for item in editable])
            reservation = next(item for item in editable if choice.startswith(item["confirmation_no"]))
            with st.form("edit_reservation"):
                col1, col2 = st.columns(2)
                with col1:
                    guest_fname = st.text_input("First name", value=reservation["guest_fname"])
                    guest_lname = st.text_input("Last name", value=reservation["guest_lname"])
                    guest_phone = st.text_input("Phone", value=reservation["guest_phone"])
                with col2:
                    guest_email = st.text_input("Email", value=reservation.get("guest_email") or "")
                    occupants = st.number_input("Occupants", min_value=1, max_value=8, value=int(reservation["num_occupants"]))
                    guaranteed = st.checkbox("Guaranteed", value=reservation["is_guaranteed"])
                card = st.text_input("Credit card", type="password", value=reservation.get("credit_card_no") or "")
                save = st.form_submit_button("Update Reservation", type="primary", use_container_width=True)
            if save:
                result = api(
                    "put",
                    f"/reservations/{reservation['id']}",
                    json={
                        "guest_fname": guest_fname,
                        "guest_lname": guest_lname,
                        "guest_phone": guest_phone,
                        "guest_email": guest_email,
                        "num_occupants": occupants,
                        "is_guaranteed": guaranteed,
                        "credit_card_no": card or None,
                    },
                )
                if result:
                    st.success("Reservation updated.")
                    st.rerun()
    else:
        st.info("No reservations found.")


def user_feedback():
    section("Feedback", "Guests can submit feedback once the stay is completed.")
    reservations = api("get", "/reservations", params={"guest_user_id": st.session_state.user["id"], "status": "checked_out"}) or []
    if not reservations:
        st.info("No completed stays available for feedback.")
        return
    choice = st.selectbox("Select stay", [f"{item['confirmation_no']} | Room {item['room_number']}" for item in reservations])
    reservation = next(item for item in reservations if choice.startswith(item["confirmation_no"]))
    with st.form("feedback_form"):
        rating = st.slider("Rating", 1, 5, 5)
        comments = st.text_area("Comments")
        submitted = st.form_submit_button("Submit Feedback", type="primary", use_container_width=True)
    if submitted:
        result = api("post", "/feedback", json={"reservation_id": reservation["id"], "rating": rating, "comments": comments})
        if result:
            st.success("Feedback saved.")


def receptionist_dashboard():
    rooms = api("get", "/rooms") or []
    reservations = api("get", "/reservations") or []
    section("Reception Desk", "Keep arrivals, departures, food orders, and payments moving smoothly.")
    show_metrics(
        [
            ("Available Rooms", sum(room["status"] == "available" for room in rooms), "Ready to sell"),
            ("Pending", sum(item["status"] == "pending" for item in reservations), "Check-ins waiting"),
            ("Checked In", sum(item["status"] == "checked_in" for item in reservations), "Active stays"),
            ("Checked Out", sum(item["status"] == "checked_out" for item in reservations), "Completed stays"),
        ]
    )


def checkin_checkout_page():
    section("Check In / Out", "Handle arrivals, departures, and cancellations.")
    reservations = api("get", "/reservations") or []
    tab1, tab2, tab3 = st.tabs(["Check In", "Check Out", "Cancel"])
    with tab1:
        pending = [item for item in reservations if item["status"] == "pending"]
        if not pending:
            st.info("No pending reservations.")
        else:
            choice = st.selectbox("Pending reservation", [f"{item['confirmation_no']} | {item['guest_fname']} {item['guest_lname']}" for item in pending])
            reservation = next(item for item in pending if choice.startswith(item["confirmation_no"]))
            if st.button("Check In Guest", type="primary", use_container_width=True):
                result = api("post", f"/reservations/{reservation['id']}/checkin")
                if result:
                    st.success("Guest checked in.")
                    st.rerun()
    with tab2:
        active = [item for item in reservations if item["status"] == "checked_in"]
        if not active:
            st.info("No checked-in guests.")
        else:
            choice = st.selectbox("Checked-in reservation", [f"{item['confirmation_no']} | Room {item['room_number']}" for item in active])
            reservation = next(item for item in active if choice.startswith(item["confirmation_no"]))
            bill = api("get", f"/reservations/{reservation['id']}/bill") or {}
            suggested_extra = float(bill.get("extra_night_charge", 0.0)) if bill else 0.0
            if bill:
                show_metrics(
                    [
                        ("Room", f"Rs {bill['room_charges']:.0f}", "Stay charges"),
                        ("Meals", f"Rs {bill['meal_charges']:.0f}", "Unpaid or room-billed orders"),
                        ("Extra", f"Rs {bill['extra_night_charge']:.0f}", "Late checkout charge"),
                        ("Balance", f"Rs {bill['balance_due']:.0f}", "Current due"),
                    ]
                )
                if bill["extra_night_charge"] > 0:
                    st.warning(f"Suggested late checkout charge: Rs {bill['extra_night_charge']:.0f}")
            with st.form("checkout_form"):
                extra_charge = st.number_input(
                    "Extra checkout charge",
                    min_value=0.0,
                    value=suggested_extra,
                    help="Receptionist can change this before checkout.",
                )
                submitted = st.form_submit_button("Check Out Guest", type="primary", use_container_width=True)
            if submitted:
                result = api("post", f"/reservations/{reservation['id']}/checkout", json={"extra_night_charge": extra_charge})
                if result:
                    st.success(f"Checked out. Total owed: Rs {result['total_owed']:.0f}")
                    if result["extra_night_charge"] > 0:
                        st.warning(f"Extra charge added: Rs {result['extra_night_charge']:.0f}")
                    st.rerun()
    with tab3:
        open_items = [item for item in reservations if item["status"] in {"pending", "checked_in"}]
        if not open_items:
            st.info("No cancellable reservations.")
        else:
            choice = st.selectbox("Reservation to cancel", [f"{item['confirmation_no']} | {item['guest_fname']} {item['guest_lname']}" for item in open_items])
            reservation = next(item for item in open_items if choice.startswith(item["confirmation_no"]))
            reason = st.selectbox("Reason", ["personal", "misbehaviour", "lack_of_facility", "non_payment"])
            if st.button("Cancel Reservation", type="primary", use_container_width=True):
                result = api(
                    "post",
                    "/cancellations",
                    json={"reservation_id": reservation["id"], "cancel_reason": reason, "staff_id": st.session_state.user["id"]},
                )
                if result:
                    st.success("Reservation cancelled.")
                    st.rerun()


def food_orders_page(guest_mode=False):
    section("Food Orders", "Create restaurant or room-service orders against active stays.")
    menu = api("get", "/menu") or []
    params = {"status": "checked_in"}
    if guest_mode:
        params["guest_user_id"] = st.session_state.user["id"]
    active_stays = api("get", "/reservations", params=params) or []
    if not active_stays:
        st.info("No checked-in stay available for food orders.")
        return
    if guest_mode:
        stay_choice = st.selectbox("Select stay", [f"{item['confirmation_no']} | Room {item['room_number']}" for item in active_stays])
    else:
        stay_choice = st.selectbox("Select guest", [f"{item['confirmation_no']} | {item['guest_fname']} {item['guest_lname']}" for item in active_stays])
    stay = next(item for item in active_stays if stay_choice.startswith(item["confirmation_no"]))
    service_type = st.radio("Service type", ["room_service"] if guest_mode else ["restaurant", "room_service"], horizontal=True)
    supported_items = [item for item in menu if item["service_channel"] in {"both", service_type}]
    selected_items = []
    with st.form("food_order_form"):
        for item in supported_items:
            qty = st.number_input(f"{item['name']} - Rs {item['current_price']:.0f}", min_value=0, max_value=10, value=0, key=f"menu_{item['id']}")
            if qty > 0:
                selected_items.append({"menu_item_id": item["id"], "quantity": qty})
        billed_to_room = True if guest_mode else st.checkbox("Bill to room", value=True)
        payment_type = None if billed_to_room else st.selectbox("Payment type", ["cash", "credit_card", "debit_card", "upi"])
        submitted = st.form_submit_button("Place Order", type="primary", use_container_width=True)
    if submitted:
        if not selected_items:
            st.error("Choose at least one menu item.")
        else:
            result = api(
                "post",
                "/meal-orders",
                json={
                    "reservation_id": stay["id"],
                    "service_type": service_type,
                    "items": selected_items,
                    "billed_to_room": billed_to_room,
                    "payment_type": payment_type,
                },
            )
            if result:
                st.success(f"Food order saved. Total: Rs {result['total']:.0f}")
                st.rerun()
    orders = api("get", f"/meal-orders/reservation/{stay['id']}") or []
    if orders:
        st.subheader("Order history")
        st.dataframe(pd.DataFrame(orders), use_container_width=True, hide_index=True)


def payments_page():
    section("Payments", "Record charges against any active or completed reservation.")
    reservations = api("get", "/reservations") or []
    eligible = [item for item in reservations if item["status"] in {"checked_in", "checked_out"}]
    if not eligible:
        st.info("No reservations ready for payment.")
        return
    choice = st.selectbox("Reservation", [f"{item['confirmation_no']} | {item['guest_fname']} {item['guest_lname']}" for item in eligible])
    reservation = next(item for item in eligible if choice.startswith(item["confirmation_no"]))
    bill = api("get", f"/reservations/{reservation['id']}/bill") or {}
    if bill:
        show_metrics(
            [
                ("Total", f"Rs {bill['total']:.0f}", "Overall bill"),
                ("Paid", f"Rs {bill['payments_made']:.0f}", "Payments captured"),
                ("Balance", f"Rs {bill['balance_due']:.0f}", "Still due"),
            ]
        )
        if bill["extra_night_charge"] > 0:
            st.info(f"Late checkout charge included in this bill: Rs {bill['extra_night_charge']:.0f}")
    with st.form("payment_form"):
        amount = st.number_input("Amount", min_value=0.0, value=float(bill.get("balance_due", 0.0)))
        payment_type = st.selectbox("Payment type", ["cash", "credit_card", "debit_card", "upi"])
        source = st.selectbox("Source", ["room", "restaurant", "room_service"])
        submitted = st.form_submit_button("Save Payment", type="primary", use_container_width=True)
    if submitted:
        result = api("post", "/payments", json={"reservation_id": reservation["id"], "amount": amount, "payment_type": payment_type, "source": source})
        if result:
            st.success("Payment recorded.")
            st.rerun()
    payments = api("get", f"/payments/reservation/{reservation['id']}") or []
    if payments:
        st.subheader("Payment history")
        st.dataframe(pd.DataFrame(payments), use_container_width=True, hide_index=True)


def manage_users():
    section("Users", "Manage staff accounts and review who is logging in.")
    users = api("get", "/users") or []
    logins = api("get", "/login-events") or []
    tab1, tab2, tab3 = st.tabs(["All Users", "Create User", "Login History"])
    with tab1:
        if users:
            st.dataframe(pd.DataFrame(users), use_container_width=True, hide_index=True)
            editable_users = [user for user in users if user["username"] != "admin"]
            if editable_users:
                choice = st.selectbox("Reset password for", [f"{user['username']} ({user['role']})" for user in users])
                user = next(user for user in users if choice.startswith(user["username"]))
                new_password = st.text_input("New password", type="password")
                if st.button("Update Password", type="primary", use_container_width=True):
                    result = api("put", f"/users/{user['id']}/password", json={"new_password": new_password})
                    if result:
                        st.success("Password updated.")
        else:
            st.info("No users available.")
    with tab2:
        with st.form("create_user_form"):
            col1, col2 = st.columns(2)
            with col1:
                username = st.text_input("Username")
                password = st.text_input("Password", type="password")
                role = st.selectbox("Role", ["admin", "receptionist", "guest"])
                fname = st.text_input("First name")
            with col2:
                lname = st.text_input("Last name")
                email = st.text_input("Email")
                phone = st.text_input("Phone")
            submitted = st.form_submit_button("Create User", type="primary", use_container_width=True)
        if submitted:
            result = api(
                "post",
                "/users",
                json={
                    "username": username,
                    "password": password,
                    "role": role,
                    "fname": fname,
                    "lname": lname,
                    "email": email,
                    "phone": phone,
                },
            )
            if result:
                st.success("User created.")
                st.rerun()
    with tab3:
        if logins:
            st.dataframe(pd.DataFrame(logins), use_container_width=True, hide_index=True)
        else:
            st.info("No login history yet.")


def menu_management():
    section("Menu Management", "Keep restaurant and room-service pricing current.")
    menu = api("get", "/menu") or []
    tab1, tab2 = st.tabs(["Menu Items", "Add Item"])
    with tab1:
        if menu:
            st.dataframe(pd.DataFrame(menu), use_container_width=True, hide_index=True)
            choice = st.selectbox("Edit item", [f"{item['name']} ({item['meal_type']})" for item in menu])
            item = next(item for item in menu if choice.startswith(item["name"]))
            with st.form("edit_menu_form"):
                col1, col2 = st.columns(2)
                with col1:
                    name = st.text_input("Name", value=item["name"])
                    meal_type = st.selectbox("Meal type", ["breakfast", "lunch", "dinner", "snack"], index=["breakfast", "lunch", "dinner", "snack"].index(item["meal_type"]))
                    default_price = st.number_input("Default price", min_value=0.0, value=float(item["default_price"]))
                with col2:
                    current_price = st.number_input("Current price", min_value=0.0, value=float(item["current_price"]))
                    service_channel = st.selectbox("Channel", ["restaurant", "room_service", "both"], index=["restaurant", "room_service", "both"].index(item["service_channel"]))
                    active = st.checkbox("Active", value=item["is_active"])
                description = st.text_area("Description", value=item["description"])
                submitted = st.form_submit_button("Update Item", type="primary", use_container_width=True)
            if submitted:
                result = api(
                    "put",
                    f"/menu/{item['id']}",
                    json={
                        "name": name,
                        "meal_type": meal_type,
                        "description": description,
                        "default_price": default_price,
                        "current_price": current_price,
                        "service_channel": service_channel,
                        "is_active": active,
                    },
                )
                if result:
                    st.success("Menu item updated.")
                    st.rerun()
        else:
            st.info("Menu is empty.")
    with tab2:
        with st.form("add_menu_form"):
            col1, col2 = st.columns(2)
            with col1:
                name = st.text_input("Item name")
                meal_type = st.selectbox("Meal type", ["breakfast", "lunch", "dinner", "snack"], key="new_meal_type")
                default_price = st.number_input("Default price", min_value=0.0, value=100.0)
            with col2:
                current_price = st.number_input("Current price", min_value=0.0, value=100.0)
                service_channel = st.selectbox("Channel", ["restaurant", "room_service", "both"], key="new_service_channel")
                active = st.checkbox("Active", value=True, key="new_active")
            description = st.text_area("Description")
            submitted = st.form_submit_button("Add Menu Item", type="primary", use_container_width=True)
        if submitted:
            result = api(
                "post",
                "/menu",
                json={
                    "name": name,
                    "meal_type": meal_type,
                    "description": description,
                    "default_price": default_price,
                    "current_price": current_price,
                    "service_channel": service_channel,
                    "is_active": active,
                },
            )
            if result:
                st.success("Menu item created.")
                st.rerun()


def reports_page():
    section("Reports", "Review occupancy, room revenue, food revenue, and pricing exceptions.")
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("From", value=date.today() - timedelta(days=30))
    with col2:
        end_date = st.date_input("To", value=date.today())
    occupancy = api("get", "/reports/occupancy", params={"start_date": start_date.isoformat(), "end_date": end_date.isoformat()}) or {}
    room_revenue = api("get", "/reports/room-revenue", params={"start_date": start_date.isoformat(), "end_date": end_date.isoformat()}) or {}
    food_revenue = api("get", "/reports/food-revenue", params={"start_date": start_date.isoformat(), "end_date": end_date.isoformat()}) or {}
    exceptions = api("get", "/reports/exceptions") or {}
    show_metrics(
        [
            ("Occupancy", f"{occupancy.get('occupancy_rate', 0)}%", "Projected + active"),
            ("Room Revenue", f"Rs {room_revenue.get('total_revenue', 0):.0f}", "Selected period"),
            ("Food Revenue", f"Rs {food_revenue.get('total_food_revenue', 0):.0f}", "Selected period"),
            ("Food Orders", food_revenue.get("order_count", 0), "Orders in range"),
        ]
    )
    if room_revenue.get("breakdown"):
        st.subheader("Room revenue breakdown")
        st.dataframe(pd.DataFrame(room_revenue["breakdown"]), use_container_width=True, hide_index=True)
    if food_revenue.get("breakdown"):
        st.subheader("Food order breakdown")
        st.dataframe(pd.DataFrame(food_revenue["breakdown"]), use_container_width=True, hide_index=True)
    else:
        st.info("No food orders found in the selected date range.")
    if exceptions:
        col3, col4 = st.columns(2)
        with col3:
            st.subheader("Rate overrides")
            st.dataframe(pd.DataFrame(exceptions.get("room_rate_exceptions", [])), use_container_width=True, hide_index=True)
        with col4:
            st.subheader("Menu price overrides")
            st.dataframe(pd.DataFrame(exceptions.get("food_price_exceptions", [])), use_container_width=True, hide_index=True)


def guest_explore_rooms():
    section("Explore Rooms", "Guests can browse currently available rooms before booking.")
    rooms = api("get", "/rooms", params={"status": "available"}) or []
    if rooms:
        st.dataframe(pd.DataFrame(rooms), use_container_width=True, hide_index=True)
    else:
        st.info("No rooms are available right now.")


def main():
    if not st.session_state.logged_in:
        login_page()
        return

    page = sidebar()
    role = st.session_state.user["role"]

    if role == "admin":
        if page == "Dashboard":
            admin_dashboard()
        elif page == "Rooms":
            manage_rooms()
        elif page == "Reservations":
            reservations_panel()
        elif page == "Users":
            manage_users()
        elif page == "Menu":
            menu_management()
        elif page == "Reports":
            reports_page()
    elif role == "receptionist":
        if page == "Dashboard":
            receptionist_dashboard()
        elif page == "Book Room":
            section("New Booking", "Create and save reservations for walk-in and phone guests.")
            booking_form(st.session_state.user, title="Create Reception Booking")
        elif page == "Reservations":
            reservations_panel()
        elif page == "Check In / Out":
            checkin_checkout_page()
        elif page == "Food Orders":
            food_orders_page()
        elif page == "Payments":
            payments_page()
    else:
        if page == "Explore Rooms":
            guest_explore_rooms()
        elif page == "Book Stay":
            section("Book Stay", "Guests can create reservations directly from their portal.")
            booking_form(st.session_state.user, title="Create Guest Booking")
        elif page == "My Bookings":
            reservations_panel(guest_only=True)
        elif page == "Order Food":
            food_orders_page(guest_mode=True)
        elif page == "Feedback":
            user_feedback()


if __name__ == "__main__":
    main()
