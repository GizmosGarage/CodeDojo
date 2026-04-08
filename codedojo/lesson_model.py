from dataclasses import dataclass, field


@dataclass
class LessonPoint:
    title: str
    explanation: str = ""
    example: str = ""


@dataclass
class QuizQuestion:
    question: str
    options: list[str] = field(default_factory=list)
    answer: str = ""
    code: str = ""


@dataclass
class LessonSpec:
    skill: str
    title: str
    summary: str = ""
    points: list[LessonPoint] = field(default_factory=list)
    quiz: list[QuizQuestion] = field(default_factory=list)
    narrative: str = ""

    @property
    def quiz_answers(self) -> list[str]:
        return [item.answer for item in self.quiz]
