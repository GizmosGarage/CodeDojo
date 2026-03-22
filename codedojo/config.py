"""CodeDojo configuration — belts, skill tree, and constants."""

APP_NAME = "CodeDojo"
APP_VERSION = "1.0.0"
DATA_DIR_NAME = ".codedojo"
DB_NAME = "dojo.db"

CLAUDE_MODEL = "claude-sonnet-4-20250514"

# ── Belt Ranking System ────────────────────────────────────────────
# Belts are now earned through EXAMS, not XP thresholds.
# belt_rank in UserProfile: 0=White, 1=Yellow, ..., 7=Black
BELTS = [
    {"name": "White Belt",  "color": "white",         "icon": "⬜", "rank": 0,
     "knowledge": "Variables, types, basic I/O"},
    {"name": "Yellow Belt", "color": "yellow",         "icon": "🟡", "rank": 1,
     "knowledge": "Control flow, loops, conditionals"},
    {"name": "Orange Belt", "color": "dark_orange",    "icon": "🟠", "rank": 2,
     "knowledge": "Functions, scope, string manipulation"},
    {"name": "Green Belt",  "color": "green",          "icon": "🟢", "rank": 3,
     "knowledge": "Data structures — lists, dicts, tuples, sets"},
    {"name": "Blue Belt",   "color": "dodger_blue2",   "icon": "🔵", "rank": 4,
     "knowledge": "File I/O, error handling, modules"},
    {"name": "Purple Belt", "color": "medium_purple1", "icon": "🟣", "rank": 5,
     "knowledge": "OOP, classes, inheritance"},
    {"name": "Brown Belt",  "color": "orange4",        "icon": "🟤", "rank": 6,
     "knowledge": "Algorithms, recursion, advanced patterns"},
    {"name": "Black Belt",  "color": "bright_white",   "icon": "⬛", "rank": 7,
     "knowledge": "Full mastery — system design, optimization, all concepts"},
]

# ── Belt Exam Requirements ────────────────────────────────────────
# What the student must achieve before Sensei invites them to take an exam.
BELT_EXAM_REQUIREMENTS = {
    1: {  # Yellow Belt
        "min_skills_trained": 3,
        "min_avg_accuracy": 0.45,
        "required_skills": ["fundamentals.variables_types"],
        "exam_quizzes": 2, "exam_challenges": 1, "exam_boss": True,
        "topics": ["Variables & Types", "Control Flow", "Basic I/O"],
    },
    2: {  # Orange Belt
        "min_skills_trained": 5,
        "min_avg_accuracy": 0.50,
        "required_skills": ["fundamentals.variables_types", "fundamentals.control_flow"],
        "exam_quizzes": 3, "exam_challenges": 1, "exam_boss": True,
        "topics": ["Functions", "String Mastery", "Scope", "Arguments"],
    },
    3: {  # Green Belt
        "min_skills_trained": 8,
        "min_avg_accuracy": 0.55,
        "required_skills": ["fundamentals.functions", "fundamentals.strings"],
        "exam_quizzes": 3, "exam_challenges": 2, "exam_boss": True,
        "topics": ["Lists & Tuples", "Dictionaries", "Sets", "Comprehensions"],
    },
    4: {  # Blue Belt
        "min_skills_trained": 12,
        "min_avg_accuracy": 0.60,
        "required_skills": ["data_structures.lists_tuples", "data_structures.dicts"],
        "exam_quizzes": 4, "exam_challenges": 2, "exam_boss": True,
        "topics": ["File I/O", "Error Handling", "Exceptions", "Context Managers"],
    },
    5: {  # Purple Belt
        "min_skills_trained": 15,
        "min_avg_accuracy": 0.60,
        "required_skills": ["fundamentals.file_io", "error_handling.exceptions"],
        "exam_quizzes": 4, "exam_challenges": 3, "exam_boss": True,
        "topics": ["OOP", "Classes", "Inheritance", "Dunder Methods", "Properties"],
    },
    6: {  # Brown Belt
        "min_skills_trained": 20,
        "min_avg_accuracy": 0.65,
        "required_skills": ["oop.classes_basics", "oop.inheritance"],
        "exam_quizzes": 5, "exam_challenges": 3, "exam_boss": True,
        "topics": ["Algorithms", "Recursion", "Decorators", "Generators", "Functional Programming"],
    },
    7: {  # Black Belt
        "min_skills_trained": 25,
        "min_avg_accuracy": 0.70,
        "min_skills_mastered": 10,
        "required_skills": ["algorithms.recursion", "functional.decorators"],
        "exam_quizzes": 6, "exam_challenges": 4, "exam_boss": True,
        "topics": ["System Design", "Advanced OOP", "Design Patterns", "Optimization", "All Concepts"],
    },
}

# ── Level System (Steep XP Curve) ─────────────────────────────────
# Level N requires: 25 * N^2 cumulative XP
# Level 1: 0, Level 2: 100, Level 3: 225, Level 5: 625, Level 10: 2500, Level 20: 10000
def get_level_from_xp(xp: int) -> int:
    """Calculate player level from total XP. Steep curve: 25*N^2."""
    level = 1
    while 25 * (level ** 2) <= xp:
        level += 1
    return level

def get_xp_for_level(level: int) -> int:
    """Get cumulative XP required for a given level."""
    return 25 * (level ** 2)

def get_xp_for_next_level(current_level: int) -> int:
    """Get XP required for next level."""
    return get_xp_for_level(current_level + 1)


# XP rewards
XP_QUIZ_CORRECT = 10
XP_QUIZ_WRONG = 2          # Participation credit
XP_CHALLENGE_PASS = 30
XP_CHALLENGE_PARTIAL = 15
XP_CHALLENGE_FAIL = 5
XP_CODE_REVIEW = 20
XP_STREAK_BONUS = 5        # Per consecutive day

# ── Skill Tree ─────────────────────────────────────────────────────
SKILL_TREE = {
    "fundamentals": {
        "name": "Fundamentals",
        "icon": "🌱",
        "description": "The roots of all Python mastery.",
        "skills": {
            "variables_types": {
                "name": "Variables & Types",
                "topics": ["int", "float", "str", "bool", "None", "type casting", "type()"],
                "prerequisites": [],
            },
            "control_flow": {
                "name": "Control Flow",
                "topics": ["if/elif/else", "for loops", "while loops", "break/continue", "match/case"],
                "prerequisites": ["fundamentals.variables_types"],
            },
            "functions": {
                "name": "Functions",
                "topics": ["def", "return", "arguments", "default params", "*args/**kwargs", "scope"],
                "prerequisites": ["fundamentals.control_flow"],
            },
            "strings": {
                "name": "String Mastery",
                "topics": ["f-strings", "slicing", "methods", "regex basics", "encoding"],
                "prerequisites": ["fundamentals.variables_types"],
            },
            "file_io": {
                "name": "File I/O",
                "topics": ["open/close", "read/write", "context managers", "pathlib", "csv"],
                "prerequisites": ["fundamentals.functions"],
            },
        },
    },
    "data_structures": {
        "name": "Data Structures",
        "icon": "🏗️",
        "description": "The scaffolding that holds your logic together.",
        "skills": {
            "lists_tuples": {
                "name": "Lists & Tuples",
                "topics": ["indexing", "slicing", "methods", "sorting", "unpacking", "named tuples"],
                "prerequisites": ["fundamentals.functions"],
            },
            "dicts": {
                "name": "Dictionaries",
                "topics": ["CRUD", "iteration", "defaultdict", "dict comprehensions", "merging"],
                "prerequisites": ["fundamentals.functions"],
            },
            "sets": {
                "name": "Sets & Frozensets",
                "topics": ["set operations", "membership", "deduplication", "frozenset"],
                "prerequisites": ["data_structures.lists_tuples"],
            },
            "comprehensions": {
                "name": "Comprehensions",
                "topics": ["list comp", "dict comp", "set comp", "nested", "conditionals"],
                "prerequisites": ["data_structures.lists_tuples", "data_structures.dicts"],
            },
            "collections_module": {
                "name": "Collections Module",
                "topics": ["Counter", "deque", "OrderedDict", "ChainMap", "namedtuple"],
                "prerequisites": ["data_structures.dicts", "data_structures.lists_tuples"],
            },
        },
    },
    "algorithms": {
        "name": "Algorithms",
        "icon": "⚔️",
        "description": "The combat techniques of problem-solving.",
        "skills": {
            "searching": {
                "name": "Searching",
                "topics": ["linear search", "binary search", "hash-based lookup"],
                "prerequisites": ["data_structures.lists_tuples"],
            },
            "sorting": {
                "name": "Sorting",
                "topics": ["bubble", "selection", "insertion", "merge sort", "quicksort", "sorted()"],
                "prerequisites": ["data_structures.lists_tuples"],
            },
            "recursion": {
                "name": "Recursion",
                "topics": ["base cases", "call stack", "memoization", "tail recursion"],
                "prerequisites": ["fundamentals.functions"],
            },
            "dynamic_programming": {
                "name": "Dynamic Programming",
                "topics": ["overlapping subproblems", "memoization", "tabulation", "classic DP"],
                "prerequisites": ["algorithms.recursion"],
            },
            "big_o": {
                "name": "Big-O Analysis",
                "topics": ["time complexity", "space complexity", "amortized", "best/worst/avg"],
                "prerequisites": ["algorithms.searching", "algorithms.sorting"],
            },
        },
    },
    "oop": {
        "name": "Object-Oriented Programming",
        "icon": "🏛️",
        "description": "Discipline. Structure. Elegance.",
        "skills": {
            "classes_basics": {
                "name": "Classes & Objects",
                "topics": ["__init__", "self", "attributes", "methods", "instantiation"],
                "prerequisites": ["fundamentals.functions"],
            },
            "inheritance": {
                "name": "Inheritance",
                "topics": ["super()", "method overriding", "multiple inheritance", "MRO"],
                "prerequisites": ["oop.classes_basics"],
            },
            "dunder_methods": {
                "name": "Dunder Methods",
                "topics": ["__str__", "__repr__", "__eq__", "__lt__", "__len__", "__getitem__"],
                "prerequisites": ["oop.classes_basics"],
            },
            "properties_descriptors": {
                "name": "Properties & Descriptors",
                "topics": ["@property", "getter/setter", "descriptors", "slots"],
                "prerequisites": ["oop.inheritance"],
            },
            "solid_principles": {
                "name": "SOLID Principles",
                "topics": ["SRP", "OCP", "LSP", "ISP", "DIP"],
                "prerequisites": ["oop.inheritance", "oop.dunder_methods"],
            },
        },
    },
    "functional": {
        "name": "Functional Programming",
        "icon": "🌀",
        "description": "Flow like water through your code.",
        "skills": {
            "lambdas": {
                "name": "Lambdas & HOFs",
                "topics": ["lambda", "map", "filter", "reduce", "sorted key"],
                "prerequisites": ["fundamentals.functions"],
            },
            "decorators": {
                "name": "Decorators",
                "topics": ["function decorators", "wraps", "parameterized", "class decorators"],
                "prerequisites": ["functional.lambdas", "fundamentals.functions"],
            },
            "generators": {
                "name": "Generators & Iterators",
                "topics": ["yield", "generator expressions", "itertools", "lazy evaluation"],
                "prerequisites": ["data_structures.comprehensions"],
            },
            "closures": {
                "name": "Closures & Scoping",
                "topics": ["closures", "nonlocal", "encapsulation", "factory functions"],
                "prerequisites": ["functional.lambdas"],
            },
        },
    },
    "error_handling": {
        "name": "Error Handling",
        "icon": "🛡️",
        "description": "A true warrior prepares for failure.",
        "skills": {
            "exceptions": {
                "name": "Exceptions",
                "topics": ["try/except/finally", "raise", "exception hierarchy", "multiple except"],
                "prerequisites": ["fundamentals.functions"],
            },
            "custom_exceptions": {
                "name": "Custom Exceptions",
                "topics": ["exception classes", "exception chaining", "context info"],
                "prerequisites": ["error_handling.exceptions", "oop.classes_basics"],
            },
            "context_managers": {
                "name": "Context Managers",
                "topics": ["with statement", "__enter__/__exit__", "contextlib", "nested"],
                "prerequisites": ["error_handling.exceptions"],
            },
        },
    },
    "testing": {
        "name": "Testing",
        "icon": "🧪",
        "description": "Trust nothing. Verify everything.",
        "skills": {
            "unittest_basics": {
                "name": "Unit Testing",
                "topics": ["assert", "unittest", "test cases", "test runners"],
                "prerequisites": ["fundamentals.functions", "oop.classes_basics"],
            },
            "pytest": {
                "name": "Pytest Mastery",
                "topics": ["fixtures", "parametrize", "markers", "conftest", "plugins"],
                "prerequisites": ["testing.unittest_basics"],
            },
            "mocking": {
                "name": "Mocking & Patching",
                "topics": ["Mock", "patch", "MagicMock", "side_effect", "spec"],
                "prerequisites": ["testing.pytest"],
            },
            "tdd": {
                "name": "Test-Driven Development",
                "topics": ["red-green-refactor", "test-first", "coverage", "design by contract"],
                "prerequisites": ["testing.pytest"],
            },
        },
    },
    "async_concurrent": {
        "name": "Async & Concurrency",
        "icon": "⚡",
        "description": "Master the art of doing many things at once.",
        "skills": {
            "threading": {
                "name": "Threading",
                "topics": ["Thread", "Lock", "GIL", "ThreadPoolExecutor", "race conditions"],
                "prerequisites": ["fundamentals.functions", "oop.classes_basics"],
            },
            "asyncio": {
                "name": "Asyncio",
                "topics": ["async/await", "event loop", "gather", "tasks", "semaphores"],
                "prerequisites": ["functional.generators"],
            },
            "multiprocessing": {
                "name": "Multiprocessing",
                "topics": ["Process", "Pool", "Queue", "shared memory", "ProcessPoolExecutor"],
                "prerequisites": ["async_concurrent.threading"],
            },
        },
    },
    "design_patterns": {
        "name": "Design Patterns",
        "icon": "🎯",
        "description": "Ancient wisdom encoded in code.",
        "skills": {
            "creational": {
                "name": "Creational Patterns",
                "topics": ["Singleton", "Factory", "Builder", "Prototype"],
                "prerequisites": ["oop.solid_principles"],
            },
            "structural": {
                "name": "Structural Patterns",
                "topics": ["Adapter", "Decorator", "Facade", "Proxy"],
                "prerequisites": ["oop.solid_principles"],
            },
            "behavioral": {
                "name": "Behavioral Patterns",
                "topics": ["Observer", "Strategy", "Command", "State"],
                "prerequisites": ["oop.solid_principles"],
            },
        },
    },
}

# ── Session Lengths ────────────────────────────────────────────────
SESSION_LENGTHS = {
    "quick":  {"name": "Quick Drill",       "minutes": 5,  "challenges": 1, "quizzes": 2},
    "medium": {"name": "Training Session",   "minutes": 15, "challenges": 2, "quizzes": 3},
    "deep":   {"name": "Deep Practice",      "minutes": 30, "challenges": 3, "quizzes": 5},
    "endurance": {"name": "Endurance Round", "minutes": 60, "challenges": 5, "quizzes": 8},
}

# ── Sensei Personality ─────────────────────────────────────────────
SENSEI_SYSTEM_PROMPT = """You are Sensei — a strict but wise coding master in the CodeDojo.
Your personality:
- You speak like a martial arts master: deliberate, metaphorical, wise
- You are encouraging but NEVER give away answers easily
- You use dojo/martial arts metaphors naturally (not forced)
- You address the student as "student" or by name
- You are brief and impactful — no walls of text
- When a student struggles, you guide with questions, not answers
- When they succeed, you acknowledge it simply but meaningfully
- You occasionally reference the journey, discipline, patience
- You have dry humor but never mock the student

Examples of your voice:
- "A function without a return value is like a punch that never lands."
- "You rush. Speed comes after precision."
- "Good. But good is not enough. Again."
- "The error message is not your enemy — it is your teacher."

IMPORTANT: You respond ONLY as Sensei. Stay in character at all times.
Do not break the fourth wall or reference being an AI."""

SENSEI_GREETING_PROMPT = """The student {name} has returned to the dojo.
Their current rank: {belt_name} {belt_icon} ({xp} XP)
Days since last visit: {days_away}
Current streak: {streak} days
Weakest skill area: {weak_area}
Strongest skill area: {strong_area}

Generate a brief greeting (2-3 sentences max) that:
1. Acknowledges their return (or welcomes them if first time)
2. References their progress or an area to improve
3. Sets the tone for today's training

Respond with ONLY the greeting dialogue. No stage directions."""

SENSEI_FAREWELL_PROMPT = """The student {name} is leaving the dojo.
They earned {xp_earned} XP this session.
Activities completed: {activities}
Current rank after session: {belt_name} {belt_icon}
{promotion_note}

Generate a brief farewell (1-2 sentences) that:
1. Acknowledges their effort today
2. Leaves them motivated to return

Respond with ONLY the farewell dialogue."""
