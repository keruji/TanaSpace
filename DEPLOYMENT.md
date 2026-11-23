## Automated deployment plan

### Production branch

The production branch is `main`.

Changes are developed on separate branches and submitted through pull
requests. Tests must pass before a pull request can merge.

Pull requests use squash merging so each merged pull request produces
one commit on the production branch.

### Deployment platform

Production runs on one server using Docker Compose.

The production configuration is `compose.production.yml`.

GitHub Actions will connect to the server through SSH.

Server address: 66.181.46.66
SSH username: keruji
Deployment directory: /opt/tanaspace
Public website URL: https://tanaspace.dpdns.org/

### Application images

GitHub Actions will build application images and publish them to
GitHub Container Registry.

Each image will be tagged with its Git commit SHA. Deployments will
record the image digest so the exact release can be restored.

Previous successful images will be retained for rollback.

### Testing

Pull requests and pushes to the production branch will run:

- Django system checks.
- Checks for missing migrations.
- Python tests against a temporary PostgreSQL database.
- The frontend asset build.

Tests will never connect to the production database.

### Deployment verification

A deployment is successful only when:

- The application starts successfully.
- Django can access the database.
- The public HTTPS endpoint responds successfully.
- Required frontend assets are available.

### Failure and recovery

If pull request tests fail, the pull request remains open and cannot merge.

If tests fail after merging, production remains unchanged. Automation
will revert the failed change on the production branch and open a new
draft pull request reapplying those changes.

If a new application release fails deployment verification, automation
will first restore and verify the last successful production release.
It will then revert the failed change and open a replacement draft
pull request.

Infrastructure failures will be reported separately and will not
automatically cause a code revert.

The original pull request will receive a comment linking to the failed
workflow and the replacement pull request.

### Database recovery

Production currently contains temporary demo data.

Database backups are outside the scope of this initial deployment setup.

Migrations should remain compatible with the previous application
release where possible.

Automatic deletion of demo data during recovery is not enabled yet.
A database reset policy must be decided before enabling automatic
rollback involving incompatible migrations.

### Deployment ordering

Only one deployment or recovery operation may modify production at a time.

Recovery must not overwrite newer changes on the production branch.

If recovery encounters conflicting or newer changes, it must stop
repository changes and report the problem.

Recovery must not create repeated revert commits or duplicate
replacement pull requests.

## Additive schema rollout for the workspace release

The workspace release adds `accounts.0003_user_nickname` and
`items.0007_item_is_favorite`. Both keep database defaults so the preceding
application image can still insert users and items. This is covered by tests
using the preceding historical models. Existing names, items, ownership, and
quotas are retained; no database reset or data backfill is required.

Production startup and release preflight deliberately reject pending migrations.
Publishing the new image does **not** apply these migrations. Before allowing
this release to deploy, separately review and approve the schema step:

1. Build/publish the reviewed candidate image and record its immutable digest.
2. Coordinate with deployment/recovery so neither is running, and acquire the
   same deployment lock for the schema operation.
3. From the production checkout, run the following with the approved candidate
   image. These commands are a manual operation, not part of startup or CI:

   ```bash
   # Use the same session for the lock and migration command.
   exec 9>"$HOME/.local/state/tanaspace/deployment.lock"
   flock -x 9
   # Set candidate_image to the reviewed ghcr.io/...@sha256:... reference.
   APP_IMAGE="$candidate_image" docker compose \
     --project-name tanaspace_prod --env-file .env.production \
     -f compose.production.yml run --rm --no-deps app \
     python manage.py migrate --noinput
   flock -u 9
   ```

4. Allow the ordinary release preflight, application deployment, and public
   health verification to run. Keep the preflight guard enabled.
5. If the application rolls back, leave these additive columns and defaults in
   place. Do not automatically reverse migrations. Schema rollback needs its
   own review.

No production migration, deployment, or schema rollback is performed by the
browser tests or normal image publication.


## Custom property schema release

This release adds `ItemTypeProperty`, `Item.property_values`, a Tana Type schema
version, and the development-demo marker/access table. Existing items receive an
empty JSON object, existing types receive version zero, and existing users remain
non-development accounts. New fields have database defaults for old-release inserts;
there is no category/data backfill. Keep `DEV_DEMO_ENABLED=false` in production.

Use the separately reviewed schema process above for these additive migrations
before deploying this image. Neither startup nor the deployment workflow applies
them automatically. Do not automatically reverse migrations during rollback.

Old application images do not enforce custom-property validation or confirmed type
changes. Before opening custom-property writes to production, designate a rollback
target containing this feature, or suspend item/type writes while an older image is
running. Database defaults preserve old inserts but cannot supply the new validation
behavior. Local migration execution does not authorize production migration/deploy.
