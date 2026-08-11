CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS vessels (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  imo varchar(7) UNIQUE,
  mmsi varchar(9) UNIQUE NOT NULL,
  name text NOT NULL,
  type text,
  flag text,
  length_m numeric,
  width_m numeric,
  deadweight_t numeric,
  owner text,
  operator text,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS ais_raw_messages (
  id bigserial PRIMARY KEY,
  provider text NOT NULL,
  provider_message_id text,
  payload jsonb NOT NULL,
  received_at timestamptz NOT NULL DEFAULT now(),
  processed_at timestamptz,
  processing_status text NOT NULL DEFAULT 'received',
  error_detail text
);
CREATE INDEX IF NOT EXISTS idx_ais_raw_received ON ais_raw_messages (received_at DESC);
CREATE UNIQUE INDEX IF NOT EXISTS idx_ais_raw_provider_id ON ais_raw_messages (provider, provider_message_id) WHERE provider_message_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS vessel_positions (
  id bigserial PRIMARY KEY,
  vessel_id uuid NOT NULL REFERENCES vessels(id),
  mmsi varchar(9) NOT NULL,
  recorded_at timestamptz NOT NULL,
  latitude double precision NOT NULL CHECK (latitude BETWEEN -90 AND 90),
  longitude double precision NOT NULL CHECK (longitude BETWEEN -180 AND 180),
  position_geometry geography(Point, 4326) NOT NULL,
  speed_kn numeric,
  course_deg numeric,
  heading_deg numeric,
  navigation_status text,
  source text NOT NULL,
  received_at timestamptz NOT NULL DEFAULT now(),
  quality_status text NOT NULL DEFAULT 'valid',
  quality_notes jsonb NOT NULL DEFAULT '[]'::jsonb,
  UNIQUE (vessel_id, recorded_at, latitude, longitude)
);
CREATE INDEX IF NOT EXISTS idx_positions_vessel_time ON vessel_positions (vessel_id, recorded_at DESC);
CREATE INDEX IF NOT EXISTS idx_positions_time ON vessel_positions (recorded_at DESC);
CREATE INDEX IF NOT EXISTS idx_positions_geometry ON vessel_positions USING gist (position_geometry);

CREATE TABLE IF NOT EXISTS vessel_current_state (
  vessel_id uuid PRIMARY KEY REFERENCES vessels(id),
  latitude double precision NOT NULL,
  longitude double precision NOT NULL,
  position_geometry geography(Point, 4326) NOT NULL,
  speed_kn numeric,
  course_deg numeric,
  heading_deg numeric,
  draught_m numeric,
  destination text,
  navigation_status text,
  last_position_at timestamptz NOT NULL,
  data_source text NOT NULL,
  quality_status text NOT NULL DEFAULT 'valid',
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_current_geometry ON vessel_current_state USING gist (position_geometry);

CREATE TABLE IF NOT EXISTS voyages (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  vessel_id uuid NOT NULL REFERENCES vessels(id),
  departure_port_id uuid,
  departure_time timestamptz,
  destination_port_id uuid,
  arrival_time timestamptz,
  reported_destination text,
  reported_eta timestamptz,
  distance_km numeric,
  duration_seconds bigint,
  status text NOT NULL DEFAULT 'in_progress'
);
CREATE INDEX IF NOT EXISTS idx_voyages_vessel_time ON voyages (vessel_id, departure_time DESC);

CREATE TABLE IF NOT EXISTS geofences (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  code text UNIQUE NOT NULL,
  name text NOT NULL,
  zone_type text NOT NULL,
  geometry geography(Polygon, 4326) NOT NULL,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  active boolean NOT NULL DEFAULT true
);
CREATE INDEX IF NOT EXISTS idx_geofences_geometry ON geofences USING gist (geometry);

CREATE TABLE IF NOT EXISTS tracking_events (
  id bigserial PRIMARY KEY,
  vessel_id uuid NOT NULL REFERENCES vessels(id),
  voyage_id uuid REFERENCES voyages(id),
  event_type text NOT NULL,
  started_at timestamptz NOT NULL,
  ended_at timestamptz,
  position_geometry geography(Point, 4326),
  details jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS vessel_behavior_profiles (
  vessel_id uuid PRIMARY KEY REFERENCES vessels(id),
  confidence numeric NOT NULL DEFAULT 0,
  confidence_level text NOT NULL DEFAULT 'insufficient',
  voyages_analyzed integer NOT NULL DEFAULT 0,
  observation_started_at timestamptz,
  observation_ended_at timestamptz,
  distance_tracked_km numeric NOT NULL DEFAULT 0,
  total_sailing_seconds bigint NOT NULL DEFAULT 0,
  total_port_seconds bigint NOT NULL DEFAULT 0,
  stops_at_sea integer NOT NULL DEFAULT 0,
  historical_ais_gaps integer NOT NULL DEFAULT 0,
  model_version text NOT NULL,
  generated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS vessel_route_profiles (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  vessel_id uuid NOT NULL REFERENCES vessels(id),
  origin_port_id uuid,
  destination_port_id uuid,
  voyage_count integer NOT NULL,
  share numeric NOT NULL,
  distance_min_km numeric,
  distance_max_km numeric,
  duration_min_seconds bigint,
  duration_max_seconds bigint,
  speed_min_kn numeric,
  speed_max_kn numeric,
  stops_min integer,
  stops_max integer,
  route_centerline geography(LineString, 4326),
  route_corridor geography(Polygon, 4326),
  sample_voyage_ids uuid[] NOT NULL DEFAULT '{}',
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_route_profiles_vessel ON vessel_route_profiles (vessel_id, voyage_count DESC);
CREATE INDEX IF NOT EXISTS idx_route_corridor ON vessel_route_profiles USING gist (route_corridor);

CREATE TABLE IF NOT EXISTS vessel_speed_profiles (
  vessel_id uuid NOT NULL REFERENCES vessels(id),
  route_profile_id uuid REFERENCES vessel_route_profiles(id),
  voyage_phase text NOT NULL,
  sample_count bigint NOT NULL,
  average_kn numeric,
  median_kn numeric,
  p95_kn numeric,
  typical_min_kn numeric,
  typical_max_kn numeric,
  histogram jsonb NOT NULL,
  updated_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (vessel_id, route_profile_id, voyage_phase)
);

CREATE TABLE IF NOT EXISTS vessel_port_profiles (
  vessel_id uuid NOT NULL REFERENCES vessels(id),
  port_id uuid NOT NULL,
  visit_count integer NOT NULL,
  visit_share numeric NOT NULL,
  median_stay_seconds bigint,
  stay_min_seconds bigint,
  stay_max_seconds bigint,
  usual boolean NOT NULL DEFAULT false,
  updated_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (vessel_id, port_id)
);

CREATE TABLE IF NOT EXISTS vessel_stop_profiles (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  vessel_id uuid NOT NULL REFERENCES vessels(id),
  cluster_center geography(Point, 4326) NOT NULL,
  cluster_radius_m numeric NOT NULL,
  stop_count integer NOT NULL,
  average_duration_seconds bigint,
  median_duration_seconds bigint,
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_stop_profiles_geometry ON vessel_stop_profiles USING gist (cluster_center);

CREATE TABLE IF NOT EXISTS vessel_draught_profiles (
  vessel_id uuid NOT NULL REFERENCES vessels(id),
  route_profile_id uuid REFERENCES vessel_route_profiles(id),
  sample_count integer NOT NULL,
  typical_min_m numeric,
  typical_max_m numeric,
  average_departure_m numeric,
  average_arrival_m numeric,
  history jsonb NOT NULL DEFAULT '[]'::jsonb,
  updated_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (vessel_id, route_profile_id)
);

CREATE TABLE IF NOT EXISTS vessel_temporal_profiles (
  vessel_id uuid PRIMARY KEY REFERENCES vessels(id),
  departures_by_time_bucket integer[] NOT NULL DEFAULT '{}',
  voyages_by_weekday integer[] NOT NULL DEFAULT '{}',
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS vessel_activity_profiles (
  vessel_id uuid PRIMARY KEY REFERENCES vessels(id),
  activity_area geography(MultiPolygon, 4326),
  density_cells jsonb NOT NULL DEFAULT '[]'::jsonb,
  position_count bigint NOT NULL DEFAULT 0,
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_activity_profiles_geometry ON vessel_activity_profiles USING gist (activity_area);

CREATE TABLE IF NOT EXISTS detected_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  event_code text UNIQUE NOT NULL,
  event_type text NOT NULL,
  vessel_id uuid NOT NULL REFERENCES vessels(id),
  related_vessel_id uuid REFERENCES vessels(id),
  voyage_id uuid REFERENCES voyages(id),
  started_at timestamptz NOT NULL,
  ended_at timestamptz,
  location geography(Point, 4326) NOT NULL,
  affected_area geography(Polygon, 4326),
  severity text NOT NULL CHECK (severity IN ('low','medium','high')),
  confidence numeric NOT NULL CHECK (confidence BETWEEN 0 AND 1),
  status text NOT NULL DEFAULT 'active' CHECK (status IN ('active','resolved','reviewed','dismissed')),
  data jsonb NOT NULL DEFAULT '{}'::jsonb,
  explanation text NOT NULL,
  factors jsonb NOT NULL DEFAULT '[]'::jsonb,
  detector_version text NOT NULL,
  reviewed_by uuid,
  review_note text,
  reviewed_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_events_vessel_time ON detected_events (vessel_id, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_events_voyage ON detected_events (voyage_id, started_at);
CREATE INDEX IF NOT EXISTS idx_events_status_severity ON detected_events (status, severity, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_events_location ON detected_events USING gist (location);
CREATE INDEX IF NOT EXISTS idx_events_data ON detected_events USING gin (data);

CREATE TABLE IF NOT EXISTS event_groups (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  group_code text UNIQUE NOT NULL,
  vessel_id uuid NOT NULL REFERENCES vessels(id),
  voyage_id uuid REFERENCES voyages(id),
  started_at timestamptz NOT NULL,
  ended_at timestamptz,
  status text NOT NULL DEFAULT 'active',
  explanation text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS event_group_members (
  event_group_id uuid NOT NULL REFERENCES event_groups(id) ON DELETE CASCADE,
  event_id uuid NOT NULL REFERENCES detected_events(id) ON DELETE CASCADE,
  sequence_number integer NOT NULL,
  PRIMARY KEY (event_group_id, event_id)
);

CREATE TABLE IF NOT EXISTS vessel_encounters (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  event_id uuid UNIQUE NOT NULL REFERENCES detected_events(id),
  vessel_a_id uuid NOT NULL REFERENCES vessels(id),
  vessel_b_id uuid NOT NULL REFERENCES vessels(id),
  started_at timestamptz NOT NULL,
  ended_at timestamptz,
  minimum_distance_m numeric NOT NULL,
  average_speed_a_kn numeric,
  average_speed_b_kn numeric,
  encounter_location geography(Point, 4326) NOT NULL,
  previous_encounter_count integer NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_encounters_pair_time ON vessel_encounters (vessel_a_id, vessel_b_id, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_encounters_location ON vessel_encounters USING gist (encounter_location);

CREATE TABLE IF NOT EXISTS event_detector_config (
  detector_type text PRIMARY KEY,
  enabled boolean NOT NULL DEFAULT true,
  parameters jsonb NOT NULL,
  version integer NOT NULL DEFAULT 1,
  updated_at timestamptz NOT NULL DEFAULT now()
);
INSERT INTO event_detector_config (detector_type, parameters) VALUES
  ('ais_gap', '{"short_minutes":15,"medium_minutes":60,"long_minutes":180}'),
  ('unusual_stop', '{"speed_threshold_kn":0.8,"minimum_duration_minutes":40}'),
  ('unexpected_speed', '{"minimum_duration_minutes":30}'),
  ('vessel_encounter', '{"distance_threshold_m":500,"minimum_duration_minutes":20,"maximum_speed_kn":2}'),
  ('draught_change', '{"minimum_change_m":0.5}'),
  ('route_deviation', '{"use_vessel_route_profile":true}')
ON CONFLICT (detector_type) DO NOTHING;

CREATE TABLE IF NOT EXISTS ais_coverage_zones (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name text NOT NULL,
  quality text NOT NULL CHECK (quality IN ('high','medium','low','unknown')),
  geometry geography(Polygon, 4326) NOT NULL,
  source text,
  valid_from timestamptz,
  valid_to timestamptz
);
CREATE INDEX IF NOT EXISTS idx_coverage_geometry ON ais_coverage_zones USING gist (geometry);

-- Stage 5: Risk Engine. Event Detection remains the source of observable facts;
-- these tables store the separate, explainable prioritisation layer.
ALTER TABLE vessel_current_state
  ADD COLUMN IF NOT EXISTS risk_score smallint NOT NULL DEFAULT 0 CHECK (risk_score BETWEEN 0 AND 100),
  ADD COLUMN IF NOT EXISTS risk_level text NOT NULL DEFAULT 'low' CHECK (risk_level IN ('low', 'moderate', 'high', 'critical')),
  ADD COLUMN IF NOT EXISTS risk_updated_at timestamptz;

CREATE INDEX IF NOT EXISTS idx_current_risk_priority
  ON vessel_current_state (risk_score DESC, risk_updated_at DESC)
  WHERE risk_level IN ('high', 'critical');

CREATE TABLE IF NOT EXISTS risk_assessments (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  vessel_id uuid NOT NULL REFERENCES vessels(id) ON DELETE CASCADE,
  voyage_id uuid REFERENCES voyages(id) ON DELETE CASCADE,
  subject_type text NOT NULL CHECK (subject_type IN ('vessel', 'voyage')),
  risk_score smallint NOT NULL CHECK (risk_score BETWEEN 0 AND 100),
  risk_level text NOT NULL CHECK (risk_level IN ('low', 'moderate', 'high', 'critical')),
  previous_score smallint CHECK (previous_score BETWEEN 0 AND 100),
  score_delta smallint NOT NULL DEFAULT 0 CHECK (score_delta BETWEEN -100 AND 100),
  factor_score smallint NOT NULL DEFAULT 0 CHECK (factor_score BETWEEN 0 AND 100),
  correlation_bonus smallint NOT NULL DEFAULT 0 CHECK (correlation_bonus BETWEEN 0 AND 100),
  confidence numeric(5,4) NOT NULL DEFAULT 0 CHECK (confidence BETWEEN 0 AND 1),
  lifecycle text NOT NULL DEFAULT 'active' CHECK (lifecycle IN ('active', 'recent', 'historical')),
  model_version text NOT NULL DEFAULT 'CI-RISK-1.0',
  explanation text NOT NULL,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  calculated_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CHECK (subject_type <> 'voyage' OR voyage_id IS NOT NULL)
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_risk_assessment_current_vessel
  ON risk_assessments (vessel_id) WHERE subject_type = 'vessel';
CREATE UNIQUE INDEX IF NOT EXISTS idx_risk_assessment_current_voyage
  ON risk_assessments (voyage_id) WHERE subject_type = 'voyage';
CREATE INDEX IF NOT EXISTS idx_risk_assessment_priority
  ON risk_assessments (risk_level, risk_score DESC, updated_at DESC);

CREATE TABLE IF NOT EXISTS risk_factors (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  assessment_id uuid NOT NULL REFERENCES risk_assessments(id) ON DELETE CASCADE,
  vessel_id uuid NOT NULL REFERENCES vessels(id) ON DELETE CASCADE,
  voyage_id uuid REFERENCES voyages(id) ON DELETE CASCADE,
  factor_type text NOT NULL,
  base_score numeric(5,2) NOT NULL CHECK (base_score BETWEEN 0 AND 100),
  adjusted_score numeric(5,2) NOT NULL CHECK (adjusted_score BETWEEN 0 AND 100),
  confidence numeric(5,4) NOT NULL CHECK (confidence BETWEEN 0 AND 1),
  source_event_id uuid REFERENCES detected_events(id) ON DELETE SET NULL,
  explanation text NOT NULL,
  evidence jsonb NOT NULL DEFAULT '{}'::jsonb,
  context_adjustments jsonb NOT NULL DEFAULT '[]'::jsonb,
  lifecycle text NOT NULL DEFAULT 'active' CHECK (lifecycle IN ('active', 'recent', 'historical')),
  decay_multiplier numeric(5,4) NOT NULL DEFAULT 1 CHECK (decay_multiplier BETWEEN 0 AND 1),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_risk_factors_assessment
  ON risk_factors (assessment_id, adjusted_score DESC);
CREATE INDEX IF NOT EXISTS idx_risk_factors_vessel_time
  ON risk_factors (vessel_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_risk_factors_event
  ON risk_factors (source_event_id) WHERE source_event_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_risk_factors_evidence
  ON risk_factors USING gin (evidence);

CREATE TABLE IF NOT EXISTS risk_history (
  id bigserial PRIMARY KEY,
  vessel_id uuid NOT NULL REFERENCES vessels(id) ON DELETE CASCADE,
  voyage_id uuid REFERENCES voyages(id) ON DELETE CASCADE,
  subject_type text NOT NULL CHECK (subject_type IN ('vessel', 'voyage')),
  risk_score smallint NOT NULL CHECK (risk_score BETWEEN 0 AND 100),
  risk_level text NOT NULL CHECK (risk_level IN ('low', 'moderate', 'high', 'critical')),
  previous_score smallint CHECK (previous_score BETWEEN 0 AND 100),
  score_delta smallint NOT NULL DEFAULT 0 CHECK (score_delta BETWEEN -100 AND 100),
  factor_score smallint NOT NULL DEFAULT 0 CHECK (factor_score BETWEEN 0 AND 100),
  correlation_bonus smallint NOT NULL DEFAULT 0 CHECK (correlation_bonus BETWEEN 0 AND 100),
  reason text NOT NULL,
  model_version text NOT NULL DEFAULT 'CI-RISK-1.0',
  factor_snapshot jsonb NOT NULL DEFAULT '[]'::jsonb,
  calculated_at timestamptz NOT NULL DEFAULT now(),
  CHECK (subject_type <> 'voyage' OR voyage_id IS NOT NULL)
);
CREATE INDEX IF NOT EXISTS idx_risk_history_vessel_time
  ON risk_history (vessel_id, calculated_at DESC);
CREATE INDEX IF NOT EXISTS idx_risk_history_voyage_time
  ON risk_history (voyage_id, calculated_at DESC) WHERE voyage_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_risk_history_level_time
  ON risk_history (risk_level, calculated_at DESC);

CREATE TABLE IF NOT EXISTS risk_scenarios (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  assessment_id uuid NOT NULL REFERENCES risk_assessments(id) ON DELETE CASCADE,
  vessel_id uuid NOT NULL REFERENCES vessels(id) ON DELETE CASCADE,
  voyage_id uuid REFERENCES voyages(id) ON DELETE CASCADE,
  scenario_type text NOT NULL,
  title text NOT NULL,
  status text NOT NULL DEFAULT 'requires_review' CHECK (status IN ('requires_review', 'reviewed', 'dismissed')),
  confidence numeric(5,4) NOT NULL CHECK (confidence BETWEEN 0 AND 1),
  score_adjustment smallint NOT NULL DEFAULT 0 CHECK (score_adjustment BETWEEN 0 AND 100),
  factor_ids uuid[] NOT NULL DEFAULT '{}',
  explanation text NOT NULL,
  evidence jsonb NOT NULL DEFAULT '{}'::jsonb,
  model_version text NOT NULL DEFAULT 'CI-RISK-1.0',
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_risk_scenarios_vessel_status
  ON risk_scenarios (vessel_id, status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_risk_scenarios_assessment
  ON risk_scenarios (assessment_id);

CREATE TABLE IF NOT EXISTS risk_rule_config (
  rule_key text PRIMARY KEY,
  enabled boolean NOT NULL DEFAULT true,
  base_score smallint NOT NULL DEFAULT 0 CHECK (base_score BETWEEN 0 AND 100),
  maximum_score smallint NOT NULL CHECK (maximum_score BETWEEN 0 AND 100),
  parameters jsonb NOT NULL DEFAULT '{}'::jsonb,
  model_version text NOT NULL DEFAULT 'CI-RISK-1.0',
  config_version integer NOT NULL DEFAULT 1,
  effective_from timestamptz NOT NULL DEFAULT now(),
  updated_by text,
  updated_at timestamptz NOT NULL DEFAULT now()
);

INSERT INTO risk_rule_config (rule_key, base_score, maximum_score, parameters) VALUES
  ('ais_gap', 10, 22, '{"duration_over_180m":8,"high_coverage_zone":4}'),
  ('route_deviation', 6, 12, '{"outside_corridor":4,"historically_rare":2}'),
  ('vessel_encounter', 7, 17, '{"duration_over_60m":5,"low_speed":3,"open_sea":2}'),
  ('draught_change', 5, 18, '{"after_ais_gap":5,"after_encounter":8}'),
  ('unusual_stop', 6, 10, '{"outside_known_area":4}'),
  ('unexpected_speed', 4, 6, '{"sustained_deviation":2}'),
  ('correlation_sequence', 0, 15, '{"route_plus_gap":4,"gap_plus_encounter":6,"encounter_plus_draught":8,"cap":15}'),
  ('risk_thresholds', 0, 100, '{"low":[0,24],"moderate":[25,49],"high":[50,74],"critical":[75,100]}'),
  ('risk_decay', 0, 100, '{"active_hours":6,"recent_hours":24,"historical_multiplier":0}'),
  ('notification_policy', 0, 100, '{"level_transitions":["moderate_to_high","high_to_critical"],"rapid_increase_per_hour":20,"critical_factor":true}')
ON CONFLICT (rule_key) DO NOTHING;

-- Stage 7: Port Aktau / Smart Port.
-- `maritime_ports` remains the canonical port registry from Stage 6. A Voyage
-- describes movement at sea; a PortCall below describes the operational visit.

-- The canonical port registry is declared here before the operational tables
-- that reference it. Stage 6 analytics below reuse this same registry.
CREATE TABLE IF NOT EXISTS maritime_ports (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  unlocode varchar(5) UNIQUE,
  name text NOT NULL,
  country_code varchar(3),
  location geography(Point, 4326),
  source text NOT NULL,
  source_timestamp timestamptz NOT NULL,
  confidence numeric(5,4) NOT NULL CHECK (confidence BETWEEN 0 AND 1),
  verification_status text NOT NULL
    CHECK (verification_status IN ('REPORTED', 'ESTIMATED', 'VERIFIED')),
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS idx_maritime_ports_location
  ON maritime_ports USING gist (location);

CREATE TABLE IF NOT EXISTS port_operational_profiles (
  port_id uuid PRIMARY KEY REFERENCES maritime_ports(id) ON DELETE CASCADE,
  timezone text NOT NULL,
  operational_status text NOT NULL
    CHECK (operational_status IN ('NORMAL', 'LIMITED', 'SUSPENDED', 'CLOSED')),
  high_risk_threshold integer NOT NULL DEFAULT 75
    CHECK (high_risk_threshold BETWEEN 0 AND 100),
  queue_policy jsonb NOT NULL DEFAULT '{}'::jsonb,
  source text NOT NULL,
  source_timestamp timestamptz NOT NULL,
  confidence numeric(5,4) NOT NULL CHECK (confidence BETWEEN 0 AND 1),
  verification_status text NOT NULL
    CHECK (verification_status IN ('REPORTED', 'ESTIMATED', 'VERIFIED')),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS berths (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  port_id uuid NOT NULL REFERENCES maritime_ports(id) ON DELETE CASCADE,
  berth_number integer NOT NULL CHECK (berth_number > 0),
  name text NOT NULL,
  length_m numeric(8,2) NOT NULL CHECK (length_m > 0),
  max_vessel_length_m numeric(8,2) NOT NULL CHECK (max_vessel_length_m > 0),
  max_draught_m numeric(6,2) NOT NULL CHECK (max_draught_m > 0),
  operational_status text NOT NULL
    CHECK (operational_status IN ('AVAILABLE', 'OCCUPIED', 'LIMITED', 'CLOSED', 'MAINTENANCE')),
  available_from timestamptz,
  restrictions jsonb NOT NULL DEFAULT '[]'::jsonb,
  source text NOT NULL,
  source_timestamp timestamptz NOT NULL,
  confidence numeric(5,4) NOT NULL CHECK (confidence BETWEEN 0 AND 1),
  verification_status text NOT NULL
    CHECK (verification_status IN ('REPORTED', 'ESTIMATED', 'VERIFIED')),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (port_id, berth_number),
  CHECK (max_vessel_length_m <= length_m)
);
CREATE INDEX IF NOT EXISTS idx_berths_port_status
  ON berths (port_id, operational_status, available_from);

CREATE TABLE IF NOT EXISTS berth_capabilities (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  berth_id uuid NOT NULL REFERENCES berths(id) ON DELETE CASCADE,
  capability_type text NOT NULL
    CHECK (capability_type IN ('CARGO', 'EQUIPMENT', 'SERVICE', 'RESTRICTION')),
  capability_key text NOT NULL,
  capability_value jsonb NOT NULL DEFAULT '{}'::jsonb,
  active boolean NOT NULL DEFAULT true,
  source text NOT NULL,
  source_timestamp timestamptz NOT NULL,
  confidence numeric(5,4) NOT NULL CHECK (confidence BETWEEN 0 AND 1),
  verification_status text NOT NULL
    CHECK (verification_status IN ('REPORTED', 'ESTIMATED', 'VERIFIED')),
  UNIQUE (berth_id, capability_type, capability_key)
);
CREATE INDEX IF NOT EXISTS idx_berth_capabilities_lookup
  ON berth_capabilities (berth_id, capability_type, active);

CREATE TABLE IF NOT EXISTS port_calls (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  external_id text UNIQUE,
  vessel_id uuid NOT NULL REFERENCES vessels(id) ON DELETE RESTRICT,
  voyage_id uuid REFERENCES voyages(id) ON DELETE SET NULL,
  port_id uuid NOT NULL REFERENCES maritime_ports(id) ON DELETE RESTRICT,
  berth_id uuid REFERENCES berths(id) ON DELETE SET NULL,
  reported_eta timestamptz,
  predicted_eta timestamptz,
  actual_arrival timestamptz,
  queue_entered_at timestamptz,
  berth_started_at timestamptz,
  service_started_at timestamptz,
  service_completed_at timestamptz,
  actual_departure timestamptz,
  status text NOT NULL
    CHECK (status IN ('APPROACHING', 'WAITING', 'ARRIVED', 'BERTH_ASSIGNED', 'IN_SERVICE', 'SERVICE_COMPLETED', 'DEPARTED', 'CANCELLED')),
  risk_score_at_arrival integer CHECK (risk_score_at_arrival BETWEEN 0 AND 100),
  risk_model_version text,
  reported_cargo_t numeric(14,3) CHECK (reported_cargo_t >= 0),
  reported_draught_m numeric(6,2) CHECK (reported_draught_m >= 0),
  source text NOT NULL,
  source_timestamp timestamptz NOT NULL,
  confidence numeric(5,4) NOT NULL CHECK (confidence BETWEEN 0 AND 1),
  verification_status text NOT NULL
    CHECK (verification_status IN ('REPORTED', 'ESTIMATED', 'VERIFIED')),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CHECK (service_started_at IS NULL OR service_completed_at IS NULL OR service_completed_at >= service_started_at),
  CHECK (actual_arrival IS NULL OR actual_departure IS NULL OR actual_departure >= actual_arrival)
);
CREATE INDEX IF NOT EXISTS idx_port_calls_port_eta
  ON port_calls (port_id, predicted_eta, status);
CREATE INDEX IF NOT EXISTS idx_port_calls_vessel_time
  ON port_calls (vessel_id, COALESCE(actual_arrival, predicted_eta) DESC);
CREATE INDEX IF NOT EXISTS idx_port_calls_berth_window
  ON port_calls (berth_id, berth_started_at, service_completed_at)
  WHERE berth_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS idx_port_calls_active_voyage_port
  ON port_calls (voyage_id, port_id)
  WHERE voyage_id IS NOT NULL AND status NOT IN ('DEPARTED', 'CANCELLED');

CREATE TABLE IF NOT EXISTS eta_predictions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  port_call_id uuid NOT NULL REFERENCES port_calls(id) ON DELETE CASCADE,
  reported_eta timestamptz,
  predicted_eta timestamptz NOT NULL,
  likely_window_start timestamptz NOT NULL,
  likely_window_end timestamptz NOT NULL,
  confidence numeric(5,4) NOT NULL CHECK (confidence BETWEEN 0 AND 1),
  factors jsonb NOT NULL,
  model_version text NOT NULL,
  calculated_at timestamptz NOT NULL,
  actual_arrival timestamptz,
  error_minutes integer,
  supersedes_id uuid REFERENCES eta_predictions(id) ON DELETE SET NULL,
  explanation text NOT NULL,
  CHECK (likely_window_start <= predicted_eta AND predicted_eta <= likely_window_end),
  CHECK ((actual_arrival IS NULL) = (error_minutes IS NULL))
);
CREATE INDEX IF NOT EXISTS idx_eta_predictions_call_time
  ON eta_predictions (port_call_id, calculated_at DESC);
CREATE INDEX IF NOT EXISTS idx_eta_predictions_accuracy
  ON eta_predictions (model_version, calculated_at DESC)
  WHERE actual_arrival IS NOT NULL;

CREATE TABLE IF NOT EXISTS service_predictions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  port_call_id uuid NOT NULL REFERENCES port_calls(id) ON DELETE CASCADE,
  berth_id uuid NOT NULL REFERENCES berths(id) ON DELETE RESTRICT,
  cargo_handling_minutes integer NOT NULL CHECK (cargo_handling_minutes >= 0),
  documentation_minutes integer NOT NULL CHECK (documentation_minutes >= 0),
  other_operations_minutes integer NOT NULL CHECK (other_operations_minutes >= 0),
  weather_delay_minutes integer NOT NULL DEFAULT 0 CHECK (weather_delay_minutes >= 0),
  total_minutes integer NOT NULL CHECK (total_minutes > 0),
  historical_rate_tph numeric(12,3) CHECK (historical_rate_tph > 0),
  predicted_start timestamptz NOT NULL,
  predicted_release timestamptz NOT NULL,
  confidence numeric(5,4) NOT NULL CHECK (confidence BETWEEN 0 AND 1),
  factors jsonb NOT NULL DEFAULT '{}'::jsonb,
  model_version text NOT NULL,
  calculated_at timestamptz NOT NULL,
  actual_minutes integer CHECK (actual_minutes >= 0),
  error_minutes integer,
  CHECK (predicted_release >= predicted_start),
  CHECK ((actual_minutes IS NULL) = (error_minutes IS NULL))
);
CREATE INDEX IF NOT EXISTS idx_service_predictions_call_time
  ON service_predictions (port_call_id, calculated_at DESC);
CREATE INDEX IF NOT EXISTS idx_service_predictions_berth_release
  ON service_predictions (berth_id, predicted_release);

CREATE TABLE IF NOT EXISTS berth_assignments (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  port_call_id uuid NOT NULL REFERENCES port_calls(id) ON DELETE CASCADE,
  recommended_berth_id uuid NOT NULL REFERENCES berths(id) ON DELETE RESTRICT,
  selected_berth_id uuid REFERENCES berths(id) ON DELETE RESTRICT,
  state text NOT NULL
    CHECK (state IN ('RECOMMENDED', 'ACCEPTED', 'CHANGED', 'DEFERRED', 'CANCELLED')),
  compatibility_snapshot jsonb NOT NULL,
  confidence numeric(5,4) NOT NULL CHECK (confidence BETWEEN 0 AND 1),
  reasons jsonb NOT NULL,
  expected_effect text NOT NULL,
  generated_at timestamptz NOT NULL,
  decided_by text,
  decided_at timestamptz,
  decision_note text,
  automated boolean NOT NULL DEFAULT false,
  CHECK ((state = 'RECOMMENDED') = (decided_at IS NULL)),
  CHECK (state <> 'CHANGED' OR selected_berth_id IS NOT NULL),
  CHECK (automated = false)
);
CREATE INDEX IF NOT EXISTS idx_berth_assignments_call_time
  ON berth_assignments (port_call_id, generated_at DESC);
CREATE INDEX IF NOT EXISTS idx_berth_assignments_selected
  ON berth_assignments (selected_berth_id, state, generated_at)
  WHERE selected_berth_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS berth_assignment_decisions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  berth_assignment_id uuid NOT NULL REFERENCES berth_assignments(id) ON DELETE CASCADE,
  action text NOT NULL CHECK (action IN ('ACCEPT', 'CHANGE_BERTH', 'DEFER')),
  previous_berth_id uuid REFERENCES berths(id) ON DELETE SET NULL,
  selected_berth_id uuid REFERENCES berths(id) ON DELETE SET NULL,
  operator_id text NOT NULL,
  note text,
  decided_at timestamptz NOT NULL,
  automated boolean NOT NULL DEFAULT false CHECK (automated = false)
);
CREATE INDEX IF NOT EXISTS idx_berth_decisions_assignment_time
  ON berth_assignment_decisions (berth_assignment_id, decided_at DESC);

CREATE TABLE IF NOT EXISTS port_queue_snapshots (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  port_id uuid NOT NULL REFERENCES maritime_ports(id) ON DELETE CASCADE,
  generated_at timestamptz NOT NULL,
  average_wait_minutes integer NOT NULL CHECK (average_wait_minutes >= 0),
  recalculation_reason text NOT NULL,
  model_version text NOT NULL,
  source_state jsonb NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS idx_port_queue_snapshots_port_time
  ON port_queue_snapshots (port_id, generated_at DESC);

CREATE TABLE IF NOT EXISTS port_queue_entries (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  snapshot_id uuid NOT NULL REFERENCES port_queue_snapshots(id) ON DELETE CASCADE,
  port_call_id uuid NOT NULL REFERENCES port_calls(id) ON DELETE CASCADE,
  berth_id uuid REFERENCES berths(id) ON DELETE SET NULL,
  queue_position integer NOT NULL CHECK (queue_position > 0),
  operational_priority integer NOT NULL CHECK (operational_priority BETWEEN 0 AND 100),
  expected_wait_minutes integer NOT NULL CHECK (expected_wait_minutes >= 0),
  expected_service_minutes integer NOT NULL CHECK (expected_service_minutes > 0),
  status text NOT NULL CHECK (status IN ('SCHEDULED', 'ATTENTION', 'WAITING', 'DEFERRED')),
  factors jsonb NOT NULL,
  UNIQUE (snapshot_id, queue_position),
  UNIQUE (snapshot_id, port_call_id)
);
CREATE INDEX IF NOT EXISTS idx_port_queue_entries_call
  ON port_queue_entries (port_call_id, snapshot_id);

CREATE TABLE IF NOT EXISTS service_operations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  port_call_id uuid NOT NULL REFERENCES port_calls(id) ON DELETE CASCADE,
  berth_id uuid NOT NULL REFERENCES berths(id) ON DELETE RESTRICT,
  operation_type text NOT NULL
    CHECK (operation_type IN ('CARGO_HANDLING', 'DOCUMENTATION', 'BUNKERING', 'INSPECTION', 'OTHER')),
  planned_start timestamptz,
  planned_end timestamptz,
  actual_start timestamptz,
  actual_end timestamptz,
  status text NOT NULL CHECK (status IN ('PLANNED', 'ACTIVE', 'DELAYED', 'COMPLETED', 'CANCELLED')),
  cargo_quantity_t numeric(14,3) CHECK (cargo_quantity_t >= 0),
  equipment jsonb NOT NULL DEFAULT '[]'::jsonb,
  source text NOT NULL,
  source_timestamp timestamptz NOT NULL,
  confidence numeric(5,4) NOT NULL CHECK (confidence BETWEEN 0 AND 1),
  verification_status text NOT NULL
    CHECK (verification_status IN ('REPORTED', 'ESTIMATED', 'VERIFIED')),
  CHECK (planned_start IS NULL OR planned_end IS NULL OR planned_end >= planned_start),
  CHECK (actual_start IS NULL OR actual_end IS NULL OR actual_end >= actual_start)
);
CREATE INDEX IF NOT EXISTS idx_service_operations_call_status
  ON service_operations (port_call_id, status, COALESCE(actual_start, planned_start));
CREATE INDEX IF NOT EXISTS idx_service_operations_berth_window
  ON service_operations (berth_id, COALESCE(actual_start, planned_start), COALESCE(actual_end, planned_end));

CREATE TABLE IF NOT EXISTS port_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  port_id uuid NOT NULL REFERENCES maritime_ports(id) ON DELETE CASCADE,
  port_call_id uuid REFERENCES port_calls(id) ON DELETE CASCADE,
  berth_id uuid REFERENCES berths(id) ON DELETE SET NULL,
  event_type text NOT NULL
    CHECK (event_type IN ('VESSEL_APPROACHING', 'ETA_CHANGED', 'VESSEL_ARRIVED', 'VESSEL_WAITING', 'BERTH_ASSIGNED', 'BERTH_CHANGED', 'SERVICE_STARTED', 'SERVICE_DELAYED', 'SERVICE_COMPLETED', 'VESSEL_DEPARTED', 'PORT_CONGESTION', 'WEATHER_RESTRICTION')),
  occurred_at timestamptz NOT NULL,
  status text NOT NULL CHECK (status IN ('ACTIVE', 'COMPLETED', 'CANCELLED')),
  severity text NOT NULL CHECK (severity IN ('INFO', 'WARNING', 'CRITICAL')),
  source text NOT NULL,
  source_timestamp timestamptz NOT NULL,
  confidence numeric(5,4) NOT NULL CHECK (confidence BETWEEN 0 AND 1),
  verification_status text NOT NULL
    CHECK (verification_status IN ('REPORTED', 'ESTIMATED', 'VERIFIED')),
  payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  explanation text NOT NULL,
  created_by text NOT NULL,
  automated boolean NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_port_events_port_time
  ON port_events (port_id, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_port_events_call_time
  ON port_events (port_call_id, occurred_at DESC)
  WHERE port_call_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_port_events_active
  ON port_events (port_id, event_type, occurred_at DESC)
  WHERE status = 'ACTIVE';

CREATE TABLE IF NOT EXISTS port_weather_observations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  port_id uuid NOT NULL REFERENCES maritime_ports(id) ON DELETE CASCADE,
  observed_at timestamptz NOT NULL,
  wind_mps numeric(6,2) NOT NULL CHECK (wind_mps >= 0),
  waves_m numeric(6,2) NOT NULL CHECK (waves_m >= 0),
  visibility_km numeric(8,2) NOT NULL CHECK (visibility_km >= 0),
  temperature_c numeric(6,2) NOT NULL,
  storm boolean NOT NULL DEFAULT false,
  source text NOT NULL,
  source_timestamp timestamptz NOT NULL,
  confidence numeric(5,4) NOT NULL CHECK (confidence BETWEEN 0 AND 1),
  verification_status text NOT NULL
    CHECK (verification_status IN ('REPORTED', 'ESTIMATED', 'VERIFIED'))
);
CREATE INDEX IF NOT EXISTS idx_port_weather_port_time
  ON port_weather_observations (port_id, observed_at DESC);

CREATE TABLE IF NOT EXISTS port_weather_restrictions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  port_id uuid NOT NULL REFERENCES maritime_ports(id) ON DELETE CASCADE,
  berth_id uuid REFERENCES berths(id) ON DELETE CASCADE,
  weather_observation_id uuid REFERENCES port_weather_observations(id) ON DELETE SET NULL,
  operation_status text NOT NULL CHECK (operation_status IN ('NORMAL', 'LIMITED', 'SUSPENDED')),
  reason text NOT NULL,
  processing_delay_minutes integer NOT NULL CHECK (processing_delay_minutes >= 0),
  started_at timestamptz NOT NULL,
  expected_end_at timestamptz,
  ended_at timestamptz,
  active boolean NOT NULL,
  CHECK (expected_end_at IS NULL OR expected_end_at >= started_at),
  CHECK (ended_at IS NULL OR ended_at >= started_at)
);
CREATE INDEX IF NOT EXISTS idx_port_weather_restrictions_active
  ON port_weather_restrictions (port_id, berth_id, started_at DESC)
  WHERE active = true;

CREATE TABLE IF NOT EXISTS port_load_forecasts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  port_id uuid NOT NULL REFERENCES maritime_ports(id) ON DELETE CASCADE,
  generated_at timestamptz NOT NULL,
  current_operational_utilization_percent integer NOT NULL
    CHECK (current_operational_utilization_percent BETWEEN 0 AND 100),
  metric_label text NOT NULL,
  model_version text NOT NULL,
  factors jsonb NOT NULL,
  explanation text NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_port_load_forecasts_port_time
  ON port_load_forecasts (port_id, generated_at DESC);

CREATE TABLE IF NOT EXISTS port_load_forecast_points (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  forecast_id uuid NOT NULL REFERENCES port_load_forecasts(id) ON DELETE CASCADE,
  horizon_hours integer NOT NULL CHECK (horizon_hours >= 0),
  forecast_at timestamptz NOT NULL,
  handling_pressure_percent integer NOT NULL CHECK (handling_pressure_percent BETWEEN 0 AND 100),
  confidence numeric(5,4) NOT NULL CHECK (confidence BETWEEN 0 AND 1),
  primary_driver text NOT NULL,
  UNIQUE (forecast_id, horizon_hours)
);
CREATE INDEX IF NOT EXISTS idx_port_load_points_time
  ON port_load_forecast_points (forecast_at, handling_pressure_percent DESC);

CREATE TABLE IF NOT EXISTS port_recommendations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  port_id uuid NOT NULL REFERENCES maritime_ports(id) ON DELETE CASCADE,
  port_call_id uuid REFERENCES port_calls(id) ON DELETE CASCADE,
  recommendation_type text NOT NULL
    CHECK (recommendation_type IN ('BERTH_MOVE', 'QUEUE_CHANGE', 'PREPARE_BERTH', 'REVIEW_ARRIVAL', 'WEATHER_ACTION')),
  action text NOT NULL,
  from_berth_id uuid REFERENCES berths(id) ON DELETE SET NULL,
  to_berth_id uuid REFERENCES berths(id) ON DELETE SET NULL,
  average_wait_change_minutes integer,
  load_before_percent integer CHECK (load_before_percent BETWEEN 0 AND 100),
  load_after_percent integer CHECK (load_after_percent BETWEEN 0 AND 100),
  confidence numeric(5,4) NOT NULL CHECK (confidence BETWEEN 0 AND 1),
  reasons jsonb NOT NULL,
  state text NOT NULL CHECK (state IN ('PENDING', 'ACCEPTED', 'CHANGED', 'DEFERRED', 'EXPIRED')),
  human_decision_required boolean NOT NULL DEFAULT true CHECK (human_decision_required = true),
  generated_at timestamptz NOT NULL,
  decided_by text,
  decided_at timestamptz,
  decision_note text
);
CREATE INDEX IF NOT EXISTS idx_port_recommendations_pending
  ON port_recommendations (port_id, generated_at DESC)
  WHERE state = 'PENDING';

CREATE TABLE IF NOT EXISTS simulation_runs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  port_id uuid NOT NULL REFERENCES maritime_ports(id) ON DELETE CASCADE,
  scenario_type text NOT NULL
    CHECK (scenario_type IN ('VESSEL_DELAY', 'BERTH_UNAVAILABLE', 'SERVICE_EXTENSION', 'NEW_VESSEL_ARRIVAL')),
  input_parameters jsonb NOT NULL,
  baseline_snapshot jsonb NOT NULL,
  simulated_snapshot jsonb NOT NULL,
  baseline_average_wait_minutes integer NOT NULL CHECK (baseline_average_wait_minutes >= 0),
  simulated_average_wait_minutes integer NOT NULL CHECK (simulated_average_wait_minutes >= 0),
  baseline_peak_load_percent integer NOT NULL CHECK (baseline_peak_load_percent BETWEEN 0 AND 100),
  simulated_peak_load_percent integer NOT NULL CHECK (simulated_peak_load_percent BETWEEN 0 AND 100),
  affected_vessel_ids uuid[] NOT NULL DEFAULT '{}',
  generated_at timestamptz NOT NULL,
  requested_by text NOT NULL,
  state_changed boolean NOT NULL DEFAULT false CHECK (state_changed = false),
  model_version text NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_simulation_runs_port_time
  ON simulation_runs (port_id, generated_at DESC);

CREATE TABLE IF NOT EXISTS simulation_impacts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  simulation_run_id uuid NOT NULL REFERENCES simulation_runs(id) ON DELETE CASCADE,
  impact_type text NOT NULL
    CHECK (impact_type IN ('WAITING_TIME', 'BERTH_CONGESTION', 'PORT_LOAD', 'QUEUE_ORDER', 'VESSEL_EFFECT')),
  baseline_value numeric,
  simulated_value numeric,
  unit text,
  explanation text NOT NULL,
  recommendation text
);
CREATE INDEX IF NOT EXISTS idx_simulation_impacts_run
  ON simulation_impacts (simulation_run_id, impact_type);

CREATE TABLE IF NOT EXISTS port_feedback_records (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  port_call_id uuid NOT NULL UNIQUE REFERENCES port_calls(id) ON DELETE CASCADE,
  vessel_id uuid NOT NULL REFERENCES vessels(id) ON DELETE RESTRICT,
  voyage_id uuid REFERENCES voyages(id) ON DELETE SET NULL,
  recorded_at timestamptz NOT NULL,
  recorded_by text NOT NULL,
  eta_error_minutes integer,
  predicted_service_minutes integer CHECK (predicted_service_minutes >= 0),
  actual_service_minutes integer CHECK (actual_service_minutes >= 0),
  service_error_minutes integer,
  documents_verified boolean,
  intelligence_update_targets jsonb NOT NULL,
  emitted_event_ids uuid[] NOT NULL DEFAULT '{}',
  closed_loop_complete boolean NOT NULL DEFAULT false,
  explanation text NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_port_feedback_vessel_time
  ON port_feedback_records (vessel_id, recorded_at DESC);

CREATE TABLE IF NOT EXISTS port_feedback_observations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  feedback_record_id uuid NOT NULL REFERENCES port_feedback_records(id) ON DELETE CASCADE,
  metric_key text NOT NULL CHECK (metric_key IN ('CARGO_MASS', 'DRAUGHT', 'ACTUAL_ARRIVAL', 'SERVICE_DURATION', 'DOCUMENT_STATUS')),
  numeric_value numeric,
  text_value text,
  unit text,
  source text NOT NULL,
  source_timestamp timestamptz NOT NULL,
  confidence numeric(5,4) NOT NULL CHECK (confidence BETWEEN 0 AND 1),
  verification_status text NOT NULL
    CHECK (verification_status IN ('REPORTED', 'ESTIMATED', 'VERIFIED')),
  CHECK (num_nonnulls(numeric_value, text_value) = 1)
);
CREATE INDEX IF NOT EXISTS idx_port_feedback_observations_record_metric
  ON port_feedback_observations (feedback_record_id, metric_key, verification_status);

CREATE TABLE IF NOT EXISTS risk_factor_reviews (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  factor_id uuid NOT NULL REFERENCES risk_factors(id) ON DELETE CASCADE,
  review_status text NOT NULL CHECK (review_status IN ('confirmed_relevant', 'normal_operation', 'false_positive', 'needs_more_data')),
  reviewed_by text NOT NULL,
  comment text,
  reviewed_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_risk_factor_reviews_factor_time
  ON risk_factor_reviews (factor_id, reviewed_at DESC);
CREATE INDEX IF NOT EXISTS idx_risk_factor_reviews_analyst_time
  ON risk_factor_reviews (reviewed_by, reviewed_at DESC);

CREATE TABLE IF NOT EXISTS risk_notifications (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  vessel_id uuid NOT NULL REFERENCES vessels(id) ON DELETE CASCADE,
  assessment_id uuid REFERENCES risk_assessments(id) ON DELETE SET NULL,
  factor_id uuid REFERENCES risk_factors(id) ON DELETE SET NULL,
  notification_type text NOT NULL CHECK (notification_type IN ('level_transition', 'rapid_increase', 'critical_factor')),
  previous_score smallint CHECK (previous_score BETWEEN 0 AND 100),
  current_score smallint NOT NULL CHECK (current_score BETWEEN 0 AND 100),
  previous_level text CHECK (previous_level IN ('low', 'moderate', 'high', 'critical')),
  current_level text NOT NULL CHECK (current_level IN ('low', 'moderate', 'high', 'critical')),
  reason text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  read_at timestamptz
);
CREATE INDEX IF NOT EXISTS idx_risk_notifications_unread
  ON risk_notifications (created_at DESC) WHERE read_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_risk_notifications_vessel_time
  ON risk_notifications (vessel_id, created_at DESC);

-- Stage 6: Advanced Analytics. These tables preserve the distinction between
-- reported facts, model estimates and independently verified observations.

CREATE TABLE IF NOT EXISTS companies (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  legal_name text NOT NULL,
  registration_number text,
  jurisdiction_code varchar(3),
  company_type text NOT NULL DEFAULT 'shipping'
    CHECK (company_type IN ('shipping', 'owner', 'operator', 'manager', 'shipper', 'consignee', 'other')),
  status text NOT NULL DEFAULT 'active'
    CHECK (status IN ('active', 'inactive', 'unknown')),
  source text NOT NULL,
  source_timestamp timestamptz NOT NULL,
  confidence numeric(5,4) NOT NULL CHECK (confidence BETWEEN 0 AND 1),
  verification_status text NOT NULL
    CHECK (verification_status IN ('REPORTED', 'ESTIMATED', 'VERIFIED')),
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_companies_registry_identity
  ON companies (jurisdiction_code, registration_number)
  WHERE registration_number IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_companies_name
  ON companies (lower(legal_name));

CREATE TABLE IF NOT EXISTS company_aliases (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id uuid NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
  alias text NOT NULL,
  source text NOT NULL,
  source_timestamp timestamptz NOT NULL,
  confidence numeric(5,4) NOT NULL CHECK (confidence BETWEEN 0 AND 1),
  verification_status text NOT NULL
    CHECK (verification_status IN ('REPORTED', 'ESTIMATED', 'VERIFIED')),
  UNIQUE (company_id, alias)
);
CREATE INDEX IF NOT EXISTS idx_company_aliases_name
  ON company_aliases (lower(alias));

CREATE TABLE IF NOT EXISTS vessel_company_relationships (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  vessel_id uuid NOT NULL REFERENCES vessels(id) ON DELETE CASCADE,
  company_id uuid NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
  relationship_role text NOT NULL
    CHECK (relationship_role IN ('OWNER', 'OPERATOR', 'MANAGER', 'BAREBOAT_CHARTERER', 'OTHER')),
  ownership_share_pct numeric(5,2) CHECK (ownership_share_pct BETWEEN 0 AND 100),
  valid_from timestamptz,
  valid_to timestamptz,
  source text NOT NULL,
  source_timestamp timestamptz NOT NULL,
  confidence numeric(5,4) NOT NULL CHECK (confidence BETWEEN 0 AND 1),
  verification_status text NOT NULL
    CHECK (verification_status IN ('REPORTED', 'ESTIMATED', 'VERIFIED')),
  evidence jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  CHECK (valid_to IS NULL OR valid_from IS NULL OR valid_to > valid_from)
);
CREATE INDEX IF NOT EXISTS idx_vessel_company_vessel_role
  ON vessel_company_relationships (vessel_id, relationship_role, valid_to);
CREATE INDEX IF NOT EXISTS idx_vessel_company_company_role
  ON vessel_company_relationships (company_id, relationship_role, valid_to);
CREATE UNIQUE INDEX IF NOT EXISTS idx_vessel_company_current_unique
  ON vessel_company_relationships (vessel_id, company_id, relationship_role)
  WHERE valid_to IS NULL;

CREATE TABLE IF NOT EXISTS company_relationships (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  from_company_id uuid NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
  to_company_id uuid NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
  relationship_type text NOT NULL
    CHECK (relationship_type IN ('PARENT_OF', 'SUBSIDIARY_OF', 'AFFILIATED_WITH', 'MANAGED_BY', 'RELATED_TO')),
  valid_from timestamptz,
  valid_to timestamptz,
  explanation text NOT NULL,
  source text NOT NULL,
  source_timestamp timestamptz NOT NULL,
  confidence numeric(5,4) NOT NULL CHECK (confidence BETWEEN 0 AND 1),
  verification_status text NOT NULL
    CHECK (verification_status IN ('REPORTED', 'ESTIMATED', 'VERIFIED')),
  evidence jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  CHECK (from_company_id <> to_company_id),
  CHECK (valid_to IS NULL OR valid_from IS NULL OR valid_to > valid_from)
);
CREATE INDEX IF NOT EXISTS idx_company_relationships_from
  ON company_relationships (from_company_id, valid_to);
CREATE INDEX IF NOT EXISTS idx_company_relationships_to
  ON company_relationships (to_company_id, valid_to);

CREATE TABLE IF NOT EXISTS analytical_observations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  vessel_id uuid REFERENCES vessels(id) ON DELETE CASCADE,
  voyage_id uuid REFERENCES voyages(id) ON DELETE CASCADE,
  company_id uuid REFERENCES companies(id) ON DELETE CASCADE,
  subject_type text NOT NULL
    CHECK (subject_type IN ('VESSEL', 'VOYAGE', 'CARGO', 'DRAUGHT', 'FUEL', 'ECONOMICS', 'WEATHER', 'CONNECTION', 'COMPANY')),
  metric_key text NOT NULL,
  numeric_value numeric,
  text_value text,
  structured_value jsonb,
  unit text,
  observed_at timestamptz NOT NULL,
  source text NOT NULL,
  source_timestamp timestamptz NOT NULL,
  confidence numeric(5,4) NOT NULL CHECK (confidence BETWEEN 0 AND 1),
  verification_status text NOT NULL
    CHECK (verification_status IN ('REPORTED', 'ESTIMATED', 'VERIFIED')),
  context jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  CHECK (num_nonnulls(numeric_value, text_value, structured_value) = 1),
  CHECK (vessel_id IS NOT NULL OR voyage_id IS NOT NULL OR company_id IS NOT NULL),
  CHECK ((subject_type = 'COMPANY') = (company_id IS NOT NULL))
);
CREATE INDEX IF NOT EXISTS idx_analytical_observations_voyage_time
  ON analytical_observations (voyage_id, observed_at DESC)
  WHERE voyage_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_analytical_observations_vessel_metric
  ON analytical_observations (vessel_id, metric_key, observed_at DESC)
  WHERE vessel_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_analytical_observations_context
  ON analytical_observations USING gin (context);

CREATE TABLE IF NOT EXISTS cargo_declarations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  declaration_reference text NOT NULL,
  vessel_id uuid NOT NULL REFERENCES vessels(id) ON DELETE CASCADE,
  voyage_id uuid NOT NULL REFERENCES voyages(id) ON DELETE CASCADE,
  origin_port_id uuid REFERENCES maritime_ports(id) ON DELETE SET NULL,
  destination_port_id uuid REFERENCES maritime_ports(id) ON DELETE SET NULL,
  shipper_company_id uuid REFERENCES companies(id) ON DELETE SET NULL,
  consignee_company_id uuid REFERENCES companies(id) ON DELETE SET NULL,
  document_reference text,
  issued_at timestamptz,
  loaded_at timestamptz,
  unloaded_at timestamptz,
  declaration_status text NOT NULL DEFAULT 'ACTIVE'
    CHECK (declaration_status IN ('DRAFT', 'ACTIVE', 'AMENDED', 'CANCELLED', 'COMPLETED')),
  source text NOT NULL,
  source_timestamp timestamptz NOT NULL,
  confidence numeric(5,4) NOT NULL CHECK (confidence BETWEEN 0 AND 1),
  verification_status text NOT NULL
    CHECK (verification_status IN ('REPORTED', 'ESTIMATED', 'VERIFIED')),
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (source, declaration_reference),
  CHECK (unloaded_at IS NULL OR loaded_at IS NULL OR unloaded_at >= loaded_at)
);
CREATE INDEX IF NOT EXISTS idx_cargo_declarations_voyage
  ON cargo_declarations (voyage_id, source_timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_cargo_declarations_vessel
  ON cargo_declarations (vessel_id, source_timestamp DESC);

CREATE TABLE IF NOT EXISTS cargo_declaration_items (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  declaration_id uuid NOT NULL REFERENCES cargo_declarations(id) ON DELETE CASCADE,
  line_number integer NOT NULL CHECK (line_number > 0),
  cargo_type text NOT NULL,
  cargo_name text NOT NULL,
  declared_mass_t numeric CHECK (declared_mass_t >= 0),
  declared_volume_m3 numeric CHECK (declared_volume_m3 >= 0),
  declared_value numeric CHECK (declared_value >= 0),
  currency varchar(3) CHECK (currency ~ '^[A-Z]{3}$'),
  dangerous_goods_code text,
  package_count integer CHECK (package_count >= 0),
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  UNIQUE (declaration_id, line_number),
  UNIQUE (id, declaration_id),
  CHECK (declared_mass_t IS NOT NULL OR declared_volume_m3 IS NOT NULL)
);
CREATE INDEX IF NOT EXISTS idx_cargo_items_type
  ON cargo_declaration_items (cargo_type);

CREATE TABLE IF NOT EXISTS cargo_timeline_entries (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  declaration_id uuid NOT NULL REFERENCES cargo_declarations(id) ON DELETE CASCADE,
  cargo_item_id uuid,
  vessel_id uuid NOT NULL REFERENCES vessels(id) ON DELETE CASCADE,
  voyage_id uuid NOT NULL REFERENCES voyages(id) ON DELETE CASCADE,
  operation_type text NOT NULL
    CHECK (operation_type IN ('DECLARED', 'LOADED', 'UNLOADED', 'CORRECTED', 'CANCELLED', 'INSPECTED')),
  mass_delta_t numeric,
  volume_delta_m3 numeric,
  port_id uuid REFERENCES maritime_ports(id) ON DELETE SET NULL,
  occurred_at timestamptz NOT NULL,
  location geography(Point, 4326),
  source text NOT NULL,
  source_timestamp timestamptz NOT NULL,
  confidence numeric(5,4) NOT NULL CHECK (confidence BETWEEN 0 AND 1),
  verification_status text NOT NULL
    CHECK (verification_status IN ('REPORTED', 'ESTIMATED', 'VERIFIED')),
  evidence jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY (cargo_item_id, declaration_id)
    REFERENCES cargo_declaration_items(id, declaration_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_cargo_timeline_voyage_time
  ON cargo_timeline_entries (voyage_id, occurred_at);
CREATE INDEX IF NOT EXISTS idx_cargo_timeline_declaration_time
  ON cargo_timeline_entries (declaration_id, occurred_at);
CREATE INDEX IF NOT EXISTS idx_cargo_timeline_location
  ON cargo_timeline_entries USING gist (location);

CREATE TABLE IF NOT EXISTS vessel_cargo_profiles (
  vessel_id uuid NOT NULL REFERENCES vessels(id) ON DELETE CASCADE,
  cargo_type text NOT NULL,
  operation_count integer NOT NULL CHECK (operation_count >= 0),
  cargo_share numeric(5,4) NOT NULL CHECK (cargo_share BETWEEN 0 AND 1),
  typical_mass_min_t numeric CHECK (typical_mass_min_t >= 0),
  typical_mass_max_t numeric CHECK (typical_mass_max_t >= 0),
  observation_started_at timestamptz,
  observation_ended_at timestamptz,
  source text NOT NULL,
  source_timestamp timestamptz NOT NULL,
  confidence numeric(5,4) NOT NULL CHECK (confidence BETWEEN 0 AND 1),
  verification_status text NOT NULL DEFAULT 'ESTIMATED'
    CHECK (verification_status IN ('REPORTED', 'ESTIMATED', 'VERIFIED')),
  model_version text NOT NULL,
  updated_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (vessel_id, cargo_type),
  CHECK (typical_mass_max_t IS NULL OR typical_mass_min_t IS NULL OR typical_mass_max_t >= typical_mass_min_t),
  CHECK (observation_ended_at IS NULL OR observation_started_at IS NULL OR observation_ended_at >= observation_started_at)
);

CREATE TABLE IF NOT EXISTS route_cargo_profiles (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  origin_port_id uuid NOT NULL REFERENCES maritime_ports(id) ON DELETE CASCADE,
  destination_port_id uuid NOT NULL REFERENCES maritime_ports(id) ON DELETE CASCADE,
  cargo_type text NOT NULL,
  operation_count integer NOT NULL CHECK (operation_count >= 0),
  cargo_share numeric(5,4) NOT NULL CHECK (cargo_share BETWEEN 0 AND 1),
  source text NOT NULL,
  source_timestamp timestamptz NOT NULL,
  confidence numeric(5,4) NOT NULL CHECK (confidence BETWEEN 0 AND 1),
  verification_status text NOT NULL DEFAULT 'ESTIMATED'
    CHECK (verification_status IN ('REPORTED', 'ESTIMATED', 'VERIFIED')),
  model_version text NOT NULL,
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (origin_port_id, destination_port_id, cargo_type)
);

CREATE TABLE IF NOT EXISTS vessel_draught_models (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  vessel_id uuid NOT NULL REFERENCES vessels(id) ON DELETE CASCADE,
  model_version text NOT NULL,
  model_type text NOT NULL DEFAULT 'VESSEL_SPECIFIC'
    CHECK (model_type = 'VESSEL_SPECIFIC'),
  draught_change_min_m_per_1000t numeric NOT NULL CHECK (draught_change_min_m_per_1000t > 0),
  draught_change_max_m_per_1000t numeric NOT NULL CHECK (draught_change_max_m_per_1000t > 0),
  historical_operation_count integer NOT NULL CHECK (historical_operation_count >= 0),
  trained_from timestamptz,
  trained_to timestamptz,
  confidence numeric(5,4) NOT NULL CHECK (confidence BETWEEN 0 AND 1),
  verification_status text NOT NULL DEFAULT 'ESTIMATED'
    CHECK (verification_status IN ('REPORTED', 'ESTIMATED', 'VERIFIED')),
  source text NOT NULL,
  source_timestamp timestamptz NOT NULL,
  parameters jsonb NOT NULL DEFAULT '{}'::jsonb,
  is_current boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  CHECK (draught_change_max_m_per_1000t >= draught_change_min_m_per_1000t),
  CHECK (trained_to IS NULL OR trained_from IS NULL OR trained_to >= trained_from),
  UNIQUE (vessel_id, model_version)
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_draught_models_current
  ON vessel_draught_models (vessel_id) WHERE is_current;

CREATE TABLE IF NOT EXISTS draught_observations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  vessel_id uuid NOT NULL REFERENCES vessels(id) ON DELETE CASCADE,
  voyage_id uuid REFERENCES voyages(id) ON DELETE CASCADE,
  draught_m numeric NOT NULL CHECK (draught_m > 0),
  observation_kind text NOT NULL
    CHECK (observation_kind IN ('DEPARTURE', 'ARRIVAL', 'IN_TRANSIT', 'CARGO_OPERATION', 'OTHER')),
  observed_at timestamptz NOT NULL,
  source text NOT NULL,
  source_timestamp timestamptz NOT NULL,
  confidence numeric(5,4) NOT NULL CHECK (confidence BETWEEN 0 AND 1),
  verification_status text NOT NULL
    CHECK (verification_status IN ('REPORTED', 'ESTIMATED', 'VERIFIED')),
  position geography(Point, 4326),
  evidence jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_draught_observations_vessel_time
  ON draught_observations (vessel_id, observed_at DESC);
CREATE INDEX IF NOT EXISTS idx_draught_observations_voyage_time
  ON draught_observations (voyage_id, observed_at)
  WHERE voyage_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS cargo_draught_assessments (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  vessel_id uuid NOT NULL REFERENCES vessels(id) ON DELETE CASCADE,
  voyage_id uuid NOT NULL REFERENCES voyages(id) ON DELETE CASCADE,
  declaration_id uuid REFERENCES cargo_declarations(id) ON DELETE SET NULL,
  draught_model_id uuid NOT NULL REFERENCES vessel_draught_models(id),
  before_observation_id uuid REFERENCES draught_observations(id) ON DELETE SET NULL,
  after_observation_id uuid REFERENCES draught_observations(id) ON DELETE SET NULL,
  declared_mass_change_t numeric NOT NULL,
  expected_change_min_m numeric NOT NULL CHECK (expected_change_min_m >= 0),
  expected_change_max_m numeric NOT NULL CHECK (expected_change_max_m >= 0),
  observed_change_m numeric NOT NULL,
  deviation_from_expected_m numeric NOT NULL,
  assessment_status text NOT NULL
    CHECK (assessment_status IN ('CONSISTENT', 'CARGO_DRAUGHT_MISMATCH', 'UNEXPLAINED_LOAD_CHANGE', 'INSUFFICIENT_DATA')),
  confidence numeric(5,4) NOT NULL CHECK (confidence BETWEEN 0 AND 1),
  verification_status text NOT NULL DEFAULT 'ESTIMATED'
    CHECK (verification_status IN ('REPORTED', 'ESTIMATED', 'VERIFIED')),
  source text NOT NULL,
  source_timestamp timestamptz NOT NULL,
  explanation text NOT NULL,
  calculation_inputs jsonb NOT NULL DEFAULT '{}'::jsonb,
  model_version text NOT NULL,
  calculated_at timestamptz NOT NULL DEFAULT now(),
  CHECK (expected_change_max_m >= expected_change_min_m)
);
CREATE INDEX IF NOT EXISTS idx_cargo_draught_voyage_time
  ON cargo_draught_assessments (voyage_id, calculated_at DESC);
CREATE INDEX IF NOT EXISTS idx_cargo_draught_anomalies
  ON cargo_draught_assessments (assessment_status, calculated_at DESC)
  WHERE assessment_status IN ('CARGO_DRAUGHT_MISMATCH', 'UNEXPLAINED_LOAD_CHANGE');

CREATE TABLE IF NOT EXISTS vessel_fuel_profiles (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  vessel_id uuid NOT NULL REFERENCES vessels(id) ON DELETE CASCADE,
  route_profile_id uuid REFERENCES vessel_route_profiles(id) ON DELETE SET NULL,
  engine_model text,
  fuel_type text,
  typical_consumption_min_t numeric NOT NULL CHECK (typical_consumption_min_t >= 0),
  typical_consumption_max_t numeric NOT NULL CHECK (typical_consumption_max_t >= 0),
  typical_speed_min_kn numeric CHECK (typical_speed_min_kn >= 0),
  typical_speed_max_kn numeric CHECK (typical_speed_max_kn >= 0),
  voyage_sample_count integer NOT NULL CHECK (voyage_sample_count >= 0),
  confidence numeric(5,4) NOT NULL CHECK (confidence BETWEEN 0 AND 1),
  verification_status text NOT NULL DEFAULT 'ESTIMATED'
    CHECK (verification_status IN ('REPORTED', 'ESTIMATED', 'VERIFIED')),
  source text NOT NULL,
  source_timestamp timestamptz NOT NULL,
  model_version text NOT NULL,
  parameters jsonb NOT NULL DEFAULT '{}'::jsonb,
  is_current boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  CHECK (typical_consumption_max_t >= typical_consumption_min_t),
  CHECK (typical_speed_max_kn IS NULL OR typical_speed_min_kn IS NULL OR typical_speed_max_kn >= typical_speed_min_kn),
  UNIQUE (vessel_id, route_profile_id, model_version)
);
CREATE INDEX IF NOT EXISTS idx_fuel_profiles_vessel_current
  ON vessel_fuel_profiles (vessel_id, is_current, created_at DESC);
CREATE UNIQUE INDEX IF NOT EXISTS idx_fuel_profiles_current_vessel_default
  ON vessel_fuel_profiles (vessel_id)
  WHERE is_current AND route_profile_id IS NULL;
CREATE UNIQUE INDEX IF NOT EXISTS idx_fuel_profiles_current_vessel_route
  ON vessel_fuel_profiles (vessel_id, route_profile_id)
  WHERE is_current AND route_profile_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS voyage_environment_observations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  voyage_id uuid NOT NULL REFERENCES voyages(id) ON DELETE CASCADE,
  observed_at timestamptz NOT NULL,
  wind_speed_kn numeric CHECK (wind_speed_kn >= 0),
  wind_direction_deg numeric CHECK (wind_direction_deg BETWEEN 0 AND 360),
  wave_height_m numeric CHECK (wave_height_m >= 0),
  current_speed_kn numeric CHECK (current_speed_kn >= 0),
  current_direction_deg numeric CHECK (current_direction_deg BETWEEN 0 AND 360),
  source text NOT NULL,
  source_timestamp timestamptz NOT NULL,
  confidence numeric(5,4) NOT NULL CHECK (confidence BETWEEN 0 AND 1),
  verification_status text NOT NULL
    CHECK (verification_status IN ('REPORTED', 'ESTIMATED', 'VERIFIED')),
  position geography(Point, 4326),
  raw_payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  CHECK (num_nonnulls(wind_speed_kn, wave_height_m, current_speed_kn) >= 1)
);
CREATE INDEX IF NOT EXISTS idx_environment_voyage_time
  ON voyage_environment_observations (voyage_id, observed_at);

CREATE TABLE IF NOT EXISTS voyage_fuel_assessments (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  vessel_id uuid NOT NULL REFERENCES vessels(id) ON DELETE CASCADE,
  voyage_id uuid NOT NULL REFERENCES voyages(id) ON DELETE CASCADE,
  fuel_profile_id uuid REFERENCES vessel_fuel_profiles(id) ON DELETE SET NULL,
  expected_fuel_min_t numeric NOT NULL CHECK (expected_fuel_min_t >= 0),
  expected_fuel_max_t numeric NOT NULL CHECK (expected_fuel_max_t >= 0),
  actual_observation_id uuid REFERENCES analytical_observations(id) ON DELETE SET NULL,
  reported_or_observed_fuel_t numeric CHECK (reported_or_observed_fuel_t >= 0),
  actual_value_status text
    CHECK (actual_value_status IN ('REPORTED', 'ESTIMATED', 'VERIFIED')),
  weather_correction_t numeric NOT NULL DEFAULT 0,
  operational_correction_t numeric NOT NULL DEFAULT 0,
  deviation_from_upper_pct numeric,
  assessment_status text NOT NULL
    CHECK (assessment_status IN ('EXPECTED', 'FUEL_ANOMALY', 'INSUFFICIENT_DATA')),
  confidence numeric(5,4) NOT NULL CHECK (confidence BETWEEN 0 AND 1),
  verification_status text NOT NULL DEFAULT 'ESTIMATED'
    CHECK (verification_status IN ('REPORTED', 'ESTIMATED', 'VERIFIED')),
  source text NOT NULL,
  source_timestamp timestamptz NOT NULL,
  explanation text NOT NULL,
  calculation_inputs jsonb NOT NULL DEFAULT '{}'::jsonb,
  model_version text NOT NULL,
  calculated_at timestamptz NOT NULL DEFAULT now(),
  is_current boolean NOT NULL DEFAULT true,
  CHECK (expected_fuel_max_t >= expected_fuel_min_t),
  CHECK ((reported_or_observed_fuel_t IS NULL) = (actual_value_status IS NULL))
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_voyage_fuel_current
  ON voyage_fuel_assessments (voyage_id) WHERE is_current;
CREATE INDEX IF NOT EXISTS idx_voyage_fuel_anomalies
  ON voyage_fuel_assessments (assessment_status, calculated_at DESC)
  WHERE assessment_status = 'FUEL_ANOMALY';

CREATE TABLE IF NOT EXISTS voyage_economic_assessments (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  vessel_id uuid NOT NULL REFERENCES vessels(id) ON DELETE CASCADE,
  voyage_id uuid NOT NULL REFERENCES voyages(id) ON DELETE CASCADE,
  cargo_declared_value numeric CHECK (cargo_declared_value >= 0),
  fuel_cost numeric NOT NULL DEFAULT 0 CHECK (fuel_cost >= 0),
  port_fees numeric NOT NULL DEFAULT 0 CHECK (port_fees >= 0),
  crew_cost numeric NOT NULL DEFAULT 0 CHECK (crew_cost >= 0),
  handling_cost numeric NOT NULL DEFAULT 0 CHECK (handling_cost >= 0),
  operating_cost numeric NOT NULL DEFAULT 0 CHECK (operating_cost >= 0),
  estimated_voyage_cost numeric NOT NULL CHECK (estimated_voyage_cost >= 0),
  currency varchar(3) NOT NULL CHECK (currency ~ '^[A-Z]{3}$'),
  value_to_cost_ratio numeric CHECK (value_to_cost_ratio >= 0),
  typical_ratio_min numeric CHECK (typical_ratio_min >= 0),
  typical_ratio_max numeric CHECK (typical_ratio_max >= 0),
  assessment_status text NOT NULL
    CHECK (assessment_status IN ('CONSISTENT', 'ECONOMIC_ANOMALY', 'INSUFFICIENT_DATA')),
  confidence numeric(5,4) NOT NULL CHECK (confidence BETWEEN 0 AND 1),
  verification_status text NOT NULL DEFAULT 'ESTIMATED'
    CHECK (verification_status IN ('REPORTED', 'ESTIMATED', 'VERIFIED')),
  source text NOT NULL,
  source_timestamp timestamptz NOT NULL,
  explanation text NOT NULL,
  calculation_inputs jsonb NOT NULL DEFAULT '{}'::jsonb,
  model_version text NOT NULL,
  calculated_at timestamptz NOT NULL DEFAULT now(),
  is_current boolean NOT NULL DEFAULT true,
  CHECK (typical_ratio_max IS NULL OR typical_ratio_min IS NULL OR typical_ratio_max >= typical_ratio_min)
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_voyage_economics_current
  ON voyage_economic_assessments (voyage_id) WHERE is_current;
CREATE INDEX IF NOT EXISTS idx_voyage_economic_anomalies
  ON voyage_economic_assessments (assessment_status, calculated_at DESC)
  WHERE assessment_status = 'ECONOMIC_ANOMALY';

CREATE TABLE IF NOT EXISTS advanced_analytical_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  event_code text UNIQUE NOT NULL,
  event_type text NOT NULL
    CHECK (event_type IN ('CARGO_ANOMALY', 'CARGO_DRAUGHT_MISMATCH', 'FUEL_ANOMALY', 'ECONOMIC_ANOMALY', 'UNUSUAL_CONNECTION', 'UNEXPLAINED_LOAD_CHANGE')),
  vessel_id uuid NOT NULL REFERENCES vessels(id) ON DELETE CASCADE,
  voyage_id uuid REFERENCES voyages(id) ON DELETE CASCADE,
  related_vessel_id uuid REFERENCES vessels(id) ON DELETE SET NULL,
  severity text NOT NULL CHECK (severity IN ('low', 'medium', 'high')),
  status text NOT NULL DEFAULT 'active'
    CHECK (status IN ('active', 'resolved', 'reviewed', 'dismissed')),
  started_at timestamptz NOT NULL,
  ended_at timestamptz,
  source text NOT NULL,
  source_timestamp timestamptz NOT NULL,
  confidence numeric(5,4) NOT NULL CHECK (confidence BETWEEN 0 AND 1),
  verification_status text NOT NULL DEFAULT 'ESTIMATED'
    CHECK (verification_status IN ('REPORTED', 'ESTIMATED', 'VERIFIED')),
  explanation text NOT NULL,
  evidence_summary jsonb NOT NULL DEFAULT '{}'::jsonb,
  detector_version text NOT NULL,
  reviewed_by text,
  review_note text,
  reviewed_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CHECK (ended_at IS NULL OR ended_at >= started_at),
  CHECK (related_vessel_id IS NULL OR related_vessel_id <> vessel_id)
);
CREATE INDEX IF NOT EXISTS idx_advanced_events_vessel_time
  ON advanced_analytical_events (vessel_id, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_advanced_events_voyage_type
  ON advanced_analytical_events (voyage_id, event_type, started_at DESC)
  WHERE voyage_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_advanced_events_status_severity
  ON advanced_analytical_events (status, severity, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_advanced_events_evidence
  ON advanced_analytical_events USING gin (evidence_summary);

CREATE TABLE IF NOT EXISTS analytical_event_evidence (
  analytical_event_id uuid NOT NULL REFERENCES advanced_analytical_events(id) ON DELETE CASCADE,
  observation_id uuid NOT NULL REFERENCES analytical_observations(id) ON DELETE CASCADE,
  evidence_role text NOT NULL
    CHECK (evidence_role IN ('INPUT', 'CONTEXT', 'CORRECTION', 'COUNTER_EVIDENCE')),
  explanation text NOT NULL,
  contribution numeric(6,3),
  PRIMARY KEY (analytical_event_id, observation_id)
);
CREATE INDEX IF NOT EXISTS idx_analytical_event_evidence_observation
  ON analytical_event_evidence (observation_id);

CREATE TABLE IF NOT EXISTS vessel_connection_aggregates (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  vessel_a_id uuid NOT NULL REFERENCES vessels(id) ON DELETE CASCADE,
  vessel_b_id uuid NOT NULL REFERENCES vessels(id) ON DELETE CASCADE,
  observation_started_at timestamptz NOT NULL,
  observation_ended_at timestamptz NOT NULL,
  encounter_count integer NOT NULL CHECK (encounter_count >= 0),
  encounters_last_6_months integer NOT NULL CHECK (encounters_last_6_months >= 0),
  open_sea_count integer NOT NULL CHECK (open_sea_count >= 0),
  port_count integer NOT NULL CHECK (port_count >= 0),
  total_duration_seconds bigint NOT NULL CHECK (total_duration_seconds >= 0),
  average_duration_seconds bigint CHECK (average_duration_seconds >= 0),
  average_distance_m numeric CHECK (average_distance_m >= 0),
  connection_strength text NOT NULL
    CHECK (connection_strength IN ('LOW', 'MODERATE', 'HIGH')),
  source text NOT NULL,
  source_timestamp timestamptz NOT NULL,
  confidence numeric(5,4) NOT NULL CHECK (confidence BETWEEN 0 AND 1),
  verification_status text NOT NULL DEFAULT 'ESTIMATED'
    CHECK (verification_status IN ('REPORTED', 'ESTIMATED', 'VERIFIED')),
  explanation text NOT NULL,
  evidence jsonb NOT NULL DEFAULT '{}'::jsonb,
  model_version text NOT NULL,
  updated_at timestamptz NOT NULL DEFAULT now(),
  CHECK (vessel_a_id < vessel_b_id),
  CHECK (observation_ended_at >= observation_started_at),
  UNIQUE (vessel_a_id, vessel_b_id, model_version)
);
CREATE INDEX IF NOT EXISTS idx_connection_aggregates_strength
  ON vessel_connection_aggregates (connection_strength, encounter_count DESC);

CREATE TABLE IF NOT EXISTS intelligence_graph_nodes (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  node_type text NOT NULL
    CHECK (node_type IN ('VESSEL', 'COMPANY', 'OWNER', 'OPERATOR', 'PORT', 'CARGO', 'VOYAGE')),
  entity_key text UNIQUE NOT NULL,
  label text NOT NULL,
  vessel_id uuid REFERENCES vessels(id) ON DELETE CASCADE,
  company_id uuid REFERENCES companies(id) ON DELETE CASCADE,
  port_id uuid REFERENCES maritime_ports(id) ON DELETE CASCADE,
  cargo_declaration_id uuid REFERENCES cargo_declarations(id) ON DELETE CASCADE,
  voyage_id uuid REFERENCES voyages(id) ON DELETE CASCADE,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CHECK (num_nonnulls(vessel_id, company_id, port_id, cargo_declaration_id, voyage_id) = 1),
  CHECK ((node_type = 'VESSEL') = (vessel_id IS NOT NULL)),
  CHECK ((node_type IN ('COMPANY', 'OWNER', 'OPERATOR')) = (company_id IS NOT NULL)),
  CHECK ((node_type = 'PORT') = (port_id IS NOT NULL)),
  CHECK ((node_type = 'CARGO') = (cargo_declaration_id IS NOT NULL)),
  CHECK ((node_type = 'VOYAGE') = (voyage_id IS NOT NULL))
);
CREATE INDEX IF NOT EXISTS idx_graph_nodes_type_label
  ON intelligence_graph_nodes (node_type, label);

CREATE TABLE IF NOT EXISTS intelligence_graph_edges (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  from_node_id uuid NOT NULL REFERENCES intelligence_graph_nodes(id) ON DELETE CASCADE,
  to_node_id uuid NOT NULL REFERENCES intelligence_graph_nodes(id) ON DELETE CASCADE,
  relationship_type text NOT NULL
    CHECK (relationship_type IN ('OWNED_BY', 'OPERATED_BY', 'VISITED', 'CARRIED', 'ENCOUNTERED', 'RELATED_TO', 'SHIPPED_BY', 'CONSIGNED_TO')),
  first_observed_at timestamptz,
  last_observed_at timestamptz,
  observation_count integer NOT NULL DEFAULT 1 CHECK (observation_count > 0),
  connection_strength text CHECK (connection_strength IN ('LOW', 'MODERATE', 'HIGH')),
  source text NOT NULL,
  source_timestamp timestamptz NOT NULL,
  confidence numeric(5,4) NOT NULL CHECK (confidence BETWEEN 0 AND 1),
  verification_status text NOT NULL
    CHECK (verification_status IN ('REPORTED', 'ESTIMATED', 'VERIFIED')),
  explanation text NOT NULL,
  evidence jsonb NOT NULL DEFAULT '{}'::jsonb,
  valid_from timestamptz,
  valid_to timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CHECK (from_node_id <> to_node_id),
  CHECK (last_observed_at IS NULL OR first_observed_at IS NULL OR last_observed_at >= first_observed_at),
  CHECK (valid_to IS NULL OR valid_from IS NULL OR valid_to > valid_from)
);
CREATE INDEX IF NOT EXISTS idx_graph_edges_from_type
  ON intelligence_graph_edges (from_node_id, relationship_type, last_observed_at DESC);
CREATE INDEX IF NOT EXISTS idx_graph_edges_to_type
  ON intelligence_graph_edges (to_node_id, relationship_type, last_observed_at DESC);
CREATE INDEX IF NOT EXISTS idx_graph_edges_evidence
  ON intelligence_graph_edges USING gin (evidence);
CREATE UNIQUE INDEX IF NOT EXISTS idx_graph_edges_current_unique
  ON intelligence_graph_edges (from_node_id, to_node_id, relationship_type)
  WHERE valid_to IS NULL;

CREATE TABLE IF NOT EXISTS advanced_correlation_rules (
  rule_key text PRIMARY KEY,
  required_event_types text[] NOT NULL,
  minimum_confidence numeric(5,4) NOT NULL CHECK (minimum_confidence BETWEEN 0 AND 1),
  maximum_score smallint NOT NULL CHECK (maximum_score BETWEEN 0 AND 100),
  parameters jsonb NOT NULL DEFAULT '{}'::jsonb,
  prevent_double_counting boolean NOT NULL DEFAULT true,
  enabled boolean NOT NULL DEFAULT true,
  model_version text NOT NULL,
  config_version integer NOT NULL DEFAULT 1,
  effective_from timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CHECK (cardinality(required_event_types) > 0)
);

CREATE TABLE IF NOT EXISTS advanced_correlations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  rule_key text NOT NULL REFERENCES advanced_correlation_rules(rule_key),
  vessel_id uuid NOT NULL REFERENCES vessels(id) ON DELETE CASCADE,
  voyage_id uuid REFERENCES voyages(id) ON DELETE CASCADE,
  risk_assessment_id uuid REFERENCES risk_assessments(id) ON DELETE SET NULL,
  input_fingerprint text NOT NULL,
  score_contribution numeric(5,2) NOT NULL CHECK (score_contribution BETWEEN 0 AND 100),
  confidence numeric(5,4) NOT NULL CHECK (confidence BETWEEN 0 AND 1),
  verification_status text NOT NULL DEFAULT 'ESTIMATED'
    CHECK (verification_status IN ('REPORTED', 'ESTIMATED', 'VERIFIED')),
  source text NOT NULL DEFAULT 'correlation_engine',
  source_timestamp timestamptz NOT NULL,
  status text NOT NULL DEFAULT 'requires_review'
    CHECK (status IN ('requires_review', 'reviewed', 'dismissed')),
  explanation text NOT NULL,
  evidence jsonb NOT NULL DEFAULT '{}'::jsonb,
  model_version text NOT NULL,
  calculated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (vessel_id, voyage_id, rule_key, input_fingerprint, model_version)
);
CREATE INDEX IF NOT EXISTS idx_advanced_correlations_voyage
  ON advanced_correlations (voyage_id, calculated_at DESC)
  WHERE voyage_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_advanced_correlations_review
  ON advanced_correlations (status, score_contribution DESC, calculated_at DESC);
CREATE UNIQUE INDEX IF NOT EXISTS idx_advanced_correlations_vessel_fingerprint
  ON advanced_correlations (vessel_id, rule_key, input_fingerprint, model_version)
  WHERE voyage_id IS NULL;

CREATE TABLE IF NOT EXISTS advanced_correlation_members (
  correlation_id uuid NOT NULL REFERENCES advanced_correlations(id) ON DELETE CASCADE,
  analytical_event_id uuid REFERENCES advanced_analytical_events(id) ON DELETE CASCADE,
  detected_event_id uuid REFERENCES detected_events(id) ON DELETE CASCADE,
  sequence_number integer NOT NULL CHECK (sequence_number > 0),
  contribution_role text NOT NULL
    CHECK (contribution_role IN ('PRIMARY', 'CONTEXT', 'CORRECTION', 'COUNTER_EVIDENCE')),
  PRIMARY KEY (correlation_id, sequence_number),
  CHECK (num_nonnulls(analytical_event_id, detected_event_id) = 1)
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_advanced_correlation_analytical_member
  ON advanced_correlation_members (correlation_id, analytical_event_id)
  WHERE analytical_event_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS idx_advanced_correlation_detected_member
  ON advanced_correlation_members (correlation_id, detected_event_id)
  WHERE detected_event_id IS NOT NULL;

ALTER TABLE risk_factors
  ADD COLUMN IF NOT EXISTS source_analytical_event_id uuid
    REFERENCES advanced_analytical_events(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS idx_risk_factors_analytical_event
  ON risk_factors (source_analytical_event_id)
  WHERE source_analytical_event_id IS NOT NULL;

ALTER TABLE risk_assessments
  ALTER COLUMN model_version SET DEFAULT 'CI-RISK-2.0';
ALTER TABLE risk_history
  ALTER COLUMN model_version SET DEFAULT 'CI-RISK-2.0';
ALTER TABLE risk_scenarios
  ALTER COLUMN model_version SET DEFAULT 'CI-RISK-2.0';
ALTER TABLE risk_rule_config
  ALTER COLUMN model_version SET DEFAULT 'CI-RISK-2.0';

INSERT INTO event_detector_config (detector_type, parameters) VALUES
  ('cargo_anomaly', '{"minimum_confidence":0.45,"historical_profile_required":true}'),
  ('cargo_draught_mismatch', '{"minimum_model_confidence":0.45,"use_vessel_specific_model":true}'),
  ('fuel_anomaly', '{"minimum_model_confidence":0.45,"apply_weather_correction":true,"apply_operational_correction":true}'),
  ('economic_anomaly', '{"minimum_model_confidence":0.45,"indicator_only":true}'),
  ('unusual_connection', '{"minimum_encounters":3,"context_only":true}')
ON CONFLICT (detector_type) DO NOTHING;

INSERT INTO risk_rule_config (rule_key, base_score, maximum_score, parameters, model_version) VALUES
  ('cargo_anomaly', 4, 8, '{"confidence_weighted":true,"requires_review":true}', 'CI-RISK-2.0'),
  ('cargo_draught_mismatch', 7, 13, '{"confidence_weighted":true,"vessel_specific_model":true}', 'CI-RISK-2.0'),
  ('fuel_anomaly', 5, 9, '{"weather_corrected":true,"operationally_corrected":true}', 'CI-RISK-2.0'),
  ('economic_anomaly', 3, 6, '{"indicator_only":true,"confidence_weighted":true}', 'CI-RISK-2.0'),
  ('historical_connection', 2, 5, '{"requires_explanation":true,"context_only":true}', 'CI-RISK-2.0'),
  ('related_vessel_context', 0, 3, '{"requires_confirming_factors":true,"no_automatic_risk_transfer":true}', 'CI-RISK-2.0'),
  ('advanced_correlation', 0, 15, '{"prevent_double_counting":true,"cap":15}', 'CI-RISK-2.0')
ON CONFLICT (rule_key) DO NOTHING;

INSERT INTO advanced_correlation_rules
  (rule_key, required_event_types, minimum_confidence, maximum_score, parameters, model_version)
VALUES
  ('route_gap_fuel', ARRAY['ROUTE_DEVIATION','AIS_GAP','FUEL_ANOMALY'], 0.55, 8,
   '{"description":"Fuel deviation is contextual only after weather and operational corrections"}', 'CI-ADV-1.0'),
  ('encounter_draught_cargo', ARRAY['VESSEL_ENCOUNTER','DRAUGHT_CHANGE','CARGO_DRAUGHT_MISMATCH'], 0.55, 10,
   '{"description":"Temporal sequence requires analyst review and does not establish causation"}', 'CI-ADV-1.0'),
  ('cargo_fuel_economics', ARRAY['CARGO_DRAUGHT_MISMATCH','FUEL_ANOMALY','ECONOMIC_ANOMALY'], 0.50, 7,
   '{"description":"Combined consistency indicators with shared-evidence de-duplication"}', 'CI-ADV-1.0')
ON CONFLICT (rule_key) DO NOTHING;

-- Stage 8: Grounded AI Assistant & Investigation.
-- The assistant stores plans, tool access and evidence separately from prose so
-- every significant claim remains auditable and write actions remain human-led.

CREATE TABLE IF NOT EXISTS assistant_tool_registry (
  tool_name text PRIMARY KEY,
  description text NOT NULL,
  tool_mode text NOT NULL CHECK (tool_mode IN ('READ', 'WRITE')),
  permission_scope text NOT NULL,
  requires_confirmation boolean NOT NULL,
  enabled boolean NOT NULL DEFAULT true,
  contract_version text NOT NULL DEFAULT 'CI-ASSIST-1.0',
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CHECK (requires_confirmation = (tool_mode = 'WRITE'))
);

CREATE TABLE IF NOT EXISTS assistant_tool_role_permissions (
  tool_name text NOT NULL REFERENCES assistant_tool_registry(tool_name) ON DELETE CASCADE,
  role_name text NOT NULL CHECK (role_name IN ('ADMIN', 'ANALYST', 'VIEWER', 'PORT_DISPATCHER')),
  allowed boolean NOT NULL DEFAULT false,
  data_scope jsonb NOT NULL DEFAULT '{}'::jsonb,
  updated_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (tool_name, role_name)
);

CREATE TABLE IF NOT EXISTS assistant_conversations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  conversation_code text UNIQUE NOT NULL,
  user_id text NOT NULL,
  role_name text NOT NULL CHECK (role_name IN ('ADMIN', 'ANALYST', 'VIEWER', 'PORT_DISPATCHER')),
  title text NOT NULL,
  current_page text NOT NULL DEFAULT '/app/assistant',
  vessel_id uuid REFERENCES vessels(id) ON DELETE SET NULL,
  voyage_id uuid REFERENCES voyages(id) ON DELETE SET NULL,
  port_id uuid REFERENCES maritime_ports(id) ON DELETE SET NULL,
  selected_area geography(Polygon, 4326),
  selected_from timestamptz,
  selected_to timestamptz,
  context jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CHECK (selected_to IS NULL OR selected_from IS NULL OR selected_to >= selected_from)
);
CREATE INDEX IF NOT EXISTS idx_assistant_conversations_user_updated
  ON assistant_conversations (user_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_assistant_conversations_area
  ON assistant_conversations USING gist (selected_area);

CREATE TABLE IF NOT EXISTS assistant_messages (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  message_code text UNIQUE NOT NULL,
  conversation_id uuid NOT NULL REFERENCES assistant_conversations(id) ON DELETE CASCADE,
  message_role text NOT NULL CHECK (message_role IN ('USER', 'ASSISTANT')),
  content text NOT NULL,
  answer_title text,
  planner_version text,
  grounded boolean,
  insufficient_data boolean NOT NULL DEFAULT false,
  response_payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  CHECK ((message_role = 'ASSISTANT') OR (planner_version IS NULL AND grounded IS NULL)),
  CHECK ((message_role = 'USER') OR grounded IS NOT NULL)
);
CREATE INDEX IF NOT EXISTS idx_assistant_messages_conversation_time
  ON assistant_messages (conversation_id, created_at);

CREATE TABLE IF NOT EXISTS assistant_tool_calls (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  message_id uuid NOT NULL REFERENCES assistant_messages(id) ON DELETE CASCADE,
  tool_name text NOT NULL REFERENCES assistant_tool_registry(tool_name),
  call_sequence integer NOT NULL CHECK (call_sequence > 0),
  arguments jsonb NOT NULL DEFAULT '{}'::jsonb,
  permission_role text NOT NULL CHECK (permission_role IN ('ADMIN', 'ANALYST', 'VIEWER', 'PORT_DISPATCHER')),
  permission_granted boolean NOT NULL,
  status text NOT NULL CHECK (status IN ('SUCCESS', 'DENIED', 'NOT_FOUND', 'ERROR')),
  record_count integer NOT NULL DEFAULT 0 CHECK (record_count >= 0),
  result_summary jsonb NOT NULL DEFAULT '{}'::jsonb,
  started_at timestamptz NOT NULL DEFAULT now(),
  completed_at timestamptz,
  UNIQUE (message_id, call_sequence),
  CHECK (completed_at IS NULL OR completed_at >= started_at),
  CHECK (permission_granted OR status = 'DENIED')
);
CREATE INDEX IF NOT EXISTS idx_assistant_tool_calls_tool_time
  ON assistant_tool_calls (tool_name, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_assistant_tool_calls_denied
  ON assistant_tool_calls (permission_role, started_at DESC) WHERE status = 'DENIED';

CREATE TABLE IF NOT EXISTS assistant_data_access (
  id bigserial PRIMARY KEY,
  tool_call_id uuid NOT NULL REFERENCES assistant_tool_calls(id) ON DELETE CASCADE,
  source_module text NOT NULL,
  entity_type text NOT NULL,
  entity_key text NOT NULL,
  access_mode text NOT NULL DEFAULT 'READ' CHECK (access_mode = 'READ'),
  fields_accessed text[] NOT NULL DEFAULT ARRAY[]::text[],
  accessed_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tool_call_id, source_module, entity_type, entity_key)
);
CREATE INDEX IF NOT EXISTS idx_assistant_data_access_entity
  ON assistant_data_access (entity_type, entity_key, accessed_at DESC);

CREATE TABLE IF NOT EXISTS assistant_claims (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  message_id uuid NOT NULL REFERENCES assistant_messages(id) ON DELETE CASCADE,
  claim_sequence integer NOT NULL CHECK (claim_sequence > 0),
  claim_kind text NOT NULL CHECK (claim_kind IN ('FACT', 'ESTIMATE', 'INFERENCE')),
  statement text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (message_id, claim_sequence)
);

CREATE TABLE IF NOT EXISTS assistant_claim_evidence (
  claim_id uuid NOT NULL REFERENCES assistant_claims(id) ON DELETE CASCADE,
  evidence_sequence integer NOT NULL CHECK (evidence_sequence > 0),
  source_module text NOT NULL,
  source_type text NOT NULL,
  source_key text NOT NULL,
  internal_href text NOT NULL CHECK (internal_href LIKE '/app/%'),
  label text NOT NULL,
  PRIMARY KEY (claim_id, evidence_sequence),
  UNIQUE (claim_id, source_module, source_type, source_key)
);
CREATE INDEX IF NOT EXISTS idx_assistant_claim_evidence_source
  ON assistant_claim_evidence (source_type, source_key);

CREATE TABLE IF NOT EXISTS investigations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  case_code text UNIQUE NOT NULL,
  title text NOT NULL,
  status text NOT NULL DEFAULT 'OPEN' CHECK (status IN ('OPEN', 'IN_REVIEW', 'CLOSED')),
  priority text NOT NULL CHECK (priority IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),
  vessel_id uuid NOT NULL REFERENCES vessels(id) ON DELETE RESTRICT,
  voyage_id uuid REFERENCES voyages(id) ON DELETE SET NULL,
  assigned_to text NOT NULL,
  summary text,
  conclusion text,
  created_by text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  closed_at timestamptz,
  CHECK ((status = 'CLOSED') = (closed_at IS NOT NULL))
);
CREATE INDEX IF NOT EXISTS idx_investigations_work_queue
  ON investigations (status, priority, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_investigations_vessel_time
  ON investigations (vessel_id, created_at DESC);

CREATE TABLE IF NOT EXISTS investigation_entities (
  investigation_id uuid NOT NULL REFERENCES investigations(id) ON DELETE CASCADE,
  entity_type text NOT NULL CHECK (entity_type IN ('VESSEL', 'COMPANY', 'PORT', 'VOYAGE')),
  entity_key text NOT NULL,
  relationship_role text NOT NULL,
  added_by text NOT NULL,
  added_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (investigation_id, entity_type, entity_key)
);

CREATE TABLE IF NOT EXISTS investigation_evidence (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  investigation_id uuid NOT NULL REFERENCES investigations(id) ON DELETE CASCADE,
  evidence_sequence integer NOT NULL CHECK (evidence_sequence > 0),
  source_type text NOT NULL CHECK (source_type IN ('DETECTED_EVENT', 'ANALYTICAL_EVENT', 'RISK_FACTOR', 'PORT_EVENT', 'VOYAGE', 'DOCUMENT')),
  source_key text NOT NULL,
  detected_event_id uuid REFERENCES detected_events(id) ON DELETE RESTRICT,
  analytical_event_id uuid REFERENCES advanced_analytical_events(id) ON DELETE RESTRICT,
  risk_factor_id uuid REFERENCES risk_factors(id) ON DELETE RESTRICT,
  port_event_id uuid REFERENCES port_events(id) ON DELETE RESTRICT,
  voyage_id uuid REFERENCES voyages(id) ON DELETE RESTRICT,
  title text NOT NULL,
  detail text NOT NULL,
  claim_kind text NOT NULL CHECK (claim_kind IN ('FACT', 'ESTIMATE', 'INFERENCE')),
  internal_href text NOT NULL CHECK (internal_href LIKE '/app/%'),
  source_snapshot jsonb NOT NULL,
  occurred_at timestamptz,
  added_by text NOT NULL,
  added_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (investigation_id, evidence_sequence),
  UNIQUE (investigation_id, source_type, source_key),
  CHECK (num_nonnulls(detected_event_id, analytical_event_id, risk_factor_id, port_event_id, voyage_id) <= 1)
);
CREATE INDEX IF NOT EXISTS idx_investigation_evidence_source
  ON investigation_evidence (source_type, source_key);
CREATE INDEX IF NOT EXISTS idx_investigation_evidence_time
  ON investigation_evidence (investigation_id, occurred_at);

CREATE TABLE IF NOT EXISTS investigation_notes (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  investigation_id uuid NOT NULL REFERENCES investigations(id) ON DELETE CASCADE,
  note_text text NOT NULL,
  author text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_investigation_notes_case_time
  ON investigation_notes (investigation_id, created_at);

CREATE TABLE IF NOT EXISTS investigation_timeline (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  investigation_id uuid NOT NULL REFERENCES investigations(id) ON DELETE CASCADE,
  occurred_at timestamptz NOT NULL,
  title text NOT NULL,
  detail text NOT NULL,
  claim_kind text NOT NULL CHECK (claim_kind IN ('FACT', 'ESTIMATE', 'INFERENCE')),
  source_key text NOT NULL,
  internal_href text NOT NULL CHECK (internal_href LIKE '/app/%'),
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (investigation_id, occurred_at, source_key)
);
CREATE INDEX IF NOT EXISTS idx_investigation_timeline_case_time
  ON investigation_timeline (investigation_id, occurred_at);

CREATE TABLE IF NOT EXISTS investigation_summaries (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  investigation_id uuid NOT NULL REFERENCES investigations(id) ON DELETE CASCADE,
  summary_text text NOT NULL,
  evidence_fingerprint text NOT NULL,
  evidence_count integer NOT NULL CHECK (evidence_count > 0),
  model_version text NOT NULL DEFAULT 'CI-ASSIST-1.0',
  generated_by text NOT NULL,
  generated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (investigation_id, evidence_fingerprint)
);

CREATE TABLE IF NOT EXISTS assistant_actions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  action_code text UNIQUE NOT NULL,
  conversation_id uuid NOT NULL REFERENCES assistant_conversations(id) ON DELETE CASCADE,
  message_id uuid NOT NULL REFERENCES assistant_messages(id) ON DELETE CASCADE,
  tool_name text NOT NULL REFERENCES assistant_tool_registry(tool_name),
  action_type text NOT NULL,
  requested_by text NOT NULL,
  requested_role text NOT NULL CHECK (requested_role IN ('ADMIN', 'ANALYST', 'VIEWER', 'PORT_DISPATCHER')),
  payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  status text NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'CONFIRMED', 'REJECTED', 'FAILED')),
  requires_confirmation boolean NOT NULL DEFAULT true CHECK (requires_confirmation),
  confirmed_by text,
  confirmed_at timestamptz,
  decision_note text,
  result_payload jsonb,
  executed_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  CHECK ((status = 'PENDING') = (confirmed_at IS NULL)),
  CHECK (executed_at IS NULL OR (status = 'CONFIRMED' AND confirmed_at IS NOT NULL)),
  CHECK (confirmed_by IS NULL OR confirmed_at IS NOT NULL)
);
CREATE INDEX IF NOT EXISTS idx_assistant_actions_pending
  ON assistant_actions (requested_by, created_at DESC) WHERE status = 'PENDING';

CREATE TABLE IF NOT EXISTS assistant_audit_log (
  id bigserial PRIMARY KEY,
  user_id text NOT NULL,
  role_name text NOT NULL CHECK (role_name IN ('ADMIN', 'ANALYST', 'VIEWER', 'PORT_DISPATCHER')),
  conversation_id uuid REFERENCES assistant_conversations(id) ON DELETE SET NULL,
  message_id uuid REFERENCES assistant_messages(id) ON DELETE SET NULL,
  question text NOT NULL,
  tools_called text[] NOT NULL DEFAULT ARRAY[]::text[],
  data_accessed jsonb NOT NULL DEFAULT '[]'::jsonb,
  answer text NOT NULL,
  actions text[] NOT NULL DEFAULT ARRAY[]::text[],
  outcome text NOT NULL CHECK (outcome IN ('ANSWERED', 'INSUFFICIENT_DATA', 'DENIED', 'CONFIRMED', 'REJECTED', 'FAILED')),
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_assistant_audit_user_time
  ON assistant_audit_log (user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_assistant_audit_outcome
  ON assistant_audit_log (outcome, created_at DESC);

INSERT INTO assistant_tool_registry (tool_name, description, tool_mode, permission_scope, requires_confirmation) VALUES
  ('get_vessel', 'Canonical vessel record', 'READ', 'vessel:read', false),
  ('get_current_voyage', 'Current voyage record', 'READ', 'voyage:read', false),
  ('get_vessel_events', 'Detected events for a vessel', 'READ', 'events:security', false),
  ('get_vessel_risk', 'Current explainable risk', 'READ', 'risk:summary', false),
  ('get_risk_factors', 'Risk factors and source events', 'READ', 'risk:security', false),
  ('get_behavior_profile', 'Vessel behavior baseline', 'READ', 'behavior:read', false),
  ('get_encounters', 'Current and historical encounters', 'READ', 'network:security', false),
  ('get_cargo_analysis', 'Cargo and draught analysis', 'READ', 'cargo:security', false),
  ('get_fuel_analysis', 'Corrected fuel analysis', 'READ', 'fuel:security', false),
  ('get_vessel_network', 'Explainable entity network', 'READ', 'network:security', false),
  ('search_vessels', 'Structured vessel search', 'READ', 'vessel:read', false),
  ('search_events', 'Structured event search', 'READ', 'events:security', false),
  ('search_area', 'Time-bounded spatial search', 'READ', 'map:read', false),
  ('get_port_status', 'Current port overview', 'READ', 'port:read', false),
  ('get_arrivals', 'Port arrivals', 'READ', 'port:read', false),
  ('get_port_forecast', 'Port load forecast', 'READ', 'port:read', false),
  ('get_eta', 'Explainable ETA', 'READ', 'port:read', false),
  ('get_pre_arrival', 'Pre-arrival report', 'READ', 'port:read', false),
  ('create_investigation', 'Create Investigation Case', 'WRITE', 'investigation:write', true),
  ('add_case_evidence', 'Add evidence to Case', 'WRITE', 'investigation:write', true),
  ('update_investigation', 'Update Case fields', 'WRITE', 'investigation:write', true),
  ('add_case_note', 'Add analyst note', 'WRITE', 'investigation:write', true),
  ('assign_berth', 'Apply berth decision', 'WRITE', 'port:write', true),
  ('change_port_queue', 'Change port queue', 'WRITE', 'port:write', true),
  ('close_event', 'Close detected event', 'WRITE', 'events:write', true)
ON CONFLICT (tool_name) DO NOTHING;

INSERT INTO assistant_tool_role_permissions (tool_name, role_name, allowed, data_scope)
SELECT registry.tool_name, roles.role_name,
  CASE
    WHEN roles.role_name = 'ADMIN' THEN true
    WHEN roles.role_name = 'ANALYST' THEN true
    WHEN roles.role_name = 'VIEWER' THEN registry.tool_mode = 'READ'
      AND registry.permission_scope IN ('vessel:read', 'voyage:read', 'behavior:read', 'map:read', 'port:read', 'risk:summary')
    WHEN roles.role_name = 'PORT_DISPATCHER' THEN registry.permission_scope IN
      ('vessel:read', 'voyage:read', 'behavior:read', 'map:read', 'port:read', 'port:write', 'risk:summary')
    ELSE false
  END,
  CASE
    WHEN roles.role_name = 'PORT_DISPATCHER' THEN '{"scope":"port_operations","security_details":false}'::jsonb
    WHEN roles.role_name = 'VIEWER' THEN '{"scope":"read_only","security_details":false}'::jsonb
    ELSE '{"scope":"authorized_workspace"}'::jsonb
  END
FROM assistant_tool_registry registry
CROSS JOIN (VALUES ('ADMIN'), ('ANALYST'), ('VIEWER'), ('PORT_DISPATCHER')) AS roles(role_name)
ON CONFLICT (tool_name, role_name) DO UPDATE SET
  allowed = EXCLUDED.allowed,
  data_scope = EXCLUDED.data_scope,
  updated_at = now();

-- Stage 10: Caspian Network / regional production architecture.
-- Existing vessels, maritime_ports, voyages and port_calls stay canonical for
-- operational analytics. The tables below add a multi-port control plane,
-- global identity, provenance, tenant-aware authorization, regional products
-- and reliable integration infrastructure around those records.
--
-- All instants use timestamptz and are persisted by PostgreSQL as UTC. IANA
-- time zones and BCP-47-like locales below are presentation/configuration data.
-- Adapter credentials are never stored here: only an external secret_reference.

CREATE TABLE IF NOT EXISTS network_regions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  region_code text UNIQUE NOT NULL CHECK (region_code ~ '^[A-Z][A-Z0-9_-]{1,31}$'),
  display_name text NOT NULL,
  default_timezone text NOT NULL CHECK (length(default_timezone) BETWEEN 3 AND 64),
  default_locale text NOT NULL CHECK (default_locale ~ '^[a-z]{2,3}(-[A-Z]{2})?$'),
  data_residency_country varchar(3) NOT NULL CHECK (data_residency_country ~ '^[A-Z]{2,3}$'),
  operational_status text NOT NULL DEFAULT 'ACTIVE'
    CHECK (operational_status IN ('ACTIVE', 'LIMITED', 'SUSPENDED', 'RETIRED')),
  configuration jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(configuration) = 'object'),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS network_port_nodes (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  region_id uuid NOT NULL REFERENCES network_regions(id) ON DELETE RESTRICT,
  port_id uuid NOT NULL REFERENCES maritime_ports(id) ON DELETE RESTRICT,
  network_port_code text UNIQUE NOT NULL CHECK (network_port_code ~ '^[A-Z0-9_-]{2,32}$'),
  timezone text NOT NULL CHECK (length(timezone) BETWEEN 3 AND 64),
  default_locale text NOT NULL CHECK (default_locale ~ '^[a-z]{2,3}(-[A-Z]{2})?$'),
  data_residency_country varchar(3) NOT NULL CHECK (data_residency_country ~ '^[A-Z]{2,3}$'),
  node_status text NOT NULL DEFAULT 'ONBOARDING'
    CHECK (node_status IN ('ONBOARDING', 'ACTIVE', 'DEGRADED', 'SUSPENDED', 'RETIRED')),
  capabilities jsonb NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(capabilities) = 'array'),
  configuration_revision integer NOT NULL DEFAULT 1 CHECK (configuration_revision > 0),
  onboarded_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (region_id, port_id),
  CHECK ((node_status = 'ONBOARDING') OR onboarded_at IS NOT NULL)
);
CREATE INDEX IF NOT EXISTS idx_network_port_nodes_region_status
  ON network_port_nodes (region_id, node_status, network_port_code);

CREATE TABLE IF NOT EXISTS integration_adapter_definitions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  adapter_key text UNIQUE NOT NULL CHECK (adapter_key ~ '^[a-z][a-z0-9._-]{2,63}$'),
  display_name text NOT NULL,
  data_domain text NOT NULL
    CHECK (data_domain IN ('AIS', 'PORT', 'WEATHER', 'CUSTOMS', 'CARGO', 'FUEL', 'SATELLITE', 'REGISTRY', 'CORPORATE', 'OTHER')),
  protocol text NOT NULL CHECK (protocol IN ('REST', 'SOAP', 'SFTP', 'KAFKA', 'AMQP', 'WEBHOOK', 'FILE', 'MANUAL')),
  delivery_mode text NOT NULL CHECK (delivery_mode IN ('PULL', 'PUSH', 'BIDIRECTIONAL', 'BATCH')),
  adapter_version text NOT NULL,
  input_schema_version text NOT NULL,
  configuration_schema jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(configuration_schema) = 'object'),
  supports_replay boolean NOT NULL DEFAULT false,
  enabled boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS port_adapter_bindings (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  port_node_id uuid NOT NULL REFERENCES network_port_nodes(id) ON DELETE CASCADE,
  adapter_id uuid NOT NULL REFERENCES integration_adapter_definitions(id) ON DELETE RESTRICT,
  external_port_key text NOT NULL,
  binding_status text NOT NULL DEFAULT 'CONFIGURED'
    CHECK (binding_status IN ('CONFIGURED', 'ACTIVE', 'DEGRADED', 'PAUSED', 'DISABLED')),
  priority integer NOT NULL DEFAULT 100 CHECK (priority BETWEEN 1 AND 1000),
  secret_reference text CHECK (secret_reference IS NULL OR secret_reference ~ '^(vault|kms|secret)://'),
  configuration jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(configuration) = 'object'),
  last_health_at timestamptz,
  last_success_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (port_node_id, adapter_id, external_port_key),
  CHECK (last_success_at IS NULL OR last_health_at IS NULL OR last_success_at <= last_health_at)
);
CREATE INDEX IF NOT EXISTS idx_port_adapter_bindings_health
  ON port_adapter_bindings (binding_status, last_health_at, port_node_id);

CREATE TABLE IF NOT EXISTS adapter_sync_cursors (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  binding_id uuid NOT NULL REFERENCES port_adapter_bindings(id) ON DELETE CASCADE,
  stream_key text NOT NULL,
  cursor_value text,
  source_watermark timestamptz,
  last_attempt_at timestamptz,
  last_success_at timestamptz,
  sync_status text NOT NULL DEFAULT 'IDLE'
    CHECK (sync_status IN ('IDLE', 'RUNNING', 'SUCCEEDED', 'FAILED', 'PAUSED')),
  error_code text,
  error_detail text,
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (binding_id, stream_key),
  CHECK (last_success_at IS NULL OR last_attempt_at IS NULL OR last_success_at <= last_attempt_at),
  CHECK ((sync_status = 'FAILED') OR error_code IS NULL)
);
CREATE INDEX IF NOT EXISTS idx_adapter_sync_status
  ON adapter_sync_cursors (sync_status, last_attempt_at);

CREATE TABLE IF NOT EXISTS network_configuration_versions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  configuration_key text NOT NULL,
  configuration_scope text NOT NULL CHECK (configuration_scope IN ('GLOBAL', 'REGION', 'PORT')),
  region_id uuid REFERENCES network_regions(id) ON DELETE CASCADE,
  port_node_id uuid REFERENCES network_port_nodes(id) ON DELETE CASCADE,
  version integer NOT NULL CHECK (version > 0),
  lifecycle_status text NOT NULL DEFAULT 'DRAFT'
    CHECK (lifecycle_status IN ('DRAFT', 'ACTIVE', 'SUPERSEDED', 'REJECTED')),
  configuration jsonb NOT NULL CHECK (jsonb_typeof(configuration) = 'object'),
  checksum_sha256 varchar(64) NOT NULL CHECK (checksum_sha256 ~ '^[0-9a-f]{64}$'),
  valid_from timestamptz,
  valid_to timestamptz,
  created_by text NOT NULL,
  approved_by text,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (configuration_key, configuration_scope, region_id, port_node_id, version),
  CHECK (valid_to IS NULL OR (valid_from IS NOT NULL AND valid_to > valid_from)),
  CHECK (
    (configuration_scope = 'GLOBAL' AND region_id IS NULL AND port_node_id IS NULL) OR
    (configuration_scope = 'REGION' AND region_id IS NOT NULL AND port_node_id IS NULL) OR
    (configuration_scope = 'PORT' AND port_node_id IS NOT NULL)
  ),
  CHECK ((lifecycle_status = 'ACTIVE') = (approved_by IS NOT NULL AND valid_from IS NOT NULL))
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_network_config_active_global
  ON network_configuration_versions (configuration_key)
  WHERE lifecycle_status = 'ACTIVE' AND configuration_scope = 'GLOBAL';
CREATE UNIQUE INDEX IF NOT EXISTS idx_network_config_active_region
  ON network_configuration_versions (configuration_key, region_id)
  WHERE lifecycle_status = 'ACTIVE' AND configuration_scope = 'REGION';
CREATE UNIQUE INDEX IF NOT EXISTS idx_network_config_active_port
  ON network_configuration_versions (configuration_key, port_node_id)
  WHERE lifecycle_status = 'ACTIVE' AND configuration_scope = 'PORT';

CREATE TABLE IF NOT EXISTS source_systems (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  source_key text UNIQUE NOT NULL CHECK (source_key ~ '^[a-z][a-z0-9._-]{2,63}$'),
  display_name text NOT NULL,
  owning_organization text NOT NULL,
  source_type text NOT NULL
    CHECK (source_type IN ('PORT', 'AIS_PROVIDER', 'REGISTRY', 'WEATHER', 'CUSTOMS', 'SATELLITE', 'ANALYTICAL_MODEL', 'MANUAL', 'OTHER')),
  trust_tier text NOT NULL CHECK (trust_tier IN ('AUTHORITATIVE', 'VERIFIED_PARTNER', 'SUPPLEMENTARY', 'UNVERIFIED')),
  data_residency_country varchar(3) CHECK (data_residency_country IS NULL OR data_residency_country ~ '^[A-Z]{2,3}$'),
  default_retention_days integer NOT NULL DEFAULT 365 CHECK (default_retention_days > 0),
  active boolean NOT NULL DEFAULT true,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(metadata) = 'object'),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS source_records (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  source_system_id uuid NOT NULL REFERENCES source_systems(id) ON DELETE RESTRICT,
  port_node_id uuid REFERENCES network_port_nodes(id) ON DELETE SET NULL,
  external_record_key text NOT NULL,
  record_version text NOT NULL DEFAULT '1',
  record_type text NOT NULL,
  schema_version text NOT NULL,
  payload_reference text NOT NULL,
  checksum_sha256 varchar(64) NOT NULL CHECK (checksum_sha256 ~ '^[0-9a-f]{64}$'),
  observed_at timestamptz,
  effective_from timestamptz,
  effective_to timestamptz,
  received_at timestamptz NOT NULL DEFAULT now(),
  provenance_kind text NOT NULL
    CHECK (provenance_kind IN ('OBSERVED', 'REPORTED', 'VERIFIED', 'ESTIMATED', 'INFERRED')),
  quality_status text NOT NULL DEFAULT 'ACCEPTED'
    CHECK (quality_status IN ('ACCEPTED', 'PARTIAL', 'QUARANTINED', 'REJECTED')),
  quality_issues jsonb NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(quality_issues) = 'array'),
  correlation_id uuid NOT NULL DEFAULT gen_random_uuid(),
  ingested_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (source_system_id, external_record_key, record_version),
  CHECK (effective_to IS NULL OR (effective_from IS NOT NULL AND effective_to > effective_from))
);
CREATE INDEX IF NOT EXISTS idx_source_records_received
  ON source_records (source_system_id, received_at DESC);
CREATE INDEX IF NOT EXISTS idx_source_records_correlation
  ON source_records (correlation_id);
CREATE INDEX IF NOT EXISTS idx_source_records_quarantine
  ON source_records (ingested_at DESC) WHERE quality_status = 'QUARANTINED';

CREATE TABLE IF NOT EXISTS global_entities (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  global_entity_code text UNIQUE NOT NULL CHECK (global_entity_code ~ '^CI-[A-Z]+-[A-Z0-9_-]+$'),
  entity_type text NOT NULL CHECK (entity_type IN ('VESSEL', 'PORT', 'COMPANY', 'PERSON', 'VOYAGE', 'CARGO')),
  canonical_name text NOT NULL,
  canonical_vessel_id uuid REFERENCES vessels(id) ON DELETE RESTRICT,
  canonical_port_id uuid REFERENCES maritime_ports(id) ON DELETE RESTRICT,
  canonical_company_id uuid REFERENCES companies(id) ON DELETE RESTRICT,
  lifecycle_status text NOT NULL DEFAULT 'ACTIVE'
    CHECK (lifecycle_status IN ('ACTIVE', 'MERGED', 'SPLIT', 'RETIRED', 'UNDER_REVIEW')),
  merged_into_id uuid REFERENCES global_entities(id) ON DELETE RESTRICT,
  identity_confidence numeric(5,4) NOT NULL CHECK (identity_confidence BETWEEN 0 AND 1),
  first_seen_at timestamptz NOT NULL,
  last_seen_at timestamptz NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CHECK (last_seen_at >= first_seen_at),
  CHECK (merged_into_id IS NULL OR (lifecycle_status = 'MERGED' AND merged_into_id <> id)),
  CHECK (
    (entity_type = 'VESSEL' AND canonical_vessel_id IS NOT NULL AND canonical_port_id IS NULL AND canonical_company_id IS NULL) OR
    (entity_type = 'PORT' AND canonical_port_id IS NOT NULL AND canonical_vessel_id IS NULL AND canonical_company_id IS NULL) OR
    (entity_type = 'COMPANY' AND canonical_company_id IS NOT NULL AND canonical_vessel_id IS NULL AND canonical_port_id IS NULL) OR
    (entity_type IN ('PERSON', 'VOYAGE', 'CARGO') AND num_nonnulls(canonical_vessel_id, canonical_port_id, canonical_company_id) = 0)
  )
);
CREATE INDEX IF NOT EXISTS idx_global_entities_type_name
  ON global_entities (entity_type, lower(canonical_name));
CREATE INDEX IF NOT EXISTS idx_global_entities_review
  ON global_entities (last_seen_at DESC) WHERE lifecycle_status = 'UNDER_REVIEW';

CREATE TABLE IF NOT EXISTS global_entity_identifiers (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  entity_id uuid NOT NULL REFERENCES global_entities(id) ON DELETE CASCADE,
  identifier_namespace text NOT NULL
    CHECK (identifier_namespace IN ('IMO', 'MMSI', 'CALL_SIGN', 'UNLOCODE', 'REGISTRY_ID', 'TAX_ID', 'INTERNAL', 'SOURCE_NATIVE')),
  identifier_value text NOT NULL,
  normalized_value text NOT NULL,
  source_record_id uuid NOT NULL REFERENCES source_records(id) ON DELETE RESTRICT,
  verification_status text NOT NULL
    CHECK (verification_status IN ('REPORTED', 'VERIFIED', 'DISPUTED', 'REJECTED')),
  confidence numeric(5,4) NOT NULL CHECK (confidence BETWEEN 0 AND 1),
  valid_from timestamptz NOT NULL,
  valid_to timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (entity_id, identifier_namespace, normalized_value, valid_from),
  CHECK (valid_to IS NULL OR valid_to > valid_from)
);
CREATE INDEX IF NOT EXISTS idx_global_identifiers_entity_history
  ON global_entity_identifiers (entity_id, identifier_namespace, valid_from DESC);
CREATE UNIQUE INDEX IF NOT EXISTS idx_global_identifiers_current_unique
  ON global_entity_identifiers (identifier_namespace, normalized_value)
  WHERE valid_to IS NULL AND verification_status IN ('REPORTED', 'VERIFIED');

CREATE TABLE IF NOT EXISTS global_entity_aliases (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  entity_id uuid NOT NULL REFERENCES global_entities(id) ON DELETE CASCADE,
  alias_text text NOT NULL,
  normalized_alias text NOT NULL,
  locale text CHECK (locale IS NULL OR locale ~ '^[a-z]{2,3}(-[A-Z]{2})?$'),
  script_code varchar(4) CHECK (script_code IS NULL OR script_code ~ '^[A-Z][a-z]{3}$'),
  alias_type text NOT NULL CHECK (alias_type IN ('OFFICIAL', 'FORMER', 'TRANSLITERATION', 'SOURCE', 'OPERATIONAL')),
  source_record_id uuid NOT NULL REFERENCES source_records(id) ON DELETE RESTRICT,
  confidence numeric(5,4) NOT NULL CHECK (confidence BETWEEN 0 AND 1),
  valid_from timestamptz NOT NULL,
  valid_to timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  CHECK (valid_to IS NULL OR valid_to > valid_from)
);
CREATE INDEX IF NOT EXISTS idx_global_aliases_lookup
  ON global_entity_aliases (lower(normalized_alias), entity_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_global_aliases_current
  ON global_entity_aliases (entity_id, normalized_alias, alias_type)
  WHERE valid_to IS NULL;

CREATE TABLE IF NOT EXISTS global_identity_matches (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  left_entity_id uuid NOT NULL REFERENCES global_entities(id) ON DELETE CASCADE,
  right_entity_id uuid NOT NULL REFERENCES global_entities(id) ON DELETE CASCADE,
  match_score numeric(5,4) NOT NULL CHECK (match_score BETWEEN 0 AND 1),
  match_status text NOT NULL DEFAULT 'PROPOSED'
    CHECK (match_status IN ('PROPOSED', 'CONFIRMED', 'REJECTED', 'SUPERSEDED')),
  match_method text NOT NULL CHECK (match_method IN ('DETERMINISTIC', 'PROBABILISTIC', 'MANUAL')),
  model_version text,
  evidence jsonb NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(evidence) = 'array'),
  proposed_at timestamptz NOT NULL DEFAULT now(),
  reviewed_by text,
  reviewed_at timestamptz,
  review_note text,
  UNIQUE (left_entity_id, right_entity_id),
  CHECK (left_entity_id < right_entity_id),
  CHECK ((match_status IN ('CONFIRMED', 'REJECTED')) = (reviewed_by IS NOT NULL AND reviewed_at IS NOT NULL))
);
CREATE INDEX IF NOT EXISTS idx_global_identity_matches_queue
  ON global_identity_matches (match_status, match_score DESC, proposed_at);

CREATE TABLE IF NOT EXISTS global_identity_history (
  id bigserial PRIMARY KEY,
  entity_id uuid NOT NULL REFERENCES global_entities(id) ON DELETE RESTRICT,
  change_type text NOT NULL CHECK (change_type IN ('CREATED', 'IDENTIFIER_ADDED', 'ALIAS_ADDED', 'MERGED', 'SPLIT', 'UPDATED', 'RETIRED')),
  previous_snapshot jsonb,
  current_snapshot jsonb NOT NULL,
  source_record_id uuid REFERENCES source_records(id) ON DELETE RESTRICT,
  changed_by text NOT NULL,
  reason text NOT NULL,
  correlation_id uuid NOT NULL,
  changed_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_global_identity_history_entity
  ON global_identity_history (entity_id, changed_at DESC);
CREATE INDEX IF NOT EXISTS idx_global_identity_history_correlation
  ON global_identity_history (correlation_id);

CREATE TABLE IF NOT EXISTS provenance_assertions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  entity_id uuid NOT NULL REFERENCES global_entities(id) ON DELETE CASCADE,
  attribute_path text NOT NULL CHECK (attribute_path ~ '^[a-zA-Z0-9_.-]+$'),
  asserted_value jsonb NOT NULL,
  normalized_value text,
  source_record_id uuid NOT NULL REFERENCES source_records(id) ON DELETE RESTRICT,
  provenance_kind text NOT NULL
    CHECK (provenance_kind IN ('OBSERVED', 'REPORTED', 'VERIFIED', 'ESTIMATED', 'INFERRED')),
  confidence numeric(5,4) NOT NULL CHECK (confidence BETWEEN 0 AND 1),
  assertion_status text NOT NULL DEFAULT 'ACTIVE'
    CHECK (assertion_status IN ('ACTIVE', 'SUPERSEDED', 'DISPUTED', 'REJECTED')),
  effective_from timestamptz NOT NULL,
  effective_to timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (entity_id, attribute_path, source_record_id, effective_from),
  CHECK (effective_to IS NULL OR effective_to > effective_from)
);
CREATE INDEX IF NOT EXISTS idx_provenance_assertions_entity
  ON provenance_assertions (entity_id, attribute_path, assertion_status, effective_from DESC);
CREATE INDEX IF NOT EXISTS idx_provenance_assertions_source
  ON provenance_assertions (source_record_id);

CREATE TABLE IF NOT EXISTS provenance_conflicts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  entity_id uuid NOT NULL REFERENCES global_entities(id) ON DELETE CASCADE,
  attribute_path text NOT NULL,
  left_assertion_id uuid NOT NULL REFERENCES provenance_assertions(id) ON DELETE RESTRICT,
  right_assertion_id uuid NOT NULL REFERENCES provenance_assertions(id) ON DELETE RESTRICT,
  conflict_type text NOT NULL CHECK (conflict_type IN ('VALUE', 'IDENTITY', 'TEMPORAL', 'SOURCE', 'QUALITY')),
  severity text NOT NULL CHECK (severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),
  conflict_status text NOT NULL DEFAULT 'OPEN'
    CHECK (conflict_status IN ('OPEN', 'IN_REVIEW', 'RESOLVED', 'ACCEPTED_DIFFERENCE')),
  detected_at timestamptz NOT NULL DEFAULT now(),
  resolved_assertion_id uuid REFERENCES provenance_assertions(id) ON DELETE RESTRICT,
  resolved_by text,
  resolved_at timestamptz,
  resolution_note text,
  UNIQUE (left_assertion_id, right_assertion_id),
  CHECK (left_assertion_id < right_assertion_id),
  CHECK ((conflict_status IN ('RESOLVED', 'ACCEPTED_DIFFERENCE')) = (resolved_by IS NOT NULL AND resolved_at IS NOT NULL))
);
CREATE INDEX IF NOT EXISTS idx_provenance_conflicts_queue
  ON provenance_conflicts (conflict_status, severity, detected_at);
CREATE INDEX IF NOT EXISTS idx_provenance_conflicts_entity
  ON provenance_conflicts (entity_id, attribute_path, detected_at DESC);

CREATE TABLE IF NOT EXISTS provenance_conflict_history (
  id bigserial PRIMARY KEY,
  conflict_id uuid NOT NULL REFERENCES provenance_conflicts(id) ON DELETE CASCADE,
  previous_status text,
  current_status text NOT NULL,
  decision text NOT NULL,
  decided_by text NOT NULL,
  evidence_snapshot jsonb NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(evidence_snapshot) = 'array'),
  decided_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_provenance_conflict_history
  ON provenance_conflict_history (conflict_id, decided_at);

CREATE TABLE IF NOT EXISTS network_localizations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  resource_type text NOT NULL,
  resource_key text NOT NULL,
  field_name text NOT NULL,
  locale text NOT NULL CHECK (locale ~ '^[a-z]{2,3}(-[A-Z]{2})?$'),
  localized_value text NOT NULL,
  source_record_id uuid REFERENCES source_records(id) ON DELETE RESTRICT,
  verification_status text NOT NULL DEFAULT 'REPORTED'
    CHECK (verification_status IN ('REPORTED', 'VERIFIED')),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (resource_type, resource_key, field_name, locale)
);
CREATE INDEX IF NOT EXISTS idx_network_localizations_lookup
  ON network_localizations (resource_type, resource_key, locale);

CREATE TABLE IF NOT EXISTS network_organizations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_code text UNIQUE NOT NULL CHECK (organization_code ~ '^[A-Z0-9_-]{2,32}$'),
  display_name text NOT NULL,
  organization_type text NOT NULL
    CHECK (organization_type IN ('NETWORK_OPERATOR', 'PORT_AUTHORITY', 'SECURITY_AGENCY', 'DATA_PROVIDER', 'REGULATOR', 'PARTNER')),
  jurisdiction_country varchar(3) CHECK (jurisdiction_country IS NULL OR jurisdiction_country ~ '^[A-Z]{2,3}$'),
  parent_organization_id uuid REFERENCES network_organizations(id) ON DELETE RESTRICT,
  default_locale text NOT NULL CHECK (default_locale ~ '^[a-z]{2,3}(-[A-Z]{2})?$'),
  default_timezone text NOT NULL,
  status text NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'SUSPENDED', 'RETIRED')),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CHECK (parent_organization_id IS NULL OR parent_organization_id <> id)
);

CREATE TABLE IF NOT EXISTS network_users (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  external_subject text UNIQUE NOT NULL,
  display_name text NOT NULL,
  email text,
  preferred_locale text NOT NULL CHECK (preferred_locale ~ '^[a-z]{2,3}(-[A-Z]{2})?$'),
  preferred_timezone text NOT NULL,
  status text NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('INVITED', 'ACTIVE', 'LOCKED', 'DISABLED')),
  last_authenticated_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS organization_memberships (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL REFERENCES network_organizations(id) ON DELETE CASCADE,
  user_id uuid NOT NULL REFERENCES network_users(id) ON DELETE CASCADE,
  role_name text NOT NULL
    CHECK (role_name IN ('ORG_ADMIN', 'NETWORK_ANALYST', 'SECURITY_ANALYST', 'PORT_DISPATCHER', 'DATA_STEWARD', 'AUDITOR', 'VIEWER')),
  membership_status text NOT NULL DEFAULT 'ACTIVE'
    CHECK (membership_status IN ('INVITED', 'ACTIVE', 'SUSPENDED', 'ENDED')),
  starts_at timestamptz NOT NULL DEFAULT now(),
  ends_at timestamptz,
  granted_by uuid REFERENCES network_users(id) ON DELETE RESTRICT,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CHECK (ends_at IS NULL OR ends_at > starts_at),
  CHECK ((membership_status = 'ENDED') = (ends_at IS NOT NULL))
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_org_memberships_active
  ON organization_memberships (organization_id, user_id)
  WHERE membership_status = 'ACTIVE';
CREATE INDEX IF NOT EXISTS idx_org_memberships_user
  ON organization_memberships (user_id, membership_status, organization_id);

CREATE TABLE IF NOT EXISTS permission_scopes (
  scope_key text PRIMARY KEY CHECK (scope_key ~ '^[a-z][a-z0-9:_-]{2,95}$'),
  data_domain text NOT NULL,
  action text NOT NULL CHECK (action IN ('READ', 'WRITE', 'EXPORT', 'ADMINISTER')),
  sensitivity text NOT NULL CHECK (sensitivity IN ('PUBLIC', 'OPERATIONAL', 'RESTRICTED', 'SECURITY')),
  description text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS membership_scope_grants (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  membership_id uuid NOT NULL REFERENCES organization_memberships(id) ON DELETE CASCADE,
  scope_key text NOT NULL REFERENCES permission_scopes(scope_key) ON DELETE RESTRICT,
  grant_effect text NOT NULL CHECK (grant_effect IN ('ALLOW', 'DENY')),
  resource_filter jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(resource_filter) = 'object'),
  granted_by uuid REFERENCES network_users(id) ON DELETE RESTRICT,
  granted_at timestamptz NOT NULL DEFAULT now(),
  expires_at timestamptz,
  UNIQUE (membership_id, scope_key),
  CHECK (expires_at IS NULL OR expires_at > granted_at)
);
CREATE INDEX IF NOT EXISTS idx_membership_scope_grants_lookup
  ON membership_scope_grants (scope_key, grant_effect, expires_at);

CREATE TABLE IF NOT EXISTS membership_port_scopes (
  membership_id uuid NOT NULL REFERENCES organization_memberships(id) ON DELETE CASCADE,
  port_node_id uuid NOT NULL REFERENCES network_port_nodes(id) ON DELETE CASCADE,
  access_level text NOT NULL CHECK (access_level IN ('READ', 'OPERATE', 'ADMINISTER')),
  granted_at timestamptz NOT NULL DEFAULT now(),
  expires_at timestamptz,
  PRIMARY KEY (membership_id, port_node_id),
  CHECK (expires_at IS NULL OR expires_at > granted_at)
);
CREATE INDEX IF NOT EXISTS idx_membership_port_scope_node
  ON membership_port_scopes (port_node_id, access_level);

-- Default partition prevents inserts from failing before monthly partitions are
-- created by operations. Production should attach monthly UTC partitions and
-- drain the default partition under a controlled retention job.
CREATE TABLE IF NOT EXISTS network_access_audit (
  id bigint GENERATED ALWAYS AS IDENTITY,
  occurred_at timestamptz NOT NULL DEFAULT now(),
  correlation_id uuid NOT NULL,
  organization_id uuid REFERENCES network_organizations(id) ON DELETE SET NULL,
  membership_id uuid REFERENCES organization_memberships(id) ON DELETE SET NULL,
  user_id uuid REFERENCES network_users(id) ON DELETE SET NULL,
  action text NOT NULL,
  scope_key text,
  resource_type text NOT NULL,
  resource_key text,
  decision text NOT NULL CHECK (decision IN ('ALLOWED', 'DENIED', 'FILTERED', 'ERROR')),
  decision_reason text NOT NULL,
  data_classes text[] NOT NULL DEFAULT ARRAY[]::text[],
  records_accessed integer NOT NULL DEFAULT 0 CHECK (records_accessed >= 0),
  client_address inet,
  user_agent text,
  request_metadata jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(request_metadata) = 'object'),
  PRIMARY KEY (id, occurred_at)
) PARTITION BY RANGE (occurred_at);
CREATE TABLE IF NOT EXISTS network_access_audit_default
  PARTITION OF network_access_audit DEFAULT;
CREATE INDEX IF NOT EXISTS idx_network_access_audit_actor
  ON network_access_audit (user_id, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_network_access_audit_resource
  ON network_access_audit (resource_type, resource_key, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_network_access_audit_denied
  ON network_access_audit (occurred_at DESC) WHERE decision = 'DENIED';

CREATE TABLE IF NOT EXISTS regional_routes (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  region_id uuid NOT NULL REFERENCES network_regions(id) ON DELETE CASCADE,
  route_code text UNIQUE NOT NULL CHECK (route_code ~ '^[A-Z0-9_-]{3,64}$'),
  display_name text NOT NULL,
  origin_port_node_id uuid NOT NULL REFERENCES network_port_nodes(id) ON DELETE RESTRICT,
  destination_port_node_id uuid NOT NULL REFERENCES network_port_nodes(id) ON DELETE RESTRICT,
  route_geometry geography(LineString, 4326),
  nominal_distance_km numeric(10,2) CHECK (nominal_distance_km > 0),
  typical_duration_minutes integer CHECK (typical_duration_minutes > 0),
  route_status text NOT NULL DEFAULT 'ACTIVE'
    CHECK (route_status IN ('ACTIVE', 'SEASONAL', 'LIMITED', 'SUSPENDED', 'RETIRED')),
  source_record_id uuid REFERENCES source_records(id) ON DELETE RESTRICT,
  confidence numeric(5,4) NOT NULL CHECK (confidence BETWEEN 0 AND 1),
  valid_from timestamptz NOT NULL,
  valid_to timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CHECK (origin_port_node_id <> destination_port_node_id),
  CHECK (valid_to IS NULL OR valid_to > valid_from)
);
CREATE INDEX IF NOT EXISTS idx_regional_routes_ports
  ON regional_routes (origin_port_node_id, destination_port_node_id, route_status);
CREATE INDEX IF NOT EXISTS idx_regional_routes_geometry
  ON regional_routes USING gist (route_geometry);

CREATE TABLE IF NOT EXISTS regional_route_segments (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  route_id uuid NOT NULL REFERENCES regional_routes(id) ON DELETE CASCADE,
  segment_sequence integer NOT NULL CHECK (segment_sequence > 0),
  segment_name text NOT NULL,
  segment_geometry geography(LineString, 4326) NOT NULL,
  distance_km numeric(10,2) NOT NULL CHECK (distance_km > 0),
  constraints jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(constraints) = 'object'),
  UNIQUE (route_id, segment_sequence)
);
CREATE INDEX IF NOT EXISTS idx_regional_route_segments_geometry
  ON regional_route_segments USING gist (segment_geometry);

CREATE TABLE IF NOT EXISTS regional_route_statistics (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  route_id uuid NOT NULL REFERENCES regional_routes(id) ON DELETE CASCADE,
  window_start timestamptz NOT NULL,
  window_end timestamptz NOT NULL,
  aggregation_period text NOT NULL CHECK (aggregation_period IN ('HOUR', 'DAY', 'WEEK', 'MONTH', 'QUARTER')),
  vessel_type text NOT NULL DEFAULT 'ALL',
  voyage_count integer NOT NULL CHECK (voyage_count >= 0),
  completed_voyage_count integer NOT NULL CHECK (completed_voyage_count >= 0),
  median_duration_minutes numeric(12,2) CHECK (median_duration_minutes >= 0),
  p90_duration_minutes numeric(12,2) CHECK (p90_duration_minutes >= 0),
  median_delay_minutes numeric(12,2),
  risk_event_count integer NOT NULL DEFAULT 0 CHECK (risk_event_count >= 0),
  port_congestion_minutes numeric(14,2) NOT NULL DEFAULT 0 CHECK (port_congestion_minutes >= 0),
  model_version text NOT NULL,
  source_snapshot jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(source_snapshot) = 'object'),
  calculated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (route_id, window_start, window_end, aggregation_period, vessel_type, model_version),
  CHECK (window_end > window_start),
  CHECK (completed_voyage_count <= voyage_count),
  CHECK (p90_duration_minutes IS NULL OR median_duration_minutes IS NULL OR p90_duration_minutes >= median_duration_minutes)
);
CREATE INDEX IF NOT EXISTS idx_regional_route_stats_window
  ON regional_route_statistics (route_id, window_end DESC, aggregation_period);

CREATE TABLE IF NOT EXISTS cross_port_voyage_links (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  voyage_id uuid NOT NULL REFERENCES voyages(id) ON DELETE CASCADE,
  vessel_entity_id uuid NOT NULL REFERENCES global_entities(id) ON DELETE RESTRICT,
  departure_port_call_id uuid NOT NULL REFERENCES port_calls(id) ON DELETE RESTRICT,
  arrival_port_call_id uuid NOT NULL REFERENCES port_calls(id) ON DELETE RESTRICT,
  route_id uuid REFERENCES regional_routes(id) ON DELETE SET NULL,
  link_method text NOT NULL CHECK (link_method IN ('IDENTIFIER', 'TRACK_CONTINUITY', 'SCHEDULE', 'MANUAL', 'COMBINED')),
  link_confidence numeric(5,4) NOT NULL CHECK (link_confidence BETWEEN 0 AND 1),
  verification_status text NOT NULL DEFAULT 'PENDING'
    CHECK (verification_status IN ('PENDING', 'VERIFIED', 'CONFLICT', 'REJECTED')),
  evidence jsonb NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(evidence) = 'array'),
  linked_at timestamptz NOT NULL DEFAULT now(),
  verified_by text,
  verified_at timestamptz,
  UNIQUE (departure_port_call_id, arrival_port_call_id),
  CHECK (departure_port_call_id <> arrival_port_call_id),
  CHECK ((verification_status = 'VERIFIED') = (verified_by IS NOT NULL AND verified_at IS NOT NULL))
);
CREATE INDEX IF NOT EXISTS idx_cross_port_voyage_links_vessel
  ON cross_port_voyage_links (vessel_entity_id, linked_at DESC);
CREATE INDEX IF NOT EXISTS idx_cross_port_voyage_links_review
  ON cross_port_voyage_links (verification_status, link_confidence DESC);

CREATE TABLE IF NOT EXISTS cross_port_verifications (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  verification_code text UNIQUE NOT NULL CHECK (verification_code ~ '^CPV-[0-9]{4}-[0-9]{5,}$'),
  voyage_link_id uuid NOT NULL REFERENCES cross_port_voyage_links(id) ON DELETE CASCADE,
  departure_port_node_id uuid NOT NULL REFERENCES network_port_nodes(id) ON DELETE RESTRICT,
  arrival_port_node_id uuid NOT NULL REFERENCES network_port_nodes(id) ON DELETE RESTRICT,
  verification_type text NOT NULL
    CHECK (verification_type IN ('VESSEL_IDENTITY', 'CARGO', 'DRAUGHT', 'FUEL', 'ETA', 'DOCUMENTS', 'FULL')),
  verification_status text NOT NULL DEFAULT 'OPEN'
    CHECK (verification_status IN ('OPEN', 'MATCHED', 'MISMATCH', 'IN_REVIEW', 'RESOLVED')),
  checked_fields text[] NOT NULL DEFAULT ARRAY[]::text[],
  mismatch_count integer NOT NULL DEFAULT 0 CHECK (mismatch_count >= 0),
  summary text NOT NULL,
  opened_at timestamptz NOT NULL DEFAULT now(),
  completed_at timestamptz,
  reviewed_by text,
  resolution text,
  CHECK (departure_port_node_id <> arrival_port_node_id),
  CHECK ((verification_status IN ('MATCHED', 'MISMATCH', 'RESOLVED')) = (completed_at IS NOT NULL)),
  CHECK (completed_at IS NULL OR completed_at >= opened_at)
);
CREATE INDEX IF NOT EXISTS idx_cross_port_verifications_queue
  ON cross_port_verifications (verification_status, opened_at, verification_type);

CREATE TABLE IF NOT EXISTS cross_port_verification_items (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  verification_id uuid NOT NULL REFERENCES cross_port_verifications(id) ON DELETE CASCADE,
  field_path text NOT NULL,
  departure_assertion_id uuid REFERENCES provenance_assertions(id) ON DELETE RESTRICT,
  arrival_assertion_id uuid REFERENCES provenance_assertions(id) ON DELETE RESTRICT,
  departure_value jsonb,
  arrival_value jsonb,
  comparison_result text NOT NULL CHECK (comparison_result IN ('MATCH', 'MISMATCH', 'MISSING_DEPARTURE', 'MISSING_ARRIVAL', 'INCOMPARABLE')),
  tolerance jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(tolerance) = 'object'),
  difference jsonb,
  explanation text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (verification_id, field_path),
  CHECK (departure_assertion_id IS NOT NULL OR departure_value IS NOT NULL),
  CHECK (arrival_assertion_id IS NOT NULL OR arrival_value IS NOT NULL)
);
CREATE INDEX IF NOT EXISTS idx_cross_port_verification_items_result
  ON cross_port_verification_items (verification_id, comparison_result);

CREATE TABLE IF NOT EXISTS regional_operational_snapshots (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  region_id uuid NOT NULL REFERENCES network_regions(id) ON DELETE CASCADE,
  snapshot_at timestamptz NOT NULL,
  active_vessels integer NOT NULL CHECK (active_vessels >= 0),
  active_voyages integer NOT NULL CHECK (active_voyages >= 0),
  vessels_waiting integer NOT NULL CHECK (vessels_waiting >= 0),
  high_risk_vessels integer NOT NULL CHECK (high_risk_vessels >= 0),
  active_environmental_events integer NOT NULL CHECK (active_environmental_events >= 0),
  port_metrics jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(port_metrics) = 'object'),
  route_metrics jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(route_metrics) = 'object'),
  source_watermarks jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(source_watermarks) = 'object'),
  calculated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (region_id, snapshot_at)
);
CREATE INDEX IF NOT EXISTS idx_regional_operational_snapshots_time
  ON regional_operational_snapshots (region_id, snapshot_at DESC);

CREATE TABLE IF NOT EXISTS network_event_topics (
  topic_key text PRIMARY KEY CHECK (topic_key ~ '^[a-z][a-z0-9._-]{2,95}$'),
  owning_domain text NOT NULL,
  description text NOT NULL,
  default_classification text NOT NULL
    CHECK (default_classification IN ('PUBLIC', 'OPERATIONAL', 'RESTRICTED', 'SECURITY')),
  retention_days integer NOT NULL CHECK (retention_days > 0),
  enabled boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS network_event_schemas (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  topic_key text NOT NULL REFERENCES network_event_topics(topic_key) ON DELETE CASCADE,
  event_type text NOT NULL,
  schema_version integer NOT NULL CHECK (schema_version > 0),
  json_schema jsonb NOT NULL CHECK (jsonb_typeof(json_schema) = 'object'),
  compatibility_mode text NOT NULL DEFAULT 'BACKWARD'
    CHECK (compatibility_mode IN ('NONE', 'BACKWARD', 'FORWARD', 'FULL')),
  checksum_sha256 varchar(64) NOT NULL CHECK (checksum_sha256 ~ '^[0-9a-f]{64}$'),
  lifecycle_status text NOT NULL DEFAULT 'ACTIVE' CHECK (lifecycle_status IN ('DRAFT', 'ACTIVE', 'DEPRECATED')),
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (topic_key, event_type, schema_version)
);

CREATE TABLE IF NOT EXISTS network_event_envelopes (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  event_code text UNIQUE NOT NULL,
  topic_key text NOT NULL REFERENCES network_event_topics(topic_key) ON DELETE RESTRICT,
  event_schema_id uuid NOT NULL REFERENCES network_event_schemas(id) ON DELETE RESTRICT,
  event_type text NOT NULL,
  aggregate_type text NOT NULL,
  aggregate_key text NOT NULL,
  aggregate_version bigint NOT NULL CHECK (aggregate_version > 0),
  source_port_node_id uuid REFERENCES network_port_nodes(id) ON DELETE SET NULL,
  source_system_id uuid REFERENCES source_systems(id) ON DELETE SET NULL,
  correlation_id uuid NOT NULL,
  causation_id uuid,
  trace_id text NOT NULL,
  data_classification text NOT NULL
    CHECK (data_classification IN ('PUBLIC', 'OPERATIONAL', 'RESTRICTED', 'SECURITY')),
  occurred_at timestamptz NOT NULL,
  recorded_at timestamptz NOT NULL DEFAULT now(),
  payload jsonb NOT NULL CHECK (jsonb_typeof(payload) = 'object'),
  headers jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(headers) = 'object'),
  idempotency_key text UNIQUE NOT NULL,
  CHECK (recorded_at >= occurred_at - interval '7 days')
);
CREATE INDEX IF NOT EXISTS idx_network_events_aggregate
  ON network_event_envelopes (aggregate_type, aggregate_key, aggregate_version);
CREATE INDEX IF NOT EXISTS idx_network_events_topic_time
  ON network_event_envelopes (topic_key, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_network_events_correlation
  ON network_event_envelopes (correlation_id, occurred_at);

CREATE TABLE IF NOT EXISTS network_outbox (
  id bigserial PRIMARY KEY,
  event_id uuid UNIQUE NOT NULL REFERENCES network_event_envelopes(id) ON DELETE CASCADE,
  publication_status text NOT NULL DEFAULT 'PENDING'
    CHECK (publication_status IN ('PENDING', 'PUBLISHING', 'PUBLISHED', 'FAILED', 'DEAD_LETTER')),
  attempt_count integer NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
  next_attempt_at timestamptz NOT NULL DEFAULT now(),
  locked_by text,
  locked_at timestamptz,
  published_at timestamptz,
  last_error text,
  created_at timestamptz NOT NULL DEFAULT now(),
  CHECK ((publication_status = 'PUBLISHED') = (published_at IS NOT NULL)),
  CHECK (locked_at IS NULL OR locked_by IS NOT NULL)
);
CREATE INDEX IF NOT EXISTS idx_network_outbox_pending
  ON network_outbox (next_attempt_at, id)
  WHERE publication_status IN ('PENDING', 'FAILED');

CREATE TABLE IF NOT EXISTS network_inbox (
  id bigserial PRIMARY KEY,
  consumer_group text NOT NULL,
  event_id uuid NOT NULL REFERENCES network_event_envelopes(id) ON DELETE CASCADE,
  processing_status text NOT NULL DEFAULT 'RECEIVED'
    CHECK (processing_status IN ('RECEIVED', 'PROCESSING', 'PROCESSED', 'FAILED', 'DEAD_LETTER')),
  received_at timestamptz NOT NULL DEFAULT now(),
  processed_at timestamptz,
  attempt_count integer NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
  last_error text,
  UNIQUE (consumer_group, event_id),
  CHECK (processed_at IS NULL OR processed_at >= received_at),
  CHECK ((processing_status = 'PROCESSED') = (processed_at IS NOT NULL))
);
CREATE INDEX IF NOT EXISTS idx_network_inbox_work
  ON network_inbox (consumer_group, processing_status, received_at);

CREATE TABLE IF NOT EXISTS network_event_deliveries (
  id bigserial PRIMARY KEY,
  event_id uuid NOT NULL REFERENCES network_event_envelopes(id) ON DELETE CASCADE,
  destination_key text NOT NULL,
  delivery_status text NOT NULL DEFAULT 'PENDING'
    CHECK (delivery_status IN ('PENDING', 'DELIVERED', 'RETRY', 'FAILED', 'SKIPPED')),
  attempt_count integer NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
  first_attempt_at timestamptz,
  last_attempt_at timestamptz,
  delivered_at timestamptz,
  response_code text,
  error_detail text,
  UNIQUE (event_id, destination_key),
  CHECK (last_attempt_at IS NULL OR first_attempt_at IS NULL OR last_attempt_at >= first_attempt_at),
  CHECK ((delivery_status = 'DELIVERED') = (delivered_at IS NOT NULL))
);
CREATE INDEX IF NOT EXISTS idx_network_event_deliveries_retry
  ON network_event_deliveries (delivery_status, last_attempt_at)
  WHERE delivery_status IN ('PENDING', 'RETRY');

CREATE TABLE IF NOT EXISTS network_dead_letters (
  id bigserial PRIMARY KEY,
  event_id uuid NOT NULL REFERENCES network_event_envelopes(id) ON DELETE RESTRICT,
  failed_component text NOT NULL,
  failure_code text NOT NULL,
  failure_detail text NOT NULL,
  payload_snapshot jsonb NOT NULL,
  failed_at timestamptz NOT NULL DEFAULT now(),
  resolution_status text NOT NULL DEFAULT 'OPEN'
    CHECK (resolution_status IN ('OPEN', 'REPLAY_PENDING', 'REPLAYED', 'DISCARDED')),
  resolved_by text,
  resolved_at timestamptz,
  resolution_note text,
  CHECK ((resolution_status IN ('REPLAYED', 'DISCARDED')) = (resolved_by IS NOT NULL AND resolved_at IS NOT NULL))
);
CREATE INDEX IF NOT EXISTS idx_network_dead_letters_queue
  ON network_dead_letters (resolution_status, failed_at);

CREATE TABLE IF NOT EXISTS data_retention_policies (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  policy_key text UNIQUE NOT NULL,
  target_relation text NOT NULL,
  data_classification text NOT NULL
    CHECK (data_classification IN ('PUBLIC', 'OPERATIONAL', 'RESTRICTED', 'SECURITY')),
  retention_days integer NOT NULL CHECK (retention_days > 0),
  terminal_action text NOT NULL CHECK (terminal_action IN ('DELETE', 'ANONYMIZE', 'ARCHIVE')),
  partition_period text CHECK (partition_period IS NULL OR partition_period IN ('DAY', 'MONTH', 'QUARTER', 'YEAR')),
  legal_basis text NOT NULL,
  enabled boolean NOT NULL DEFAULT true,
  approved_by text NOT NULL,
  approved_at timestamptz NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS data_legal_holds (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  hold_code text UNIQUE NOT NULL,
  resource_type text NOT NULL,
  resource_key text NOT NULL,
  reason text NOT NULL,
  placed_by text NOT NULL,
  placed_at timestamptz NOT NULL DEFAULT now(),
  expires_at timestamptz,
  released_by text,
  released_at timestamptz,
  release_note text,
  CHECK (expires_at IS NULL OR expires_at > placed_at),
  CHECK (released_at IS NULL OR (released_by IS NOT NULL AND released_at >= placed_at))
);
CREATE INDEX IF NOT EXISTS idx_data_legal_holds_active
  ON data_legal_holds (resource_type, resource_key, placed_at DESC)
  WHERE released_at IS NULL;

CREATE TABLE IF NOT EXISTS data_retention_runs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  policy_id uuid NOT NULL REFERENCES data_retention_policies(id) ON DELETE RESTRICT,
  run_status text NOT NULL CHECK (run_status IN ('RUNNING', 'SUCCEEDED', 'PARTIAL', 'FAILED', 'CANCELLED')),
  cutoff_at timestamptz NOT NULL,
  started_at timestamptz NOT NULL DEFAULT now(),
  completed_at timestamptz,
  scanned_records bigint NOT NULL DEFAULT 0 CHECK (scanned_records >= 0),
  affected_records bigint NOT NULL DEFAULT 0 CHECK (affected_records >= 0),
  held_records bigint NOT NULL DEFAULT 0 CHECK (held_records >= 0),
  error_detail text,
  CHECK (completed_at IS NULL OR completed_at >= started_at),
  CHECK (affected_records + held_records <= scanned_records)
);
CREATE INDEX IF NOT EXISTS idx_data_retention_runs_policy
  ON data_retention_runs (policy_id, started_at DESC);

CREATE TABLE IF NOT EXISTS observability_services (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  service_key text UNIQUE NOT NULL CHECK (service_key ~ '^[a-z][a-z0-9._-]{2,63}$'),
  display_name text NOT NULL,
  service_domain text NOT NULL,
  owning_team text NOT NULL,
  criticality text NOT NULL CHECK (criticality IN ('TIER_0', 'TIER_1', 'TIER_2', 'TIER_3')),
  health_endpoint text,
  runbook_url text,
  enabled boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS observability_metrics (
  id bigint GENERATED ALWAYS AS IDENTITY,
  observed_at timestamptz NOT NULL,
  service_id uuid NOT NULL REFERENCES observability_services(id) ON DELETE CASCADE,
  metric_name text NOT NULL,
  metric_value double precision NOT NULL,
  metric_unit text NOT NULL,
  labels jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(labels) = 'object'),
  trace_id text,
  PRIMARY KEY (id, observed_at)
) PARTITION BY RANGE (observed_at);
CREATE TABLE IF NOT EXISTS observability_metrics_default
  PARTITION OF observability_metrics DEFAULT;
CREATE INDEX IF NOT EXISTS idx_observability_metrics_series
  ON observability_metrics (service_id, metric_name, observed_at DESC);

CREATE TABLE IF NOT EXISTS observability_health_checks (
  id bigserial PRIMARY KEY,
  service_id uuid NOT NULL REFERENCES observability_services(id) ON DELETE CASCADE,
  port_node_id uuid REFERENCES network_port_nodes(id) ON DELETE CASCADE,
  checked_at timestamptz NOT NULL DEFAULT now(),
  health_status text NOT NULL CHECK (health_status IN ('HEALTHY', 'DEGRADED', 'UNHEALTHY', 'UNKNOWN')),
  latency_ms integer CHECK (latency_ms >= 0),
  source_watermark timestamptz,
  lag_seconds integer CHECK (lag_seconds >= 0),
  details jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(details) = 'object')
);
CREATE INDEX IF NOT EXISTS idx_observability_health_latest
  ON observability_health_checks (service_id, port_node_id, checked_at DESC);
CREATE INDEX IF NOT EXISTS idx_observability_health_problems
  ON observability_health_checks (checked_at DESC)
  WHERE health_status IN ('DEGRADED', 'UNHEALTHY');

CREATE TABLE IF NOT EXISTS observability_incidents (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  incident_code text UNIQUE NOT NULL CHECK (incident_code ~ '^INC-[0-9]{4}-[0-9]{5,}$'),
  service_id uuid NOT NULL REFERENCES observability_services(id) ON DELETE RESTRICT,
  port_node_id uuid REFERENCES network_port_nodes(id) ON DELETE SET NULL,
  severity text NOT NULL CHECK (severity IN ('SEV1', 'SEV2', 'SEV3', 'SEV4')),
  incident_status text NOT NULL DEFAULT 'OPEN'
    CHECK (incident_status IN ('OPEN', 'ACKNOWLEDGED', 'MITIGATED', 'RESOLVED')),
  title text NOT NULL,
  description text NOT NULL,
  correlation_id uuid,
  opened_at timestamptz NOT NULL DEFAULT now(),
  acknowledged_at timestamptz,
  resolved_at timestamptz,
  owner text,
  resolution text,
  CHECK (acknowledged_at IS NULL OR acknowledged_at >= opened_at),
  CHECK (resolved_at IS NULL OR resolved_at >= opened_at),
  CHECK ((incident_status = 'RESOLVED') = (resolved_at IS NOT NULL))
);
CREATE INDEX IF NOT EXISTS idx_observability_incidents_queue
  ON observability_incidents (incident_status, severity, opened_at);

INSERT INTO network_regions
  (region_code, display_name, default_timezone, default_locale, data_residency_country, configuration)
VALUES
  ('CASPIAN', 'Caspian Intelligence Network', 'Asia/Aqtau', 'ru-KZ', 'KZ',
   '{"clock":"UTC","supported_locales":["ru-KZ","kk-KZ","en"],"geometry_srid":4326}'::jsonb)
ON CONFLICT (region_code) DO NOTHING;

INSERT INTO integration_adapter_definitions
  (adapter_key, display_name, data_domain, protocol, delivery_mode, adapter_version, input_schema_version, configuration_schema, supports_replay)
VALUES
  ('ais-rest-v1', 'Provider-neutral AIS REST adapter', 'AIS', 'REST', 'PULL', '1.0.0', 'ais-position-1.0', '{"type":"object","required":["endpoint","secret_reference"]}'::jsonb, true),
  ('port-pcs-rest-v1', 'Port PCS/TOS REST adapter', 'PORT', 'REST', 'BIDIRECTIONAL', '1.0.0', 'port-operations-1.0', '{"type":"object","required":["endpoint","external_port_key","secret_reference"]}'::jsonb, true),
  ('weather-rest-v1', 'Marine weather REST adapter', 'WEATHER', 'REST', 'PULL', '1.0.0', 'marine-weather-1.0', '{"type":"object","required":["endpoint","secret_reference"]}'::jsonb, true),
  ('registry-file-v1', 'Registry controlled file adapter', 'REGISTRY', 'FILE', 'BATCH', '1.0.0', 'registry-record-1.0', '{"type":"object","required":["storage_reference"]}'::jsonb, true)
ON CONFLICT (adapter_key) DO NOTHING;

INSERT INTO permission_scopes (scope_key, data_domain, action, sensitivity, description) VALUES
  ('network:overview:read', 'NETWORK', 'READ', 'OPERATIONAL', 'Regional network overview'),
  ('network:identity:read', 'IDENTITY', 'READ', 'RESTRICTED', 'Global entity identities and provenance'),
  ('network:identity:resolve', 'IDENTITY', 'WRITE', 'SECURITY', 'Resolve identity matches and conflicts'),
  ('network:ports:read', 'PORT', 'READ', 'OPERATIONAL', 'Authorized multi-port operational data'),
  ('network:ports:operate', 'PORT', 'WRITE', 'RESTRICTED', 'Port-scoped operational changes'),
  ('network:verification:read', 'VERIFICATION', 'READ', 'RESTRICTED', 'Cross-port verification results'),
  ('network:verification:review', 'VERIFICATION', 'WRITE', 'SECURITY', 'Review cross-port discrepancies'),
  ('network:audit:read', 'AUDIT', 'READ', 'SECURITY', 'Access audit and security decisions'),
  ('network:config:admin', 'CONFIGURATION', 'ADMINISTER', 'SECURITY', 'Versioned regional configuration')
ON CONFLICT (scope_key) DO NOTHING;

INSERT INTO network_event_topics
  (topic_key, owning_domain, description, default_classification, retention_days)
VALUES
  ('ci.vessel.identity', 'IDENTITY', 'Canonical vessel identity changes', 'RESTRICTED', 730),
  ('ci.voyage.lifecycle', 'VOYAGE', 'Cross-port voyage lifecycle', 'OPERATIONAL', 365),
  ('ci.port.operations', 'PORT', 'PortCall and berth operation changes', 'OPERATIONAL', 365),
  ('ci.risk.assessment', 'RISK', 'Explainable risk assessment changes', 'SECURITY', 730),
  ('ci.environment.event', 'ENVIRONMENT', 'Environmental event lifecycle', 'SECURITY', 730),
  ('ci.network.verification', 'VERIFICATION', 'Cross-port verification changes', 'RESTRICTED', 730)
ON CONFLICT (topic_key) DO NOTHING;

INSERT INTO data_retention_policies
  (policy_key, target_relation, data_classification, retention_days, terminal_action, partition_period, legal_basis, approved_by, approved_at)
VALUES
  ('network-access-audit-7y', 'network_access_audit', 'SECURITY', 2557, 'ARCHIVE', 'MONTH', 'Security audit and accountability', 'platform-governance', now()),
  ('observability-metrics-90d', 'observability_metrics', 'OPERATIONAL', 90, 'DELETE', 'MONTH', 'Operational telemetry lifecycle', 'platform-governance', now()),
  ('source-records-2y', 'source_records', 'RESTRICTED', 730, 'ARCHIVE', 'MONTH', 'Source provenance and dispute resolution', 'platform-governance', now()),
  ('event-envelopes-1y', 'network_event_envelopes', 'OPERATIONAL', 365, 'ARCHIVE', 'Reliable replay and integration audit', 'platform-governance', now())
ON CONFLICT (policy_key) DO NOTHING;

-- Stage 9: Environmental Intelligence.
-- Provider payloads, observations, reconstructed origin areas and inferred
-- vessel associations are intentionally stored as separate evidence layers.

CREATE TABLE IF NOT EXISTS environmental_data_providers (
  provider_key text PRIMARY KEY,
  display_name text NOT NULL,
  input_mode text NOT NULL CHECK (input_mode IN ('EXTERNAL_API', 'PREPROCESSED_SATELLITE', 'MANUAL', 'DEMO')),
  enabled boolean NOT NULL DEFAULT true,
  configuration jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS environmental_raw_data (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  provider_key text NOT NULL REFERENCES environmental_data_providers(provider_key),
  external_reference text,
  observed_at timestamptz NOT NULL,
  received_at timestamptz NOT NULL DEFAULT now(),
  source_uri text,
  source_bbox geometry(Polygon, 4326),
  payload jsonb NOT NULL,
  payload_sha256 text,
  processing_status text NOT NULL DEFAULT 'RECEIVED'
    CHECK (processing_status IN ('RECEIVED', 'NORMALIZED', 'PROCESSED', 'REJECTED')),
  processing_notes text,
  UNIQUE (provider_key, external_reference)
);
CREATE INDEX IF NOT EXISTS idx_environment_raw_provider_time
  ON environmental_raw_data (provider_key, observed_at DESC);
CREATE INDEX IF NOT EXISTS idx_environment_raw_bbox
  ON environmental_raw_data USING gist (source_bbox);

CREATE TABLE IF NOT EXISTS environmental_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  event_code text UNIQUE NOT NULL,
  short_code text UNIQUE,
  event_type text NOT NULL
    CHECK (event_type IN ('OIL_POLLUTION', 'CHEMICAL_POLLUTION', 'FLOATING_WASTE', 'ALGAE_BLOOM', 'UNKNOWN_POLLUTION')),
  detected_at timestamptz NOT NULL,
  estimated_started_at timestamptz,
  estimated_ended_at timestamptz,
  affected_geometry geometry(Geometry, 4326) NOT NULL,
  center geography(Point, 4326) NOT NULL,
  area_km2 numeric NOT NULL CHECK (area_km2 > 0),
  detection_source text NOT NULL,
  raw_observation_id uuid REFERENCES environmental_raw_data(id) ON DELETE SET NULL,
  confidence numeric NOT NULL CHECK (confidence BETWEEN 0 AND 1),
  status text NOT NULL DEFAULT 'DETECTED'
    CHECK (status IN ('DETECTED', 'ANALYZING', 'UNDER REVIEW', 'INVESTIGATION', 'RESOLVED', 'FALSE POSITIVE')),
  environmental_data jsonb NOT NULL DEFAULT '{}'::jsonb,
  provenance text NOT NULL DEFAULT 'OBSERVED'
    CHECK (provenance IN ('OBSERVED', 'ESTIMATED', 'INFERRED')),
  model_version text NOT NULL DEFAULT 'CI-ENV-1.0',
  created_by text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CHECK (GeometryType(affected_geometry) IN ('POLYGON', 'MULTIPOLYGON')),
  CHECK (estimated_ended_at IS NULL OR estimated_started_at IS NULL OR estimated_ended_at >= estimated_started_at)
);
CREATE INDEX IF NOT EXISTS idx_environment_events_geometry
  ON environmental_events USING gist (affected_geometry);
CREATE INDEX IF NOT EXISTS idx_environment_events_center
  ON environmental_events USING gist (center);
CREATE INDEX IF NOT EXISTS idx_environment_events_queue
  ON environmental_events (status, detected_at DESC);

CREATE TABLE IF NOT EXISTS environmental_observations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  event_id uuid NOT NULL REFERENCES environmental_events(id) ON DELETE CASCADE,
  observation_type text NOT NULL
    CHECK (observation_type IN ('SATELLITE_DETECTION', 'OIL_INDEX', 'WIND', 'CURRENT', 'WEATHER', 'SEA_STATE', 'CLOUD_COVER')),
  observed_at timestamptz NOT NULL,
  observation_geometry geometry(Geometry, 4326),
  numeric_value numeric,
  unit text,
  direction_deg numeric CHECK (direction_deg IS NULL OR direction_deg BETWEEN 0 AND 360),
  speed_value numeric CHECK (speed_value IS NULL OR speed_value >= 0),
  details jsonb NOT NULL DEFAULT '{}'::jsonb,
  provenance text NOT NULL CHECK (provenance IN ('OBSERVED', 'ESTIMATED', 'INFERRED')),
  confidence numeric NOT NULL CHECK (confidence BETWEEN 0 AND 1),
  raw_observation_id uuid REFERENCES environmental_raw_data(id) ON DELETE SET NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_environment_observations_event_time
  ON environmental_observations (event_id, observed_at);
CREATE INDEX IF NOT EXISTS idx_environment_observations_geometry
  ON environmental_observations USING gist (observation_geometry);

CREATE TABLE IF NOT EXISTS environmental_reconstructions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  event_id uuid NOT NULL REFERENCES environmental_events(id) ON DELETE CASCADE,
  reconstruction_code text UNIQUE NOT NULL,
  model_version text NOT NULL DEFAULT 'CI-ENV-RECON-1.0',
  interval_started_at timestamptz NOT NULL,
  interval_ended_at timestamptz NOT NULL,
  origin_geometry_start geometry(Geometry, 4326) NOT NULL,
  origin_geometry_end geometry(Geometry, 4326) NOT NULL,
  weather_observation_ids uuid[] NOT NULL DEFAULT ARRAY[]::uuid[],
  current_observation_ids uuid[] NOT NULL DEFAULT ARRAY[]::uuid[],
  parameters jsonb NOT NULL DEFAULT '{}'::jsonb,
  confidence numeric NOT NULL CHECK (confidence BETWEEN 0 AND 1),
  provenance text NOT NULL DEFAULT 'ESTIMATED' CHECK (provenance = 'ESTIMATED'),
  explanation text NOT NULL,
  disclaimer text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  CHECK (interval_ended_at >= interval_started_at),
  CHECK (GeometryType(origin_geometry_start) IN ('POLYGON', 'MULTIPOLYGON')),
  CHECK (GeometryType(origin_geometry_end) IN ('POLYGON', 'MULTIPOLYGON'))
);
CREATE INDEX IF NOT EXISTS idx_environment_reconstructions_event
  ON environmental_reconstructions (event_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_environment_reconstructions_origin_start
  ON environmental_reconstructions USING gist (origin_geometry_start);
CREATE INDEX IF NOT EXISTS idx_environment_reconstructions_origin_end
  ON environmental_reconstructions USING gist (origin_geometry_end);

CREATE TABLE IF NOT EXISTS environmental_reconstruction_steps (
  reconstruction_id uuid NOT NULL REFERENCES environmental_reconstructions(id) ON DELETE CASCADE,
  step_sequence integer NOT NULL CHECK (step_sequence >= 0),
  reconstructed_at timestamptz NOT NULL,
  probable_area geometry(Geometry, 4326) NOT NULL,
  centroid geography(Point, 4326) NOT NULL,
  wind_vector jsonb NOT NULL DEFAULT '{}'::jsonb,
  current_vector jsonb NOT NULL DEFAULT '{}'::jsonb,
  PRIMARY KEY (reconstruction_id, step_sequence),
  CHECK (GeometryType(probable_area) IN ('POLYGON', 'MULTIPOLYGON'))
);
CREATE INDEX IF NOT EXISTS idx_environment_reconstruction_steps_geometry
  ON environmental_reconstruction_steps USING gist (probable_area);

CREATE TABLE IF NOT EXISTS environmental_candidate_searches (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  event_id uuid NOT NULL REFERENCES environmental_events(id) ON DELETE CASCADE,
  reconstruction_id uuid NOT NULL REFERENCES environmental_reconstructions(id) ON DELETE RESTRICT,
  window_started_at timestamptz NOT NULL,
  window_ended_at timestamptz NOT NULL,
  search_geometry geometry(Geometry, 4326) NOT NULL,
  extended_candidate_count integer NOT NULL CHECK (extended_candidate_count >= 0),
  relevant_candidate_count integer NOT NULL CHECK (relevant_candidate_count >= 0),
  model_version text NOT NULL DEFAULT 'CI-ENV-ASSOC-1.0',
  created_at timestamptz NOT NULL DEFAULT now(),
  CHECK (window_ended_at >= window_started_at),
  CHECK (relevant_candidate_count <= extended_candidate_count)
);
CREATE INDEX IF NOT EXISTS idx_environment_candidate_search_geometry
  ON environmental_candidate_searches USING gist (search_geometry);

CREATE TABLE IF NOT EXISTS environmental_candidate_vessels (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  event_id uuid NOT NULL REFERENCES environmental_events(id) ON DELETE CASCADE,
  search_id uuid NOT NULL REFERENCES environmental_candidate_searches(id) ON DELETE CASCADE,
  vessel_id uuid NOT NULL REFERENCES vessels(id) ON DELETE RESTRICT,
  candidate_rank integer NOT NULL CHECK (candidate_rank > 0),
  relevance text NOT NULL CHECK (relevance IN ('HIGH', 'MEDIUM', 'LOW')),
  association_score numeric NOT NULL CHECK (association_score BETWEEN 0 AND 1),
  closest_distance_km numeric NOT NULL CHECK (closest_distance_km >= 0),
  time_overlap_percent numeric NOT NULL CHECK (time_overlap_percent BETWEEN 0 AND 100),
  ais_gap_present boolean NOT NULL DEFAULT false,
  direction_consistency numeric CHECK (direction_consistency BETWEEN 0 AND 1),
  route_consistency numeric CHECK (route_consistency BETWEEN 0 AND 1),
  vessel_type_consistency numeric CHECK (vessel_type_consistency BETWEEN 0 AND 1),
  track_geometry geometry(LineString, 4326),
  factor_evidence jsonb NOT NULL DEFAULT '[]'::jsonb,
  association_statement text NOT NULL,
  provenance text NOT NULL DEFAULT 'INFERRED' CHECK (provenance = 'INFERRED'),
  disclaimer text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (event_id, vessel_id)
);
CREATE INDEX IF NOT EXISTS idx_environment_candidates_rank
  ON environmental_candidate_vessels (event_id, candidate_rank);
CREATE INDEX IF NOT EXISTS idx_environment_candidates_vessel
  ON environmental_candidate_vessels (vessel_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_environment_candidates_track
  ON environmental_candidate_vessels USING gist (track_geometry);

CREATE TABLE IF NOT EXISTS environmental_reviews (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  event_id uuid NOT NULL REFERENCES environmental_events(id) ON DELETE CASCADE,
  decision text NOT NULL
    CHECK (decision IN ('CONFIRMED POLLUTION', 'LIKELY POLLUTION', 'UNCERTAIN', 'FALSE POSITIVE')),
  source_assessment text NOT NULL
    CHECK (source_assessment IN ('UNKNOWN', 'VERIFIED EXTERNAL FINDING')),
  status_after text NOT NULL
    CHECK (status_after IN ('UNDER REVIEW', 'INVESTIGATION', 'RESOLVED', 'FALSE POSITIVE')),
  note text,
  reviewed_by text NOT NULL,
  reviewed_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_environment_reviews_event_time
  ON environmental_reviews (event_id, reviewed_at DESC);

CREATE TABLE IF NOT EXISTS environmental_replay_frames (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  event_id uuid NOT NULL REFERENCES environmental_events(id) ON DELETE CASCADE,
  frame_sequence integer NOT NULL CHECK (frame_sequence >= 0),
  frame_at timestamptz NOT NULL,
  reconstructed_area geometry(Geometry, 4326),
  vessel_states jsonb NOT NULL DEFAULT '[]'::jsonb,
  wind_vector jsonb NOT NULL DEFAULT '{}'::jsonb,
  current_vector jsonb NOT NULL DEFAULT '{}'::jsonb,
  provenance text NOT NULL CHECK (provenance IN ('OBSERVED', 'ESTIMATED', 'INFERRED')),
  UNIQUE (event_id, frame_sequence)
);
CREATE INDEX IF NOT EXISTS idx_environment_replay_event_time
  ON environmental_replay_frames (event_id, frame_at);
CREATE INDEX IF NOT EXISTS idx_environment_replay_geometry
  ON environmental_replay_frames USING gist (reconstructed_area);

CREATE TABLE IF NOT EXISTS environmental_risk_context (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  event_id uuid NOT NULL REFERENCES environmental_events(id) ON DELETE CASCADE,
  candidate_id uuid NOT NULL REFERENCES environmental_candidate_vessels(id) ON DELETE CASCADE,
  vessel_id uuid NOT NULL REFERENCES vessels(id) ON DELETE RESTRICT,
  maritime_risk_score integer NOT NULL CHECK (maritime_risk_score BETWEEN 0 AND 100),
  environmental_adjustment_raw integer NOT NULL CHECK (environmental_adjustment_raw BETWEEN 0 AND 100),
  environmental_adjustment_effective integer NOT NULL CHECK (environmental_adjustment_effective BETWEEN 0 AND 100),
  combined_context_score integer NOT NULL CHECK (combined_context_score BETWEEN 0 AND 100),
  model_version text NOT NULL DEFAULT 'CI-ENV-RISK-1.0',
  review_required boolean NOT NULL DEFAULT true,
  explanation text NOT NULL,
  disclaimer text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (event_id, vessel_id)
);
CREATE INDEX IF NOT EXISTS idx_environment_risk_vessel
  ON environmental_risk_context (vessel_id, created_at DESC);

CREATE TABLE IF NOT EXISTS environmental_risk_factors (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  risk_context_id uuid NOT NULL REFERENCES environmental_risk_context(id) ON DELETE CASCADE,
  factor_code text NOT NULL
    CHECK (factor_code IN ('ENVIRONMENTAL_PROXIMITY', 'ENVIRONMENTAL_TIME_OVERLAP', 'ENVIRONMENTAL_ROUTE_MATCH', 'ENVIRONMENTAL_ASSOCIATION')),
  raw_contribution integer NOT NULL CHECK (raw_contribution BETWEEN 0 AND 100),
  effective_contribution integer NOT NULL CHECK (effective_contribution BETWEEN 0 AND raw_contribution),
  provenance text NOT NULL CHECK (provenance IN ('OBSERVED', 'ESTIMATED', 'INFERRED')),
  observed_value text NOT NULL,
  explanation text NOT NULL,
  evidence jsonb NOT NULL DEFAULT '[]'::jsonb,
  review_status text NOT NULL DEFAULT 'UNDER REVIEW'
    CHECK (review_status IN ('UNDER REVIEW', 'REVIEWED', 'DISMISSED')),
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (risk_context_id, factor_code)
);
CREATE INDEX IF NOT EXISTS idx_environment_risk_factors_context
  ON environmental_risk_factors (risk_context_id, factor_code);

CREATE TABLE IF NOT EXISTS environmental_event_outbox (
  id bigserial PRIMARY KEY,
  event_id uuid NOT NULL REFERENCES environmental_events(id) ON DELETE CASCADE,
  message_type text NOT NULL
    CHECK (message_type IN ('environmental_event_detected', 'environmental_event_updated', 'environmental_candidate_updated')),
  payload jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  published_at timestamptz
);
CREATE INDEX IF NOT EXISTS idx_environment_outbox_pending
  ON environmental_event_outbox (created_at) WHERE published_at IS NULL;

ALTER TABLE investigations
  ADD COLUMN IF NOT EXISTS case_type text NOT NULL DEFAULT 'MARITIME';
ALTER TABLE investigations
  ADD COLUMN IF NOT EXISTS environmental_event_id uuid REFERENCES environmental_events(id) ON DELETE SET NULL;
ALTER TABLE assistant_conversations
  ADD COLUMN IF NOT EXISTS environmental_event_id uuid REFERENCES environmental_events(id) ON DELETE SET NULL;

CREATE TABLE IF NOT EXISTS investigation_environmental_evidence (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  investigation_id uuid NOT NULL REFERENCES investigations(id) ON DELETE CASCADE,
  environmental_event_id uuid NOT NULL REFERENCES environmental_events(id) ON DELETE RESTRICT,
  source_type text NOT NULL
    CHECK (source_type IN ('SATELLITE_DETECTION', 'AFFECTED_POLYGON', 'WEATHER', 'CURRENT', 'RECONSTRUCTION', 'AIS_TRACK', 'CANDIDATE', 'AIS_GAP', 'VOYAGE_EVENT')),
  source_key text NOT NULL,
  claim_kind text NOT NULL CHECK (claim_kind IN ('FACT', 'ESTIMATE', 'INFERENCE')),
  source_snapshot jsonb NOT NULL,
  internal_href text NOT NULL CHECK (internal_href LIKE '/app/%'),
  added_by text NOT NULL,
  added_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (investigation_id, source_type, source_key)
);
CREATE INDEX IF NOT EXISTS idx_investigation_environment_event
  ON investigation_environmental_evidence (environmental_event_id, investigation_id);

INSERT INTO environmental_data_providers (provider_key, display_name, input_mode, configuration) VALUES
  ('demo-satellite', 'Demo preprocessed satellite product', 'DEMO', '{"adapter":"provider-neutral","stores_raw":true}'::jsonb),
  ('manual-review', 'Authorized analyst input', 'MANUAL', '{"requires_role":"ANALYST"}'::jsonb)
ON CONFLICT (provider_key) DO NOTHING;

INSERT INTO assistant_tool_registry (tool_name, description, tool_mode, permission_scope, requires_confirmation) VALUES
  ('get_environmental_event', 'Grounded environmental event record', 'READ', 'environment:security', false),
  ('get_environmental_candidates', 'Ranked possible vessel associations', 'READ', 'environment:security', false),
  ('get_environmental_reconstruction', 'Wind/current backward reconstruction', 'READ', 'environment:security', false),
  ('get_environmental_timeline', 'Environmental evidence timeline and replay', 'READ', 'environment:security', false)
ON CONFLICT (tool_name) DO NOTHING;

INSERT INTO assistant_tool_role_permissions (tool_name, role_name, allowed, data_scope)
SELECT tools.tool_name, roles.role_name,
  roles.role_name IN ('ADMIN', 'ANALYST'),
  CASE
    WHEN roles.role_name IN ('ADMIN', 'ANALYST') THEN '{"scope":"environmental_investigation"}'::jsonb
    ELSE '{"scope":"none","security_details":false}'::jsonb
  END
FROM (VALUES
  ('get_environmental_event'),
  ('get_environmental_candidates'),
  ('get_environmental_reconstruction'),
  ('get_environmental_timeline')
) AS tools(tool_name)
CROSS JOIN (VALUES ('ADMIN'), ('ANALYST'), ('VIEWER'), ('PORT_DISPATCHER')) AS roles(role_name)
ON CONFLICT (tool_name, role_name) DO UPDATE SET
  allowed = EXCLUDED.allowed,
  data_scope = EXCLUDED.data_scope,
  updated_at = now();
