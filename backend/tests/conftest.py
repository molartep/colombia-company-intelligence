import copy
import json
from pathlib import Path

import pytest


@pytest.fixture
def record():
    """Synthetic company; never used by the running application."""
    return {
        "upstream_id": "row-synthetic-001",
        "codigo_camara": "99",
        "camara_comercio": "SYNTHETIC CHAMBER",
        "matricula": "TEST001",
        "razon_social": "COMPAÑÍA SINTÉTICA ANDINA S.A.S.",
        "nit": "000123456",
        "digito_verificacion": "7",
        "organizacion_juridica": "SOCIEDAD POR ACCIONES SIMPLIFICADA",
        "estado_matricula": "ACTIVA",
        "cod_ciiu_act_econ_pri": "0011",
        "fecha_matricula": "20200115",
        "fecha_renovacion": "20250120",
        "fecha_actualizacion": "2025/01/20 10:30:00.000000000",
        "num_identificacion_representante_legal": "SYNTHETIC-PRIVATE-ID",
        "representante_legal": "SYNTHETIC PRIVATE PERSON",
    }


@pytest.fixture
def metadata():
    return copy.deepcopy(
        json.loads((Path(__file__).parents[2] / "docs/discovery/metadata.json").read_text())
    )
