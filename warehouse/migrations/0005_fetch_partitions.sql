-- Monthly partitions so a new calendar month does not break the warehouse.
CREATE TABLE IF NOT EXISTS fetch_observation_2026m10 PARTITION OF fetch_observation
    FOR VALUES FROM ('2026-10-01') TO ('2026-11-01');
CREATE TABLE IF NOT EXISTS fetch_observation_2026m11 PARTITION OF fetch_observation
    FOR VALUES FROM ('2026-11-01') TO ('2026-12-01');
CREATE TABLE IF NOT EXISTS fetch_observation_2026m12 PARTITION OF fetch_observation
    FOR VALUES FROM ('2026-12-01') TO ('2027-01-01');
CREATE TABLE IF NOT EXISTS fetch_observation_2027m01 PARTITION OF fetch_observation
    FOR VALUES FROM ('2027-01-01') TO ('2027-02-01');
CREATE TABLE IF NOT EXISTS fetch_observation_2027m02 PARTITION OF fetch_observation
    FOR VALUES FROM ('2027-02-01') TO ('2027-03-01');
CREATE TABLE IF NOT EXISTS fetch_observation_2027m03 PARTITION OF fetch_observation
    FOR VALUES FROM ('2027-03-01') TO ('2027-04-01');
CREATE TABLE IF NOT EXISTS fetch_observation_2027m04 PARTITION OF fetch_observation
    FOR VALUES FROM ('2027-04-01') TO ('2027-05-01');
CREATE TABLE IF NOT EXISTS fetch_observation_2027m05 PARTITION OF fetch_observation
    FOR VALUES FROM ('2027-05-01') TO ('2027-06-01');
CREATE TABLE IF NOT EXISTS fetch_observation_2027m06 PARTITION OF fetch_observation
    FOR VALUES FROM ('2027-06-01') TO ('2027-07-01');
CREATE TABLE IF NOT EXISTS fetch_observation_2027m07 PARTITION OF fetch_observation
    FOR VALUES FROM ('2027-07-01') TO ('2027-08-01');
CREATE TABLE IF NOT EXISTS fetch_observation_2027m08 PARTITION OF fetch_observation
    FOR VALUES FROM ('2027-08-01') TO ('2027-09-01');
CREATE TABLE IF NOT EXISTS fetch_observation_2027m09 PARTITION OF fetch_observation
    FOR VALUES FROM ('2027-09-01') TO ('2027-10-01');
CREATE TABLE IF NOT EXISTS fetch_observation_2027m10 PARTITION OF fetch_observation
    FOR VALUES FROM ('2027-10-01') TO ('2027-11-01');
CREATE TABLE IF NOT EXISTS fetch_observation_2027m11 PARTITION OF fetch_observation
    FOR VALUES FROM ('2027-11-01') TO ('2027-12-01');
CREATE TABLE IF NOT EXISTS fetch_observation_2027m12 PARTITION OF fetch_observation
    FOR VALUES FROM ('2027-12-01') TO ('2028-01-01');
