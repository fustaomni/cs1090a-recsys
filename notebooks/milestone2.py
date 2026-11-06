# notebooks/milestone2.py
# %% [markdown]
# # Milestone 2: MovieLens 1M (A.244, the walking skeleton)
#
# This notebook is a py:percent text notebook: a plain Python file, versioned and tested as code.
# `milestone2.run_notebook` verifies the archive against its pinned SHA-256, extracts
# `ratings.dat`, and gives its path here as `RATINGS`. The notebook's one finding so far is the
# count of ratings, which the run records with the archive's digest.

# %%
from pathlib import Path

from model_run import read_ratings

# GIVEN BY milestone2.run_notebook, never defaulted: a run without it fails here, by name.
RATINGS = Path(globals()["RATINGS"])

# %%
ratings_count = len(read_ratings(RATINGS))
