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

Each Django app (`accounts`, `dashboard`, `items`) owns one part of the
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
| `config/urls.py` | Top-level routes: `/`, `/accounts/`, `/tana`, `/tana/items/`, and `/admin/`. |
| `accounts/` | Custom `User` model, signup form and view, login/logout routes, admin registration, tests. Login/logout use Django's built-in views. |
| `dashboard/` | The `/tana` page. Its view fetches the signed-in user's three latest items. |
| `items/` | Item model, form, add/list/edit views, routes, admin, migrations, and tests. |
| `templates/base.html` | Shared HTML shell for app and account pages. |
| `templates/app/base.html` | App header, sidebar, logout form, and `app_main` block. |
| `templates/dashboard/`, `templates/items/`, `templates/registration/` | Page HTML. |
| `templates/includes/` | Reused logo and form-field markup. |
| `templates/landing.html` | Public landing page at `/`. |
| `static/css/app.css` | Styles for account, dashboard, and item pages. |
| `static/images/` | Logo and avatar assets; add future static images here. |
| `src/style.css`, `src/main.js` | Landing page styles and its section-scrolling JavaScript. Vite builds these into `dist/app.css` and `dist/app.js`. |
| `docker-compose.yml`, `Dockerfile` | Local containers and image build. |
| `tests.py` in each app | Checks for that app's behavior. |

The landing page uses Tailwind classes in `templates/landing.html`, with extra
rules in `src/style.css`. The signed-in pages use `static/css/app.css`.
Changing one stylesheet will not normally change the other part of the site.
Django serves both the landing page and the app; Vite only **builds assets** for
the landing page. Edit source files, not generated `dist/` files.

## Run it locally

From the repository root, in the VS Code terminal:

```bash
docker compose up --build -d
```

Open <http://localhost:5173>. Create an account at `/accounts/signup/`, then
open `/tana` for the dashboard or `/tana/items/` for My Tana. The port is
5173 because Compose maps it to Django's port 8000 inside the container.

While Compose is running, Django reloads Python and template changes, and Vite
rebuilds landing-page assets. Refresh the browser after editing. The app CSS
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

`createsuperuser` enables a login for `/admin/`. `docker compose down`
stops the app but keeps the database volume. Avoid `docker compose down -v`
unless you intend to delete local data.

## Follow one feature through the code

Adding an item is a useful example of the full path:

1. `config/urls.py` includes `items.urls` under `/tana/items/`.
2. `items/urls.py` maps that path to `items.views.index`.
3. On GET, `index` builds an empty `ItemForm` and queries items belonging to
   `request.user`; it renders `templates/items/index.html`.
4. The template extends `templates/app/base.html`, shows the list, and renders
   the form. Its POST form includes `{% csrf_token %}`.
5. On POST, the view validates `ItemForm`, assigns `owner = request.user`,
   saves the item, and redirects back to the list.
6. `items/models.py` defines the `Item` table. The dashboard view reads the
   same table to display recent items.

Editing goes through `items.views.edit` and
`templates/items/edit.html`. The view looks up an item by both its ID **and**
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
4. Show it in `templates/items/index.html`, `templates/items/edit.html`, or
   `templates/dashboard/index.html` as needed. The shared form include
   renders fields from `ItemForm` automatically.
5. Add or adjust styles in `static/css/app.css` if needed.
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
configured for the landing template in `src/style.css`. The landing page's
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
