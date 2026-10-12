"""Modelos de mensagem dos alertas para a API oficial do WhatsApp (Cloud API).

Mensagem que a empresa inicia só sai por modelo aprovado pela Meta. O modelo tem texto
fixo e variáveis {{1}}, {{2}}...; a Meta recusa variável com quebra de linha (erro 132018),
modelo que começa ou termina em variável e corpo acima de 1.024 caracteres. Este módulo
guarda os dois modelos que o Samuel aprova uma vez (datas e concurso novo) e converte o
que o leitor dos alertas e o casamento produzem nos parâmetros de cada modelo, já dentro
desses limites. O envio (a escrever) usa só estas funções, para que o texto que sai seja
o texto aprovado.
"""
import re

LIMITE_CORPO = 1024
MAX_PARTES = 3
RODAPE = "Para não receber mais, responda SAIR."

DATAS = {
    "nome": "alerta_datas_concurso",
    "categoria": "UTILITY",
    "idioma": "pt_BR",
    "corpo": ("Radar Aula Nota 10: aviso do concurso {{1}} para {{2}}.\n\n"
              "{{3}}\n\n"
              "Confira nos documentos oficiais ({{4}}). A informação oficial é sempre a do edital e dos documentos da instituição."),
    "rodape": RODAPE,
    "exemplo": [
        "IFMG 1077/2026",
        "a área Pedagogia (AEE)",
        "Novo documento publicado: 09/10/2026, Retificação 01 do edital (novas vagas). "
        "Datas que se aproximam: 14/10/2026 (quarta), último dia das solicitações de isenção "
        "da taxa de inscrição (faltam 2 dias).",
        "https://portal.concursos.ifmg.edu.br/",
    ],
}

CONCURSO_NOVO = {
    "nome": "alerta_concurso_novo",
    "categoria": "UTILITY",
    "idioma": "pt_BR",
    "corpo": ("Radar Aula Nota 10, alerta do seu acompanhamento de concursos: saiu o concurso {{1}}, "
              "com vaga que pode servir à formação que você informou no cadastro.\n\n"
              "Vaga: {{2}}.\n"
              "Inscrições: {{3}}.\n"
              "Requisito no edital: {{4}}\n\n"
              "Confira o requisito completo no edital ({{5}}). Quem decide o enquadramento é a banca, "
              "pelo texto do edital."),
    "rodape": RODAPE,
    "exemplo": [
        "IFRN 15/2026",
        "Química, área 12",
        "até 20/11/2026",
        "Graduação em Química (licenciatura ou bacharelado) e mestrado em Química ou Engenharia Química.",
        "https://portal.ifrn.edu.br/",
    ],
}

MODELOS = (DATAS, CONCURSO_NOVO)


def limpa(s):
    """Parâmetro em uma linha: sem quebra, sem tabulação e sem mais de 4 espaços seguidos."""
    s = re.sub(r"\s*\n\s*", " ", str(s or "")).replace("\t", " ")
    return re.sub(r" {2,}", " ", s).strip()


def corta(s, n, sufixo=" (continua no edital)"):
    s = limpa(s)
    if len(s) <= n:
        return s
    corte = s[:n - len(sufixo)].rsplit(" ", 1)[0].rstrip(",;:. ")
    return corte + sufixo


def render(modelo, params):
    txt = modelo["corpo"]
    for i, p in enumerate(params, 1):
        txt = txt.replace("{{%d}}" % i, p)
    return txt


def problemas(modelo, params):
    """Lista vazia quando a mensagem passa nos limites da Meta."""
    out = []
    n = len(re.findall(r"\{\{\d+\}\}", modelo["corpo"]))
    if len(params) != n:
        out.append(f"{len(params)} parâmetros para {n} variáveis")
    for i, p in enumerate(params, 1):
        if not p:
            out.append(f"parâmetro {i} vazio")
        if "\n" in p or "\t" in p or "     " in p:
            out.append(f"parâmetro {i} com quebra de linha, tabulação ou espaços seguidos")
    if len(render(modelo, params)) > LIMITE_CORPO:
        out.append(f"corpo com {len(render(modelo, params))} caracteres (limite {LIMITE_CORPO})")
    return out


# ------------------------------------------------------------------ datas

def _blocos_da_fila(texto):
    """Separa a mensagem do leitor (agenda.mensagem) em cabeçalho, itens, fonte e link."""
    linhas = texto.split("\n")
    cab = linhas[0]
    itens, fonte, link = [], "", ""
    for l in linhas[1:]:
        if not l.strip() or l.startswith("Para não receber"):
            continue
        if l.startswith("Fonte: "):
            fonte = l[len("Fonte: "):].rstrip(".")
        elif l.startswith("A informação oficial"):
            m = re.search(r"Confira em (.+)\.$", l)
            link = m.group(1) if m else ""
        else:
            itens.append(l)
    return cab, itens, fonte, link


def _frase(itens):
    """Itens do leitor em uma linha: 'Novo documento publicado: X. • a. Datas...: • b.'"""
    partes = []
    for l in itens:
        l = l.strip()
        if l.startswith("• "):
            l = l[2:]
        if not l.endswith((".", ":")):
            l += "."
        partes.append(l)
    return " ".join(partes)


def params_datas(texto, concurso, area):
    """Converte uma mensagem da fila de datas em uma ou mais mensagens do modelo DATAS.

    Quando o conteúdo não cabe em uma, divide pelos itens, na ordem, e numera as partes
    no próprio parâmetro do conteúdo ('Parte 1 de 2.'). Devolve lista de listas de parâmetros.
    """
    _, itens, fonte, link = _blocos_da_fila(texto)
    link = link or "site da instituição"
    area = limpa(area)
    area = f"a área {area}" if area and area != "todas as áreas" else "todas as áreas"
    # a fonte fica só na fila interna (conferência); ao aluno basta o link (decisão de 12/10)
    base = [limpa(concurso), area, "", link]
    fixo = len(render(DATAS, base))
    cabe = LIMITE_CORPO - fixo - len("Parte 10 de 10. ")

    grupos, atual, cab_atual = [], [], None
    for l in itens:
        eh_cab = not l.startswith("• ")
        if eh_cab:
            cab_atual = l
        teste = _frase(atual + [l])
        if atual and len(teste) > cabe:
            grupos.append(atual)
            atual = [] if eh_cab else [cab_atual + " (continuação)"]
        atual.append(l)
    if atual:
        grupos.append(atual)

    # cronograma inteiro (UFRGS 09, UFSM 198) não vira sete mensagens: no máximo MAX_PARTES,
    # e a última diz quantas datas ficaram de fora e manda ao documento
    if len(grupos) > MAX_PARTES:
        sobra = sum(1 for g in grupos[MAX_PARTES - 1:] for l in g if l.startswith("• "))
        ultimo = list(grupos[MAX_PARTES - 1])
        aviso = f"Há mais {sobra} data(s) neste aviso; veja todas no documento."
        while ultimo and len(_frase(ultimo + [aviso])) > cabe:
            ultimo.pop()
        mostradas = sum(1 for l in ultimo if l.startswith("• "))
        aviso = f"Há mais {sobra - mostradas} data(s) neste aviso; veja todas no documento."
        grupos = grupos[:MAX_PARTES - 1] + [ultimo + [aviso]]

    out = []
    for i, g in enumerate(grupos, 1):
        conteudo = _frase(g)
        if len(grupos) > 1:
            conteudo = f"Parte {i} de {len(grupos)}. " + conteudo
        conteudo = corta(conteudo, cabe + len("Parte 10 de 10. "))
        out.append([base[0], base[1], conteudo, base[3]])
    return out


def ler_fila(caminho):
    """Mensagens da fila.md do leitor: [(concurso, rótulo de área, texto)]."""
    t = open(caminho, encoding="utf-8").read()
    out = []
    for m in re.finditer(r"\*\*Para: (.+?) · (.+?)\*\*\n\n```\n(.*?)\n```", t, re.S):
        concurso, rot, texto = m.groups()
        cab = texto.split("\n")[0].split(" · ")
        area = cab[2] if len(cab) > 2 else ("todas as áreas" if rot.startswith("todas") else rot)
        out.append((concurso, area, rot, texto))
    return out


# ------------------------------------------------------------------ concurso novo

def params_concurso_novo(nome_concurso, vagas, inscricao_fim, requisito, link, prazo_varia=False):
    """vagas: lista de rótulos ('Química, área 12'). requisito: o texto já montado pelo chamador
    (quando as vagas têm requisitos diferentes, ele diz isso e traz o da primeira)."""
    if inscricao_fim:
        y, m, d = str(inscricao_fim)[:10].split("-")
        insc = f"até {d}/{m}/{y}" + (", mas o prazo varia por vaga; confira no edital" if prazo_varia else "")
    else:
        insc = "confira o prazo no edital"
    rot = "; ".join(vagas[:3]) + (f" e mais {len(vagas) - 3}" if len(vagas) > 3 else "")
    p = [limpa(nome_concurso), corta(rot, 200), insc, "", limpa(link) or "site da instituição"]
    cabe = LIMITE_CORPO - len(render(CONCURSO_NOVO, p))
    p[3] = corta(requisito or "veja o edital", min(cabe, 400))
    return p
