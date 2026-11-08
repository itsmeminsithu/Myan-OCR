# Upgrade from v0.1.2 to v0.1.3

1. Back up your current project folder, especially `.env` and `models/`. No database migration is needed; this project has no server database.
2. Extract `Myan-OCR-v0.1.3-Update-Patch.zip` into Downloads.
3. Run `bash ~/Downloads/Myan-OCR-v0.1.3-Update-Patch/apply-update-mac.sh "$HOME/Downloads/Myan-OCR-v0.1.2"` (change target path as needed). The patch makes a source backup; it does not overwrite `.env` or `models/`.
4. In the original project directory run `docker compose up -d --build`.
5. Verify `http://localhost:8388/api/health`, then scan a non-sensitive local photo and check the result.

## Configuration

The updated Compose file defaults to `MYAN_OCR_LOCAL_DEV=1` for local, loopback-only testing. **Never use this setting with publicly reachable ports or an internet-facing proxy.** The default `MYAN_OCR_ALLOWED_HOSTS` includes localhost, 127.0.0.1 and testserver only. Use `MYAN_OCR_LOCAL_DEV=0` and add server-side authentication before any remote deployment. Optional `OCR_JOB_DEADLINE_SECONDS` is 75 by default. See `docs/SECURITY.md`.

Docker deployments behind a proxy must set a correct host allowlist; Google Cloud keys belong only in `.env` and must not be committed. Browser history is localStorage and is cleared separately by the user.
