# Publishing Crypto Check

How to get Crypto Check onto GitHub, make releases, and publish it to PyPI.
After this one-time setup, **making a release is just pushing a git tag**. GitHub builds the Windows installer, the Linux AppImage and the PyPI package for you.

---

## One-time setup

### 1. Put the project on GitHub

From the project folder:

```bash
git init
git add .
git commit -m "Initial release"
gh repo create g0d1k/crypto-check --public --source . --push
```

The repo name **must be `crypto-check`**, because the README, `pyproject.toml`, the metainfo file and the screenshot link all point at `github.com/g0d1k/crypto-check`.
If you pick a different name, search the project for `g0d1k/crypto-check` and update every match.

### 2. Test the build (optional but recommended)

On GitHub, open **Actions → Release → Run workflow**.
This builds everything without publishing anything. When it finishes, download the files from the run's **Artifacts** section and try them out.

### 3. Set up PyPI publishing

This lets people run `pipx install crypto-check`. It uses PyPI's *trusted publishing*, so no passwords or tokens get stored anywhere.

1. Create an account at <https://pypi.org/account/register/> and turn on two-factor authentication (PyPI requires it).
2. Go to <https://pypi.org/manage/account/publishing/> and fill in **"Add a new pending publisher"**:
   | Field | Value |
   |---|---|
   | PyPI Project Name | `crypto-check` |
   | Owner | `g0d1k` |
   | Repository name | `crypto-check` |
   | Workflow name | `release.yml` |
   | Environment name | `pypi` |
3. On GitHub, open **Settings → Environments → New environment** and name it `pypi`.

If you skip this step, everything else still works. Only the "Publish to PyPI" job will fail.

---

## Making a release

1. Bump the version in **`crypto_check/__init__.py`**:
   ```python
   __version__ = "1.1.0"
   ```
2. Add a `<release>` entry at the top of the `<releases>` list in
   `packaging/linux/io.github.g0d1k.CryptoCheck.metainfo.xml` (Linux app stores show this as the changelog).
3. Commit, tag and push:
   ```bash
   git commit -am "Release 1.1.0"
   git tag v1.1.0
   git push && git push origin v1.1.0
   ```
4. Watch the **Actions** tab. In about 5 minutes you'll have a new release on the **Releases** page containing:
   - `CryptoCheck-Setup-1.1.0.exe`: Windows installer
   - `CryptoCheck-1.1.0-windows-portable.zip`: Windows, no install
   - `CryptoCheck-1.1.0-x86_64.AppImage`: Linux, any distro
   - `crypto_check-1.1.0-py3-none-any.whl` and `.tar.gz`: Python package (also uploaded to PyPI)

The workflow refuses to run if the tag (`v1.1.0`) doesn't match `__version__`, so the two can't drift apart.

**Never change the `AppId` GUID in `packaging/windows/installer.iss`.** Windows uses it to recognize upgrades.

---

## Next: app stores

Once the first GitHub release exists, these can be added (each needs your own account):

| Store | Reaches | What it needs |
|---|---|---|
| **AUR** | Arch, Manjaro, EndeavourOS | A `PKGBUILD` file pushed to aur.archlinux.org |
| **winget** | Windows 10/11 | A manifest submitted as a pull request to `microsoft/winget-pkgs` |
| **Flathub** | Nearly every Linux distro's software center | A Flatpak manifest submitted as a pull request to `flathub/flathub`, then a review |

The `.desktop` file, AppStream metainfo, icons and screenshot those stores need are already in `packaging/linux/` and `docs/`.

## Code signing (optional)

The Windows installer isn't signed, so SmartScreen shows a warning the first time people run it. Code-signing certificates cost money, but free signing for open-source projects is available through [SignPath Foundation](https://signpath.org/). The warning also fades on its own as more people download a given release.
