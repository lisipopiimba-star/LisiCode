# Public GitHub release checklist

This package is prepared for review, but publication is intentionally not automatic.

- [x] README and Windows startup instructions
- [x] Release notes for 1.4.0
- [x] `.gitignore` for local secrets, OAuth files, Telegram sessions, generated audio and caches
- [x] Python compile workflow for GitHub Actions
- [x] Smoke tests for local web API and ElevenLabs request formatting
- [x] Web server bound to loopback only (`127.0.0.1`)
- [ ] Choose and add a project license (author decision required)
- [ ] Review the upstream API provider/base URL and public-facing branding
- [ ] Test clean installation on Windows CMD and PowerShell
- [ ] Test Google OAuth and Telegram sign-in on the author's own accounts
- [ ] Test ElevenLabs with a real key and verify billing/credit behavior
- [ ] Review shell-command safety and external-path permissions before inviting public users
- [ ] Create a GitHub repository and publish only after explicit author approval

Do not publish a public repository until all unchecked items that matter to the intended audience are resolved.
