"""Persistent top-10 highscore table stored as JSON.

Owner: Person B
Planned contents: HighscoreEntry, sanitize_name(), is_valid_name(),
  is_valid_score(), HighscoreTable (load tolerant to missing/corrupt file,
  atomic save via temp file + rename).
"""
