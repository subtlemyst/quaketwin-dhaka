-- QuakeTwin Dhaka — Phase 0 graph schema (PostGIS)
-- Run: psql -d quaketwin -f data/schema/dhaka_graph.sql

CREATE EXTENSION IF NOT EXISTS postgis;

-- ---------------------------------------------------------------------------
-- Buildings: core unit of analysis for thesis digital twin
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS buildings (
    building_id       BIGINT PRIMARY KEY,
    geom              GEOMETRY(POLYGON, 4326) NOT NULL,
    construction_type VARCHAR(64),
    height_m          REAL,
    age_years         INTEGER,
    occupancy_type    VARCHAR(64),
    population_est    INTEGER,
    soil_zone_code    VARCHAR(8),
    dist_fault_km     REAL,
    liquefaction_index REAL,
    dist_hospital_m   REAL,
    road_width_m      REAL,
    dist_open_space_m REAL,
    bridge_dependency BOOLEAN DEFAULT FALSE,
    power_grid_dep    BOOLEAN DEFAULT FALSE,
  -- Phase 2+ outputs (nullable until models are trained)
    collapse_probability REAL,
    fire_probability     REAL,
    rescue_difficulty    REAL,
    recovery_priority    REAL,
    metadata          JSONB DEFAULT '{}'::jsonb,
    created_at        TIMESTAMPTZ DEFAULT NOW(),
    updated_at        TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_buildings_geom ON buildings USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_buildings_soil ON buildings (soil_zone_code);

-- ---------------------------------------------------------------------------
-- Road network (OSM-derived)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS roads (
    road_id           BIGINT PRIMARY KEY,
    geom              GEOMETRY(LINESTRING, 4326) NOT NULL,
    road_class        VARCHAR(32),
    width_m           REAL,
    lanes             SMALLINT,
    bridge            BOOLEAN DEFAULT FALSE,
    surface           VARCHAR(32),
    metadata          JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_roads_geom ON roads USING GIST (geom);

-- ---------------------------------------------------------------------------
-- Emergency facilities
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS hospitals (
    facility_id       BIGINT PRIMARY KEY,
    name              VARCHAR(256),
    geom              GEOMETRY(POINT, 4326) NOT NULL,
    beds              INTEGER,
    emergency_capacity INTEGER,
    facility_type     VARCHAR(64) DEFAULT 'hospital',
    metadata          JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_hospitals_geom ON hospitals USING GIST (geom);

CREATE TABLE IF NOT EXISTS shelters (
    shelter_id        BIGINT PRIMARY KEY,
    name              VARCHAR(256),
    geom              GEOMETRY(POINT, 4326) NOT NULL,
    capacity          INTEGER,
    open_space_m2     REAL,
    metadata          JSONB DEFAULT '{}'::jsonb
);

-- ---------------------------------------------------------------------------
-- Infrastructure nodes for cascade analysis (Phase 5+)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS infrastructure_nodes (
    node_id           BIGINT PRIMARY KEY,
    node_type         VARCHAR(64) NOT NULL,  -- substation, cell_tower, pump_station
    geom              GEOMETRY(POINT, 4326) NOT NULL,
    dependency_group  VARCHAR(64),
    metadata          JSONB DEFAULT '{}'::jsonb
);

-- ---------------------------------------------------------------------------
-- Hazard scenario runs (Phase 1)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS hazard_scenarios (
    scenario_id       VARCHAR(64) PRIMARY KEY,
    magnitude         REAL NOT NULL,
    magnitude_type    VARCHAR(8) DEFAULT 'Mw',
    epicenter         GEOMETRY(POINT, 4326) NOT NULL,
    depth_km          REAL NOT NULL,
    fault_name        VARCHAR(128),
    time_of_day       VARCHAR(16),
    season            VARCHAR(32),
    parameters        JSONB DEFAULT '{}'::jsonb,
    created_at        TIMESTAMPTZ DEFAULT NOW()
);

-- Raster-style hazard cells stored as points with attributes (GeoJSON-friendly)
CREATE TABLE IF NOT EXISTS hazard_cells (
    id                BIGSERIAL PRIMARY KEY,
    scenario_id       VARCHAR(64) REFERENCES hazard_scenarios(scenario_id),
    geom              GEOMETRY(POINT, 4326) NOT NULL,
    pga_g             REAL,           -- peak ground acceleration (g)
    mmi               REAL,             -- modified mercalli intensity
    amplified_pga_g   REAL,
    liquefaction_index REAL,
    soil_zone_code    VARCHAR(8),
    UNIQUE (scenario_id, geom)
);

CREATE INDEX IF NOT EXISTS idx_hazard_cells_scenario ON hazard_cells (scenario_id);
CREATE INDEX IF NOT EXISTS idx_hazard_cells_geom ON hazard_cells USING GIST (geom);

-- ---------------------------------------------------------------------------
-- Data provenance for thesis methodology chapter
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS data_sources (
    source_id         SERIAL PRIMARY KEY,
    layer_name        VARCHAR(64) NOT NULL,
    source_name       VARCHAR(256) NOT NULL,
    source_url        TEXT,
    license           VARCHAR(128),
    retrieval_date    DATE,
    notes             TEXT
);
