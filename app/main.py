import os
import httpx
import shutil

from pathlib import Path
from typing import Optional
from datetime import datetime

from dotenv import load_dotenv

from fastapi import (
    FastAPI,
    Request,
    Form,
    Depends,
    File,
    UploadFile,
)

from starlette.middleware.sessions import SessionMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .database import Base, engine, get_db
from . import models
from sqlalchemy.orm import Session
from passlib.context import CryptContext


pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto"
)


# ---------------------------------------------------------
# APP
# ---------------------------------------------------------

app = FastAPI(
    title="Taste of Home",
    description="Homemade Spicy Food Store",
    version="1.0.0",
)

app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv(
        "SESSION_SECRET_KEY",
        "taste-of-home-secret-key-change-this"
    )
)


# Create database tables
Base.metadata.create_all(bind=engine)


# ---------------------------------------------------------
# BASE DIRECTORY
# ---------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent


# ---------------------------------------------------------
# LOAD ENVIRONMENT VARIABLES
# ---------------------------------------------------------

load_dotenv(
    BASE_DIR.parent / ".env"
)

TWOFACTOR_API_KEY = os.getenv("TWOFACTOR_API_KEY")

if not TWOFACTOR_API_KEY:
    raise RuntimeError(
        "TWOFACTOR_API_KEY is missing from .env"
    )


# ---------------------------------------------------------
# STATIC FILES
# ---------------------------------------------------------

STATIC_DIR = BASE_DIR / "static"

app.mount(
    "/static",
    StaticFiles(directory=str(STATIC_DIR)),
    name="static",
)


# ---------------------------------------------------------
# TEMPLATES
# ---------------------------------------------------------

TEMPLATES_DIR = BASE_DIR / "templates"

templates = Jinja2Templates(
    directory=str(TEMPLATES_DIR)
)


# ---------------------------------------------------------
# HOME PAGE
# ---------------------------------------------------------

@app.get("/")
async def home(
    request: Request,
    db: Session = Depends(get_db),
):

    customer_id = request.session.get("customer_id")

    customer = None

    if customer_id:

        customer = (
            db.query(models.Customer)
            .filter(
                models.Customer.id == customer_id
            )
            .first()
        )

    return templates.TemplateResponse(
        request=request,
        name="home.html",
        context={
            "request": request,
            "site_name": "Taste of Home",
            "customer": customer,
        },
    )


@app.get("/register")
async def register_page(request: Request):

    return templates.TemplateResponse(
        request=request,
        name="accounts/register.html",
        context={
            "request": request,
        },
    )
# ---------------------------------------------------------
# FORGOT PASSWORD PAGE
# ---------------------------------------------------------

@app.get("/forgot-password", response_class=HTMLResponse)
async def forgot_password_page(
    request: Request,
):
    return templates.TemplateResponse(
        request=request,
        name="accounts/forgot_password.html",
        context={
            "request": request,
        },
    )


@app.post("/forgot-password/send-otp")
async def forgot_password_send_otp(
    request: Request,
    mobile_number: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
    db: Session = Depends(get_db),
):
    mobile_number = mobile_number.strip()
    new_password = new_password.strip()
    confirm_password = confirm_password.strip()

    # Validate mobile
    if not mobile_number:
        return {
            "success": False,
            "message": "Mobile number is required."
        }

    if not mobile_number.isdigit() or len(mobile_number) != 10:
        return {
            "success": False,
            "message": "Please enter a valid 10-digit mobile number."
        }

    # Validate password
    if not new_password:
        return {
            "success": False,
            "message": "Please enter a new password."
        }

    if len(new_password) < 6:
        return {
            "success": False,
            "message": "Password must be at least 6 characters."
        }

    if new_password != confirm_password:
        return {
            "success": False,
            "message": "Passwords do not match."
        }

    # Check registered account
    customer = (
        db.query(models.Customer)
        .filter(
            models.Customer.mobile_number == mobile_number
        )
        .first()
    )

    if not customer:
        return {
            "success": False,
            "message": "This mobile number is not registered."
        }

    # Check API key
    if not TWOFACTOR_API_KEY:
        return {
            "success": False,
            "message": "TWOFACTOR_API_KEY is missing from .env"
        }

    try:
        phone_number = "91" + mobile_number

        url = (
            f"https://2factor.in/API/V1/"
            f"{TWOFACTOR_API_KEY}/SMS/"
            f"{phone_number}/AUTOGEN"
        )

        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(url)

        print(
            "FORGOT PASSWORD OTP RESPONSE:",
            response.status_code
        )
        print(
            "FORGOT PASSWORD OTP BODY:",
            response.text
        )

        data = response.json()

        if data.get("Status") == "Success":

            # Remember only the mobile number.
            # DO NOT store the password in the session.
            request.session["forgot_password_mobile"] = mobile_number

            return {
                "success": True,
                "message": "OTP sent successfully.",
                "session_id": data.get("Details")
            }

        return {
            "success": False,
            "message": data.get(
                "Details",
                "Unable to send OTP."
            )
        }

    except Exception as e:
        print(
            "FORGOT PASSWORD SEND OTP ERROR:",
            repr(e)
        )

        return {
            "success": False,
            "message": "Unable to send OTP. Please try again."
        }


@app.post("/forgot-password/verify-otp")
async def forgot_password_verify_otp(
    request: Request,
    mobile_number: str = Form(...),
    otp_code: str = Form(...),
    session_id: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
    db: Session = Depends(get_db),
):
    mobile_number = mobile_number.strip()
    otp_code = otp_code.strip()
    session_id = session_id.strip()
    new_password = new_password.strip()
    confirm_password = confirm_password.strip()

    # Check mobile session
    saved_mobile = request.session.get(
        "forgot_password_mobile"
    )

    if saved_mobile != mobile_number:
        return {
            "success": False,
            "message": "Please request a new OTP."
        }

    # Validate OTP
    if not otp_code:
        return {
            "success": False,
            "message": "Please enter the OTP."
        }

    # Validate password again
    if len(new_password) < 6:
        return {
            "success": False,
            "message": "Password must be at least 6 characters."
        }

    if new_password != confirm_password:
        return {
            "success": False,
            "message": "Passwords do not match."
        }

    if not TWOFACTOR_API_KEY:
        return {
            "success": False,
            "message": "TWOFACTOR_API_KEY is missing from .env"
        }

    try:
        # Verify OTP with 2Factor
        url = (
            f"https://2factor.in/API/V1/"
            f"{TWOFACTOR_API_KEY}/SMS/VERIFY/"
            f"{session_id}/{otp_code}"
        )

        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(url)

        print(
            "FORGOT PASSWORD VERIFY RESPONSE:",
            response.status_code
        )
        print(
            "FORGOT PASSWORD VERIFY BODY:",
            response.text
        )

        data = response.json()

        if data.get("Status") != "Success":
            return {
                "success": False,
                "message": data.get(
                    "Details",
                    "Invalid OTP. Please try again."
                )
            }

        # Find customer
        customer = (
            db.query(models.Customer)
            .filter(
                models.Customer.mobile_number == mobile_number
            )
            .first()
        )

        if not customer:
            return {
                "success": False,
                "message": "Account not found."
            }

        # OTP VERIFIED
        # NOW change the password
        customer.password_hash = pwd_context.hash(
            new_password
        )

        db.commit()

        # Clear forgot-password session
        request.session.pop(
            "forgot_password_mobile",
            None
        )

        return {
            "success": True,
            "verified": True,
            "password_reset": True,
            "message": "Password reset successfully."
        }

    except Exception as e:
        print(
            "FORGOT PASSWORD VERIFY ERROR:",
            repr(e)
        )

        return {
            "success": False,
            "message": "Unable to verify OTP. Please try again."
        }




@app.get("/login")
async def login_page(request: Request):

    return templates.TemplateResponse(
        request=request,
        name="accounts/login.html",
        context={
            "request": request,
        },
    )


# ---------------------------------------------------------
# LOGIN
# ---------------------------------------------------------

@app.post("/login")
async def login_user(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):

    username = username.strip()

    if not username or not password:
        return {
            "success": False,
            "message": "Username and password are required.",
        }

    # -----------------------------------------------------
    # FIND CUSTOMER
    # -----------------------------------------------------

    customer = (
        db.query(models.Customer)
        .filter(
            models.Customer.username == username
        )
        .first()
    )

    if not customer:
        return {
            "success": False,
            "message": "Invalid username or password.",
        }

    # -----------------------------------------------------
    # CHECK PASSWORD
    # -----------------------------------------------------

    if not pwd_context.verify(
        password,
        customer.password_hash
    ):
        return {
            "success": False,
            "message": "Invalid username or password.",
        }

    # -----------------------------------------------------
    # CHECK ACCOUNT
    # -----------------------------------------------------

    if customer.is_active is False:
        return {
            "success": False,
            "message": "Your account is inactive.",
        }

    # -----------------------------------------------------
    # LOGIN SUCCESS
    # -----------------------------------------------------

    request.session["customer_id"] = customer.id
    request.session["username"] = customer.username

    return {
        "success": True,
        "message": "Login successful.",
        "username": customer.username,
    }


@app.get("/account")
async def account_page(
    request: Request,
    db: Session = Depends(get_db),
):

    customer_id = request.session.get("customer_id")

    # User is NOT logged in
    if not customer_id:
        return RedirectResponse(
            url="/login",
            status_code=303
        )

    # Find logged-in customer
    customer = (
        db.query(models.Customer)
        .filter(
            models.Customer.id == customer_id
        )
        .first()
    )

    # Customer no longer exists
    if not customer:
        request.session.clear()

        return RedirectResponse(
            url="/login",
            status_code=303
        )

    return templates.TemplateResponse(
        request=request,
        name="accounts/account.html",
        context={
            "request": request,
            "customer": customer,
        },
    )


# ---------------------------------------------------------
# SHOP PAGE
# ---------------------------------------------------------

@app.get("/shop")
async def shop_page(
    request: Request,
    db: Session = Depends(get_db),
):

    products = (
        db.query(models.Product)
        .filter(
            models.Product.is_active == True
        )
        .all()
    )

    return templates.TemplateResponse(
        request=request,
        name="shop.html",
        context={
            "request": request,
            "products": products,
        },
    )


# ---------------------------------------------------------
# SEND OTP
# ---------------------------------------------------------

@app.post("/send-otp")
async def send_otp(
    mobile_number: str = Form(...)
):

    mobile_number = mobile_number.strip()

    if not mobile_number:
        return {
            "success": False,
            "message": "Mobile number is required."
        }

    if not mobile_number.isdigit() or len(mobile_number) != 10:
        return {
            "success": False,
            "message": "Please enter a valid 10-digit Indian mobile number."
        }

    if not TWOFACTOR_API_KEY:
        return {
            "success": False,
            "message": "TWOFACTOR_API_KEY is missing from .env"
        }

    try:

        phone_number = "91" + mobile_number

        url = (
            f"https://2factor.in/API/V1/"
            f"{TWOFACTOR_API_KEY}/SMS/"
            f"{phone_number}/AUTOGEN"
        )

        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(url)

        print(
            "2Factor response:",
            response.status_code
        )

        print(
            "2Factor body:",
            response.text
        )

        data = response.json()

        if data.get("Status") == "Success":

            return {
                "success": True,
                "message": "OTP sent successfully.",
                "session_id": data.get("Details")
            }

        return {
            "success": False,
            "message": data.get(
                "Details",
                "2Factor could not send the OTP."
            )
        }

    except Exception as e:

        print(
            "SEND OTP ERROR:",
            repr(e)
        )

        return {
            "success": False,
            "message": str(e)
        }


# ---------------------------------------------------------
# VERIFY OTP
# ---------------------------------------------------------

@app.post("/verify-otp")
async def verify_otp(
    request: Request,
    mobile_number: str = Form(...),
    otp_code: str = Form(...),
    session_id: str = Form(...),
):

    mobile_number = mobile_number.strip()
    otp_code = otp_code.strip()
    session_id = session_id.strip()

    if not mobile_number:
        return {
            "success": False,
            "message": "Mobile number is required."
        }

    if not otp_code:
        return {
            "success": False,
            "message": "OTP is required."
        }

    if not session_id:
        return {
            "success": False,
            "message": "OTP session is missing. Please send OTP again."
        }

    if not TWOFACTOR_API_KEY:
        return {
            "success": False,
            "message": "TWOFACTOR_API_KEY is missing from .env"
        }

    try:

        url = (
            f"https://2factor.in/API/V1/"
            f"{TWOFACTOR_API_KEY}/SMS/VERIFY/"
            f"{session_id}/{otp_code}"
        )

        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(url)

        print(
            "2Factor VERIFY response:",
            response.status_code
        )

        print(
            "2Factor VERIFY body:",
            response.text
        )

        data = response.json()

        if data.get("Status") == "Success":

            request.session[
                "otp_verified_mobile"
            ] = mobile_number

            return {
                "success": True,
                "verified": True,
                "message": "Mobile number verified successfully."
            }

        return {
            "success": False,
            "verified": False,
            "message": data.get(
                "Details",
                "Invalid OTP. Please try again."
            )
        }

    except Exception as e:

        print(
            "VERIFY OTP ERROR:",
            repr(e)
        )

        return {
            "success": False,
            "verified": False,
            "message": str(e)
        }


# ---------------------------------------------------------
# REGISTER ACCOUNT
# ---------------------------------------------------------

@app.post("/register")
async def register_user(
    request: Request,
    username: str = Form(...),
    mobile_number: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
    db: Session = Depends(get_db),
):

    username = username.strip()
    mobile_number = mobile_number.strip()
    email = email.strip()

    # -----------------------------------------------------
    # CHECK BASIC FIELDS
    # -----------------------------------------------------

    if not username:
        return {
            "success": False,
            "message": "Username is required."
        }

    if not mobile_number:
        return {
            "success": False,
            "message": "Mobile number is required."
        }

    if not email:
        return {
            "success": False,
            "message": "Email address is required."
        }

    if not password:
        return {
            "success": False,
            "message": "Password is required."
        }

    # -----------------------------------------------------
    # PASSWORD LENGTH
    # -----------------------------------------------------

    if len(password) < 8:
        return {
            "success": False,
            "message": "Password must be at least 8 characters."
        }

    # -----------------------------------------------------
    # PASSWORD MATCH
    # -----------------------------------------------------

    if password != confirm_password:
        return {
            "success": False,
            "message": "Passwords do not match."
        }

    # -----------------------------------------------------
    # CHECK OTP VERIFICATION
    # -----------------------------------------------------

    verified_mobile = request.session.get(
        "otp_verified_mobile"
    )

    if verified_mobile != mobile_number:
        return {
            "success": False,
            "message": "Please verify your mobile number with OTP first."
        }

    # -----------------------------------------------------
    # CHECK EXISTING USERNAME
    # -----------------------------------------------------

    existing_username = (
        db.query(models.Customer)
        .filter(
            models.Customer.username == username
        )
        .first()
    )

    if existing_username:
        return {
            "success": False,
            "message": "Username already exists."
        }

    # -----------------------------------------------------
    # CHECK EXISTING MOBILE
    # -----------------------------------------------------

    existing_mobile = (
        db.query(models.Customer)
        .filter(
            models.Customer.mobile_number == mobile_number
        )
        .first()
    )

    if existing_mobile:
        return {
            "success": False,
            "message": "Mobile number is already registered."
        }

    # -----------------------------------------------------
    # CHECK EXISTING EMAIL
    # -----------------------------------------------------

    existing_email = (
        db.query(models.Customer)
        .filter(
            models.Customer.email == email
        )
        .first()
    )

    if existing_email:
        return {
            "success": False,
            "message": "Email address is already registered."
        }

    # -----------------------------------------------------
    # HASH PASSWORD
    # -----------------------------------------------------

    password_hash = pwd_context.hash(password)

    # -----------------------------------------------------
    # CREATE CUSTOMER
    # -----------------------------------------------------

    customer = models.Customer(
        username=username,
        full_name=username,
        mobile_number=mobile_number,
        email=email,
        password_hash=password_hash,
        is_active=True,
        is_verified=True,
    )

    db.add(customer)
    db.commit()
    db.refresh(customer)

    # -----------------------------------------------------
    # REMOVE OTP VERIFICATION FROM SESSION
    # -----------------------------------------------------

    request.session.pop(
        "otp_verified_mobile",
        None
    )

    # -----------------------------------------------------
    # SUCCESS
    # -----------------------------------------------------

    return {
        "success": True,
        "message": "Account created successfully.",
    }
# ---------------------------------------------------------
# HEALTH CHECK
# ---------------------------------------------------------

@app.get("/health")
async def health():

    return {
        "status": "ok",
        "message": "Taste of Home is running",
    }


# ---------------------------------------------------------
# LOGOUT
# ---------------------------------------------------------

@app.get("/logout")
async def logout(request: Request):

    # Clear logged-in user session
    request.session.clear()

    # Go directly to login page
    return RedirectResponse(
        url="/login",
        status_code=303
    )


# ---------------------------------------------------------
# ADD PRODUCTS
# ---------------------------------------------------------

@app.get("/add-products")
async def add_products(
    db: Session = Depends(get_db),
):

    products = [

        models.Product(
            name="Homemade Spicy Mango Pickle",
            description="Traditional homemade mango pickle with authentic spices.",
            price=299,
            category="Pickles",
            stock=50,
            is_active=True,
        ),

        models.Product(
            name="Homemade Special Masala",
            description="Rich aromatic spice blend for everyday cooking.",
            price=249,
            category="Masalas",
            stock=50,
            is_active=True,
        ),

        models.Product(
            name="Homemade Spicy Chutney",
            description="Fresh homemade chutney packed with flavour.",
            price=199,
            category="Chutneys",
            stock=50,
            is_active=True,
        ),

        models.Product(
            name="Homemade Crispy Snack",
            description="Crunchy, tasty and made in small batches.",
            price=179,
            category="Snacks",
            stock=50,
            is_active=True,
        ),

    ]

    for product in products:
        db.add(product)

    db.commit()

    return {
        "success": True,
        "message": "Products added successfully."
    }


# ---------------------------------------------------------
# ADD PRODUCT TO CART
# ---------------------------------------------------------

@app.post("/cart/add")
async def add_to_cart(
    request: Request,
    product_id: int = Form(...),
    db: Session = Depends(get_db),
):

    product = (
        db.query(models.Product)
        .filter(
            models.Product.id == product_id,
            models.Product.is_active == True
        )
        .first()
    )

    if not product:
        return RedirectResponse(
            url="/shop",
            status_code=303
        )

    cart = request.session.get(
        "cart",
        {}
    )

    product_id_str = str(product_id)

    if product_id_str in cart:
        cart[product_id_str] += 1
    else:
        cart[product_id_str] = 1

    request.session["cart"] = cart

    return RedirectResponse(
        url="/cart",
        status_code=303
    )


# ---------------------------------------------------------
# CART PAGE
# ---------------------------------------------------------

@app.get("/cart")
async def cart_page(
    request: Request,
    db: Session = Depends(get_db),
):

    cart = request.session.get(
        "cart",
        {}
    )

    cart_items = []

    for product_id, quantity in cart.items():

        product = (
            db.query(models.Product)
            .filter(
                models.Product.id == int(product_id),
                models.Product.is_active == True
            )
            .first()
        )

        if product:

            cart_items.append({
                "product": product,
                "quantity": quantity,
            })

    cart_total = 0

    for item in cart_items:

        cart_total += (
            item["product"].price *
            item["quantity"]
        )

    return templates.TemplateResponse(
        request=request,
        name="cart.html",
        context={
            "request": request,
            "cart_items": cart_items,
            "cart_total": cart_total,
        },
    )


# ---------------------------------------------------------
# CHECKOUT PAGE
# ---------------------------------------------------------

@app.get("/checkout")
async def checkout_page(
    request: Request,
    db: Session = Depends(get_db),
):

    # -----------------------------------------------------
    # CHECK LOGIN
    # -----------------------------------------------------

    customer_id = request.session.get(
        "customer_id"
    )

    if not customer_id:
        return RedirectResponse(
            url="/login",
            status_code=303
        )

    # -----------------------------------------------------
    # GET CUSTOMER
    # -----------------------------------------------------

    customer = (
        db.query(models.Customer)
        .filter(
            models.Customer.id == customer_id
        )
        .first()
    )

    if not customer:

        request.session.clear()

        return RedirectResponse(
            url="/login",
            status_code=303
        )

    # -----------------------------------------------------
    # GET CART
    # -----------------------------------------------------

    cart = request.session.get(
        "cart",
        {}
    )

    if not cart:
        return RedirectResponse(
            url="/cart",
            status_code=303
        )

    # -----------------------------------------------------
    # BUILD CART ITEMS
    # -----------------------------------------------------

    cart_items = []

    for product_id, quantity in cart.items():

        product = (
            db.query(models.Product)
            .filter(
                models.Product.id == int(product_id),
                models.Product.is_active == True
            )
            .first()
        )

        if product:

            cart_items.append({
                "product": product,
                "quantity": quantity,
            })

    # -----------------------------------------------------
    # CALCULATE TOTAL
    # -----------------------------------------------------

    cart_total = 0

    for item in cart_items:

        cart_total += (
            item["product"].price *
            item["quantity"]
        )

    # -----------------------------------------------------
    # CHECK CART AFTER INVALID PRODUCTS
    # -----------------------------------------------------

    if not cart_items:

        request.session["cart"] = {}

        return RedirectResponse(
            url="/cart",
            status_code=303
        )

    # -----------------------------------------------------
    # CHECKOUT TEMPLATE
    # -----------------------------------------------------

    return templates.TemplateResponse(
        request=request,
        name="checkout.html",
        context={
            "request": request,
            "customer": customer,
            "cart_items": cart_items,
            "cart_total": cart_total,
        },
    )


# ---------------------------------------------------------
# INCREASE CART QUANTITY
# ---------------------------------------------------------

@app.post("/cart/increase")
async def increase_cart(
    request: Request,
    product_id: int = Form(...),
):

    cart = request.session.get(
        "cart",
        {}
    )

    product_id_str = str(product_id)

    if product_id_str in cart:
        cart[product_id_str] += 1

    request.session["cart"] = cart

    return RedirectResponse(
        url="/cart",
        status_code=303
    )


# ---------------------------------------------------------
# DECREASE CART QUANTITY
# ---------------------------------------------------------

@app.post("/cart/decrease")
async def decrease_cart(
    request: Request,
    product_id: int = Form(...),
):

    cart = request.session.get(
        "cart",
        {}
    )

    product_id_str = str(product_id)

    if product_id_str in cart:

        cart[product_id_str] -= 1

        if cart[product_id_str] <= 0:
            del cart[product_id_str]

    request.session["cart"] = cart

    return RedirectResponse(
        url="/cart",
        status_code=303
    )


# ---------------------------------------------------------
# REMOVE FROM CART
# ---------------------------------------------------------

@app.post("/cart/remove")
async def remove_from_cart(
    request: Request,
    product_id: int = Form(...),
):

    cart = request.session.get(
        "cart",
        {}
    )

    product_id_str = str(product_id)

    if product_id_str in cart:
        del cart[product_id_str]

    request.session["cart"] = cart

    return RedirectResponse(
        url="/cart",
        status_code=303
    )


# ---------------------------------------------------------
# PLACE ORDER
# ---------------------------------------------------------

@app.post("/place-order")
async def place_order(
    request: Request,
    full_name: str = Form(...),
    mobile_number: str = Form(...),
    shipping_address: str = Form(...),
    city: str = Form(...),
    pincode: str = Form(...),
    payment_method: str = Form("cod"),
    db: Session = Depends(get_db),
):

    # -----------------------------------------------------
    # CHECK LOGIN
    # -----------------------------------------------------

    customer_id = request.session.get(
        "customer_id"
    )

    if not customer_id:
        return RedirectResponse(
            url="/login",
            status_code=303
        )

    # -----------------------------------------------------
    # CHECK CART
    # -----------------------------------------------------

    cart = request.session.get(
        "cart",
        {}
    )

    if not cart:
        return RedirectResponse(
            url="/cart",
            status_code=303
        )

    # -----------------------------------------------------
    # ONLINE PAYMENT
    # -----------------------------------------------------
    # Do NOT create the order yet.
    # The customer must first complete the UPI payment.

    if payment_method == "online":

        request.session["pending_order"] = {
            "full_name": full_name.strip(),
            "mobile_number": mobile_number.strip(),
            "shipping_address": shipping_address.strip(),
            "city": city.strip(),
            "pincode": pincode.strip(),
        }

        return RedirectResponse(
            url="/upi-payment",
            status_code=303
        )

    # -----------------------------------------------------
    # CASH ON DELIVERY
    # -----------------------------------------------------

    complete_address = (
        f"{shipping_address.strip()}, "
        f"{city.strip()} - {pincode.strip()}"
    )

    total_amount = 0

    # -----------------------------------------------------
    # CALCULATE TOTAL
    # -----------------------------------------------------

    for product_id, quantity in cart.items():

        product = (
            db.query(models.Product)
            .filter(
                models.Product.id == int(product_id),
                models.Product.is_active == True
            )
            .first()
        )

        if product:

            total_amount += (
                product.price *
                quantity
            )

    # -----------------------------------------------------
    # CHECK TOTAL
    # -----------------------------------------------------

    if total_amount <= 0:

        return RedirectResponse(
            url="/cart",
            status_code=303
        )

    # -----------------------------------------------------
    # CREATE COD ORDER
    # -----------------------------------------------------

    order = models.Order(
        customer_id=customer_id,
        total_amount=total_amount,
        status="Pending",

        payment_method="cod",
        payment_status="Pending",
        utr_number=None,

        shipping_address=complete_address,
    )

    db.add(order)

    db.flush()

    # -----------------------------------------------------
    # CREATE ORDER ITEMS
    # -----------------------------------------------------

    for product_id, quantity in cart.items():

        product = (
            db.query(models.Product)
            .filter(
                models.Product.id == int(product_id),
                models.Product.is_active == True
            )
            .first()
        )

        if not product:
            continue

        order_item = models.OrderItem(
            order_id=order.id,
            product_id=product.id,
            quantity=quantity,
            price=product.price,
        )

        db.add(order_item)

    # -----------------------------------------------------
    # SAVE ORDER
    # -----------------------------------------------------

    db.commit()

    # -----------------------------------------------------
    # EMPTY CART
    # -----------------------------------------------------

    request.session["cart"] = {}

    # -----------------------------------------------------
    # ORDER SUCCESS
    # -----------------------------------------------------

    return RedirectResponse(
        url=f"/order-success/{order.id}",
        status_code=303
    )


# ---------------------------------------------------------
# UPI PAYMENT PAGE
# ---------------------------------------------------------

@app.get("/upi-payment")
async def upi_payment_page(
    request: Request,
    db: Session = Depends(get_db),
):

    customer_id = request.session.get(
        "customer_id"
    )

    if not customer_id:
        return RedirectResponse(
            url="/login",
            status_code=303
        )

    pending_order = request.session.get(
        "pending_order"
    )

    if not pending_order:
        return RedirectResponse(
            url="/checkout",
            status_code=303
        )

    cart = request.session.get(
        "cart",
        {}
    )

    if not cart:
        return RedirectResponse(
            url="/cart",
            status_code=303
        )

    cart_items = []

    cart_total = 0

    for product_id, quantity in cart.items():

        product = (
            db.query(models.Product)
            .filter(
                models.Product.id == int(product_id),
                models.Product.is_active == True
            )
            .first()
        )

        if product:

            cart_items.append({
                "product": product,
                "quantity": quantity,
            })

            cart_total += (
                product.price *
                quantity
            )

    if not cart_items:

        request.session["cart"] = {}

        request.session.pop(
            "pending_order",
            None
        )

        return RedirectResponse(
            url="/cart",
            status_code=303
        )

    return templates.TemplateResponse(
        request=request,
        name="upi-payment.html",
        context={
            "request": request,
            "cart_items": cart_items,
            "cart_total": cart_total,
            "upi_id": "7019842253@axl",
        },
    )


# ---------------------------------------------------------
# CONFIRM UPI PAYMENT
# ---------------------------------------------------------

@app.post("/confirm-upi-payment")
async def confirm_upi_payment(
    request: Request,
    utr_number: str = Form(...),
    db: Session = Depends(get_db),
):

    utr_number = utr_number.strip()

    if not utr_number:
        return RedirectResponse(
            url="/upi-payment",
            status_code=303
        )

    customer_id = request.session.get(
        "customer_id"
    )

    if not customer_id:
        return RedirectResponse(
            url="/login",
            status_code=303
        )

    pending_order = request.session.get(
        "pending_order"
    )

    if not pending_order:
        return RedirectResponse(
            url="/checkout",
            status_code=303
        )

    cart = request.session.get(
        "cart",
        {}
    )

    if not cart:
        return RedirectResponse(
            url="/cart",
            status_code=303
        )

    # -----------------------------------------------------
    # BUILD ADDRESS
    # -----------------------------------------------------

    complete_address = (
        f"{pending_order['shipping_address']}, "
        f"{pending_order['city']} - "
        f"{pending_order['pincode']}"
    )

    # -----------------------------------------------------
    # CALCULATE TOTAL
    # -----------------------------------------------------

    total_amount = 0

    for product_id, quantity in cart.items():

        product = (
            db.query(models.Product)
            .filter(
                models.Product.id == int(product_id),
                models.Product.is_active == True
            )
            .first()
        )

        if product:

            total_amount += (
                product.price *
                quantity
            )

    if total_amount <= 0:

        return RedirectResponse(
            url="/cart",
            status_code=303
        )

    # -----------------------------------------------------
    # CREATE UPI ORDER
    # -----------------------------------------------------

    order = models.Order(
        customer_id=customer_id,
        total_amount=total_amount,
        status="Pending",

        payment_method="online",
        payment_status="Pending Verification",
        utr_number=utr_number,

        shipping_address=complete_address,
    )

    db.add(order)

    db.flush()

    # -----------------------------------------------------
    # CREATE ORDER ITEMS
    # -----------------------------------------------------

    for product_id, quantity in cart.items():

        product = (
            db.query(models.Product)
            .filter(
                models.Product.id == int(product_id),
                models.Product.is_active == True
            )
            .first()
        )

        if not product:
            continue

        order_item = models.OrderItem(
            order_id=order.id,
            product_id=product.id,
            quantity=quantity,
            price=product.price,
        )

        db.add(order_item)

    # -----------------------------------------------------
    # SAVE ORDER
    # -----------------------------------------------------

    db.commit()

    # -----------------------------------------------------
    # CLEAR CART
    # -----------------------------------------------------

    request.session["cart"] = {}

    # -----------------------------------------------------
    # REMOVE PENDING ORDER
    # -----------------------------------------------------

    request.session.pop(
        "pending_order",
        None
    )

    # -----------------------------------------------------
    # ORDER SUCCESS
    # -----------------------------------------------------

    return RedirectResponse(
        url=f"/order-success/{order.id}",
        status_code=303
    )


# ---------------------------------------------------------
# ORDER SUCCESS PAGE
# ---------------------------------------------------------

@app.get("/order-success/{order_id}")
async def order_success(
    request: Request,
    order_id: int,
    db: Session = Depends(get_db),
):

    customer_id = request.session.get(
        "customer_id"
    )

    if not customer_id:
        return RedirectResponse(
            url="/login",
            status_code=303
        )

    order = (
        db.query(models.Order)
        .filter(
            models.Order.id == order_id,
            models.Order.customer_id == customer_id
        )
        .first()
    )

    if not order:
        return RedirectResponse(
            url="/shop",
            status_code=303
        )

    return templates.TemplateResponse(
        request=request,
        name="order-success.html",
        context={
            "request": request,
            "order": order,
        },
    )


# ---------------------------------------------------------
# ADMIN LOGIN
# ---------------------------------------------------------

ADMIN_USERNAME = os.getenv(
    "ADMIN_USERNAME",
    "admin"
)

ADMIN_PASSWORD = os.getenv(
    "ADMIN_PASSWORD",
    "change-this-password"
)


@app.get("/admin/login")
async def admin_login_page(
    request: Request,
):

    # Already logged in as admin
    if request.session.get("admin_logged_in"):

        return RedirectResponse(
            url="/admin/dashboard",
            status_code=303
        )

    return templates.TemplateResponse(
        request=request,
        name="admin/login.html",
        context={
            "request": request,
        },
    )


@app.post("/admin/login")
async def admin_login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
):

    username = username.strip()

    # -----------------------------------------------------
    # CHECK ADMIN CREDENTIALS
    # -----------------------------------------------------

    if (
        username != ADMIN_USERNAME
        or password != ADMIN_PASSWORD
    ):

        return templates.TemplateResponse(
            request=request,
            name="admin/login.html",
            context={
                "request": request,
                "error": "Invalid admin username or password.",
            },
            status_code=401,
        )

    # -----------------------------------------------------
    # ADMIN LOGIN SUCCESS
    # -----------------------------------------------------

    request.session["admin_logged_in"] = True

    request.session["admin_username"] = username

    print(
        "ADMIN SESSION:",
        request.session
    )

    return RedirectResponse(
        url="/admin/dashboard",
        status_code=303
    )


# ---------------------------------------------------------
# ADMIN DASHBOARD
# ---------------------------------------------------------

@app.get("/admin/dashboard")
async def admin_dashboard(
    request: Request,
    db: Session = Depends(get_db),
):

    # -----------------------------------------------------
    # CHECK ADMIN LOGIN
    # -----------------------------------------------------

    if not request.session.get("admin_logged_in"):

        return RedirectResponse(
            url="/admin/login",
            status_code=303
        )

    # -----------------------------------------------------
    # GET ORDER INFORMATION
    # -----------------------------------------------------

    total_orders = (
        db.query(models.Order)
        .count()
    )

    total_customers = (
        db.query(models.Customer)
        .count()
    )

    pending_payments = (
        db.query(models.Order)
        .filter(
            models.Order.payment_status == "Pending Verification"
        )
        .count()
    )

    paid_orders = (
        db.query(models.Order)
        .filter(
            models.Order.payment_status == "Paid"
        )
        .count()
    )

    # -----------------------------------------------------
    # CALCULATE REVENUE
    # -----------------------------------------------------

    orders = (
        db.query(models.Order)
        .filter(
            models.Order.payment_status == "Paid"
        )
        .all()
    )

    total_revenue = sum(
        order.total_amount or 0
        for order in orders
    )

    # -----------------------------------------------------
    # RECENT ORDERS
    # -----------------------------------------------------

    recent_orders = (
        db.query(models.Order)
        .order_by(
            models.Order.id.desc()
        )
        .limit(10)
        .all()
    )

    # -----------------------------------------------------
    # DASHBOARD
    # -----------------------------------------------------

    return templates.TemplateResponse(
        request=request,
        name="admin/dashboard.html",
        context={
            "request": request,

            "total_orders": total_orders,

            "total_customers": total_customers,

            "pending_payments": pending_payments,

            "paid_orders": paid_orders,

            "total_revenue": total_revenue,

            "recent_orders": recent_orders,
        },
    )


# ---------------------------------------------------------
# ADMIN UPI PAYMENTS
# ---------------------------------------------------------
# ---------------------------------------------------------
# ADMIN PRODUCT MANAGEMENT
# ---------------------------------------------------------

@app.get("/admin/products")
async def admin_products(
    request: Request,
    db: Session = Depends(get_db),
):

    # -----------------------------------------------------
    # CHECK ADMIN LOGIN
    # -----------------------------------------------------

    if not request.session.get("admin_logged_in"):

        return RedirectResponse(
            url="/admin/login",
            status_code=303
        )

    # -----------------------------------------------------
    # GET ALL PRODUCTS
    # -----------------------------------------------------

    products = (
        db.query(models.Product)
        .order_by(
            models.Product.id.desc()
        )
        .all()
    )

    # -----------------------------------------------------
    # PRODUCT MANAGEMENT PAGE
    # -----------------------------------------------------

    return templates.TemplateResponse(
        request=request,
        name="admin/products.html",
        context={
            "request": request,
            "products": products,
        },
    )


# ---------------------------------------------------------
# ADMIN ADD PRODUCT
# ---------------------------------------------------------

@app.get("/admin/products/add")
async def admin_add_product_page(
    request: Request,
):

    if not request.session.get("admin_logged_in"):

        return RedirectResponse(
            url="/admin/login",
            status_code=303
        )

    return templates.TemplateResponse(
        request=request,
        name="admin/add_product.html",
        context={
            "request": request,
        },
    )
# ---------------------------------------------------------
# UPDATE PRODUCT
# ---------------------------------------------------------

@app.post("/admin/products/edit/{product_id}")
async def update_product(
    product_id: int,
    request: Request,
    name: str = Form(...),
    description: str = Form(""),
    price: float = Form(...),
    category: str = Form(""),
    stock: int = Form(0),
    is_active: str = Form(""),
    image: UploadFile = File(None),
    db: Session = Depends(get_db),
):
    # Check admin login
    if not request.session.get("admin_logged_in"):
        return RedirectResponse(
            url="/admin/login",
            status_code=303
        )

    # Find product
    product = (
        db.query(models.Product)
        .filter(models.Product.id == product_id)
        .first()
    )

    if not product:
        return RedirectResponse(
            url="/admin/products",
            status_code=303
        )

    # Update normal information
    product.name = name
    product.description = description
    product.price = price
    product.category = category
    product.stock = stock

    # Active / inactive
    product.is_active = bool(is_active)

    # -----------------------------------------------------
    # IMAGE
    # -----------------------------------------------------
    # Only replace image if admin selected a new image.
    # Otherwise keep the existing image.

    if image and image.filename:
        upload_dir = "app/static/images"

        os.makedirs(
            upload_dir,
            exist_ok=True
        )

        file_path = os.path.join(
            upload_dir,
            image.filename
        )

        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(
                image.file,
                buffer
            )

        product.image = image.filename

    db.commit()

    return RedirectResponse(
        url="/admin/products",
        status_code=303
    )
# ---------------------------------------------------------
# ADMIN DELETE PRODUCT
# ---------------------------------------------------------

@app.post("/admin/products/delete/{product_id}")
async def delete_product(
    request: Request,
    product_id: int,
    db: Session = Depends(get_db),
):

    # -----------------------------------------------------
    # CHECK ADMIN LOGIN
    # -----------------------------------------------------

    if not request.session.get("admin_logged_in"):

        return RedirectResponse(
            url="/admin/login",
            status_code=303
        )

    # -----------------------------------------------------
    # FIND PRODUCT
    # -----------------------------------------------------

    product = (
        db.query(models.Product)
        .filter(
            models.Product.id == product_id
        )
        .first()
    )

    # -----------------------------------------------------
    # PRODUCT NOT FOUND
    # -----------------------------------------------------

    if not product:

        return RedirectResponse(
            url="/admin/products",
            status_code=303
        )

    # -----------------------------------------------------
    # DELETE PRODUCT
    # -----------------------------------------------------

    db.delete(product)
    db.commit()

    # -----------------------------------------------------
    # BACK TO PRODUCTS
    # -----------------------------------------------------

    return RedirectResponse(
        url="/admin/products",
        status_code=303
    )
@app.get("/admin/upi-payments")
async def admin_upi_payments(
    request: Request,
    db: Session = Depends(get_db),
):

    # -----------------------------------------------------
    # CHECK ADMIN LOGIN
    # -----------------------------------------------------

    if not request.session.get("admin_logged_in"):

        return RedirectResponse(
            url="/admin/login",
            status_code=303
        )

    # -----------------------------------------------------
    # GET PENDING UPI PAYMENTS
    # -----------------------------------------------------

    pending_payments = (
        db.query(models.Order)
        .filter(
            models.Order.payment_method == "online",
            models.Order.payment_status == "Pending Verification"
        )
        .order_by(
            models.Order.id.desc()
        )
        .all()
    )

    # -----------------------------------------------------
    # PAGE
    # -----------------------------------------------------

    return templates.TemplateResponse(
        request=request,
        name="admin/upi-payments.html",
        context={
            "request": request,
            "pending_payments": pending_payments,
        },
    )


# ---------------------------------------------------------
# ADMIN PAYMENTS URL
# ---------------------------------------------------------
# FIX:
# Your browser was opening /admin/payments
# but your actual page was /admin/upi-payments.
#
# This keeps BOTH URLs working.

@app.get("/admin/payments")
async def admin_payments(
    request: Request,
):

    if not request.session.get("admin_logged_in"):

        return RedirectResponse(
            url="/admin/login",
            status_code=303
        )

    return RedirectResponse(
        url="/admin/upi-payments",
        status_code=303
    )


# ---------------------------------------------------------
# VERIFY UPI PAYMENT
# ---------------------------------------------------------

@app.post("/admin/verify-upi/{order_id}")
async def verify_upi_payment(
    request: Request,
    order_id: int,
    db: Session = Depends(get_db),
):

    # -----------------------------------------------------
    # CHECK ADMIN LOGIN
    # -----------------------------------------------------

    if not request.session.get("admin_logged_in"):

        return RedirectResponse(
            url="/admin/login",
            status_code=303
        )

    # -----------------------------------------------------
    # FIND ORDER
    # -----------------------------------------------------

    order = (
        db.query(models.Order)
        .filter(
            models.Order.id == order_id,
            models.Order.payment_method == "online",
            models.Order.payment_status == "Pending Verification"
        )
        .first()
    )

    if not order:

        return RedirectResponse(
            url="/admin/upi-payments",
            status_code=303
        )

    # -----------------------------------------------------
    # VERIFY PAYMENT
    # -----------------------------------------------------

    order.payment_status = "Paid"
    order.status = "Paid"

    db.commit()
    db.refresh(order)

    print(
        f"PAYMENT VERIFIED: "
        f"Order #{order.id}, "
        f"UTR={order.utr_number}"
    )

    # -----------------------------------------------------
    # BACK TO UPI PAYMENTS
    # -----------------------------------------------------

    return RedirectResponse(
        url="/admin/upi-payments",
        status_code=303
    )


# ---------------------------------------------------------
# REJECT UPI PAYMENT
# ---------------------------------------------------------

@app.post("/admin/reject-upi/{order_id}")
async def reject_upi_payment(
    request: Request,
    order_id: int,
    db: Session = Depends(get_db),
):

    # -----------------------------------------------------
    # CHECK ADMIN LOGIN
    # -----------------------------------------------------

    if not request.session.get("admin_logged_in"):

        return RedirectResponse(
            url="/admin/login",
            status_code=303
        )

    # -----------------------------------------------------
    # FIND ORDER
    # -----------------------------------------------------

    order = (
        db.query(models.Order)
        .filter(
            models.Order.id == order_id,
            models.Order.payment_method == "online",
            models.Order.payment_status == "Pending Verification"
        )
        .first()
    )

    # -----------------------------------------------------
    # ORDER NOT FOUND
    # -----------------------------------------------------

    if not order:

        return RedirectResponse(
            url="/admin/upi-payments",
            status_code=303
        )

    # -----------------------------------------------------
    # REJECT PAYMENT
    # -----------------------------------------------------

    order.payment_status = "Rejected"
    order.status = "Payment Rejected"

    # -----------------------------------------------------
    # SAVE DATABASE
    # -----------------------------------------------------

    db.commit()
    db.refresh(order)

    print(
        f"PAYMENT REJECTED: "
        f"Order #{order.id}, "
        f"UTR={order.utr_number}"
    )

    # -----------------------------------------------------
    # IMPORTANT FIX:
    # GO TO ALL ORDERS AFTER REJECTION
    #
    # This lets you immediately see the rejected order
    # instead of returning to the pending-payment page
    # where the order disappears because it is no longer
    # Pending Verification.
    # -----------------------------------------------------

    return RedirectResponse(
        url="/admin/orders",
        status_code=303
    )


# ---------------------------------------------------------
# ADMIN ALL ORDERS
# ---------------------------------------------------------

@app.get("/admin/orders")
async def admin_orders(
    request: Request,
    db: Session = Depends(get_db),
):

    # -----------------------------------------------------
    # CHECK ADMIN LOGIN
    # -----------------------------------------------------

    if not request.session.get("admin_logged_in"):

        return RedirectResponse(
            url="/admin/login",
            status_code=303
        )

    # -----------------------------------------------------
    # GET ALL ORDERS
    # -----------------------------------------------------

    orders = (
        db.query(models.Order)
        .order_by(
            models.Order.id.desc()
        )
        .all()
    )

    # -----------------------------------------------------
    # PAGE
    # -----------------------------------------------------

    return templates.TemplateResponse(
        request=request,
        name="admin/orders.html",
        context={
            "request": request,
            "orders": orders,
        },
    )


# ---------------------------------------------------------
# ADMIN ORDER DETAILS
# ---------------------------------------------------------

@app.get("/admin/orders/{order_id}")
async def admin_order_details(
    request: Request,
    order_id: int,
    db: Session = Depends(get_db),
):

    # -----------------------------------------------------
    # CHECK ADMIN LOGIN
    # -----------------------------------------------------

    if not request.session.get("admin_logged_in"):

        return RedirectResponse(
            url="/admin/login",
            status_code=303
        )

    # -----------------------------------------------------
    # FIND ORDER
    # -----------------------------------------------------

    order = (
        db.query(models.Order)
        .filter(
            models.Order.id == order_id
        )
        .first()
    )

    if not order:

        return RedirectResponse(
            url="/admin/orders",
            status_code=303
        )

    # -----------------------------------------------------
    # ORDER DETAILS PAGE
    # -----------------------------------------------------

    return templates.TemplateResponse(
        request=request,
        name="admin/order-details.html",
        context={
            "request": request,
            "order": order,
        },
    )


# ---------------------------------------------------------
# ADMIN UPDATE ORDER STATUS
# ---------------------------------------------------------

@app.post("/admin/orders/{order_id}/status")
async def update_order_status(
    request: Request,
    order_id: int,
    status: str = Form(...),
    db: Session = Depends(get_db),
):

    # -----------------------------------------------------
    # CHECK ADMIN LOGIN
    # -----------------------------------------------------

    if not request.session.get("admin_logged_in"):

        return RedirectResponse(
            url="/admin/login",
            status_code=303
        )

    # -----------------------------------------------------
    # FIND ORDER
    # -----------------------------------------------------

    order = (
        db.query(models.Order)
        .filter(
            models.Order.id == order_id
        )
        .first()
    )

    if not order:

        return RedirectResponse(
            url="/admin/orders",
            status_code=303
        )

    # -----------------------------------------------------
    # ALLOWED ORDER STATUSES
    # -----------------------------------------------------

    allowed_statuses = [
        "Pending",
        "Confirmed",
        "Preparing",
        "Out for Delivery",
        "Delivered",
    ]

    if status not in allowed_statuses:

        return RedirectResponse(
            url=f"/admin/orders/{order_id}",
            status_code=303
        )

    # -----------------------------------------------------
    # UPDATE STATUS
    # -----------------------------------------------------

    order.status = status

    db.commit()

    # -----------------------------------------------------
    # BACK TO ORDER DETAILS
    # -----------------------------------------------------

    return RedirectResponse(
        url=f"/admin/orders/{order_id}",
        status_code=303
    )
# ---------------------------------------------------------
# CUSTOMER MY ORDERS
# ---------------------------------------------------------

@app.get("/my-orders")
async def my_orders(
    request: Request,
    db: Session = Depends(get_db),
):

    # -----------------------------------------------------
    # CHECK LOGIN
    # -----------------------------------------------------

    customer_id = request.session.get("customer_id")

    if not customer_id:
        return RedirectResponse(
            url="/login",
            status_code=303
        )

    # -----------------------------------------------------
    # GET CUSTOMER
    # -----------------------------------------------------

    customer = (
        db.query(models.Customer)
        .filter(
            models.Customer.id == customer_id
        )
        .first()
    )

    if not customer:
        request.session.clear()

        return RedirectResponse(
            url="/login",
            status_code=303
        )

    # -----------------------------------------------------
    # GET CUSTOMER ORDERS
    # -----------------------------------------------------

    orders = (
        db.query(models.Order)
        .filter(
            models.Order.customer_id == customer_id
        )
        .order_by(
            models.Order.id.desc()
        )
        .all()
    )

    # -----------------------------------------------------
    # MY ORDERS PAGE
    # -----------------------------------------------------

    return templates.TemplateResponse(
        request=request,
        name="accounts/my-orders.html",
        context={
            "request": request,
            "customer": customer,
            "orders": orders,
        },
    )
# ---------------------------------------------------------
# CUSTOMER ORDER DETAILS
# ---------------------------------------------------------

@app.get("/my-orders/{order_id}")
async def my_order_details(
    request: Request,
    order_id: int,
    db: Session = Depends(get_db),
):

    # -----------------------------------------------------
    # CHECK LOGIN
    # -----------------------------------------------------

    customer_id = request.session.get("customer_id")

    if not customer_id:
        return RedirectResponse(
            url="/login",
            status_code=303
        )

    # -----------------------------------------------------
    # GET CUSTOMER
    # -----------------------------------------------------

    customer = (
        db.query(models.Customer)
        .filter(
            models.Customer.id == customer_id
        )
        .first()
    )

    if not customer:
        request.session.clear()

        return RedirectResponse(
            url="/login",
            status_code=303
        )

    # -----------------------------------------------------
    # FIND CUSTOMER ORDER
    # -----------------------------------------------------

    order = (
        db.query(models.Order)
        .filter(
            models.Order.id == order_id,
            models.Order.customer_id == customer_id
        )
        .first()
    )

    # -----------------------------------------------------
    # ORDER NOT FOUND
    # -----------------------------------------------------

    if not order:
        return RedirectResponse(
            url="/my-orders",
            status_code=303
        )

    # -----------------------------------------------------
    # CUSTOMER ORDER DETAILS
    # -----------------------------------------------------

    return templates.TemplateResponse(
        request=request,
        name="accounts/order-details.html",
        context={
            "request": request,
            "customer": customer,
            "order": order,
        },
    )
# =========================================================
# CUSTOMER REORDER
# =========================================================

@app.post("/reorder/{order_id}")
async def reorder_order(
    request: Request,
    order_id: int,
    db: Session = Depends(get_db),
):
    # -----------------------------------------------------
    # CHECK LOGIN
    # -----------------------------------------------------

    customer_id = request.session.get("customer_id")

    if not customer_id:
        return RedirectResponse(
            url="/login",
            status_code=303
        )

    # -----------------------------------------------------
    # FIND CUSTOMER
    # -----------------------------------------------------

    customer = (
        db.query(models.Customer)
        .filter(
            models.Customer.id == customer_id
        )
        .first()
    )

    if not customer:
        request.session.clear()

        return RedirectResponse(
            url="/login",
            status_code=303
        )

    # -----------------------------------------------------
    # FIND ORIGINAL ORDER
    # IMPORTANT:
    # Only allow the logged-in customer to reorder
    # their own order.
    # -----------------------------------------------------

    order = (
        db.query(models.Order)
        .filter(
            models.Order.id == order_id,
            models.Order.customer_id == customer_id
        )
        .first()
    )

    if not order:
        return RedirectResponse(
            url="/my-orders",
            status_code=303
        )

    # -----------------------------------------------------
    # CHECK ORDER ITEMS
    # -----------------------------------------------------

    if not order.items:
        return RedirectResponse(
            url="/my-orders",
            status_code=303
        )

    # -----------------------------------------------------
    # GET EXISTING CART FROM SESSION
    # -----------------------------------------------------

    cart = request.session.get("cart", {})

    if not isinstance(cart, dict):
        cart = {}

    # -----------------------------------------------------
    # ADD EACH PREVIOUS PRODUCT TO CART
    # -----------------------------------------------------

    for item in order.items:

        product = (
            db.query(models.Product)
            .filter(
                models.Product.id == item.product_id,
                models.Product.is_active == True
            )
            .first()
        )

        # Product may have been removed/deactivated.
        # Simply skip it instead of breaking reorder.
        if not product:
            continue

        # Check stock
        if product.stock is not None and product.stock <= 0:
            continue

        product_id = str(product.id)

        old_quantity = cart.get(product_id, 0)

        try:
            old_quantity = int(old_quantity)
        except (TypeError, ValueError):
            old_quantity = 0

        new_quantity = old_quantity + int(item.quantity or 1)

        # Do not exceed available stock
        if product.stock is not None:
            new_quantity = min(
                new_quantity,
                product.stock
            )

        cart[product_id] = new_quantity

    # -----------------------------------------------------
    # SAVE CART
    # -----------------------------------------------------

    request.session["cart"] = cart

    request.session.modified = True

    # -----------------------------------------------------
    # GO DIRECTLY TO CART
    # -----------------------------------------------------

    return RedirectResponse(
        url="/cart",
        status_code=303
    )

# ---------------------------------------------------------
# CUSTOMER DELETE ORDER
# ---------------------------------------------------------

@app.post("/my-orders/{order_id}/delete")
async def delete_my_order(
    request: Request,
    order_id: int,
    db: Session = Depends(get_db),
):

    customer_id = request.session.get("customer_id")

    if not customer_id:
        return RedirectResponse(
            url="/login",
            status_code=303
        )

    order = (
        db.query(models.Order)
        .filter(
            models.Order.id == order_id,
            models.Order.customer_id == customer_id
        )
        .first()
    )

    if not order:
        return RedirectResponse(
            url="/my-orders",
            status_code=303
        )

    db.delete(order)

    db.commit()

    return RedirectResponse(
        url="/my-orders",
        status_code=303
    )