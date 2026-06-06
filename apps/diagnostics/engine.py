"""
apps/diagnostics/engine.py
Core diagnostic engine.

Loads YAML rules, evaluates conditions against collected command output,
produces structured findings, and optionally executes autonomous remediation.

Design principles:
  - Every decision is traceable to a specific rule and version
  - Autonomous actions are opt-in per rule, default off
  - All actions are logged before execution
  - Engine never modifies rules — rules are read-only at runtime
"""

import os
import re
import logging
import yaml
from datetime import datetime, timezone, timedelta
from pathlib import Path

from django.utils import timezone as django_timezone

from .models import DiagnosticRule, DiagnosticFinding, RemediationLog

logger = logging.getLogger(__name__)

# Path to the rules directory relative to this file
RULES_DIR = Path(__file__).parent / 'rules'


class RuleLoadError(Exception):
    pass


class DiagnosticEngine:
    """
    Main engine class. Instantiate per scan run.
    """

    def __init__(self, host, collected_data: dict, triggered_by=None):
        """
        host:           ManagedHost instance
        collected_data: dict of {command_name: output_string}
        triggered_by:   User instance if manually triggered, None if scheduled
        """
        self.host           = host
        self.collected_data = collected_data
        self.triggered_by   = triggered_by
        self.findings       = []

    def run(self) -> list:
        """
        Load all applicable rules for this host's platform and run them.
        Returns a list of DiagnosticFinding instances.
        """
        rules = self._load_rules()
        logger.info(f"DiagnosticEngine: running {len(rules)} rules against {self.host.hostname}")

        for rule_def in rules:
            try:
                for item in rule_def.get('collect', []):
                    commands.add(item['command'])
                # Also collect prerequisite commands
                for prereq in rule_def.get('prerequisites', []):
                    cmd = prereq.get('command', prereq.get('field', ''))
                    if cmd:
                        commands.add(cmd)
                
                finding = self._evaluate_rule(rule_def)
                if finding:
                    self.findings.append(finding)
                    if rule_def.get('remediation', {}).get('autonomous', False):
                        self._execute_autonomous_remediation(finding, rule_def)
            except Exception as e:
                logger.error(f"Error evaluating rule {rule_def.get('rule', {}).get('id', '?')}: {e}")

        return self.findings

    def _load_rules(self) -> list:
        """
        Load all YAML rules applicable to this host's platform.
        Returns a list of parsed rule dicts.
        """
        rules = []
        platform = self.host.os_type  # 'windows' or 'linux'

        if not RULES_DIR.exists():
            logger.warning(f"Rules directory not found: {RULES_DIR}")
            return rules

        for yaml_file in sorted(RULES_DIR.rglob('*.yaml')):
            try:
                with open(yaml_file, 'r') as f:
                    rule_def = yaml.safe_load(f)

                if not rule_def or 'rule' not in rule_def:
                    continue

                rule = rule_def['rule']
                rule_platform = rule.get('platform', 'both')

                # Skip rules that don't apply to this host's platform
                if rule_platform != 'both' and rule_platform != platform:
                    continue

                # Skip disabled rules
                if rule.get('status', 'active') != 'active':
                    continue

                rules.append(rule_def)

            except Exception as e:
                logger.error(f"Failed to load rule {yaml_file}: {e}")

        return rules

    def _evaluate_rule(self, rule_def: dict):
        """
        Evaluate a single rule against collected data.
        Returns a DiagnosticFinding if conditions are met, None otherwise.
        """
        rule       = rule_def.get('rule', {})
        rule_id    = rule.get('id', 'UNKNOWN')
        conditions = rule_def.get('conditions', {})
        finding_def = rule_def.get('finding', {})

        # Check prerequisites before evaluating conditions
        prerequisites = rule_def.get('prerequisites', [])
        if prerequisites:
            if not self._check_prerequisites(prerequisites):
                logger.info(f"Rule {rule_id} skipped — prerequisites not met on {self.host.hostname}")
                return None

                return None

        match_mode = conditions.get('match', 'any')  # 'any' or 'all'
        patterns   = conditions.get('patterns', [])

        matched = []

        for pattern in patterns:
            field   = pattern.get('field')
            data    = self.collected_data.get(field, '')

            if not data:
                continue

            result = self._evaluate_pattern(pattern, data)
            if result:
                matched.append((pattern, result))

        # Determine if conditions are met
        if match_mode == 'any' and not matched:
            return None
        if match_mode == 'all' and len(matched) != len(patterns):
            return None
        if not matched:
            return None

        # Determine severity from matched patterns
        severities = [p.get('severity', rule.get('severity', 'warning')) for p, _ in matched]
        severity   = 'critical' if 'critical' in severities else \
                     'warning'  if 'warning'  in severities else 'info'

        # Determine confidence based on number of patterns matched
        total    = len(patterns)
        n_matched = len(matched)
        if total == 0:
            confidence = 'low'
        elif n_matched == total:
            confidence = 'high'
        elif n_matched >= total / 2:
            confidence = 'medium'
        else:
            confidence = 'low'

        # Build detail string from matched pattern data
        detail_parts = []
        detail_field = finding_def.get('detail_field')
        if detail_field and detail_field in self.collected_data:
            detail_parts.append(self.collected_data[detail_field])
        for pattern, match_detail in matched:
            if match_detail and match_detail not in detail_parts:
                detail_parts.append(str(match_detail))
        detail = '\n'.join(detail_parts)

        # Get or create the rule record in DB
        db_rule, _ = DiagnosticRule.objects.get_or_create(
            rule_id  = rule_id,
            defaults = {
                'name':      rule.get('name', rule_id),
                'version':   rule.get('version', '1.0'),
                'severity':  rule.get('severity', 'warning'),
                'platform':  rule.get('platform', 'both'),
                'category':  rule.get('category', 'general'),
                'description': rule.get('description', ''),
                'yaml_path': str(rule_id),
                'autonomous': rule_def.get('remediation', {}).get('autonomous', False),
            }
        )

        # Create the finding
        finding = DiagnosticFinding.objects.create(
            rule           = db_rule,
            host           = self.host,
            severity       = severity,
            confidence     = confidence,
            probable_cause = finding_def.get('probable_cause', 'Condition matched'),
            detail         = detail,
            recommendation = self._build_recommendation(rule_def),
            rule_version   = rule.get('version', '1.0'),
        )

        logger.info(
            f"Finding created: {rule_id} on {self.host.hostname} "
            f"({severity}, {confidence} confidence)"
        )
        return finding

    def _check_prerequisites(self, prerequisites: list) -> bool:
        """Check all prerequisites — all must pass for the rule to run."""
        for prereq in prerequisites:
            field = prereq.get('command', prereq.get('field', ''))
            data  = self.collected_data.get(field, '')
            condition = prereq.get('condition', 'contains')
            value = prereq.get('value', prereq.get('contains', ''))
            if condition == 'contains':
                if value.lower() not in data.lower():
                    return False
            elif condition == 'not_contains':
                if value.lower() in data.lower():
                    return False
            elif condition == 'regex':
                import re
                if not re.search(value, data, re.IGNORECASE):
                    return False
        return True

    def _check_prerequisites(self, prerequisites: list) -> bool:
        """
        Check all prerequisites for a rule.
        All prerequisites must pass for the rule to run.
        Returns True if all prerequisites are met, False otherwise.
        """
        for prereq in prerequisites:
            field     = prereq.get('command', prereq.get('field', ''))
            data      = self.collected_data.get(field, '')
            condition = prereq.get('condition', 'contains')
            value     = prereq.get('value', prereq.get('contains', ''))

            if condition == 'contains':
                if value.lower() not in data.lower():
                    return False
            elif condition == 'not_contains':
                if value.lower() in data.lower():
                    return False
            elif condition == 'regex':
                import re
                if not re.search(value, data, re.IGNORECASE):
                    return False

        return True

    def _evaluate_pattern(self, pattern: dict, data: str):
        """
        Evaluate a single pattern condition against data string.
        Returns match detail if matched, None otherwise.

        Supported condition types:
          contains      — substring match
          not_contains  — substring absence
          regex         — regular expression match
          older_than_hours — for timestamp patterns (snapshot age etc.)
          greater_than  — numeric comparison
          equals        — exact match
        """
        condition = pattern.get('condition', 'contains')
        value     = pattern.get('value', pattern.get('contains', ''))

        if condition == 'contains' or 'contains' in pattern:
            search = pattern.get('contains', value)
            if search.lower() in data.lower():
                # Return the matching line for context
                for line in data.splitlines():
                    if search.lower() in line.lower():
                        return line.strip()
                return search

        elif condition == 'not_contains':
            if value.lower() not in data.lower():
                return f"Expected '{value}' not found"

        elif condition == 'regex':
            match = re.search(value, data, re.IGNORECASE | re.MULTILINE)
            if match:
                return match.group(0)

        elif condition == 'older_than_hours':
            # Parse timestamps from data and check age
            hours     = pattern.get('hours', 24)
            cutoff    = datetime.now(timezone.utc) - timedelta(hours=hours)
            ts_pattern = pattern.get('timestamp_regex', r'\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}')
            matches   = re.findall(ts_pattern, data)
            old_items = []
            for ts_str in matches:
                try:
                    ts = datetime.fromisoformat(ts_str.replace(' ', 'T'))
                    if ts.tzinfo is None:
                        ts = ts.replace(tzinfo=timezone.utc)
                    if ts < cutoff:
                        old_items.append(ts_str)
                except ValueError:
                    continue
            if old_items:
                return f"Found {len(old_items)} item(s) older than {hours} hours: {', '.join(old_items[:3])}"

        elif condition == 'greater_than':
            numbers = re.findall(r'\d+\.?\d*', data)
            for n in numbers:
                if float(n) > float(value):
                    return f"Value {n} exceeds threshold {value}"

        elif condition == 'equals':
            if value.lower() == data.strip().lower():
                return value

        return None

    def _build_recommendation(self, rule_def: dict) -> str:
        """Build a human-readable recommendation string from rule actions."""
        remediation = rule_def.get('remediation', {})
        actions     = remediation.get('recommended_actions', [])
        if not actions:
            return ''
        lines = ['Recommended actions:']
        for i, action in enumerate(actions, 1):
            lines.append(f"  {i}. {action.get('description', action.get('action', ''))}")
        return '\n'.join(lines)

    def _execute_autonomous_remediation(self, finding: DiagnosticFinding, rule_def: dict):
        """
        Execute autonomous remediation actions for a finding.
        Only called when rule has autonomous: true.
        Every action is logged BEFORE execution.
        """
        from .collector import CommandCollector

        remediation = rule_def.get('remediation', {})
        actions     = remediation.get('autonomous_actions', [])

        if not actions:
            logger.warning(f"Rule {rule_def['rule']['id']} has autonomous=true but no autonomous_actions defined")
            return

        collector = CommandCollector(self.host)

        for action_def in actions:
            action_type = action_def.get('action')
            command     = action_def.get('command', '')
            description = action_def.get('description', command)

            # Log BEFORE executing
            log_entry = RemediationLog.objects.create(
                finding      = finding,
                action       = description,
                command      = command,
                outcome      = 'skipped',  # will update after execution
                trigger      = 'autonomous',
                triggered_by = None,
                rule_id      = rule_def['rule']['id'],
                rule_version = rule_def['rule'].get('version', '1.0'),
            )

            try:
                if action_type == 'run_command':
                    output = collector.run_command(command)
                    log_entry.output  = output or ''
                    log_entry.outcome = 'success'
                    log_entry.save(update_fields=['output', 'outcome'])
                    logger.info(f"Autonomous action executed: {command} on {self.host.hostname}")
                else:
                    log_entry.outcome      = 'skipped'
                    log_entry.error_message = f"Unknown action type: {action_type}"
                    log_entry.save(update_fields=['outcome', 'error_message'])

            except Exception as e:
                log_entry.outcome       = 'failure'
                log_entry.error_message = str(e)
                log_entry.save(update_fields=['outcome', 'error_message'])
                logger.error(f"Autonomous action failed: {command} on {self.host.hostname}: {e}")

        # Mark finding as remediated if all actions succeeded
        logs    = finding.remediation_logs.all()
        all_ok  = all(l.outcome == 'success' for l in logs)
        if all_ok:
            finding.resolve('remediated')
