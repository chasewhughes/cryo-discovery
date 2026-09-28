"""Cryo hydration v1: unique-water counts and an equal-frame nearest-distance PDF.

This is an explicitly defined new representation, not a reproduced DOLMEN PCF.
Solute selection includes hydrogens. Water selection includes oxygen only.
"""
import numpy as np

VERSION = 'cryo-nearest-water-v1'
CUTOFFS = np.array([.20, .25, .30, .35, .40, .45, .50])
EDGES = np.linspace(0, .5, 101)


def measure(xyz, box, solute_indices, water_oxygen_indices):
    xyz, box = np.asarray(xyz, dtype=float), np.asarray(box, dtype=float)
    sol, wat = np.asarray(solute_indices), np.asarray(water_oxygen_indices)
    if xyz.ndim != 2 or xyz.shape[1] != 3 or not np.isfinite(xyz).all():
        raise ValueError('Coordinates must be finite Nx3')
    if box.shape != (3, 3) or not np.isfinite(box).all() or not np.allclose(box, np.diag(np.diag(box)), atol=1e-8):
        raise ValueError('Requires a finite orthorhombic box')
    lengths = np.diag(box)
    if np.any(lengths <= 2 * EDGES[-1]):
        raise ValueError('Box too small for the descriptor range')
    for indices in (sol, wat):
        if indices.ndim != 1 or not len(indices) or not np.issubdtype(indices.dtype, np.integer) or len(set(indices)) != len(indices) or np.any(indices < 0) or np.any(indices >= len(xyz)):
            raise ValueError('Selections must be nonempty unique valid atom indices')
    if np.intersect1d(sol, wat).size:
        raise ValueError('Solute and water selections must be disjoint')
    delta = xyz[wat, None, :] - xyz[None, sol, :]
    delta -= lengths * np.rint(delta / lengths)
    nearest = np.linalg.norm(delta, axis=2).min(axis=1)
    counts = np.array([np.count_nonzero(nearest <= cutoff) for cutoff in CUTOFFS])
    hist = np.histogram(nearest, bins=EDGES)[0]
    if not hist.sum():
        raise ValueError('No waters in the histogram range')
    return counts, hist / (hist.sum() * np.diff(EDGES))
