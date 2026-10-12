"""Catálogo de formações do alerta de concurso novo (Radar, Aula Nota 10).

Lê catalogo/formacoes.json e resolve um nome de formação, do jeito que o edital ou o
candidato escreveu, para o nome canônico do catálogo, com a grande área e a área de
avaliação da CAPES. Não interpreta requisito: isso o extrator já faz no campo
vagas[].requisito_interpretado. Aqui só se normalizam nomes.

Uso como módulo:
    from catalogo import Catalogo
    cat = Catalogo.carregar()
    cat.resolver("Licenciatura em Química")          -> registro de "Química"
    cat.resolver("Ciências", contexto="pos")         -> título genérico de pós
"""
import json, os, re, unicodedata

AQUI = os.path.dirname(os.path.abspath(__file__))
ARQUIVO = os.path.join(AQUI, "formacoes.json")

# prefixos e sufixos de grau que não mudam a formação ("Licenciatura em Química" = "Química")
_PREFIXOS = (r"^(curso (superior )?de |graduacao (plena )?em |licenciatura (plena )?(em |de )?|"
             r"bacharelado (em |de )?|bacharel em |licenciado em |tecnologo em |tecnologia em |"
             r"curso superior de tecnologia em |superior de tecnologia em |habilitacao em )+")
_SUFIXOS = r" (licenciatura|bacharelado)( plena)?$"

NIVEIS_ACADEMICOS = ["especializacao", "mestrado", "doutorado", "livre_docencia"]


def sem_acento(s):
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()


def normalizar(s):
    """minúsculas, sem acento, só letras, números e espaço simples."""
    s = sem_acento(s or "").lower()
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def chave(s):
    """Chave de busca: normalizada e sem as palavras de grau."""
    n = normalizar(s)
    k = re.sub(_PREFIXOS, "", n)
    k = re.sub(_SUFIXOS, "", k).strip()
    return k or n


class Catalogo:
    def __init__(self, dados):
        self.dados = dados
        self.formacoes = {f["nome"]: f for f in dados["formacoes"]}
        self.sinonimos = dados["sinonimos"]
        self.sinonimos_pos = dados.get("sinonimos_pos", {})
        self.areas = {a["nome"]: a for a in dados["areas_avaliacao"]}
        self._areas_norm = {normalizar(a): a for a in self.areas}
        self.grandes_areas = dados["grandes_areas"]
        self._ga_norm = {normalizar(g): g for g in self.grandes_areas}

    @classmethod
    def carregar(cls, arquivo=ARQUIVO):
        with open(arquivo, encoding="utf-8") as f:
            return cls(json.load(f))

    # ------------------------------------------------------------ resolução
    def nome_canonico(self, nome, contexto=None):
        """Nome canônico ou None se o catálogo não conhece o nome.
        contexto: 'graduacao' ou 'pos'; alguns nomes mudam de sentido ("Ciências")."""
        if not nome:
            return None
        k = chave(nome)
        if contexto == "pos" and k in self.sinonimos_pos:
            return self.sinonimos_pos[k]
        if k in self.sinonimos:
            return self.sinonimos[k]
        if nome in self.formacoes:
            return nome
        return None

    def resolver(self, nome, contexto=None):
        c = self.nome_canonico(nome, contexto)
        return self.formacoes.get(c) if c else None

    def area_avaliacao_exata(self, nome):
        """Se o nome é uma das 50 áreas de avaliação, devolve o nome oficial."""
        return self._areas_norm.get(normalizar(nome))

    def grande_area_de(self, nome):
        """Grande área da CAPES que um nome designa, pelo nome direto ou pelo catálogo."""
        ga = self._ga_norm.get(normalizar(nome))
        if ga:
            return ga
        f = self.resolver(nome)
        return f["grande_area"] if f else None

    def areas_da_formacao(self, nome, contexto=None):
        """(principal, alternativas) de área de avaliação pelo catálogo."""
        f = self.resolver(nome, contexto)
        if not f:
            a = self.area_avaliacao_exata(nome or "")
            return (a, []) if a else (None, [])
        return f.get("area_avaliacao"), list(f.get("areas_alternativas") or [])

    def opcoes_graduacao(self):
        """Lista para o formulário do candidato: cursos que aparecem como graduação."""
        return sorted(n for n, f in self.formacoes.items()
                      if "graduacao" in f.get("aparece_como", []) and f["tipo"] != "grande_area")
