"""
Data processing package for the VRPTW.

Responsible for the entire data pipeline: student record preprocessing
(geocoding, address enrichment) and bus stop point generation via
K-means clustering.

Data subdirectories:
    - ``raw/``        — raw input data (student CSVs).
    - ``processed/``  — processed data ready for the model.
"""
