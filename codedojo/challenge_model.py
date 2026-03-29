from dataclasses import dataclass, field


@dataclass
class ChallengeSpec:
    challenge_id: str                        # uuid4 hex[:8]
    skill: str                               # from skill_tree
    title: str                               # challenge title
    required_concepts: list[str] = field(default_factory=list)  # e.g. ["round()", "f-string"]
    expected_behavior: str = ""              # one-line description of correct output
    narrative: str = ""                      # full Sensei text shown to student
