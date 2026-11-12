"""Erros de domínio para leitura operacional dos eventos."""


class EventoNaoEncontrado(LookupError):
    """ID ou data não disponíveis no cache."""


class DadosInconsistentes(ValueError):
    """Arquivos ausentes/incompatíveis, hashes divergentes ou GeoJSON inválido."""


class EntradaInvalida(ValueError):
    """Parâmetros de consulta inválidos."""
