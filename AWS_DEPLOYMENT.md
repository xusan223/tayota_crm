# AWS deployment (Elastic Beanstalk + RDS PostgreSQL)

The app remains on SQLite for local development. AWS uses RDS PostgreSQL because
an instance-local SQLite file is not durable across Elastic Beanstalk deployments
or instance replacement.

## 1. Create AWS resources

1. In AWS Certificate Manager, request/validate a certificate for the domain you
   will use. In the same AWS region, create an Elastic Beanstalk web environment
   on **Python 3.12 running on 64bit Amazon Linux 2023** with a load balancer and
   an HTTPS (443) listener using that certificate. Keep the HTTP listener
   redirecting to HTTPS.
2. Create an RDS PostgreSQL database in the same VPC as Elastic Beanstalk. Keep
   it private (not publicly accessible). Allow inbound TCP 5432 from the
   Elastic Beanstalk instance security group only.
3. Use a separate production database/user and a newly generated Django secret.
   Do not reuse the sample account passwords or commit secrets to files.

## 2. Configure and deploy

Install AWS CLI and the Elastic Beanstalk CLI, configure AWS credentials, then
from this project directory run:

```powershell
eb init
```

Choose the AWS region and Python 3.12 platform, then create the environment from
the AWS console or with the EB CLI. In the environment's **Configuration →
Updates, monitoring, and logging → Software → Environment properties**, set:

- `DJANGO_SECRET_KEY`: a new value generated with
  `python -c "import secrets; print(secrets.token_urlsafe(50))"`
- `DATABASE_URL`: `postgresql://USER:PASSWORD@RDS-ENDPOINT:5432/DB_NAME`
  (URL-encode special characters in the username/password)
- `DJANGO_ALLOWED_HOSTS`: `.elasticbeanstalk.com,crm.example.com` (replace the
  example with your actual domain)
- `DJANGO_CSRF_TRUSTED_ORIGINS`:
  `https://*.elasticbeanstalk.com,https://crm.example.com`

Keep `DJANGO_DEBUG=False` and `DJANGO_SECURE_SSL_REDIRECT=True`. Configure DNS
for the custom domain to point to the Elastic Beanstalk load balancer. The
included EB config collects static files, runs database migrations once per
deployment, and checks `/health/`.

Create a deployment bundle without the local SQLite database or virtualenv:

```powershell
eb deploy
```

If using the EB CLI for the first time, create/select an environment with
`eb create` before running `eb deploy`. AWS resources (load balancer, EC2, and
RDS) can incur charges; review the selected instance/database sizes and AWS
budget alerts.

## 3. Initialize production data and administrator

The existing local `db.sqlite3` is not automatically copied to RDS. After
deployment, connect to the EB instance with `eb ssh`, activate the Python
environment under `/var/app/venv/`, then run:

```bash
cd /var/app/current
source /var/app/venv/staging-*/bin/activate
python manage.py seed_demo_data
python manage.py createsuperuser
```

The seed command creates at least 100 sample customers and deals without
duplicating existing phone numbers. Use the new superuser to sign in at
`/admin/`, create the director and staff accounts, and assign each CRM role.
Set new, unique production passwords; the local demo credentials are not for
production.

To transfer existing SQLite records instead, make a protected fixture locally:

```powershell
python manage.py dumpdata auth.user crm.staffprofile crm.car crm.customer crm.deal --natural-foreign --natural-primary --indent 2 -o aws_initial_data.json
```

Transfer that file securely to the instance, load it with
`python manage.py loaddata aws_initial_data.json`, then remove the fixture from
the instance. Treat it as sensitive because it contains user password hashes,
and reset all imported demo-account passwords before production use.
