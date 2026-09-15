BEGIN;

UPDATE usuarios SET email = 'unknown+' || id || '@invalid.local' WHERE email IS NULL;

DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'usuarios_email_not_null'
    ) THEN
        BEGIN
            ALTER TABLE usuarios ALTER COLUMN email SET NOT NULL;
        EXCEPTION WHEN others THEN
            RAISE NOTICE 'usuarios.email NOT NULL no aplicado: %', SQLERRM;
        END;
    END IF;
END $$;

DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'potreros_base_usuario_id_id_key'
    ) THEN
        ALTER TABLE potreros_base ADD CONSTRAINT potreros_base_usuario_id_id_key UNIQUE (usuario_id, id);
    END IF;
END $$;

DO $$ DECLARE r record; BEGIN
    FOR r IN SELECT conname, conrelid::regclass AS tabla
             FROM pg_constraint
             WHERE contype = 'f'
               AND conrelid IN ('mapa_color'::regclass, 'zonas_exclusion'::regclass,
                                'calculos_stock'::regclass, 'fotos_calibracion'::regclass)
    LOOP
        BEGIN
            EXECUTE format('ALTER TABLE %s DROP CONSTRAINT %I', r.tabla, r.conname);
        EXCEPTION WHEN undefined_object THEN
            CONTINUE;
        END;
    END LOOP;
END $$;

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'mapa_color_usuario_id_fkey') THEN
        ALTER TABLE mapa_color ADD CONSTRAINT mapa_color_usuario_id_fkey
            FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'mapa_color_titularidad_fkey') THEN
        ALTER TABLE mapa_color ADD CONSTRAINT mapa_color_titularidad_fkey
            FOREIGN KEY (usuario_id, potrero_id) REFERENCES potreros_base(usuario_id, id) ON DELETE CASCADE;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'zonas_exclusion_usuario_id_fkey') THEN
        ALTER TABLE zonas_exclusion ADD CONSTRAINT zonas_exclusion_usuario_id_fkey
            FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'zonas_exclusion_titularidad_fkey') THEN
        ALTER TABLE zonas_exclusion ADD CONSTRAINT zonas_exclusion_titularidad_fkey
            FOREIGN KEY (usuario_id, potrero_id) REFERENCES potreros_base(usuario_id, id) ON DELETE CASCADE;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'calculos_stock_usuario_id_fkey') THEN
        ALTER TABLE calculos_stock ADD CONSTRAINT calculos_stock_usuario_id_fkey
            FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'calculos_stock_titularidad_fkey') THEN
        ALTER TABLE calculos_stock ADD CONSTRAINT calculos_stock_titularidad_fkey
            FOREIGN KEY (usuario_id, potrero_id) REFERENCES potreros_base(usuario_id, id) ON DELETE CASCADE;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fotos_calibracion_usuario_id_fkey') THEN
        ALTER TABLE fotos_calibracion ADD CONSTRAINT fotos_calibracion_usuario_id_fkey
            FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fotos_calibracion_titularidad_fkey') THEN
        ALTER TABLE fotos_calibracion ADD CONSTRAINT fotos_calibracion_titularidad_fkey
            FOREIGN KEY (usuario_id, potrero_id) REFERENCES potreros_base(usuario_id, id) ON DELETE CASCADE;
    END IF;
END $$;

COMMIT;
