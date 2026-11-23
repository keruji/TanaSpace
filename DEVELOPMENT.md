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
| `accounts/` | Custom `User`, Profile editing, Settings overview, demo entry/logout, and unchanged disabled public login/signup routes. |
| `common/models.py` | Abstract `OwnershipModel` with shared name, owner, creation time, and edit history fields for future user-owned models. |
| `dashboard/` | The `/tana` page. Its view fetches the signed-in user's three latest items and owner-scoped totals. |
| `items/` | Owner-scoped items, search/type filters, Favorites, HTML window fragments, quota enforcement, and tests. |
| `item_types/` | Type model, form, ordered list, floating create/view/edit/delete pages, routes, migrations, and tests. |
| `templates/base.html` | Shared HTML shell for app and account pages. |
| `templates/app/base.html` | Persistent header, collapsible sidebar, account menu with POST logout, and workspace content mount. |
| `templates/dashboard/`, `templates/items/`, `templates/registration/` | Page HTML. |
| `templates/includes/` | Reused logo and form-field markup. |
| `templates/landing.html` | Public landing page at `/`. |
| `src/css/global.css` | Shared typography, buttons, and form controls. |
| `src/css/workspace.css` | Workspace shell, record windows, and custom selection controls. |
| `src/css/auth.css`, `dashboard.css`, `items.css`, `landing.css` | Styles owned by their page or module; Vite compiles them together. |
| `static/images/` | Logo and the local Lucide icon sprite; add future static images here. |
| `src/style.css`, `src/main.js` | Shared frontend stylesheet and JavaScript entry points. Vite builds these into `dist/app.css` and `dist/app.js`. |
| `docker-compose.yml`, `Dockerfile` | Local containers and image build. |
| `tests.py` in each app | Checks for that app's behavior. |

All templates can use Tailwind utilities. The frontend watcher compiles
`src/style.css` into `dist/app.css`; `@source "../templates"` scans the Django
templates. `templates/base.html` and the landing page load that output.
Landing-specific rules live in `src/css/landing.css`. Shared rules live in
`src/css/global.css`, and each module has its own source stylesheet. All of
these files run through Vite, so they can use Tailwind directives such as
`@apply`. The browser receives one compiled `dist/app.css` file.
UI icons use `templates/includes/icon.html` and `static/images/lucide.svg`;
`src/css/icons.css` sets their shared size and stroke style. The TanaSpace
logo remains its own asset. The refined Soft Shelf SVGs live in
`static/images/logo-{24,32,48,64,128}.svg`; `static/images/logo.svg` is the
256 px master. The shared logo include uses the 32 px drawing by default;
the landing footer uses 24 px and the README uses 128 px.
`public/favicon.svg` uses the 24 px drawing. These transparent SVGs adapt to
light and dark color schemes, including the app's selected theme through
the root `color-scheme` setting. The 24 and 32 px drawings have geometry
adjusted for those sizes; larger drawings use the refined master.
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

Open <http://localhost:5173> and click **Demo**. By default, this creates a temporary demo
user named `demo` plus nine digits and opens `/tana`. Its session expires after
one hour. Logging out removes the demo user and its data immediately; a small
cleanup loop deletes expired demo accounts every five minutes. At most 25 demo
accounts can be active at once by default. To keep local test data across logout,
opt into **Persistent development demos** below. Public login and signup
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


## Dynamic workspace

The header and sidebar remain mounted during authenticated navigation. HTMX
2.0.11 is pinned in npm and bundled locally by Vite; no CDN or separate API is
needed. `common/workspace.py` renders the same Django context as a full document,
a workspace fragment, main-content-only fragment, or window fragment depending
on `HX-Request` and `HX-Target`. Authentication and ownership checks run for every
request. History-restore requests without `HX-Request` receive a full document.

- `src/workspace.js` owns HTMX requests, URL history, titles, independent content
  scroll restoration, dirty-form confirmation, asynchronous forms, and windows.
- `src/workspace-shell.js` owns the persistent sidebar, mobile drawer, and account
  menu. Desktop navigation preference is stored under `tanaspace-sidebar`;
  mobile drawer state is temporary. Theme storage remains independent.
- `templates/app/workspace_page.html` wraps the shared content templates for
  direct visits. `content.html` and `window.html` in each record app contain the
  reusable HTML. Normal links and CSRF-protected POST forms remain usable when
  JavaScript is disabled.
- The history controller stores only URLs, entry indexes, and scroll positions
  in browser history. It uses the History API around HTMX so dirty forms can
  reject Back/Forward before replacement; it does not cache private page HTML
  in browser storage. Window Close returns to the previous in-app window or page. Successful
  deletion returns directly to the originating collection so it cannot reopen
  a deleted record. Direct window visits close through a safe collection URL.
- Mutation responses return `X-Workspace-Changed`, optionally
  `X-Workspace-URL` or `X-Workspace-Close`. These tell the controller to update
  the detail URL, refresh the underlying region, or close a deleted record.
  Validation returns the bound form with HTTP 200 and no mutation header.
- Return URLs are allowlisted to non-modal workspace routes. Failure responses
  never replace a form with a server error document. Writes are not retried
  automatically; if a connection fails, check records before submitting again.

Profile lives at `/tana/profile/`, Settings at `/tana/settings/`, and Favorites at
`/tana/favorites/`. Tana Types keeps every existing `/tana/item_types/` URL but is
accessed from Settings. Profile edits nickname and existing first/last name
fields; username is read-only. Display names prefer nickname, then available
name components, then username.

Search uses `q`, `type`, and `page` query parameters on My Tana and Favorites.
Results are owner-scoped, paginated at 40, and keep their filters when a window
closes. Item and type limits remain 100 and 20. Favorites use an explicit-state
POST rather than a blind toggle and do not change content edit metadata.

The nickname and favorite fields have additive migrations with database defaults
for previous-release insert compatibility. Local development runs migrations
through its normal startup script. Production needs the separate schema step
in [DEPLOYMENT.md](DEPLOYMENT.md); the deployment preflight remains in place.

## Browser regression tests

Install the browser runtime once after `npm ci`:

```bash
npx playwright install --with-deps chromium
npm run build
npm run test:browser
```

Run these commands in an environment with the Python requirements installed.
Playwright starts `tests/browser_server.py` twice, using separate temporary SQLite
databases on ports 5174 (public demo) and 5175 (development demo). It never migrates or
changes your development database. Django's existing CI suite continues to run
against PostgreSQL, including the concurrent quota test. Browser coverage runs
in the same required CI check before image publication.

For already running **disposable test servers**, set `BROWSER_BASE_URL` and
`BROWSER_DEV_BASE_URL` to their respective URLs. Browser tests create temporary demo accounts and delete their own sessions
on completion. Do not point them at production or a shared dataset.


### Selection controls and action icons

`src/select.js` progressively enhances single selects using vanilla JavaScript
and the browser's Popover API. Django's native select remains the submitted
value and validation source, and stays visible when JavaScript or popovers are
unavailable. Enhanced controls support Arrow/Home/End keys, type-ahead,
Enter/Space selection, and Escape without closing the surrounding window.
Menus use the shared light/dark tokens and stay within the viewport.

Record action icons use the existing local Lucide sprite. The shared window
close control is icon-only and keeps its accessible name. The avatar menu only
moves focus into its options for keyboard opening; pointer opening keeps focus
on the avatar, and closed options are inert.

Workspace content is temporarily inert during navigation and submission. The
route state is committed before new content becomes interactive, preventing
rapid clicks from opening records against a stale page or window origin.


Window Back/Cancel links use `data-window-back`, not `data-window`. They reverse
an existing transition instead of pushing another detail window into history.
When a delete URL was opened directly, its Back/Cancel link replaces that entry
with the detail URL; Close can then safely return to the collection.


## Custom Tana Type properties

Settings → Manage Tana Types → Edit type includes **Custom Properties**. Save a
new type first, then add properties. Text, Number, Date, Boolean, and single-choice
Dropdown fields are supported. Required fields show an asterisk; optional checkboxes
save an unchecked value as No. Required Boolean properties require an explicit
Yes/No answer. Numbers allow eight integer digits and four decimal places; they
are JSON numbers and are not an exact financial calculation system.

Definitions use stable UUIDs; renaming fields or dropdown options preserves values.
Move up/down controls change display order. Archive removes fields/options from
new entry without erasing saved values. Item details show archived property values
in a separate section. Archived dropdown selections may remain unchanged on their
existing item. A property's data type cannot change while it has saved values;
numeric bounds cannot be tightened past existing values. Adding a required field
leaves existing records intact and requires completion on their next save.

Each type supports 20 active / 50 total properties, and each dropdown supports 50
options including archived options. Existing 100-item and 20-type quotas remain.
Changing an item's type never matches fields by name: confirm clearing all previous
custom values, including archived ones, and complete the destination fields. Data
is cleared only on a fully valid save. Without JavaScript, select the type and click
**Load properties**, then fill its fields and Save.

`item_types/properties.py` centralizes definition-aware fields and serialization.
`item_types/property_views.py` handles owner-scoped, transactional management.
`items/forms.py` builds dynamic fields; it never accepts a raw JSON mapping from
clients. The POST-only custom-fields endpoint renders HTML without saving. Form
schema versions reject stale writes. The frontend replaces only that field region,
keeps core drafts, ignores old responses, and blocks Save until loading succeeds.

## Persistent development demos

This feature is opt-in. In your local `.env`, set:

```dotenv
DJANGO_DEBUG=true
DEV_DEMO_ENABLED=true
```

Then recreate the application container to load its environment:

```bash
docker compose up -d app
```

The existing **Demo** button creates a development account on first use. Logout
ends authentication and returns to the landing page without deleting its data.
Click Demo again in the same browser to resume it. The private 30-day HttpOnly,
SameSite=Strict cookie is scoped to `/accounts/demo/`; only a token hash is stored
in the database. No account credentials are stored in localStorage or URLs.

**Reset Demo · Development**, above Log out, opens a confirmation window. Its
CSRF-protected POST clears the current demo's items, types, and property definitions
in place, preserves profile/identity, rotates the resume credential, and leaves the
account signed in. No templates or initial categories are generated.

Losing, clearing, or expiring the cookie creates a new development demo on the next
Demo click; the old account stays stored. To remove an abandoned account locally,
use `python manage.py shell` inside the app container, select the precise
`is_demo=True, is_development_demo=True` user, delete its owned Items first, then
its user record. Do not use this procedure against production.

Development accounts are excluded from public expiry cleanup and public capacity.
Public demos retain their one-hour expiry and deletion on logout. Existing temporary
demos are not converted. Turning the flag off does not delete development data.
Both DEBUG and the explicit flag are required; production configuration rejects the
flag. Do not enable it on shared or publicly reachable environments.

Browser tests now use two disposable databases: normal workspace scenarios on
5174 and development-demo scenarios on 5175. `npm run test:browser` starts both;
neither uses the local development database. With externally managed test servers,
set `BROWSER_BASE_URL` and `BROWSER_DEV_BASE_URL`. `BROWSER_TEST_PORT` chooses the
helper's port; `BROWSER_TEST_DEV_DEMO=true` explicitly enables its development mode.
