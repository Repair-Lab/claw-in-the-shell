-- =============================================================================
-- Migration 61: LLM Manager v0.12.0 — Vollständige Dokumentation
-- =============================================================================
-- Datum: 2026-03-17
-- Beschreibung:
--   - LLM-Scan erweitert: erkennt HuggingFace-Verzeichnisse via config.json
--   - Scan-Pfade: /home, /opt, /mnt, /mnt/nvme, /data
--   - Neue API-Endpunkte: /api/llm/download, /api/llm/models/{id}/activate,
--     /api/llm/models/{id}/deactivate, /api/gpu/vram-budget
--   - Frontend: Download-Button (HuggingFace Repo-ID), Aktivieren/Deaktivieren-Toggle
--   - VRAM-Budget-Diagramm im GPU-Tab mit Admin-Alert (>75% Warnung, >90% Kritisch)
--   - docker-compose.yml: NVIDIA GPU Pass-through aktiviert
--   - docker-compose.yml: /mnt/nvme/models in Container gemountet
-- =============================================================================

BEGIN;

-- ─────────────────────────────────────────────────────────────────────────────
-- 1) LLM-Scan Konfiguration dokumentieren
-- ─────────────────────────────────────────────────────────────────────────────
INSERT INTO dbai_knowledge.changelog (version, change_type, title, description)
VALUES
  ('0.12.0', 'feature', 'LLM-Scan: HuggingFace-Verzeichnisse',
   'Der Festplatten-Scanner erkennt jetzt HuggingFace-Modell-Verzeichnisse (config.json mit model_type/architectures). Zeigt Modelltyp, Parameterschätzung, Gewichts-Status. Scan-Pfade erweitert um /mnt/nvme.'),
  ('0.12.0', 'feature', 'LLM Manager: Download-Button',
   'Neuer Download-Bereich im Modelle-Tab: HuggingFace Repo-ID eingeben → Modell wird nach /mnt/nvme/models heruntergeladen. Nutzt huggingface_hub oder git clone als Fallback.'),
  ('0.12.0', 'feature', 'LLM Manager: Aktivieren/Deaktivieren',
   'Modelle können per ▶/⏹-Button aktiviert oder deaktiviert werden. Setzt state=active/inactive in dbai_llm.ghost_models.'),
  ('0.12.0', 'feature', 'VRAM-Budget-Diagramm',
   'GPU-Tab zeigt VRAM-Auslastung pro GPU via nvidia-smi. Admin-Alerts: gelb bei >75%, rot bei >90% VRAM. Listet alle aktuell geladenen Modelle mit GPU-Zuordnung.'),
  ('0.12.0', 'feature', 'NVIDIA GPU Pass-through docker-compose',
   'ghost-api Container nutzt jetzt NVIDIA GPU-Treiber (deploy.resources.reservations.devices[nvidia]). nvidia-smi im Container verfügbar. /mnt/nvme/models eingebunden.'),
  ('0.12.0', 'fix', 'LLMManager TypeError appSettings?.default_tab',
   'Null-Safety: appSettings.default_tab → appSettings?.default_tab. useAppSettings gibt initial null zurück.')
ON CONFLICT DO NOTHING;

-- ─────────────────────────────────────────────────────────────────────────────
-- 2) System-Memory Dokumentation
-- ─────────────────────────────────────────────────────────────────────────────
INSERT INTO dbai_knowledge.system_memory (category, title, content, valid_from, tags)
VALUES
  ('architecture', 'LLM Manager Feature-Set v0.12.0',
   'Vollständig implementiert: HF-Scan, Download, Aktivieren/Deaktivieren, VRAM-Monitoring. GPU via NVIDIA Container Toolkit (deploy.resources.reservations.devices). Modelle unter /mnt/nvme/models.',
   '0.12.0',
   ARRAY['llm', 'gpu', 'vram', 'nvidia', 'scan', 'download', '0.12.0']),
  ('architecture', 'NVIDIA GPU im Docker-Container',
   'docker-compose.yml ghost-api: deploy.resources.reservations.devices[driver=nvidia, count=all, capabilities=[gpu]]. Voraussetzung: nvidia-container-toolkit auf Host installiert (apt install nvidia-container-toolkit).',
   '0.12.0',
   ARRAY['nvidia', 'docker', 'gpu', 'container-toolkit'])
ON CONFLICT DO NOTHING;

-- ─────────────────────────────────────────────────────────────────────────────
-- 3) API-Endpunkte in llm_providers registrieren (falls Tabelle existiert)
-- ─────────────────────────────────────────────────────────────────────────────
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM pg_tables
    WHERE schemaname = 'dbai_llm' AND tablename = 'llm_api_endpoints'
  ) THEN
    INSERT INTO dbai_llm.llm_api_endpoints (path, method, description, added_version)
    VALUES
      ('/api/llm/scan',                    'POST', 'Festplatten-Scan: findet GGUF/SafeTensors/HuggingFace-Verzeichnisse', '0.12.0'),
      ('/api/llm/download',                'POST', 'Modell von HuggingFace Hub herunterladen', '0.12.0'),
      ('/api/llm/models/{id}/activate',    'POST', 'Modell aktivieren (state→active)', '0.12.0'),
      ('/api/llm/models/{id}/deactivate',  'POST', 'Modell deaktivieren (state→inactive)', '0.12.0'),
      ('/api/gpu/vram-budget',             'GET',  'VRAM-Auslastung pro GPU + geladene Modelle + Alert-Status', '0.12.0')
    ON CONFLICT DO NOTHING;
  END IF;
END $$;

COMMIT;
