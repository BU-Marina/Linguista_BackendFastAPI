"""Container for exercises-related ORM models."""

from apps.exercises.models import (
    Exercise,
    FavoriteExercise,
    ExerciseConfiguration,
    ExerciseSessionHistory,
    WordsSet,
    Hint,
)

EXERCISE_MODELS = {
    'Exercise': Exercise,
    'FavoriteExercise': FavoriteExercise,
    'ExerciseConfiguration': ExerciseConfiguration,
    'ExerciseSessionHistory': ExerciseSessionHistory,
    'WordsSet': WordsSet,
    'Hint': Hint,
}
