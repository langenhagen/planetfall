"""Tests for game scene blueprint data."""

from unittest import TestCase

from fooproj.game.scene import starter_scene_blueprints

CHECKER = TestCase()


def test_starter_scene_models() -> None:
    """Define a large mixed-shape world with a ground plane."""
    blueprints = starter_scene_blueprints()
    models = [blueprint.model for blueprint in blueprints]
    unique_models = set(models)
    CHECKER.assertEqual(models[0], "plane")
    CHECKER.assertIn("cube", unique_models)
    CHECKER.assertIn("sphere", unique_models)
    CHECKER.assertNotIn("cylinder", unique_models)
    CHECKER.assertGreaterEqual(len(models), 80)


def test_starter_scene_positions_are_above_ground() -> None:
    """Keep all starter entities at or above y=0."""
    blueprints = starter_scene_blueprints()
    is_above_ground = all(blueprint.position.y >= 0.0 for blueprint in blueprints)
    CHECKER.assertTrue(is_above_ground)


def test_starter_scene_spans_large_distances() -> None:
    """Place landmarks far from origin to show expanded world scale."""
    blueprints = starter_scene_blueprints()
    max_axis_distance = max(
        max(abs(blueprint.position.x), abs(blueprint.position.z))
        for blueprint in blueprints
    )
    CHECKER.assertGreaterEqual(max_axis_distance, 110.0)
