BEGIN;

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'mapa_color_densidades_no_negativas') THEN
        ALTER TABLE mapa_color ADD CONSTRAINT mapa_color_densidades_no_negativas CHECK (
            (densidad_verde_g_m2 IS NULL OR densidad_verde_g_m2 >= 0) AND
            (densidad_muerta_g_m2 IS NULL OR densidad_muerta_g_m2 >= 0) AND
            (densidad_total_g_m2 IS NULL OR densidad_total_g_m2 >= 0)
        );
    END IF;
END $$;

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'mapa_color_total_coherente') THEN
        ALTER TABLE mapa_color ADD CONSTRAINT mapa_color_total_coherente CHECK (
            densidad_verde_g_m2 IS NULL OR densidad_muerta_g_m2 IS NULL OR densidad_total_g_m2 IS NULL OR
            abs(densidad_total_g_m2 - (densidad_verde_g_m2 + densidad_muerta_g_m2))
                <= 0.05 * GREATEST(densidad_verde_g_m2 + densidad_muerta_g_m2, 1)
        );
    END IF;
END $$;

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'calculos_stock_no_negativos') THEN
        ALTER TABLE calculos_stock ADD CONSTRAINT calculos_stock_no_negativos CHECK (
            (area_neta_ha IS NULL OR area_neta_ha >= 0) AND
            (masa_seca_verde IS NULL OR masa_seca_verde >= 0) AND
            (masa_seca_muerta IS NULL OR masa_seca_muerta >= 0)
        );
    END IF;
END $$;

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'potreros_base_usuario_finca_nombre_key') THEN
        ALTER TABLE potreros_base ADD CONSTRAINT potreros_base_usuario_finca_nombre_key UNIQUE (usuario_id, finca, nombre);
    END IF;
END $$;

COMMIT;
