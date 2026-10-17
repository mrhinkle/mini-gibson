#!/usr/bin/env python3
"""Recount sanitized receipts offline. Original-source hashes are references only.

Run: python3 verify_tool_calling_evidence.py
No model, network, credentials, third-party packages, or original traces required.
"""
from pathlib import Path
import hashlib
import json
import re
import sys

# Pinned reference hashes identify the saved original receipts, not their availability.
EXPECTED = {
    'v8-base': ('76b4903d7db3e6e4186aa6cb43f330832172ed1f98b85b9580ed1c6087d1f60d', '77fe13ff512e99fc8a1e64d42b9f7fa33a3001c8c32a243b0276783abc4bf625', 512, 24, 3),
    'v8-adapter': ('0e4c00585fce317dc89a9f510dd88dcf5f8dfba11bf53d88e25a36968340e08a', '77fe13ff512e99fc8a1e64d42b9f7fa33a3001c8c32a243b0276783abc4bf625', 512, 24, 4),
    'selected-1024': ('6e55224299d8613522e9d2f28b59efd1d28f828fb5e6138cd0d280dedc212518', '0b3a0832851bf408f2c3bf4f4928cd1afbdbb47d40eade7a8c493d49f49592ba', 1024, 21, 8),
    'residual-1536': ('17840a37a3b89217e1efc609dca4a11ab323ee7fbcac6a10c372b1e4aa6e7b04', '5d82507fbbb8237284cb952aac07e2aa5f748aa364a9d339cf526b612af87818', 1536, 4, 2),
}
HASH_FIELDS = {'source_sha256', 'task_fixture_sha256', 'fixtures_sha256', 'harness_sha256', 'system_prompt_sha256', 'tools_sha256', 'lock_sha256'}
INT_FIELDS = {'schema_version', 'verify_exit', 'invalid_responses', 'max_new_tokens', 'generation_count', 'total_output_tokens', 'last_output_tokens', 'tool_call_count', 'execution_errors', 'policy_violation_count', 'local_trace_event_count'}
BOOL_FIELDS = {'passed', 'invalid_at_token_limit', 'tests_tampered'}
FIELDS = HASH_FIELDS | INT_FIELDS | BOOL_FIELDS | {'batch_id', 'task_id', 'arm', 'model', 'model_revision', 'adapter_weights_sha256', 'adapter_config_sha256'}
ADAPTER_WEIGHTS = 'a7c6f56ea24527816a0a2c4aa652b7e28e4766ba902deaebb9186727d9bda23c'
ADAPTER_CONFIG = '1f2871fa1b90e1d546e5fb319ad39db4451514415535432d1764847e7513d410'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def recount(rows):
    return {
        'rows': len(rows), 'passed': sum(x['passed'] for x in rows),
        'invalid_tasks': sum(x['invalid_responses'] > 0 for x in rows),
        'invalid_at_token_limit_tasks': sum(x['invalid_at_token_limit'] for x in rows),
        'policy_violation_tasks': sum(x['policy_violation_count'] > 0 for x in rows),
        'tests_tampered_tasks': sum(x['tests_tampered'] for x in rows),
        'execution_error_tasks': sum(x['execution_errors'] > 0 for x in rows),
        'execution_errors': sum(x['execution_errors'] for x in rows),
    }


def main():
    root = Path(__file__).resolve().parent
    summary = json.loads((root / 'summary.json').read_text())
    require(summary['schema_version'] == 1, 'Unsupported summary schema')
    quality = summary['quality']
    require(quality['final_quality_gains_pending'] is True, 'Final quality must remain pending')
    for key in ('heldout_quality_verified', 'reduced_human_intervention_verified', 'new_training_completed_by_this_revision', 'training_provenance_reconciled'):
        require(quality[key] is False, 'Unsupported quality promotion: ' + key)
    obs = summary['observability']
    require(obs['local_trace_records_present'] is True, 'Local trace evidence missing')
    require(obs['hosted_langfuse_export_verified'] is False and obs['hosted_jev_score_verified'] is False, 'Hosted exports are not verified by these receipts')
    manifests = {x['batch_id']: x for x in summary['artifacts']}
    require(len(summary['artifacts']) == len(EXPECTED) and set(manifests) == set(EXPECTED), 'Unexpected or duplicate artifact batch')
    all_rows, counts = {}, {}
    for label, (source, harness, cap, size, passed) in EXPECTED.items():
        item = manifests[label]
        require(item['file'] == label + '.jsonl', 'Artifact filename must be a fixed local basename')
        blob = (root / item['file']).read_bytes()
        require(sha256(blob) == item['artifact_sha256'], 'Sanitized artifact hash mismatch: ' + label)
        require(item['source_sha256'] == source, 'Original-source reference mismatch: ' + label)
        require(item['harness_sha256'] == [harness] and item['max_new_tokens'] == [cap], 'Batch provenance changed: ' + label)
        rows = [json.loads(line) for line in blob.decode().splitlines()]
        require(len(rows) == size, 'Unexpected row count: ' + label)
        require(len({x['task_id'] for x in rows}) == size, 'Duplicate task IDs: ' + label)
        for row in rows:
            require(set(row) == FIELDS, 'Unexpected scalar fields: ' + label)
            for field in INT_FIELDS:
                require(type(row[field]) is int, 'Non-integer scalar: ' + field)
                require(row[field] >= 0, 'Negative scalar: ' + field)
            for field in BOOL_FIELDS:
                require(type(row[field]) is bool, 'Non-boolean scalar: ' + field)
            for field in HASH_FIELDS:
                require(isinstance(row[field], str) and re.fullmatch('[0-9a-f]{64}', row[field]), 'Invalid SHA256: ' + field)
            require(row['schema_version'] == 1 and row['batch_id'] == label, 'Row batch/schema mismatch')
            require(re.fullmatch('fresh-[a-z0-9-]+', row['task_id']), 'Unexpected task ID')
            require(row['source_sha256'] == source and row['harness_sha256'] == harness and row['max_new_tokens'] == cap, 'Row provenance mismatch')
            require(row['model'] == 'nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-BF16' and row['model_revision'] == 'a9904d24bcc1d289a1950fa9d2b978c47cf903b9', 'Model identity mismatch')
            base = label == 'v8-base'
            require(row['arm'] == ('base' if base else 'openhands-lightning'), 'Arm identity mismatch')
            require(row['adapter_weights_sha256'] == (None if base else ADAPTER_WEIGHTS), 'Adapter weights mismatch')
            require(row['adapter_config_sha256'] == (None if base else ADAPTER_CONFIG), 'Adapter configuration mismatch')
            require(row['passed'] == (row['verify_exit'] == 0 and row['policy_violation_count'] == 0), 'Pass contradicts deterministic gate')
            require(not row['tests_tampered'] or (row['policy_violation_count'] > 0 and not row['passed']), 'Test modification escaped failure gate')
            require(row['generation_count'] >= 1 and row['last_output_tokens'] <= cap, 'Invalid generation/token count')
            require(row['last_output_tokens'] <= row['total_output_tokens'] <= cap * row['generation_count'], 'Token sum inconsistent')
            require(row['execution_errors'] <= row['tool_call_count'] <= row['generation_count'], 'Tool counters inconsistent')
            require(row['local_trace_event_count'] == row['generation_count'] + row['tool_call_count'], 'Local trace counters inconsistent')
            require(row['invalid_at_token_limit'] == bool(row['invalid_responses'] and row['last_output_tokens'] == cap), 'At-limit flag inconsistent')
        count = recount(rows)
        require(count == item['counts'] and count['passed'] == passed, 'Recount mismatch: ' + label)
        all_rows[label], counts[label] = rows, count
    base = {x['task_id']: x for x in all_rows['v8-base']}
    tuned = {x['task_id']: x for x in all_rows['v8-adapter']}
    require(set(base) == set(tuned), 'v8 arms use different task IDs')
    require(all(base[k]['task_fixture_sha256'] == tuned[k]['task_fixture_sha256'] for k in base), 'v8 arms use different task fixtures')
    selected = {x['task_id']: x for x in all_rows['selected-1024']}
    residual = {x['task_id']: x for x in all_rows['residual-1536']}
    require(set(residual) == {k for k, x in selected.items() if x['invalid_responses']}, 'Residual selection differs from remaining malformed calls')
    require(all(residual[k]['task_fixture_sha256'] == selected[k]['task_fixture_sha256'] for k in residual), 'Residual fixture mismatch')
    require(counts['selected-1024']['invalid_at_token_limit_tasks'] == 4 and counts['selected-1024']['tests_tampered_tasks'] == 1, 'Selected diagnostic finding changed')
    require(counts['residual-1536']['invalid_at_token_limit_tasks'] == 2, 'Residual diagnostic finding changed')
    require(all(x['execution_errors'] == 1 for x in all_rows['residual-1536'] if x['passed']), 'Residual recovery count changed')
    print(json.dumps({'status': 'PASS', 'recount': counts, 'original_sources': 'Hashes checked as pinned references only; originals not read', 'final_quality_gains': 'PENDING', 'hosted_exports': 'NOT_VERIFIED'}, indent=2))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, KeyError, OSError, TypeError) as exc:
        print('FAIL: ' + str(exc), file=sys.stderr)
        sys.exit(1)
