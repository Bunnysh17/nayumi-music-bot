# CrownX Final Perfect Bot

## Fixed API Commands

```text
phone <number>
aadhar <number>
vehicle <number>
like <uid>
profile <server> <uid>
pincode <code>
biochange <jwt> <newbio>
jwt <uid> <password> <newbio>
bypasskey <days>
whitelistuid <uid> <days>
```

## Main Commands

```text
help
ping
services
access
owner
prefix
setprefix <prefix>
```

## Access Commands

```text
wl add @user
wl remove @user
wl list
wl status @user
setaccessrole @role
removeaccessrole
```

## Owner Commands

```text
np add @user
np remove @user
np list
testservice
synccommands
shutdown
```

## Setup

```powershell
pip install -r requirements.txt
Copy-Item .env.example .env
notepad .env
python bot.py
```

## Notes

- Uses exact API IDs you provided.
- `.env` uses HELLBYTEX_API_KEY and HELLBYTEX_BASE_URL.
- Bunny owner has no-prefix and full access.
- Service commands require whitelist or access role.


## Premium Emoji Version
Uses your uploaded bot/application emojis. If any emoji does not render, update the emoji constants at the top of `bot.py`.
