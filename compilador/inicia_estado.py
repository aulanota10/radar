#!/usr/bin/env python3
"""Cria o esqueleto de concurso-<slug>.json (esquema v2) e, se não existir, triagem-<slug>.json.

Uso:
    python inicia_estado.py <slug> [--pasta DIR]

Escreve os arquivos na pasta atual (ou em --pasta). Não sobrescreve arquivo existente.
"""

import argparse
import json
import os
from datetime import date

ESCOPO_VAZIO = {"padrao": {}, "por_escopo": []}


def escopo(padrao):
    return {"padrao": padrao, "por_escopo": []}


def tempo():
    return {
        "nominal_min": None, "tolerancia_menos_min": None, "tolerancia_mais_min": None,
        "piso_eliminatorio_min": None, "piso_penalidade_min": None, "piso_sem_consequencia_min": None, "teto_min": None, "interrupcao_min": None,
        "consequencia_fora_da_tolerancia": None,
        "penalidade": {"valor": None, "unidade": None, "limite": None, "aplicacao": None},
    }


def secoes():
    return {"itens": [], "modalidade_literal": None, "ordem_obrigatoria": None}


def documento_memorial():
    return {
        "definicao_literal": None, "finalidade_literal": None, "remissao": None,
        "conteudo_exigido": [], "janela_temporal": [], "exigencias_redacao": [],
        "extensao": None, "formatacao": None, "arquivo": None, "comprobatorios": None,
        "entrega": {"meio": None, "vias": None, "prazo": None, "quem_entrega": None, "consequencia": None},
    }


def modulo_didatica():
    return escopo({
        "existe": None, "nome_literal": None, "temas": [], "regra_exclusao_tema": None,
        "pdd": {"tempo": tempo(), "montagem": None, "arguicao": None, "sorteio": None},
        "recursos": {"fornecidos": [], "proibidos": [], "proprios_permitidos": None,
                     "entrega_material": None, "observacoes": None},
        "plano_de_aula": {
            "exigido": None, "modelo_obrigatorio": None, "modelo_referencia": None,
            "secoes_exigidas": secoes(), "numero_de_vias": None, "formato_entrega": None,
            "momento_entrega": None, "envio_digital": None, "exige_minutagem_na_metodologia": None,
            "consequencia_nao_entrega": None, "referencias": {"janela_anos": None},
        },
        "barema": None,
    })


def modulo_escrita():
    return escopo({
        "existe": None, "nome_literal": None, "formato": None, "numero_questoes": None,
        "parte_objetiva_existe": None,
        "conteudo": {"origem": None, "temas": [], "lista_compartilhada_com_didatica": None,
                     "regra_exclusao_didatica": None},
        "sorteio": None,
        "tempo": {"duracao_total_min": None, "permanencia_minima_min": None},
        "consulta": {"situacao": None, "duracao_min": None, "posicao": None, "material": None,
                     "anotacoes_previas": None, "escrita_durante": None},
        "extensao": None, "meio_de_escrita": None, "anonimato": None, "leitura_publica": None,
        "acesso_a_prova": None, "regras_literais": [],
        "avaliacao": {"barema": None, "corte_por_classificacao": None},
    })


def modulo_objetiva():
    return escopo({
        "existe": None, "nome_literal": None, "formato_item": None, "total_questoes": None,
        "pontuacao_maxima": None, "regra_pontuacao_literal": None, "desconto_por_erro": None,
        "componentes": [], "conteudo_geral": None, "vigencia_legislacao_literal": None,
    })


def modulo_memorial():
    return escopo({
        "existe": None, "nome_literal": None, "configuracao": None, "juncao_projeto": None,
        "documento": documento_memorial(), "avaliacoes": [],
    })


def modulo_projeto():
    return escopo({
        "existe": None, "nome_literal": None, "vinculo_memorial": None, "escopo_delegado": None,
        "areas_citadas_literal": [], "articulacao_institucional_literal": None,
        "pecas": [], "documento": documento_memorial(), "avaliacoes": [],
    })


def modulo_titulos():
    return escopo({
        "existe": None, "nome_literal": None, "pontuacao_maxima": None, "teto_geral": None,
        "normalizacao": None, "barema": None, "grupos": [], "areas_para_pontuacao": [],
        "regras_contagem_literais": [], "exclusoes_literais": [], "comprovacao_literais": [],
        "formulario_oficial": None, "entrega": None,
    })


def modulo_pratica():
    return escopo({"existe": None, "nome_literal": None, "barema": None, "regras_literais": []})


MODULOS = {
    "didatica": modulo_didatica, "escrita": modulo_escrita, "objetiva": modulo_objetiva,
    "memorial": modulo_memorial, "projeto": modulo_projeto, "titulos": modulo_titulos,
    "pratica": modulo_pratica,
}


def esqueleto():
    return {
        "controle": {"versao_esquema": "2.1", "extraido_em": date.today().isoformat(),
                     "estado_extracao": "em_extracao", "conferida_em": None, "passadas": []},
        "instituicao": None, "sigla": None, "numero_edital": None, "carreira": None,
        "data_ato": None, "data_publicacao": None, "organizadora": None, "cidade_uf": None,
        "url_oficial": None, "email_oficial": None, "validade_concurso": None,
        "vagas": [],
        "remuneracao": {"vencimento_basico": [], "retribuicao_por_titulacao": [], "remuneracao_total": []},
        "inscricao": escopo({"inscricao_inicio": None, "inscricao_fim": None, "taxa": None,
                             "isencao_periodo": None, "pagamento_limite": None}),
        "reserva": {"regras": None, "distribuicao": []},
        "inscritos_homologados": [],
        "etapas": escopo({"lista": []}),
        "estrutura_de_pontuacao": escopo({"fases": [], "formula_final": None}),
        "eventos": [], "lotacoes": [], "alteracoes": [], "pendencias": [], "conflitos_internos": [],
        "recursos_administrativos": [],
        "restricoes_ao_recurso": escopo({"lista": []}),
        "acesso_a_documentos": [],
        "apuracao_da_nota": {"casas_decimais": None, "por_etapa": []},
        "formulario_recurso": {"campos": None, "anexos_permitidos": None},
        "regras_de_banca": {"composicao": None, "qualificacao_exigida": None, "declaracao_impedimentos": None,
                            "regra_impugnacao": None, "prazo_resultado": None, "criterios_impedimento": None},
        "bancas": [], "homologados": [], "impugnacoes": [],
        "didatica": None, "escrita": None, "objetiva": None, "memorial": None,
        "projeto": None, "titulos": None, "pratica": None,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("slug")
    ap.add_argument("--pasta", default=".")
    ap.add_argument("--modulo", choices=sorted(MODULOS), help="imprime só o esqueleto de um módulo")
    ap.add_argument("--sem-triagem", action="store_true", help="edital de pacote: não cria triagem (a do pacote é única)")
    a = ap.parse_args()
    if a.modulo:
        print(json.dumps(MODULOS[a.modulo](), ensure_ascii=False, indent=2))
        return
    arquivos = [(f"concurso-{a.slug}.json", esqueleto())] + ([] if a.sem_triagem else [(f"triagem-{a.slug}.json", [])])
    for nome, conteudo in arquivos:
        caminho = os.path.join(a.pasta, nome)
        if os.path.exists(caminho):
            print(f"já existe, não sobrescrito: {caminho}")
            continue
        with open(caminho, "w", encoding="utf-8") as f:
            json.dump(conteudo, f, ensure_ascii=False, indent=2)
        print(f"criado: {caminho}")


if __name__ == "__main__":
    main()
