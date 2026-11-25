# LisiCode 1.3.0 — Gmail, Drive & Telegram

- Added Google OAuth Desktop flow with local loopback callback.
- Added Gmail search/read/send tools. Sending requires explicit confirmation.
- Added Google Drive search/read/create tools. File creation requires confirmation.
- Added Telegram personal-account login via Telethon, dialog listing, chat history and send/reply tools. Every send requires confirmation.
- Added `/connections gmail`, `/connections drive`, `/connections telegram` and disconnect commands.
- Added truthful connection status reporting and setup documentation.
- Added `requirements.txt` for Telethon.

Not included: Calendar, deleting/moving Drive files, deleting/modifying Gmail messages, background monitoring. Real account authorization must be completed by the user.
