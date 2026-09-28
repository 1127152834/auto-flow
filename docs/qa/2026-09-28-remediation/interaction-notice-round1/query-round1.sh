#!/bin/sh
set -eu

db=${1:-/tmp/autoflow-task3-round1-qa.UlhnXI/data/autoflow.sqlite3}

sqlite3 -readonly -json "$db" <<'SQL'
PRAGMA query_only = ON;

SELECT b.id AS batch_id,
       b.status AS batch_status,
       t.id AS task_id,
       r.id AS run_id,
       r.status AS run_status,
       r.execution_generation,
       r.last_sequence,
       r.error
FROM project_batches AS b
JOIN project_tasks AS t ON t.batch_id = b.id
JOIN project_workflow_runs AS r ON r.id = t.run_id
WHERE b.id IN (
  '2c82d320-47a6-457e-89e6-8dd462f6ce7a',
  'c05fd0df-484e-4d4d-b5c4-be4e2e018560'
)
ORDER BY b.created_at;

SELECT run_id,
       COUNT(DISTINCT CASE WHEN kind = 'nodeAttempt' AND node_id = 'script' THEN attempt END) AS distinct_script_attempts,
       SUM(CASE WHEN kind = 'output' AND node_id = 'script' THEN 1 ELSE 0 END) AS script_outputs,
       MAX(CASE WHEN kind = 'output' AND node_id = 'script' THEN json_extract(payload, '$.value') END) AS result
FROM project_workflow_run_events
WHERE run_id = '70bae1a2-f936-455d-86fd-41ac6330f709'
GROUP BY run_id;

SELECT sequence, kind, node_id, attempt, payload
FROM project_workflow_run_events
WHERE run_id = '70bae1a2-f936-455d-86fd-41ac6330f709'
  AND (kind = 'interaction' OR kind = 'output' OR kind = 'nodeAttempt')
ORDER BY sequence;

SELECT sequence, kind, node_id, attempt, payload
FROM project_workflow_run_events
WHERE run_id = 'd25462ec-6c04-4bd9-9f21-c7c987ac4762'
  AND (kind = 'interaction' OR kind = 'output' OR kind = 'nodeAttempt')
ORDER BY sequence;
SQL
