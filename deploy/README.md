# Setting up the droplet

Groover runs on `bondi`, the shared DigitalOcean droplet at `206.189.238.107`, next to the other projects. bondi already has the `deploy` user, 2 GiB of swap, Caddy importing `/etc/caddy/sites/*.caddy`, and a firewall open on 22, 80, and 443. These steps happen once.

## 1. DNS

At Porkbun, add an A record for `groover.siena.codes` pointing at `206.189.238.107`. Check it answers:

```bash
dig +short groover.siena.codes
```

## 2. On bondi, as root

```bash
ssh root@206.189.238.107
```

Install the venv module for the system Python 3.12:

```bash
apt install -y python3.12-venv
```

Check that port 9295 is free. This should print only the header line:

```bash
ss -ltn 'sport = :9295'
```

Make the app folders and the virtualenv:

```bash
install -d -o deploy -g deploy /srv/groover /srv/groover/app
```

```bash
sudo -u deploy python3.12 -m venv /srv/groover/venv
```

Make the key file, readable only by root. systemd reads it before starting the app as `deploy`:

```bash
install -d -m 700 /etc/groover && install -m 600 /dev/null /etc/groover/groover.env
```

Open it in an editor, so the keys stay out of shell history, and add `MUSIX_API_KEY=`, `SPOTIFY_CLIENT_ID=`, and `SPOTIFY_CLIENT_SECRET=` lines with their values:

```bash
nano /etc/groover/groover.env
```

Let `deploy` restart the service without a password:

```bash
printf 'deploy ALL=(root) NOPASSWD: /usr/bin/systemctl restart groover\n' > /tmp/groover.sudoers && visudo -cf /tmp/groover.sudoers && install -m 440 /tmp/groover.sudoers /etc/sudoers.d/groover
```

## 3. Install the service and the Caddy site

From the repo on your laptop:

```bash
scp deploy/groover.service deploy/groover.caddy root@206.189.238.107:/tmp/
```

Back on bondi, as root:

```bash
install -m 644 /tmp/groover.service /etc/systemd/system/groover.service && systemctl daemon-reload && systemctl enable groover
```

```bash
install -m 644 /tmp/groover.caddy /etc/caddy/sites/groover.caddy && systemctl reload caddy
```

The service starts on the first deploy, once the app files are there.

## 4. GitHub

From the repo on your laptop. Create the repo and use PR titles as merge commit titles:

```bash
gh repo create sienaguerrero/groover-revived --public --source . --remote origin --description "Song recommendations from lyrics, a 2019 Harvey Mudd CS121 project revived"
```

```bash
gh api -X PATCH repos/sienaguerrero/groover-revived -f merge_commit_title=PR_TITLE -f merge_commit_message=BLANK --silent
```

Copy the two deploy variables from housewives-taglines, which deploys to the same droplet as the same user:

```bash
gh variable set DEPLOY_HOST -R sienaguerrero/groover-revived --body "$(gh variable get DEPLOY_HOST -R sienaguerrero/housewives-taglines)"
```

```bash
gh variable set DEPLOY_KNOWN_HOSTS -R sienaguerrero/groover-revived --body "$(gh variable get DEPLOY_KNOWN_HOSTS -R sienaguerrero/housewives-taglines)"
```

Set the deploy key secret from the same private key file you gave housewives-taglines. GitHub can't read a secret back, so it has to come from the file:

```bash
gh secret set DEPLOY_KEY -R sienaguerrero/groover-revived < PATH_TO_DEPLOY_PRIVATE_KEY
```

Push. The workflow runs the tests, copies the app to bondi, installs the requirements and NLTK data, restarts the service, and checks that `https://groover.siena.codes/` answers 200:

```bash
git push -u origin main
```

## 5. Check it

```bash
curl -sI https://groover.siena.codes/ | head -1
```

On bondi, if anything is off:

```bash
systemctl status groover --no-pager
```

```bash
journalctl -u groover -n 50 --no-pager
```

The app holds about 300 MB once both models are loaded, so check that bondi still has room:

```bash
free -m
```
