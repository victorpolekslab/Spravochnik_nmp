-- Yandex Cloud / spravochnik-nmp / medical-platform-db / 2026-11-22.
-- Определения из SHOW CREATE TABLE; вторичные индексы не объявлены.

CREATE TABLE `users` (
    `user_id` Utf8 NOT NULL,
    `password_hash` Utf8 NOT NULL,
    `status` Utf8 NOT NULL,
    `auth_version` Uint64 NOT NULL,
    `created_at` Timestamp NOT NULL,
    `updated_at` Timestamp NOT NULL,
    PRIMARY KEY (`user_id`)
)
WITH (
    AUTO_PARTITIONING_BY_SIZE = ENABLED,
    AUTO_PARTITIONING_PARTITION_SIZE_MB = 2048
);

CREATE TABLE `user_emails` (
    `email_normalized` Utf8 NOT NULL,
    `user_id` Utf8 NOT NULL,
    `verified_at` Timestamp,
    `created_at` Timestamp NOT NULL,
    PRIMARY KEY (`email_normalized`)
)
WITH (
    AUTO_PARTITIONING_BY_SIZE = ENABLED,
    AUTO_PARTITIONING_PARTITION_SIZE_MB = 2048
);

CREATE TABLE `auth_sessions` (
    `user_id` Utf8 NOT NULL,
    `session_id` Utf8 NOT NULL,
    `app_id` Utf8 NOT NULL,
    `refresh_token_hash` String NOT NULL,
    `auth_version` Uint64 NOT NULL,
    `created_at` Timestamp NOT NULL,
    `expires_at` Timestamp NOT NULL,
    `revoked_at` Timestamp,
    PRIMARY KEY (`user_id`, `session_id`)
)
WITH (
    AUTO_PARTITIONING_BY_SIZE = ENABLED,
    AUTO_PARTITIONING_PARTITION_SIZE_MB = 2048,
    TTL = INTERVAL('PT0S') DELETE ON expires_at
);

CREATE TABLE `auth_challenges` (
    `token_hash` String NOT NULL,
    `user_id` Utf8 NOT NULL,
    `email_normalized` Utf8 NOT NULL,
    `purpose` Utf8 NOT NULL,
    `created_at` Timestamp NOT NULL,
    `expires_at` Timestamp NOT NULL,
    `consumed_at` Timestamp,
    PRIMARY KEY (`token_hash`)
)
WITH (
    AUTO_PARTITIONING_BY_SIZE = ENABLED,
    AUTO_PARTITIONING_PARTITION_SIZE_MB = 2048,
    TTL = INTERVAL('PT0S') DELETE ON expires_at
);

CREATE TABLE `user_access` (
    `user_id` Utf8 NOT NULL,
    `app_id` Utf8 NOT NULL,
    `permission` Utf8 NOT NULL,
    `granted_at` Timestamp NOT NULL,
    `revoked_at` Timestamp,
    PRIMARY KEY (`user_id`, `app_id`, `permission`)
)
WITH (
    AUTO_PARTITIONING_BY_SIZE = ENABLED,
    AUTO_PARTITIONING_PARTITION_SIZE_MB = 2048
);

CREATE TABLE `test_attempts` (
    `user_id` Utf8 NOT NULL,
    `app_id` Utf8 NOT NULL,
    `test_id` Utf8 NOT NULL,
    `attempt_id` Utf8 NOT NULL,
    `course_id` Utf8 NOT NULL,
    `test_version` Utf8 NOT NULL,
    `score` Uint32 NOT NULL,
    `max_score` Uint32 NOT NULL,
    `passed` Bool NOT NULL,
    `completed_at` Timestamp NOT NULL,
    PRIMARY KEY (`user_id`, `app_id`, `test_id`, `attempt_id`)
)
WITH (
    AUTO_PARTITIONING_BY_SIZE = ENABLED,
    AUTO_PARTITIONING_PARTITION_SIZE_MB = 2048
);

CREATE TABLE `learning_progress` (
    `user_id` Utf8 NOT NULL,
    `app_id` Utf8 NOT NULL,
    `course_id` Utf8 NOT NULL,
    `item_id` Utf8 NOT NULL,
    `status` Utf8 NOT NULL,
    `updated_at` Timestamp NOT NULL,
    `completed_at` Timestamp,
    PRIMARY KEY (`user_id`, `app_id`, `course_id`, `item_id`)
)
WITH (
    AUTO_PARTITIONING_BY_SIZE = ENABLED,
    AUTO_PARTITIONING_PARTITION_SIZE_MB = 2048
);
