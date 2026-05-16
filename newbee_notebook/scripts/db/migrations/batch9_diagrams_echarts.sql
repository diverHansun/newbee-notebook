DO $$
DECLARE
    constraint_record RECORD;
BEGIN
    IF to_regclass('public.diagrams') IS NULL THEN
        RETURN;
    END IF;

    IF EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conrelid = 'public.diagrams'::regclass
          AND contype = 'c'
          AND conname = 'ck_diagrams_format'
          AND pg_get_constraintdef(oid) LIKE '%echarts_option%'
    ) THEN
        RETURN;
    END IF;

    FOR constraint_record IN
        SELECT conname
        FROM pg_constraint
        WHERE conrelid = 'public.diagrams'::regclass
          AND contype = 'c'
          AND (
              conname IN ('ck_diagrams_format', 'diagrams_format_check')
              OR (
                  pg_get_constraintdef(oid) LIKE '%reactflow_json%'
                  AND pg_get_constraintdef(oid) LIKE '%mermaid%'
              )
          )
    LOOP
        EXECUTE format('ALTER TABLE diagrams DROP CONSTRAINT IF EXISTS %I', constraint_record.conname);
    END LOOP;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conrelid = 'public.diagrams'::regclass
          AND conname = 'ck_diagrams_format'
    ) THEN
        ALTER TABLE diagrams
            ADD CONSTRAINT ck_diagrams_format
            CHECK (format IN ('reactflow_json', 'mermaid', 'echarts_option'));
    END IF;
END $$;
