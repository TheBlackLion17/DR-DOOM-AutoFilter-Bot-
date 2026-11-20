# Samantha AutoFilter log channel integration

Log channel: `-1002801544620`. Add `@agsfilterV3_bot` as a channel administrator with post permissions.

> **Deployment warning:** GitHub's current `bot.py` is a patch/updater script, while the VPS has the restored full bot. Do not overwrite the VPS `bot.py` with GitHub's version or run an unreviewed `git pull`.

Copy `samantha_logs.py` to the VPS project directory and add the following **to the full VPS bot** after reviewing its actual handlers:

```python
import samantha_logs as slog

# Immediately after the running bot client is started:
await slog.start(bot)

# In the existing private /start handler, after user registration:
await slog.user_started(message.from_user)

# After copy_message/send_video/send_document succeeds:
await slog.delivery_success(user_id, row)

# When all delivery attempts fail:
await slog.delivery_failed(user_id, row, exc)

# In existing admin command handlers after checking admin authorization:
await slog.admin_action(message.from_user.id, message.command[0])

# In indexer progress/completion/failure handlers:
await slog.index_event("completed", channel_id, scanned=scanned, indexed=indexed, skipped=skipped)
```

The module catches Telegram failures and rate limits repetitive logs. Logs do not change database records or fix channel peer resolution. Verify `python -m py_compile bot.py samantha_logs.py` before restarting `autofilter.service`.

The event integrations above are **not installed in the live VPS** and must be adapted to the full running source. Keep tokens, user-session strings, and DB credentials out of GitHub.
