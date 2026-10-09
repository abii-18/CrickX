CREATE TABLE IF NOT EXISTS matches (
 match_id text PRIMARY KEY, match_name text NOT NULL, is_simulated boolean NOT NULL DEFAULT true,
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS delivery_events (
 match_id text NOT NULL REFERENCES matches, innings_number integer NOT NULL,
 raw_delivery_sequence integer NOT NULL, event_id text NOT NULL UNIQUE,
 revision_number integer NOT NULL, payload jsonb NOT NULL,
 revision_history jsonb NOT NULL DEFAULT '[]', received_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(match_id, innings_number, raw_delivery_sequence)
);
CREATE TABLE IF NOT EXISTS innings_scorecard (
 match_id text NOT NULL REFERENCES matches, innings_number integer NOT NULL,
 runs integer NOT NULL, wickets integer NOT NULL, legal_balls integer NOT NULL,
 extras integer NOT NULL, updated_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(match_id, innings_number)
);
CREATE TABLE IF NOT EXISTS over_summary (
 match_id text NOT NULL REFERENCES matches, innings_number integer NOT NULL,
 over_number integer NOT NULL, runs integer NOT NULL, wickets integer NOT NULL,
 legal_balls integer NOT NULL, PRIMARY KEY(match_id, innings_number, over_number)
);
CREATE TABLE IF NOT EXISTS batting_scorecard (
 match_id text NOT NULL REFERENCES matches, innings_number integer NOT NULL,
 player text NOT NULL, runs integer NOT NULL, balls integer NOT NULL,
 fours integer NOT NULL, sixes integer NOT NULL, dismissal text,
 PRIMARY KEY(match_id, innings_number, player)
);
CREATE TABLE IF NOT EXISTS bowling_scorecard (
 match_id text NOT NULL REFERENCES matches, innings_number integer NOT NULL,
 player text NOT NULL, runs integer NOT NULL, legal_balls integer NOT NULL,
 wickets integer NOT NULL, PRIMARY KEY(match_id, innings_number, player)
);
CREATE TABLE IF NOT EXISTS rejected_events (
 rejection_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 source_key text NOT NULL UNIQUE, reason text NOT NULL, raw_payload text NOT NULL,
 received_at timestamptz NOT NULL DEFAULT now()
);
