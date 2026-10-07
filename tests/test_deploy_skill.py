"""
Consistency checks for the sdlc-deploy skill file (SP-047).

The skill is a markdown instruction file, not code, so there is nothing to run.
What can go wrong when it is edited is mechanical: steps get renumbered and a
"see Step N" reference keeps pointing at the old number, or a rule that must
survive (never use `az webapp deploy --type zip`) gets lost. These tests read
the file as plain text and check exactly that - no git and no Azure involved.
"""

import re
from pathlib import Path

SKILL_PATH = Path(__file__).resolve().parent.parent / '.claude' / 'skills' / 'sdlc-deploy' / 'SKILL.md'

TEXT = SKILL_PATH.read_text(encoding='utf-8')
HEADINGS = re.findall(r'^### Step (\d+) \S+ (.+)$', TEXT, flags=re.MULTILINE)  # (number, title)


def step_number(title_fragment: str) -> int:
    """Number of the step whose heading contains title_fragment."""
    matches = [int(n) for n, title in HEADINGS if title_fragment.lower() in title.lower()]
    assert len(matches) == 1, f'expected exactly one step titled like {title_fragment!r}, got {matches}'
    return matches[0]


class TestStepNumbering:

    def test_steps_are_numbered_consecutively(self):
        numbers = [int(n) for n, _ in HEADINGS]

        assert numbers == list(range(1, len(numbers) + 1))
        assert len(numbers) == 11

    def test_every_step_reference_points_at_an_existing_step(self):
        last_step = len(HEADINGS)
        # Headings themselves are definitions, not references
        body = re.sub(r'^### Step .*$', '', TEXT, flags=re.MULTILINE)

        referenced = [int(n) for n in re.findall(r'\bStep (\d+)', body)]

        assert referenced, 'the skill should refer to its own steps somewhere'
        assert all(1 <= n <= last_step for n in referenced), referenced

    def test_steps_run_in_the_expected_order(self):
        order = [
            step_number('data migration'),
            step_number('Prepare the release entry'),
            step_number('Build the deployment package'),
            step_number('Deploy using'),
            step_number('Verify'),
            step_number('Record the new deployment marker'),
            step_number('Mark deployed stories'),
            step_number('Report'),
        ]

        assert order == sorted(order)
        assert len(set(order)) == len(order)

    def test_cross_references_follow_the_renumbered_steps(self):
        package = step_number('Build the deployment package')
        deploy = step_number('Deploy using')
        verify = step_number('Verify')
        marker = step_number('Record the new deployment marker')
        release = step_number('Prepare the release entry')

        assert f'(see Step {package})' in TEXT                    # uncommitted changes don't ship
        assert f'`config-zip` in Step {deploy}' in TEXT           # migration step: why no stop needed
        assert f"Step {deploy}'s code deploy" in TEXT
        assert f"Only after Step {verify}'s verification" in TEXT  # marker is written after verify
        assert f'Only after Step {marker} succeeds' in TEXT       # Deployed lines after the marker
        assert f'skip straight to Step {release}' in TEXT         # no marker / no migration


class TestReleaseStepContent:

    def test_release_entry_is_committed_before_packaging(self):
        release = step_number('Prepare the release entry')
        package = step_number('Build the deployment package')

        assert release < package
        assert 'git commit -m "Release N"' in TEXT
        assert 'git push origin main' in TEXT
        assert 'committed **before** packaging' in TEXT

    def test_entry_is_drafted_for_approval_before_anything_is_written(self):
        assert 'releases.json' in TEXT
        assert 'ask the user to approve it or edit the text' in TEXT
        assert 'Write nothing before that.' in TEXT

    def test_no_commit_shas_in_releases_json(self):
        assert 'never\nstore commit SHAs in `releases.json`' in TEXT

    def test_pending_entry_is_reused_not_bumped_again(self):
        assert 'git show <marker-commit>:releases.json' in TEXT
        assert 'treat that version as `0`' in TEXT          # marker predates releases.json
        assert '**Do not bump the version.**' in TEXT         # failed earlier deploy
        assert '**extend**' in TEXT and '**replace**' in TEXT  # partial coverage question

    def test_non_sp_change_asks_whether_to_release_anyway(self):
        assert 'create a release anyway' in TEXT
        assert 'deploy without a version bump' in TEXT


class TestExistingRulesSurvive:

    def test_still_forbids_onedeploy_zip_and_uses_config_zip(self):
        assert '**Do not use `az webapp deploy --type zip`**' in TEXT
        assert 'az webapp deployment source config-zip' in TEXT

    def test_marker_and_deployed_line_steps_remain(self):
        assert '"commit": "<full sha>"' in TEXT
        assert '**Deployed**: <short-sha> (<date>)' in TEXT
        assert 'Mark SP-{NNN}' in TEXT

    def test_report_mentions_the_released_version(self):
        report = TEXT[TEXT.index('### Step 11'):]

        assert 'released version number' in report
