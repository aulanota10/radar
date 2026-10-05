#!/usr/bin/env python3
"""Validação determinística de concurso-<slug>.json (esquema v2) e de triagem-<slug>.json.

Uso:
    python valida_concurso.py concurso-<slug>.json [--triagem triagem-<slug>.json] [--aceitar-conflitos]

Sai com código 0 quando não há ERRO, e 1 quando há.
Só verifica o que não depende de julgamento. Nada aqui substitui conferir o PDF.

O que o script confere:
  forma      valor com fonte, registro de lista, contêiner, invólucro de escopo; chaves conhecidas
  listas     tipo_evento, tipo de etapa, tipos de pendência e de documento, enumerações dos módulos
  dependente campo dependente nulo quando a condição é falsa, sem pendência
  somas      barema (itens contra soma_declarada), remuneração, componentes da objetiva, reserva ≤ vagas
  datas      ato ≤ publicação, inscrição, isenção, pagamento, piso ≤ nominal ≤ teto, consulta ≤ duração
  cadeia     "onde se lê" da alteração N igual ao "leia-se" da N-1 sobre o mesmo alvo
  banca      no máximo um presidente por banca (lotação, identificação e versão), funções, chave normalizada, nome em duas lotações
  homologados chave única por lotação, contagem contra inscritos_homologados
  fonte      item e trecho presentes, trecho curto, documento com ficha de triagem
  pendencias caminho existente, campos por tipo, essencial nulo sem pendência
  estado     conferida só sem verificar_no_pdf aberto
Com --aceitar-conflitos, uma falha cujo campo tem conflito_interno registrado vira AVISO.
"""

from email.utils import parsedate_to_datetime
import argparse
import json
import os
import re
import sys
import unicodedata

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from inicia_estado import esqueleto, MODULOS  # noqa: E402

ISO_DATA = re.compile(r"^\d{4}-\d{2}-\d{2}$")
ISO_HORA = re.compile(r"^\d{2}:\d{2}$")

TIPOS_ETAPA = {"objetiva", "escrita", "pratica", "didatica", "memorial", "projeto", "titulos",
               "defesa_producao", "seminario", "prova_oral", "compatibilidade_perfil", "outra"}  # sessão 14: quatro tipos sem módulo
ETAPA_REF_FORA_DE_ETAPA = {"todas", "inscricao", "isencao", "procedimento_cotas", "banca", "resultado_final"}  # recursos, sessão 14
MODALIDADES_LIMITE = {"ampla", "pcd", "negros", "indigenas", "quilombolas"}
ID_EVENTO = re.compile(r"^ev-\d{4}$")
MODULOS_NOMES = ["didatica", "escrita", "objetiva", "memorial", "projeto", "titulos", "pratica"]

TIPOS_EVENTO = {
    "publicacao_edital": (False, False), "impugnacao_edital": (False, False),
    "impugnacao_edital_resultado": (False, False), "inscricao": (False, False),
    "isencao_pedido": (False, False), "isencao_resultado": (False, True), "pagamento": (False, False),
    "atendimento_especial_resultado": (False, True), "homologacao_inscricoes": (False, True),
    "sorteio_reserva": (False, False), "portaria_banca": (False, False), "impugnacao_banca": (False, False),
    "impugnacao_banca_resultado": (False, False), "convocacao": (True, False), "sorteio_turma": (True, False),
    "sorteio_tema": (True, False), "confinamento": (True, False), "sorteio_ordem": (True, False),
    "entrega_documento": (True, False), "divulgacao_vinculo": (True, False), "prova": (True, False),
    "resultado": (True, True), "recurso": (None, False), "recurso_resultado": (None, False),
    "procedimento_cotas": (False, True),
    "resultado_final": (False, True), "homologacao_resultado": (False, False),
    "suspensao": (False, False), "retomada": (False, False), "prorrogacao": (False, False),
    "cancelamento": (False, False),  # sessão 15
    "outro": (None, False),
}

TIPOS_DOCUMENTO = {
    "edital_abertura", "edital_por_escopo", "condicoes_gerais", "condicoes_especificas", "anexo",
    "resolucao_normativa", "programa_da_area", "barema_por_unidade", "formulario_titulos",
    "pagina_de_arquivos", "documento_externo", "versao_outra_lingua",
    "retificacao", "edital_consolidado", "impugnacao_edital_resultado", "retificacao_cronograma", "cancelamento",
    "suspensao", "retomada", "prorrogacao", "reabertura_inscricoes",
    "isencao_resultado", "atendimento_especial_resultado", "homologados_preliminar", "homologados_final",
    "sorteio_reserva_resultado", "portaria_banca", "retificacao_portaria_banca", "impugnacao_banca_resultado",
    "cronograma", "convocacao", "edital_convocacao_etapa", "sorteio", "nota_informativa",
    "resultado_etapa", "resultado_recursos", "resultado_final", "homologacao_resultado", "gabarito", "outro",
}
LEITURA_POR_TIPO = {
    "versao_outra_lingua": "nao_le", "gabarito": "nao_le", "outro": "nao_le",
    "edital_consolidado": "so_conferencia", "pagina_de_arquivos": "so_conferencia",
    "isencao_resultado": "so_datas", "atendimento_especial_resultado": "so_datas",
    "resultado_etapa": "so_datas", "resultado_recursos": "so_datas",
}
LEITURAS = {"le", "so_conferencia", "so_datas", "nao_le"}
MOTIVOS_VERIFICAR = {"celula_mesclada", "formula_nao_decodificada", "ocr", "texto_corrompido",
                     "trecho_de_outro_edital", "sem_data_no_texto"}
MOTIVOS_NAO_PERTENCE = {"pagina_institucional", "outro_concurso", "outro_edital_mesma_instituicao", "sem_texto",
                        "substituto_fora_do_escopo"}  # sessão 15

# Campos essenciais: (caminho relativo ao padrão do módulo, ou absoluto no núcleo)
ESSENCIAIS_NUCLEO = ["instituicao", "sigla", "numero_edital", "carreira", "data_publicacao",
                     "inscricao.padrao.inscricao_inicio", "inscricao.padrao.inscricao_fim"]
ESSENCIAIS_MODULO = {
    "didatica": ["recursos.proprios_permitidos", "plano_de_aula.exigido", "plano_de_aula.modelo_obrigatorio",
                 "plano_de_aula.exige_minutagem_na_metodologia"],
    "escrita": ["formato", "conteudo.origem", "tempo.duracao_total_min", "consulta.situacao"],
    "objetiva": ["formato_item", "total_questoes"],
    "memorial": ["configuracao"],
    "projeto": [], "titulos": ["pontuacao_maxima"], "pratica": [],
}


# ----------------------------------------------------------------------------- relatório

class Relatorio:
    def __init__(self, conflitos, aceitar):
        self.erros, self.avisos, self.avisos_edital = [], [], []
        self.conflitos = conflitos
        self.aceitar = aceitar

    def erro(self, caminho, msg):
        if self.aceitar and self._tem_conflito(caminho):
            self.avisos.append(f"{caminho}: {msg} (aceito: conflito_interno registrado)")
        else:
            self.erros.append(f"{caminho}: {msg}")

    def aviso(self, caminho, msg):
        self.avisos.append(f"{caminho}: {msg}")

    def aviso_edital(self, caminho, msg):
        """Conta do edital que não fecha (soma, total, teto, contagem, tempo).
        Não bloqueia: a extração copia o edital como está, e a informação oficial
        é sempre a do edital. Vira aviso para conferir no edital; a plataforma
        mostra ao candidato como possível erro no edital."""
        self.avisos_edital.append(f"{caminho}: {msg}")

    def _tem_conflito(self, caminho):
        base = re.sub(r"\[\d+\]", "", caminho)
        for c in self.conflitos:
            cc = re.sub(r"\[\d+\]", "", str(c.get("campo") or ""))
            if cc and (base == cc or base.startswith(cc + ".") or cc.startswith(base + ".")):
                return True
        return False

    def imprimir(self):
        for m in self.erros:
            print(f"ERRO   {m}")
        for m in self.avisos:
            print(f"AVISO  {m}")
        for m in self.avisos_edital:
            print(f"EDITAL {m} · possível erro no edital; confira no edital, que é a fonte oficial")
        print()
        print(f"{'FALHA' if self.erros else 'OK'}: {len(self.erros)} erro(s), {len(self.avisos)} aviso(s), "
              f"{len(self.avisos_edital)} possível(is) erro(s) no edital")
        return 1 if self.erros else 0


# ----------------------------------------------------------------------------- utilidades


MESES = {"janeiro": 1, "fevereiro": 2, "março": 3, "marco": 3, "abril": 4, "maio": 5, "junho": 6, "julho": 7,
         "agosto": 8, "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12}
LINK_EXTENSO = re.compile(r"(?:(?:segunda|ter[çc]a|quarta|quinta|sexta)-feira|s[áa]bado|domingo),\s*(\d{1,2})\s+de\s+([a-zç]+)\s+de\s+(\d{4})\s*$", re.I)  # link do IFMT (sessão 14)


def data_do_texto_do_link(trecho):
    """Data ISO do texto do link nas formas aceitas, ou None (mesma regra do extracoes/pendencias.py)."""
    m = re.match(r"\s*(\d{2})/(\d{2})/(\d{4})\b", trecho) or re.search(
        r"\(\s*(\d{2})[-/](\d{2})[-/](\d{4})\s*\)\s*\.?\s*$", trecho) or re.search(
        r"\s-\s(\d{2})/(\d{2})/(\d{4})\s*\|\s*\d{2}:\d{2}\s*$", trecho)  # SIGRH
    if m:
        return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
    e = LINK_EXTENSO.search(trecho)
    if e and MESES.get(e.group(2).lower()):
        return f"{e.group(3)}-{MESES[e.group(2).lower()]:02d}-{int(e.group(1)):02d}"
    return None

def normaliza(nome):
    s = unicodedata.normalize("NFKD", nome or "").encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-zA-Z ]+", " ", s).lower()
    return re.sub(r"\s+", " ", s).strip()


def e_vf(x):
    """Valor com fonte: objeto só com valor, fonte e, opcionalmente, verificar_no_pdf.
    Um registro que por acaso tenha um campo chamado 'valor' (item de títulos, linha de remuneração)
    tem outras chaves e por isso não é VF."""
    return isinstance(x, dict) and "valor" in x and "fonte" in x and set(x) <= {"valor", "fonte", "verificar_no_pdf"}


def val(x):
    """Valor cru de um VF, ou o próprio x quando é cru."""
    return x["valor"] if e_vf(x) else x


def resolve(obj, caminho):
    """Resolve um caminho com pontos e índices. Devolve (achou, valor)."""
    cur = obj
    for parte in re.findall(r"[^.\[\]]+|\[\d+\]", caminho):
        if parte.startswith("["):
            i = int(parte[1:-1])
            if not isinstance(cur, list) or i >= len(cur):
                return False, None
            cur = cur[i]
        else:
            if not isinstance(cur, dict) or parte not in cur:
                return False, None
            cur = cur[parte]
    return True, cur


def percorre(obj, caminho=""):
    """Gera (caminho, objeto) para todo dict e list."""
    if isinstance(obj, dict):
        yield caminho, obj
        for k, v in obj.items():
            yield from percorre(v, f"{caminho}.{k}" if caminho else k)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from percorre(v, f"{caminho}[{i}]")


def data_de(forma):
    """Primeira data ISO de uma forma de data, ou None."""
    if not isinstance(forma, dict):
        return None
    if forma.get("forma") == "fixa":
        return forma.get("data")
    if forma.get("forma") == "janela":
        return (forma.get("inicio") or {}).get("data")
    return None


# ----------------------------------------------------------------------------- forma

def checa_fonte(r, caminho, fonte, triagem_caminhos, exige=True):
    if fonte is None:
        if exige:
            r.erro(caminho, "fonte ausente")
        return
    if not isinstance(fonte, dict):
        r.erro(caminho, "fonte não é objeto")
        return
    extras = set(fonte) - {"item", "pagina", "trecho", "documento"}
    if extras:
        r.erro(caminho, f"fonte com chaves desconhecidas: {sorted(extras)}")
    if not fonte.get("item"):
        r.erro(caminho, "fonte.item vazio")
    if fonte.get("pagina") is not None and not isinstance(fonte.get("pagina"), int):
        r.erro(caminho, "fonte.pagina não é inteiro nem null")
    trecho = fonte.get("trecho")
    if not trecho:
        r.erro(caminho, "fonte.trecho vazio")
    elif len(trecho.split()) > 60:
        r.aviso(caminho, f"fonte.trecho longo ({len(trecho.split())} palavras; o limite é 40)")
    if "..." in (trecho or "") or "…" in (trecho or ""):
        r.aviso(caminho, "fonte.trecho com reticências")
    doc = fonte.get("documento")
    if doc is None and PACOTE["ativo"]:
        r.erro(caminho, "num edital de pacote, toda fonte diz o documento (sessão 14)")
    if doc is not None and triagem_caminhos is not None and doc not in triagem_caminhos:
        r.erro(caminho, f"fonte.documento sem ficha de triagem{' deste edital' if PACOTE['ativo'] else ''}: {doc}")


def checa_verificar(r, caminho, marca):
    if not isinstance(marca, dict):
        r.erro(caminho, "verificar_no_pdf não é objeto")
        return
    if marca.get("motivo") not in MOTIVOS_VERIFICAR:
        r.erro(caminho, f"verificar_no_pdf.motivo fora da lista: {marca.get('motivo')}")
    if marca.get("pagina") is not None and not isinstance(marca.get("pagina"), int):
        r.erro(caminho, "verificar_no_pdf.pagina não é inteiro")


def checa_vf(r, caminho, x, triagem_caminhos, tipo=None, enum=None):
    """x é null ou valor com fonte."""
    if x is None:
        return
    if not e_vf(x):
        r.erro(caminho, "deveria ser null ou {valor, fonte}")
        return
    extras = set(x) - {"valor", "fonte", "verificar_no_pdf"}
    if extras:
        r.erro(caminho, f"chaves desconhecidas no valor com fonte: {sorted(extras)}")
    tem_marca = "verificar_no_pdf" in x
    if tem_marca:
        checa_verificar(r, caminho, x["verificar_no_pdf"])
    checa_fonte(r, caminho, x["fonte"], triagem_caminhos, exige=not tem_marca)
    v = x["valor"]
    if v is None and not tem_marca:
        r.erro(caminho, "valor null dentro de {valor, fonte}; use null cru")
    if v is not None and tipo is not None and not isinstance(v, tipo):
        r.erro(caminho, f"valor de tipo errado (esperado {getattr(tipo, '__name__', tipo)})")
    if v is not None and enum is not None and v not in enum:
        r.erro(caminho, f"valor fora da lista {sorted(enum)}: {v!r}")


def checa_data_iso(r, caminho, v):
    if v is not None and not (isinstance(v, str) and ISO_DATA.match(v)):
        r.erro(caminho, f"data fora do formato AAAA-MM-DD: {v!r}")


def checa_forma_data(r, caminho, d):
    if d is None:
        return
    if not isinstance(d, dict) or "forma" not in d:
        r.erro(caminho, "forma de data deve ser objeto com 'forma'")
        return
    f = d["forma"]
    if f == "fixa":
        checa_data_iso(r, caminho + ".data", d.get("data"))
        if d.get("hora") is not None and not ISO_HORA.match(str(d.get("hora"))):
            r.erro(caminho, "hora fora do formato HH:MM")
    elif f == "janela":
        for k in ("inicio", "fim"):
            p = d.get(k)
            if not isinstance(p, dict):
                r.erro(caminho, f"janela sem {k}")
            else:
                checa_data_iso(r, f"{caminho}.{k}.data", p.get("data"))
        di, df = (d.get("inicio") or {}).get("data"), (d.get("fim") or {}).get("data")
        if di and df and di > df:
            r.erro(caminho, "janela com início depois do fim")
    elif f == "relativa":
        if not isinstance(d.get("quantidade"), (int, float)):
            r.erro(caminho, "relativa sem quantidade numérica")
        if d.get("unidade") not in {"dias_uteis", "dias_corridos", "horas", "nao_informada"}:
            r.erro(caminho, f"unidade fora da lista: {d.get('unidade')}")
        if not d.get("evento_ancora"):
            r.erro(caminho, "relativa sem evento_ancora")
        if d.get("sentido") not in {"apos", "antes"}:
            r.erro(caminho, f"sentido fora da lista: {d.get('sentido')}")
    elif f == "condicionada":
        if not d.get("condicao_literal"):
            r.erro(caminho, "condicionada sem condicao_literal")
    else:
        r.erro(caminho, f"forma de data desconhecida: {f}")


def checa_chaves(r, caminho, obj, esperadas, parcial=False):
    if not isinstance(obj, dict):
        r.erro(caminho, "deveria ser objeto")
        return False
    extras = set(obj) - set(esperadas)
    if extras:
        r.erro(caminho, f"chaves desconhecidas: {sorted(extras)}")
    if not parcial:
        faltam = set(esperadas) - set(obj)
        if faltam:
            r.erro(caminho, f"chaves ausentes: {sorted(faltam)}")
    return True


def checa_conteiner_contra_esqueleto(r, caminho, obj, esq, triagem_caminhos, parcial=False):
    """Confere recursivamente um contêiner contra o esqueleto: chaves, e VF nos campos folha."""
    if obj is None:
        return
    if not checa_chaves(r, caminho, obj, esq.keys(), parcial):
        return
    for k, modelo in esq.items():
        if k not in obj:
            continue
        v = obj[k]
        sub = f"{caminho}.{k}"
        if k == "barema":
            continue  # conferido por checa_barema
        if isinstance(modelo, dict) and modelo and "padrao" in modelo and "por_escopo" in modelo:
            checa_escopo(r, sub, v, modelo["padrao"], triagem_caminhos)
        elif isinstance(modelo, dict) and modelo:
            if v is None:
                continue  # bloco inteiro nulo (por exemplo, módulo ausente)
            if isinstance(v, dict) and "fonte" in v and not e_vf(v):
                # bloco com fonte única: campos crus
                checa_chaves(r, sub, v, list(modelo.keys()) + ["fonte", "verificar_no_pdf"], parcial=True)
                checa_fonte(r, sub, v["fonte"], triagem_caminhos)
            else:
                checa_conteiner_contra_esqueleto(r, sub, v, modelo, triagem_caminhos, parcial=parcial)
        elif isinstance(modelo, list):
            if not isinstance(v, list):
                r.erro(sub, "deveria ser lista")
            else:
                for i, item in enumerate(v):
                    if isinstance(item, dict) and "fonte" in item and not e_vf(item):
                        checa_fonte(r, f"{sub}[{i}]", item["fonte"], triagem_caminhos,
                                    exige="verificar_no_pdf" not in item)
                        if "verificar_no_pdf" in item:
                            checa_verificar(r, f"{sub}[{i}]", item["verificar_no_pdf"])
                    elif e_vf(item):
                        checa_vf(r, f"{sub}[{i}]", item, triagem_caminhos)
                    else:
                        r.erro(f"{sub}[{i}]", "item de lista deveria ser registro com fonte ou valor com fonte")
        else:
            # folha: null, VF, ou (dentro de bloco cru) escalar
            if v is None or e_vf(v):
                checa_vf(r, sub, v, triagem_caminhos)
            elif isinstance(v, dict) and "fonte" in v:
                checa_fonte(r, sub, v["fonte"], triagem_caminhos)
            else:
                r.erro(sub, "deveria ser null ou {valor, fonte}")


def checa_escopo(r, caminho, obj, esq_padrao, triagem_caminhos):
    if obj is None:
        return
    if not checa_chaves(r, caminho, obj, ["padrao", "por_escopo"]):
        return
    checa_conteiner_contra_esqueleto(r, caminho + ".padrao", obj.get("padrao"), esq_padrao, triagem_caminhos)
    pe = obj.get("por_escopo")
    if not isinstance(pe, list):
        r.erro(caminho + ".por_escopo", "deveria ser lista")
        return
    for i, reg in enumerate(pe):
        sub = f"{caminho}.por_escopo[{i}]"
        if not isinstance(reg, dict):
            r.erro(sub, "deveria ser objeto")
            continue
        if reg.get("eixo") not in {"lotacao", "area", "unidade", "carreira"}:
            r.erro(sub, f"eixo fora da lista: {reg.get('eixo')}")
        if not isinstance(reg.get("codigos"), list) or not reg.get("codigos"):
            r.erro(sub, "codigos deve ser lista não vazia")
        resto = {k: v for k, v in reg.items() if k not in ("eixo", "codigos")}
        checa_conteiner_contra_esqueleto(r, sub, resto, esq_padrao, triagem_caminhos, parcial=True)


# ----------------------------------------------------------------------------- regras do núcleo

def checa_controle(r, d):
    c = d.get("controle") or {}
    if c.get("versao_esquema") != "2.1":
        r.erro("controle.versao_esquema", f"esperado '2.1', veio {c.get('versao_esquema')!r}")
    checa_data_iso(r, "controle.extraido_em", c.get("extraido_em"))
    if c.get("estado_extracao") not in {"em_extracao", "conferida"}:
        r.erro("controle.estado_extracao", "fora da lista")
    if not isinstance(c.get("passadas"), list):
        r.erro("controle.passadas", "deveria ser lista")
    marcas = [p for p, o in percorre(d) if isinstance(o, dict) and "verificar_no_pdf" in o]
    if c.get("estado_extracao") == "conferida" and marcas:
        r.erro("controle.estado_extracao", f"conferida com {len(marcas)} verificar_no_pdf aberto(s)")
    if c.get("estado_extracao") == "conferida" and not c.get("conferida_em"):
        r.erro("controle.conferida_em", "conferida sem data")
    return marcas


def codigos_vagas(d):
    out = set()
    for v in d.get("vagas") or []:
        cod = v.get("codigo")
        if isinstance(cod, dict):
            out.add(str(cod.get("numero")))
        elif cod is not None:
            out.add(str(cod))
    return out


def checa_identificacao(r, d):
    car = d.get("carreira")
    if not (isinstance(car, dict) and "padrao" in car):
        # Decisão da sessão 14 (03/10/2026): carreira fora de EBTT e MS é "outra", com o literal ao lado.
        if isinstance(car, dict) and car.get("valor") == "outra":
            if not (isinstance(car.get("literal"), str) and car["literal"].strip()):
                r.erro("carreira.literal", "carreira 'outra' exige literal com a sigla ou o nome do edital")
            car = {k: v for k, v in car.items() if k != "literal"}
        elif isinstance(car, dict) and "literal" in car:
            r.erro("carreira.literal", "literal só cabe com valor 'outra'")
            car = {k: v for k, v in car.items() if k != "literal"}
        checa_vf(r, "carreira", car, None, enum={"EBTT", "MS", "outra"})
    for k in ("data_ato", "data_publicacao"):
        checa_data_iso(r, k, val(d.get(k)))
    da, dp = val(d.get("data_ato")), val(d.get("data_publicacao"))
    if da and dp and da > dp:
        r.erro("data_ato", "data_ato depois de data_publicacao")


def checa_vagas(r, d):
    vistos = {}
    for i, v in enumerate(d.get("vagas") or []):
        p = f"vagas[{i}]"
        cod = v.get("codigo")
        chave = str(cod.get("numero") if isinstance(cod, dict) else cod)
        if chave in vistos:
            r.erro(p + ".codigo", f"código repetido: {chave} (também em vagas[{vistos[chave]}])")
        vistos[chave] = i
        if v.get("vagas_imediatas") is not None and not isinstance(v.get("vagas_imediatas"), int):
            r.erro(p + ".vagas_imediatas", "deveria ser inteiro")
        sit = v.get("situacao")
        if sit is not None and not (isinstance(sit, dict) and sit.get("valor") == "cancelada" and sit.get("fonte")):
            r.erro(p + ".situacao", "deveria ser null ou {valor: 'cancelada', fonte} (sessão 15)")
        if v.get("titulacao_minima") not in {None, "graduacao", "especializacao", "mestrado", "doutorado"}:
            r.erro(p + ".titulacao_minima", "fora da lista")
        lm = v.get("limite_aprovados_por_modalidade")
        if lm is not None:
            if not isinstance(lm, list):
                r.erro(p + ".limite_aprovados_por_modalidade", "deveria ser lista ou null")
            else:
                for j, x in enumerate(lm):
                    q = f"{p}.limite_aprovados_por_modalidade[{j}]"
                    if x.get("modalidade") not in MODALIDADES_LIMITE:
                        r.erro(q + ".modalidade", f"fora da lista {sorted(MODALIDADES_LIMITE)}")
                    if not isinstance(x.get("limite"), int):
                        r.erro(q + ".limite", "deveria ser inteiro")
                    if not x.get("fonte"):
                        r.erro(q + ".fonte", "limite por modalidade exige fonte")


def checa_remuneracao(r, d):
    rem = d.get("remuneracao") or {}
    venc = {(x.get("regime")): x.get("valor") for x in rem.get("vencimento_basico") or []}
    retr = {(x.get("regime"), x.get("titulacao")): x.get("valor") for x in rem.get("retribuicao_por_titulacao") or []}
    for i, t in enumerate(rem.get("remuneracao_total") or []):
        k = (t.get("regime"), t.get("titulacao"))
        comp = t.get("componentes_literal")
        if comp is not None:
            if not (isinstance(comp, list) and comp and all(isinstance(c, str) and c.strip() for c in comp)):
                r.erro(f"remuneracao.remuneracao_total[{i}].componentes_literal", "deveria ser lista não vazia de textos ou null")
            continue  # total com outras parcelas: a soma vencimento + retribuição não se aplica (sessão 14)
        if k in retr and t.get("regime") in venc and None not in (venc[t["regime"]], retr[k], t.get("valor")):
            if abs(venc[t["regime"]] + retr[k] - t["valor"]) > 0.011:
                r.aviso_edital(f"remuneracao.remuneracao_total[{i}]",
                       f"vencimento + retribuição ≠ total ({venc[t['regime']]} + {retr[k]} ≠ {t['valor']})")


def checa_inscricao(r, d):
    ins = (d.get("inscricao") or {}).get("padrao") or {}
    ini, fim = val(ins.get("inscricao_inicio")), val(ins.get("inscricao_fim"))
    checa_data_iso(r, "inscricao.padrao.inscricao_inicio", ini)
    checa_data_iso(r, "inscricao.padrao.inscricao_fim", fim)
    if ini and fim and ini > fim:
        r.erro("inscricao.padrao", "inscrição com início depois do fim")
    ise = val(ins.get("isencao_periodo"))
    checa_forma_data(r, "inscricao.padrao.isencao_periodo", ise)
    if isinstance(ise, dict) and fim:
        fim_ise = (ise.get("fim") or {}).get("data") if ise.get("forma") == "janela" else ise.get("data")
        if fim_ise and fim_ise > fim:
            r.erro("inscricao.padrao.isencao_periodo", "isenção termina depois da inscrição")
    pag = val(ins.get("pagamento_limite"))
    checa_data_iso(r, "inscricao.padrao.pagamento_limite", pag)
    if pag and fim and pag < fim:
        r.erro("inscricao.padrao.pagamento_limite", "pagamento termina antes do fim da inscrição")


def checa_reserva(r, d):
    vagas = {}
    for v in d.get("vagas") or []:
        cod = v.get("codigo")
        chave = str(cod.get("numero") if isinstance(cod, dict) else cod)
        if isinstance(v.get("vagas_imediatas"), int):
            vagas[chave] = v["vagas_imediatas"]
    soma = {}
    for i, x in enumerate((d.get("reserva") or {}).get("distribuicao") or []):
        lot = str(x.get("lotacao"))
        if isinstance(x.get("vagas"), int):
            soma[lot] = soma.get(lot, 0) + x["vagas"]
    for lot, s in soma.items():
        if lot in vagas and s > vagas[lot]:
            r.aviso_edital("reserva.distribuicao", f"lotação {lot}: reservadas {s} > vagas {vagas[lot]}")


def etapas_existentes(d):
    out = {}
    lista = ((d.get("etapas") or {}).get("padrao") or {}).get("lista") or []
    for e in lista:
        out[e.get("tipo")] = e.get("existe")
    return out


def checa_etapas(r, d):
    lista = ((d.get("etapas") or {}).get("padrao") or {}).get("lista") or []
    vistos = set()
    for i, e in enumerate(lista):
        p = f"etapas.padrao.lista[{i}]"
        if e.get("tipo") not in TIPOS_ETAPA:
            r.erro(p + ".tipo", f"fora da lista: {e.get('tipo')}")
        if e.get("tipo") in vistos and e.get("tipo") != "outra":
            r.erro(p + ".tipo", "etapa repetida no padrão")
        vistos.add(e.get("tipo"))
        if e.get("existe") not in {True, False, None}:
            r.erro(p + ".existe", "deveria ser true, false ou null")
        if e.get("existe") is False and not (e.get("fonte") or {}).get("trecho"):
            r.erro(p + ".existe", "false exige trecho literal na fonte")
        for k in ("data_primeira", "data_ultima"):
            checa_forma_data(r, f"{p}.{k}", e.get(k))
        if e.get("lingua") is not None:
            checa_vf(r, p + ".lingua", e.get("lingua"), None, tipo=str)
    for tipo in MODULOS_NOMES:
        if tipo not in vistos:
            r.aviso("etapas.padrao.lista", f"etapa '{tipo}' não registrada (nem como ausente)")
    pont = d.get("estrutura_de_pontuacao") or {}
    regs = [("estrutura_de_pontuacao.padrao", pont.get("padrao") or {})] + [
        (f"estrutura_de_pontuacao.por_escopo[{i}]", x) for i, x in enumerate(pont.get("por_escopo") or [])]
    ex = etapas_existentes(d)
    for base, reg in regs:
        for i, f in enumerate(reg.get("fases") or []):
            p = f"{base}.fases[{i}]"
            if f.get("etapa_ref") not in ex:
                r.erro(p + ".etapa_ref", f"etapa não registrada: {f.get('etapa_ref')}")
            if f.get("carater") not in {None, "eliminatorio", "classificatorio", "ambos"}:
                r.erro(p + ".carater", "fora da lista")
            if f.get("escala") == 10 and isinstance(f.get("peso"), (int, float)) and isinstance(f.get("maximo"), (int, float)):
                if abs(f["peso"] * 10 - f["maximo"]) > 0.001:
                    r.aviso_edital(p + ".maximo", f"máximo {f['maximo']} ≠ peso × 10 = {f['peso'] * 10}")


def checa_eventos(r, d):
    ex = etapas_existentes(d)
    cods = codigos_vagas(d)
    ids = {}
    for i, e in enumerate(d.get("eventos") or []):
        eid = e.get("id")
        if not (isinstance(eid, str) and ID_EVENTO.match(eid)):
            r.erro(f"eventos[{i}].id", "id obrigatório no formato ev-0000 (sessão 14)")
        elif eid in ids:
            r.erro(f"eventos[{i}].id", f"id repetido: {eid} (também em eventos[{ids[eid]}])")
        else:
            ids[eid] = i
    for i, e in enumerate(d.get("eventos") or []):
        p = f"eventos[{i}]"
        t = e.get("tipo_evento")
        if t not in TIPOS_EVENTO:
            r.erro(p + ".tipo_evento", f"fora da lista: {t}")
            continue
        usa_etapa, usa_fase = TIPOS_EVENTO[t]
        if usa_etapa is True and not e.get("etapa_ref"):
            r.erro(p + ".etapa_ref", f"obrigatório em {t}")
        if usa_etapa is False and e.get("etapa_ref"):
            r.erro(p + ".etapa_ref", f"não se usa em {t}")
        if e.get("etapa_ref") and e["etapa_ref"] not in ex:
            r.erro(p + ".etapa_ref", f"etapa não registrada: {e['etapa_ref']}")
        if not usa_fase and e.get("fase"):
            r.erro(p + ".fase", f"não se usa em {t}")
        if t == "procedimento_cotas":
            if e.get("fase") not in {"convocacao", "resultado", "resultado_final"}:
                r.erro(p + ".fase", "procedimento_cotas exige fase convocacao, resultado ou resultado_final")
            if e.get("modalidade") not in {"negros", "indigenas", "quilombolas", "pcd", "todas"}:
                r.erro(p + ".modalidade", "procedimento_cotas exige modalidade negros, indigenas, quilombolas, pcd ou todas")
        else:
            if e.get("fase") not in {None, "preliminar", "final"}:
                r.erro(p + ".fase", "fora da lista")
            if "modalidade" in e:
                r.erro(p + ".modalidade", "só existe em procedimento_cotas")
        if t == "outro" and not e.get("descricao_literal"):
            r.erro(p + ".descricao_literal", "obrigatório em 'outro'")
        if e.get("estado") not in {"vigente", "substituido", "cancelado"}:  # cancelado: sessão 15
            r.erro(p + ".estado", "fora da lista")
        checa_forma_data(r, p + ".data", e.get("data"))
        esc = e.get("escopo")
        if isinstance(esc, list):
            for c in esc:
                if cods and str(c) not in cods:
                    r.erro(p + ".escopo", f"lotação desconhecida: {c}")
        elif esc not in (None, "geral"):
            r.erro(p + ".escopo", "deveria ser 'geral', lista de códigos ou null")
    for i, lot in enumerate(d.get("lotacoes") or []):
        if cods and str(lot.get("lotacao")) not in cods:
            r.erro(f"lotacoes[{i}].lotacao", f"lotação desconhecida: {lot.get('lotacao')}")
        for j, t in enumerate(lot.get("turmas") or []):
            for k in ("sorteio_tema", "confinamento", "apresentacao"):
                checa_forma_data(r, f"lotacoes[{i}].turmas[{j}].{k}", t.get(k))


def checa_alteracoes(r, d):
    alts = d.get("alteracoes") or []
    ids_eventos = {e.get("id") for e in d.get("eventos") or []}
    for i, a in enumerate(alts):
        p = f"alteracoes[{i}]"
        doc = a.get("documento") or {}
        if doc.get("tipo") not in TIPOS_DOCUMENTO:
            r.erro(p + ".documento.tipo", f"fora da lista: {doc.get('tipo')}")
        checa_data_iso(r, p + ".data_publicacao", a.get("data_publicacao"))
        if not a.get("evento_afetado") and not a.get("campo_afetado"):
            r.erro(p, "alteração sem evento_afetado nem campo_afetado")
        ea = a.get("evento_afetado")
        if isinstance(ea, dict) and ea.get("evento_id") is not None and ea["evento_id"] not in ids_eventos:
            r.erro(p + ".evento_afetado.evento_id", f"evento inexistente: {ea['evento_id']}")
    # cadeia: mesmo alvo, em ordem de data; onde_se_le[N] == leia_se[N-1]
    por_alvo = {}
    for i, a in enumerate(alts):
        alvo = a.get("campo_afetado") or json.dumps(a.get("evento_afetado"), sort_keys=True, ensure_ascii=False)
        por_alvo.setdefault(alvo, []).append((a.get("data_publicacao") or "", i, a))
    for alvo, seq in por_alvo.items():
        seq.sort(key=lambda x: (x[0], x[1]))
        for (_, i0, a0), (_, i1, a1) in zip(seq, seq[1:]):
            if a0.get("leia_se") and a1.get("onde_se_le") and a0["leia_se"].strip() != a1["onde_se_le"].strip():
                r.erro(f"alteracoes[{i1}].onde_se_le",
                       f"não bate com o leia_se de alteracoes[{i0}] sobre o mesmo alvo")
        ultimo = seq[-1][2]
        if ultimo.get("campo_afetado") and ultimo.get("valor_novo") is not None:
            achou, atual = resolve(d, ultimo["campo_afetado"])
            if achou and val(atual) != ultimo["valor_novo"] and atual != ultimo["valor_novo"]:
                r.aviso(f"alteracoes[{seq[-1][1]}].valor_novo",
                        "difere do valor atual do campo (confira se a alteração foi aplicada)")


def checa_pendencias(r, d):
    for i, pnd in enumerate(d.get("pendencias") or []):
        p = f"pendencias[{i}]"
        campo = pnd.get("campo") or ""
        achou, _ = resolve(d, campo)
        if not achou:
            r.erro(p + ".campo", f"caminho não existe no JSON: {campo}")
        t = pnd.get("tipo")
        if t not in {"omissao", "diferida"}:
            r.erro(p + ".tipo", "fora da lista")
        if t == "diferida" and not pnd.get("promessa_literal"):
            r.erro(p + ".promessa_literal", "obrigatório em diferida")
        if t == "omissao" and pnd.get("promessa_literal"):
            r.erro(p + ".promessa_literal", "deve ser null em omissão")
        if t == "diferida":
            dp = pnd.get("documento_prometido") or {}
            if dp.get("tipo") not in TIPOS_DOCUMENTO:
                r.erro(p + ".documento_prometido.tipo", f"fora da lista: {dp.get('tipo')}")
            if pnd.get("resolvida_por") not in TIPOS_DOCUMENTO:
                r.erro(p + ".resolvida_por", f"fora da lista: {pnd.get('resolvida_por')}")
        if pnd.get("estado") not in {"aberta", "resolvida"}:
            r.erro(p + ".estado", "fora da lista")
        if pnd.get("estado") == "resolvida" and not pnd.get("resolvida_em"):
            r.erro(p + ".resolvida_em", "resolvida sem documento e data")
        checa_forma_data(r, p + ".prazo_prometido", pnd.get("prazo_prometido"))
    for i, c in enumerate(d.get("conflitos_internos") or []):
        p = f"conflitos_internos[{i}]"
        if not c.get("campo") or not c.get("descricao"):
            r.erro(p, "conflito sem campo ou sem descrição")
        if len(c.get("fontes") or []) < 2:
            r.erro(p + ".fontes", "conflito exige pelo menos duas fontes")


def pendencias_por_campo(d):
    out = {}
    for pnd in d.get("pendencias") or []:
        out.setdefault(re.sub(r"\[\d+\]", "", pnd.get("campo") or ""), []).append(pnd)
    return out


def checa_essenciais(r, d):
    pend = pendencias_por_campo(d)

    def exige(caminho):
        achou, v = resolve(d, caminho)
        if achou and v is None and caminho not in pend:
            r.erro(caminho, "campo essencial null sem pendência")

    for c in ESSENCIAIS_NUCLEO:
        exige(c)
    lista = ((d.get("etapas") or {}).get("padrao") or {}).get("lista") or []
    for i, e in enumerate(lista):
        if e.get("existe") is None and f"etapas.padrao.lista.existe" not in pend:
            r.aviso(f"etapas.padrao.lista[{i}].existe", "null: o edital não permite dizer se a etapa existe")
    for m in MODULOS_NOMES:
        mod = d.get(m)
        if not isinstance(mod, dict):
            continue
        pad = mod.get("padrao") or {}
        if pad.get("existe") is None:
            exige(f"{m}.padrao.existe")
            continue
        if val(pad.get("existe")) is not True:
            continue
        for c in ESSENCIAIS_MODULO.get(m, []):
            exige(f"{m}.padrao.{c}")
        if m == "didatica":
            t = ((pad.get("pdd") or {}).get("tempo") or {})
            if t.get("nominal_min") is None and t.get("teto_min") is None and "didatica.padrao.pdd.tempo" not in pend \
                    and "didatica.padrao.pdd.tempo.nominal_min" not in pend and "didatica.padrao.pdd.tempo.teto_min" not in pend:
                r.erro("didatica.padrao.pdd.tempo", "sem nominal nem teto, e sem pendência")
        if m == "memorial":
            conf = val(pad.get("configuracao"))
            if isinstance(conf, dict) and conf.get("tipo") != "so_oral":
                exige("memorial.padrao.documento.entrega.prazo")


def checa_recursos_apuracao(r, d):
    ex = etapas_existentes(d)
    for i, x in enumerate(d.get("recursos_administrativos") or []):
        p = f"recursos_administrativos[{i}]"
        if x.get("etapa_ref") not in ex and x.get("etapa_ref") not in ETAPA_REF_FORA_DE_ETAPA:
            r.erro(p + ".etapa_ref", f"etapa não registrada: {x.get('etapa_ref')}")
        if x.get("efeito") not in {None, "suspensivo", "nao_suspensivo"}:
            r.erro(p + ".efeito", "fora da lista")
        checa_forma_data(r, p + ".prazo", x.get("prazo"))
        checa_forma_data(r, p + ".prazo_resposta", x.get("prazo_resposta"))
    for i, x in enumerate(d.get("acesso_a_documentos") or []):
        p = f"acesso_a_documentos[{i}]"
        if x.get("etapa_ref") not in ex and x.get("etapa_ref") != "todas":
            r.erro(p + ".etapa_ref", f"etapa não registrada: {x.get('etapa_ref')}")
        for k in ("espelho", "copia", "gravacao"):
            s = (x.get(k) or {}).get("situacao") if isinstance(x.get(k), dict) else None
            if s not in {None, "permitido", "negado"}:
                r.erro(f"{p}.{k}.situacao", "fora da lista")
    for i, x in enumerate((d.get("apuracao_da_nota") or {}).get("por_etapa") or []):
        p = f"apuracao_da_nota.por_etapa[{i}]"
        if x.get("etapa_ref") not in ex and x.get("etapa_ref") != "todas":
            r.erro(p + ".etapa_ref", f"etapa não registrada: {x.get('etapa_ref')}")
        if x.get("metodo") not in {None, "media", "soma", "nota_individual", "outra"}:
            r.erro(p + ".metodo", "fora da lista")


def checa_bancas(r, d):
    cods = codigos_vagas(d)
    por_lot_vig = {}
    nomes_por_lot = {}
    for i, b in enumerate(d.get("bancas") or []):
        p = f"bancas[{i}]"
        lot = str(b.get("lotacao"))
        if cods and lot not in cods:
            r.erro(p + ".lotacao", f"lotação desconhecida: {lot}")
        if b.get("vigente") not in {True, False}:
            r.erro(p + ".vigente", "deveria ser true ou false")
        ident = b.get("identificacao")  # sessão 15: mais de uma banca por lotação
        if ident is not None and not (isinstance(ident, str) and ident.strip()):
            r.erro(p + ".identificacao", "deveria ser null ou texto")
        if b.get("vigente"):
            chave_b = lot if ident is None else f"{lot} ({ident})"
            por_lot_vig[chave_b] = por_lot_vig.get(chave_b, 0) + 1
        pres = 0
        for j, m in enumerate(b.get("membros") or []):
            q = f"{p}.membros[{j}]"
            if m.get("funcao") not in {"titular", "suplente", "secretario"}:
                r.erro(q + ".funcao", f"fora da lista: {m.get('funcao')}")
            if m.get("presidente") is True:
                pres += 1
            esperado = normaliza(m.get("nome_literal"))
            if m.get("chave_normalizada") != esperado:
                r.erro(q + ".chave_normalizada", f"esperado {esperado!r}")
            if b.get("vigente") and m.get("funcao") != "secretario":
                nomes_por_lot.setdefault(esperado, set()).add(lot)
        if pres > 1:
            r.erro(p + ".membros", f"{pres} presidentes; esperado no máximo 1")
    for lot, n in por_lot_vig.items():
        if n > 1:
            r.erro("bancas", f"lotação {lot} com {n} versões vigentes")
    for nome, lots in nomes_por_lot.items():
        if len(lots) > 1:
            r.aviso("bancas", f"'{nome}' em bancas vigentes de mais de uma lotação: {sorted(lots)}")


def checa_homologados(r, d):
    cods = codigos_vagas(d)
    contagem = {}
    for i, h in enumerate(d.get("homologados") or []):
        p = f"homologados[{i}]"
        lot = str(h.get("lotacao"))
        if cods and lot not in cods:
            r.erro(p + ".lotacao", f"lotação desconhecida: {lot}")
        if h.get("lista_publicada") is False and not h.get("motivo"):
            r.erro(p + ".motivo", "lista não publicada exige motivo")
        chaves = set()
        for j, c in enumerate(h.get("candidatos") or []):
            esperado = normaliza(c.get("nome_literal"))
            if c.get("chave_normalizada") != esperado:
                r.erro(f"{p}.candidatos[{j}].chave_normalizada", f"esperado {esperado!r}")
            if esperado in chaves:
                r.erro(f"{p}.candidatos[{j}]", "candidato repetido na lotação; una as modalidades num registro")
            chaves.add(esperado)
        contagem[lot] = len(chaves)
    for i, x in enumerate(d.get("inscritos_homologados") or []):
        lot = str(x.get("lotacao"))
        if x.get("modalidade") in (None, "total", "todas") and lot in contagem and isinstance(x.get("quantidade"), int):
            if x["quantidade"] != contagem[lot]:
                r.erro(f"inscritos_homologados[{i}].quantidade",
                       f"{x['quantidade']} ≠ {contagem[lot]} candidatos únicos em homologados[]")
    for i, x in enumerate(d.get("impugnacoes") or []):
        if x.get("lotacao") is None and "impugnacoes.lotacao" not in pendencias_por_campo(d):
            r.aviso(f"impugnacoes[{i}].lotacao", "null sem pendência de omissão")


# ----------------------------------------------------------------------------- módulos

def registros_modulo(d, m):
    mod = d.get(m)
    if not isinstance(mod, dict):
        return []
    out = [(f"{m}.padrao", mod.get("padrao") or {})]
    for i, x in enumerate(mod.get("por_escopo") or []):
        out.append((f"{m}.por_escopo[{i}]", x))
    return out


def checa_barema(r, caminho, b):
    if b is None:
        return
    if e_vf(b):
        r.erro(caminho, "barema não é valor com fonte; é contêiner com localizacao, texto_integral e fichas")
        return
    if not checa_chaves(r, caminho, b, ["localizacao", "texto_integral", "fichas"]):
        return
    checa_vf(r, caminho + ".localizacao", b.get("localizacao"), None,
             enum={"edital", "anexo", "resolucao", "programa_da_area", "documento_da_banca", "delegado"})
    checa_vf(r, caminho + ".texto_integral", b.get("texto_integral"), None, tipo=str)
    if b.get("texto_integral") is None and b.get("fichas"):
        r.erro(caminho + ".texto_integral", "fichas sem texto_integral")
    for i, f in enumerate(b.get("fichas") or []):
        p = f"{caminho}.fichas[{i}]"
        if not isinstance(f, dict) or "fonte" not in f:
            r.erro(p, "ficha deve ser registro com fonte")
            continue
        checa_chaves(r, p, f, ["identificacao", "avaliador", "peso", "soma_declarada", "itens", "fonte", "verificar_no_pdf"], parcial=True)
        itens = f.get("itens") or []
        pontos = [it.get("pontos") for it in itens]
        for j, it in enumerate(itens):
            if not it.get("texto"):
                r.erro(f"{p}.itens[{j}].texto", "vazio")
            if it.get("pontos") is not None and not isinstance(it.get("pontos"), (int, float)):
                r.erro(f"{p}.itens[{j}].pontos", "deveria ser número ou null")
        if itens and all(isinstance(x, (int, float)) for x in pontos) and isinstance(f.get("soma_declarada"), (int, float)):
            s = sum(pontos)
            if abs(s - f["soma_declarada"]) > 0.011:
                r.aviso_edital(p, f"soma dos itens {s} ≠ soma_declarada {f['soma_declarada']}")


def checa_tempo(r, caminho, t):
    if not isinstance(t, dict):
        return
    g = lambda k: val(t.get(k))  # noqa: E731
    piso, nom, teto = g("piso_eliminatorio_min"), g("nominal_min"), g("teto_min")
    pen = g("piso_penalidade_min")
    sem = g("piso_sem_consequencia_min")  # sessão 15
    if isinstance(sem, (int, float)) and (isinstance(piso, (int, float)) or isinstance(pen, (int, float))):
        r.erro(caminho, "piso sem consequência exclui piso eliminatório e piso de penalidade")
    for a, b, na, nb in ((sem, nom, "piso sem consequência", "nominal"), (sem, teto, "piso sem consequência", "teto"),(piso, nom, "piso", "nominal"), (nom, teto, "nominal", "teto"), (piso, teto, "piso", "teto"),
                         (piso, pen, "piso eliminatório", "piso de penalidade"), (pen, nom, "piso de penalidade", "nominal"),
                         (pen, teto, "piso de penalidade", "teto")):
        if isinstance(a, (int, float)) and isinstance(b, (int, float)) and a > b:
            r.aviso_edital(caminho, f"{na} {a} > {nb} {b}")


def checa_secoes(r, caminho, s):
    if not isinstance(s, dict):
        return
    for i, it in enumerate(s.get("itens") or []):
        if it.get("origem") not in {"texto_do_edital", "descritor_do_barema", "modelo_obrigatorio"}:
            r.erro(f"{caminho}.itens[{i}].origem", f"fora da lista: {it.get('origem')}")


def dep_nulo(r, caminho, v, condicao_falsa, pend):
    """Campo dependente: quando a condição é falsa, tem de ser null e não ter pendência."""
    base = re.sub(r"\[\d+\]", "", caminho)
    if condicao_falsa:
        if v is not None:
            r.erro(caminho, "campo dependente preenchido com a condição falsa")
        if base in pend:
            r.erro(caminho, "campo dependente com pendência, mas a condição é falsa")


def checa_modulos(r, d):
    pend = pendencias_por_campo(d)
    ex = etapas_existentes(d)
    for m in MODULOS_NOMES:
        if d.get(m) is None:
            if ex.get(m) is True:
                r.aviso(m, "etapa existe e o módulo ainda não foi extraído")
            continue
        for base, reg in registros_modulo(d, m):
            existe = val(reg.get("existe")) if "existe" in reg else None
            padrao = base.endswith(".padrao")
            if padrao and existe is False:
                for k, v in reg.items():
                    if k not in ("existe", "nome_literal") and v not in (None, [], {}) and not (
                            isinstance(v, dict) and all(x in (None, [], {}) or isinstance(x, dict) for x in v.values())):
                        r.erro(f"{base}.{k}", "módulo com existe false deveria ter o restante vazio")
            if "existe" in reg:
                checa_vf(r, base + ".existe", reg.get("existe"), None, tipo=bool)
            if m == "didatica":
                pdd = reg.get("pdd") or {}
                checa_tempo(r, base + ".pdd.tempo", pdd.get("tempo"))
                pa = reg.get("plano_de_aula") or {}
                checa_secoes(r, base + ".plano_de_aula.secoes_exigidas", pa.get("secoes_exigidas"))
                checa_barema(r, base + ".barema", reg.get("barema"))
                for k in ("fornecidos", "proibidos"):
                    if (reg.get("recursos") or {}).get(k) is None and "recursos" in reg:
                        r.erro(f"{base}.recursos.{k}", "lista, nunca null")
                for i, t in enumerate(reg.get("temas") or []):
                    if isinstance(t.get("lista"), list) and isinstance(t.get("quantidade"), int) and len(t["lista"]) != t["quantidade"]:
                        r.aviso_edital(f"{base}.temas[{i}].quantidade", f"{t['quantidade']} ≠ {len(t['lista'])} itens na lista")
            if m == "escrita":
                fmt = val(reg.get("formato")) or {}
                tipo = fmt.get("tipo") if isinstance(fmt, dict) else None
                if "formato" in reg and fmt and tipo not in {"dissertacao_sobre_tema", "questoes_discursivas", "mista", "outro"}:
                    r.erro(base + ".formato", f"tipo fora da lista: {tipo}")
                if "numero_questoes" in reg:
                    dep_nulo(r, base + ".numero_questoes", reg.get("numero_questoes"), tipo not in {"questoes_discursivas", "mista"} and "formato" in reg, pend)
                if "parte_objetiva_existe" in reg:
                    dep_nulo(r, base + ".parte_objetiva_existe", reg.get("parte_objetiva_existe"), tipo != "mista" and "formato" in reg, pend)
                cont = reg.get("conteudo") or {}
                if "conteudo" in reg:
                    checa_vf(r, base + ".conteudo.origem", cont.get("origem"), None,
                             enum={"lista_de_temas", "programa_por_vaga", "programa_geral", "outro"})
                    if val(cont.get("origem")) == "lista_de_temas" and not cont.get("temas") and padrao and not any(
                            x.get("conteudo", {}).get("temas") for x in (d[m].get("por_escopo") or [])):
                        r.erro(base + ".conteudo.temas", "origem lista_de_temas exige temas não vazios (no padrão ou por escopo)")
                    compart = val(cont.get("lista_compartilhada_com_didatica"))
                    if "regra_exclusao_didatica" in cont:
                        dep_nulo(r, base + ".conteudo.regra_exclusao_didatica", cont.get("regra_exclusao_didatica"), compart is not True and "lista_compartilhada_com_didatica" in cont, pend)
                    for i, t in enumerate(cont.get("temas") or []):
                        if isinstance(t.get("lista"), list) and isinstance(t.get("quantidade"), int) and len(t["lista"]) != t["quantidade"]:
                            r.aviso_edital(f"{base}.conteudo.temas[{i}].quantidade", f"{t['quantidade']} ≠ {len(t['lista'])} itens")
                sort = reg.get("sorteio")
                if isinstance(sort, dict) and "fonte" in sort:
                    q = sort.get("quantidade")
                    dep_nulo(r, base + ".sorteio.desenvolver_todos", sort.get("desenvolver_todos"), not (isinstance(q, int) and q > 1), pend)
                cons = reg.get("consulta") or {}
                if "consulta" in reg:
                    sit = val(cons.get("situacao"))
                    checa_vf(r, base + ".consulta.situacao", cons.get("situacao"), None,
                             enum={"permitida", "proibida", "a_criterio_da_banca"})
                    for k in ("duracao_min", "posicao", "material", "anotacoes_previas", "escrita_durante"):
                        if k in cons:
                            dep_nulo(r, f"{base}.consulta.{k}", cons.get(k), sit == "proibida", pend)
                    checa_vf(r, base + ".consulta.posicao", cons.get("posicao"), None, enum={"dentro", "somada"})
                    dur, tot = val(cons.get("duracao_min")), val((reg.get("tempo") or {}).get("duracao_total_min"))
                    if val(cons.get("posicao")) == "dentro" and isinstance(dur, (int, float)) and isinstance(tot, (int, float)) and dur > tot:
                        r.aviso_edital(base + ".consulta.duracao_min", f"consulta {dur} > duração total {tot}")
                checa_barema(r, base + ".avaliacao.barema", (reg.get("avaliacao") or {}).get("barema"))
            if m == "objetiva":
                tot = val(reg.get("total_questoes"))
                comps = reg.get("componentes") or []
                soma_q = sum(c.get("numero_questoes") or 0 for c in comps if isinstance(c.get("numero_questoes"), int))
                if comps and isinstance(tot, int) and soma_q != tot and all(isinstance(c.get("numero_questoes"), int) for c in comps):
                    r.aviso_edital(base + ".componentes", f"soma das questões {soma_q} ≠ total {tot}")
                for i, c in enumerate(comps):
                    q, v, mx = c.get("numero_questoes"), c.get("pontos_por_questao"), c.get("pontuacao_maxima")
                    if all(isinstance(x, (int, float)) for x in (q, v, mx)) and abs(q * v - mx) > 0.05:
                        r.aviso_edital(f"{base}.componentes[{i}]", f"questões × valor = {q * v} ≠ máximo {mx}")
                    dep_nulo(r, f"{base}.componentes[{i}].conteudo", c.get("conteudo"), c.get("comum_a_todas_areas") is not True, pend)
                    if c.get("numero_questoes_literal") and isinstance(q, int):
                        nums = re.findall(r"\d+", c["numero_questoes_literal"])
                        if nums and int(nums[0]) != q:
                            r.erro(f"{base}.componentes[{i}].numero_questoes", "difere do numeral em numero_questoes_literal")
                desc = val(reg.get("desconto_por_erro"))
                if "regra_pontuacao_literal" in reg and desc is True and reg.get("regra_pontuacao_literal") is None:
                    r.erro(base + ".regra_pontuacao_literal", "desconto_por_erro true exige a regra literal")
            if m in ("memorial", "projeto"):
                conf = val(reg.get("configuracao")) if m == "memorial" else None
                ctipo = conf.get("tipo") if isinstance(conf, dict) else None
                if m == "memorial" and conf and ctipo not in {"escrito_e_oral", "so_escrito", "so_oral"}:
                    r.erro(base + ".configuracao", f"tipo fora da lista: {ctipo}")
                if m == "memorial" and "documento" in reg:
                    dep_nulo(r, base + ".documento", reg.get("documento") if reg.get("documento") not in ({},) else None, ctipo == "so_oral", pend)
                if m == "projeto" and "documento" in reg:
                    mem = d.get("memorial") or {}
                    ju = ((mem.get("padrao") or {}).get("juncao_projeto") or {}) if isinstance(mem, dict) else {}
                    unico = ju.get("documento_unico") if isinstance(ju, dict) else None
                    dep_nulo(r, base + ".documento", reg.get("documento"), unico is True, pend)
                for i, av in enumerate(reg.get("avaliacoes") or []):
                    p = f"{base}.avaliacoes[{i}]"
                    if av.get("etapa_ref") not in ex:
                        r.erro(p + ".etapa_ref", f"etapa não registrada: {av.get('etapa_ref')}")
                    if av.get("objeto") not in {None, "documento", "defesa", "ambos"}:
                        r.erro(p + ".objeto", "fora da lista")
                    if m == "memorial":
                        dep_nulo(r, p + ".defesa", av.get("defesa"), ctipo == "so_escrito", pend)
                    df = av.get("defesa") or {}
                    checa_tempo(r, p + ".defesa.apresentacao.tempo", (df.get("apresentacao") or {}).get("tempo"))
                    apres = val(((df.get("apresentacao") or {}).get("tempo") or {}).get("nominal_min"))
                    tot = df.get("sessao_total_min")
                    if isinstance(apres, (int, float)) and isinstance(tot, (int, float)) and apres > tot:
                        r.aviso_edital(p + ".defesa", f"apresentação {apres} > sessão total {tot}")
                    checa_barema(r, p + ".barema", av.get("barema"))
                if m == "projeto":
                    if existe is True and padrao and not reg.get("pecas") and not any(
                            x.get("pecas") for x in (d[m].get("por_escopo") or [])):
                        r.erro(base + ".pecas", "projeto existe sem nenhuma peça")
                    for i, pc in enumerate(reg.get("pecas") or []):
                        checa_secoes(r, f"{base}.pecas[{i}].secoes_exigidas", pc.get("secoes_exigidas"))
                        vinc = pc.get("vinculo") or {}
                        if vinc and vinc.get("tipo") not in {"linha", "tema", "subarea", "departamento", "programa"}:
                            r.erro(f"{base}.pecas[{i}].vinculo.tipo", "fora da lista")
            if m == "titulos":
                checa_barema(r, base + ".barema", reg.get("barema"))
                mx = val(reg.get("pontuacao_maxima"))
                tetos = [g.get("teto") for g in reg.get("grupos") or []]
                if tetos and all(isinstance(t, (int, float)) for t in tetos):
                    s = sum(tetos)
                    if isinstance(mx, (int, float)):
                        if s < mx - 0.011 or (s > mx + 0.011 and val(reg.get("teto_geral")) is None):
                            r.aviso_edital(base + ".grupos", f"soma dos tetos {s} ≠ máximo {mx} (sem teto geral)")
                    elif padrao:
                        r.aviso(base + ".grupos", f"soma dos tetos dos grupos = {s}; pontuacao_maxima não declarada")
                for i, g in enumerate(reg.get("grupos") or []):
                    if g.get("peso") is not None and not isinstance(g.get("peso"), (int, float)):
                        r.erro(f"{base}.grupos[{i}].peso", "deveria ser número ou null")
                    cods_it = {str(it.get("codigo")) for it in g.get("itens") or []}
                    filhos = {}
                    for j, it in enumerate(g.get("itens") or []):
                        cp = it.get("codigo_pai")
                        if cp is not None:
                            if str(cp) not in cods_it:
                                r.erro(f"{base}.grupos[{i}].itens[{j}].codigo_pai", f"item-pai {cp!r} não está no grupo")
                            filhos.setdefault(str(cp), []).append(it)
                    for j, it in enumerate(g.get("itens") or []):
                        pai_tp = it.get("teto_pontos")
                        if str(it.get("codigo")) in filhos and isinstance(pai_tp, (int, float)):
                            for f in filhos[str(it.get("codigo"))]:
                                if isinstance(f.get("teto_pontos"), (int, float)) and f["teto_pontos"] > pai_tp:
                                    r.aviso_edital(f"{base}.grupos[{i}].itens[{j}]", f"subitem {f.get('codigo')} com teto {f['teto_pontos']} > teto do item-pai {pai_tp}")
                    for j, it in enumerate(g.get("itens") or []):
                        p = f"{base}.grupos[{i}].itens[{j}]"
                        if isinstance(it.get("teto_pontos"), (int, float)) and isinstance(g.get("teto"), (int, float)) and it["teto_pontos"] > g["teto"]:
                            r.aviso_edital(p + ".teto_pontos", f"{it['teto_pontos']} > teto do grupo {g['teto']}")
                        v, tq, tp = it.get("valor"), it.get("teto_quantidade"), it.get("teto_pontos")
                        if all(isinstance(x, (int, float)) for x in (v, tq, tp)) and v * tq < tp - 0.011:
                            r.aviso(p, f"valor × teto de quantidade = {v * tq} < teto de pontos {tp}")
            if m == "pratica":
                checa_barema(r, base + ".barema", reg.get("barema"))


def _temas_por_escopo(mod, pega):
    """Mapa {chave_de_escopo: [temas]} de um módulo; chave None é o padrão."""
    out = {}
    if not isinstance(mod, dict):
        return out
    t = pega(mod.get("padrao") or {})
    if t:
        out[None] = t
    for e in mod.get("por_escopo") or []:
        t = pega(e)
        if t:
            for c in e.get("codigos") or []:
                out[(e.get("eixo"), c)] = t
    return out


def _chave_fonte(f):
    f = f or {}
    return (f.get("documento"), f.get("item"))


def checa_temas_compartilhados(r, d):
    """Problema 12 da sessão 8: quando escrita e didática copiam a mesma lista de temas
    (mesma fonte, mesmo escopo), as duas cópias têm de ser idênticas."""
    esc = _temas_por_escopo(d.get("escrita"), lambda reg: (reg.get("conteudo") or {}).get("temas") or [])
    did = _temas_por_escopo(d.get("didatica"), lambda reg: reg.get("temas") or [])
    for chave in esc.keys() & did.keys():
        onde = "padrao" if chave is None else f"por_escopo[{chave[0]}={chave[1]}]"
        fontes_e = {_chave_fonte(t.get("fonte")): t for t in esc[chave]}
        fontes_d = {_chave_fonte(t.get("fonte")): t for t in did[chave]}
        for f in fontes_e.keys() & fontes_d.keys():
            le, ld = fontes_e[f].get("lista"), fontes_d[f].get("lista")
            if le != ld:
                r.erro(f"escrita.{onde}.conteudo.temas", f"lista com fonte {f[1]!r} difere da cópia em didatica.{onde}.temas ({len(le or [])} × {len(ld or [])} itens ou texto diferente)")


def checa_barema_contra_pontuacao(r, d):
    """Soma do barema de cada módulo contra a escala da fase no núcleo (mudança 5 do adendo da sessão 8):
    o barema é escrito na escala da fase e o peso entra depois; sem escala declarada, compara com o máximo.
    Divergência é erro, aceito com --aceitar-conflitos quando há conflito_interno registrado."""
    pont = ((d.get("estrutura_de_pontuacao") or {}).get("padrao") or {}).get("fases") or []
    maximos = {f.get("etapa_ref"): (f.get("escala") if isinstance(f.get("escala"), (int, float)) else f.get("maximo"))
               for f in pont if isinstance(f.get("maximo"), (int, float)) or isinstance(f.get("escala"), (int, float))}
    locais = {"didatica": "barema", "escrita": "avaliacao.barema", "pratica": "barema", "titulos": "barema"}
    for m, cam in locais.items():
        mod = d.get(m)
        if not isinstance(mod, dict) or m not in maximos:
            continue
        achou, b = resolve(mod.get("padrao") or {}, cam)
        if not achou or not isinstance(b, dict):
            continue
        for i, f in enumerate(b.get("fichas") or []):
            sd = f.get("soma_declarada")
            if isinstance(sd, (int, float)) and f.get("peso") is None and abs(sd - maximos[m]) > 0.011:
                r.aviso_edital(f"{m}.padrao.{cam}.fichas[{i}].soma_declarada",
                       f"{sd} ≠ escala (ou máximo, sem escala) da fase no núcleo {maximos[m]}")


# ----------------------------------------------------------------------------- triagem

def checa_triagem(r, fichas):
    caminhos = set()
    if not isinstance(fichas, list):
        r.erro("triagem", "deveria ser lista de fichas")
        return caminhos
    for i, f in enumerate(fichas):
        p = f"triagem[{i}]"
        if not isinstance(f, dict):
            r.erro(p, "ficha deveria ser objeto")
            continue
        checa_chaves(r, p, f, ["caminho", "url", "sha256", "versao", "conversao", "tipo_provavel_vigia", "concurso",
                               "pertence", "tipo", "divergencia_com_vigia", "numero_literal", "data_publicacao",
                               "escopo", "leitura", "versao_anterior", "triado_em"])
        if f.get("caminho"):
            caminhos.add(f["caminho"])
        if f.get("conversao") not in {"docling", "pdftotext", "texto_colado", None}:
            r.erro(p + ".conversao", "fora da lista")
        pert = f.get("pertence") or {}
        pv = pert.get("valor") if isinstance(pert, dict) else pert
        if pv not in {"sim", "nao", "verificar"}:
            r.erro(p + ".pertence", "valor fora da lista")
        if pv == "nao" and (pert.get("motivo") if isinstance(pert, dict) else None) not in MOTIVOS_NAO_PERTENCE:
            r.erro(p + ".pertence.motivo", "não pertencer exige motivo da lista")
        t = f.get("tipo")
        if t not in TIPOS_DOCUMENTO:
            r.erro(p + ".tipo", f"fora da lista: {t}")
        if f.get("tipo_provavel_vigia") and f.get("divergencia_com_vigia") not in (None, f.get("tipo_provavel_vigia")):
            r.erro(p + ".divergencia_com_vigia", "deveria ser null ou o palpite do vigia")
        lei = f.get("leitura")
        if lei not in LEITURAS:
            r.erro(p + ".leitura", "fora da lista")
        if pv == "nao" and lei != "nao_le":
            r.erro(p + ".leitura", "documento que não pertence deve ter leitura nao_le")
        if pv == "sim" and t in LEITURA_POR_TIPO and lei != LEITURA_POR_TIPO[t]:
            r.erro(p + ".leitura", f"para tipo {t} esperado {LEITURA_POR_TIPO[t]}")
        if pv == "sim" and t not in LEITURA_POR_TIPO and lei != "le" and t != "documento_externo":
            r.erro(p + ".leitura", f"para tipo {t} esperado le")
        dp = f.get("data_publicacao")
        if dp is None and pv == "sim":
            r.erro(p + ".data_publicacao", "sem data: use {valor: null, fonte: null, verificar_no_pdf: {...}}")
        elif isinstance(dp, dict):
            if dp.get("valor") is None and "verificar_no_pdf" not in dp:
                r.erro(p + ".data_publicacao", "valor null exige verificar_no_pdf")
            checa_data_iso(r, p + ".data_publicacao", dp.get("valor"))
            item = ((dp.get("fonte") or {}).get("item") or "").lower()
            if dp.get("valor") and item not in {"dou", "diario-citado", "link", "assinatura", "documento-pai", "servidor"}:
                r.erro(p + ".data_publicacao.fonte.item", "deve dizer qual data foi usada: DOU, diario-citado, link, assinatura, documento-pai ou servidor")
            if item == "diario-citado" and dp.get("valor"):
                # Decisão da sessão 15 (03/10/2026): data em diário oficial declarada por outro documento do concurso.
                fo = dp.get("fonte") or {}
                if not fo.get("documento") or not fo.get("trecho"):
                    r.erro(p + ".data_publicacao.fonte", "diário citado exige o documento que declara a publicação e o trecho")
                elif fo.get("documento") == f.get("caminho"):
                    r.erro(p + ".data_publicacao.fonte.documento", "diário citado é a data declarada por outro documento; no próprio documento, use DOU")
            if item == "servidor" and dp.get("valor"):
                # Decisão da sessão 14 (03/10/2026): Last-Modified do servidor, última fonte, limite superior da publicação.
                try:
                    iso = parsedate_to_datetime(((dp.get("fonte") or {}).get("trecho") or "")).date().isoformat()
                except (TypeError, ValueError, IndexError):
                    iso = None
                if iso is None:
                    r.erro(p + ".data_publicacao.fonte.trecho", "data do servidor exige o cabeçalho Last-Modified como está")
                elif iso != dp.get("valor"):
                    r.erro(p + ".data_publicacao", "valor diferente da data do cabeçalho Last-Modified")
                else:
                    r.aviso(p + ".data_publicacao", "datada pelo servidor (Last-Modified): limite superior da publicação")
            if item == "link" and dp.get("valor"):
                # adendo da sessão 9, item 8: só vale data que abre o texto do link (dd/mm/aaaa) ou, no fim do texto,
                # data sozinha entre parênteses, (dd-mm-aaaa) ou (dd/mm/aaaa); o valor tem de ser essa data.
                # Decisão da sessão 12 (02/10/2026): vale também o fim do link do SIGRH, " - dd/mm/aaaa | hh:mm".
                trecho = ((dp.get("fonte") or {}).get("trecho") or "")
                # Decisão da sessão 14 (03/10/2026): vale também o fim do link do IFMT, "Segunda-feira, 28 de Setembro de 2026".
                iso = data_do_texto_do_link(trecho)
                if iso is None:
                    r.erro(p + ".data_publicacao.fonte.trecho",
                           "data do link exige trecho com o texto do link começando por dd/mm/aaaa, terminando em (dd-mm-aaaa), "
                           "terminando em ' - dd/mm/aaaa | hh:mm' (SIGRH) ou terminando em dia da semana e data por extenso (IFMT)")
                elif iso != dp.get("valor"):
                    r.erro(p + ".data_publicacao", "valor diferente da data do texto do link")
            if item == "assinatura" and t in {"retificacao", "retificacao_cronograma", "retificacao_portaria_banca"}:
                r.aviso(p + ".data_publicacao", "retificação datada pela assinatura; a ordem da cadeia pode diferir da publicação")
        checa_data_iso(r, p + ".triado_em", f.get("triado_em"))
        va = f.get("versao_anterior")
        if va is not None and not (isinstance(va, dict) and {"caminho", "versao", "conteudo_mudou"} <= set(va)):
            r.erro(p + ".versao_anterior", "deveria ser null ou {caminho, versao, conteudo_mudou}")
    outros = [f for f in fichas if isinstance(f, dict) and f.get("tipo") == "outro"]
    if outros:
        r.aviso("triagem", f"{len(outros)} documento(s) de tipo 'outro'")
    return caminhos


# ----------------------------------------------------------------------------- principal

PACOTE = {"ativo": False}


def no_escopo(ficha, edital):
    esc = ficha.get("escopo")
    v = esc.get("valor") if isinstance(esc, dict) else esc
    return v in (None, "geral") or (isinstance(v, list) and edital in v)


def main():
    ap = argparse.ArgumentParser(description="Valida concurso-<slug>.json (e a triagem), ou só a triagem.")
    ap.add_argument("arquivo", nargs="?", help="concurso-<slug>.json; sem ele, valida só a triagem")
    ap.add_argument("--triagem")
    ap.add_argument("--aceitar-conflitos", action="store_true")
    a = ap.parse_args()
    if not a.arquivo and not a.triagem:
        ap.error("informe o arquivo do concurso, a triagem ou os dois")

    if not a.arquivo:
        r = Relatorio([], False)
        with open(a.triagem, encoding="utf-8") as f:
            checa_triagem(r, json.load(f))
        sys.exit(r.imprimir())

    with open(a.arquivo, encoding="utf-8") as f:
        d = json.load(f)
    r = Relatorio(d.get("conflitos_internos") or [], a.aceitar_conflitos)

    triagem_caminhos = None
    if a.triagem:
        with open(a.triagem, encoding="utf-8") as f:
            fichas = json.load(f)
        triagem_caminhos = checa_triagem(r, fichas)
        # edital de pacote (sessão 14): a triagem é do pacote; valem só as fichas cujo escopo inclui este edital
        slug = os.path.basename(a.arquivo)[len("concurso-"):-len(".json")]
        if isinstance(fichas, list) and fichas and all(isinstance(x, dict) and x.get("concurso") != slug for x in fichas):
            PACOTE["ativo"] = True
            triagem_caminhos = {x["caminho"] for x in fichas if x.get("caminho") and no_escopo(x, slug)}

    esq = esqueleto()
    # módulos: o esqueleto tem null; para a forma, usamos o esqueleto de cada módulo
    for m in MODULOS_NOMES:
        esq[m] = MODULOS[m]()
    # controle é cru
    checa_chaves(r, "controle", d.get("controle") or {}, esq["controle"].keys())
    for k in esq:
        if k == "controle":
            continue
        if k not in d:
            r.erro(k, "chave ausente no nível superior")
            continue
        v = d[k]
        modelo = esq[k]
        if k in ("carreira", "cidade_uf") and isinstance(v, dict) and "padrao" in v:
            checa_vf(r, k + ".padrao", v.get("padrao"), triagem_caminhos)
            for i, reg in enumerate(v.get("por_escopo") or []):
                checa_vf(r, f"{k}.por_escopo[{i}].valor_escopo", reg.get("valor_escopo"), triagem_caminhos)
            continue
        if isinstance(modelo, dict) and "padrao" in modelo and "por_escopo" in modelo:
            checa_escopo(r, k, v, modelo["padrao"], triagem_caminhos)
        elif isinstance(modelo, dict) and modelo:
            checa_conteiner_contra_esqueleto(r, k, v, modelo, triagem_caminhos)
        elif isinstance(modelo, list):
            if not isinstance(v, list):
                r.erro(k, "deveria ser lista")
            else:
                for i, item in enumerate(v):
                    if k in ("eventos", "alteracoes", "pendencias", "conflitos_internos", "lotacoes", "bancas",
                             "homologados", "impugnacoes", "vagas", "inscritos_homologados",
                             "recursos_administrativos", "acesso_a_documentos"):
                        if not isinstance(item, dict):
                            r.erro(f"{k}[{i}]", "deveria ser objeto")
                        elif k not in ("pendencias", "conflitos_internos", "lotacoes"):
                            checa_fonte(r, f"{k}[{i}]", item.get("fonte"), triagem_caminhos,
                                        exige="verificar_no_pdf" not in item)
        else:
            if k == "carreira" and isinstance(v, dict) and v.get("valor") == "outra":
                v = {kk: vv for kk, vv in v.items() if kk != "literal"}  # literal conferido em checa_identificacao
            checa_vf(r, k, v, triagem_caminhos)
    extras = set(d) - set(esq) - {"vinculo"}
    if extras:
        r.erro("(raiz)", f"chaves desconhecidas: {sorted(extras)}")
    if "vinculo" in d:
        # sessão 15: preparado para professor substituto; ausente quer dizer cargo efetivo
        vin = d["vinculo"]
        if not (isinstance(vin, dict) and vin.get("valor") in {"efetivo", "substituto"}):
            r.erro("vinculo", "deveria ser {valor: 'efetivo' ou 'substituto', fonte}")
        else:
            checa_vf(r, "vinculo", vin, triagem_caminhos)

    checa_controle(r, d)
    checa_identificacao(r, d)
    checa_vagas(r, d)
    checa_remuneracao(r, d)
    checa_inscricao(r, d)
    checa_reserva(r, d)
    checa_etapas(r, d)
    checa_eventos(r, d)
    checa_alteracoes(r, d)
    checa_pendencias(r, d)
    checa_recursos_apuracao(r, d)
    checa_bancas(r, d)
    checa_homologados(r, d)
    checa_modulos(r, d)
    checa_temas_compartilhados(r, d)
    checa_barema_contra_pontuacao(r, d)
    checa_essenciais(r, d)

    sys.exit(r.imprimir())


if __name__ == "__main__":
    main()
