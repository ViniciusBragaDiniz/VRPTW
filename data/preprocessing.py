"""Pré-processamento dos dados de alunos para o VRPTW.

Responsável por carregar, limpar, enriquecer e georreferenciar os dados
dos alunos. O pipeline inclui:

1. Carregamento dos CSVs de alunos (nível médio e graduação).
2. Filtragem de CEPs válidos (estado do Rio de Janeiro).
3. Enriquecimento de endereços via API ViaCEP.
4. Georreferenciamento via API Google Maps Geocoding.
5. Padronização de nomes de cidades/bairros.
6. Merge com dados de turnos por curso.
7. Salvamento dos arquivos processados.

Pré-requisitos:
    - Arquivo ``secrets`` na raiz do projeto com ``GOOGLEMAPS_APIKEY=<chave>``.
    - Arquivos de entrada em ``data/raw/`` e ``data/processed/``.

Exemplo de uso:
    >>> from data.preprocessing import preprocess_student_data
    >>> preprocess_student_data()  # processa e salva os dados
"""

import logging
import os
import unicodedata
from time import sleep

import googlemaps
import pandas as pd
import requests

from vrptw.config import DATA_PROCESSED_DIR, DATA_RAW_DIR, PROJECT_ROOT

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Funções auxiliares
# ---------------------------------------------------------------------------

def _build_full_address(row: pd.Series) -> str:
    """Constrói endereço completo a partir de campos individuais.

    Concatena os campos não vazios e acrescenta "Rio de Janeiro, Brasil".

    Args:
        row: Série com campos de endereço (LOGRADOURO, BAIRRO, CIDADE, etc.).

    Returns:
        Endereço completo formatado como string.
    """
    parts = [str(v) for v in row if isinstance(v, str) and v.strip()]
    parts.extend(["Rio de Janeiro", "Brasil"])
    return ", ".join(parts)


def _remove_accents(text: str) -> str:
    """Remove acentos de um texto usando decomposição Unicode NFD.

    Args:
        text: Texto com possíveis acentos.

    Returns:
        Texto sem acentos.
    """
    normalized = unicodedata.normalize("NFD", text)
    return "".join(c for c in normalized if unicodedata.category(c) != "Mn")


def _load_api_key() -> str:
    """Carrega a chave da API do Google Maps a partir do arquivo ``secrets``.

    O arquivo deve ter o formato ``CHAVE=VALOR`` (uma por linha).

    Returns:
        Chave da API do Google Maps.

    Raises:
        FileNotFoundError: Se o arquivo ``secrets`` não existir.
        KeyError: Se ``GOOGLEMAPS_APIKEY`` não estiver definida.
    """
    secrets_path = PROJECT_ROOT / "secrets"
    if not secrets_path.exists():
        raise FileNotFoundError(
            f"Arquivo de segredos não encontrado: {secrets_path}. "
            "Crie um arquivo 'secrets' com a linha GOOGLEMAPS_APIKEY=<sua_chave>."
        )

    with open(secrets_path, "r") as f:
        for line in f.read().splitlines():
            if "=" in line:
                key, value = line.split("=", 1)
                os.environ[key.strip()] = value.strip()

    api_key = os.getenv("GOOGLEMAPS_APIKEY")
    if not api_key:
        raise KeyError("GOOGLEMAPS_APIKEY não encontrada no arquivo 'secrets'.")
    return api_key


# ---------------------------------------------------------------------------
# Enriquecimento de endereço via ViaCEP
# ---------------------------------------------------------------------------

def _enrich_addresses_viacep(df: pd.DataFrame) -> int:
    """Preenche LOGRADOURO e COMPLEMENTO ausentes usando a API ViaCEP.

    Args:
        df: DataFrame de alunos (modificado in-place).

    Returns:
        Número de CEPs não encontrados.
    """
    missing_idx = df.loc[df["LOGRADOURO"] == ""].index
    not_found = 0

    for idx in missing_idx:
        cep = df.loc[idx, "CEP"]
        url = f"https://viacep.com.br/ws/{cep}/json/"
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                df.loc[idx, "LOGRADOURO"] = data.get("logradouro", "")
                df.loc[idx, "COMPLEMENTO"] = data.get("complemento", "")
            else:
                logger.warning("CEP %s: HTTP %d", cep, response.status_code)
                not_found += 1
        except Exception as e:
            logger.error("Erro ao consultar CEP %s: %s", cep, e)
            not_found += 1
        sleep(0.5)

    return not_found


# ---------------------------------------------------------------------------
# Georreferenciamento via Google Maps
# ---------------------------------------------------------------------------

def _geocode_students(df: pd.DataFrame, gmaps_client: googlemaps.Client) -> None:
    """Obtém latitude/longitude para alunos sem geolocalização.

    Args:
        df: DataFrame de alunos (modificado in-place). Deve conter a coluna
            ``ENDERECO_COMPLETO`` e as colunas ``LATITUDE`` / ``LONGITUDE``.
        gmaps_client: Cliente autenticado da API Google Maps.
    """
    missing_idx = df[df["LATITUDE"] == 0].index

    for i, address in enumerate(df["ENDERECO_COMPLETO"]):
        if i not in missing_idx:
            continue

        try:
            result = gmaps_client.geocode(address)
            if result:
                location = result[0]["geometry"]["location"]
                df.loc[i, "LATITUDE"] = location["lat"]
                df.loc[i, "LONGITUDE"] = location["lng"]
            else:
                logger.warning("Geocoding sem resultado para: %s", address)
        except Exception as e:
            logger.error("Erro no geocoding do índice %d: %s", i, e)

        if (i + 1) % 50 == 0:
            logger.info("Geocoding: %d/%d processados", i + 1, len(df))


# ---------------------------------------------------------------------------
# Pipeline principal
# ---------------------------------------------------------------------------

def preprocess_student_data() -> pd.DataFrame:
    """Executa o pipeline completo de pré-processamento dos dados de alunos.

    Carrega os dados brutos, enriquece endereços, georreferencia, padroniza
    nomes e salva os resultados.

    Returns:
        DataFrame consolidado com todos os alunos processados.
    """
    logger.info("Iniciando pré-processamento de dados de alunos")

    # --- Carregar dados de turno ---
    df_shifts = pd.read_csv(DATA_PROCESSED_DIR / "turno_resumo.csv", sep=";")

    # --- Carregar e unificar dados de alunos ---
    df_medio = pd.read_csv(DATA_RAW_DIR / "info_medio.csv")
    df_medio["id_aluno"] = "tec_" + df_medio.index.astype(str)

    df_grad = pd.read_csv(DATA_RAW_DIR / "info_graduacao.csv")
    df_grad["id_aluno"] = "grad_" + df_grad.index.astype(str)

    df = pd.concat([df_medio, df_grad], ignore_index=True)

    # --- Filtrar CEPs do Rio de Janeiro (iniciam com '2') ---
    valid_ceps = df["CEP"].apply(lambda x: str(x)[0] == "2")
    logger.info("CEPs inválidos (fora do RJ): %d", len(df) - valid_ceps.sum())
    df = df.loc[valid_ceps].reset_index(drop=True)

    # --- Inicializar colunas para evitar erros em reprocessamento ---
    for col, default in [("COMPLEMENTO", ""), ("LOGRADOURO", ""),
                         ("LONGITUDE", 0), ("LATITUDE", 0)]:
        if col not in df.columns:
            df[col] = default
        else:
            df[col] = df[col].fillna(default)

    # --- Enriquecer endereços via ViaCEP ---
    not_found = _enrich_addresses_viacep(df)
    logger.info("CEPs não encontrados no ViaCEP: %d", not_found)

    # --- Georreferenciamento ---
    api_key = _load_api_key()
    gmaps_client = googlemaps.Client(key=api_key)

    address_cols = ["LOGRADOURO", "BAIRRO", "CIDADE", "CEP", "COMPLEMENTO"]
    df["ENDERECO_COMPLETO"] = df[address_cols].apply(_build_full_address, axis=1)
    _geocode_students(df, gmaps_client)

    # --- Padronização de nomes ---
    df["CIDADE"] = df["CIDADE"].apply(lambda x: _remove_accents(x).title())
    df["BAIRRO"] = df["BAIRRO"].apply(lambda x: _remove_accents(x).title())

    # --- Merge com turnos e salvamento ---
    df = df_shifts.merge(df, how="left", on=["CURSO", "PERÍODO_ATUAL"])
    DATA_PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(DATA_PROCESSED_DIR / "info_alunos.csv", index=False)

    # Salvar separadamente por nível
    df_tec = df[df["id_aluno"].str.contains("tec")].drop_duplicates(subset="id_aluno")
    df_tec.to_csv(DATA_PROCESSED_DIR / "info_medio.csv", index=False)

    df_grad_out = df[df["id_aluno"].str.contains("grad")].drop_duplicates(subset="id_aluno")
    df_grad_out.to_csv(DATA_PROCESSED_DIR / "info_graduacao.csv", index=False)

    logger.info("Pré-processamento concluído. %d alunos processados.", len(df))
    return df
