-- After a restore performed as the superuser, hand every object in the public schema to the application role
-- (usage: psql -v app='"world_of_islam"' -f assign-ownership.sql). A superuser restore is required because the schema's
-- foreign-key checks read rows that row-level security would otherwise hide.
SELECT set_config('woi.app_role', trim(both '"' from :'app'), false);
DO $$
DECLARE r record; app text := current_setting('woi.app_role');
BEGIN
  EXECUTE format('ALTER SCHEMA public OWNER TO %I', app);
  FOR r IN SELECT tablename FROM pg_tables WHERE schemaname = 'public' LOOP EXECUTE format('ALTER TABLE public.%I OWNER TO %I', r.tablename, app); END LOOP;
  FOR r IN SELECT sequencename FROM pg_sequences WHERE schemaname = 'public' LOOP EXECUTE format('ALTER SEQUENCE public.%I OWNER TO %I', r.sequencename, app); END LOOP;
  FOR r IN SELECT viewname FROM pg_views WHERE schemaname = 'public' LOOP EXECUTE format('ALTER VIEW public.%I OWNER TO %I', r.viewname, app); END LOOP;
  FOR r IN SELECT p.oid::regprocedure AS sig FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace WHERE n.nspname = 'public' LOOP EXECUTE format('ALTER FUNCTION %s OWNER TO %I', r.sig, app); END LOOP;
END $$;
