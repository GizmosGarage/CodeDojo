from codedojo.challenge_model import ChallengeSpec
from codedojo.session_persist import (
    clear_interrupted_challenge,
    load_interrupted_challenge,
    save_interrupted_challenge,
)


def test_interrupted_challenge_round_trip(tmp_path):
    path = tmp_path / "interrupted.json"
    spec = ChallengeSpec(
        challenge_id="abc12345",
        skill="string concatenation and f-strings",
        title="Greeting Board",
        required_concepts=["f-string", "print()"],
        expected_behavior="Print a personalized greeting banner.",
        brief_description="Make a small welcome board for the dojo entrance.",
        what_to_do=[
            "Create a student name variable.",
            "Print a greeting banner that includes the student's name.",
        ],
        expected_output="Welcome, Maya!\nTrain hard today!",
        narrative="Write a small greeting board program.",
    )

    save_interrupted_challenge(
        path,
        spec,
        attempt_count=2,
        phase="challenge",
        skill=spec.skill,
        challenge_kind="belt_exam",
    )
    loaded = load_interrupted_challenge(path)

    assert loaded is not None
    assert loaded["attempt_count"] == 2
    assert loaded["phase"] == "challenge"
    assert loaded["skill"] == spec.skill
    assert loaded["challenge_kind"] == "belt_exam"
    assert loaded["challenge"].title == "Greeting Board"
    assert loaded["challenge"].brief_description == spec.brief_description
    assert loaded["challenge"].what_to_do == spec.what_to_do
    assert loaded["challenge"].expected_output == spec.expected_output


def test_clear_interrupted_challenge_removes_file(tmp_path):
    path = tmp_path / "interrupted.json"
    path.write_text("{}", encoding="utf-8")

    clear_interrupted_challenge(path)

    assert not path.exists()
