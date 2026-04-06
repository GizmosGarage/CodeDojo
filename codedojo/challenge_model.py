from dataclasses import dataclass, field


@dataclass
class ChallengeSpec:
    challenge_id: str                        # uuid4 hex[:8]
    skill: str                               # from skill_tree
    title: str                               # challenge title
    required_concepts: list[str] = field(default_factory=list)  # e.g. ["round()", "f-string"]
    expected_behavior: str = ""              # one-line description of correct output
    brief_description: str = ""             # short setup/context for the challenge
    what_to_do: list[str] = field(default_factory=list)  # concrete task steps
    expected_output: str = ""               # exact/near-exact output target for the student
    narrative: str = ""                      # full Sensei text shown to student
