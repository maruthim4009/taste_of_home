# taste_of_home# Taste of Home

### Homemade Spice. Authentic Taste. Made with Care.

A FastAPI-based e-commerce web application for homemade spicy foods and
masala products.

![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-Backend-009688?logo=fastapi&logoColor=white)
![SQLAlchemy](https://img.shields.io/badge/ORM-SQLAlchemy-D71F00)
![Database](https://img.shields.io/badge/Database-SQLite-003B57)

------------------------------------------------------------------------

## Overview

**Taste of Home** combines a customer-facing storefront with
administrative workflows. It is built with FastAPI, SQLAlchemy, SQLite,
and Jinja2 templates.

## Features

### Customer

-   Browse products
-   Register and sign in
-   Mobile OTP verification through the 2Factor API
-   Forgot-password OTP flow
-   Cart and checkout
-   View orders and order details

### Admin

-   Dashboard with store summaries
-   Order management
-   Payment review, including UPI-related workflows
-   Customer records

> Features and payment options depend on the current application
> configuration.

## Technology Stack

  Technology                    Purpose
  ----------------------------- -----------------------------------
  Python                        Application language
  FastAPI                       Web framework and routes
  Uvicorn                       ASGI development server
  SQLAlchemy                    ORM and database access
  SQLite                        Local database
  Jinja2                        Server-rendered HTML templates
  Starlette SessionMiddleware   Session handling
  HTTPX                         HTTP requests to OTP provider
  2Factor API                   SMS OTP delivery and verification
  HTML, CSS, JavaScript         Frontend
  python-dotenv                 Environment configuration

## Project Structure

``` text
taste-of-home/
├── app/
│   ├── main.py
│   ├── models.py
│   ├── database.py
│   ├── static/
│   │   ├── css/
│   │   ├── js/
│   │   └── images/
│   └── templates/
│       ├── accounts/
│       ├── admin/
│       ├── home.html
│       ├── shop.html
│       ├── cart.html
│       └── checkout.html
├── .env                 # Local secrets; do not commit
├── .gitignore
├── requirements.txt
└── README.md
```

*The exact files may vary as the project evolves.*

## Run Locally (Windows)

### 1. Prerequisites

Install Python 3.10+, Git, and optionally VS Code. Verify:

``` powershell
python --version
git --version
```

### 2. Open the project folder

``` powershell
cd E:\taste-of-home
```

Run commands from the folder containing `app` and `requirements.txt`.

### 3. Create and activate a virtual environment

``` powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

If PowerShell blocks activation, use Command Prompt:

``` bat
venv\Scripts\activate.bat
```

### 4. Install dependencies

``` powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

If `requirements.txt` does not exist, create it from the activated
project environment and review it:

``` powershell
pip freeze > requirements.txt
```

### 5. Configure `.env`

Create `.env` in the project root, next to the `app` folder:

``` dotenv
SESSION_SECRET_KEY=replace_with_a_long_random_secret
TWOFACTOR_API_KEY=your_2factor_api_key
```

The current application expects `TWOFACTOR_API_KEY` at startup. Use your
own credentials. Never commit `.env` or publish API keys.

### 6. Start the server

``` powershell
uvicorn app.main:app --reload
```

Open: - Storefront: http://127.0.0.1:8000 - API documentation (if
enabled): http://127.0.0.1:8000/docs

Stop the server with `Ctrl + C`.

### 7. Smoke-test the app

1.  Browse the storefront.
2.  Test registration and OTP delivery with a valid Indian mobile
    number.
3.  Sign in and inspect account/order pages.
4.  Test cart and checkout.
5.  Sign in as an authorized admin and inspect dashboard, orders, and
    payments.

OTP delivery may incur provider charges and depends on your 2Factor
account.

## Environment Variables

  -----------------------------------------------------------------------
  Variable                            Purpose
  ----------------------------------- -----------------------------------
  `SESSION_SECRET_KEY`                Secret used to sign session
                                      cookies; use a long random value

  `TWOFACTOR_API_KEY`                 2Factor API key for OTP operations;
                                      required by current startup
                                      configuration
  -----------------------------------------------------------------------

## Publish to GitHub Professionally

### 1. Add a `.gitignore`

Create `.gitignore` in the repository root:

``` gitignore
__pycache__/
*.py[cod]
.pytest_cache/
venv/
.venv/
env/
.env
.env.*
*.db
*.sqlite
*.sqlite3
.vscode/
.idea/
.DS_Store
Thumbs.db
```

Do not publish private customer/order data. If you choose to include a
demo database, verify that it contains no sensitive data first.

### 2. Initialize Git and commit

Run from `E:\taste-of-home`:

``` powershell
git init
git add .
git status
git commit -m "Initial commit: Taste of Home e-commerce app"
```

Check `git status` before committing. Ensure `.env`, virtual
environments, and private database files are not staged.

### 3. Create the GitHub repository

1.  Sign in to [GitHub](https://github.com/).
2.  Click **New repository**.
3.  Name it `taste-of-home`.
4.  Description:
    `A FastAPI e-commerce web app for homemade spicy foods and masala products.`
5.  Choose Public or Private.
6.  Since you already have a local README, do not initialize GitHub with
    a second README.
7.  Create the repository.

### 4. Push your project

Replace `YOUR-USERNAME` with your GitHub username:

``` powershell
git branch -M main
git remote add origin https://github.com/YOUR-USERNAME/taste-of-home.git
git push -u origin main
```

Refresh the GitHub repository page. GitHub displays `README.md` on the
repository homepage.

### 5. Make the repository portfolio-ready

-   Add screenshots of the storefront, cart/checkout, and admin
    dashboard.
-   Keep commit messages clear and descriptive.
-   Keep secrets, virtual environments, and private data out of Git.
-   Update the README when setup instructions or dependencies change.
-   Add a license only after deciding the terms you want to publish.

## Troubleshooting

  ----------------------------------------------------------------------------------------
  Problem                                    What to check
  ------------------------------------------ ---------------------------------------------
  `TWOFACTOR_API_KEY is missing from .env`   Confirm `.env` is in the project root and
                                             restart Uvicorn

  `uvicorn` not recognized                   Activate the virtual environment and install
                                             requirements

  Template not found                         Run from the project root and confirm the
                                             template exists under `app/templates/`

  OTP not sent                               Check API key, provider account/balance,
                                             phone number, network, and terminal logs

  Port 8000 in use                           Stop the other server or run
                                             `uvicorn app.main:app --reload --port 8001`

  `.env` was already tracked                 Run `git rm --cached .env`, commit the
                                             removal, and rotate exposed credentials
  ----------------------------------------------------------------------------------------

## Security Notes

This is a development/portfolio setup unless separately hardened for
production.

-   Never commit API keys, session secrets, passwords, or customer
    information.
-   Use a strong, unique session secret.
-   Rotate credentials if they were exposed.
-   Configure HTTPS and production settings before deployment.
-   Review authentication, authorization, payment verification, and
    database backups before accepting real orders.

## Roadmap

Possible future improvements: - Automated tests for authentication,
cart, checkout, and orders - Production deployment configuration -
Inventory and order reporting - Accessibility and mobile usability
checks - Screenshots and a demo walkthrough

## License

No license has been specified. Add a `LICENSE` file and update this
section if you decide to publish license terms.

------------------------------------------------------------------------

**Taste of Home** · Homemade taste, thoughtfully delivered.
