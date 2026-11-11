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