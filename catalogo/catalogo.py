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
        self._ga_chaves = {chave(g) for g in self.grandes_areas} | {
            "ciencias exatas e da terra", "ciencias biologicas", "engenharias", "ciencias da saude",
            "ciencias agrarias", "ciencias sociais aplicadas", "ciencias humanas",
            "linguistica letras e artes", "outra", "multidisciplinar"}

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

    def e_subarea_de(self, nome, acima):
        """True se, na tabela do CNPq, `nome` fica abaixo de `acima` (Fitotecnia está em
        Agronomia). Usa a grafia dada e a canônica dos dois lados."""
        hier = self.dados.get("hierarquia_cnpq", {})
        if self._ga_norm.get(normalizar(acima)) or chave(acima) in self._ga_chaves:
            return False  # estar na mesma grande área não aproxima dois programas
        alvos = {chave(acima)}
        ca = self.nome_canonico(acima)
        if ca:
            alvos.add(chave(ca))
        for n in {nome, self.nome_canonico(nome) or nome}:
            if alvos & set(hier.get(chave(n), [])):
                return True
        return False

    def comeca_com(self, nome, inicio, contexto=None):
        """True se o nome do candidato começa pelo nome do edital, palavra a palavra
        ("Letras Português" começa por "Letras"), e os dois ficam na mesma área de
        avaliação, ou o nome do edital é genérico ("Engenharia"). Assim "Medicina
        Veterinária" não passa por "Medicina" nem "Educação Física" por "Educação".
        "Ciências" sozinho não vale (Ciências Sociais, Ciências Biológicas)."""
        ki = chave(inicio)
        if ki in ("ciencias", "ciencia", ""):
            return False
        c = self.nome_canonico(nome, contexto)
        ks = {chave(nome)} | ({chave(c)} if c else set())
        if not any(k != ki and k.startswith(ki + " ") for k in ks):
            return False
        fi, fn = self.resolver(inicio, contexto), self.resolver(nome, contexto)
        if not fn or not fi or not fi.get("area_avaliacao"):
            return True  # nome do candidato fora do catálogo, ou nome do edital genérico
        return fi.get("area_avaliacao") == fn.get("area_avaliacao")

    def resto_do_nome(self, nome, inicio):
        """O que sobra do nome do candidato depois do nome do edital
        ("Letras Língua Portuguesa" menos "Letras" = "lingua portuguesa")."""
        k, ki = chave(nome), chave(inicio)
        return k[len(ki):].strip() if k.startswith(ki + " ") else ""

    def areas_do_tema(self, nome, contexto=None):
        """Áreas de avaliação de um tema que pode não estar no catálogo (área do concurso,
        tema de tese): pelo catálogo; se não houver, pelo termo mais próximo acima dele
        na tabela do CNPq que o catálogo conheça."""
        partes = [nome or ""] + [x for x in re.split(r"[,:;/()]| subarea | subárea ", nome or "") if x.strip()]
        for parte in partes:
            p, alt = self.areas_da_formacao(parte.strip(), contexto)
            if p:
                return {x for x in [p] + alt if x}
        for parte in partes:
            acima = self.dados.get("hierarquia_cnpq", {}).get(chave(parte), [])
            for termo in acima:  # do mais próximo ao mais geral
                p, alt = self.areas_da_formacao(termo, contexto)
                if p:
                    return {x for x in [p] + alt if x}
        return set()

    def opcoes_graduacao(self):
        """Lista para o formulário do candidato: cursos que aparecem como graduação."""
        return sorted(n for n, f in self.formacoes.items()
                      if "graduacao" in f.get("aparece_como", []) and f["tipo"] != "grande_area")
