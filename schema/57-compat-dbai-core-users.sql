-- Compatibility layer: provide dbai_core.users view that maps to dbai_ui.users
-- This fixes legacy code paths that still reference dbai_core.users

CREATE SCHEMA IF NOT EXISTS dbai_core;
COMMENT ON SCHEMA dbai_core IS 'Compatibility schema mapping legacy core tables to new ui schema';

-- Create a read-write view that exposes the columns the API expects
CREATE OR REPLACE VIEW dbai_core.users AS
SELECT
  id,
  username,
  display_name,
  password_hash,
  db_role AS role,
  is_active,
  created_at,
  last_login_at AS last_login
FROM dbai_ui.users;

-- Insert handler: forward inserts to dbai_ui.users
CREATE OR REPLACE FUNCTION dbai_core.users_insert_trigger()
RETURNS trigger AS $$
BEGIN
  INSERT INTO dbai_ui.users (id, username, display_name, password_hash, db_role, is_active, created_at, last_login_at)
  VALUES (COALESCE(NEW.id, gen_random_uuid()), NEW.username, NEW.display_name, NEW.password_hash, COALESCE(NEW.role, 'dbai_monitor'), COALESCE(NEW.is_active, true), COALESCE(NEW.created_at, NOW()), NEW.last_login);
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_dbai_core_users_insert
INSTEAD OF INSERT ON dbai_core.users
FOR EACH ROW EXECUTE FUNCTION dbai_core.users_insert_trigger();

-- Update handler: forward updates to dbai_ui.users
CREATE OR REPLACE FUNCTION dbai_core.users_update_trigger()
RETURNS trigger AS $$
BEGIN
  UPDATE dbai_ui.users SET
    username = COALESCE(NEW.username, username),
    display_name = COALESCE(NEW.display_name, display_name),
    password_hash = COALESCE(NEW.password_hash, password_hash),
    db_role = COALESCE(NEW.role, db_role),
    is_active = COALESCE(NEW.is_active, is_active),
    updated_at = NOW(),
    last_login_at = COALESCE(NEW.last_login, last_login_at)
  WHERE id = NEW.id;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_dbai_core_users_update
INSTEAD OF UPDATE ON dbai_core.users
FOR EACH ROW EXECUTE FUNCTION dbai_core.users_update_trigger();

-- Delete handler: forward deletes (soft-delete to keep cascade semantics)
CREATE OR REPLACE FUNCTION dbai_core.users_delete_trigger()
RETURNS trigger AS $$
BEGIN
  -- Perform a soft-delete by setting is_active = false to avoid accidental data loss
  UPDATE dbai_ui.users SET is_active = false, updated_at = NOW() WHERE id = OLD.id;
  RETURN OLD;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_dbai_core_users_delete
INSTEAD OF DELETE ON dbai_core.users
FOR EACH ROW EXECUTE FUNCTION dbai_core.users_delete_trigger();

-- Grant minimal privileges to expected roles
GRANT USAGE ON SCHEMA dbai_core TO dbai_system;
GRANT SELECT ON TABLE dbai_core.users TO dbai_system;

-- End of migration
