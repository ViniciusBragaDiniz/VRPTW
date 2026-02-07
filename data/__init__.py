"""
Pacote de tratamento de dados para o VRPTW.

Responsável por todo o pipeline de dados: pré-processamento dos registros
de alunos (geocodificação, enriquecimento de endereços) e geração de pontos
de parada via clusterização K-means.

Subdiretórios de dados:
    - ``raw/``        — dados brutos de entrada (CSVs de alunos).
    - ``processed/``  — dados tratados e prontos para o modelo.
"""
