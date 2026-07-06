# MockAPI

A lightweight API mocking tool. Upload a CSV or JSON file, register it as an HTTP endpoint, and point your target systems at it. Runs as a single Docker container on AWS EC2.

---

## How it works

There are two parts:

- **Server** — a FastAPI app that serves registered mock endpoints. All management happens through a protected `/admin` API.
- **CLI** (`mockapi`) — a command-line tool you run on your local machine to talk to the server's admin API.

Every mock endpoint is tied 1:1 to a data file. Creating an endpoint uploads the file in the same step. Deleting an endpoint removes the file too.

Supported formats: **CSV** and **JSON** are served as `application/json`. **XML** is served as `application/xml`, exactly as uploaded.

---

## Deploying to AWS EC2

### 1. Launch an EC2 instance

Any instance type will do for typical mock traffic. Recommended:

- AMI: **Amazon Linux 2023** or **Ubuntu 22.04**
- Instance type: `t3.small` or larger
- Storage: 20 GB gp3 (default is fine)
- Security group: open **port 8000** (TCP) to the IP ranges that need access. Keep port 22 (SSH) locked to your own IP.

### 2. Copy the files to the instance

From your local machine, copy the project folder to the instance:

```bash
scp -i your-key.pem -r /path/to/mockapi ec2-user@<your-ec2-ip>:~
```

Then SSH in:

```bash
ssh -i your-key.pem ec2-user@<your-ec2-ip>
```

If `scp` gives a permissions error on your `.pem` file:
```bash
chmod 400 your-key.pem
```

### 3. Run the setup script

```bash
sudo bash ~/mockapi/deploy/ec2-setup.sh
```

The script installs Docker, copies the app to `/opt/mockapi`, and auto-generates a random `ADMIN_TOKEN` in `/opt/mockapi/.env`.

### 4. Fix Docker permissions

By default you need `sudo` to run Docker commands. Add your user to the docker group so you don't have to:

```bash
sudo usermod -aG docker $USER
newgrp docker
```

### 5. Install Docker Buildx (if needed)

If you see `compose build requires buildx 0.17.0 or later`, install it manually:

```bash
mkdir -p ~/.docker/cli-plugins
curl -SL https://github.com/docker/buildx/releases/download/v0.17.1/buildx-v0.17.1.linux-amd64 \
  -o ~/.docker/cli-plugins/docker-buildx
chmod +x ~/.docker/cli-plugins/docker-buildx
```

### 6. Review the .env file

```bash
cat /opt/mockapi/.env
```

At minimum, confirm `ADMIN_TOKEN` is set to something you'd be happy treating as a secret. Change it if you like:

```bash
nano /opt/mockapi/.env
```

### 7. Start the server

```bash
cd /opt/mockapi
docker compose up -d --build
```

Check it's running:

```bash
docker compose logs -f
curl http://localhost:8000/health
# {"status":"ok"}
```

The server persists all config and uploaded files in a Docker volume (`mockapi_data`). Restarting or rebuilding the container does not lose your endpoints or data.

---

## Installing the CLI

The CLI runs on your local machine and talks to the server over HTTP. It requires Python 3.11+.

**macOS — install Python via Homebrew first if you haven't already:**
```bash
brew install python
```

**Create a virtual environment** (required on macOS — the system Python is externally managed):
```bash
cd mockapi
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

You'll see `(.venv)` at the start of your prompt confirming it's active. You need to reactivate it each time you open a new terminal:
```bash
source /path/to/mockapi/.venv/bin/activate
```

**Configure the CLI** by adding these to your `~/.zshrc` (replace values with your actual token):
```bash
echo 'export MOCKAPI_URL=http://<your-ec2-ip>:8000' >> ~/.zshrc
echo 'export MOCKAPI_ADMIN_TOKEN=<your-admin-token>' >> ~/.zshrc
source ~/.zshrc
```

To find your admin token on the server:
```bash
ssh -i your-key.pem ec2-user@<your-ec2-ip> "grep ADMIN_TOKEN /opt/mockapi/.env"
```

Alternatively, create a `.env` file in the directory where you run the CLI — it will be picked up automatically:
```
MOCKAPI_URL=http://<your-ec2-ip>:8000
MOCKAPI_ADMIN_TOKEN=<your-token>
```

Verify the connection:
```bash
mockapi ping
# Server is up. Status: ok
```

---

## Creating a mock endpoint

Everything starts with a data file — a CSV, JSON, or XML file containing the response you want the endpoint to return.

**CSV example (`users.csv`):**
```csv
id,name,email,role
1,Alice,alice@example.com,admin
2,Bob,bob@example.com,viewer
```
Served as `application/json` — each row becomes an object in a JSON array.

**JSON example (`products.json`):**
```json
[
  {"id": 1, "name": "Widget", "price": 9.99},
  {"id": 2, "name": "Gadget", "price": 24.99}
]
```
Served as `application/json`, unchanged.

**XML example (`orders.xml`):**
```xml
<?xml version="1.0" encoding="UTF-8"?>
<orders>
  <order>
    <id>1001</id>
    <customer>Alice</customer>
    <status>shipped</status>
  </order>
  <order>
    <id>1002</id>
    <customer>Bob</customer>
    <status>pending</status>
  </order>
</orders>
```
Served as `application/xml`, exactly as uploaded. The "row count" shown in listings is the number of direct child elements under the root (`<order>` in this case).

Create the endpoint in one command:

```bash
mockapi endpoint create --path /api/users --file users.csv
```

The file is uploaded and the endpoint is registered immediately. The mock URL is printed on success:

```
Endpoint created: GET /api/users
  ID:       b9dee069…
  Auth:     none
  File:     users.csv  (CSV, 2 rows)
  Mock URL: http://<your-ec2-ip>:8000/api/users
```

Test it:

```bash
curl http://<your-ec2-ip>:8000/api/users
```

```json
[
  {"id": "1", "name": "Alice", "email": "alice@example.com", "role": "admin"},
  {"id": "2", "name": "Bob", "email": "bob@example.com", "role": "viewer"}
]
```

### Options

| Flag | Default | Description |
|------|---------|-------------|
| `--path` | required | URL path, e.g. `/api/users` |
| `--file` | required | Path to `.csv`, `.json`, or `.xml` file |
| `--method` | `GET` | HTTP method (`GET`, `POST`, `PUT`, etc.) |
| `--auth` | `none` | Auth type: `none`, `api_key`, `basic`, or `jwt` |
| `--desc` | — | Optional description shown in listings |

### Validation rules

Uploads and endpoint fields are validated before anything is saved:

- **File size**: capped at 5MB.
- **CSV**: must not be empty, must have a header row, and every row must have the same number of columns as the header. Capped at 10,000 rows.
- **JSON**: must be a single object or an array of objects — a bare scalar (`42`, `"hello"`) or an array of non-objects (`["a", "b"]`) is rejected.
- **XML**: must be well-formed; entity expansion (the "billion laughs" DoS pattern) is rejected outright.
- **Encoding**: files must be valid UTF-8.
- **`--path`**: must be a bare path — no query string, fragment, or whitespace — and can't collide with the reserved `/admin/*` or `/health` paths (a mock endpoint there could never actually be reached, since those routes are matched first).
- **`--method`**: must be one of `GET`, `POST`, `PUT`, `PATCH`, `DELETE`, `HEAD`, `OPTIONS` (case-sensitive, per RFC 7231 — `get` is not `GET`).

A validation failure returns `422` with a structured body:

```json
{"detail": {"errors": [{"field": "path", "reason": "..."}]}}
```

---

## Authentication

Each endpoint can be protected independently. Set `--auth` when creating the endpoint, then configure the corresponding credentials.

### No auth (default)

```bash
mockapi endpoint create --path /api/public --file data.csv --auth none
```

### API Key

Any client with a valid key in the `X-API-Key` header (or `?api_key=` query param) can access the endpoint.

**Create the endpoint:**
```bash
mockapi endpoint create --path /api/orders --file orders.csv --auth api_key
```

**Generate a key for a client:**
```bash
mockapi auth api-key create my-service
```
```
API key created.  ID: 3f8a1c2d…
  Name: my-service
  Key (save this — shown once):
  xK9mP2qR5tV8wY1zA4bD7eG0hJ3nL6oQ
```

The full key is only shown at creation time. Store it somewhere safe.

**Client usage:**
```bash
curl http://<host>:8000/api/orders -H "X-API-Key: xK9mP2qR5tV8wY1zA4bD7eG0hJ3nL6oQ"
# or
curl "http://<host>:8000/api/orders?api_key=xK9mP2qR5tV8wY1zA4bD7eG0hJ3nL6oQ"
```

### Basic Auth

**Create the endpoint:**
```bash
mockapi endpoint create --path /api/internal --file internal.csv --auth basic
```

**Create a user:**
```bash
mockapi auth user create --username alice
# You'll be prompted for a password (input is hidden)
```

**Client usage:**
```bash
curl http://<host>:8000/api/internal -u alice:yourpassword
```

### JWT (Bearer token)

**Step 1 — configure the JWT secret** (do this once):
```bash
mockapi auth jwt config
```
```
JWT configured.  Algorithm: HS256
  Secret (save this): 3rN8kQ2mT5wX9pL1yZ4bV7eA0hD6jF
```

If you want to supply your own secret instead of auto-generating one:
```bash
mockapi auth jwt config --secret "my-own-secret-value"
```

**Step 2 — create the endpoint:**
```bash
mockapi endpoint create --path /api/secure --file secure.csv --auth jwt
```

**Step 3 — generate a token for a client:**
```bash
mockapi auth jwt token --subject my-service --expires 86400
```
```
Token (expires in 86400s):
eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

**Client usage:**
```bash
curl http://<host>:8000/api/secure -H "Authorization: Bearer eyJhbGci..."
```

---

## Managing endpoints

**List all endpoints:**
```bash
mockapi endpoint list
```

```
         Mock Endpoints
┌──────────┬────────┬──────────────┬─────────┬────────────┬──────┐
│ ID       │ Method │ Path         │ Auth    │ File       │ Rows │
├──────────┼────────┼──────────────┼─────────┼────────────┼──────┤
│ b9dee069 │ GET    │ /api/users   │ none    │ users.csv  │ 2    │
│ 3f8a1c2d │ GET    │ /api/orders  │ api_key │ orders.csv │ 50   │
│ 7c2e4b1a │ GET    │ /api/secure  │ jwt     │ secure.csv │ 10   │
└──────────┴────────┴──────────────┴─────────┴────────────┴──────┘
```

**Update an endpoint** (only the fields you pass are changed):
```bash
mockapi endpoint update b9dee069-<full-id-from-list> --method POST --desc "now a POST"
```
Pass `--file` to replace the underlying data file — the old one is deleted.

**Delete an endpoint** (also deletes its data file):
```bash
mockapi endpoint delete b9dee069-<full-id-from-list>
```

You'll be asked to confirm before anything is deleted.

---

## Managing credentials

**API keys:**
```bash
mockapi auth api-key list      # list all keys (masked)
mockapi auth api-key delete <id>
```

**Basic auth users:**
```bash
mockapi auth user list
mockapi auth user delete alice
```

**JWT:**
```bash
mockapi auth jwt status        # check if configured
mockapi auth jwt config        # set/rotate secret
mockapi auth jwt token         # generate a token
```

---

## Full CLI reference

```
mockapi ping                                        Check server connectivity

mockapi endpoint create                             Create a mock endpoint
  --path  PATH        URL path (required)
  --file  FILE        Data file — .csv, .json, or .xml (required)
  --method METHOD     HTTP method (default: GET)
  --auth  TYPE        none | api_key | basic | jwt (default: none)
  --desc  TEXT        Optional description

mockapi endpoint list                               List all endpoints
mockapi endpoint update ID                          Update an endpoint (only passed fields change)
  --path  PATH        New URL path
  --method METHOD     New HTTP method
  --auth  TYPE        New auth type: none | api_key | basic | jwt
  --desc  TEXT        New description
  --file  FILE        Replacement data file (deletes the old one)
mockapi endpoint delete ID                          Delete endpoint + its file

mockapi auth api-key create NAME                    Generate an API key
mockapi auth api-key list                           List keys (masked)
mockapi auth api-key delete ID                      Delete an API key

mockapi auth user create --username U --password P  Create a basic auth user
mockapi auth user list                              List users
mockapi auth user delete USERNAME                   Delete a user

mockapi auth jwt config [--secret S] [--algorithm A]  Set JWT secret
mockapi auth jwt status                               Check JWT config
mockapi auth jwt token [--subject S] [--expires N]    Generate a JWT
```

All commands support `--help` for details.

---

## Updating the server

To deploy a new version:

```bash
cd /opt/mockapi
git pull   # or copy new files
docker compose up -d --build
```

Data is in the `mockapi_data` Docker volume and is unaffected by rebuilds.

---

## Backing up data

All state lives in the `mockapi_data` Docker volume. To back it up:

```bash
docker run --rm \
  -v mockapi_data:/data \
  -v $(pwd):/backup \
  alpine tar czf /backup/mockapi-backup-$(date +%Y%m%d).tar.gz /data
```

To restore, reverse the process:

```bash
docker run --rm \
  -v mockapi_data:/data \
  -v $(pwd):/backup \
  alpine tar xzf /backup/mockapi-backup-YYYYMMDD.tar.gz -C /
```

---

## Security notes

**`ADMIN_TOKEN` is required.** The server now refuses to start if `ADMIN_TOKEN` is unset or left as the default `changeme` — every `/admin/*` route (and therefore every mock endpoint it can create) is only as protected as that one shared secret, so booting with no real value set is treated as a startup error rather than a silently insecure default. The EC2 setup script already auto-generates a random token, so this only matters if you're running the container some other way.

**Put TLS in front of this.** The admin token, API keys, and Basic-auth credentials all travel as plain HTTP headers — there's no TLS termination built into the container itself. For anything beyond local testing, put a reverse proxy (Caddy or nginx with a Let's Encrypt cert) or an AWS ALB with an ACM certificate in front of port 8000, and don't expose port 8000 directly to the internet.

**Upgrading to a non-root container.** As of this change, the container runs as an unprivileged `mockapi` user (UID/GID `999`) instead of root. A **brand-new** `mockapi_data` volume picks up the right ownership automatically on first mount. If you're upgrading an **existing** deployment, the volume's files were written by root under the old image and need a one-time ownership fix, or the new non-root process won't be able to write to them:

```bash
docker compose down
docker run --rm -v mockapi_data:/data alpine chown -R 999:999 /data
docker compose up -d --build
```

---

## Troubleshooting

**ConnectTimeout / "Operation timed out"** — port 8000 isn't open in your EC2 security group. Go to AWS Console → EC2 → Security Groups → Inbound Rules and add a TCP rule for port 8000. Also confirm the container is running: `docker ps`.

**"Permission denied while trying to connect to the Docker API"** — your user isn't in the docker group. Run:
```bash
sudo usermod -aG docker $USER
newgrp docker
```

**"compose build requires buildx 0.17.0 or later"** — install a newer Buildx binary manually:
```bash
mkdir -p ~/.docker/cli-plugins
curl -SL https://github.com/docker/buildx/releases/download/v0.17.1/buildx-v0.17.1.linux-amd64 \
  -o ~/.docker/cli-plugins/docker-buildx
chmod +x ~/.docker/cli-plugins/docker-buildx
```

**403 on admin routes** — `MOCKAPI_ADMIN_TOKEN` in your local env doesn't match `ADMIN_TOKEN` on the server. Check what the server has with:
```bash
ssh -i your-key.pem ec2-user@<your-ec2-ip> "grep ADMIN_TOKEN /opt/mockapi/.env"
```
Then update your local export to match.

**"Cannot connect to server"** — confirm `MOCKAPI_URL` is set correctly (`echo $MOCKAPI_URL`). If it prints nothing or shows a placeholder, re-export it.

**404 on a mock endpoint** — the path and HTTP method must match exactly. Run `mockapi endpoint list` to confirm.

**JWT 401 "JWT auth is not configured"** — you created a JWT-protected endpoint before running `mockapi auth jwt config`. Run the config command and try again.

**Container won't start** — check logs with `docker compose logs`. Confirm the `.env` file exists at `/opt/mockapi/.env` and contains a valid `ADMIN_TOKEN`.
