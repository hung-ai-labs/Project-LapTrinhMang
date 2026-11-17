-- Explicit initialization for an empty PostgreSQL database; compatible with Alembic 0004.
CREATE TABLE IF NOT EXISTS provinces (
 id varchar(20) PRIMARY KEY, name varchar(150) NOT NULL, dataset_version varchar(64) NOT NULL,
 is_active boolean NOT NULL DEFAULT true, created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS wards (
 id varchar(20) PRIMARY KEY, province_id varchar(20) NOT NULL REFERENCES provinces(id) ON DELETE RESTRICT,
 name varchar(150) NOT NULL, administrative_type varchar(32), latitude numeric(8,5), longitude numeric(8,5),
 dataset_version varchar(64) NOT NULL, is_active boolean NOT NULL DEFAULT true,
 created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
 CHECK ((latitude IS NULL) = (longitude IS NULL)), CHECK (latitude BETWEEN -90 AND 90), CHECK (longitude BETWEEN -180 AND 180)
);
CREATE TABLE IF NOT EXISTS users (
 id varchar(36) PRIMARY KEY, name varchar(100) NOT NULL, email varchar(254) NOT NULL UNIQUE,
 password_hash varchar(255) NOT NULL, token_version integer NOT NULL DEFAULT 0,
 address_text varchar(500), default_ward_id varchar(20) REFERENCES wards(id) ON DELETE RESTRICT,
 created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS observations (
 id varchar(36) PRIMARY KEY, ward_id varchar(20) NOT NULL REFERENCES wards(id) ON DELETE RESTRICT,
 temperature double precision NOT NULL, humidity double precision NOT NULL, wind_speed double precision NOT NULL,
 rainfall double precision NOT NULL, source varchar(32) NOT NULL, observed_at timestamptz NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_wards_province_name ON wards(province_id,name);
CREATE INDEX IF NOT EXISTS ix_users_default_ward_id ON users(default_ward_id);
CREATE INDEX IF NOT EXISTS ix_observations_ward_time ON observations(ward_id,source,observed_at);

-- Gemini assistant: one row per chat thread, message history replayed as model context.
CREATE TABLE IF NOT EXISTS chat_conversations (
 id varchar(36) PRIMARY KEY, user_id varchar(36) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 title varchar(200) NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS chat_messages (
 id varchar(36) PRIMARY KEY,
 conversation_id varchar(36) NOT NULL REFERENCES chat_conversations(id) ON DELETE CASCADE,
 role varchar(16) NOT NULL, content text NOT NULL, citations text,
 created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
 CHECK (role IN ('user','model'))
);
CREATE INDEX IF NOT EXISTS ix_chat_conversations_user ON chat_conversations(user_id,updated_at);
CREATE INDEX IF NOT EXISTS ix_chat_messages_conversation ON chat_messages(conversation_id,created_at);

-- Retrieval over the project's own research reports. Requires pgvector (Neon ships 0.8).
CREATE EXTENSION IF NOT EXISTS vector;
CREATE TABLE IF NOT EXISTS doc_chunks (
 id varchar(36) PRIMARY KEY, source_path varchar(500) NOT NULL, heading varchar(300),
 chunk_index integer NOT NULL, content text NOT NULL, content_hash varchar(64) NOT NULL UNIQUE,
 embedding vector(768) NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_doc_chunks_source ON doc_chunks(source_path,chunk_index);
