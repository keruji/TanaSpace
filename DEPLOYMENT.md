## Automated deployment plan

### Production branch

The production branch is `main`.

Changes are developed on separate branches and submitted through pull
requests. Tests must pass before a pull request can merge.

Pull requests use squash merging so each merged pull request produces
one commit on the production branch.

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
3. Use the manual migration helper described below to preview the migration plan,
   then explicitly apply it with the same reviewed candidate digest. The helper
   acquires the deployment lock and overrides old local-image Compose settings.

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


## Running production migrations manually

Run `scripts/migrate-production.sh` on the VPS as `<server username>`. It uses the exact
published image, even if `/home/<server username>/TanaSpace/compose.production.yml` still
selects `tanaspace_prod-app` and ignores `APP_IMAGE`. No database reset is needed.

### First-time installation

Commit the script, helper tests, workflow syntax check, and this documentation on
your working branch and merge their PR through the usual repository checks.
The migration helper does not need to be part of a successful production deploy
before you can use it. On your **local development machine**, copy only the script:

```bash
scp scripts/migrate-production.sh '<server username>@<server address>:~/migrate-production.sh'
```

Replace `<server username>` and `<server address>` with your SSH username and
server hostname/IP before running the command. Add `-P PORT`
if your SSH server uses a custom port. Running it with `bash` needs no chmod.
Copy the script again whenever this helper changes; its location is independent
of the production checkout. Do not replace the production Compose file merely to
install this helper.

### Each release with pending migrations

1. On GitHub Actions, copy the **Exact image** reference from the image-publication
   summary for the release you intend to deploy. Use the full `@sha256:` digest,
   not a branch/tag or the image currently running on the server.
2. SSH into the VPS as `<server username>` and set that reference:

   ```bash
   candidate_image='ghcr.io/keruji/tanaspace@sha256:PASTE_THE_FULL_DIGEST'
   ```

3. Preview the pending migrations:

   ```bash
   bash ~/migrate-production.sh "$candidate_image"
   ```

   Preview pulls the image and reads production migration state; it does not
   apply migrations. Review schema/data changes and their compatibility with
   the running app and rollback image before proceeding.
4. Apply that reviewed candidate's migrations explicitly:

   ```bash
   bash ~/migrate-production.sh "$candidate_image" --apply
   ```

   Wait for `Migrations completed and verified.` If any step fails, keep its output
   and resolve the error before retrying deployment. Do not use `--fake` or delete
   migration records to bypass failures.
5. Rerun the failed production deployment workflow in GitHub Actions.

The helper holds `/home/<server username>/.local/state/tanaspace/deployment.lock` for both
preview and apply, waiting up to 60 seconds. It creates a private temporary image
override, verifies Compose's effective image, runs one-off containers on the
production Compose network, and removes temporary files on exit. It neither
replaces the running application nor edits the Compose/env files or release records.
The automatic preflight and production startup migration guards remain enabled.

The example installation uses `/home/<server username>/TanaSpace`, its
`.env.production`, and the existing release state directory. Match the helper
defaults to your installation; `DEPLOY_PATH` and `PRODUCTION_ENV_FILE` support
alternate checkouts. `DEPLOY_STATE_DIR` is available for isolated tests; on production it must
match the directory used by `deploy-release.sh`, or the operations will not share
one lock. Preview/apply both require Docker,
Docker Compose, Python 3, `flock`, and registry pull access already configured for
`<server username>`.
