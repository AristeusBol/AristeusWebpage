BEGIN;

UPDATE usuarios SET email = lower(email) WHERE email <> lower(email);

DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'usuarios_email_key') THEN
        ALTER TABLE usuarios DROP CONSTRAINT usuarios_email_key;
    END IF;
END $$;

CREATE UNIQUE INDEX IF NOT EXISTS usuarios_email_lower_uniq ON usuarios (lower(email));

COMMIT;
