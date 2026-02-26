"""Helpers for post-processing and render mode state transitions."""


def next_post_process_option(
    *,
    current_index: int,
    options: tuple[tuple[str, object | None], ...],
) -> tuple[int, str, object | None]:
    """Advance and wrap post-process selection, returning index and option."""
    if not options:
        msg = "post process options cannot be empty"
        raise ValueError(msg)

    next_index = (current_index + 1) % len(options)
    next_name, next_shader = options[next_index]
    return next_index, next_name, next_shader


def toggle_render_mode(current_mode: str) -> str:
    """Toggle render mode between default and wireframe."""
    return "wireframe" if current_mode != "wireframe" else "default"
