-- Nexo CRM Mono 3.0 / Business OS
-- Idempotent conceptual migration for deployments that manage schema explicitly.
-- The application metadata.create_all() creates this additive table automatically.
CREATE TABLE IF NOT EXISTS user_scopes (
    user_id VARCHAR(80) PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    client_id VARCHAR(80) NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_user_scopes_client_id ON user_scopes(client_id);
