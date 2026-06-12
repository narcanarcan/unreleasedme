# unreleased.me

New website for the old unreleased.me, heavily WIP
Contact me on discord for any inquires @falloutofheaven

## Start the site

Run this from PowerShell or Command Prompt in the project folder:

```powershell
.\start-server.cmd
```

The `.cmd` launcher does not require PowerShell script execution to be enabled.

Then open [http://127.0.0.1:8000](http://127.0.0.1:8000). Do not open the HTML files with `file://`; the account APIs require the local server.

The initial invite code is:

```text
UNRELEASED2026
```

Set `UNRELEASED_DEFAULT_INVITE` before the first run to use a different initial code.

## Manage invite codes

```powershell
python manage_invites.py list
python manage_invites.py add NEWCODE --max-uses 10
python manage_invites.py set-active NEWCODE no
```

The database is stored at `data/unreleased.db` and is excluded from version control.
