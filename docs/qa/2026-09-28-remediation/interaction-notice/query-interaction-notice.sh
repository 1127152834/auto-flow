#!/bin/sh
set -eu

db_path=${1:-/tmp/autoflow-task3-qa.j6AbYM/data/autoflow.sqlite3}
project_id=718795f2-40ae-4167-bb55-bec829df9a82
automation_id=320e22b3-e2b6-4442-9287-088065c9ff6b
task_id=1b7823b4-6930-4ede-98a0-0e3e460297da
run_id=d6befbcf-cdc3-4303-b9e4-c9f2dc28eae2

test -f "$db_path"

echo '== identity_and_terminal_state =='
sqlite3 -readonly -json "$db_path" <<SQL
PRAGMA query_only=ON;
SELECT
  p.id AS project_id,
  p.name AS project_name,
  a.id AS automation_id,
  a.name AS automation_name,
  a.workflow_id,
  t.id AS task_id,
  t.batch_id,
  t.run_id,
  t.run_request_id,
  t.ordinal,
  r.status,
  r.status_revision,
  r.execution_generation,
  r.last_sequence,
  r.started_at,
  r.completed_at
FROM project_tasks AS t
JOIN projects AS p ON p.id = t.project_id
JOIN project_automations AS a ON a.project_id = t.project_id
JOIN project_workflow_runs AS r ON r.id = t.run_id
WHERE t.id = '$task_id'
  AND p.id = '$project_id'
  AND a.id = '$automation_id'
  AND r.id = '$run_id';
SQL

echo '== interaction_and_result_events =='
sqlite3 -readonly -json "$db_path" <<SQL
PRAGMA query_only=ON;
SELECT
  sequence,
  kind,
  node_id,
  node_visit_id,
  attempt,
  execution_generation,
  occurred_at,
  payload
FROM project_workflow_run_events
WHERE run_id = '$run_id'
  AND sequence BETWEEN 4 AND 12
ORDER BY sequence;
SQL

echo '== single_execution_summary =='
sqlite3 -readonly -json "$db_path" <<SQL
PRAGMA query_only=ON;
SELECT
  COUNT(DISTINCT CASE WHEN node_id = 'script' THEN attempt END) AS distinct_script_attempts,
  COUNT(CASE WHEN kind = 'output' AND node_id = 'script' THEN 1 END) AS script_outputs,
  MAX(CASE WHEN kind = 'output' AND node_id = 'script' THEN json_extract(payload, '$.value') END) AS result,
  MAX(sequence) AS evidence_max_sequence
FROM project_workflow_run_events
WHERE run_id = '$run_id';
SQL
