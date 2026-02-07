"""Geração de pontos de parada de ônibus via clusterização K-means.

Utiliza dados geográficos dos alunos para identificar locais ótimos de
parada, aplicando o método do cotovelo (Kneedle) para determinar o número
ideal de clusters por município.

Pipeline:
    1. Para cada município com alunos suficientes, executa K-means para
       uma faixa de valores de k e registra a inércia (WCSS).
    2. Identifica o "cotovelo" na curva de inércia.
    3. Gera os centroides finais e calcula a demanda por turno/dia.

.. note::
    Este módulo **não realiza leitura nem escrita em disco**. A função
    ``generate_bus_stops`` recebe e retorna DataFrames, garantindo
    idempotência do pipeline.

Exemplo de uso:
    >>> from data.point_generation import generate_bus_stops
    >>> df_stops = generate_bus_stops(df_students, student_filter="full", shift="SAIDA")
"""

import logging

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.cluster import k_means

from vrptw.config import (
    IMGS_DIR,
    KMEANS_N_INIT,
    MIN_STUDENTS_PER_MUNICIPALITY,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Método do cotovelo
# ---------------------------------------------------------------------------

def _plot_elbow(
    k_values: np.ndarray,
    inertias: np.ndarray,
    elbow_k: int,
    elbow_index: int,
) -> None:
    """Plota o gráfico do método do cotovelo e salva como imagem.

    Desenha a curva de inércia, a reta de referência (primeiro ao último ponto)
    e uma perpendicular no ponto de cotovelo para visualização.

    Args:
        k_values: Valores de k testados.
        inertias: Valores de inércia correspondentes (serão escalados ×10⁴).
        elbow_k: Valor de k identificado como cotovelo.
        elbow_index: Índice do cotovelo nos arrays.
    """
    scaled_inertias = inertias * 10_000

    elbow_x = k_values[elbow_index]
    elbow_y = scaled_inertias[elbow_index]

    x1, y1 = k_values[0], scaled_inertias[0]
    x2, y2 = k_values[-1], scaled_inertias[-1]

    # Inclinação da reta de referência e sua perpendicular
    if x2 - x1 != 0:
        ref_slope = (y2 - y1) / (x2 - x1)
    else:
        ref_slope = np.inf

    if ref_slope not in (0, np.inf):
        perp_slope = -1 / ref_slope
    elif ref_slope == 0:
        perp_slope = np.inf
    else:
        perp_slope = 0

    x_range = np.linspace(min(k_values), max(k_values), 100)
    if perp_slope != np.inf:
        perp_y = perp_slope * (x_range - elbow_x) + elbow_y
    else:
        perp_y = np.linspace(min(scaled_inertias), max(scaled_inertias), 100)
        x_range = np.full_like(perp_y, elbow_x)

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(k_values, scaled_inertias, "bo-", label="Curva de Inércia")
    ax.plot([x1, x2], [y1, y2], "r-", label="Reta de Referência")
    ax.plot(elbow_x, elbow_y, "go", markersize=10, label=f"Cotovelo (k={elbow_k})")
    ax.plot(x_range, perp_y, "g--", label="Perpendicular no Cotovelo")

    ax.set_xlabel("Número de Clusters (k)")
    ax.set_ylabel("Inércia (WCSS) × 10⁴")
    ax.set_xticks(k_values)
    ax.set_aspect("equal", "box")
    ax.grid(True)

    amplitude = max(scaled_inertias) - min(scaled_inertias)
    ax.set_ylim(
        min(scaled_inertias) - 0.1 * amplitude,
        max(scaled_inertias) + 0.1 * amplitude,
    )
    ax.legend(loc="lower center", ncol=4, fancybox=True, shadow=True,
              bbox_to_anchor=(0.5, -0.2))
    fig.tight_layout()

    IMGS_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(IMGS_DIR / "ilustracao_cotovelo.png")
    plt.close(fig)


def find_elbow(
    k_values: list | np.ndarray,
    inertias: list | np.ndarray,
    plot: bool = False,
) -> int:
    """Encontra o k ótimo pelo método do cotovelo (Kneedle).

    Identifica o ponto na curva de inércia com maior distância perpendicular
    à reta traçada entre o primeiro e o último ponto.

    Args:
        k_values: Valores de k testados.
        inertias: Valores de inércia correspondentes.
        plot: Se ``True``, gera e salva o gráfico do cotovelo.

    Returns:
        Valor de k considerado ótimo.
    """
    k_arr = np.array(k_values)
    inertia_arr = np.array(inertias)

    x1, y1 = k_arr[0], inertia_arr[0]
    x2, y2 = k_arr[-1], inertia_arr[-1]

    line_vec = np.array([x2 - x1, y2 - y1])
    line_unit = line_vec / np.linalg.norm(line_vec)

    points = np.vstack((k_arr, inertia_arr)).T
    from_start = points - np.array([x1, y1])

    projections = np.outer(np.dot(from_start, line_unit), line_unit)
    perpendicular = from_start - projections
    distances = np.linalg.norm(perpendicular, axis=1)

    elbow_idx = int(np.argmax(distances))

    if plot:
        _plot_elbow(k_arr, inertia_arr, k_arr[elbow_idx], elbow_idx)

    return k_arr[elbow_idx]


# ---------------------------------------------------------------------------
# Geração de pontos de parada
# ---------------------------------------------------------------------------

def generate_bus_stops(
    df_students: pd.DataFrame,
    student_filter: str = "full",
    shift: str = "SAIDA",
) -> pd.DataFrame:
    """Gera pontos de parada (centroides) a partir dos dados dos alunos.

    Para cada município com alunos suficientes, aplica K-means e o método
    do cotovelo para definir o número ideal de clusters. Calcula a demanda
    por turno e dia da semana para cada centroide gerado.

    **Não realiza leitura nem escrita em disco** — recebe e retorna
    DataFrames, garantindo idempotência.

    Args:
        df_students: DataFrame com os dados dos alunos (saída do
            pré-processamento).
        student_filter: Filtro de tipo de aluno (``"full"`` para todos,
            ``"tec"`` para técnico, ``"grad"`` para graduação).
        shift: Turno a considerar (``"ENTRADA"`` ou ``"SAIDA"``).

    Returns:
        DataFrame com colunas ``lon``, ``lat``, ``cd_municipio``,
        ``demanda_manha``, ``demanda_tarde``, ``demanda_noite``,
        ``demanda_fim`` e ``dia``.
    """
    logger.info("Gerando pontos de parada: filtro=%s, turno=%s", student_filter, shift)

    # Copiar para não modificar o DataFrame original do chamador
    df_students = df_students.copy()

    if student_filter != "full":
        df_students = df_students[
            df_students["id_aluno"].str.contains(student_filter)
        ]

    municipalities = df_students["CIDADE"].unique()
    weekdays = df_students["DIA"].unique()

    bus_stops: list[pd.DataFrame] = []
    skipped_municipalities = 0
    skipped_students = 0

    for municipality in municipalities:
        mun_students = df_students[
            df_students["CIDADE"] == municipality
        ].drop_duplicates(subset="id_aluno")

        if len(mun_students) < MIN_STUDENTS_PER_MUNICIPALITY:
            skipped_municipalities += 1
            skipped_students += len(mun_students)
            continue

        logger.info("Município: %s | Alunos: %d", municipality, len(mun_students))

        # Determinar k ótimo via método do cotovelo
        k_range = range(2, len(mun_students) + 1)
        wcss = []
        for k in k_range:
            _, _, inertia = k_means(
                mun_students[["LATITUDE", "LONGITUDE"]], k, n_init=KMEANS_N_INIT,
            )
            wcss.append(inertia)

        optimal_k = find_elbow(k_range, wcss, plot=False)

        # Gerar centroides com k ótimo
        centroids, classes, _ = k_means(
            mun_students[["LATITUDE", "LONGITUDE"]], optimal_k, n_init=KMEANS_N_INIT,
        )
        mun_students = mun_students.copy()
        mun_students["class"] = classes

        merged = df_students.merge(
            mun_students[["id_aluno", "class"]], how="left", on="id_aluno",
        )

        for day in weekdays:
            centroids_df = pd.DataFrame(centroids, columns=["lon", "lat"])
            centroids_df["cd_municipio"] = municipality

            day_filter = merged["DIA"] == day
            shift_col = f"TURNO_{shift}"

            for demand_name, shift_value in [
                ("demanda_manha", "manhã"),
                ("demanda_tarde", "tarde"),
                ("demanda_noite", "noite"),
                ("demanda_fim", "fim"),
            ]:
                demand = (
                    merged[(merged[shift_col] == shift_value) & day_filter]
                    .groupby("class")[shift_col]
                    .count()
                )
                centroids_df.loc[demand.index, demand_name] = demand

            centroids_df["dia"] = day
            centroids_df.fillna(0, inplace=True)
            bus_stops.append(centroids_df)

    result = pd.concat(bus_stops, ignore_index=True)

    logger.info(
        "Municípios desconsiderados: %d | Alunos desconsiderados: %d",
        skipped_municipalities,
        skipped_students,
    )

    return result
