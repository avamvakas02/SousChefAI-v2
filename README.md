# SousChefAI v2

SousChefAI is a Django web application that helps users discover recipes from pantry ingredients, save generated recipes, manage their profile, and access subscription-based recipe generation limits.

## Features

- Landing, pricing, about, contact, and privacy pages
- User registration, login, logout, password change, account settings, and profile settings
- Optional Google and Facebook login through `django-allauth`
- Pantry management by ingredient category
- AI recipe discovery powered by Gemini
- Generated recipe images through Gemini or external image providers
- Saved recipes for authenticated users
- Monthly recipe generation quotas by plan
- Stripe checkout, customer portal, and webhook support
- Owner dashboard for managing users, subscriptions, usage, active status, and owner access
- Django admin panel

## Tech Stack

- Python
- Django 6
- SQLite for local development by default
- PostgreSQL-compatible `DATABASE_URL` support for production
- WhiteNoise for static files
- Gunicorn for deployment
- Stripe for billing
- Gemini API for AI recipe generation
- TheMealDB ingredient list API for pantry ingredient catalog data

## Project Structure

```text
core/                 Django project settings, URLs, ASGI, and WSGI
pages/                Landing, pricing, about, contact, and privacy pages
users/                Authentication, profiles, account settings, and social auth adapters
pantry/               Pantry ingredient storage and pantry views
recipe_discovery/     AI recipe generation, recipe detail pages, and saved recipes
subscriptions/        Stripe billing, plans, permissions, and recipe quotas
owner/                Owner dashboard and owner management command
templates/            Django templates
static/               CSS, JavaScript, images, and icons
media/                Uploaded/generated media files
```

## Requirements

- Python 3.12 or newer is recommended for Django 6
- `pip`
- A Gemini API key for AI recipe generation
- Stripe API keys if subscription checkout is enabled

## Local Setup

1. Clone the repository.

```powershell
git clone <repository-url>
cd SousChefAI-v2
```

2. Create and activate a virtual environment.

```powershell
python -m venv .venv
.\.venv\Scripts\activate
```

3. Install dependencies.

```powershell
pip install -r requirements.txt
```

4. Create a `.env` file in the project root.

```env
DEBUG=True
SECRET_KEY=change-this-local-secret
ALLOWED_HOSTS=localhost,127.0.0.1
CSRF_TRUSTED_ORIGINS=http://localhost:8000
GEMINI_API_KEY=your-gemini-api-key
```

5. Run database migrations.

```powershell
python manage.py migrate
```

6. Start the development server.

```powershell
python manage.py runserver
```

7. Open the app.

```text
http://127.0.0.1:8000/
```

## Environment Variables

### Core Django Settings

- `SECRET_KEY` - Django secret key
- `DEBUG` - set to `True` for local development
- `ALLOWED_HOSTS` - comma-separated host list
- `CSRF_TRUSTED_ORIGINS` - comma-separated trusted origins
- `DATABASE_URL` - optional database connection URL; defaults to local SQLite
- `DB_CONN_MAX_AGE` - optional database connection lifetime
- `DB_SSL_REQUIRE` - set to `0`, `false`, or `no` to disable PostgreSQL SSL override

### Deployment Security

- `TRUST_PROXY_TLS` - enables proxy SSL headers when set to `1`, `true`, or `yes`
- `SECURE_SSL_REDIRECT` - controls HTTPS redirects
- `SESSION_COOKIE_SECURE` - controls secure session cookies
- `CSRF_COOKIE_SECURE` - controls secure CSRF cookies
- `SECURE_HSTS_SECONDS` - HSTS duration

### OAuth Login

- `SITE_ID`
- `ACCOUNT_EMAIL_VERIFICATION`
- `ACCOUNT_DEFAULT_HTTP_PROTOCOL`
- `GOOGLE_OAUTH_CLIENT_ID_LOCAL`
- `GOOGLE_OAUTH_CLIENT_SECRET_LOCAL`
- `GOOGLE_OAUTH_CLIENT_ID_PROD`
- `GOOGLE_OAUTH_CLIENT_SECRET_PROD`
- `FACEBOOK_OAUTH_CLIENT_ID_LOCAL`
- `FACEBOOK_OAUTH_CLIENT_SECRET_LOCAL`
- `FACEBOOK_OAUTH_CLIENT_ID_PROD`
- `FACEBOOK_OAUTH_CLIENT_SECRET_PROD`

### Recipe Images and AI

- `GEMINI_API_KEY`
- `GEMINI_RECIPE_MODEL` - defaults to `gemini-2.5-flash`
- `GEMINI_IMAGE_MODEL` - defaults to `gemini-2.0-flash-preview-image-generation`
- `RECIPE_IMAGE_PROVIDER` - defaults to `gemini`
- `PEXELS_API_KEY`
- `UNSPLASH_ACCESS_KEY`

### Pantry

- `PANTRY_USE_INGREDIENT_API` - defaults to `True`
- `PANTRY_INGREDIENT_LIST_URL` - defaults to TheMealDB ingredient list endpoint
- `PANTRY_MAX_INGREDIENTS_PER_ZONE` - `0` means no cap
- `PANTRY_SHOW_INGREDIENT_IMAGES` - defaults to `True`

### Stripe

- `STRIPE_SECRET_KEY`
- `STRIPE_WEBHOOK_SECRET`
- `STRIPE_PRICE_REGULAR_MONTHLY`
- `STRIPE_PRICE_PREMIUM_MONTHLY`
- `STRIPE_PRICE_PREMIUM_YEARLY`
- `STRIPE_LINK_REGULAR_MONTHLY`
- `STRIPE_LINK_PREMIUM_MONTHLY`
- `STRIPE_LINK_PREMIUM_YEARLY`

## Useful Commands

Run migrations:

```powershell
python manage.py migrate
```

Create an admin/superuser:

```powershell
python manage.py createsuperuser
```

Grant owner access to an existing user:

```powershell
python manage.py make_owner <username>
```

Remove owner access:

```powershell
python manage.py make_owner <username> --remove
```

Collect static files for deployment:

```powershell
python manage.py collectstatic
```

Run tests:

```powershell
python manage.py test
```

## Main Routes

- `/` - landing page
- `/pricing/` - pricing page
- `/about-us/` - about page
- `/contact-us/` - contact page
- `/privacy/` - privacy policy
- `/users/login/` - login
- `/users/register/` - registration
- `/users/account/` - account settings
- `/users/profile/` - profile settings
- `/pantry/` - pantry home
- `/recipe-discovery/` - AI recipe discovery
- `/saved-recipes/` - saved recipes
- `/subscriptions/checkout/` - Stripe checkout
- `/subscriptions/portal/` - Stripe customer portal
- `/owner/` - owner dashboard
- `/admin/` - Django admin

## Recipe Quotas

Monthly recipe generation is enforced server-side before AI calls are made.

- Visitors and users without an active paid plan: 2 recipes per month
- Regular plan: 10 recipes per month
- Premium plan: unlimited recipes
- Superusers are treated as Premium users

## Deployment

The included `Procfile` runs the app with Gunicorn:

```text
web: gunicorn core.wsgi --log-file -
```

For production, set `DEBUG=False`, configure `SECRET_KEY`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, `DATABASE_URL`, security settings, Stripe keys, and Gemini credentials in the hosting provider environment.

## Demo Credentials

### Admin Credentials

- User: `SousChef_admin`
- Password: `1Sv2fm3av@`

### Owner Credentials

- User: `SousChef_owner`
- Password: `1Sv2fm3av@`
