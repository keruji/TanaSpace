# Developing TanaSpace

This guide is for working on the project yourself, one feature at a time. The
public [README](README.md) describes the product; this file explains the code.

## The mental model

TanaSpace is a Django application that renders HTML on the server. It currently
has no separate frontend application or JSON API. A browser request follows
this path:

```text
Browser → config/urls.py → app/urls.py → view → model/database
                                      ↘ form (for input)
                                      ↘ template → HTML response
```

Each Django app (`accounts`, `dashboard`, `items`, `item_types`) owns one part of the
product. These files are the main building blocks:

| File | What it does |
| --- | --- |
| `models.py` | Defines stored data and relationships. |
| `urls.py` | Names URLs and connects them to views. |
| `views.py` | Handles requests, reads or saves data, and returns a page or redirect. |
| `forms.py` | Defines which inputs users can submit and validates them. |
| `templates/` | Renders HTML using data from the view. |
| `migrations/` | Records database schema changes. |
| `admin.py` | Configures models in Django's built-in admin at `/admin/`. |
| `tests.py` | Checks expected behavior and important access rules. |

`config/settings.py` registers the apps and holds shared Django settings.
`requirements.txt` lists Python packages; `package.json` lists frontend
packages. For private data, views must require login and restrict database
queries to the signed-in user; creating a model does not add those rules.

## Where things live

| Path | Purpose |
| --- | --- |
| `config/settings.py` | Installed apps, database, authentication, templates, static files, and environment settings. |
| `config/urls.py` | Top-level routes: `/`, `/accounts/`, `/tana`, `/tana/items/`, `/tana/item_types/`, and `/admin/`. |
| `accounts/` | Custom `User` model, session-scoped demo entry and logout, temporarily disabled public login/signup routes, admin registration, tests. |
| `common/models.py` | Abstract `OwnershipModel` with shared name, owner, creation time, and edit history fields for future user-owned models. |
| `dashboard/` | The `/tana` page. Its view fetches the signed-in user's three latest items. |
| `items/` | Required type relation, item forms, list, floating create/view/edit/delete pages, routes, admin, migrations, and tests. |
| `item_types/` | Type model, form, ordered list, floating create/view/edit/delete pages, routes, migrations, and tests. |
| `templates/base.html` | Shared HTML shell for app and account pages. |
| `templates/app/base.html` | App header, sidebar, logout form, and `app_main` block. |
| `templates/dashboard/`, `templates/items/`, `templates/registration/` | Page HTML. |
| `templates/includes/` | Reused logo and form-field markup. |
| `templates/landing.html` | Public landing page at `/`. |
| `src/css/global.css` | Shared page shell, form, and modal styles. |
| `src/css/auth.css`, `dashboard.css`, `items.css`, `item_types.css` | Styles owned by their page or module; Vite compiles them together. |
| `static/images/` | Logo and the local Lucide icon sprite; add future static images here. |
| `src/style.css`, `src/main.js` | Shared Tailwind entry plus landing styles and JavaScript. Vite builds these into `dist/app.css` and `dist/app.js`. |
| `docker-compose.yml`, `Dockerfile` | Local containers and image build. |
| `tests.py` in each app | Checks for that app's behavior. |

All templates can use Tailwind utilities. The frontend watcher compiles
`src/style.css` into `dist/app.css`; `@source "../templates"` scans the Django
templates. `templates/base.html` and the landing page load that output.
Landing-specific rules stay in `src/style.css`; shared rules stay in
`src/css/global.css`, and each module has its own source stylesheet. All of
these files run through Vite, so they can use Tailwind directives such as
`@apply`. The browser receives one compiled `dist/app.css` file.
UI icons use `templates/includes/icon.html` and `static/images/lucide.svg`;
`src/css/icons.css` sets their shared size and stroke style. The TanaSpace
logo remains its own asset.
Django serves the pages; Vite **builds Tailwind assets** for every page. Edit
source files, not generated `dist/` files. Item and type lists show 40 records per page. An item needs a type; no fallback type is created.

Each account can create up to 20 types and 100 items. Names are limited to 160
characters, descriptions to 500, and item notes to 2,000. The create views
check quotas inside a transaction while locking the account row, so concurrent
requests cannot normally pass the same quota check on PostgreSQL. Editing a
record does not consume another slot; deleting one frees a slot.

## Run it locally

From the repository root, in the VS Code terminal:

Copy `.env.example` to `.env` and set a long random `POSTGRES_PASSWORD`, then run:

```bash
docker compose up --build -d
```

Open <http://localhost:5173> and click **Demo**. This creates a temporary demo
user named `demo` plus nine digits and opens `/tana`. Its session expires after
one hour. Logging out removes the demo user and its data immediately; a small
cleanup loop deletes expired demo accounts every five minutes. At most 25 demo
accounts can be active at once by default. Public login and signup
are temporarily disabled. The port is 5173 because Compose maps it to Django's
port 8000 inside the container.

While Compose is running, Django reloads Python and template changes, and Vite
rebuilds Tailwind assets. Refresh the browser after editing. The app CSS
link includes a version based on the file's modification time to refresh
cached styles. If you change `docker-compose.yml`, `requirements.txt`, or the
`Dockerfile`, recreate the containers with `docker compose up --build -d`.
If you change a model, run the migration commands below.

Useful commands:

```bash
docker compose logs -f app frontend
docker compose exec app python manage.py check
docker compose exec app python manage.py test
docker compose exec app python manage.py createsuperuser
docker compose down
```

`createsuperuser` enables a login for `/admin/`. PostgreSQL stores data in the
`postgres_data` volume; `docker compose down` keeps it. Avoid `docker compose down -v`
unless you intend to delete local data.

## Follow one feature through the code

Adding an item is a useful example of the full path:

1. `config/urls.py` includes `items.urls` under `/tana/items/`.
2. `items/urls.py` maps the list and floating create/view/edit/delete paths.
3. The view limits queries to `request.user` and renders `templates/items/index.html`.
4. The create window shows an error until the user creates a Tana Type. Its
   POST form includes `{% csrf_token %}`.
5. On POST, the view validates `ItemForm`, assigns `owner = request.user`,
   saves the item, and redirects to its read-only view.
6. `items/models.py` defines the `Item` table by inheriting the shared
   `OwnershipModel` fields from `common/models.py`. The dashboard view reads the
   same table to display recent items.

Editing goes through `items.views.edit` and the floating form in
`templates/items/index.html`. The view looks up an item by both its ID **and**
`owner=request.user`, then records `edited_at` and `edited_by` on a
successful save. Audit fields are not part of `ItemForm`, so visitors cannot
submit them. The view also requires login. Keep these rules whenever you add a
new user-owned page.

## How to make a change

Start by writing one sentence describing the behavior: for example, “An owner
can record a category for each item and see it in My Tana.” Then trace the
feature from stored data to browser output.

**For a new item field:**

1. Add the field to `Item` in `items/models.py`. Decide if it is required,
   optional, or needs a default for existing rows.
2. Create and apply a migration:

   ```bash
   docker compose exec app python manage.py makemigrations items
   docker compose exec app python manage.py migrate
   ```

3. Add the field to the explicit `ItemForm.Meta.fields` list in
   `items/forms.py` if users should edit it. Do not put owner or audit fields
   in that list.
4. Show it in `templates/items/index.html` or
   `templates/dashboard/index.html` as needed. The shared form include
   renders fields from `ItemForm` automatically.
5. Add shared styles in `src/css/global.css`, or module styles in the
   matching stylesheet under `src/css/`. Use Tailwind utilities directly in
   templates for small layout and spacing changes.
6. Update `items/tests.py` to check saving, display, and owner privacy.
7. Run tests and commit the new file in `items/migrations/` with the code.

**For a new page or feature:** choose the owning app first. Put its URL pattern
in that app's `urls.py`, request and database logic in `views.py`, input
validation in `forms.py`, and HTML in a template for that app. Include new
app routes in `config/urls.py` when needed. Add navigation in
`templates/app/base.html` and a named `{% url 'app_name:route_name' %}` link
instead of hardcoding a path. Add styles to the correct stylesheet and test the
new flow. Only create another Django app when the feature has a distinct
responsibility; a new screen alone does not require one.

**For landing-page changes:** edit `templates/landing.html`, `src/style.css`,
or `src/main.js`. Vite watches these files in Compose. Its Tailwind source is
configured for all templates in `src/style.css`. The shared
`app.css` and `app.js` are generated files in `dist/`; do not edit them.

## A repeatable workflow

1. Read the relevant URL, view, form, model, template, and test. Follow the
   current request path before editing.
2. Make a small vertical change: data/validation → view → template/style →
   test. Keep HTML indented across lines as the existing templates do.
3. If a model changed, create and apply a migration. Review the generated
   migration before committing it.
4. Check behavior in the browser, including an empty state, an invalid form,
   and a second account if the feature stores private data.
5. Run checks:

   ```bash
   docker compose exec app python manage.py check
   docker compose exec app python manage.py test
   docker compose exec app python manage.py makemigrations --check --dry-run
   git status --short
   git diff --check
   git diff
   ```

   For landing-page asset changes, also run
   `docker compose exec frontend npm run build`. New files do not appear in
   `git diff` until they are staged; inspect them directly, then review
   `git diff --cached` after `git add`.
6. Commit one coherent change. The repository's commit format is
   `type: short description`, such as `feat: add item categories`,
   `fix: keep item rows full width`, or `docs: explain local setup`.

For a first independent exercise, add one optional field to `Item` using the
steps above. It will take you through the database, form, server view,
template, CSS, and test without introducing another app.
