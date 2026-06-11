-- 0001_init.sql -- FlowDesk derived-snapshot storage (TimescaleDB).
--
-- Matches PRD #8 §4 DDL as a SUPERSET: same core columns + composite PK
-- (instrument, ts), hypertable on ts, replay index, and a 90-day retention
-- policy. Adds two extracted fast-filter columns required by this build task:
--   * state        -- SessionState, for status filtering
--   * regime_sign  -- -1 | 0 | 1, for quick regime scans
-- The full canonical Snapshot (PRD #8 §3) is always preserved verbatim in the
-- JSONB `payload`; the extracted columns are derived projections only.
--
-- NOTE (PRD #8 §4 wrote the table name as `snapshot` singular). This build task
-- explicitly specifies `snapshots` (plural); we follow the task. See README.
--
-- Requires the TimescaleDB extension to be available on the Postgres instance.

CREATE EXTENSION IF NOT EXISTS timescaledb;

CREATE TABLE IF NOT EXISTS snapshots (
    instrument    TEXT             NOT NULL,
    session_date  DATE             NOT NULL,
    ts            TIMESTAMPTZ      NOT NULL,
    minute_index  INT              NOT NULL,
    state         TEXT             NOT NULL,   -- extracted: SessionState (PRD #9)
    regime_sign   SMALLINT         NOT NULL,   -- extracted: regime.sign (-1|0|1)
    forward       DOUBLE PRECISION NOT NULL,
    payload       JSONB            NOT NULL,   -- full Snapshot JSON (PRD #8 §3)
    PRIMARY KEY (instrument, ts),
    CONSTRAINT snapshots_regime_sign_chk CHECK (regime_sign IN (-1, 0, 1)),
    CONSTRAINT snapshots_state_chk
        CHECK (state IN ('PREMARKET', 'LIVE', 'STALE', 'CLOSED', 'HOLIDAY'))
);

-- Time-partition by ts. The partitioning column (ts) is part of the composite
-- primary key, as required by TimescaleDB for unique constraints.
SELECT create_hypertable('snapshots', 'ts', if_not_exists => TRUE);

-- Fast replay filters (PRD #10 §2): session listing + minute-range scans.
CREATE INDEX IF NOT EXISTS snapshots_replay_idx
    ON snapshots (instrument, session_date, minute_index);

-- Retention: keep 90 days of DERIVED-ONLY snapshots (PRD #10 §4), accumulative
-- since launch. Raw option chains are NEVER stored in the production database.
SELECT add_retention_policy('snapshots', INTERVAL '90 days', if_not_exists => TRUE);
