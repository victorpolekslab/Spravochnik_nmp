CREATE TABLE browser_sessions (
    app_id Utf8 NOT NULL,
    handle_digest String NOT NULL,
    user_id Utf8 NOT NULL,
    session_id Utf8 NOT NULL,
    auth_version Uint64 NOT NULL,
    expires_at Timestamp NOT NULL,
    issued_at_seconds Uint64 NOT NULL,
    PRIMARY KEY (app_id, handle_digest)
) WITH (TTL = Interval("PT0S") ON expires_at);
