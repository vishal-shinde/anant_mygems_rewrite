-- Create application database and user for the refactored MYGEMS app.
-- Update the values below to match your preferred database/user names.
-- Run as PostgreSQL superuser, for example:
--   psql -U postgres -f database/bootstrap.sql

CREATE USER mygems_admin WITH PASSWORD 'Thakur_boyz';
CREATE DATABASE mygems_app OWNER mygems_admin;
GRANT ALL PRIVILEGES ON DATABASE mygems_app TO mygems_admin;
